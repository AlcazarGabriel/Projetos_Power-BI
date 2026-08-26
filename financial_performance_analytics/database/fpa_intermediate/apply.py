from __future__ import annotations

import argparse
import os

from .schema import ACCOUNT_GROUP_RULES, DRE_LINES, generate_configuration_sql, generate_models_sql


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or rebuild the PostgreSQL INTERMEDIATE layer.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--check", action="store_true", help="Compile the SQL contracts without changing the database.")
    args = parser.parse_args()

    configuration_sql = generate_configuration_sql()
    models_sql = generate_models_sql()
    if args.check:
        print(
            "INTERMEDIATE contracts compiled: "
            f"{len(DRE_LINES)} DRE lines, {len(ACCOUNT_GROUP_RULES)} account-group rules and 7 materialized models."
        )
        return
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before applying INTERMEDIATE.")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before applying INTERMEDIATE.") from exc

    with psycopg.connect(args.database_url) as connection:
        connection.execute(configuration_sql)
        mapping_issues = connection.execute(
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
        if mapping_issues:
            raise RuntimeError(f"DRE mapping gate failed: {mapping_issues} postable result accounts are unmapped.")
        connection.execute(models_sql)
        connection.commit()

    print("INTERMEDIATE created successfully: mapping gate passed, 3 configuration tables and 7 models ready.")


if __name__ == "__main__":
    main()
