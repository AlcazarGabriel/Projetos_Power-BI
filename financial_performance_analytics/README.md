# Financial Performance Analytics

> Pipeline end-to-end de dados financeiros em PostgreSQL, construído para transformar dados operacionais de ERP em uma camada analítica confiável para **DRE Gerencial, Budget vs Actual, análise de performance e drivers de resultado**.

![Status](https://img.shields.io/badge/Pipeline-RAW%20%E2%86%92%20STAGING%20%E2%86%92%20INTERMEDIATE%20%E2%86%92%20MARTS-0f766e)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Analytics-336791)
![Data Quality](https://img.shields.io/badge/Data%20Quality-PASS-16a34a)
![Power BI](https://img.shields.io/badge/Power%20BI-Pr%C3%B3xima%20etapa-F2C811)

<p align="center">
  <img src="docs/Arquitetura/tecnico/architecture_overview.png" alt="Arquitetura do Pipeline: ERP para RAW, STAGING, INTERMEDIATE, MARTS, Semantic Model e Power BI" width="900">
</p>

---

## Visão geral

O projeto simula o ambiente de dados de uma distribuidora B2B nacional fictícia, a **Nexa Distribuição**, com dados sintéticos gerados de forma determinística e coerente entre os módulos comercial, logístico, contábil e de planejamento.

O objetivo não é apenas construir um dashboard. A proposta é demonstrar o fluxo completo entre **origem, ingestão, qualidade, transformação, regras de negócio, modelagem dimensional e consumo analítico**.

A arquitetura implementada segue:

```text
ERP / CSVs
    ↓
RAW
    ↓
STAGING
    ↓
INTERMEDIATE
    ↓
MARTS
    ↓
Semantic Model
    ↓
Power BI
```

O pipeline financeiro e o modelo dimensional em PostgreSQL estão concluídos. A próxima etapa é a construção do modelo semântico, medidas DAX e dashboards no Power BI.

---

## Contexto de negócio

A Nexa Distribuição apresenta crescimento de receita e volume, porém parte desse crescimento não está se convertendo na mesma proporção em resultado operacional.

O cenário foi construído para permitir uma análise realista de performance financeira, combinando:

- faturamento e descontos comerciais;
- custo das mercadorias vendidas (CMV);
- custos e subsídios logísticos;
- despesas operacionais e estrutura organizacional;
- resultado financeiro;
- orçamento independente do realizado;
- lançamentos contábeis, reversões e ajustes;
- rateios gerenciais e conciliações entre módulos.

Os dados de **Actual abrangem jan/2024 a jul/2026**, enquanto o **Budget cobre 2024 a 2026**, permitindo análises históricas, YoY, YTD e Budget vs Actual.

---

## Pergunta central

> **A empresa está crescendo de maneira rentável e quais fatores explicam os desvios entre o resultado realizado e o planejado?**

### Perguntas que o projeto deverá responder

1. Como Receita Líquida, Lucro Bruto, Resultado Operacional e Margem Operacional estão evoluindo ao longo do tempo?
2. O crescimento de receita está sendo acompanhado pelo crescimento do resultado?
3. Qual é o desvio entre **Actual e Budget** e em quais linhas da DRE ele está concentrado?
4. Quais fatores explicam o gap de performance: **volume, preço, desconto, mix, CMV, logística, OPEX ou resultado financeiro**?
5. Quais filiais, clientes, produtos ou categorias mais contribuem positiva ou negativamente para o resultado?
6. O aumento do custo logístico está relacionado à expansão regional, distância, peso, transportadoras ou maior frequência de entregas?
7. A política de descontos está pressionando receita líquida e margem em segmentos específicos?
8. As despesas administrativas estão crescendo acima ou abaixo da receita?
9. O resultado apresentado na DRE pode ser rastreado até os eventos comerciais, logísticos e contábeis de origem?
10. Quais poucos drivers concentram a maior parte do desvio desfavorável em relação ao Budget?

---

## Arquitetura do pipeline

### Papel de cada camada

| Camada | Responsabilidade |
|---|---|
| **RAW** | Preservar os dados da origem, histórico dos eventos e metadados de ingestão. |
| **STAGING** | Tipagem, padronização e validações estruturais sem aplicar regra de negócio. |
| **INTERMEDIATE** | Aplicar regras gerenciais: DRE, sinais, rateios, conciliações, Actual vs Budget e drivers. |
| **MARTS** | Entregar fatos e dimensões conformadas e otimizadas para análise. |
| **CONTROL / QUALITY** | Registrar execução, idempotência, testes, reconciliações e quality gates do pipeline. |

<p align="center">
  <img src="docs/Arquitetura/tecnico/layer_responsibilities.png" alt="Responsabilidade das Camadas" width="900">
</p>

---

## Fluxo de negócio

A arquitetura mantém rastreabilidade entre a operação e o resultado financeiro:

```text
Cliente
   ↓
Pedido
   ↓
Faturamento
   ├────────→ Entrega / Logística
   └────────→ Contabilização
                  ↓
             DRE Gerencial
```

<p align="center">
  <img src="docs/Arquitetura/tecnico/business_flow.png" alt="Fluxo de Negócio até a DRE" width="900">
</p>

A DRE não é construída por regras `CASE` espalhadas nas consultas. O relacionamento entre **conta contábil e linha gerencial** é controlado por tabelas de mapeamento com vigência temporal.

---

## DRE Gerencial e regras de negócio

A camada `intermediate` possui **14 linhas funcionais de DRE** e mapeamento integral das **83 contas de resultado** utilizadas pelo projeto.

Entre as principais regras implementadas estão:

- normalização do sinal contábil para valor gerencial;
- mapeamento Conta Contábil → Linha DRE;
- competência financeira;
- Actual e Budget conformados às mesmas dimensões;
- rateios por `REVENUE`, `HEADCOUNT` e `FIXED_PERCENTAGE`;
- conservação integral de valor antes e depois dos rateios;
- conciliação comercial × contabilidade;
- conciliação logística × contabilidade;
- drivers de volume, preço, desconto, mix, CMV, logística, OPEX e financeiro.

---

## Modelo dimensional MARTS

A camada de consumo possui **4 tabelas fato e 9 dimensões conformadas**, materializadas no PostgreSQL para reduzir o custo de processamento no consumo analítico.

<p align="center">
  <img src="docs/Arquitetura/tecnico/marts_dimensional_model.png" alt="Modelo Dimensional MARTS" width="900">
</p>

### Tabelas fato

| Tabela | Grão | Principal finalidade |
|---|---|---|
| `marts.fct_financial_entries` | lançamento financeiro/gerencial | Actual, DRE e análise contábil |
| `marts.fct_budget` | mês × conta × dimensões | Budget e variações |
| `marts.fct_sales` | item de nota fiscal | receita, preço, desconto, mix e volume |
| `marts.fct_deliveries` | entrega | frete, distância, peso, SLA e subsídio |

### Dimensões

`dim_date` · `dim_branch` · `dim_account` · `dim_dre` · `dim_cost_center` · `dim_customer` · `dim_product` · `dim_carrier` · `dim_sales_representative`

Membros técnicos `UNKNOWN` foram implementados para preservar integridade referencial e evitar chaves nulas nas fatos.

<details>
<summary><strong>ERD completo por camada</strong> (todas as colunas, exportado do DBeaver)</summary>
<br>

| Camada | ERD |
|---|---|
| RAW | [raw.png](docs/Arquitetura/tecnico/raw.png) |
| STAGING | [staging.png](docs/Arquitetura/tecnico/staging.png) |
| INTERMEDIATE | [intermediate.png](docs/Arquitetura/tecnico/intermediate.png) |
| MARTS | [marts.png](docs/Arquitetura/tecnico/marts.png) |
| CONTROL | [control.png](docs/Arquitetura/tecnico/control.png) |

Diagramas de referência com todas as colunas, tipos, PKs e FKs, úteis para consulta técnica detalhada. As versões acima (`marts_dimensional_model` etc.) são a leitura recomendada para entender o modelo; estas são o detalhe completo por trás delas.

</details>

---

## Volumetria

### Ingestão RAW

- **359 arquivos** processados;
- **3.749.884 registros** inseridos;
- **0 registros rejeitados**;
- reexecução validada sem duplicação;
- controle por hash SHA-256 e metadados de ingestão.

### MARTS

| Fato | Registros |
|---|---:|
| `fct_financial_entries` | 1.389.672 |
| `fct_budget` | 8.676 |
| `fct_sales` | 615.602 |
| `fct_deliveries` | 256.857 |

---

## Data Quality, auditoria e idempotência

Qualidade de dados é tratada como parte do pipeline e não como uma validação manual posterior.

<p align="center">
  <img src="docs/Arquitetura/tecnico/data_quality_governance.png" alt="Data Quality e Governança" width="900">
</p>

### Resultado das validações

| Camada | Resultado |
|---|---:|
| **RAW** | PASS |
| **STAGING** | **251 / 251 PASS** |
| **INTERMEDIATE** | **18 / 18 PASS** |
| **MARTS** | **33 / 33 PASS** |

Também foram validados:

- balanço entre débito e crédito;
- integridade entre headers e linhas contábeis;
- PKs, FKs e relacionamentos;
- ausência de registros órfãos nas MARTS;
- reconciliações financeiras, comerciais e logísticas;
- Budget reconciliado;
- conservação de valor dos rateios com diferença consolidada igual a zero;
- idempotência em reaplicações do pipeline;
- rastreabilidade das execuções e quality runs.

---

## Stack utilizada

- **PostgreSQL**: armazenamento, transformação e MARTS;
- **Python**: geração/ingestão dos dados e automações do pipeline;
- **SQL**: modelagem, transformação, regras gerenciais e validações;
- **Docker**: execução local reproduzível do ambiente;
- **DBeaver**: administração, consultas e inspeção dos modelos;
- **Git / GitHub**: versionamento e documentação;
- **Power BI**: modelo semântico, DAX e visualização na próxima etapa.

---

## Estrutura do repositório

```text
database/
├── fpa_raw/                  ingestão, schemas e validações da RAW
├── fpa_staging/              views tipadas e padronizadas
├── fpa_intermediate/         DRE, regras, reconciliações, rateios e drivers
├── fpa_marts/                fatos, dimensões e materialização analítica
└── README.md                 execução local e detalhes técnicos

docs/
├── guias/                    dossiê e documentação física do banco
└── Arquitetura/
    ├── tecnico/              diagramas completos para documentação/GitHub
    └── apresentacao/         diagramas 1080×1350 para LinkedIn/portfólio
```

> Consulte [`database/README.md`](database/README.md) para detalhes de implementação, comandos de execução e validação local.

---

## Diagramas disponíveis

| Diagrama | Objetivo |
|---|---|
| `architecture_overview` | Arquitetura completa da origem ao Power BI |
| `layer_responsibilities` | Responsabilidade de RAW, STAGING, INTERMEDIATE, MARTS e CONTROL |
| `business_flow` | Fluxo Cliente → Pedido → Faturamento → Logística/Contabilidade → DRE |
| `marts_dimensional_model` | Modelo dimensional com 4 fatos e 9 dimensões |
| `data_quality_governance` | Auditoria, testes, reconciliações e quality gate |

Cada diagrama acima tem uma versão técnica (horizontal, em `docs/Arquitetura/tecnico/`) e uma versão de apresentação (vertical 1080×1350, em `docs/Arquitetura/apresentacao/`), pronta para carrossel no LinkedIn e portfólio:

<p align="center">
  <a href="docs/Arquitetura/apresentacao/architecture_overview.png"><img src="docs/Arquitetura/apresentacao/architecture_overview.png" alt="Carrossel: Arquitetura do Pipeline" width="150"></a>
  <a href="docs/Arquitetura/apresentacao/layer_responsibilities.png"><img src="docs/Arquitetura/apresentacao/layer_responsibilities.png" alt="Carrossel: Papel de Cada Camada" width="150"></a>
  <a href="docs/Arquitetura/apresentacao/business_flow.png"><img src="docs/Arquitetura/apresentacao/business_flow.png" alt="Carrossel: Fluxo de Negócio até a DRE" width="150"></a>
  <a href="docs/Arquitetura/apresentacao/marts_dimensional_model.png"><img src="docs/Arquitetura/apresentacao/marts_dimensional_model.png" alt="Carrossel: Modelo Dimensional MARTS" width="150"></a>
  <a href="docs/Arquitetura/apresentacao/data_quality_governance.png"><img src="docs/Arquitetura/apresentacao/data_quality_governance.png" alt="Carrossel: Auditoria e Qualidade" width="150"></a>
</p>

---

## Dados

As bases utilizadas são **sintéticas** e foram construídas para preservar coerência entre os diferentes módulos do projeto. Os arquivos-fonte não são versionados no GitHub devido à volumetria.

A carga é executada localmente pelos scripts do projeto, preservando controles de arquivo, hash, quantidade de registros, status da execução e rastreabilidade.

---

## Próxima etapa: Power BI

Com a infraestrutura de dados concluída, o Power BI deverá consumir prioritariamente a camada `marts`.

O relatório será orientado a três perguntas analíticas principais:

1. **Executive Financial Performance**: como receita, resultado e margens estão evoluindo?
2. **DRE Gerencial**: onde estão os principais desvios entre Actual e Budget?
3. **Performance Drivers**: quais fatores explicam esses desvios e onde agir?

A proposta é manter um modelo semântico enxuto e dashboards com poucos indicadores, foco em análise e storytelling, deixando regras complexas de transformação no PostgreSQL.

---

## O que este projeto demonstra

Mais do que uma visualização financeira, este projeto busca demonstrar capacidade de trabalhar no ciclo completo do dado:

**ingestão → qualidade → SQL → modelagem → regras de negócio → reconciliação → modelo dimensional → analytics**.

O Power BI será a camada de consumo de uma arquitetura já validada, auditável e preparada para análise.
