from __future__ import annotations

from pathlib import Path

from database.fpa_raw.schema import (
    ENTITY_ORDER,
    FOREIGN_KEYS,
    PRIMARY_KEYS,
    discover_entity_files,
    postgres_type,
    profile_columns,
    validate_headers,
)


ACCEPTED_VALUES: dict[tuple[str, str], tuple[str, ...]] = {
    ("erp_sales_orders", "order_status"): ("CANCELED", "FULFILLED", "PARTIALLY_FULFILLED"),
    ("erp_sales_order_items", "item_status"): ("CANCELED", "FULFILLED", "OPEN"),
    ("erp_invoices", "invoice_status"): ("CANCELED", "ISSUED"),
    ("erp_invoices", "invoice_type"): ("SALE",),
    ("erp_invoice_items", "item_status"): ("CANCELED", "ISSUED"),
    ("erp_deliveries", "delivery_status"): ("DELIVERED",),
    ("erp_expense_documents", "document_status"): ("POSTED",),
    ("erp_journal_entries", "posting_status"): ("POSTED",),
    ("erp_journal_entries", "entry_type"): ("NORMAL", "REVERSAL"),
    ("erp_accounting_periods", "period_status"): ("CLOSED", "OPEN"),
    ("erp_budget_versions", "status"): ("APPROVED",),
    ("erp_budget", "scenario"): ("BUDGET",),
    ("erp_customers", "customer_status"): ("ACTIVE", "INACTIVE"),
    ("erp_suppliers", "supplier_status"): ("ACTIVE", "BLOCKED", "INACTIVE"),
    ("erp_carriers", "carrier_status"): ("ACTIVE", "INACTIVE"),
    ("erp_products", "lifecycle_status"): ("ACTIVE", "DISCONTINUED", "NEW"),
    ("erp_sales_representatives", "sales_rep_status"): ("ACTIVE", "INACTIVE"),
}

BUSINESS_PREDICATES: dict[str, tuple[tuple[str, str], ...]] = {
    "erp_accounting_periods": (
        ("valid_period_number", "fiscal_period NOT BETWEEN 1 AND 12"),
        ("valid_period_dates", "start_date > end_date"),
    ),
    "erp_sales_orders": (
        ("positive_order_values", "total_gross_amount < 0 OR total_discount_amount < 0 OR total_net_amount < 0"),
        ("valid_order_dates", "order_date > requested_delivery_date"),
    ),
    "erp_sales_order_items": (
        ("positive_ordered_qty", "ordered_qty <= 0"),
        ("positive_order_item_values", "gross_line_amount < 0 OR discount_amount < 0 OR net_line_amount < 0"),
    ),
    "erp_invoices": (
        ("positive_invoice_values", "gross_product_amount < 0 OR discount_amount < 0 OR net_product_amount < 0 OR invoice_total_amount < 0"),
        ("valid_cancellation_date", "cancellation_date IS NOT NULL AND cancellation_date < issue_date"),
    ),
    "erp_invoice_items": (
        ("positive_billed_qty", "billed_qty <= 0"),
        ("positive_invoice_item_values", "gross_line_amount < 0 OR discount_amount < 0 OR net_line_amount < 0 OR total_tax_amount < 0"),
    ),
    "erp_deliveries": (
        ("valid_delivery_dates", "actual_delivery_date < shipment_date"),
        ("positive_delivery_values", "freight_cost_total < 0 OR freight_charged_to_customer < 0"),
        (
            "freight_subsidy_reconciliation",
            "ABS(freight_subsidy_amount - (freight_cost_total - freight_charged_to_customer)) > 0.01",
        ),
    ),
    "erp_journal_entries": (
        ("balanced_entry_header", "ABS(total_debit_amount - total_credit_amount) > 0.01"),
        ("positive_entry_totals", "total_debit_amount < 0 OR total_credit_amount < 0"),
    ),
    "erp_journal_lines": (
        ("positive_debit_credit", "debit_amount < 0 OR credit_amount < 0"),
    ),
    "erp_budget": (
        ("valid_budget_period", "fiscal_period NOT BETWEEN 1 AND 12"),
    ),
}


def staging_name(entity: str) -> str:
    return f"stg_{entity.removeprefix('erp_')}"


def should_uppercase(column: str) -> bool:
    suffixes = (
        "_code",
        "_status",
        "_type",
        "_state",
        "_region",
        "_module",
        "_balance",
        "_statement",
        "_scenario",
        "_uom",
    )
    explicit = {
        "account_code",
        "parent_account_code",
        "batch_id",
        "currency_code",
        "domestic_or_foreign",
        "entry_type",
        "financial_statement",
        "freight_policy",
        "invoice_type",
        "movement_type",
        "normal_balance",
        "period",
        "period_label",
        "quarter",
        "reference_document_id",
        "reference_document_type",
        "scenario",
        "service_quality_tier",
        "source_document_id",
        "source_document_type",
        "source_module",
        "source_system",
        "uom",
    }
    return column.endswith(suffixes) or column in explicit


def projection_expression(column: str, data_type: str) -> str:
    if data_type.startswith("VARCHAR") or data_type.startswith("CHAR") or data_type == "TEXT":
        expression = f"NULLIF(BTRIM({column}::TEXT), '')"
        if should_uppercase(column):
            expression = f"UPPER({expression})"
        return f"{expression}::{data_type} AS {column}"
    return f"{column}::{data_type} AS {column}"


def build_contracts(dataset_root: Path) -> tuple[dict[str, tuple[str, ...]], dict[str, dict[str, str]]]:
    entity_files = discover_entity_files(dataset_root)
    headers = validate_headers(entity_files)
    contracts: dict[str, dict[str, str]] = {}
    for entity in ENTITY_ORDER:
        profiles = profile_columns(entity_files[entity], headers[entity])
        contracts[entity] = {
            column: postgres_type(column, profiles[column])
            for column in headers[entity]
        }
    return headers, contracts


def generate_staging_sql(dataset_root: Path) -> tuple[str, dict[str, tuple[str, ...]]]:
    headers, contracts = build_contracts(dataset_root)
    statements = [
        "SET client_encoding = 'UTF8';",
        "CREATE SCHEMA IF NOT EXISTS staging;",
        "CREATE SCHEMA IF NOT EXISTS control;",
        "COMMENT ON SCHEMA staging IS 'Espelho tipado e padronizado da RAW, sem regras gerenciais.';",
        """
CREATE TABLE IF NOT EXISTS control.staging_quality_runs (
    quality_run_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ended_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING', 'PASSED', 'FAILED')),
    tests_passed INTEGER NOT NULL DEFAULT 0,
    tests_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);""".strip(),
        """
CREATE TABLE IF NOT EXISTS control.staging_quality_results (
    quality_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quality_run_id UUID NOT NULL REFERENCES control.staging_quality_runs(quality_run_id),
    test_name VARCHAR(150) NOT NULL,
    source_entity VARCHAR(100),
    status VARCHAR(10) NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    issue_count BIGINT NOT NULL CHECK (issue_count >= 0),
    details TEXT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);""".strip(),
        "CREATE INDEX IF NOT EXISTS ix_staging_quality_results_run ON control.staging_quality_results (quality_run_id);",
    ]

    for entity in ENTITY_ORDER:
        source_columns = [
            projection_expression(column, contracts[entity][column])
            for column in headers[entity]
        ]
        source_columns.extend(
            [
                "ingestion_id::BIGINT AS ingestion_id",
                "pipeline_run_id::UUID AS pipeline_run_id",
                "NULLIF(BTRIM(source_file), '')::TEXT AS source_file",
                "UPPER(NULLIF(BTRIM(source_system), ''))::VARCHAR(50) AS source_system",
                "ingested_at::TIMESTAMPTZ AS ingested_at",
            ]
        )
        view_name = staging_name(entity)
        statements.append(
            f"CREATE OR REPLACE VIEW staging.{view_name} AS\nSELECT\n    "
            + ",\n    ".join(source_columns)
            + f"\nFROM raw.{entity};"
        )
        statements.append(
            f"COMMENT ON VIEW staging.{view_name} IS "
            f"'Espelho tipado e padronizado de raw.{entity}; granularidade preservada.';"
        )

    return "\n\n".join(statements) + "\n", headers
