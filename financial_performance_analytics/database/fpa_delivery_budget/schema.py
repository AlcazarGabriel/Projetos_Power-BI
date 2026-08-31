from __future__ import annotations


SOURCE_COLUMNS = (
    "delivery_budget_plan_id",
    "budget_version_id",
    "budget_version_code",
    "scenario",
    "fiscal_year",
    "fiscal_period",
    "period",
    "company_id",
    "branch_id",
    "branch_code",
    "planned_gross_product_revenue",
    "planned_price_index",
    "planned_volume_index",
    "planned_order_consolidation_index",
    "planned_avg_gross_value_per_delivery",
    "planned_deliveries",
    "planned_avg_distance_km",
    "planned_avg_weight_kg",
    "planned_avg_volume_m3",
    "planned_freight_cost",
    "planned_freight_charge",
    "planned_freight_cost_pct",
    "planned_freight_charge_pct",
    "planned_cost_per_delivery",
    "planned_charge_per_delivery",
    "planned_on_time_rate",
    "currency_code",
    "planning_method",
    "created_at",
)


RAW_DDL = r"""
SET client_encoding = 'UTF8';
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.erp_budget_delivery_plan (
    delivery_budget_plan_id BIGINT PRIMARY KEY,
    budget_version_id BIGINT NOT NULL REFERENCES raw.erp_budget_versions (budget_version_id),
    budget_version_code VARCHAR(50) NOT NULL,
    scenario VARCHAR(30) NOT NULL CHECK (scenario = 'BUDGET'),
    fiscal_year INTEGER NOT NULL CHECK (fiscal_year BETWEEN 2000 AND 2100),
    fiscal_period INTEGER NOT NULL CHECK (fiscal_period BETWEEN 1 AND 12),
    period CHAR(7) NOT NULL,
    company_id BIGINT NOT NULL REFERENCES raw.erp_companies (company_id),
    branch_id BIGINT NOT NULL REFERENCES raw.erp_branches (branch_id),
    branch_code VARCHAR(50) NOT NULL,
    planned_gross_product_revenue NUMERIC(18,2) NOT NULL CHECK (planned_gross_product_revenue >= 0),
    planned_price_index NUMERIC(12,6) NOT NULL CHECK (planned_price_index > 0),
    planned_volume_index NUMERIC(12,6) NOT NULL CHECK (planned_volume_index > 0),
    planned_order_consolidation_index NUMERIC(12,6) NOT NULL CHECK (planned_order_consolidation_index > 0),
    planned_avg_gross_value_per_delivery NUMERIC(18,4) NOT NULL CHECK (planned_avg_gross_value_per_delivery > 0),
    planned_deliveries INTEGER NOT NULL CHECK (planned_deliveries > 0),
    planned_avg_distance_km NUMERIC(18,4) NOT NULL CHECK (planned_avg_distance_km >= 0),
    planned_avg_weight_kg NUMERIC(18,4) NOT NULL CHECK (planned_avg_weight_kg >= 0),
    planned_avg_volume_m3 NUMERIC(18,4) NOT NULL CHECK (planned_avg_volume_m3 >= 0),
    planned_freight_cost NUMERIC(18,2) NOT NULL CHECK (planned_freight_cost >= 0),
    planned_freight_charge NUMERIC(18,2) NOT NULL CHECK (planned_freight_charge >= 0),
    planned_freight_cost_pct NUMERIC(12,6) NOT NULL CHECK (planned_freight_cost_pct BETWEEN 0 AND 1),
    planned_freight_charge_pct NUMERIC(12,6) NOT NULL CHECK (planned_freight_charge_pct BETWEEN 0 AND 1),
    planned_cost_per_delivery NUMERIC(18,4) NOT NULL CHECK (planned_cost_per_delivery >= 0),
    planned_charge_per_delivery NUMERIC(18,4) NOT NULL CHECK (planned_charge_per_delivery >= 0),
    planned_on_time_rate NUMERIC(12,6) NOT NULL CHECK (planned_on_time_rate BETWEEN 0 AND 1),
    currency_code CHAR(3) NOT NULL,
    planning_method VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    ingestion_id BIGINT NOT NULL REFERENCES raw.ingestion_control (ingestion_id),
    pipeline_run_id UUID NOT NULL REFERENCES raw.pipeline_runs (pipeline_run_id),
    source_file TEXT NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_erp_budget_delivery_plan_grain
        UNIQUE (budget_version_id, period, branch_id)
);

CREATE INDEX IF NOT EXISTS ix_erp_budget_delivery_plan_period
    ON raw.erp_budget_delivery_plan (period, branch_id);
CREATE INDEX IF NOT EXISTS ix_erp_budget_delivery_plan_version
    ON raw.erp_budget_delivery_plan (budget_version_id, fiscal_year, fiscal_period);
""".strip() + "\n"


LAYER_DDL = r"""
SET client_encoding = 'UTF8';
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE OR REPLACE VIEW staging.stg_budget_delivery_plan AS
SELECT
    delivery_budget_plan_id::BIGINT AS delivery_budget_plan_id,
    budget_version_id::BIGINT AS budget_version_id,
    UPPER(NULLIF(BTRIM(budget_version_code), ''))::VARCHAR(50) AS budget_version_code,
    UPPER(NULLIF(BTRIM(scenario), ''))::VARCHAR(30) AS scenario,
    fiscal_year::INTEGER AS fiscal_year,
    fiscal_period::INTEGER AS fiscal_period,
    period::CHAR(7) AS period,
    company_id::BIGINT AS company_id,
    branch_id::BIGINT AS branch_id,
    UPPER(NULLIF(BTRIM(branch_code), ''))::VARCHAR(50) AS branch_code,
    planned_gross_product_revenue::NUMERIC(18,2) AS planned_gross_product_revenue,
    planned_price_index::NUMERIC(12,6) AS planned_price_index,
    planned_volume_index::NUMERIC(12,6) AS planned_volume_index,
    planned_order_consolidation_index::NUMERIC(12,6) AS planned_order_consolidation_index,
    planned_avg_gross_value_per_delivery::NUMERIC(18,4) AS planned_avg_gross_value_per_delivery,
    planned_deliveries::INTEGER AS planned_deliveries,
    planned_avg_distance_km::NUMERIC(18,4) AS planned_avg_distance_km,
    planned_avg_weight_kg::NUMERIC(18,4) AS planned_avg_weight_kg,
    planned_avg_volume_m3::NUMERIC(18,4) AS planned_avg_volume_m3,
    planned_freight_cost::NUMERIC(18,2) AS planned_freight_cost,
    planned_freight_charge::NUMERIC(18,2) AS planned_freight_charge,
    planned_freight_cost_pct::NUMERIC(12,6) AS planned_freight_cost_pct,
    planned_freight_charge_pct::NUMERIC(12,6) AS planned_freight_charge_pct,
    planned_cost_per_delivery::NUMERIC(18,4) AS planned_cost_per_delivery,
    planned_charge_per_delivery::NUMERIC(18,4) AS planned_charge_per_delivery,
    planned_on_time_rate::NUMERIC(12,6) AS planned_on_time_rate,
    UPPER(NULLIF(BTRIM(currency_code), ''))::CHAR(3) AS currency_code,
    UPPER(NULLIF(BTRIM(planning_method), ''))::VARCHAR(100) AS planning_method,
    created_at::TIMESTAMP AS created_at,
    ingestion_id::BIGINT AS ingestion_id,
    pipeline_run_id::UUID AS pipeline_run_id,
    source_file::TEXT AS source_file,
    UPPER(NULLIF(BTRIM(source_system), ''))::VARCHAR(50) AS source_system,
    ingested_at::TIMESTAMPTZ AS ingested_at
FROM raw.erp_budget_delivery_plan;

COMMENT ON VIEW staging.stg_budget_delivery_plan IS
    'Budget operacional de entregas tipado e padronizado; grao versao x competencia x filial.';

DROP MATERIALIZED VIEW IF EXISTS marts.fct_delivery_budget;
DROP MATERIALIZED VIEW IF EXISTS intermediate.int_delivery_budget;

CREATE MATERIALIZED VIEW intermediate.int_delivery_budget AS
SELECT
    plan.delivery_budget_plan_id,
    plan.budget_version_id,
    plan.budget_version_code,
    plan.scenario,
    to_date(plan.period || '-01', 'YYYY-MM-DD') AS competence_month,
    plan.fiscal_year,
    plan.fiscal_period,
    plan.company_id,
    plan.branch_id,
    plan.branch_code,
    plan.planned_gross_product_revenue,
    plan.planned_price_index,
    plan.planned_volume_index,
    plan.planned_order_consolidation_index,
    plan.planned_avg_gross_value_per_delivery,
    plan.planned_deliveries,
    plan.planned_avg_distance_km,
    plan.planned_avg_weight_kg,
    plan.planned_avg_volume_m3,
    plan.planned_freight_cost,
    plan.planned_freight_charge,
    (plan.planned_freight_cost - plan.planned_freight_charge)::NUMERIC(18,2)
        AS planned_freight_subsidy,
    plan.planned_freight_cost_pct,
    plan.planned_freight_charge_pct,
    plan.planned_cost_per_delivery,
    plan.planned_charge_per_delivery,
    plan.planned_on_time_rate,
    plan.currency_code,
    plan.planning_method,
    plan.ingestion_id,
    plan.pipeline_run_id,
    plan.source_file,
    plan.source_system,
    plan.ingested_at
FROM staging.stg_budget_delivery_plan plan;

CREATE UNIQUE INDEX ux_int_delivery_budget_grain
    ON intermediate.int_delivery_budget (budget_version_id, competence_month, branch_id);
CREATE INDEX ix_int_delivery_budget_reporting
    ON intermediate.int_delivery_budget (competence_month, branch_id);

COMMENT ON MATERIALIZED VIEW intermediate.int_delivery_budget IS
    'Budget operacional de entregas conformado e enriquecido com subsidio planejado.';

CREATE MATERIALIZED VIEW marts.fct_delivery_budget AS
SELECT
    budget.delivery_budget_plan_id AS delivery_budget_key,
    budget.delivery_budget_plan_id,
    budget.budget_version_id,
    budget.budget_version_code,
    budget.scenario,
    to_char(budget.competence_month, 'YYYYMMDD')::INTEGER AS date_key,
    budget.fiscal_year,
    budget.fiscal_period,
    budget.company_id,
    budget.branch_id AS branch_key,
    budget.planned_gross_product_revenue,
    budget.planned_price_index,
    budget.planned_volume_index,
    budget.planned_order_consolidation_index,
    budget.planned_avg_gross_value_per_delivery,
    budget.planned_deliveries,
    budget.planned_avg_distance_km,
    budget.planned_avg_weight_kg,
    budget.planned_avg_volume_m3,
    budget.planned_freight_cost,
    budget.planned_freight_charge,
    budget.planned_freight_subsidy,
    budget.planned_freight_cost_pct,
    budget.planned_freight_charge_pct,
    budget.planned_cost_per_delivery,
    budget.planned_charge_per_delivery,
    budget.planned_on_time_rate,
    budget.currency_code,
    budget.planning_method,
    budget.pipeline_run_id,
    budget.ingestion_id,
    budget.source_file,
    budget.source_system
FROM intermediate.int_delivery_budget budget;

CREATE UNIQUE INDEX ux_fct_delivery_budget_key
    ON marts.fct_delivery_budget (delivery_budget_key);
CREATE UNIQUE INDEX ux_fct_delivery_budget_grain
    ON marts.fct_delivery_budget (budget_version_id, date_key, branch_key);
CREATE INDEX ix_fct_delivery_budget_analysis
    ON marts.fct_delivery_budget (date_key, branch_key);

COMMENT ON MATERIALIZED VIEW marts.fct_delivery_budget IS
    'Budget de entregas no grao versao x competencia x filial para consumo exclusivo do Power BI.';
""".strip() + "\n"

