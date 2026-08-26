from __future__ import annotations

import argparse
import os
import uuid
from dataclasses import dataclass

from database.fpa_raw.schema import ENTITY_ORDER, FOREIGN_KEYS, PRIMARY_KEYS
from .schema import ACCEPTED_VALUES, BUSINESS_PREDICATES, staging_name


@dataclass(frozen=True)
class TestResult:
    test_name: str
    entity: str | None
    issue_count: int
    details: str

    @property
    def status(self) -> str:
        return "PASS" if self.issue_count == 0 else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the STAGING structural acceptance suite.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before validating STAGING.")
    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before validating STAGING.") from exc

    quality_run_id = uuid.uuid4()
    results: list[TestResult] = []

    def add(test_name: str, entity: str | None, issue_count: int, details: str) -> None:
        result = TestResult(test_name, entity, int(issue_count), details)
        results.append(result)
        print(f"{result.status} {test_name}{f' [{entity}]' if entity else ''}: issues={result.issue_count}")

    with psycopg.connect(args.database_url) as connection:
        connection.execute(
            "INSERT INTO control.staging_quality_runs (quality_run_id, status) VALUES (%s, 'RUNNING')",
            (quality_run_id,),
        )
        connection.commit()
        try:
            actual_views = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.views WHERE table_schema = 'staging'"
                )
            }
            expected_views = {staging_name(entity) for entity in ENTITY_ORDER}
            add(
                "expected_view_set",
                None,
                len(actual_views.symmetric_difference(expected_views)),
                f"expected={len(expected_views)} actual={len(actual_views)}",
            )

            for entity in ENTITY_ORDER:
                view = staging_name(entity)
                raw_count = connection.execute(
                    sql.SQL("SELECT COUNT(*) FROM raw.{}").format(sql.Identifier(entity))
                ).fetchone()[0]
                staging_count = connection.execute(
                    sql.SQL("SELECT COUNT(*) FROM staging.{}").format(sql.Identifier(view))
                ).fetchone()[0]
                add(
                    "row_count_reconciliation",
                    entity,
                    abs(raw_count - staging_count),
                    f"raw={raw_count} staging={staging_count}",
                )

                type_mismatches = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.columns r
                    FULL JOIN information_schema.columns s
                      ON s.table_schema = 'staging'
                     AND s.table_name = %s
                     AND s.column_name = r.column_name
                    WHERE r.table_schema = 'raw'
                      AND r.table_name = %s
                      AND (
                          s.column_name IS NULL
                          OR r.data_type IS DISTINCT FROM s.data_type
                          OR r.numeric_precision IS DISTINCT FROM s.numeric_precision
                          OR r.numeric_scale IS DISTINCT FROM s.numeric_scale
                          OR r.character_maximum_length IS DISTINCT FROM s.character_maximum_length
                      )
                    """,
                    (view, entity),
                ).fetchone()[0]
                add("column_type_contract", entity, type_mismatches, "RAW and STAGING physical types must match")

                pk_columns = PRIMARY_KEYS[entity]
                null_predicate = sql.SQL(" OR ").join(
                    sql.SQL("{} IS NULL").format(sql.Identifier(column)) for column in pk_columns
                )
                null_pk_count = connection.execute(
                    sql.SQL("SELECT COUNT(*) FROM staging.{} WHERE ").format(sql.Identifier(view))
                    + null_predicate
                ).fetchone()[0]
                add("primary_key_not_null", entity, null_pk_count, ", ".join(pk_columns))

                group_columns = sql.SQL(", ").join(sql.Identifier(column) for column in pk_columns)
                duplicate_count = connection.execute(
                    sql.SQL(
                        "SELECT COALESCE(SUM(duplicate_rows), 0) FROM ("
                        "SELECT COUNT(*) - 1 AS duplicate_rows FROM staging.{} GROUP BY {} HAVING COUNT(*) > 1"
                        ") duplicates"
                    ).format(sql.Identifier(view), group_columns)
                ).fetchone()[0]
                add("primary_key_unique", entity, duplicate_count, ", ".join(pk_columns))

                metadata_issues = connection.execute(
                    sql.SQL(
                        "SELECT COUNT(*) FROM staging.{} WHERE ingestion_id IS NULL OR pipeline_run_id IS NULL "
                        "OR source_file IS NULL OR source_system IS NULL OR ingested_at IS NULL"
                    ).format(sql.Identifier(view))
                ).fetchone()[0]
                add("lineage_metadata_not_null", entity, metadata_issues, "technical lineage columns")

            for entity, relationships in FOREIGN_KEYS.items():
                child_view = staging_name(entity)
                for local_columns, target_entity, target_columns in relationships:
                    parent_view = staging_name(target_entity)
                    join_predicate = sql.SQL(" AND ").join(
                        sql.SQL("c.{} = p.{}").format(sql.Identifier(local), sql.Identifier(target))
                        for local, target in zip(local_columns, target_columns)
                    )
                    present_predicate = sql.SQL(" AND ").join(
                        sql.SQL("c.{} IS NOT NULL").format(sql.Identifier(column))
                        for column in local_columns
                    )
                    orphan_count = connection.execute(
                        sql.SQL(
                            "SELECT COUNT(*) FROM staging.{} c LEFT JOIN staging.{} p ON {} "
                            "WHERE {} AND p.{} IS NULL"
                        ).format(
                            sql.Identifier(child_view),
                            sql.Identifier(parent_view),
                            join_predicate,
                            present_predicate,
                            sql.Identifier(target_columns[0]),
                        )
                    ).fetchone()[0]
                    relationship = f"{','.join(local_columns)} -> {target_entity}.{','.join(target_columns)}"
                    add("relationship", entity, orphan_count, relationship)

            for (entity, column), allowed_values in ACCEPTED_VALUES.items():
                unexpected_count = connection.execute(
                    sql.SQL("SELECT COUNT(*) FROM staging.{} WHERE {} IS NOT NULL AND NOT ({} = ANY(%s))").format(
                        sql.Identifier(staging_name(entity)),
                        sql.Identifier(column),
                        sql.Identifier(column),
                    ),
                    (list(allowed_values),),
                ).fetchone()[0]
                add("accepted_values", entity, unexpected_count, f"{column}: {', '.join(allowed_values)}")

            for entity, predicates in BUSINESS_PREDICATES.items():
                for test_name, predicate in predicates:
                    issue_count = connection.execute(
                        sql.SQL("SELECT COUNT(*) FROM staging.{} WHERE ").format(
                            sql.Identifier(staging_name(entity))
                        )
                        + sql.SQL(predicate)
                    ).fetchone()[0]
                    add(test_name, entity, issue_count, predicate)

            balance_issues = connection.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT journal_entry_id
                    FROM staging.stg_journal_lines
                    GROUP BY journal_entry_id
                    HAVING ABS(SUM(debit_amount) - SUM(credit_amount)) > 0.01
                ) issues
                """
            ).fetchone()[0]
            add("journal_balance", "erp_journal_lines", balance_issues, "debit equals credit by journal entry")

            header_line_issues = connection.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT e.journal_entry_id
                    FROM staging.stg_journal_entries e
                    LEFT JOIN staging.stg_journal_lines l USING (journal_entry_id)
                    GROUP BY e.journal_entry_id, e.line_count, e.total_debit_amount, e.total_credit_amount
                    HAVING e.line_count <> COUNT(l.journal_line_id)
                       OR ABS(e.total_debit_amount - COALESCE(SUM(l.debit_amount), 0)) > 0.01
                       OR ABS(e.total_credit_amount - COALESCE(SUM(l.credit_amount), 0)) > 0.01
                ) issues
                """
            ).fetchone()[0]
            add("journal_header_line_reconciliation", "erp_journal_entries", header_line_issues, "header totals equal lines")

            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO control.staging_quality_results (
                        quality_run_id, test_name, source_entity, status, issue_count, details
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            quality_run_id,
                            result.test_name,
                            result.entity,
                            result.status,
                            result.issue_count,
                            result.details,
                        )
                        for result in results
                    ],
                )
            failed = sum(result.status == "FAIL" for result in results)
            passed = len(results) - failed
            connection.execute(
                """
                UPDATE control.staging_quality_runs
                SET ended_at = clock_timestamp(), status = %s, tests_passed = %s, tests_failed = %s
                WHERE quality_run_id = %s
                """,
                ("FAILED" if failed else "PASSED", passed, failed, quality_run_id),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            connection.execute(
                """
                UPDATE control.staging_quality_runs
                SET ended_at = clock_timestamp(), status = 'FAILED', error_message = %s
                WHERE quality_run_id = %s
                """,
                (str(exc)[:4000], quality_run_id),
            )
            connection.commit()
            raise

    failed_results = [result for result in results if result.status == "FAIL"]
    if failed_results:
        raise SystemExit(f"STAGING validation failed: {len(failed_results)} tests with issues.")
    print(f"All STAGING acceptance checks passed ({len(results)} tests). quality_run_id={quality_run_id}")


if __name__ == "__main__":
    main()
