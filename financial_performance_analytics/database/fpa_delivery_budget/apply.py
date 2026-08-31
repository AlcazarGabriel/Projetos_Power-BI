from __future__ import annotations

import argparse
import hashlib
import os
import uuid
from pathlib import Path

from .schema import LAYER_DDL, RAW_DDL, SOURCE_COLUMNS


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load and materialize the Delivery Budget extension.")
    parser.add_argument("extension_root", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--source-system", default="NEXA_PLANNING")
    parser.add_argument("--check", action="store_true", help="Validate the package and compile SQL only.")
    args = parser.parse_args()

    source_file = args.extension_root.resolve() / "erp_budget_delivery_plan.csv"
    if not source_file.is_file():
        raise SystemExit(f"Missing source file: {source_file}")
    if args.check:
        print(f"Delivery Budget contract compiled: {len(SOURCE_COLUMNS)} columns; source={source_file}")
        return
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before loading Delivery Budget.")
    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before loading Delivery Budget.") from exc

    pipeline_run_id = uuid.uuid4()
    source_hash = file_sha256(source_file)
    rows_loaded = 0
    skipped = False

    with psycopg.connect(args.database_url) as connection:
        connection.execute(RAW_DDL)
        connection.execute(
            "INSERT INTO raw.pipeline_runs (pipeline_run_id, dataset_root, status) VALUES (%s, %s, 'RUNNING')",
            (pipeline_run_id, args.extension_root.resolve().as_posix()),
        )
        connection.commit()
        try:
            existing = connection.execute(
                """
                SELECT ingestion_id
                FROM raw.ingestion_control
                WHERE source_entity = 'erp_budget_delivery_plan'
                  AND file_sha256 = %s
                  AND status = 'LOADED'
                """,
                (source_hash,),
            ).fetchone()
            if existing:
                skipped = True
            else:
                with connection.transaction():
                    ingestion_id = connection.execute(
                        """
                        INSERT INTO raw.ingestion_control (
                            pipeline_run_id, source_system, source_entity, source_file,
                            file_sha256, file_size_bytes, status
                        ) VALUES (%s, %s, 'erp_budget_delivery_plan', %s, %s, %s, 'RECEIVED')
                        ON CONFLICT (source_entity, file_sha256) DO UPDATE SET
                            pipeline_run_id = EXCLUDED.pipeline_run_id,
                            started_at = clock_timestamp(), ended_at = NULL,
                            status = 'REPROCESSED', error_message = NULL
                        RETURNING ingestion_id
                        """,
                        (
                            pipeline_run_id,
                            args.source_system,
                            source_file.as_posix(),
                            source_hash,
                            source_file.stat().st_size,
                        ),
                    ).fetchone()[0]
                    column_list = sql.SQL(", ").join(map(sql.Identifier, SOURCE_COLUMNS))
                    connection.execute(
                        sql.SQL("CREATE TEMP TABLE load_delivery_budget ON COMMIT DROP AS SELECT {} FROM raw.erp_budget_delivery_plan WITH NO DATA").format(column_list)
                    )
                    copy_sql = sql.SQL(
                        "COPY load_delivery_budget ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '', ENCODING 'UTF8')"
                    ).format(column_list)
                    with source_file.open("rb") as stream, connection.cursor().copy(copy_sql) as copy:
                        while chunk := stream.read(1024 * 1024):
                            copy.write(chunk)
                    rows_received = connection.execute("SELECT COUNT(*) FROM load_delivery_budget").fetchone()[0]
                    update_columns = sql.SQL(", ").join(
                        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
                        for column in SOURCE_COLUMNS
                        if column != "delivery_budget_plan_id"
                    )
                    upsert = sql.SQL(
                        """
                        INSERT INTO raw.erp_budget_delivery_plan (
                            {}, ingestion_id, pipeline_run_id, source_file, source_system
                        )
                        SELECT {}, %s, %s, %s, %s FROM load_delivery_budget
                        ON CONFLICT (delivery_budget_plan_id) DO UPDATE SET
                            {}, ingestion_id = EXCLUDED.ingestion_id,
                            pipeline_run_id = EXCLUDED.pipeline_run_id,
                            source_file = EXCLUDED.source_file,
                            source_system = EXCLUDED.source_system,
                            ingested_at = clock_timestamp()
                        RETURNING 1
                        """
                    ).format(column_list, column_list, update_columns)
                    rows_loaded = len(
                        connection.execute(
                            upsert,
                            (ingestion_id, pipeline_run_id, source_file.as_posix(), args.source_system),
                        ).fetchall()
                    )
                    connection.execute(
                        """
                        UPDATE raw.ingestion_control
                        SET rows_received = %s, rows_loaded = %s, rows_rejected = 0,
                            ended_at = clock_timestamp(), status = 'LOADED'
                        WHERE ingestion_id = %s
                        """,
                        (rows_received, rows_loaded, ingestion_id),
                    )

            connection.execute(LAYER_DDL)
            connection.execute(
                """
                UPDATE raw.pipeline_runs
                SET ended_at = clock_timestamp(), status = 'LOADED',
                    files_loaded = %s, files_skipped = %s, rows_loaded = %s
                WHERE pipeline_run_id = %s
                """,
                (0 if skipped else 1, 1 if skipped else 0, rows_loaded, pipeline_run_id),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            connection.execute(
                """
                UPDATE raw.pipeline_runs
                SET ended_at = clock_timestamp(), status = 'FAILED', error_message = %s
                WHERE pipeline_run_id = %s
                """,
                (str(exc)[:4000], pipeline_run_id),
            )
            connection.commit()
            raise

    action = "skipped; layers refreshed" if skipped else f"loaded {rows_loaded} rows"
    print(f"Delivery Budget pipeline {pipeline_run_id}: {action}.")


if __name__ == "__main__":
    main()

