# Credit card adoption by tier: Arkterus Bank (FE Bar prototype)

[YOUR WORDS] One paragraph: the problem, who it is for and what changes. (Draft: Arkterus Bank pays an outside vendor to choose its credit card campaign targets and can only report new cards by city after the fact. This prototype finds, in-house and every morning, which customer cohorts are adopting which card tier, picks the next campaign's targets with reasons, and lets the campaign team review them before offers go out.)

All customer data is synthetic. Public price data comes from BLS (CPI, South region), EIA (Lower Atlantic gasoline) and FHFA (metro house price index). No real customers, names or contact details are used anywhere.

## The journey (one connected flow)

| Stage | What it does here | Evidence |
|---|---|---|
| Lakeflow | Lands the daily customer system (ecif) and campaign system (crm) files and the public price data; joins the two systems through a customer key cross-reference; quarantines bad rows, drops duplicates from a resent file, picks up a late file | `evidence/01_data_generation.txt`, `evidence/02_pipeline.txt` |
| Unity Catalog | Personas from an entitlement table (D&A analyst, campaign team by region, CDO totals only); masks on address and SSN tokens; region row filters; PII and protected-attribute tags; the model reads a view without age, generation, marital status or gender | `evidence/03_governance.txt`, `evidence/12_access_test.txt` |
| ML and GenAI | One acceptance model per offer (MLflow, Unity Catalog model `cards_acceptance_model`), judged against a vendor-style rule baseline; plain-English explanations with `ai_query`; an LLM judge; a fairness monitor | `evidence/04_model.txt`, `evidence/05_explanations.txt`, `evidence/10_eval_protocol.txt`, `evidence/11_genai_judge.txt`, `evidence/13_fairness.txt` |
| Lakebase | Serves the next campaign's target list and stores the campaign team's accept or exclude decisions (Postgres views and row-level security by region); decisions copied back to Unity Catalog nightly | `evidence/06_lakebase.txt`, `evidence/09_review_loop.txt` |
| Genie | CDO and analyst questions on new cards and penetration by city, tier and cohort, growing cohorts, price trends and review outcomes; 10 benchmark questions | `evidence/07_genie.txt` |
| App | Streamlit app `cards-campaigns`: new cards by city, growing cohorts, target review with an age-group fairness check, target detail | `evidence/08_app.txt`, `evidence/09_review_loop.txt` |

One job, `cards_daily`, runs all 12 tasks in order after the 12:01 am file drop (schedule 12:30 am America/New_York, paused outside evidence runs): `evidence/00_setup.txt`.

## Results (judged by `EVAL_PROTOCOL.md`, committed before any data or results)

| Question | Result | Verdict |
|---|---|---|
| Do in-house targets beat a vendor-style rule list? (bar 1.2x, 3 of 4 tiers) | 1.56x to 1.74x in all four runs | Met in every run |
| Does public cost-of-living data improve targeting? (bar +0.01 ROC AUC) | Runs 1 and 2: no (-0.001, -0.003); runs 3 and 4 (revised data): yes (+0.014, +0.014) | Inconclusive: met in 2 of 4 runs, within chance variation for the test size |
| Which cohorts grow above 10% a year in both training and test periods? | 5 cohorts in the final data, mostly mass affluent Millennials and Gen X in urban and suburban markets | Met |
| Are the explanations grounded, free of protected attributes and relevant? (bar 95% each) | Final: 99.5%, 100%, 100% (after documented fixes; every judge run kept) | Met |
| Fairness monitor (adverse impact ratio, flag below 0.8) | Boomers and Silent customers are selected far less often; the model never sees age but learns age-linked patterns | Flagged and shown on the review screen; not adjusted by age |

Every run and every change is kept: `evidence/*_run1..4.txt`, the dated change notes in `EVAL_PROTOCOL.md`, and `BUILD_LOG.md`.

## Data

How the synthetic dataset is built is in `DATA_DESIGN.md`: an authored synthetic customer profile (175,885 customers in North Carolina and South Carolina) plus 6,250 added and about 80 adjusted synthetic customers, all flagged in the data (`record_origin`), with the planted adoption patterns and data problems the pipeline must handle.

## How to run

Prerequisites: Databricks CLI, a workspace with Unity Catalog, serverless compute, Lakebase and Databricks Apps, and a CLI profile.

```
databricks bundle validate --profile <profile>
databricks bundle deploy --profile <profile>
databricks bundle run cards_setup --profile <profile>      # one time: generate the source files
databricks bundle run cards_pipeline --full-refresh-all --profile <profile>
databricks bundle run cards_daily --profile <profile>       # land files, govern, train, explain, judge, serve
databricks bundle run cards_app --profile <profile>
```

The generator reads an authored synthetic profile file from the `seed` volume (`seed/source/customer_profile.csv`) and the public price CSVs in `data/public/` (download script: `tools/download_public_data.py`). The access test (`tools/access_test.py`), app test (`tools/test_app.py`) and Genie evidence (`tools/genie_evidence.py`) run from a laptop with the CLI profile.

## Limits

[YOUR WORDS] What this prototype does not prove. (Draft: synthetic data with planted patterns, so the results show the platform can detect and act on such patterns, not that they exist in a real bank; customer profile attributes are a single snapshot; public price indexes are regional, so city differences come only from house prices; the test set is small (about 3,900 qualified offers), which is why the cost-of-living result is inconclusive; no credit decisioning, pricing or real campaign sending; no comparison with a real vendor's list.)

## Repository

`FEBAR_CONTEXT.md` (rules), `USE_CASE.md`, `BUILD_PLAN.md`, `EVAL_PROTOCOL.md`, `DATA_DESIGN.md`, `DECISIONS.md`, `BUILD_LOG.md`, `databricks.yml`, `resources/`, `src/` (data, pipeline, governance, ai, serve, genie, app), `tools/`, `evidence/`.
