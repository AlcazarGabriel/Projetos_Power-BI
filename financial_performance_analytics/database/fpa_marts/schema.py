from __future__ import annotations


DIMENSIONS = (
    "dim_date",
    "dim_branch",
    "dim_account",
    "dim_dre",
    "dim_cost_center",
    "dim_customer",
    "dim_product",
    "dim_carrier",
    "dim_sales_representative",
)

FACTS = (
    "fct_financial_entries",
    "fct_budget",
    "fct_sales",
    "fct_deliveries",
)


def generate_marts_sql() -> str:
    return r"""
SET client_encoding = 'UTF8';
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS control;
COMMENT ON SCHEMA marts IS 'Modelo dimensional de consumo para Semantic Model e Power BI.';

CREATE TABLE IF NOT EXISTS control.marts_quality_runs (
    quality_run_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ended_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING', 'PASSED', 'FAILED')),
    tests_passed INTEGER NOT NULL DEFAULT 0,
    tests_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS control.marts_quality_results (
    quality_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quality_run_id UUID NOT NULL REFERENCES control.marts_quality_runs(quality_run_id),
    test_name VARCHAR(150) NOT NULL,
    source_entity VARCHAR(100),
    status VARCHAR(10) NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    issue_count BIGINT NOT NULL CHECK (issue_count >= 0),
    details TEXT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS ix_marts_quality_results_run
    ON control.marts_quality_results (quality_run_id);

DROP MATERIALIZED VIEW IF EXISTS marts.fct_deliveries;
DROP MATERIALIZED VIEW IF EXISTS marts.fct_sales;
DROP MATERIALIZED VIEW IF EXISTS marts.fct_budget;
DROP MATERIALIZED VIEW IF EXISTS marts.fct_financial_entries;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_sales_representative;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_carrier;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_product;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_customer;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_cost_center;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_dre;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_account;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_branch;
DROP MATERIALIZED VIEW IF EXISTS marts.dim_date;

CREATE MATERIALIZED VIEW marts.dim_date AS
WITH date_bounds AS (
    SELECT MIN(business_date)::DATE AS min_date, MAX(business_date)::DATE AS max_date
    FROM (
        SELECT competence_date AS business_date FROM staging.stg_journal_entries
        UNION ALL SELECT competence_date FROM staging.stg_invoices
        UNION ALL SELECT actual_delivery_date FROM staging.stg_deliveries
        UNION ALL SELECT (to_date(period || '-01', 'YYYY-MM-DD') + INTERVAL '1 month - 1 day')::DATE
                  FROM staging.stg_budget
    ) dates
), calendar AS (
    SELECT generate_series(min_date, max_date, INTERVAL '1 day')::DATE AS full_date
    FROM date_bounds
)
SELECT
    0::INTEGER AS date_key,
    NULL::DATE AS full_date,
    0::SMALLINT AS calendar_year,
    0::SMALLINT AS calendar_quarter,
    0::SMALLINT AS calendar_month,
    'UNKNOWN'::VARCHAR(20) AS month_name,
    0::INTEGER AS year_month_number,
    'UNKNOWN'::VARCHAR(20) AS year_month_label,
    0::SMALLINT AS day_of_month,
    0::SMALLINT AS day_of_week,
    'UNKNOWN'::VARCHAR(20) AS day_name,
    0::SMALLINT AS iso_week,
    FALSE AS is_weekend,
    NULL::DATE AS month_start_date,
    NULL::DATE AS month_end_date,
    0::SMALLINT AS fiscal_year,
    0::SMALLINT AS fiscal_period
UNION ALL
SELECT
    to_char(full_date, 'YYYYMMDD')::INTEGER AS date_key,
    full_date,
    EXTRACT(YEAR FROM full_date)::SMALLINT AS calendar_year,
    EXTRACT(QUARTER FROM full_date)::SMALLINT AS calendar_quarter,
    EXTRACT(MONTH FROM full_date)::SMALLINT AS calendar_month,
    trim(to_char(full_date, 'Month'))::VARCHAR(20) AS month_name,
    to_char(full_date, 'YYYYMM')::INTEGER AS year_month_number,
    to_char(full_date, 'YYYY-MM')::VARCHAR(20) AS year_month_label,
    EXTRACT(DAY FROM full_date)::SMALLINT AS day_of_month,
    EXTRACT(ISODOW FROM full_date)::SMALLINT AS day_of_week,
    trim(to_char(full_date, 'Day'))::VARCHAR(20) AS day_name,
    EXTRACT(WEEK FROM full_date)::SMALLINT AS iso_week,
    EXTRACT(ISODOW FROM full_date) IN (6, 7) AS is_weekend,
    date_trunc('month', full_date)::DATE AS month_start_date,
    (date_trunc('month', full_date) + INTERVAL '1 month - 1 day')::DATE AS month_end_date,
    EXTRACT(YEAR FROM full_date)::SMALLINT AS fiscal_year,
    EXTRACT(MONTH FROM full_date)::SMALLINT AS fiscal_period
FROM calendar;

CREATE UNIQUE INDEX ux_dim_date_key ON marts.dim_date (date_key);
CREATE UNIQUE INDEX ux_dim_date_value ON marts.dim_date (full_date) WHERE full_date IS NOT NULL;
COMMENT ON MATERIALIZED VIEW marts.dim_date IS 'Calendario diario conformado cobrindo Actual e Budget.';

CREATE MATERIALIZED VIEW marts.dim_branch AS
SELECT
    0::BIGINT AS branch_key,
    0::BIGINT AS branch_id,
    0::BIGINT AS company_id,
    'UNKNOWN'::VARCHAR(50) AS company_code,
    'Unknown'::VARCHAR(150) AS company_name,
    'UNKNOWN'::VARCHAR(50) AS branch_code,
    'Unknown'::VARCHAR(150) AS branch_name,
    'UNKNOWN'::VARCHAR(150) AS branch_type,
    'Unknown'::VARCHAR(150) AS city,
    'UN'::VARCHAR(50) AS state_code,
    'UNKNOWN'::VARCHAR(150) AS region,
    NULL::TIMESTAMP AS opened_at,
    0::INTEGER AS warehouse_capacity_m3,
    FALSE AS is_distribution_center,
    FALSE AS is_active
UNION ALL
SELECT
    branch.branch_id AS branch_key,
    branch.branch_id,
    branch.company_id,
    company.company_code,
    company.trade_name AS company_name,
    branch.branch_code,
    branch.branch_name,
    branch.branch_type,
    branch.city,
    branch.state_code,
    branch.region,
    branch.opened_at,
    branch.warehouse_capacity_m3,
    branch.is_distribution_center,
    branch.is_active
FROM staging.stg_branches branch
JOIN staging.stg_companies company USING (company_id);

CREATE UNIQUE INDEX ux_dim_branch_key ON marts.dim_branch (branch_key);
CREATE UNIQUE INDEX ux_dim_branch_natural ON marts.dim_branch (branch_id);
COMMENT ON MATERIALIZED VIEW marts.dim_branch IS 'Filiais e atributos organizacionais conformados.';

CREATE MATERIALIZED VIEW marts.dim_dre AS
SELECT
    0::SMALLINT AS dre_key,
    '00'::VARCHAR(10) AS dre_line_id,
    'UNKNOWN'::VARCHAR(60) AS dre_line_code,
    'Unknown'::VARCHAR(150) AS dre_line_name,
    0::SMALLINT AS display_order,
    'GROUP'::VARCHAR(20) AS line_type,
    'RESULT'::VARCHAR(20) AS performance_nature,
    FALSE AS is_calculated,
    NULL::TEXT AS formula_expression,
    FALSE AS is_active
UNION ALL
SELECT
    display_order AS dre_key,
    dre_line_id,
    dre_line_code,
    dre_line_name,
    display_order,
    line_type,
    performance_nature,
    is_calculated,
    formula_expression,
    is_active
FROM intermediate.dre_lines;

CREATE UNIQUE INDEX ux_dim_dre_key ON marts.dim_dre (dre_key);
CREATE UNIQUE INDEX ux_dim_dre_natural ON marts.dim_dre (dre_line_id);
COMMENT ON MATERIALIZED VIEW marts.dim_dre IS 'Hierarquia funcional da DRE, incluindo grupos e subtotais.';

CREATE MATERIALIZED VIEW marts.dim_account AS
SELECT
    0::BIGINT AS account_key,
    0::BIGINT AS account_id,
    0::BIGINT AS company_id,
    'UNKNOWN'::VARCHAR(50) AS account_code,
    'Unknown'::VARCHAR(150) AS account_name,
    NULL::VARCHAR(50) AS parent_account_code,
    0::INTEGER AS account_level,
    'UNKNOWN'::VARCHAR(150) AS account_type,
    'UNKNOWN'::VARCHAR(150) AS financial_statement,
    'UNKNOWN'::VARCHAR(150) AS normal_balance,
    FALSE AS is_result_account,
    FALSE AS is_postable,
    FALSE AS requires_cost_center,
    0::SMALLINT AS current_dre_key,
    'UNMAPPED'::VARCHAR(100) AS management_group,
    'NOT_APPLICABLE'::VARCHAR(30) AS sign_rule,
    'NOT_APPLICABLE'::VARCHAR(30) AS management_nature,
    NULL::DATE AS valid_from,
    NULL::DATE AS valid_to,
    FALSE AS is_active
UNION ALL
SELECT
    account.account_id AS account_key,
    account.account_id,
    account.company_id,
    account.account_code,
    account.account_name,
    account.parent_account_code,
    account.account_level,
    account.account_type,
    account.financial_statement,
    account.normal_balance,
    account.is_result_account,
    account.is_postable,
    account.requires_cost_center,
    COALESCE(dre.display_order, 0)::SMALLINT AS current_dre_key,
    COALESCE(mapping.management_group, 'UNMAPPED')::VARCHAR(100),
    COALESCE(mapping.sign_rule, 'NOT_APPLICABLE')::VARCHAR(30),
    COALESCE(mapping.performance_nature, 'NOT_APPLICABLE')::VARCHAR(30),
    account.valid_from,
    account.valid_to,
    account.is_active
FROM staging.stg_chart_of_accounts account
LEFT JOIN LATERAL (
    SELECT active_mapping.*
    FROM intermediate.account_dre_mapping active_mapping
    WHERE active_mapping.account_code = account.account_code
      AND active_mapping.is_active
    ORDER BY active_mapping.valid_from DESC
    LIMIT 1
) mapping ON TRUE
LEFT JOIN intermediate.dre_lines dre USING (dre_line_id);

CREATE UNIQUE INDEX ux_dim_account_key ON marts.dim_account (account_key);
CREATE UNIQUE INDEX ux_dim_account_natural ON marts.dim_account (account_code);
CREATE INDEX ix_dim_account_dre ON marts.dim_account (current_dre_key, account_type);
COMMENT ON MATERIALIZED VIEW marts.dim_account IS 'Plano de contas com classificacao gerencial corrente para navegacao.';

CREATE MATERIALIZED VIEW marts.dim_cost_center AS
SELECT
    0::BIGINT AS cost_center_key,
    0::BIGINT AS cost_center_id,
    'UNKNOWN'::VARCHAR(50) AS cost_center_code,
    'Unknown'::VARCHAR(150) AS cost_center_name,
    'UNKNOWN'::VARCHAR(50) AS department_code,
    'Unknown'::VARCHAR(150) AS department_name,
    0::BIGINT AS source_branch_key,
    'UNKNOWN'::VARCHAR(150) AS management_scope,
    FALSE AS allocation_eligible,
    NULL::DATE AS valid_from,
    NULL::DATE AS valid_to,
    FALSE AS is_active
UNION ALL
SELECT
    cost_center.cost_center_id AS cost_center_key,
    cost_center.cost_center_id,
    cost_center.cost_center_code,
    cost_center.cost_center_name,
    cost_center.department_code,
    cost_center.department_name,
    COALESCE(cost_center.branch_id, 0) AS source_branch_key,
    cost_center.management_scope,
    cost_center.allocation_eligible,
    cost_center.valid_from,
    cost_center.valid_to,
    cost_center.is_active
FROM staging.stg_cost_centers cost_center;

CREATE UNIQUE INDEX ux_dim_cost_center_key ON marts.dim_cost_center (cost_center_key);
CREATE UNIQUE INDEX ux_dim_cost_center_natural ON marts.dim_cost_center (cost_center_id);
CREATE INDEX ix_dim_cost_center_department ON marts.dim_cost_center (department_code, management_scope);
COMMENT ON MATERIALIZED VIEW marts.dim_cost_center IS 'Centros de custo e escopo de responsabilidade.';

CREATE MATERIALIZED VIEW marts.dim_customer AS
SELECT
    0::BIGINT AS customer_key,
    0::BIGINT AS customer_id,
    'UNKNOWN'::VARCHAR(50) AS customer_code,
    'Unknown'::VARCHAR(150) AS customer_name,
    'UNKNOWN'::VARCHAR(150) AS customer_segment,
    'UNKNOWN'::VARCHAR(150) AS industry_segment,
    'Unknown'::VARCHAR(150) AS city,
    'UN'::VARCHAR(50) AS state_code,
    'UNKNOWN'::VARCHAR(150) AS region,
    0::BIGINT AS default_branch_key,
    'UNKNOWN'::VARCHAR(50) AS payment_term_code,
    0::NUMERIC(18,2) AS credit_limit,
    'UNKNOWN'::VARCHAR(150) AS freight_policy,
    'UNKNOWN'::VARCHAR(150) AS credit_risk_class,
    NULL::DATE AS registration_date,
    'UNKNOWN'::VARCHAR(150) AS customer_status,
    FALSE AS is_active
UNION ALL
SELECT
    customer.customer_id AS customer_key,
    customer.customer_id,
    customer.customer_code,
    COALESCE(customer.trade_name, customer.legal_name) AS customer_name,
    customer.customer_segment,
    customer.industry_segment,
    customer.city,
    customer.state_code,
    customer.region,
    COALESCE(customer.default_branch_id, 0) AS default_branch_key,
    customer.payment_term_code,
    customer.credit_limit,
    customer.freight_policy,
    customer.credit_risk_class,
    customer.registration_date,
    customer.customer_status,
    customer.is_active
FROM staging.stg_customers customer;

CREATE UNIQUE INDEX ux_dim_customer_key ON marts.dim_customer (customer_key);
CREATE UNIQUE INDEX ux_dim_customer_natural ON marts.dim_customer (customer_id);
CREATE INDEX ix_dim_customer_segmentation ON marts.dim_customer (customer_segment, region);
COMMENT ON MATERIALIZED VIEW marts.dim_customer IS 'Clientes, segmentacao comercial, regiao e risco.';

CREATE MATERIALIZED VIEW marts.dim_product AS
SELECT
    0::BIGINT AS product_key,
    0::BIGINT AS product_id,
    'UNKNOWN'::VARCHAR(50) AS product_code,
    'UNKNOWN'::VARCHAR(150) AS sku,
    'Unknown'::VARCHAR(150) AS product_name,
    0::BIGINT AS category_id,
    'UNKNOWN'::VARCHAR(50) AS category_code,
    'Unknown'::VARCHAR(150) AS category_name,
    'UNKNOWN'::VARCHAR(150) AS logistics_profile,
    'UNKNOWN'::VARCHAR(150) AS storage_class,
    'Unknown'::VARCHAR(150) AS brand_name,
    'UNKNOWN'::VARCHAR(50) AS model_code,
    'UNKNOWN'::VARCHAR(150) AS uom,
    0::NUMERIC(18,2) AS standard_cost,
    0::NUMERIC(18,2) AS list_price,
    0::NUMERIC(18,6) AS weight_kg,
    0::NUMERIC(18,6) AS volume_m3,
    'UNKNOWN'::VARCHAR(150) AS lifecycle_status,
    FALSE AS is_active
UNION ALL
SELECT
    product.product_id AS product_key,
    product.product_id,
    product.product_code,
    product.sku,
    product.product_name,
    product.category_id,
    category.category_code,
    category.category_name,
    category.logistics_profile,
    category.storage_class,
    product.brand_name,
    product.model_code,
    product.uom,
    product.standard_cost,
    product.list_price,
    product.weight_kg,
    product.volume_m3,
    product.lifecycle_status,
    product.is_active
FROM staging.stg_products product
JOIN staging.stg_product_categories category USING (category_id);

CREATE UNIQUE INDEX ux_dim_product_key ON marts.dim_product (product_key);
CREATE UNIQUE INDEX ux_dim_product_natural ON marts.dim_product (product_id);
CREATE INDEX ix_dim_product_category ON marts.dim_product (category_id, lifecycle_status);
COMMENT ON MATERIALIZED VIEW marts.dim_product IS 'Produtos enriquecidos com categoria e perfil logistico.';

CREATE MATERIALIZED VIEW marts.dim_carrier AS
SELECT
    0::BIGINT AS carrier_key,
    0::BIGINT AS carrier_id,
    'UNKNOWN'::VARCHAR(50) AS carrier_code,
    'Unknown'::VARCHAR(150) AS carrier_name,
    'UNKNOWN'::VARCHAR(150) AS carrier_type,
    'UNKNOWN'::VARCHAR(150) AS service_scope,
    'UNKNOWN'::VARCHAR(150) AS headquarters_state,
    'UNKNOWN'::VARCHAR(150) AS service_quality_tier,
    FALSE AS tracking_available,
    FALSE AS proof_of_delivery_available,
    'UNKNOWN'::VARCHAR(150) AS carrier_status,
    FALSE AS is_active
UNION ALL
SELECT
    carrier.carrier_id AS carrier_key,
    carrier.carrier_id,
    carrier.carrier_code,
    COALESCE(carrier.trade_name, carrier.legal_name) AS carrier_name,
    carrier.carrier_type,
    carrier.service_scope,
    carrier.headquarters_state,
    carrier.service_quality_tier,
    carrier.tracking_available,
    carrier.proof_of_delivery_available,
    carrier.carrier_status,
    carrier.is_active
FROM staging.stg_carriers carrier;

CREATE UNIQUE INDEX ux_dim_carrier_key ON marts.dim_carrier (carrier_key);
CREATE UNIQUE INDEX ux_dim_carrier_natural ON marts.dim_carrier (carrier_id);
COMMENT ON MATERIALIZED VIEW marts.dim_carrier IS 'Transportadoras e atributos de nivel de servico.';

CREATE MATERIALIZED VIEW marts.dim_sales_representative AS
SELECT
    0::BIGINT AS sales_rep_key,
    0::BIGINT AS sales_rep_id,
    'UNKNOWN'::VARCHAR(50) AS sales_rep_code,
    'Unknown'::VARCHAR(150) AS sales_rep_name,
    0::BIGINT AS home_branch_key,
    'UNKNOWN'::VARCHAR(150) AS sales_team,
    'UNKNOWN'::VARCHAR(150) AS sales_role,
    'UNKNOWN'::VARCHAR(150) AS territory,
    'UNKNOWN'::VARCHAR(150) AS customer_focus,
    0::NUMERIC(12,6) AS base_commission_pct,
    0::NUMERIC(18,2) AS monthly_sales_target,
    'UNKNOWN'::VARCHAR(150) AS sales_rep_status,
    FALSE AS is_active
UNION ALL
SELECT
    representative.sales_rep_id AS sales_rep_key,
    representative.sales_rep_id,
    representative.sales_rep_code,
    representative.sales_rep_name,
    COALESCE(representative.branch_id, 0) AS home_branch_key,
    representative.sales_team,
    representative.sales_role,
    representative.territory,
    representative.customer_focus,
    representative.base_commission_pct,
    representative.monthly_sales_target,
    representative.sales_rep_status,
    representative.is_active
FROM staging.stg_sales_representatives representative;

CREATE UNIQUE INDEX ux_dim_sales_representative_key ON marts.dim_sales_representative (sales_rep_key);
CREATE UNIQUE INDEX ux_dim_sales_representative_natural ON marts.dim_sales_representative (sales_rep_id);
COMMENT ON MATERIALIZED VIEW marts.dim_sales_representative IS 'Equipe comercial, territorio e metas.';

CREATE MATERIALIZED VIEW marts.fct_financial_entries AS
SELECT
    md5(concat_ws('|', financial.journal_line_id, COALESCE(allocation.allocated_branch_id, financial.branch_id, 0))) AS financial_entry_key,
    financial.journal_line_id,
    financial.journal_entry_id,
    financial.line_number,
    to_char(financial.competence_date, 'YYYYMMDD')::INTEGER AS competence_date_key,
    to_char(financial.posting_date, 'YYYYMMDD')::INTEGER AS posting_date_key,
    financial.company_id,
    COALESCE(allocation.allocated_branch_id, financial.branch_id, 0) AS branch_key,
    COALESCE(financial.branch_id, 0) AS source_branch_key,
    COALESCE(allocation.allocated_cost_center_id, financial.cost_center_id, 0) AS cost_center_key,
    account.account_id AS account_key,
    COALESCE(dre.display_order, 0)::SMALLINT AS dre_key,
    COALESCE(financial.customer_id, 0) AS customer_key,
    COALESCE(financial.supplier_id, 0) AS supplier_id,
    COALESCE(financial.carrier_id, 0) AS carrier_key,
    financial.entry_number,
    financial.account_code,
    financial.source_module,
    financial.source_document_type,
    financial.source_document_id,
    financial.entry_type,
    financial.is_reversal,
    financial.mapping_status,
    COALESCE(allocation.allocation_status, 'NOT_APPLICABLE') AS allocation_status,
    allocation.driver_type AS allocation_driver,
    COALESCE(allocation.allocation_weight, 1)::NUMERIC(24,12) AS allocation_weight,
    (financial.debit_amount * COALESCE(allocation.allocation_weight, 1))::NUMERIC(30,12) AS debit_amount,
    (financial.credit_amount * COALESCE(allocation.allocation_weight, 1))::NUMERIC(30,12) AS credit_amount,
    (financial.accounting_amount * COALESCE(allocation.allocation_weight, 1))::NUMERIC(30,12) AS accounting_amount,
    CASE
        WHEN financial.mapping_status = 'MAPPED' THEN allocation.allocated_management_amount
        ELSE NULL
    END::NUMERIC(30,12) AS management_amount,
    financial.pipeline_run_id,
    financial.line_ingestion_id,
    financial.source_file,
    financial.source_system
FROM intermediate.int_financial_entries financial
JOIN staging.stg_chart_of_accounts account USING (account_code)
LEFT JOIN intermediate.dre_lines dre USING (dre_line_id)
LEFT JOIN intermediate.int_financial_allocated allocation USING (journal_line_id);

CREATE UNIQUE INDEX ux_fct_financial_entries_key ON marts.fct_financial_entries (financial_entry_key);
CREATE INDEX ix_fct_financial_entries_dre ON marts.fct_financial_entries (competence_date_key, dre_key, branch_key);
CREATE INDEX ix_fct_financial_entries_account ON marts.fct_financial_entries (account_key, cost_center_key);
CREATE INDEX ix_fct_financial_entries_source ON marts.fct_financial_entries (source_document_type, source_document_id);
COMMENT ON MATERIALIZED VIEW marts.fct_financial_entries IS 'Partida contabil/gerencial aditiva, expandida por rateio quando aplicavel.';

CREATE MATERIALIZED VIEW marts.fct_budget AS
SELECT
    budget.dre_budget_id AS budget_key,
    budget.budget_version_id,
    budget.budget_version_code,
    budget.scenario,
    to_char(budget.competence_month, 'YYYYMMDD')::INTEGER AS date_key,
    budget.company_id,
    COALESCE(budget.branch_id, 0) AS branch_key,
    COALESCE(budget.cost_center_id, 0) AS cost_center_key,
    account.account_id AS account_key,
    dre.display_order::SMALLINT AS dre_key,
    budget.account_code,
    budget.management_group,
    budget.performance_nature,
    budget.budget_driver,
    budget.budget_driver_value,
    budget.source_budget_amount,
    budget.budget_amount,
    budget.currency_code,
    budget.budget_row_count
FROM intermediate.int_dre_budget budget
JOIN staging.stg_chart_of_accounts account USING (account_code)
JOIN intermediate.dre_lines dre USING (dre_line_id);

CREATE UNIQUE INDEX ux_fct_budget_key ON marts.fct_budget (budget_key);
CREATE INDEX ix_fct_budget_analysis ON marts.fct_budget (date_key, dre_key, branch_key);
CREATE INDEX ix_fct_budget_version ON marts.fct_budget (budget_version_id, account_key);
COMMENT ON MATERIALIZED VIEW marts.fct_budget IS 'Budget assinado e conformado as dimensoes do Actual.';

CREATE MATERIALIZED VIEW marts.fct_sales AS
SELECT
    item.invoice_item_id AS sales_key,
    item.invoice_item_id,
    invoice.invoice_id,
    item.invoice_line_number,
    item.order_id,
    item.order_item_id,
    to_char(invoice.competence_date, 'YYYYMMDD')::INTEGER AS date_key,
    to_char(invoice.issue_date, 'YYYYMMDD')::INTEGER AS issue_date_key,
    COALESCE(to_char(sales_order.order_date, 'YYYYMMDD')::INTEGER, 0) AS order_date_key,
    invoice.company_id,
    invoice.branch_id AS branch_key,
    invoice.customer_id AS customer_key,
    item.product_id AS product_key,
    COALESCE(sales_order.sales_rep_id, 0) AS sales_rep_key,
    invoice.invoice_number,
    invoice.invoice_status,
    item.item_status,
    COALESCE(sales_order.sales_channel, 'UNKNOWN') AS sales_channel,
    invoice.currency_code,
    item.billed_qty AS source_billed_qty,
    CASE WHEN invoice.invoice_status = 'ISSUED' AND item.item_status = 'ISSUED' THEN item.billed_qty ELSE 0 END AS sold_qty,
    item.list_unit_price,
    item.discount_pct,
    item.net_unit_price,
    item.gross_line_amount AS source_gross_amount,
    item.discount_amount AS source_discount_amount,
    item.net_line_amount AS source_net_amount,
    item.total_tax_amount AS source_tax_amount,
    CASE WHEN invoice.invoice_status = 'ISSUED' AND item.item_status = 'ISSUED' THEN item.gross_line_amount ELSE 0 END::NUMERIC(18,2) AS gross_sales_amount,
    CASE WHEN invoice.invoice_status = 'ISSUED' AND item.item_status = 'ISSUED' THEN item.discount_amount ELSE 0 END::NUMERIC(18,2) AS discount_amount,
    CASE WHEN invoice.invoice_status = 'ISSUED' AND item.item_status = 'ISSUED' THEN item.net_line_amount ELSE 0 END::NUMERIC(18,2) AS net_sales_amount,
    CASE WHEN invoice.invoice_status = 'ISSUED' AND item.item_status = 'ISSUED' THEN item.total_tax_amount ELSE 0 END::NUMERIC(18,2) AS sales_tax_amount,
    CASE WHEN invoice.invoice_status = 'CANCELED' OR item.item_status = 'CANCELED' THEN item.net_line_amount ELSE 0 END::NUMERIC(18,2) AS canceled_net_amount,
    (invoice.invoice_status = 'CANCELED' OR item.item_status = 'CANCELED') AS is_canceled,
    item.pipeline_run_id,
    item.ingestion_id,
    item.source_file,
    item.source_system
FROM staging.stg_invoice_items item
JOIN staging.stg_invoices invoice USING (invoice_id)
LEFT JOIN staging.stg_sales_orders sales_order ON sales_order.order_id = item.order_id;

CREATE UNIQUE INDEX ux_fct_sales_key ON marts.fct_sales (sales_key);
CREATE INDEX ix_fct_sales_analysis ON marts.fct_sales (date_key, branch_key, customer_key, product_key);
CREATE INDEX ix_fct_sales_invoice ON marts.fct_sales (invoice_id, invoice_line_number);
CREATE INDEX ix_fct_sales_representative ON marts.fct_sales (sales_rep_key, date_key);
COMMENT ON MATERIALIZED VIEW marts.fct_sales IS 'Item de NF com medidas de venda reconhecida e cancelamento separadas.';

CREATE MATERIALIZED VIEW marts.fct_deliveries AS
SELECT
    delivery.delivery_id AS delivery_key,
    delivery.delivery_id,
    delivery.invoice_id,
    delivery.order_id,
    to_char(delivery.shipment_date, 'YYYYMMDD')::INTEGER AS shipment_date_key,
    COALESCE(to_char(delivery.promised_delivery_date, 'YYYYMMDD')::INTEGER, 0) AS promised_delivery_date_key,
    COALESCE(to_char(delivery.actual_delivery_date, 'YYYYMMDD')::INTEGER, 0) AS actual_delivery_date_key,
    delivery.company_id,
    delivery.branch_id AS branch_key,
    delivery.customer_id AS customer_key,
    delivery.carrier_id AS carrier_key,
    delivery.carrier_rate_id,
    delivery.delivery_number,
    delivery.delivery_status,
    delivery.delivery_attempts,
    delivery.on_time_flag,
    delivery.origin_state,
    delivery.destination_state,
    delivery.destination_region,
    delivery.distance_km,
    delivery.total_weight_kg,
    delivery.total_volume_m3,
    delivery.declared_value,
    delivery.base_contract_amount,
    delivery.distance_component_amount,
    delivery.weight_component_amount,
    delivery.volume_component_amount,
    delivery.fuel_surcharge_amount,
    delivery.insurance_amount,
    delivery.toll_amount,
    delivery.handling_amount,
    delivery.freight_cost_total,
    delivery.freight_charged_to_customer,
    delivery.freight_subsidy_amount,
    delivery.freight_cost_pct_net_products,
    delivery.pipeline_run_id,
    delivery.ingestion_id,
    delivery.source_file,
    delivery.source_system
FROM staging.stg_deliveries delivery;

CREATE UNIQUE INDEX ux_fct_deliveries_key ON marts.fct_deliveries (delivery_key);
CREATE INDEX ix_fct_deliveries_analysis ON marts.fct_deliveries (shipment_date_key, branch_key, carrier_key);
CREATE INDEX ix_fct_deliveries_invoice ON marts.fct_deliveries (invoice_id);
COMMENT ON MATERIALIZED VIEW marts.fct_deliveries IS 'Entrega no grao operacional com SLA, custo, cobranca e subsidio de frete.';
""".strip() + "\n"
