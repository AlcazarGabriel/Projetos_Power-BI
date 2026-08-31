# Banco PostgreSQL - Financial Performance Analytics

Implementação completa do pipeline PostgreSQL aprovado no dossiê: RAW, STAGING, INTERMEDIATE e MARTS, com ingestão incremental auditável, regras gerenciais, modelo dimensional e testes automatizados.

## Escopo entregue

- Database único: `financial_performance_analytics`.
- Schemas: `raw`, `staging`, `intermediate`, `marts` e `control`.
- 29 tabelas RAW de origem (13 mestres, 5 planning e 11 Actual), além de `pipeline_runs` e `ingestion_control`.
- 29 views STAGING, uma para cada entidade RAW, preservando granularidade e lineage.
- Casts explícitos, limpeza de espaços e padronização de códigos/status sem regras gerenciais.
- Suíte de aceite STAGING com reconciliação de volumes, tipos, PKs, FKs, valores aceitos e regras estruturais.
- PKs, business keys, FKs, checks e índices prioritários do guia físico.
- Carga por arquivo com SHA-256, transação isolada, rastreabilidade e reprocessamento sem duplicidade.
- Views de qualidade para balanceamento contábil e reconciliação header x lines.
- Estrutura funcional da DRE com 14 linhas, incluindo grupos e subtotais calculados.
- `account_dre_mapping` configurável, temporal e protegido contra sobreposição de vigência.
- Razão gerencial materializado com `accounting_amount` preservado e `management_amount` normalizado.
- Actual e Budget conformados no mesmo grão: competência, empresa, filial, centro de custo, conta e linha DRE.
- Reconciliações Comercial x Contabilidade e Logística x Contabilidade com classificação explícita.
- Rateios por `REVENUE`, `HEADCOUNT` e `FIXED_PERCENTAGE`, com conservação de valor validada.
- Métricas de drivers com direção de favorabilidade explícita e valores financeiros interpretados pelo sinal gerencial.
- Bridge sequencial `VOLUME → PRICE → DISCOUNT → MIX → CMV → LOGISTICS → OPEX → RESIDUAL`, fechado contra o Resultado Operacional Actual menos Budget por competência, filial/Corporate e versão.
- `FINANCIAL` preservado para análise pré-tributos, sem participar do waterfall operacional.
- Auditoria persistida em `control.intermediate_quality_runs` e `control.intermediate_quality_results`.
- Onze dimensões conformadas: data, filial, driver, versão de Budget, conta, DRE, centro de custo, cliente, produto, transportadora e representante comercial.
- `dim_branch` mantém `0 = UNKNOWN` e o membro governado `-1 = CORPORATE` sem misturar os dois significados.
- `dim_budget_version` conforma versão, cenário, exercício, vigência e aprovação para filtrar `fct_budget`, `fct_delivery_budget` e `fct_performance_drivers` pelo mesmo `budget_version_id`.
- Seis fatos materializados para consumo: lançamentos financeiros, Budget, vendas, entregas, reconciliação e impactos de performance.
- `marts.fct_reconciliation` unifica eventos Comercial e Logística sem perder seus grãos de origem.
- `marts.fct_performance_drivers` publica nove drivers por mês, filial/Corporate e versão de Budget; residual acima de R$ 0,01 reprova a qualidade.
- Extensão operacional de Budget com `marts.fct_delivery_budget`, no grão versão x competência x filial.
- Medidas financeiras rateadas de forma aditiva, evitando duplicação de débito, crédito e valores gerenciais no Power BI.
- Vendas reconhecidas e canceladas separadas sem apagar os valores físicos recebidos da origem.
- Integridade estrela, cobertura de datas, grãos e reconciliações financeiras auditadas em `control.marts_quality_*`.

A transformação PostgreSQL está concluída. O próximo consumidor é o Semantic Model/Power BI, que deve usar prioritariamente o schema `marts`.

## Execução local com Docker

No PowerShell, a partir da raiz do projeto:

```powershell
Copy-Item database/.env.example database/.env
docker compose --env-file database/.env -f database/docker-compose.yml up -d
python -m venv .venv
.venv/Scripts/python -m pip install -r database/requirements.txt
$env:DATABASE_URL = "postgresql://fpa_admin:change_me_for_non_local_use@localhost:5433/financial_performance_analytics"
.venv/Scripts/python -m database.fpa_raw.load `
  Financial_Performance_Analytics_FINAL_Actual_2024_2026/financial_performance_final_actual `
  --bootstrap
.venv/Scripts/python -m database.fpa_raw.validate
.venv/Scripts/python -m database.fpa_staging.apply `
  Financial_Performance_Analytics_FINAL_Actual_2024_2026/financial_performance_final_actual
.venv/Scripts/python -m database.fpa_staging.validate
.venv/Scripts/python -m database.fpa_intermediate.apply
.venv/Scripts/python -m database.fpa_intermediate.validate
.venv/Scripts/python -m database.fpa_marts.apply
.venv/Scripts/python -m database.fpa_marts.validate
.venv/Scripts/python -m database.fpa_delivery_budget.apply `
  ../Financial_Performance_Analytics_Delivery_Budget_Extension_v1
.venv/Scripts/python -m database.fpa_delivery_budget.validate
```

Para uma carga piloto em banco vazio, use o primeiro período:

```powershell
.venv/Scripts/python -m database.fpa_raw.load `
  Financial_Performance_Analytics_FINAL_Actual_2024_2026/financial_performance_final_actual `
  --bootstrap --period 2024-01
```

Executar novamente o mesmo comando não duplica registros: arquivos já carregados com o mesmo hash são marcados como `skipped`.

`--period YYYY-MM` é uma carga incremental: períodos anteriores precisam estar no banco quando existirem referências cruzadas entre meses. Para a primeira implantação definitiva, omita `--period` e carregue todo o histórico.

## PostgreSQL já instalado

Também é possível usar uma instância PostgreSQL existente. Defina `DATABASE_URL` com um usuário autorizado a criar schemas e tabelas, depois execute os mesmos módulos `load` e `validate`.

## Decisões de modelagem

- Moeda usa `NUMERIC(18,2)`; percentuais usam `NUMERIC(12,6)`; datas de negócio usam `DATE`.
- IDs usam `BIGINT` para manter compatibilidade entre mestres e fatos.
- O `source_document_id` contábil permanece polimórfico, conforme a especificação.
- Cancelamentos, reemissões e estornos permanecem como eventos; a carga não apaga histórico de negócio.
- Particionamento não é aplicado nesta versão; o volume atual não o exige.
- STAGING é composta por views para evitar duplicar fisicamente 3,7 milhões de linhas.
- A unicidade física continua garantida pelas PKs da RAW; STAGING testa novamente o contrato antes da INTERMEDIATE.
- A INTERMEDIATE usa tabelas para configurações e materialized views para os modelos analíticos mais pesados.
- Contas de resultado não são classificadas por `CASE` no consumo: o mapeamento exato e temporal fica em `account_dre_mapping`.
- `management_amount` torna receitas positivas e custos, deduções e despesas negativas, mantendo débito, crédito e `accounting_amount` originais.
- Rateios substituem a visão corporativa por parcelas nas filiais-alvo e preservam o total por partida dentro de tolerância financeira de R$ 0,01.
- Alterações em mapeamentos ou regras exigem reaplicar `database.fpa_intermediate.apply` e executar a validação antes de liberar MARTS.
- MARTS usa chaves dimensionais não nulas; `0` referencia `UNKNOWN` e, somente em `dim_branch`, `-1` referencia `CORPORATE`.
- `fct_financial_entries` expande partidas rateadas, mas aplica o peso também aos valores contábeis para manter todas as medidas aditivas.
- `fct_sales` mantém medidas físicas de origem e medidas analíticas reconhecidas/canceladas em colunas separadas.
- O Power BI não deve usar RAW ou STAGING como fonte principal; auditoria e drill-through técnico permanecem disponíveis nessas camadas.
