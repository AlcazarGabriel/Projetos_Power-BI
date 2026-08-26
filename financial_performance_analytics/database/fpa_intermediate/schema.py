from __future__ import annotations


DRE_LINES = (
    ("01", "RECEITA_BRUTA", "Receita Bruta", 1, "GROUP", "REVENUE", False, None),
    ("02", "DEDUCOES", "(-) Deducoes", 2, "GROUP", "EXPENSE", False, None),
    ("03", "RECEITA_LIQUIDA", "Receita Liquida", 3, "SUBTOTAL", "RESULT", True, "01 + 02"),
    ("04", "CMV", "(-) CMV", 4, "GROUP", "EXPENSE", False, None),
    ("05", "LUCRO_BRUTO", "Lucro Bruto", 5, "SUBTOTAL", "RESULT", True, "03 + 04"),
    ("06", "DESPESAS_COMERCIAIS", "(-) Despesas Comerciais", 6, "GROUP", "EXPENSE", False, None),
    ("07", "LOGISTICA", "(-) Logistica", 7, "GROUP", "EXPENSE", False, None),
    ("08", "DESPESAS_ADMINISTRATIVAS", "(-) Despesas Administrativas", 8, "GROUP", "EXPENSE", False, None),
    ("09", "TECNOLOGIA", "(-) Tecnologia", 9, "GROUP", "EXPENSE", False, None),
    ("10", "RESULTADO_OPERACIONAL", "Resultado Operacional", 10, "SUBTOTAL", "RESULT", True, "05 + 06 + 07 + 08 + 09"),
    ("11", "RESULTADO_FINANCEIRO", "(+/-) Resultado Financeiro", 11, "GROUP", "MIXED", False, None),
    ("12", "RESULTADO_ANTES_TRIBUTOS", "Resultado Antes dos Tributos", 12, "SUBTOTAL", "RESULT", True, "10 + 11"),
    ("13", "TRIBUTOS", "(-) Tributos", 13, "GROUP", "EXPENSE", False, None),
    ("14", "LUCRO_LIQUIDO", "Lucro Liquido", 14, "SUBTOTAL", "RESULT", True, "12 + 13"),
)


ACCOUNT_GROUP_RULES = (
    ("4.01", "01", "RECEITA_PRODUTOS_E_FRETE", "CREDIT_POSITIVE", "REVENUE"),
    ("4.02", "02", "DEDUCOES_DA_RECEITA", "DEBIT_NEGATIVE", "DEDUCTION"),
    ("4.03", "01", "OUTRAS_RECEITAS_OPERACIONAIS", "CREDIT_POSITIVE", "REVENUE"),
    ("5.01", "04", "CUSTO_DAS_MERCADORIAS_VENDIDAS", "DEBIT_NEGATIVE", "COST"),
    ("5.02", "07", "CUSTOS_LOGISTICOS_DE_VENDA", "DEBIT_NEGATIVE", "LOGISTICS"),
    ("5.03", "07", "CUSTOS_DOS_CENTROS_DE_DISTRIBUICAO", "DEBIT_NEGATIVE", "LOGISTICS"),
    ("6.01", "06", "DESPESAS_COMERCIAIS", "DEBIT_NEGATIVE", "OPEX"),
    ("6.02", "08", "DESPESAS_ADMINISTRATIVAS", "DEBIT_NEGATIVE", "OPEX"),
    ("6.03", "09", "DESPESAS_DE_TECNOLOGIA", "DEBIT_NEGATIVE", "OPEX"),
    ("6.04", "08", "DESPESAS_COM_PESSOAS", "DEBIT_NEGATIVE", "OPEX"),
    ("6.05", "08", "OCUPACAO_E_FACILITIES", "DEBIT_NEGATIVE", "OPEX"),
    ("6.06", "08", "DEPRECIACAO_E_AMORTIZACAO", "DEBIT_NEGATIVE", "OPEX"),
    ("6.07", "08", "OUTRAS_DESPESAS_OPERACIONAIS", "DEBIT_NEGATIVE", "OPEX"),
    ("7.01", "11", "RECEITAS_FINANCEIRAS", "CREDIT_POSITIVE", "FINANCIAL"),
    ("7.02", "11", "DESPESAS_FINANCEIRAS", "DEBIT_NEGATIVE", "FINANCIAL"),
    ("7.03", "13", "TRIBUTOS_SOBRE_O_LUCRO", "DEBIT_NEGATIVE", "TAX"),
)


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _values(rows: tuple[tuple[object, ...], ...]) -> str:
    return ",\n        ".join("(" + ", ".join(_sql_literal(value) for value in row) + ")" for row in rows)


def generate_configuration_sql() -> str:
    dre_values = _values(DRE_LINES)
    mapping_rule_values = _values(ACCOUNT_GROUP_RULES)
    return f"""
SET client_encoding = 'UTF8';
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS control;
COMMENT ON SCHEMA intermediate IS 'Regras gerenciais, conciliacoes, rateios e enriquecimentos financeiros.';

CREATE TABLE IF NOT EXISTS intermediate.dre_lines (
    dre_line_id VARCHAR(10) PRIMARY KEY,
    dre_line_code VARCHAR(60) NOT NULL UNIQUE,
    dre_line_name VARCHAR(150) NOT NULL,
    display_order SMALLINT NOT NULL UNIQUE CHECK (display_order > 0),
    line_type VARCHAR(20) NOT NULL CHECK (line_type IN ('GROUP', 'SUBTOTAL')),
    performance_nature VARCHAR(20) NOT NULL CHECK (performance_nature IN ('REVENUE', 'EXPENSE', 'MIXED', 'RESULT')),
    is_calculated BOOLEAN NOT NULL,
    formula_expression TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK ((line_type = 'SUBTOTAL') = is_calculated),
    CHECK (NOT is_calculated OR formula_expression IS NOT NULL)
);

INSERT INTO intermediate.dre_lines (
    dre_line_id, dre_line_code, dre_line_name, display_order, line_type,
    performance_nature, is_calculated, formula_expression
)
VALUES
        {dre_values}
ON CONFLICT (dre_line_id) DO UPDATE SET
    dre_line_code = EXCLUDED.dre_line_code,
    dre_line_name = EXCLUDED.dre_line_name,
    display_order = EXCLUDED.display_order,
    line_type = EXCLUDED.line_type,
    performance_nature = EXCLUDED.performance_nature,
    is_calculated = EXCLUDED.is_calculated,
    formula_expression = EXCLUDED.formula_expression,
    is_active = TRUE,
    updated_at = clock_timestamp();

CREATE TABLE IF NOT EXISTS intermediate.account_dre_mapping (
    mapping_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_code VARCHAR(50) NOT NULL,
    dre_line_id VARCHAR(10) NOT NULL REFERENCES intermediate.dre_lines(dre_line_id),
    management_group VARCHAR(100) NOT NULL,
    sign_rule VARCHAR(30) NOT NULL CHECK (sign_rule IN ('CREDIT_POSITIVE', 'DEBIT_POSITIVE', 'DEBIT_NEGATIVE')),
    performance_nature VARCHAR(30) NOT NULL CHECK (performance_nature IN ('REVENUE', 'DEDUCTION', 'COST', 'LOGISTICS', 'OPEX', 'FINANCIAL', 'TAX')),
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    mapping_source VARCHAR(30) NOT NULL DEFAULT 'DEFAULT_SEED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_account_dre_mapping_version UNIQUE (account_code, valid_from),
    CONSTRAINT ck_account_dre_mapping_dates CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE INDEX IF NOT EXISTS ix_account_dre_mapping_lookup
    ON intermediate.account_dre_mapping (account_code, valid_from, valid_to)
    WHERE is_active;
CREATE INDEX IF NOT EXISTS ix_account_dre_mapping_dre
    ON intermediate.account_dre_mapping (dre_line_id, account_code);

CREATE OR REPLACE FUNCTION intermediate.prevent_account_dre_mapping_overlap()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.is_active AND EXISTS (
        SELECT 1
        FROM intermediate.account_dre_mapping current_mapping
        WHERE current_mapping.account_code = NEW.account_code
          AND current_mapping.is_active
          AND current_mapping.mapping_id <> COALESCE(NEW.mapping_id, -1)
          AND daterange(current_mapping.valid_from, COALESCE(current_mapping.valid_to, 'infinity'::date), '[]')
              && daterange(NEW.valid_from, COALESCE(NEW.valid_to, 'infinity'::date), '[]')
    ) THEN
        RAISE EXCEPTION 'Overlapping active DRE mapping for account %', NEW.account_code;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_account_dre_mapping_no_overlap ON intermediate.account_dre_mapping;
CREATE TRIGGER trg_account_dre_mapping_no_overlap
BEFORE INSERT OR UPDATE ON intermediate.account_dre_mapping
FOR EACH ROW EXECUTE FUNCTION intermediate.prevent_account_dre_mapping_overlap();

WITH mapping_rules (account_prefix, dre_line_id, management_group, sign_rule, performance_nature) AS (
    VALUES
        {mapping_rule_values}
), source_mapping AS (
    SELECT
        account.account_code,
        rule.dre_line_id,
        rule.management_group,
        rule.sign_rule,
        rule.performance_nature,
        account.valid_from,
        account.valid_to,
        account.is_active,
        'DEFAULT_SEED'::VARCHAR(30) AS mapping_source
    FROM staging.stg_chart_of_accounts account
    JOIN mapping_rules rule
      ON account.account_code LIKE rule.account_prefix || '.%'
    WHERE account.is_postable
      AND account.is_result_account
)
MERGE INTO intermediate.account_dre_mapping AS target
USING source_mapping AS source
ON target.account_code = source.account_code
AND target.valid_from = source.valid_from
WHEN MATCHED THEN UPDATE SET
    dre_line_id = source.dre_line_id,
    management_group = source.management_group,
    sign_rule = source.sign_rule,
    performance_nature = source.performance_nature,
    valid_to = source.valid_to,
    is_active = source.is_active,
    updated_at = clock_timestamp()
WHEN NOT MATCHED THEN INSERT (
    account_code, dre_line_id, management_group, sign_rule, performance_nature,
    valid_from, valid_to, is_active, mapping_source
) VALUES (
    source.account_code, source.dre_line_id, source.management_group, source.sign_rule,
    source.performance_nature, source.valid_from, source.valid_to, source.is_active,
    source.mapping_source
);

CREATE TABLE IF NOT EXISTS intermediate.int_allocation_rules (
    allocation_rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_code VARCHAR(120) NOT NULL,
    account_code VARCHAR(50) NOT NULL,
    target_branch_id BIGINT NOT NULL,
    driver_type VARCHAR(30) NOT NULL CHECK (driver_type IN ('REVENUE', 'HEADCOUNT', 'FIXED_PERCENTAGE')),
    fixed_percentage NUMERIC(18,10),
    priority SMALLINT NOT NULL DEFAULT 100,
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_int_allocation_rules_version UNIQUE (account_code, target_branch_id, valid_from),
    CONSTRAINT ck_int_allocation_rules_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ck_int_allocation_rules_percentage CHECK (fixed_percentage IS NULL OR fixed_percentage BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS ix_int_allocation_rules_lookup
    ON intermediate.int_allocation_rules (account_code, valid_from, valid_to)
    WHERE is_active;

WITH active_branches AS (
    SELECT branch_id, COUNT(*) OVER ()::NUMERIC AS branch_count
    FROM staging.stg_branches
    WHERE is_active
), allocation_accounts AS (
    SELECT mapping.account_code, mapping.valid_from, mapping.valid_to,
           CASE
               WHEN mapping.dre_line_id IN ('06', '07') THEN 'REVENUE'
               WHEN mapping.account_code IN (
                   '6.02.001', '6.02.002', '6.02.003', '6.03.001',
                   '6.03.004', '6.03.007', '6.04.001', '6.04.002', '6.04.005'
               ) THEN 'HEADCOUNT'
               ELSE 'FIXED_PERCENTAGE'
           END AS driver_type
    FROM intermediate.account_dre_mapping mapping
    WHERE mapping.is_active
      AND mapping.dre_line_id IN ('06', '07', '08', '09')
)
INSERT INTO intermediate.int_allocation_rules (
    rule_code, account_code, target_branch_id, driver_type, fixed_percentage,
    valid_from, valid_to, is_active
)
SELECT
    'ALLOC_' || REPLACE(account.account_code, '.', '_') || '_B' || LPAD(branch.branch_id::TEXT, 2, '0'),
    account.account_code,
    branch.branch_id,
    account.driver_type,
    1 / branch.branch_count,
    account.valid_from,
    account.valid_to,
    TRUE
FROM allocation_accounts account
CROSS JOIN active_branches branch
ON CONFLICT (account_code, target_branch_id, valid_from) DO UPDATE SET
    rule_code = EXCLUDED.rule_code,
    driver_type = EXCLUDED.driver_type,
    fixed_percentage = EXCLUDED.fixed_percentage,
    valid_to = EXCLUDED.valid_to,
    is_active = TRUE,
    updated_at = clock_timestamp();

CREATE TABLE IF NOT EXISTS control.intermediate_quality_runs (
    quality_run_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ended_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING', 'PASSED', 'FAILED')),
    tests_passed INTEGER NOT NULL DEFAULT 0,
    tests_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS control.intermediate_quality_results (
    quality_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quality_run_id UUID NOT NULL REFERENCES control.intermediate_quality_runs(quality_run_id),
    test_name VARCHAR(150) NOT NULL,
    source_entity VARCHAR(100),
    status VARCHAR(10) NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    issue_count BIGINT NOT NULL CHECK (issue_count >= 0),
    details TEXT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS ix_intermediate_quality_results_run
    ON control.intermediate_quality_results (quality_run_id);
""".strip() + "\n"


def generate_models_sql() -> str:
    return r"""
DROP MATERIALIZED VIEW IF EXISTS intermediate.int_performance_drivers;
DROP MATERIALIZED VIEW IF EXISTS intermediate.int_financial_allocated;
DROP MATERIALIZED VIEW IF EXISTS intermediate.int_reconciliation_logistics_accounting;
DROP MATERIALIZED VIEW IF EXISTS intermediate.int_reconciliation_commercial_accounting;
DROP MATERIALIZED VIEW IF EXISTS intermediate.int_dre_budget;
DROP MATERIALIZED VIEW IF EXISTS intermediate.int_dre_actual;
DROP MATERIALIZED VIEW IF EXISTS intermediate.int_financial_entries;

CREATE MATERIALIZED VIEW intermediate.int_financial_entries AS
SELECT
    line.journal_line_id,
    line.journal_entry_id,
    line.line_number,
    entry.entry_number,
    entry.posting_date,
    entry.document_date,
    entry.competence_date,
    date_trunc('month', entry.competence_date)::DATE AS competence_month,
    entry.fiscal_year,
    entry.fiscal_period,
    entry.company_id,
    entry.branch_id,
    line.cost_center_id,
    line.customer_id,
    line.supplier_id,
    line.carrier_id,
    line.account_code,
    account.account_name,
    account.account_type,
    account.normal_balance,
    account.is_result_account,
    line.debit_amount,
    line.credit_amount,
    (line.debit_amount - line.credit_amount)::NUMERIC(18,2) AS accounting_amount,
    CASE mapping.sign_rule
        WHEN 'CREDIT_POSITIVE' THEN line.credit_amount - line.debit_amount
        WHEN 'DEBIT_POSITIVE' THEN line.debit_amount - line.credit_amount
        WHEN 'DEBIT_NEGATIVE' THEN line.credit_amount - line.debit_amount
    END::NUMERIC(18,2) AS management_amount,
    mapping.mapping_id,
    mapping.dre_line_id,
    mapping.management_group,
    mapping.sign_rule,
    mapping.performance_nature,
    CASE
        WHEN NOT account.is_result_account THEN 'NOT_APPLICABLE'
        WHEN mapping.mapping_id IS NULL THEN 'UNMAPPED'
        ELSE 'MAPPED'
    END::VARCHAR(20) AS mapping_status,
    entry.source_module,
    entry.source_document_type,
    entry.source_document_id,
    entry.entry_type,
    (entry.entry_type = 'REVERSAL') AS is_reversal,
    line.reference_document_type,
    line.reference_document_id,
    line.line_description,
    line.ingestion_id AS line_ingestion_id,
    entry.ingestion_id AS entry_ingestion_id,
    line.pipeline_run_id,
    line.source_file,
    line.source_system,
    line.ingested_at
FROM staging.stg_journal_lines line
JOIN staging.stg_journal_entries entry USING (journal_entry_id)
JOIN staging.stg_chart_of_accounts account USING (account_code)
LEFT JOIN intermediate.account_dre_mapping mapping
  ON mapping.account_code = line.account_code
 AND entry.competence_date >= mapping.valid_from
 AND entry.competence_date <= COALESCE(mapping.valid_to, 'infinity'::DATE)
 AND mapping.is_active
WHERE entry.posting_status = 'POSTED';

CREATE UNIQUE INDEX ux_int_financial_entries_line
    ON intermediate.int_financial_entries (journal_line_id);
CREATE INDEX ix_int_financial_entries_competence
    ON intermediate.int_financial_entries (competence_month, branch_id, cost_center_id);
CREATE INDEX ix_int_financial_entries_dre
    ON intermediate.int_financial_entries (dre_line_id, account_code, competence_month);
CREATE INDEX ix_int_financial_entries_source_document
    ON intermediate.int_financial_entries (source_document_type, source_document_id);

COMMENT ON MATERIALIZED VIEW intermediate.int_financial_entries IS
    'Razao enriquecido com mapeamento DRE temporal, valor contabil preservado e sinal gerencial.';

CREATE MATERIALIZED VIEW intermediate.int_dre_actual AS
SELECT
    md5(concat_ws('|', financial.competence_month, financial.company_id,
        COALESCE(financial.branch_id, 0), COALESCE(financial.cost_center_id, 0),
        financial.account_code, financial.dre_line_id)) AS dre_actual_id,
    financial.competence_month,
    financial.company_id,
    financial.branch_id,
    financial.cost_center_id,
    financial.account_code,
    MAX(financial.account_name) AS account_name,
    financial.dre_line_id,
    MAX(financial.management_group) AS management_group,
    MAX(financial.performance_nature) AS performance_nature,
    SUM(financial.debit_amount)::NUMERIC(24,2) AS debit_amount,
    SUM(financial.credit_amount)::NUMERIC(24,2) AS credit_amount,
    SUM(financial.accounting_amount)::NUMERIC(24,2) AS accounting_amount,
    SUM(financial.management_amount)::NUMERIC(24,2) AS actual_amount,
    COUNT(DISTINCT financial.journal_entry_id)::BIGINT AS journal_entry_count,
    COUNT(*)::BIGINT AS journal_line_count,
    MIN(financial.competence_date) AS first_competence_date,
    MAX(financial.competence_date) AS last_competence_date
FROM intermediate.int_financial_entries financial
WHERE financial.mapping_status = 'MAPPED'
GROUP BY
    financial.competence_month, financial.company_id, financial.branch_id,
    financial.cost_center_id, financial.account_code, financial.dre_line_id;

CREATE UNIQUE INDEX ux_int_dre_actual_grain
    ON intermediate.int_dre_actual (
        competence_month, company_id, COALESCE(branch_id, 0),
        COALESCE(cost_center_id, 0), account_code, dre_line_id
    );
CREATE INDEX ix_int_dre_actual_reporting
    ON intermediate.int_dre_actual (competence_month, dre_line_id, branch_id);

COMMENT ON MATERIALIZED VIEW intermediate.int_dre_actual IS
    'Actual no grao competencia x empresa x filial x centro de custo x conta x linha DRE.';

CREATE MATERIALIZED VIEW intermediate.int_dre_budget AS
SELECT
    md5(concat_ws('|', budget.budget_version_id, to_date(budget.period || '-01', 'YYYY-MM-DD'),
        budget.company_id, COALESCE(budget.branch_id, 0), COALESCE(budget.cost_center_id, 0),
        budget.account_code, mapping.dre_line_id)) AS dre_budget_id,
    budget.budget_version_id,
    budget.budget_version_code,
    budget.scenario,
    to_date(budget.period || '-01', 'YYYY-MM-DD') AS competence_month,
    budget.company_id,
    budget.branch_id,
    budget.cost_center_id,
    budget.account_code,
    MAX(account.account_name) AS account_name,
    mapping.dre_line_id,
    MAX(mapping.management_group) AS management_group,
    MAX(mapping.performance_nature) AS performance_nature,
    MAX(budget.budget_driver) AS budget_driver,
    SUM(budget.budget_driver_value)::NUMERIC(24,6) AS budget_driver_value,
    SUM(budget.budget_amount)::NUMERIC(24,2) AS source_budget_amount,
    SUM(CASE mapping.sign_rule
        WHEN 'CREDIT_POSITIVE' THEN budget.budget_amount
        WHEN 'DEBIT_POSITIVE' THEN budget.budget_amount
        WHEN 'DEBIT_NEGATIVE' THEN -budget.budget_amount
    END)::NUMERIC(24,2) AS budget_amount,
    MAX(budget.currency_code) AS currency_code,
    COUNT(*)::BIGINT AS budget_row_count
FROM staging.stg_budget budget
JOIN staging.stg_chart_of_accounts account USING (account_code)
JOIN intermediate.account_dre_mapping mapping
  ON mapping.account_code = budget.account_code
 AND to_date(budget.period || '-01', 'YYYY-MM-DD') >= mapping.valid_from
 AND to_date(budget.period || '-01', 'YYYY-MM-DD') <= COALESCE(mapping.valid_to, 'infinity'::DATE)
 AND mapping.is_active
GROUP BY
    budget.budget_version_id, budget.budget_version_code, budget.scenario,
    to_date(budget.period || '-01', 'YYYY-MM-DD'), budget.company_id,
    budget.branch_id, budget.cost_center_id, budget.account_code, mapping.dre_line_id;

CREATE UNIQUE INDEX ux_int_dre_budget_grain
    ON intermediate.int_dre_budget (
        budget_version_id, competence_month, company_id, COALESCE(branch_id, 0),
        COALESCE(cost_center_id, 0), account_code, dre_line_id
    );
CREATE INDEX ix_int_dre_budget_reporting
    ON intermediate.int_dre_budget (competence_month, dre_line_id, branch_id);

COMMENT ON MATERIALIZED VIEW intermediate.int_dre_budget IS
    'Budget normalizado no mesmo grao dimensional e na mesma regra de sinal do Actual.';

CREATE MATERIALIZED VIEW intermediate.int_reconciliation_commercial_accounting AS
WITH accounting AS (
    SELECT
        entry.source_document_id::BIGINT AS invoice_id,
        MIN(entry.competence_date) AS accounting_competence_date,
        MIN(entry.posting_date) AS first_posting_date,
        MAX(entry.posting_date) AS last_posting_date,
        SUM(financial.management_amount)::NUMERIC(24,2) AS accounting_amount,
        COUNT(DISTINCT entry.journal_entry_id)::BIGINT AS accounting_entry_count,
        COUNT(DISTINCT entry.journal_entry_id) FILTER (WHERE entry.entry_type = 'REVERSAL')::BIGINT AS reversal_entry_count
    FROM staging.stg_journal_entries entry
    JOIN intermediate.int_financial_entries financial USING (journal_entry_id)
    WHERE entry.source_document_type IN ('INVOICE', 'INVOICE_CANCELLATION')
      AND entry.source_document_id ~ '^[0-9]+$'
      AND financial.mapping_status = 'MAPPED'
    GROUP BY entry.source_document_id::BIGINT
)
SELECT
    COALESCE(invoice.invoice_id, accounting.invoice_id) AS invoice_id,
    invoice.invoice_number,
    invoice.invoice_status,
    invoice.competence_date AS commercial_competence_date,
    accounting.accounting_competence_date,
    invoice.company_id,
    invoice.branch_id,
    invoice.customer_id,
    invoice.invoice_total_amount AS commercial_amount,
    accounting.accounting_amount,
    (COALESCE(accounting.accounting_amount, 0) -
        CASE WHEN invoice.invoice_status = 'CANCELED' THEN 0 ELSE COALESCE(invoice.invoice_total_amount, 0) END
    )::NUMERIC(24,2) AS difference_amount,
    accounting.accounting_entry_count,
    accounting.reversal_entry_count,
    accounting.first_posting_date,
    accounting.last_posting_date,
    CASE
        WHEN invoice.invoice_id IS NULL THEN 'MISSING_COMMERCIAL'
        WHEN invoice.invoice_status = 'CANCELED' THEN 'CANCELED'
        WHEN accounting.invoice_id IS NULL THEN 'MISSING_ACCOUNTING'
        WHEN date_trunc('month', invoice.competence_date) <> date_trunc('month', accounting.accounting_competence_date)
            THEN 'TIMING_DIFFERENCE'
        WHEN ABS(invoice.invoice_total_amount - accounting.accounting_amount) > 0.01 THEN 'VALUE_MISMATCH'
        ELSE 'MATCHED'
    END::VARCHAR(30) AS reconciliation_status
FROM staging.stg_invoices invoice
FULL OUTER JOIN accounting USING (invoice_id);

CREATE UNIQUE INDEX ux_int_reconciliation_commercial_invoice
    ON intermediate.int_reconciliation_commercial_accounting (invoice_id);
CREATE INDEX ix_int_reconciliation_commercial_status
    ON intermediate.int_reconciliation_commercial_accounting (reconciliation_status, commercial_competence_date);

COMMENT ON MATERIALIZED VIEW intermediate.int_reconciliation_commercial_accounting IS
    'Conciliacao por NF entre faturamento e contas de resultado contabilizadas, incluindo estornos.';

CREATE MATERIALIZED VIEW intermediate.int_reconciliation_logistics_accounting AS
WITH logistics AS (
    SELECT
        delivery.shipment_date,
        delivery.branch_id,
        delivery.carrier_id,
        COUNT(*)::BIGINT AS delivery_count,
        SUM(delivery.freight_cost_total)::NUMERIC(24,2) AS logistics_amount
    FROM staging.stg_deliveries delivery
    GROUP BY delivery.shipment_date, delivery.branch_id, delivery.carrier_id
), accounting AS (
    SELECT
        entry.competence_date AS accounting_competence_date,
        entry.branch_id,
        substring(entry.source_document_id FROM 'C([0-9]+)$')::BIGINT AS carrier_id,
        MIN(left(entry.source_document_id, 10)::DATE) AS source_batch_date,
        COUNT(DISTINCT entry.journal_entry_id)::BIGINT AS accounting_entry_count,
        SUM(line.debit_amount - line.credit_amount)::NUMERIC(24,2) AS accounting_amount
    FROM staging.stg_journal_entries entry
    JOIN staging.stg_journal_lines line USING (journal_entry_id)
    WHERE entry.source_document_type = 'DAILY_FREIGHT_BATCH'
      AND line.account_code = '5.02.001'
      AND entry.source_document_id ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}-B[0-9]+-C[0-9]+$'
    GROUP BY
        entry.competence_date, entry.branch_id,
        substring(entry.source_document_id FROM 'C([0-9]+)$')::BIGINT
)
SELECT
    md5(concat_ws('|', COALESCE(logistics.shipment_date, accounting.source_batch_date),
        COALESCE(logistics.branch_id, accounting.branch_id),
        COALESCE(logistics.carrier_id, accounting.carrier_id))) AS reconciliation_id,
    logistics.shipment_date,
    accounting.accounting_competence_date,
    accounting.source_batch_date,
    COALESCE(logistics.branch_id, accounting.branch_id) AS branch_id,
    COALESCE(logistics.carrier_id, accounting.carrier_id) AS carrier_id,
    logistics.delivery_count,
    logistics.logistics_amount,
    accounting.accounting_amount,
    (COALESCE(accounting.accounting_amount, 0) - COALESCE(logistics.logistics_amount, 0))::NUMERIC(24,2) AS difference_amount,
    accounting.accounting_entry_count,
    CASE
        WHEN logistics.shipment_date IS NULL THEN 'MISSING_LOGISTICS'
        WHEN accounting.accounting_competence_date IS NULL THEN 'MISSING_ACCOUNTING'
        WHEN logistics.shipment_date <> accounting.accounting_competence_date
          OR accounting.source_batch_date <> accounting.accounting_competence_date THEN 'TIMING_DIFFERENCE'
        WHEN ABS(logistics.logistics_amount - accounting.accounting_amount) > 0.01 THEN 'VALUE_MISMATCH'
        ELSE 'MATCHED'
    END::VARCHAR(30) AS reconciliation_status
FROM logistics
FULL OUTER JOIN accounting
  ON accounting.source_batch_date = logistics.shipment_date
 AND accounting.branch_id = logistics.branch_id
 AND accounting.carrier_id = logistics.carrier_id;

CREATE UNIQUE INDEX ux_int_reconciliation_logistics_grain
    ON intermediate.int_reconciliation_logistics_accounting (reconciliation_id);
CREATE INDEX ix_int_reconciliation_logistics_status
    ON intermediate.int_reconciliation_logistics_accounting (reconciliation_status, shipment_date);

COMMENT ON MATERIALIZED VIEW intermediate.int_reconciliation_logistics_accounting IS
    'Conciliacao de frete no grao data de expedicao x filial x transportadora.';

CREATE MATERIALIZED VIEW intermediate.int_financial_allocated AS
WITH branch_driver AS (
    SELECT
        periods.competence_month,
        branch.branch_id,
        COALESCE(revenue.revenue_amount, 0)::NUMERIC AS revenue_amount,
        COALESCE(headcount.headcount, 0)::NUMERIC AS headcount,
        SUM(COALESCE(revenue.revenue_amount, 0)) OVER (PARTITION BY periods.competence_month)::NUMERIC AS total_revenue,
        SUM(COALESCE(headcount.headcount, 0)) OVER (PARTITION BY periods.competence_month)::NUMERIC AS total_headcount
    FROM (SELECT DISTINCT competence_month FROM intermediate.int_financial_entries) periods
    CROSS JOIN (SELECT branch_id FROM staging.stg_branches WHERE is_active) branch
    LEFT JOIN (
        SELECT competence_month, branch_id, SUM(actual_amount) AS revenue_amount
        FROM intermediate.int_dre_actual
        WHERE dre_line_id = '01' AND branch_id IS NOT NULL
        GROUP BY competence_month, branch_id
    ) revenue USING (competence_month, branch_id)
    LEFT JOIN (
        SELECT to_date(period || '-01', 'YYYY-MM-DD') AS competence_month,
               branch_id, SUM(headcount)::NUMERIC AS headcount
        FROM staging.stg_headcount_monthly
        WHERE branch_id IS NOT NULL
        GROUP BY to_date(period || '-01', 'YYYY-MM-DD'), branch_id
    ) headcount USING (competence_month, branch_id)
), eligible AS (
    SELECT financial.*
    FROM intermediate.int_financial_entries financial
    JOIN staging.stg_cost_centers cost_center USING (cost_center_id)
    WHERE financial.mapping_status = 'MAPPED'
      AND cost_center.management_scope = 'CORPORATE'
      AND cost_center.allocation_eligible
      AND EXISTS (
          SELECT 1
          FROM intermediate.int_allocation_rules rule
          WHERE rule.account_code = financial.account_code
            AND rule.is_active
            AND financial.competence_date >= rule.valid_from
            AND financial.competence_date <= COALESCE(rule.valid_to, 'infinity'::DATE)
      )
), allocated AS (
    SELECT
        financial.journal_line_id,
        financial.journal_entry_id,
        financial.competence_date,
        financial.competence_month,
        financial.company_id,
        financial.branch_id AS source_branch_id,
        rule.target_branch_id AS allocated_branch_id,
        financial.cost_center_id AS source_cost_center_id,
        financial.cost_center_id AS allocated_cost_center_id,
        financial.account_code,
        financial.dre_line_id,
        financial.management_group,
        financial.performance_nature,
        financial.management_amount AS source_management_amount,
        rule.allocation_rule_id,
        rule.driver_type,
        CASE rule.driver_type
            WHEN 'REVENUE' THEN COALESCE(driver.revenue_amount / NULLIF(driver.total_revenue, 0), rule.fixed_percentage)
            WHEN 'HEADCOUNT' THEN COALESCE(driver.headcount / NULLIF(driver.total_headcount, 0), rule.fixed_percentage)
            WHEN 'FIXED_PERCENTAGE' THEN rule.fixed_percentage
        END::NUMERIC(24,12) AS allocation_weight,
        (financial.management_amount * CASE rule.driver_type
            WHEN 'REVENUE' THEN COALESCE(driver.revenue_amount / NULLIF(driver.total_revenue, 0), rule.fixed_percentage)
            WHEN 'HEADCOUNT' THEN COALESCE(driver.headcount / NULLIF(driver.total_headcount, 0), rule.fixed_percentage)
            WHEN 'FIXED_PERCENTAGE' THEN rule.fixed_percentage
        END)::NUMERIC(30,12) AS allocated_management_amount,
        'ALLOCATED'::VARCHAR(30) AS allocation_status,
        financial.source_module,
        financial.source_document_type,
        financial.source_document_id
    FROM eligible financial
    JOIN intermediate.int_allocation_rules rule
      ON rule.account_code = financial.account_code
     AND rule.is_active
     AND financial.competence_date >= rule.valid_from
     AND financial.competence_date <= COALESCE(rule.valid_to, 'infinity'::DATE)
    JOIN branch_driver driver
      ON driver.competence_month = financial.competence_month
     AND driver.branch_id = rule.target_branch_id
), direct AS (
    SELECT
        financial.journal_line_id,
        financial.journal_entry_id,
        financial.competence_date,
        financial.competence_month,
        financial.company_id,
        financial.branch_id AS source_branch_id,
        COALESCE(financial.branch_id, cost_center.branch_id) AS allocated_branch_id,
        financial.cost_center_id AS source_cost_center_id,
        financial.cost_center_id AS allocated_cost_center_id,
        financial.account_code,
        financial.dre_line_id,
        financial.management_group,
        financial.performance_nature,
        financial.management_amount AS source_management_amount,
        NULL::BIGINT AS allocation_rule_id,
        NULL::VARCHAR(30) AS driver_type,
        1::NUMERIC(24,12) AS allocation_weight,
        financial.management_amount::NUMERIC(30,12) AS allocated_management_amount,
        CASE
            WHEN cost_center.management_scope = 'CORPORATE' AND cost_center.allocation_eligible
                THEN 'RULE_NOT_APPLICABLE'
            ELSE 'DIRECT'
        END::VARCHAR(30) AS allocation_status,
        financial.source_module,
        financial.source_document_type,
        financial.source_document_id
    FROM intermediate.int_financial_entries financial
    LEFT JOIN staging.stg_cost_centers cost_center USING (cost_center_id)
    WHERE financial.mapping_status = 'MAPPED'
      AND NOT EXISTS (SELECT 1 FROM eligible WHERE eligible.journal_line_id = financial.journal_line_id)
)
SELECT * FROM direct
UNION ALL
SELECT * FROM allocated;

CREATE UNIQUE INDEX ux_int_financial_allocated_grain
    ON intermediate.int_financial_allocated (journal_line_id, COALESCE(allocated_branch_id, 0));
CREATE INDEX ix_int_financial_allocated_reporting
    ON intermediate.int_financial_allocated (competence_month, allocated_branch_id, dre_line_id);

COMMENT ON MATERIALIZED VIEW intermediate.int_financial_allocated IS
    'Partidas DRE diretas ou redistribuidas por filial; total consolidado preservado.';

CREATE MATERIALIZED VIEW intermediate.int_performance_drivers AS
WITH actual_commercial AS (
    SELECT
        date_trunc('month', invoice.competence_date)::DATE AS competence_month,
        invoice.company_id,
        invoice.branch_id,
        item.category_id,
        SUM(item.billed_qty)::NUMERIC AS billed_qty,
        SUM(item.gross_line_amount)::NUMERIC AS gross_revenue,
        SUM(item.discount_amount)::NUMERIC AS discount_amount,
        SUM(item.net_line_amount)::NUMERIC AS net_revenue
    FROM staging.stg_invoices invoice
    JOIN staging.stg_invoice_items item USING (invoice_id)
    WHERE invoice.invoice_status = 'ISSUED' AND item.item_status = 'ISSUED'
    GROUP BY date_trunc('month', invoice.competence_date)::DATE,
             invoice.company_id, invoice.branch_id, item.category_id
), branch_commercial AS (
    SELECT competence_month, company_id, branch_id,
           SUM(billed_qty) AS billed_qty, SUM(gross_revenue) AS gross_revenue,
           SUM(discount_amount) AS discount_amount, SUM(net_revenue) AS net_revenue
    FROM actual_commercial
    GROUP BY competence_month, company_id, branch_id
), commercial_baseline AS (
    SELECT company_id, branch_id,
           MAX(billed_qty) FILTER (WHERE competence_month = DATE '2024-01-01') AS base_volume,
           MAX(gross_revenue / NULLIF(billed_qty, 0)) FILTER (WHERE competence_month = DATE '2024-01-01') AS base_price
    FROM branch_commercial
    GROUP BY company_id, branch_id
), assumption AS (
    SELECT to_date(period || '-01', 'YYYY-MM-DD') AS competence_month,
           branch_id, budget_version_id, planned_volume_index, planned_price_index,
           planned_discount_pct, planned_freight_cost_pct
    FROM staging.stg_budget_assumptions
), volume_price_discount AS (
    SELECT
        actual.competence_month, actual.company_id, actual.branch_id, NULL::BIGINT AS category_id,
        assumption.budget_version_id,
        driver.driver_name,
        driver.dre_line_id,
        driver.comparison_basis,
        CASE driver.driver_name
            WHEN 'VOLUME' THEN actual.billed_qty / NULLIF(baseline.base_volume, 0)
            WHEN 'PRICE' THEN (actual.gross_revenue / NULLIF(actual.billed_qty, 0)) / NULLIF(baseline.base_price, 0)
            WHEN 'DISCOUNT' THEN actual.discount_amount / NULLIF(actual.gross_revenue, 0)
        END::NUMERIC(24,8) AS actual_value,
        CASE driver.driver_name
            WHEN 'VOLUME' THEN assumption.planned_volume_index
            WHEN 'PRICE' THEN assumption.planned_price_index
            WHEN 'DISCOUNT' THEN assumption.planned_discount_pct
        END::NUMERIC(24,8) AS budget_value
    FROM branch_commercial actual
    JOIN commercial_baseline baseline USING (company_id, branch_id)
    LEFT JOIN assumption USING (competence_month, branch_id)
    CROSS JOIN (VALUES
        ('VOLUME'::VARCHAR, '01'::VARCHAR, 'INDEX'::VARCHAR),
        ('PRICE'::VARCHAR, '01'::VARCHAR, 'INDEX'::VARCHAR),
        ('DISCOUNT'::VARCHAR, '02'::VARCHAR, 'PERCENTAGE'::VARCHAR)
    ) driver(driver_name, dre_line_id, comparison_basis)
), mix AS (
    SELECT
        actual.competence_month, actual.company_id, actual.branch_id, actual.category_id,
        budget.budget_version_id,
        'MIX'::VARCHAR AS driver_name,
        '01'::VARCHAR AS dre_line_id,
        'PERCENTAGE'::VARCHAR AS comparison_basis,
        (actual.gross_revenue / NULLIF(SUM(actual.gross_revenue) OVER (
            PARTITION BY actual.competence_month, actual.company_id, actual.branch_id
        ), 0))::NUMERIC(24,8) AS actual_value,
        budget.planned_mix_pct::NUMERIC(24,8) AS budget_value
    FROM actual_commercial actual
    LEFT JOIN staging.stg_budget_product_mix budget
      ON to_date(budget.period || '-01', 'YYYY-MM-DD') = actual.competence_month
     AND budget.branch_id = actual.branch_id
     AND budget.category_id = actual.category_id
), logistics AS (
    SELECT
        commercial.competence_month, commercial.company_id, commercial.branch_id,
        NULL::BIGINT AS category_id, assumption.budget_version_id,
        'LOGISTICS'::VARCHAR AS driver_name, '07'::VARCHAR AS dre_line_id,
        'PERCENTAGE'::VARCHAR AS comparison_basis,
        (SUM(delivery.freight_cost_total) / NULLIF(MAX(commercial.gross_revenue), 0))::NUMERIC(24,8) AS actual_value,
        MAX(assumption.planned_freight_cost_pct)::NUMERIC(24,8) AS budget_value
    FROM branch_commercial commercial
    LEFT JOIN staging.stg_deliveries delivery
      ON date_trunc('month', delivery.shipment_date)::DATE = commercial.competence_month
     AND delivery.branch_id = commercial.branch_id
    LEFT JOIN assumption
      ON assumption.competence_month = commercial.competence_month
     AND assumption.branch_id = commercial.branch_id
    GROUP BY commercial.competence_month, commercial.company_id, commercial.branch_id,
             assumption.budget_version_id
), financial_driver AS (
    SELECT
        COALESCE(actual.competence_month, budget.competence_month) AS competence_month,
        COALESCE(actual.company_id, budget.company_id) AS company_id,
        COALESCE(actual.branch_id, budget.branch_id) AS branch_id,
        NULL::BIGINT AS category_id,
        budget.budget_version_id,
        CASE COALESCE(actual.dre_line_id, budget.dre_line_id)
            WHEN '04' THEN 'CMV'
            WHEN '06' THEN 'OPEX'
            WHEN '08' THEN 'OPEX'
            WHEN '09' THEN 'OPEX'
            WHEN '11' THEN 'FINANCIAL'
        END::VARCHAR AS driver_name,
        COALESCE(actual.dre_line_id, budget.dre_line_id) AS dre_line_id,
        'CURRENCY'::VARCHAR AS comparison_basis,
        SUM(actual.actual_amount)::NUMERIC(24,8) AS actual_value,
        SUM(budget.budget_amount)::NUMERIC(24,8) AS budget_value
    FROM intermediate.int_dre_actual actual
    FULL OUTER JOIN intermediate.int_dre_budget budget
      ON budget.competence_month = actual.competence_month
     AND budget.company_id = actual.company_id
     AND budget.branch_id IS NOT DISTINCT FROM actual.branch_id
     AND budget.cost_center_id IS NOT DISTINCT FROM actual.cost_center_id
     AND budget.account_code = actual.account_code
     AND budget.dre_line_id = actual.dre_line_id
    WHERE COALESCE(actual.dre_line_id, budget.dre_line_id) IN ('04', '06', '08', '09', '11')
    GROUP BY COALESCE(actual.competence_month, budget.competence_month),
             COALESCE(actual.company_id, budget.company_id),
             COALESCE(actual.branch_id, budget.branch_id), budget.budget_version_id,
             COALESCE(actual.dre_line_id, budget.dre_line_id)
), combined AS (
    SELECT * FROM volume_price_discount
    UNION ALL SELECT * FROM mix
    UNION ALL SELECT * FROM logistics
    UNION ALL SELECT * FROM financial_driver
)
SELECT
    md5(concat_ws('|', competence_month, company_id, COALESCE(branch_id, 0),
        COALESCE(category_id, 0), COALESCE(budget_version_id, 0), driver_name, dre_line_id)) AS driver_record_id,
    competence_month,
    company_id,
    branch_id,
    category_id,
    budget_version_id,
    driver_name,
    dre_line_id,
    comparison_basis,
    actual_value,
    budget_value,
    (COALESCE(actual_value, 0) - COALESCE(budget_value, 0))::NUMERIC(24,8) AS variance_value,
    CASE
        WHEN budget_value IS NULL OR budget_value = 0 THEN NULL
        ELSE ((actual_value - budget_value) / ABS(budget_value))::NUMERIC(24,8)
    END AS variance_pct,
    CASE
        WHEN actual_value IS NULL OR budget_value IS NULL THEN 'NOT_COMPARABLE'
        WHEN driver_name IN ('CMV', 'OPEX', 'LOGISTICS', 'DISCOUNT') AND actual_value >= budget_value THEN 'UNFAVORABLE'
        WHEN driver_name IN ('CMV', 'OPEX', 'LOGISTICS', 'DISCOUNT') THEN 'FAVORABLE'
        WHEN actual_value >= budget_value THEN 'FAVORABLE'
        ELSE 'UNFAVORABLE'
    END::VARCHAR(30) AS favorability
FROM combined
WHERE driver_name IS NOT NULL;

CREATE UNIQUE INDEX ux_int_performance_drivers_record
    ON intermediate.int_performance_drivers (driver_record_id);
CREATE INDEX ix_int_performance_drivers_reporting
    ON intermediate.int_performance_drivers (competence_month, driver_name, branch_id);

COMMENT ON MATERIALIZED VIEW intermediate.int_performance_drivers IS
    'Drivers em formato longo para explicar Budget versus Actual: volume, preco, desconto, mix, CMV, logistica, OPEX e financeiro.';
""".strip() + "\n"
