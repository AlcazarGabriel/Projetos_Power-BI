# 📊 Portfólio de Business Intelligence | Gabriel Alcazar

Este repositório reúne meus projetos de **Business Intelligence, Power BI e Análise de Dados**, organizados em ordem cronológica para mostrar minha evolução técnica, analítica e profissional ao longo do tempo.

Os projetos mais antigos foram preservados em sua essência original. A intenção não é modernizar trabalhos anteriores para que pareçam atuais, mas permitir que a evolução entre diferentes etapas da minha trajetória fique visível.

> **Projeto mais recente:** [Pagamentos Analytics](./pagamentos-analytics/) — 07/08/2026

---

## 🧭 Sobre este portfólio

Este portfólio começou como um espaço para praticar Power BI e visualização de dados e, ao longo do tempo, passou a incorporar conceitos de **DAX, modelagem, bancos de dados, Python, SQL, ETL/ELT, Data Quality, conciliação e análise orientada ao negócio**.

A evolução dos projetos acompanha também minha evolução profissional.

Em 2025, passei a direcionar cada vez mais meu foco para a área de dados e, em **agosto de 2025**, essa transição foi oficialmente consolidada no ambiente profissional. A partir desse período, boa parte do aprendizado que antes acontecia apenas em projetos pessoais passou a ocorrer também em demandas reais de trabalho.

Esse contato com problemas reais de negócio, usuários, qualidade de dados e desenvolvimento de soluções analíticas influenciou diretamente a maturidade dos projetos seguintes.

---

## 📈 Evolução técnica

```text
2024
Power BI
   ↓
Exploração de dados e visualização
   ↓
DAX + inteligência de tempo
   ↓
2025
MySQL + modelagem fato/dimensão
   ↓
DAX mais estruturado + parâmetros + UX
   ↓
PostgreSQL + Python
   ↓
Arquitetura de dados + análise executiva + visão de negócio
   ↓
2026
ETL/ELT + SQL
   ↓
Data Quality + conciliação + análise operacional
   ↓
Pagamentos Analytics
```

---

## 🗓️ Linha do tempo dos projetos

| # | Projeto | Data | Principal evolução |
|---|---|---|---|
| 01 | [Evolução dos Preços de Combustíveis no Brasil](./projeto-posto/) | 07/08/2024 | Primeiro projeto em Power BI: exploração de dados, filtros, mapa e análise temporal |
| 02 | [Carga Tributária Brasileira](./carga-tributaria-Brasil/) | 11/09/2024 | DAX, inteligência de tempo, indicadores estatísticos, bookmarks e múltiplas páginas |
| 03 | [Dashboard Comercial - Vendas Apple](./Vendas_Apple/) | 24/03/2025 | MySQL, modelagem fato/dimensão, field parameters, tooltips, textos dinâmicos e UX |
| 04 | [Dashboard Executivo de Vendas](./Vendas-Esportiva/) | 31/12/2025 | PostgreSQL, Python, visão executiva, Pareto, matriz de rentabilidade, produtividade e storytelling |
| 05 | [Pagamentos Analytics](./pagamentos-analytics/) | 07/08/2026 | Projeto mais recente: BI mais estruturado, Data Quality, conciliação e análise operacional |

---

## 🚀 Evolução entre os projetos

### 01. Evolução dos Preços de Combustíveis no Brasil

**Meu primeiro projeto em Power BI.**

O objetivo foi explorar uma grande base pública de preços de combustíveis no Brasil e transformar os dados em uma análise histórica e geográfica.

Principais pontos praticados:

- importação e tratamento de arquivos;
- análise temporal;
- filtros e segmentações;
- visualização geográfica;
- exploração de uma base com mais de 23 milhões de registros;
- construção do primeiro dashboard interativo.

📂 [Acessar projeto](./projeto-posto/)

---

### 02. Carga Tributária Brasileira

No segundo projeto, a análise passou a utilizar uma camada maior de cálculos e comparações temporais.

Principais avanços:

- criação de medidas DAX;
- `DATEADD` e `PREVIOUSYEAR`;
- variação percentual anual;
- CAGR;
- desvio padrão;
- média ponderada;
- bookmarks;
- navegação entre páginas;
- diferentes perspectivas sobre o mesmo conjunto de dados.

📂 [Acessar projeto](./carga-tributaria-Brasil/)

---

### 03. Dashboard Comercial - Vendas Apple

O terceiro projeto marcou uma mudança para um cenário mais próximo de um dashboard comercial.

A fonte de dados deixou de ser composta apenas por arquivos estáticos e passou a utilizar um **banco MySQL**, com tabelas fato e dimensão e uma estrutura mais organizada para análise.

Principais avanços:

- conexão do Power BI ao MySQL;
- modelagem com fatos e dimensões;
- tabela calendário;
- DAX mais estruturado;
- field parameters;
- comparação com ano anterior;
- rankings e Top N;
- textos dinâmicos;
- tooltips personalizados;
- árvore de decomposição;
- bookmarks;
- navegação estruturada entre páginas;
- análise de vendas, produtos e devoluções.

📂 [Acessar projeto](./Vendas_Apple/)

---

### 04. Dashboard Executivo de Vendas

Este projeto representou um dos maiores saltos de maturidade do portfólio até aquele momento.

O desenvolvimento passou a considerar a solução de BI de forma mais ampla: **dados, banco, regras de negócio, usuário final, análise e tomada de decisão**.

A pergunta que passou a orientar o desenvolvimento foi:

> **Quem é o usuário deste relatório?**

A visão principal foi construída pensando em consumo executivo, priorizando poucos filtros, KPIs claros, leitura rápida e informações que ajudassem na tomada de decisão.

Principais avanços:

- PostgreSQL como camada de dados;
- geração e carga de dados com Python;
- modelo fato/dimensão;
- tabela dedicada de medidas;
- inteligência de tempo;
- YoY;
- tratamento de períodos incompletos;
- Top N dinâmico;
- Curva ABC / Pareto;
- matriz de rentabilidade e risco;
- benchmark de produtividade;
- análise de vendedores e supervisores;
- regras de negócio incorporadas às medidas;
- textos executivos dinâmicos em DAX;
- layout planejado com foco em público executivo.

📂 [Acessar projeto](./Vendas-Esportiva/)

---

### 05. Pagamentos Analytics

**Projeto mais recente do portfólio.**

O Pagamentos Analytics representa atualmente a etapa mais recente da minha evolução com Power BI e análise de dados.

O projeto foi desenvolvido com foco em um cenário de **meios de pagamento**, reunindo perspectivas executivas, comerciais, operacionais e de qualidade de dados.

Principais áreas trabalhadas:

- visão executiva;
- análise de carteira;
- performance operacional;
- Data Quality;
- conciliação de dados;
- indicadores financeiros e transacionais;
- DAX;
- Power Query;
- modelagem;
- análise temporal;
- tooltips;
- SVG;
- Power BI Service;
- ETL/ELT;
- SQL;
- Python;
- tratamento e validação de dados;
- identificação de divergências, duplicidades e inconsistências.

A página de **Qualidade de Dados e Conciliação** foi desenvolvida justamente para aproximar o projeto de problemas encontrados em ambientes reais de dados, como divergências entre origem, banco e camada analítica.

📂 [Acessar projeto](./pagamentos-analytics/)

---

## 💼 2025: evolução também no ambiente profissional

A partir de 2025, os intervalos entre projetos pessoais ficaram maiores porque uma parte cada vez mais relevante da minha evolução passou a acontecer também no ambiente profissional.

Em **agosto de 2025**, minha atuação na área de dados foi oficialmente consolidada.

Nesse ambiente profissional, tive contato direto com etapas que não aparecem nos projetos deste portfólio por questões de confidencialidade: participei do desenvolvimento de um data warehouse, consumi APIs para integração de dados e desenvolvi um banco de dados MySQL com rotinas de inserção e atualização (insert/update) para alimentar dashboards em produção. Essa vivência complementa o aprendizado dos projetos pessoais documentados aqui, mesmo sem estar diretamente representada neles.

O contato com demandas reais trouxe uma nova perspectiva sobre temas como:

- entendimento de requisitos;
- regras de negócio;
- integração entre sistemas;
- tratamento e validação de dados;
- qualidade de dados;
- automação;
- consultas SQL;
- construção de indicadores;
- desenvolvimento para usuários reais;
- importância de entender quem irá consumir a informação.

Essa experiência aparece de forma mais clara nos projetos desenvolvidos a partir do final de 2025.

---

## 🧩 Evolução das tecnologias

| Etapa | Tecnologias e conceitos |
|---|---|
| Início | Power BI, Power Query, CSV, visualização de dados |
| Evolução analítica | DAX, inteligência de tempo, estatística, bookmarks |
| BI comercial | MySQL, fato/dimensão, parâmetros, tooltips, UX |
| Arquitetura e negócio | PostgreSQL, Python, SQL, modelagem, Pareto, análise executiva |
| Momento atual | ETL/ELT, Data Quality, conciliação, automação e BI mais estruturado |

### Stack presente ao longo do portfólio

`Power BI` • `DAX` • `Power Query` • `SQL` • `MySQL` • `PostgreSQL` • `Python` • `ETL/ELT` • `Data Quality` • `Modelagem de Dados` • `Business Intelligence`

---

## 📣 Compartilhando a evolução

Ao longo dessa trajetória, também passei a compartilhar partes do desenvolvimento dos projetos no **LinkedIn**.

As publicações não serviram apenas para apresentar dashboards finalizados. Muitas vezes documentaram decisões, dificuldades, técnicas utilizadas e aprendizados durante a construção.

Alguns dos temas compartilhados foram:

- criação e estruturação de bancos de dados;
- integração entre Python e banco;
- DAX e análise dinâmica;
- matriz de rentabilidade;
- Curva ABC / Pareto;
- análise de crescimento e queda YoY;
- construção de dashboards orientados ao público;
- análise de equipes e produtividade;
- Data Quality e conciliação.

Esse processo gerou comentários, feedbacks e discussões com outros profissionais da área de dados e passou a fazer parte da minha evolução profissional.

---

## 🧠 Por que manter os projetos antigos?

Os projetos mais antigos não foram refeitos utilizando meu conhecimento atual.

Essa foi uma decisão intencional.

Ao preservá-los em sua essência original, é possível observar mudanças reais em:

- modelagem;
- DAX;
- organização das medidas;
- qualidade visual;
- profundidade analítica;
- entendimento de negócio;
- arquitetura de dados;
- experiência do usuário;
- capacidade de transformar dados em informações acionáveis.

O objetivo deste repositório, portanto, não é apresentar apenas os projetos mais recentes, mas também registrar **o processo de evolução entre eles**.

---

## 📂 Estrutura do repositório

```text
Projetos_Power-BI/
│
├── README.md
│
├── projeto-posto/
│   └── README.md
│
├── carga-tributaria-Brasil/
│   └── README.md
│
├── Vendas_Apple/
│   └── README.md
│
├── Vendas-Esportiva/
│   └── README.md
│
└── pagamentos-analytics/
    └── README.md
```

Cada projeto possui sua própria documentação com informações sobre:

- contexto;
- fonte e estrutura dos dados;
- modelagem;
- indicadores;
- medidas;
- páginas do dashboard;
- técnicas utilizadas;
- aprendizados;
- possíveis evoluções futuras.

---

## 👤 Autor

**Gabriel Alcazar**

Analista de Dados com foco em **Business Intelligence, Power BI, SQL, Python, ETL/ELT e qualidade de dados**.

- LinkedIn: [linkedin.com/in/gabriel-alcazar-3329a91b4](https://www.linkedin.com/in/gabriel-alcazar-3329a91b4/)
- GitHub: [github.com/AlcazarGabriel](https://github.com/AlcazarGabriel)

---

> Este repositório continuará sendo atualizado conforme novos projetos forem desenvolvidos. A ordem cronológica será mantida para preservar a evolução do portfólio.
