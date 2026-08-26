from __future__ import annotations

import argparse
import os
import uuid
from dataclasses import dataclass


EXPECTED_OBJECTS = {
    "dre_lines",
    "account_dre_mapping",
    "int_allocation_rules",
    "int_financial_entries",
    "int_dre_actual",
    "int_dre_budget",
    "int_reconciliation_commercial_accounting",
    "int_reconciliation_logistics_accounting",
    "int_financial_allocated",
    "int_performance_drivers",
}

EXPECTED_DRIVERS = {"VOLUME", "PRICE", "DISCOUNT", "MIX", "CMV", "LOGISTICS", "OPEX", "FINANCIAL"}


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
    parser = argparse.ArgumentParser(description="Run the INTERMEDIATE business acceptance suite.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before validating INTERMEDIATE.")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before validating INTERMEDIATE.") from exc

    quality_run_id = uuid.uuid4()
    results: list[TestResult] = []

    def add(test_name: str, entity: str | None, issue_count: int, details: str) -> None:
        result = TestResult(test_name, entity, int(issue_count), details)
        results.append(result)
        suffix = f" [{entity}]" if entity else ""
        print(f"{result.status} {test_name}{suffix}: issues={result.issue_count}")

    with psycopg.connect(args.database_url) as connection:
        connection.execute(
            "INSERT INTO control.intermediate_quality_runs (quality_run_id, status) VALUES (%s, 'RUNNING')",
            (quality_run_id,),
        )
        connection.commit()
        try:
            actual_objects = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT class.relname
                    FROM pg_class class
                    JOIN pg_namespace namespace ON namespace.oid = class.relnamespace
                    WHERE namespace.nspname = 'intermediate'
                      AND class.relkind IN ('r', 'm')
                    """
                )
            }
            add(
                "expected_object_set",
                None,
                len(actual_objects.symmetric_difference(EXPECTED_OBJECTS)),
                f"expected={len(EXPECTED_OBJECTS)} actual={len(actual_objects)}",
            )

            dre_line_issues = connection.execute(
                """
                SELECT ABS(COUNT(*) - 14)
                     + COUNT(*) FILTER (WHERE is_calculated <> (line_type = 'SUBTOTAL'))
                FROM intermediate.dre_lines
                WHERE is_active
                """
            ).fetchone()[0]
            add("dre_structure", "dre_lines", dre_line_issues, "14 ordered lines and calculated subtotal contract")

            unmapped_accounts = connection.execute(
                """
                SELECT COUNT(*)
                FROM staging.stg_chart_of_accounts account
                WHERE account.is_postable
                  AND account.is_result_account
                  AND NOT EXISTS (
                      SELECT 1
                      FROM intermediate.account_dre_mapping mapping
                      WHERE mapping.account_code = account.account_code
                        AND mapping.is_active
                        AND account.valid_from >= mapping.valid_from
                        AND account.valid_from <= COALESCE(mapping.valid_to, 'infinity'::DATE)
                  )
                """
            ).fetchone()[0]
            add("account_mapping_coverage", "account_dre_mapping", unmapped_accounts, "all postable result accounts mapped")

            overlap_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM intermediate.account_dre_mapping left_mapping
                JOIN intermediate.account_dre_mapping right_mapping
                  ON right_mapping.account_code = left_mapping.account_code
                 AND right_mapping.mapping_id > left_mapping.mapping_id
                 AND right_mapping.is_active AND left_mapping.is_active
                 AND daterange(left_mapping.valid_from, COALESCE(left_mapping.valid_to, 'infinity'::DATE), '[]')
                     && daterange(right_mapping.valid_from, COALESCE(right_mapping.valid_to, 'infinity'::DATE), '[]')
                """
            ).fetchone()[0]
            add("mapping_temporal_overlap", "account_dre_mapping", overlap_count, "no active validity overlap")

            unmapped_value_lines = connection.execute(
                """
                SELECT COUNT(*)
                FROM intermediate.int_financial_entries
                WHERE is_result_account AND mapping_status <> 'MAPPED'
                  AND debit_amount + credit_amount <> 0
                """
            ).fetchone()[0]
            add("financial_value_mapping_coverage", "int_financial_entries", unmapped_value_lines, "100% used result value mapped")

            financial_count_difference = connection.execute(
                """
                SELECT ABS(
                    (SELECT COUNT(*) FROM intermediate.int_financial_entries)
                    -
                    (SELECT COUNT(*) FROM staging.stg_journal_lines line
                     JOIN staging.stg_journal_entries entry USING (journal_entry_id)
                     WHERE entry.posting_status = 'POSTED')
                )
                """
            ).fetchone()[0]
            add("financial_row_reconciliation", "int_financial_entries", financial_count_difference, "one row per posted journal line")

            duplicate_financial_lines = connection.execute(
                """
                SELECT COALESCE(SUM(rows_per_line - 1), 0)
                FROM (
                    SELECT journal_line_id, COUNT(*) AS rows_per_line
                    FROM intermediate.int_financial_entries
                    GROUP BY journal_line_id HAVING COUNT(*) > 1
                ) duplicate
                """
            ).fetchone()[0]
            add("financial_grain_unique", "int_financial_entries", duplicate_financial_lines, "journal_line_id unique")

            management_sign_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM intermediate.int_financial_entries
                WHERE mapping_status = 'MAPPED'
                  AND ABS(management_amount - CASE sign_rule
                      WHEN 'CREDIT_POSITIVE' THEN credit_amount - debit_amount
                      WHEN 'DEBIT_POSITIVE' THEN debit_amount - credit_amount
                      WHEN 'DEBIT_NEGATIVE' THEN credit_amount - debit_amount
                  END) > 0.01
                """
            ).fetchone()[0]
            add("management_sign_rule", "int_financial_entries", management_sign_issues, "accounting value preserved and management sign deterministic")

            actual_difference = connection.execute(
                """
                SELECT CASE WHEN ABS(
                    (SELECT SUM(actual_amount) FROM intermediate.int_dre_actual)
                    -
                    (SELECT SUM(management_amount) FROM intermediate.int_financial_entries WHERE mapping_status = 'MAPPED')
                ) <= 0.01 THEN 0 ELSE 1 END
                """
            ).fetchone()[0]
            add("dre_actual_reconciliation", "int_dre_actual", actual_difference, "aggregated Actual equals mapped ledger")

            budget_unmapped = connection.execute(
                """
                SELECT COUNT(*)
                FROM staging.stg_budget budget
                WHERE NOT EXISTS (
                    SELECT 1 FROM intermediate.account_dre_mapping mapping
                    WHERE mapping.account_code = budget.account_code
                      AND mapping.is_active
                      AND to_date(budget.period || '-01', 'YYYY-MM-DD') >= mapping.valid_from
                      AND to_date(budget.period || '-01', 'YYYY-MM-DD') <= COALESCE(mapping.valid_to, 'infinity'::DATE)
                )
                """
            ).fetchone()[0]
            add("budget_mapping_coverage", "int_dre_budget", budget_unmapped, "all Budget rows use the same DRE mapping")

            budget_count_difference = connection.execute(
                """
                SELECT ABS(
                    (SELECT SUM(budget_row_count) FROM intermediate.int_dre_budget)
                    - (SELECT COUNT(*) FROM staging.stg_budget)
                )
                """
            ).fetchone()[0]
            add("budget_row_reconciliation", "int_dre_budget", budget_count_difference, "Budget source rows preserved")

            commercial_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM intermediate.int_reconciliation_commercial_accounting
                WHERE reconciliation_status NOT IN ('MATCHED', 'CANCELED')
                   OR (reconciliation_status = 'MATCHED' AND ABS(difference_amount) > 0.01)
                   OR (reconciliation_status = 'CANCELED' AND ABS(accounting_amount) > 0.01)
                """
            ).fetchone()[0]
            add("commercial_accounting_reconciliation", "int_reconciliation_commercial_accounting", commercial_issues, "issued matched; canceled net accounting zero")

            logistics_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM intermediate.int_reconciliation_logistics_accounting
                WHERE reconciliation_status <> 'MATCHED' OR ABS(difference_amount) > 0.01
                """
            ).fetchone()[0]
            add("logistics_accounting_reconciliation", "int_reconciliation_logistics_accounting", logistics_issues, "freight batch matches shipment date, branch and carrier")

            allocation_rule_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT account_code, valid_from,
                           ABS(SUM(fixed_percentage) - 1) AS weight_difference
                    FROM intermediate.int_allocation_rules
                    WHERE is_active
                    GROUP BY account_code, valid_from
                    HAVING ABS(SUM(fixed_percentage) - 1) > 0.00000001
                ) issue
                """
            ).fetchone()[0]
            add("allocation_rule_weights", "int_allocation_rules", allocation_rule_issues, "configured fallback percentages sum to one")

            unallocated_eligible = connection.execute(
                """
                SELECT COUNT(*)
                FROM intermediate.int_financial_allocated
                WHERE allocation_status = 'RULE_NOT_APPLICABLE'
                """
            ).fetchone()[0]
            add("allocation_rule_coverage", "int_financial_allocated", unallocated_eligible, "all eligible corporate entries have a rule")

            allocation_weight_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT journal_line_id
                    FROM intermediate.int_financial_allocated
                    GROUP BY journal_line_id
                    HAVING ABS(SUM(allocation_weight) - 1) > 0.00000001
                ) issue
                """
            ).fetchone()[0]
            add("allocation_weight_conservation", "int_financial_allocated", allocation_weight_issues, "weights sum to one by source line")

            allocation_value_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT journal_line_id
                    FROM intermediate.int_financial_allocated
                    GROUP BY journal_line_id, source_management_amount
                    HAVING ABS(SUM(allocated_management_amount) - source_management_amount) > 0.01
                ) issue
                """
            ).fetchone()[0]
            add("allocation_value_conservation", "int_financial_allocated", allocation_value_issues, "no value created or destroyed")

            actual_drivers = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT driver_name FROM intermediate.int_performance_drivers"
                )
            }
            add(
                "performance_driver_set",
                "int_performance_drivers",
                len(actual_drivers.symmetric_difference(EXPECTED_DRIVERS)),
                ", ".join(sorted(actual_drivers)),
            )

            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO control.intermediate_quality_results (
                        quality_run_id, test_name, source_entity, status, issue_count, details
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (quality_run_id, result.test_name, result.entity, result.status, result.issue_count, result.details)
                        for result in results
                    ],
                )
            failed = sum(result.status == "FAIL" for result in results)
            passed = len(results) - failed
            connection.execute(
                """
                UPDATE control.intermediate_quality_runs
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
                UPDATE control.intermediate_quality_runs
                SET ended_at = clock_timestamp(), status = 'FAILED', error_message = %s
                WHERE quality_run_id = %s
                """,
                (str(exc)[:4000], quality_run_id),
            )
            connection.commit()
            raise

    failed_results = [result for result in results if result.status == "FAIL"]
    if failed_results:
        raise SystemExit(f"INTERMEDIATE validation failed: {len(failed_results)} tests with issues.")
    print(f"All INTERMEDIATE acceptance checks passed ({len(results)} tests). quality_run_id={quality_run_id}")


if __name__ == "__main__":
    main()
