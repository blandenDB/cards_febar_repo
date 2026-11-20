# Build plan

Everything lives in `c360_bank.cards` on the FEVM workspace (CLI profile `febar`). All workspace object names start with `cards_` so they do not collide with the CLV build. Data rules are in `DATA_DESIGN.md`; how results are judged is in `EVAL_PROTOCOL.md`.

## 1. Data flow

```
src/data/generate.py  +  data/public/*.csv (committed public price series)
        |  writes daily files (12:01 am drop, simulated)
        v
/Volumes/c360_bank/cards/raw/
   ecif_customers/  ecif_accounts/  ecif_balances/
   crm_campaigns/   crm_solicitations/  crm_customer_xref/  macro_prices/
        |  Auto Loader (Lakeflow SDP pipeline cards_pipeline)
        v
BRONZE  bronze_ecif_customers  bronze_ecif_accounts  bronze_ecif_balances
        bronze_crm_campaigns   bronze_crm_solicitations  bronze_crm_xref
        bronze_macro_prices
        |  expectations, dedupe, xref join, conform
        v
SILVER  silver_customers  silver_accounts  silver_balances_monthly
        silver_solicitations  silver_solicitations_quarantine  silver_macro_monthly
        |
        v
GOLD    gold_penetration_by_tier   gold_cohort_growth   gold_fairness_monitor
        gold_features (point-in-time, one row per solicitation)
        |                                   |
        |  UC: masks, row filter,           |  v_model_features (no protected attributes)
        |  tags, entitlements               v
        |                       src/ai: train (MLflow, UC model) -> score -> ai_query explanations
        |                                   |
        |                                   v
        |                       gold_target_scores (next campaign, per customer x offer)
        |                                   |
        |                       serving copy -> Lakebase synced table cards_target_list
        |                                   |
        v                                   v
Genie space cards_genie  <---------  Streamlit app cards_app (reads synced table,
(gold tables, target_reviews)         writes Postgres target_reviews)
        ^                                   |
        |  nightly copy back                |
        +---- c360_bank.cards.target_reviews <-+
```

Every stage reads the previous one: the app needs the synced table, which needs the scores, which need the governed feature view, which needs the pipeline. The review decisions flow back into Delta, Genie and the next day's run.

## 2. Stages

### Lakeflow (ingest and conform)
- **For the CDO:** replaces the manual pulls and checks before every vendor file; each morning's data is ready and trusted.
- **In:** raw files in `/Volumes/c360_bank/cards/raw/`. **Out:** bronze, silver and gold tables above.
- **Features:** Lakeflow Spark Declarative Pipelines in SQL (serverless), Auto Loader `read_files`, expectations (drop to quarantine, warn, fail), materialized views, pipeline event log.
- **Verify:** row counts per layer reconcile with the generator's counts; quarantine counts match the planted issues; duplicates from the resent file removed; event log expectation metrics. **Evidence:** `evidence/01_data_generation.txt`, `evidence/02_pipeline.txt`.

### Unity Catalog (governance and fair lending)
- **For the CDO:** each persona sees only what it should; protected attributes are kept out of targeting, and that is provable.
- **In:** silver and gold tables. **Out:** column masks (address and SSN tokens), row filter on target lists by campaign region via `cards_entitlements`, governed tags on personal and protected columns, `v_model_features`, `v_cdo_summary`, grants.
- **Features:** column masks, row filters, governed tags, views, grants, lineage.
- **Verify:** queries as the non-admin service principal show masked values, region-only rows and no protected columns in the model view. **Evidence:** `evidence/03_governance.txt`, `evidence/12_access_test.txt`.

### ML and GenAI (scores, reasons, cohorts)
- **For the CDO:** who will accept which offer, why in plain English, and which cohorts are growing above 10% a year.
- **In:** `gold_features` through `v_model_features`, `silver_macro_monthly`. **Out:** UC model `c360_bank.cards.cards_acceptance_model` (one per offer, five offers), `gold_target_scores` (score, rank, top reasons, explanation), eval tables.
- **Features:** MLflow tracking and UC model registry, scikit-learn gradient boosting, `ai_query` (Claude Haiku), MLflow GenAI judges (Claude Sonnet).
- **Verify:** `EVAL_PROTOCOL.md` checks (baseline, ablation, cohort growth, fairness monitor, judge). **Evidence:** `evidence/04_model.txt`, `evidence/05_explanations.txt`, `evidence/10_eval_protocol.txt`, `evidence/11_genai_judge.txt`, `evidence/13_fairness.txt`.

### Lakebase (serve and capture review)
- **For the CDO:** the campaign team works the daily target list and records accept or exclude before a campaign goes out; every decision is audited.
- **In:** owner-only serving copy of `gold_target_scores`. **Out:** synced table `cards_target_list` in Lakebase project `cards-lakebase`; Postgres table `target_reviews`; nightly copy to `c360_bank.cards.target_reviews`.
- **Features:** Lakebase Autoscaling project, synced table (triggered), Postgres security-barrier views with row-level security by campaign region.
- **Verify:** synced row count equals source; a review written in the app appears in Delta after the copy task. **Evidence:** `evidence/06_lakebase.txt`, `evidence/09_review_loop.txt`.

### Genie (ask in plain English)
- **For the CDO:** opens on new cards by city, then answers how penetration by tier and cohort is changing and how it tracks the cost of living.
- **In:** `gold_penetration_by_tier`, `gold_cohort_growth`, `silver_macro_monthly`, `gold_target_scores` (masked), `target_reviews`. **Out:** Genie space `cards_genie` with instructions, sample questions and 10 benchmark questions.
- **Features:** Genie space defined in the bundle, benchmark evaluation runs.
- **Verify:** benchmark run; bar 8 of 10. **Evidence:** `evidence/07_genie.txt`.

### App (campaign workspace)
- **For the CDO:** the monthly city report, live, with drill-down; the campaign team's review screen.
- **In:** Lakebase synced table and views; Genie for questions. **Out:** rows in `target_reviews`.
- **Features:** Databricks Apps (Streamlit) with a Lakebase resource and user identity.
- **Screens:** (1) New cards by city, drill to tier and cohort; (2) Growing cohorts; (3) Target review with accept or exclude; (4) Customer detail with reasons.
- **Verify:** Streamlit AppTest run plus a deployed health check and a review round trip. **Evidence:** `evidence/08_app.txt`.

## 3. Tables

| Layer | Table | Grain | One line |
|---|---|---|---|
| Bronze | bronze_ecif_customers | one row per customer per file | customer profile as landed, plus source file name and load time |
| Bronze | bronze_ecif_accounts | one row per account per file | checking, savings, money market accounts |
| Bronze | bronze_ecif_balances | one row per account per month per file | month-end balances |
| Bronze | bronze_crm_campaigns | one row per campaign offer per file | five offers with dates and card |
| Bronze | bronze_crm_solicitations | one row per solicitation per file | date sent, offer, response, crm customer key |
| Bronze | bronze_crm_xref | one row per crm key per file | crm key to ecif customer ID |
| Bronze | bronze_macro_prices | one row per series per month per area | public price data as downloaded |
| Silver | silver_customers | one row per customer | cleaned, city spelling fixed, Chapel Hill fill, market type, mass affluent flag, record origin |
| Silver | silver_accounts | one row per account | conformed accounts |
| Silver | silver_balances_monthly | one row per customer per month | balance by product and total |
| Silver | silver_solicitations | one row per solicitation | deduplicated, mapped to customer ID, qualification on the solicitation date |
| Silver | silver_solicitations_quarantine | one row per rejected record | rejected rows with the rule that failed |
| Silver | silver_macro_monthly | one row per area per month | price series aligned, with one-month publication lag |
| Gold | gold_features | one row per solicitation | point-in-time features and label |
| Gold | gold_penetration_by_tier | one row per month x city x tier x cohort | qualified targeted, accepted, penetration rate |
| Gold | gold_cohort_growth | one row per cohort x tier x period | growth versus a year earlier and the above-10% flag |
| Gold | gold_target_scores | one row per customer x offer for the next campaign | score, rank, top reasons, explanation |
| Gold | gold_fairness_monitor | one row per protected group x tier | selection share and adverse impact ratio |

Supporting: `cards_entitlements` (persona and region), `target_reviews` (copied back from Lakebase), eval and judge result tables.

## 4. Bundle layout

`databricks.yml` variables: `catalog` (c360_bank), `schema` (cards), `warehouse_id`, `llm_endpoint` (databricks-claude-haiku-5-5), `judge_endpoint` (databricks-claude-sonnet-5-5), `lakebase_project` (cards-lakebase), `access_test_sp`. One target, `dev`, on the FEVM workspace.

| File | Resources |
|---|---|
| resources/cards_schema.yml | schema `cards`, volume `raw`, MLflow experiment |
| resources/cards_pipeline.yml | pipeline `cards_pipeline` (serverless, SQL) |
| resources/cards_jobs.yml | job `cards_setup` (one-time data generation and governance setup), job `cards_daily` |
| resources/cards_lakebase.yml | Lakebase project and synced table |
| resources/cards_genie.yml | Genie space |
| resources/cards_app.yml | app `cards_app` |

## 5. Orchestration

Job `cards_daily`, scheduled daily at 12:30 am America/New_York (files land at 12:01 am):

1. `land_files`: drop the day's simulated ecif and crm files (idempotent, date-stamped names)
2. `pipeline`: refresh `cards_pipeline`
3. `governance`: apply masks, row filters, tags and grants (idempotent)
4. `train_and_score`: train (when due), score the next campaign, write `gold_target_scores`
5. `explanations`: `ai_query` explanations for the top targets; fails if more than 5% are empty
6. `evaluate`: eval protocol checks, fairness monitor, GenAI judge
7. `serve`: refresh the owner-only serving copy and the synced table
8. `reviews_back`: copy `target_reviews` from Lakebase to Delta

Every task prints or exits with a JSON run summary that `tools/collect_evidence.py` reads into `evidence/`. The schedule is paused after the evidence runs.

## 6. Time plan

| Stage | Hours |
|---|---|
| Synthetic data generator and public data download | 1.25 |
| Lakeflow pipeline | 1.25 |
| Unity Catalog governance and access test | 0.75 |
| ML model, scores, explanations, eval protocol, judge | 1.5 |
| Lakebase synced table, review table, copy back | 0.75 |
| Genie space and benchmarks | 0.5 |
| Streamlit app | 1.0 |
| Evidence collection and README | 0.5 |
| **Total** | **7.5** |
