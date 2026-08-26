from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import uuid
from pathlib import Path

from .schema import (
    ACTUAL_ENTITIES,
    ENTITY_ORDER,
    PRIMARY_KEYS,
    discover_entity_files,
    generate_schema_sql,
)


PERIOD_PATTERN = re.compile(r"(\d{4})_(\d{2})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load master, planning and monthly Actual CSVs into RAW.")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--source-system", default="NEXA_ERP")
    parser.add_argument("--period", help="Load only one Actual batch, e.g. 2026-07; masters/planning still load.")
    parser.add_argument("--bootstrap", action="store_true", help="Create/verify the schema before loading.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reference_period(path: Path) -> str | None:
    match = PERIOD_PATTERN.search(path.parent.name) or PERIOD_PATTERN.search(path.stem)
    return f"{match.group(1)}-{match.group(2)}" if match else None


def select_files(dataset_root: Path, requested_period: str | None) -> list[tuple[str, Path]]:
    grouped = discover_entity_files(dataset_root)
    selected: list[tuple[str, Path]] = []
    normalized_period = requested_period.replace("-", "_") if requested_period else None
    for entity in ENTITY_ORDER:
        for path in grouped[entity]:
            if entity in ACTUAL_ENTITIES and normalized_period and path.parent.name != normalized_period:
                continue
            selected.append((entity, path))
    return selected


def load_file(connection, pipeline_run_id: uuid.UUID, entity: str, path: Path, columns: tuple[str, ...], source_system: str) -> tuple[str, int]:
    from psycopg import sql

    file_hash = sha256(path)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ingestion_id FROM raw.ingestion_control WHERE source_entity = %s AND file_sha256 = %s AND status = 'LOADED'",
            (entity, file_hash),
        )
        if cursor.fetchone():
            return "skipped", 0

    ingestion_id: int | None = None
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO raw.ingestion_control (
                        pipeline_run_id, source_system, source_entity, source_file, reference_period,
                        file_sha256, file_size_bytes, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'RECEIVED')
                    ON CONFLICT (source_entity, file_sha256) DO UPDATE SET
                        pipeline_run_id = EXCLUDED.pipeline_run_id,
                        started_at = clock_timestamp(), ended_at = NULL,
                        status = 'REPROCESSED', error_message = NULL
                    RETURNING ingestion_id
                    """,
                    (
                        pipeline_run_id,
                        source_system,
                        entity,
                        path.as_posix(),
                        reference_period(path),
                        file_hash,
                        path.stat().st_size,
                    ),
                )
                ingestion_id = cursor.fetchone()[0]
                temp_table = f"load_{entity}_{ingestion_id}"
                column_list = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
                cursor.execute(
                    sql.SQL("CREATE TEMP TABLE {} ON COMMIT DROP AS SELECT {} FROM raw.{} WITH NO DATA").format(
                        sql.Identifier(temp_table), column_list, sql.Identifier(entity)
                    )
                )
                copy_statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '', ENCODING 'UTF8')").format(
                    sql.Identifier(temp_table), column_list
                )
                with path.open("rb") as stream, cursor.copy(copy_statement) as copy:
                    while chunk := stream.read(1024 * 1024):
                        copy.write(chunk)
                cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(temp_table)))
                rows_received = cursor.fetchone()[0]
                pk_columns = PRIMARY_KEYS[entity]
                conflict_columns = sql.SQL(", ").join(sql.Identifier(column) for column in pk_columns)
                insert_statement = sql.SQL(
                    """
                    WITH inserted AS (
                        INSERT INTO raw.{} ({}, ingestion_id, pipeline_run_id, source_file, source_system)
                        SELECT {}, %s, %s, %s, %s FROM {}
                        ON CONFLICT ({}) DO NOTHING
                        RETURNING 1
                    ) SELECT COUNT(*) FROM inserted
                    """
                ).format(
                    sql.Identifier(entity),
                    column_list,
                    column_list,
                    sql.Identifier(temp_table),
                    conflict_columns,
                )
                cursor.execute(
                    insert_statement,
                    (ingestion_id, pipeline_run_id, path.as_posix(), source_system),
                )
                rows_loaded = cursor.fetchone()[0]
                cursor.execute(
                    """
                    UPDATE raw.ingestion_control
                    SET rows_received = %s, rows_loaded = %s, rows_rejected = %s,
                        ended_at = clock_timestamp(), status = 'LOADED'
                    WHERE ingestion_id = %s
                    """,
                    (rows_received, rows_loaded, rows_received - rows_loaded, ingestion_id),
                )
        return "loaded", rows_loaded
    except Exception as exc:
        connection.rollback()
        with connection.transaction():
            connection.execute(
                """
                INSERT INTO raw.ingestion_control (
                    pipeline_run_id, source_system, source_entity, source_file, reference_period,
                    file_sha256, file_size_bytes, status, ended_at, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'FAILED', clock_timestamp(), %s)
                ON CONFLICT (source_entity, file_sha256) DO UPDATE SET
                    pipeline_run_id = EXCLUDED.pipeline_run_id, status = 'FAILED',
                    ended_at = clock_timestamp(), error_message = EXCLUDED.error_message
                """,
                (
                    pipeline_run_id,
                    source_system,
                    entity,
                    path.as_posix(),
                    reference_period(path),
                    file_hash,
                    path.stat().st_size,
                    str(exc)[:4000],
                ),
            )
        raise


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before loading.")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before loading.") from exc

    dataset_root = args.dataset_root.resolve()
    ddl, headers = generate_schema_sql(dataset_root)
    files = select_files(dataset_root, args.period)
    pipeline_run_id = uuid.uuid4()
    files_loaded = files_skipped = rows_loaded = 0

    with psycopg.connect(args.database_url) as connection:
        if args.bootstrap:
            connection.execute(ddl)
            connection.commit()
        connection.execute(
            "INSERT INTO raw.pipeline_runs (pipeline_run_id, dataset_root, status) VALUES (%s, %s, 'RUNNING')",
            (pipeline_run_id, dataset_root.as_posix()),
        )
        connection.commit()
        try:
            for position, (entity, path) in enumerate(files, start=1):
                status, loaded = load_file(
                    connection,
                    pipeline_run_id,
                    entity,
                    path,
                    headers[entity],
                    args.source_system,
                )
                files_loaded += status == "loaded"
                files_skipped += status == "skipped"
                rows_loaded += loaded
                print(f"[{position:03d}/{len(files):03d}] {status:7s} {entity} <- {path.name} ({loaded:,} rows)")
            connection.execute(
                """
                UPDATE raw.pipeline_runs
                SET ended_at = clock_timestamp(), status = 'LOADED', files_loaded = %s,
                    files_skipped = %s, rows_loaded = %s
                WHERE pipeline_run_id = %s
                """,
                (files_loaded, files_skipped, rows_loaded, pipeline_run_id),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            connection.execute(
                """
                UPDATE raw.pipeline_runs
                SET ended_at = clock_timestamp(), status = 'FAILED', files_loaded = %s,
                    files_skipped = %s, rows_loaded = %s, error_message = %s
                WHERE pipeline_run_id = %s
                """,
                (files_loaded, files_skipped, rows_loaded, str(exc)[:4000], pipeline_run_id),
            )
            connection.commit()
            raise
    print(
        f"Pipeline {pipeline_run_id} completed: {files_loaded} files loaded, "
        f"{files_skipped} skipped, {rows_loaded:,} rows inserted."
    )


if __name__ == "__main__":
    main()
