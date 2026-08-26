from __future__ import annotations

import argparse
import os


EXPECTED_COUNTS = {
    "erp_sales_orders": 248_415,
    "erp_sales_order_items": 635_002,
    "erp_invoices": 258_377,
    "erp_invoice_items": 615_602,
    "erp_deliveries": 256_857,
    "erp_journal_entries": 316_392,
    "erp_journal_lines": 1_372_132,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the loaded RAW database.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before validation.")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before validation.") from exc

    failures: list[str] = []
    with psycopg.connect(args.database_url) as connection:
        schema_names = {
            row[0]
            for row in connection.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('raw', 'staging', 'intermediate', 'marts', 'control')"
            )
        }
        schemas_ok = schema_names == {"raw", "staging", "intermediate", "marts", "control"}
        print(f"{'PASS' if schemas_ok else 'FAIL'} schemas: {', '.join(sorted(schema_names))}")
        if not schemas_ok:
            failures.append("schemas")
        for table, expected in EXPECTED_COUNTS.items():
            actual = connection.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
            outcome = "PASS" if actual == expected else "FAIL"
            print(f"{outcome} row_count {table}: actual={actual:,} expected={expected:,}")
            if actual != expected:
                failures.append(f"{table} row count")
        balance_issues = connection.execute("SELECT COUNT(*) FROM control.v_journal_balance_issues").fetchone()[0]
        print(f"{'PASS' if balance_issues == 0 else 'FAIL'} journal_balance: issues={balance_issues}")
        if balance_issues:
            failures.append("journal balance")
        header_issues = connection.execute("SELECT COUNT(*) FROM control.v_journal_header_line_issues").fetchone()[0]
        print(f"{'PASS' if header_issues == 0 else 'FAIL'} journal_header_lines: issues={header_issues}")
        if header_issues:
            failures.append("journal header/line reconciliation")
        actual_periods = connection.execute(
            "SELECT MIN(competence_date), MAX(competence_date), COUNT(DISTINCT date_trunc('month', competence_date)) FROM raw.erp_journal_entries"
        ).fetchone()
        period_ok = str(actual_periods[0])[:7] == "2024-01" and str(actual_periods[1])[:7] == "2026-07" and actual_periods[2] == 31
        print(
            f"{'PASS' if period_ok else 'FAIL'} period_coverage: "
            f"min={actual_periods[0]} max={actual_periods[1]} months={actual_periods[2]}"
        )
        if not period_ok:
            failures.append("period coverage")
        loaded_files = connection.execute(
            "SELECT COUNT(*) FROM raw.ingestion_control WHERE status = 'LOADED'"
        ).fetchone()[0]
        print(f"{'PASS' if loaded_files == 359 else 'FAIL'} ingestion_control: loaded_files={loaded_files}")
        if loaded_files != 359:
            failures.append("ingestion control")
        raw_constraints = connection.execute(
            """
            SELECT COUNT(*) FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'raw'
            """
        ).fetchone()[0]
        raw_indexes = connection.execute(
            "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'raw'"
        ).fetchone()[0]
        database_size = connection.execute(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        ).fetchone()[0]
        print(f"INFO physical_structure: constraints={raw_constraints} indexes={raw_indexes} database_size={database_size}")
    if failures:
        raise SystemExit("Validation failed: " + ", ".join(failures))
    print("All RAW acceptance checks passed.")


if __name__ == "__main__":
    main()
