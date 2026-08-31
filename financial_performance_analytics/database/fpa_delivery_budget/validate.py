from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the Delivery Budget extension in PostgreSQL.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before validating Delivery Budget.")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before validating Delivery Budget.") from exc

    checks = (
        ("raw_row_count", "SELECT ABS(COUNT(*) - 180) FROM raw.erp_budget_delivery_plan"),
        ("mart_row_count", "SELECT ABS(COUNT(*) - 180) FROM marts.fct_delivery_budget"),
        (
            "natural_grain_unique",
            "SELECT COUNT(*) - COUNT(DISTINCT (budget_version_id, period, branch_id)) FROM raw.erp_budget_delivery_plan",
        ),
        (
            "critical_values_valid",
            "SELECT COUNT(*) FROM raw.erp_budget_delivery_plan WHERE planned_deliveries <= 0 OR planned_freight_cost < 0 OR planned_cost_per_delivery < 0",
        ),
        (
            "all_36_months",
            "SELECT ABS(COUNT(DISTINCT period) - 36) FROM raw.erp_budget_delivery_plan",
        ),
        (
            "five_branches_per_month",
            "SELECT COUNT(*) FROM (SELECT period FROM raw.erp_budget_delivery_plan GROUP BY period HAVING COUNT(*) <> 5) issue",
        ),
        (
            "cost_per_delivery_math",
            "SELECT COUNT(*) FROM raw.erp_budget_delivery_plan WHERE ABS(planned_cost_per_delivery - planned_freight_cost / planned_deliveries) > 0.0001",
        ),
        (
            "freight_cost_reconciles_to_budget",
            """
            WITH financial AS (
                SELECT budget_version_id, date_key, branch_key, -SUM(budget_amount) AS freight_cost
                FROM marts.fct_budget WHERE account_code = '5.02.001'
                GROUP BY budget_version_id, date_key, branch_key
            )
            SELECT COUNT(*) FROM marts.fct_delivery_budget plan
            LEFT JOIN financial USING (budget_version_id, date_key, branch_key)
            WHERE financial.freight_cost IS NULL OR ABS(plan.planned_freight_cost - financial.freight_cost) > 0.01
            """,
        ),
        (
            "freight_charge_reconciles_to_budget",
            """
            WITH financial AS (
                SELECT budget_version_id, date_key, branch_key, SUM(budget_amount) AS freight_charge
                FROM marts.fct_budget WHERE account_code = '4.01.008'
                GROUP BY budget_version_id, date_key, branch_key
            )
            SELECT COUNT(*) FROM marts.fct_delivery_budget plan
            LEFT JOIN financial USING (budget_version_id, date_key, branch_key)
            WHERE financial.freight_charge IS NULL OR ABS(plan.planned_freight_charge - financial.freight_charge) > 0.01
            """,
        ),
        (
            "star_keys_resolve",
            """
            SELECT COUNT(*) FROM marts.fct_delivery_budget fact
            LEFT JOIN marts.dim_date date_dimension ON date_dimension.date_key = fact.date_key
            LEFT JOIN marts.dim_branch branch ON branch.branch_key = fact.branch_key
            LEFT JOIN marts.dim_budget_version budget_version
              ON budget_version.budget_version_id = fact.budget_version_id
            WHERE date_dimension.date_key IS NULL OR branch.branch_key IS NULL
               OR budget_version.budget_version_key IS NULL
            """,
        ),
    )

    failed = []
    with psycopg.connect(args.database_url) as connection:
        for name, query in checks:
            issues = int(connection.execute(query).fetchone()[0])
            status = "PASS" if issues == 0 else "FAIL"
            print(f"{status} {name}: issues={issues}")
            if issues:
                failed.append((name, issues))
    if failed:
        raise SystemExit(f"Delivery Budget validation failed: {failed}")
    print(f"All Delivery Budget acceptance checks passed ({len(checks)} tests).")


if __name__ == "__main__":
    main()
