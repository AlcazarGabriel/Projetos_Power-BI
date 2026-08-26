from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


PERIOD_SUFFIX = re.compile(r"_\d{4}_\d{2}$")
ACTUAL_ENTITIES = (
    "erp_sales_orders",
    "erp_sales_order_items",
    "erp_invoices",
    "erp_invoice_items",
    "erp_deliveries",
    "erp_expense_documents",
    "erp_expense_lines",
    "erp_headcount_monthly",
    "erp_financial_movements",
    "erp_journal_entries",
    "erp_journal_lines",
)
MASTER_ENTITIES = (
    "erp_companies",
    "erp_product_categories",
    "erp_branches",
    "erp_customers",
    "erp_suppliers",
    "erp_products",
    "erp_product_suppliers",
    "erp_cost_centers",
    "erp_chart_of_accounts",
    "erp_carriers",
    "erp_carrier_rates",
    "erp_sales_representatives",
    "erp_accounting_periods",
)
PLANNING_ENTITIES = (
    "erp_budget_versions",
    "erp_budget_assumptions",
    "erp_budget_product_mix",
    "erp_budget_headcount",
    "erp_budget",
)
ENTITY_ORDER = MASTER_ENTITIES + PLANNING_ENTITIES + ACTUAL_ENTITIES

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "erp_companies": ("company_id",),
    "erp_branches": ("branch_id",),
    "erp_customers": ("customer_id",),
    "erp_suppliers": ("supplier_id",),
    "erp_product_categories": ("category_id",),
    "erp_products": ("product_id",),
    "erp_product_suppliers": ("product_supplier_id",),
    "erp_cost_centers": ("cost_center_id",),
    "erp_chart_of_accounts": ("account_id",),
    "erp_carriers": ("carrier_id",),
    "erp_carrier_rates": ("carrier_rate_id",),
    "erp_sales_representatives": ("sales_rep_id",),
    "erp_accounting_periods": ("accounting_period_id",),
    "erp_sales_orders": ("order_id",),
    "erp_sales_order_items": ("order_item_id",),
    "erp_invoices": ("invoice_id",),
    "erp_invoice_items": ("invoice_item_id",),
    "erp_deliveries": ("delivery_id",),
    "erp_expense_documents": ("expense_document_id",),
    "erp_expense_lines": ("expense_line_id",),
    "erp_headcount_monthly": ("headcount_snapshot_id",),
    "erp_financial_movements": ("financial_movement_id",),
    "erp_journal_entries": ("journal_entry_id",),
    "erp_journal_lines": ("journal_line_id",),
    "erp_budget_versions": ("budget_version_id",),
    "erp_budget_assumptions": ("budget_version_id", "period", "branch_id"),
    "erp_budget_product_mix": (
        "budget_version_id",
        "period",
        "branch_id",
        "category_id",
    ),
    "erp_budget_headcount": ("budget_version_id", "period", "cost_center_id"),
    "erp_budget": ("budget_id",),
}

UNIQUE_KEYS: dict[str, tuple[tuple[str, ...], ...]] = {
    "erp_companies": (("company_code",),),
    "erp_branches": (("branch_code",),),
    "erp_customers": (("customer_code",),),
    "erp_suppliers": (("supplier_code",),),
    "erp_product_categories": (("category_code",),),
    "erp_products": (("product_code",), ("sku",)),
    "erp_product_suppliers": (("product_id", "supplier_id"),),
    "erp_cost_centers": (("cost_center_code",),),
    "erp_chart_of_accounts": (("account_code",),),
    "erp_carriers": (("carrier_code",),),
    "erp_sales_representatives": (("sales_rep_code",),),
    "erp_accounting_periods": (("company_id", "fiscal_year", "fiscal_period"),),
    "erp_sales_orders": (("order_number",),),
    "erp_sales_order_items": (("order_id", "line_number"),),
    "erp_invoices": (("invoice_number",),),
    "erp_invoice_items": (("invoice_id", "invoice_line_number"),),
    "erp_deliveries": (("delivery_number",),),
    "erp_expense_documents": (("document_number",),),
    "erp_expense_lines": (("expense_document_id", "line_number"),),
    "erp_journal_entries": (("entry_number",),),
    "erp_journal_lines": (("journal_entry_id", "line_number"),),
    "erp_budget_versions": (("budget_version_code",),),
}

FOREIGN_KEYS: dict[str, tuple[tuple[tuple[str, ...], str, tuple[str, ...]], ...]] = {
    "erp_branches": ((("company_id",), "erp_companies", ("company_id",)),),
    "erp_customers": ((("default_branch_id",), "erp_branches", ("branch_id",)),),
    "erp_suppliers": ((("primary_category_id",), "erp_product_categories", ("category_id",)),),
    "erp_products": ((("category_id",), "erp_product_categories", ("category_id",)),),
    "erp_product_suppliers": (
        (("product_id",), "erp_products", ("product_id",)),
        (("supplier_id",), "erp_suppliers", ("supplier_id",)),
    ),
    "erp_cost_centers": ((("branch_id",), "erp_branches", ("branch_id",)),),
    "erp_chart_of_accounts": (
        (("company_id",), "erp_companies", ("company_id",)),
        (("parent_account_code",), "erp_chart_of_accounts", ("account_code",)),
    ),
    "erp_carrier_rates": (
        (("carrier_id",), "erp_carriers", ("carrier_id",)),
        (("origin_branch_id",), "erp_branches", ("branch_id",)),
    ),
    "erp_sales_representatives": ((("branch_id",), "erp_branches", ("branch_id",)),),
    "erp_accounting_periods": ((("company_id",), "erp_companies", ("company_id",)),),
    "erp_sales_orders": (
        (("company_id",), "erp_companies", ("company_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
        (("customer_id",), "erp_customers", ("customer_id",)),
        (("sales_rep_id",), "erp_sales_representatives", ("sales_rep_id",)),
    ),
    "erp_sales_order_items": (
        (("order_id",), "erp_sales_orders", ("order_id",)),
        (("product_id",), "erp_products", ("product_id",)),
        (("category_id",), "erp_product_categories", ("category_id",)),
    ),
    "erp_invoices": (
        (("order_id",), "erp_sales_orders", ("order_id",)),
        (("company_id",), "erp_companies", ("company_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
        (("customer_id",), "erp_customers", ("customer_id",)),
        (("replacement_invoice_id",), "erp_invoices", ("invoice_id",)),
    ),
    "erp_invoice_items": (
        (("invoice_id",), "erp_invoices", ("invoice_id",)),
        (("order_id",), "erp_sales_orders", ("order_id",)),
        (("order_item_id",), "erp_sales_order_items", ("order_item_id",)),
        (("product_id",), "erp_products", ("product_id",)),
        (("category_id",), "erp_product_categories", ("category_id",)),
    ),
    "erp_deliveries": (
        (("invoice_id",), "erp_invoices", ("invoice_id",)),
        (("order_id",), "erp_sales_orders", ("order_id",)),
        (("company_id",), "erp_companies", ("company_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
        (("customer_id",), "erp_customers", ("customer_id",)),
        (("carrier_id",), "erp_carriers", ("carrier_id",)),
        (("carrier_rate_id",), "erp_carrier_rates", ("carrier_rate_id",)),
    ),
    "erp_expense_documents": (
        (("company_id",), "erp_companies", ("company_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
        (("supplier_id",), "erp_suppliers", ("supplier_id",)),
        (("cost_center_id",), "erp_cost_centers", ("cost_center_id",)),
    ),
    "erp_expense_lines": (
        (("expense_document_id",), "erp_expense_documents", ("expense_document_id",)),
        (("account_code",), "erp_chart_of_accounts", ("account_code",)),
    ),
    "erp_headcount_monthly": (
        (("cost_center_id",), "erp_cost_centers", ("cost_center_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
    ),
    "erp_financial_movements": (
        (("account_code",), "erp_chart_of_accounts", ("account_code",)),
        (("counterpart_account_code",), "erp_chart_of_accounts", ("account_code",)),
    ),
    "erp_journal_entries": (
        (("company_id",), "erp_companies", ("company_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
        (("reversal_of_entry_id",), "erp_journal_entries", ("journal_entry_id",)),
    ),
    "erp_journal_lines": (
        (("journal_entry_id",), "erp_journal_entries", ("journal_entry_id",)),
        (("account_code",), "erp_chart_of_accounts", ("account_code",)),
        (("cost_center_id",), "erp_cost_centers", ("cost_center_id",)),
        (("customer_id",), "erp_customers", ("customer_id",)),
        (("supplier_id",), "erp_suppliers", ("supplier_id",)),
        (("carrier_id",), "erp_carriers", ("carrier_id",)),
    ),
    "erp_budget_assumptions": (
        (("budget_version_id",), "erp_budget_versions", ("budget_version_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
    ),
    "erp_budget_product_mix": (
        (("budget_version_id",), "erp_budget_versions", ("budget_version_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
        (("category_id",), "erp_product_categories", ("category_id",)),
    ),
    "erp_budget_headcount": (
        (("budget_version_id",), "erp_budget_versions", ("budget_version_id",)),
        (("cost_center_id",), "erp_cost_centers", ("cost_center_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
    ),
    "erp_budget": (
        (("budget_version_id",), "erp_budget_versions", ("budget_version_id",)),
        (("company_id",), "erp_companies", ("company_id",)),
        (("branch_id",), "erp_branches", ("branch_id",)),
        (("cost_center_id",), "erp_cost_centers", ("cost_center_id",)),
        (("account_code",), "erp_chart_of_accounts", ("account_code",)),
    ),
}

INDEXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "erp_sales_orders": (("order_date",), ("customer_id",), ("branch_id",)),
    "erp_sales_order_items": (("order_id",), ("product_id",)),
    "erp_invoices": (("issue_date",), ("order_id",), ("customer_id",)),
    "erp_invoice_items": (("invoice_id",), ("order_item_id",), ("product_id",)),
    "erp_deliveries": (("shipment_date",), ("invoice_id",), ("carrier_id",), ("branch_id",)),
    "erp_journal_entries": (
        ("posting_date",),
        ("source_module", "source_document_type", "source_document_id"),
        ("reversal_of_entry_id",),
    ),
    "erp_journal_lines": (
        ("journal_entry_id",),
        ("account_code",),
        ("cost_center_id",),
        ("customer_id",),
    ),
    "erp_budget": (
        ("period",),
        ("account_code",),
        ("branch_id",),
        ("cost_center_id",),
        ("budget_version_id",),
    ),
}


def entity_name(path: Path) -> str:
    return PERIOD_SUFFIX.sub("", path.stem)


def discover_entity_files(dataset_root: Path) -> dict[str, list[Path]]:
    candidates = [*dataset_root.joinpath("master").glob("erp_*.csv")]
    candidates.extend(dataset_root.joinpath("planning").glob("erp_*.csv"))
    candidates.extend(dataset_root.joinpath("actual_batches").glob("*/*.csv"))
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in candidates:
        grouped[entity_name(path)].append(path.resolve())
    for paths in grouped.values():
        paths.sort()
    missing = set(ENTITY_ORDER) - set(grouped)
    unexpected = set(grouped) - set(ENTITY_ORDER)
    if missing or unexpected:
        raise ValueError(f"Entity mismatch. missing={sorted(missing)}, unexpected={sorted(unexpected)}")
    return dict(grouped)


def read_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream), None)
    if not header:
        raise ValueError(f"CSV without header: {path}")
    if len(header) != len(set(header)):
        raise ValueError(f"Duplicate columns in {path}")
    return tuple(header)


def validate_headers(entity_files: dict[str, list[Path]]) -> dict[str, tuple[str, ...]]:
    headers: dict[str, tuple[str, ...]] = {}
    for entity, files in entity_files.items():
        expected = read_header(files[0])
        for path in files[1:]:
            actual = read_header(path)
            if actual != expected:
                raise ValueError(f"Header mismatch for {entity}: {path}")
        headers[entity] = expected
    return headers


def _classify(value: str) -> str:
    if not value:
        return "empty"
    if value.lower() in {"true", "false"}:
        return "boolean"
    if re.fullmatch(r"-?\d+", value):
        return "integer"
    if re.fullmatch(r"-?\d+\.\d+", value):
        return "numeric"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return "date"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?", value):
        return "timestamp"
    return "text"


def profile_columns(files: Iterable[Path], columns: tuple[str, ...], sample_rows: int = 250) -> dict[str, set[str]]:
    observed = {column: set() for column in columns}
    for path in files:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row_number, row in enumerate(reader):
                if row_number >= sample_rows:
                    break
                for column in columns:
                    kind = _classify((row.get(column) or "").strip())
                    if kind != "empty":
                        observed[column].add(kind)
    return observed


def postgres_type(column: str, observed: set[str]) -> str:
    if column in {
        "tax_id",
        "barcode_ean13",
        "batch_id",
        "source_document_id",
        "reference_document_id",
    } or column.endswith("_code") or column == "account_code" or column == "parent_account_code":
        return "VARCHAR(50)"
    if column == "period" or column == "period_label":
        return "CHAR(7)"
    if column.endswith("_at") or column.endswith("_timestamp") or "timestamp" in observed:
        return "TIMESTAMP"
    if column.endswith("_date") or column in {"valid_from", "valid_to", "effective_from", "effective_to", "opened_at"} or observed == {"date"}:
        return "DATE"
    if observed == {"boolean"} or column.startswith("is_") or column.endswith("_flag") or column.endswith("_available"):
        return "BOOLEAN"
    if column.endswith("_id"):
        return "BIGINT"
    if "text" in observed:
        if column in {"description", "category_description", "industry"} or column.endswith("_description"):
            return "TEXT"
        return "VARCHAR(150)"
    if observed == {"integer"}:
        return "INTEGER"
    if column.endswith("_pct") or column.endswith("_share") or column.endswith("_index"):
        return "NUMERIC(12,6)"
    monetary_tokens = ("amount", "price", "cost", "revenue", "value", "limit", "target", "freight")
    if any(token in column for token in monetary_tokens):
        return "NUMERIC(18,2)"
    quantity_tokens = ("qty", "weight", "volume", "distance", "height", "width", "length", "capacity")
    if any(token in column for token in quantity_tokens):
        return "NUMERIC(18,4)"
    if "numeric" in observed:
        return "NUMERIC(18,6)"
    return "VARCHAR(150)"


def _constraint_name(prefix: str, table: str, columns: tuple[str, ...]) -> str:
    raw_name = f"{prefix}_{table}_{'_'.join(columns)}"
    return raw_name[:63]


def generate_schema_sql(dataset_root: Path) -> tuple[str, dict[str, tuple[str, ...]]]:
    entity_files = discover_entity_files(dataset_root)
    headers = validate_headers(entity_files)
    profiles = {
        entity: profile_columns(entity_files[entity], headers[entity])
        for entity in ENTITY_ORDER
    }
    statements = [
        "SET client_encoding = 'UTF8';",
        "CREATE SCHEMA IF NOT EXISTS raw;",
        "CREATE SCHEMA IF NOT EXISTS staging;",
        "CREATE SCHEMA IF NOT EXISTS intermediate;",
        "CREATE SCHEMA IF NOT EXISTS marts;",
        "CREATE SCHEMA IF NOT EXISTS control;",
        """
CREATE TABLE IF NOT EXISTS raw.pipeline_runs (
    pipeline_run_id UUID PRIMARY KEY,
    dataset_root TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ended_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING', 'LOADED', 'FAILED')),
    files_loaded INTEGER NOT NULL DEFAULT 0,
    files_skipped INTEGER NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    error_message TEXT
);""".strip(),
        """
CREATE TABLE IF NOT EXISTS raw.ingestion_control (
    ingestion_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id UUID NOT NULL REFERENCES raw.pipeline_runs(pipeline_run_id),
    source_system VARCHAR(50) NOT NULL,
    source_entity VARCHAR(100) NOT NULL,
    source_file TEXT NOT NULL,
    reference_period CHAR(7),
    file_sha256 CHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
    rows_received BIGINT NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    rows_rejected BIGINT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ended_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RECEIVED', 'LOADED', 'FAILED', 'REPROCESSED')),
    error_message TEXT,
    UNIQUE (source_entity, file_sha256)
);""".strip(),
        """
CREATE TABLE IF NOT EXISTS control.data_quality_issues (
    issue_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    pipeline_run_id UUID REFERENCES raw.pipeline_runs(pipeline_run_id),
    source_entity VARCHAR(100) NOT NULL,
    record_id TEXT,
    rule_id VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    expected_value TEXT,
    actual_value TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED', 'ACCEPTED'))
);""".strip(),
    ]

    for entity in ENTITY_ORDER:
        columns = headers[entity]
        definitions = []
        for column in columns:
            nullable = " NOT NULL" if column in PRIMARY_KEYS[entity] else ""
            definitions.append(f"    {column} {postgres_type(column, profiles[entity][column])}{nullable}")
        definitions.extend(
            [
                "    ingestion_id BIGINT NOT NULL REFERENCES raw.ingestion_control(ingestion_id)",
                "    pipeline_run_id UUID NOT NULL REFERENCES raw.pipeline_runs(pipeline_run_id)",
                "    source_file TEXT NOT NULL",
                "    source_system VARCHAR(50) NOT NULL",
                "    ingested_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()",
            ]
        )
        constraints = [
            f"    CONSTRAINT {_constraint_name('pk', entity, PRIMARY_KEYS[entity])} PRIMARY KEY ({', '.join(PRIMARY_KEYS[entity])})"
        ]
        for unique_columns in UNIQUE_KEYS.get(entity, ()):
            constraints.append(
                f"    CONSTRAINT {_constraint_name('uq', entity, unique_columns)} UNIQUE ({', '.join(unique_columns)})"
            )
        for local_columns, target_table, target_columns in FOREIGN_KEYS.get(entity, ()):
            constraints.append(
                f"    CONSTRAINT {_constraint_name('fk', entity, local_columns)} FOREIGN KEY ({', '.join(local_columns)}) "
                f"REFERENCES raw.{target_table} ({', '.join(target_columns)}) DEFERRABLE INITIALLY DEFERRED"
            )
        for column in columns:
            if column == "fiscal_period":
                constraints.append(
                    f"    CONSTRAINT {_constraint_name('ck', entity, (column,))} CHECK ({column} BETWEEN 1 AND 12)"
                )
            elif column.endswith("_pct"):
                constraints.append(
                    f"    CONSTRAINT {_constraint_name('ck', entity, (column,))} CHECK ({column} IS NULL OR {column} BETWEEN 0 AND 1)"
                )
        if entity == "erp_journal_lines":
            constraints.append(
                "    CONSTRAINT ck_erp_journal_lines_debit_credit_nonnegative "
                "CHECK (debit_amount >= 0 AND credit_amount >= 0)"
            )
        statements.append(
            f"CREATE TABLE IF NOT EXISTS raw.{entity} (\n"
            + ",\n".join(definitions + constraints)
            + "\n);"
        )
        for index_columns in INDEXES.get(entity, ()):
            index_name = _constraint_name("ix", entity, index_columns)
            statements.append(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON raw.{entity} ({', '.join(index_columns)});"
            )

    statements.extend(
        [
            """
CREATE OR REPLACE VIEW control.v_journal_balance_issues AS
SELECT
    journal_entry_id,
    SUM(debit_amount) AS debit_amount,
    SUM(credit_amount) AS credit_amount,
    ABS(SUM(debit_amount) - SUM(credit_amount)) AS difference
FROM raw.erp_journal_lines
GROUP BY journal_entry_id
HAVING ABS(SUM(debit_amount) - SUM(credit_amount)) > 0.01;""".strip(),
            """
CREATE OR REPLACE VIEW control.v_journal_header_line_issues AS
SELECT
    e.journal_entry_id,
    e.line_count AS header_line_count,
    COUNT(l.journal_line_id) AS actual_line_count,
    e.total_debit_amount AS header_debit,
    COALESCE(SUM(l.debit_amount), 0) AS actual_debit,
    e.total_credit_amount AS header_credit,
    COALESCE(SUM(l.credit_amount), 0) AS actual_credit
FROM raw.erp_journal_entries e
LEFT JOIN raw.erp_journal_lines l USING (journal_entry_id)
GROUP BY e.journal_entry_id, e.line_count, e.total_debit_amount, e.total_credit_amount
HAVING e.line_count <> COUNT(l.journal_line_id)
    OR ABS(e.total_debit_amount - COALESCE(SUM(l.debit_amount), 0)) > 0.01
    OR ABS(e.total_credit_amount - COALESCE(SUM(l.credit_amount), 0)) > 0.01;""".strip(),
        ]
    )
    return "\n\n".join(statements) + "\n", headers
