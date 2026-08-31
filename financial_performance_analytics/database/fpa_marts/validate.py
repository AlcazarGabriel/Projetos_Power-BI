from __future__ import annotations

import argparse
import os
import uuid
from dataclasses import dataclass

from .schema import DIMENSIONS, FACTS


EXPECTED_OBJECTS = set(DIMENSIONS + FACTS)


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
    parser = argparse.ArgumentParser(description="Run the MARTS dimensional acceptance suite.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before validating MARTS.")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before validating MARTS.") from exc

    quality_run_id = uuid.uuid4()
    results: list[TestResult] = []

    def add(test_name: str, entity: str | None, issue_count: int, details: str) -> None:
        result = TestResult(test_name, entity, int(issue_count), details)
        results.append(result)
        suffix = f" [{entity}]" if entity else ""
        print(f"{result.status} {test_name}{suffix}: issues={result.issue_count}")

    with psycopg.connect(args.database_url) as connection:
        connection.execute(
            "INSERT INTO control.marts_quality_runs (quality_run_id, status) VALUES (%s, 'RUNNING')",
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
                    WHERE namespace.nspname = 'marts' AND class.relkind = 'm'
                    """
                )
            }
            missing_objects = EXPECTED_OBJECTS - actual_objects
            add(
                "expected_object_set",
                None,
                len(missing_objects),
                f"required={len(EXPECTED_OBJECTS)} actual={len(actual_objects)}; extensions are allowed",
            )

            dimension_contracts = (
                ("dim_branch", "staging.stg_branches", "branch_key", 2),
                ("dim_budget_version", "staging.stg_budget_versions", "budget_version_key", 1),
                ("dim_account", "staging.stg_chart_of_accounts", "account_key", 1),
                ("dim_dre", "intermediate.dre_lines", "dre_key", 1),
                ("dim_cost_center", "staging.stg_cost_centers", "cost_center_key", 1),
                ("dim_customer", "staging.stg_customers", "customer_key", 1),
                ("dim_product", "staging.stg_products", "product_key", 1),
                ("dim_carrier", "staging.stg_carriers", "carrier_key", 1),
                ("dim_sales_representative", "staging.stg_sales_representatives", "sales_rep_key", 1),
            )
            for dimension, source, key, special_members in dimension_contracts:
                difference = connection.execute(
                    f"SELECT ABS((SELECT COUNT(*) FROM marts.{dimension}) - (SELECT COUNT(*) + {special_members} FROM {source}))"
                ).fetchone()[0]
                add(
                    "dimension_row_reconciliation",
                    dimension,
                    difference,
                    f"source={source} plus {special_members} governed special member(s)",
                )
                unknown_count = connection.execute(
                    f"SELECT COUNT(*) FROM marts.{dimension} WHERE {key} = 0"
                ).fetchone()[0]
                add("dimension_unknown_member", dimension, abs(unknown_count - 1), "exactly one key zero")

            corporate_branch_issues = connection.execute(
                """
                SELECT ABS(COUNT(*) - 1)
                FROM marts.dim_branch
                WHERE branch_key = -1 AND branch_code = 'CORPORATE' AND is_active
                """
            ).fetchone()[0]
            add(
                "dimension_corporate_member",
                "dim_branch",
                corporate_branch_issues,
                "key -1 is the governed CORPORATE member; key zero remains UNKNOWN",
            )

            driver_dimension_issues = connection.execute(
                """
                SELECT
                    ABS(COUNT(*) - 10)
                  + ABS(COUNT(DISTINCT driver_key) - 10)
                  + ABS(COUNT(DISTINCT driver_name) - 10)
                  + COUNT(*) FILTER (
                        WHERE driver_name = 'FINANCIAL' AND is_operational_bridge
                    )
                  + COUNT(*) FILTER (
                        WHERE driver_name IN (
                            'VOLUME', 'PRICE', 'DISCOUNT', 'MIX', 'CMV',
                            'LOGISTICS', 'OPEX', 'RESIDUAL'
                        ) AND NOT is_operational_bridge
                    )
                FROM marts.dim_driver
                """
            ).fetchone()[0]
            add(
                "driver_dimension_contract",
                "dim_driver",
                driver_dimension_issues,
                "UNKNOWN plus nine ordered drivers; FINANCIAL excluded from operational bridge",
            )

            date_issues = connection.execute(
                """
                SELECT CASE
                    WHEN COUNT(*) FILTER (WHERE date_key = 0) <> 1 THEN 1
                    WHEN COUNT(*) FILTER (WHERE NOT is_unknown)
                         <> MAX(full_date) FILTER (WHERE NOT is_unknown)
                            - MIN(full_date) FILTER (WHERE NOT is_unknown) + 1 THEN 1
                    WHEN MIN(full_date) FILTER (WHERE NOT is_unknown) <> DATE '2024-01-01' THEN 1
                    WHEN MAX(full_date) FILTER (WHERE NOT is_unknown) <> DATE '2026-12-31' THEN 1
                    WHEN (SELECT full_date FROM marts.dim_date WHERE date_key = 0) <> DATE '1900-01-01' THEN 1
                    ELSE 0
                END
                FROM marts.dim_date
                """
            ).fetchone()[0]
            add("date_dimension_continuity", "dim_date", date_issues, "continuous 2024-01-01 through 2026-12-31 plus UNKNOWN")

            fact_contracts = (
                (
                    "fct_financial_entries",
                    "SELECT COUNT(*) FROM intermediate.int_financial_entries financial "
                    "LEFT JOIN intermediate.int_financial_allocated allocation USING (journal_line_id)",
                    "financial_entry_key",
                ),
                (
                    "fct_budget",
                    "SELECT COUNT(*) FROM intermediate.int_dre_budget budget "
                    "LEFT JOIN intermediate.int_budget_allocated allocation USING (dre_budget_id)",
                    "budget_key",
                ),
                ("fct_sales", "SELECT COUNT(*) FROM staging.stg_invoice_items", "sales_key"),
                ("fct_deliveries", "SELECT COUNT(*) FROM staging.stg_deliveries", "delivery_key"),
                (
                    "fct_reconciliation",
                    "SELECT (SELECT COUNT(*) FROM intermediate.int_reconciliation_commercial_accounting) "
                    "+ (SELECT COUNT(*) FROM intermediate.int_reconciliation_logistics_accounting)",
                    "reconciliation_key",
                ),
                (
                    "fct_performance_drivers",
                    "SELECT COUNT(*) FROM intermediate.int_performance_driver_impacts",
                    "performance_driver_key",
                ),
            )
            for fact, source_query, key in fact_contracts:
                difference = connection.execute(
                    f"SELECT ABS((SELECT COUNT(*) FROM marts.{fact}) - ({source_query}))"
                ).fetchone()[0]
                add("fact_row_reconciliation", fact, difference, source_query)
                duplicate_count = connection.execute(
                    f"SELECT COUNT(*) - COUNT(DISTINCT {key}) FROM marts.{fact}"
                ).fetchone()[0]
                add("fact_grain_unique", fact, duplicate_count, f"{key} unique")

            null_key_issues = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM marts.fct_financial_entries
                     WHERE competence_date_key IS NULL OR posting_date_key IS NULL OR branch_key IS NULL
                        OR cost_center_key IS NULL OR account_key IS NULL OR dre_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_budget
                     WHERE date_key IS NULL OR budget_version_id IS NULL
                        OR branch_key IS NULL OR cost_center_key IS NULL
                        OR account_key IS NULL OR dre_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_sales
                     WHERE date_key IS NULL OR issue_date_key IS NULL OR order_date_key IS NULL
                        OR branch_key IS NULL OR customer_key IS NULL OR product_key IS NULL OR sales_rep_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_deliveries
                     WHERE shipment_date_key IS NULL OR promised_delivery_date_key IS NULL
                        OR actual_delivery_date_key IS NULL OR branch_key IS NULL
                        OR customer_key IS NULL OR carrier_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_reconciliation
                     WHERE date_key IS NULL OR accounting_date_key IS NULL OR branch_key IS NULL
                        OR customer_key IS NULL OR carrier_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_performance_drivers
                     WHERE date_key IS NULL OR branch_key IS NULL OR driver_key IS NULL
                        OR budget_version_id IS NULL)
                """
            ).fetchone()[0]
            add(
                "fact_keys_not_null",
                None,
                null_key_issues,
                "all dimensional keys populated; zero is UNKNOWN and branch -1 is CORPORATE",
            )

            orphan_issues = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM marts.fct_financial_entries fact
                     LEFT JOIN marts.dim_date date_dimension ON date_dimension.date_key = fact.competence_date_key
                     LEFT JOIN marts.dim_branch branch ON branch.branch_key = fact.branch_key
                     LEFT JOIN marts.dim_cost_center cost_center ON cost_center.cost_center_key = fact.cost_center_key
                     LEFT JOIN marts.dim_account account ON account.account_key = fact.account_key
                     LEFT JOIN marts.dim_dre dre ON dre.dre_key = fact.dre_key
                     WHERE date_dimension.date_key IS NULL OR branch.branch_key IS NULL
                        OR cost_center.cost_center_key IS NULL OR account.account_key IS NULL OR dre.dre_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_budget fact
                     LEFT JOIN marts.dim_date date_dimension ON date_dimension.date_key = fact.date_key
                     LEFT JOIN marts.dim_budget_version budget_version
                       ON budget_version.budget_version_id = fact.budget_version_id
                     LEFT JOIN marts.dim_branch branch ON branch.branch_key = fact.branch_key
                     LEFT JOIN marts.dim_cost_center cost_center ON cost_center.cost_center_key = fact.cost_center_key
                     LEFT JOIN marts.dim_account account ON account.account_key = fact.account_key
                     LEFT JOIN marts.dim_dre dre ON dre.dre_key = fact.dre_key
                     WHERE date_dimension.date_key IS NULL OR budget_version.budget_version_key IS NULL
                        OR branch.branch_key IS NULL
                        OR cost_center.cost_center_key IS NULL OR account.account_key IS NULL OR dre.dre_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_sales fact
                     LEFT JOIN marts.dim_date date_dimension ON date_dimension.date_key = fact.date_key
                     LEFT JOIN marts.dim_branch branch ON branch.branch_key = fact.branch_key
                     LEFT JOIN marts.dim_customer customer ON customer.customer_key = fact.customer_key
                     LEFT JOIN marts.dim_product product ON product.product_key = fact.product_key
                     LEFT JOIN marts.dim_sales_representative representative ON representative.sales_rep_key = fact.sales_rep_key
                     WHERE date_dimension.date_key IS NULL OR branch.branch_key IS NULL
                        OR customer.customer_key IS NULL OR product.product_key IS NULL OR representative.sales_rep_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_deliveries fact
                     LEFT JOIN marts.dim_date date_dimension ON date_dimension.date_key = fact.shipment_date_key
                     LEFT JOIN marts.dim_branch branch ON branch.branch_key = fact.branch_key
                     LEFT JOIN marts.dim_customer customer ON customer.customer_key = fact.customer_key
                     LEFT JOIN marts.dim_carrier carrier ON carrier.carrier_key = fact.carrier_key
                     WHERE date_dimension.date_key IS NULL OR branch.branch_key IS NULL
                        OR customer.customer_key IS NULL OR carrier.carrier_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_reconciliation fact
                     LEFT JOIN marts.dim_date date_dimension ON date_dimension.date_key = fact.date_key
                     LEFT JOIN marts.dim_date accounting_date ON accounting_date.date_key = fact.accounting_date_key
                     LEFT JOIN marts.dim_branch branch ON branch.branch_key = fact.branch_key
                     LEFT JOIN marts.dim_customer customer ON customer.customer_key = fact.customer_key
                     LEFT JOIN marts.dim_carrier carrier ON carrier.carrier_key = fact.carrier_key
                     WHERE date_dimension.date_key IS NULL OR accounting_date.date_key IS NULL
                        OR branch.branch_key IS NULL OR customer.customer_key IS NULL OR carrier.carrier_key IS NULL)
                  + (SELECT COUNT(*) FROM marts.fct_performance_drivers fact
                     LEFT JOIN marts.dim_date date_dimension ON date_dimension.date_key = fact.date_key
                     LEFT JOIN marts.dim_budget_version budget_version
                       ON budget_version.budget_version_id = fact.budget_version_id
                     LEFT JOIN marts.dim_branch branch ON branch.branch_key = fact.branch_key
                     LEFT JOIN marts.dim_driver driver ON driver.driver_key = fact.driver_key
                     WHERE date_dimension.date_key IS NULL OR budget_version.budget_version_key IS NULL
                        OR branch.branch_key IS NULL
                        OR driver.driver_key IS NULL)
                """
            ).fetchone()[0]
            add("star_relationship_integrity", None, orphan_issues, "all primary fact keys resolve to dimensions")

            financial_value_issues = connection.execute(
                """
                WITH fact AS (
                    SELECT SUM(debit_amount) debit, SUM(credit_amount) credit,
                           SUM(accounting_amount) accounting, SUM(management_amount) management
                    FROM marts.fct_financial_entries
                ), source AS (
                    SELECT SUM(debit_amount) debit, SUM(credit_amount) credit,
                           SUM(accounting_amount) accounting,
                           SUM(management_amount) FILTER (WHERE mapping_status = 'MAPPED') management
                    FROM intermediate.int_financial_entries
                )
                SELECT
                    (CASE WHEN ABS(fact.debit - source.debit) > 0.01 THEN 1 ELSE 0 END)
                  + (CASE WHEN ABS(fact.credit - source.credit) > 0.01 THEN 1 ELSE 0 END)
                  + (CASE WHEN ABS(fact.accounting - source.accounting) > 0.01 THEN 1 ELSE 0 END)
                  + (CASE WHEN ABS(fact.management - source.management) > 0.01 THEN 1 ELSE 0 END)
                FROM fact CROSS JOIN source
                """
            ).fetchone()[0]
            add("financial_additive_reconciliation", "fct_financial_entries", financial_value_issues, "debit, credit, accounting and management totals preserved")

            financial_weight_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT journal_line_id
                    FROM marts.fct_financial_entries
                    GROUP BY journal_line_id
                    HAVING ABS(SUM(allocation_weight) - 1) > 0.00000001
                ) issue
                """
            ).fetchone()[0]
            add("financial_allocation_weight", "fct_financial_entries", financial_weight_issues, "allocation weights sum to one")

            budget_value_issues = connection.execute(
                """
                SELECT CASE WHEN ABS(
                    (SELECT SUM(budget_amount) FROM marts.fct_budget)
                    - (SELECT SUM(budget_amount) FROM intermediate.int_dre_budget)
                ) <= 0.01 THEN 0 ELSE 1 END
                """
            ).fetchone()[0]
            add("budget_value_reconciliation", "fct_budget", budget_value_issues, "signed Budget total preserved")

            budget_weight_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT dre_budget_id
                    FROM marts.fct_budget
                    GROUP BY dre_budget_id
                    HAVING ABS(SUM(allocation_weight) - 1) > 0.00000001
                ) issue
                """
            ).fetchone()[0]
            add("budget_allocation_weight", "fct_budget", budget_weight_issues, "allocation weights sum to one")

            budget_branch_validity_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM marts.fct_budget fb
                LEFT JOIN marts.dim_branch db ON db.branch_key = fb.branch_key
                WHERE db.branch_key IS NULL
                """
            ).fetchone()[0]
            add(
                "budget_allocation_branch_validity",
                "fct_budget",
                budget_branch_validity_issues,
                "every allocated branch_key resolves to a real dim_branch member",
            )

            same_grain_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM marts.fct_budget fb
                JOIN marts.dim_dre dre ON dre.dre_key = fb.dre_key
                WHERE dre.dre_line_id IN ('06','07','08','09') AND fb.branch_key = -1
                """
            ).fetchone()[0]
            add(
                "budget_actual_same_management_grain",
                "fct_budget",
                same_grain_issues,
                "OPEX/logistics budget fully attributed to real branches, comparable to Actual by period x branch x DRE",
            )

            sales_value_issues = connection.execute(
                """
                WITH fact AS (
                    SELECT SUM(source_gross_amount) source_gross,
                           SUM(gross_sales_amount) recognized_gross,
                           SUM(net_sales_amount) recognized_net,
                           SUM(canceled_net_amount) canceled_net
                    FROM marts.fct_sales
                ), source AS (
                    SELECT SUM(item.gross_line_amount) source_gross,
                           SUM(item.gross_line_amount) FILTER (
                               WHERE invoice.invoice_status = 'ISSUED' AND item.item_status = 'ISSUED'
                           ) recognized_gross,
                           SUM(item.net_line_amount) FILTER (
                               WHERE invoice.invoice_status = 'ISSUED' AND item.item_status = 'ISSUED'
                           ) recognized_net,
                           SUM(item.net_line_amount) FILTER (
                               WHERE invoice.invoice_status = 'CANCELED' OR item.item_status = 'CANCELED'
                           ) canceled_net
                    FROM staging.stg_invoice_items item
                    JOIN staging.stg_invoices invoice USING (invoice_id)
                )
                SELECT
                    (CASE WHEN ABS(fact.source_gross - source.source_gross) > 0.01 THEN 1 ELSE 0 END)
                  + (CASE WHEN ABS(fact.recognized_gross - source.recognized_gross) > 0.01 THEN 1 ELSE 0 END)
                  + (CASE WHEN ABS(fact.recognized_net - source.recognized_net) > 0.01 THEN 1 ELSE 0 END)
                  + (CASE WHEN ABS(fact.canceled_net - source.canceled_net) > 0.01 THEN 1 ELSE 0 END)
                FROM fact CROSS JOIN source
                """
            ).fetchone()[0]
            add("sales_value_reconciliation", "fct_sales", sales_value_issues, "source, recognized and canceled measures preserved")

            delivery_value_issues = connection.execute(
                """
                WITH fact AS (
                    SELECT SUM(freight_cost_total) cost,
                           SUM(freight_charged_to_customer) charged,
                           SUM(freight_subsidy_amount) subsidy
                    FROM marts.fct_deliveries
                ), source AS (
                    SELECT SUM(freight_cost_total) cost,
                           SUM(freight_charged_to_customer) charged,
                           SUM(freight_subsidy_amount) subsidy
                    FROM staging.stg_deliveries
                )
                SELECT
                    (CASE WHEN ABS(fact.cost - source.cost) > 0.01 THEN 1 ELSE 0 END)
                  + (CASE WHEN ABS(fact.charged - source.charged) > 0.01 THEN 1 ELSE 0 END)
                  + (CASE WHEN ABS(fact.subsidy - source.subsidy) > 0.01 THEN 1 ELSE 0 END)
                FROM fact CROSS JOIN source
                """
            ).fetchone()[0]
            add("delivery_value_reconciliation", "fct_deliveries", delivery_value_issues, "freight cost, charge and subsidy preserved")

            reconciliation_value_issues = connection.execute(
                """
                WITH fact AS (
                    SELECT reconciliation_type,
                           SUM(source_amount) source_amount,
                           SUM(accounting_amount) accounting_amount,
                           SUM(difference_amount) difference_amount,
                           SUM(source_record_count) source_record_count,
                           SUM(accounting_entry_count) accounting_entry_count
                    FROM marts.fct_reconciliation
                    GROUP BY reconciliation_type
                ), source AS (
                    SELECT 'COMMERCIAL'::VARCHAR AS reconciliation_type,
                           SUM(commercial_amount)::NUMERIC source_amount,
                           SUM(accounting_amount)::NUMERIC accounting_amount,
                           SUM(difference_amount)::NUMERIC difference_amount,
                           COUNT(*) FILTER (WHERE commercial_competence_date IS NOT NULL)::NUMERIC source_record_count,
                           SUM(COALESCE(accounting_entry_count, 0))::NUMERIC accounting_entry_count
                    FROM intermediate.int_reconciliation_commercial_accounting
                    UNION ALL
                    SELECT 'LOGISTICS'::VARCHAR,
                           SUM(logistics_amount)::NUMERIC,
                           SUM(accounting_amount)::NUMERIC,
                           SUM(difference_amount)::NUMERIC,
                           SUM(COALESCE(delivery_count, 0))::NUMERIC,
                           SUM(COALESCE(accounting_entry_count, 0))::NUMERIC
                    FROM intermediate.int_reconciliation_logistics_accounting
                )
                SELECT COUNT(*)
                FROM fact JOIN source USING (reconciliation_type)
                WHERE ABS(COALESCE(fact.source_amount, 0) - COALESCE(source.source_amount, 0)) > 0.01
                   OR ABS(COALESCE(fact.accounting_amount, 0) - COALESCE(source.accounting_amount, 0)) > 0.01
                   OR ABS(COALESCE(fact.difference_amount, 0) - COALESCE(source.difference_amount, 0)) > 0.01
                   OR fact.source_record_count <> source.source_record_count
                   OR fact.accounting_entry_count <> source.accounting_entry_count
                """
            ).fetchone()[0]
            add(
                "reconciliation_value_preservation",
                "fct_reconciliation",
                reconciliation_value_issues,
                "source, accounting, difference, event and entry totals preserved by type",
            )

            reconciliation_flag_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM marts.fct_reconciliation
                WHERE reconciliation_status NOT IN (
                    'MATCHED', 'CANCELED', 'VALUE_MISMATCH', 'TIMING_DIFFERENCE',
                    'MISSING_ACCOUNTING', 'MISSING_COMMERCIAL', 'MISSING_LOGISTICS'
                )
                   OR is_reconciled <> (reconciliation_status = 'MATCHED')
                   OR is_exception <> (reconciliation_status NOT IN ('MATCHED', 'CANCELED'))
                   OR is_canceled <> (reconciliation_status = 'CANCELED')
                   OR (reconciliation_type = 'COMMERCIAL' AND carrier_key <> 0)
                   OR (reconciliation_type = 'LOGISTICS' AND customer_key <> 0)
                """
            ).fetchone()[0]
            add(
                "reconciliation_status_and_flags",
                "fct_reconciliation",
                reconciliation_flag_issues,
                "status domain, flags and not-applicable dimension keys are consistent",
            )

            performance_value_issues = connection.execute(
                """
                WITH fact AS (
                    SELECT driver_name,
                           SUM(impact_amount) impact_amount,
                           SUM(impact_amount_abs) impact_amount_abs
                    FROM marts.fct_performance_drivers
                    GROUP BY driver_name
                ), source AS (
                    SELECT driver_name,
                           SUM(impact_amount) impact_amount,
                           SUM(impact_amount_abs) impact_amount_abs
                    FROM intermediate.int_performance_driver_impacts
                    GROUP BY driver_name
                )
                SELECT COUNT(*)
                FROM fact FULL OUTER JOIN source USING (driver_name)
                WHERE ABS(COALESCE(fact.impact_amount, 0) - COALESCE(source.impact_amount, 0)) > 0.01
                   OR ABS(COALESCE(fact.impact_amount_abs, 0) - COALESCE(source.impact_amount_abs, 0)) > 0.01
                """
            ).fetchone()[0]
            add(
                "performance_driver_value_preservation",
                "fct_performance_drivers",
                performance_value_issues,
                "signed and absolute impacts are preserved by driver",
            )

            performance_bridge_issues = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT date_key, company_id, branch_key, budget_version_id,
                           ABS(SUM(impact_amount) FILTER (WHERE is_operational_bridge)
                               - MAX(operational_gap_amount)) AS closure_difference,
                           MAX(ABS(impact_amount)) FILTER (WHERE driver_name = 'RESIDUAL')
                               AS residual_amount
                    FROM marts.fct_performance_drivers
                    GROUP BY date_key, company_id, branch_key, budget_version_id
                ) bridge
                WHERE closure_difference > 0.01 OR residual_amount > 0.01
                """
            ).fetchone()[0]
            add(
                "performance_operational_bridge",
                "fct_performance_drivers",
                performance_bridge_issues,
                "operational impacts close Actual minus Budget and residual stays within R$ 0.01",
            )

            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO control.marts_quality_results (
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
                UPDATE control.marts_quality_runs
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
                UPDATE control.marts_quality_runs
                SET ended_at = clock_timestamp(), status = 'FAILED', error_message = %s
                WHERE quality_run_id = %s
                """,
                (str(exc)[:4000], quality_run_id),
            )
            connection.commit()
            raise

    failed_results = [result for result in results if result.status == "FAIL"]
    if failed_results:
        raise SystemExit(f"MARTS validation failed: {len(failed_results)} tests with issues.")
    print(f"All MARTS acceptance checks passed ({len(results)} tests). quality_run_id={quality_run_id}")


if __name__ == "__main__":
    main()
