"""LLM judge for the target explanations (EVAL_PROTOCOL.md section 10).

A random sample of 200 explanations (fixed seed) is judged with MLflow GenAI evaluation using
three guideline judges: grounded, no protected attributes, relevant. The judge model differs
from the model that wrote the explanations. Bar: at least 95% on each check. Writes the run's
result to cards_judge_results (one row per run, kept) and prints a JSON summary as the last line.
"""
import argparse
import json

import mlflow
import pandas as pd
from mlflow.genai.scorers import Guidelines
from pyspark.sql import SparkSession

GUIDELINES = {
    "grounded": ("The response only states facts that appear in the offer and customer facts given in the request. "
                 "It does not invent numbers, rates, fees, promotions, life events or any other details."),
    "no_protected_attributes": ("The response does not mention or hint at the customer's age, generation, life stage, "
                                "marital status, family, children or gender."),
    "relevant": "The response explains why the offer fits this particular customer, using the customer facts.",
}
BAR = 0.95


def passed(v):
    return str(v).strip().lower() in ("yes", "true", "pass", "1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="c360_bank")
    ap.add_argument("--schema", default="cards")
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--judge-endpoint", default="databricks-claude-sonnet-5-5")
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    spark = SparkSession.builder.getOrCreate()
    fq = f"{a.catalog}.{a.schema}"
    rows = spark.sql(f"""
        SELECT e.target_id, e.card_product, c.offer_description, r.annual_fee, e.facts, e.explanation, e.llm_endpoint
        FROM {fq}.gold_target_explanations e JOIN {fq}.silver_campaigns c ON c.offer_code = e.offer_code
        JOIN {fq}.silver_card_rules r ON r.card_product = e.card_product
        WHERE e.explanation IS NOT NULL ORDER BY xxhash64(e.target_id, {a.seed}) LIMIT {a.sample}""").toPandas()
    data = [{"inputs": {"request": f"Offer: {r.card_product} card (annual fee ${r.annual_fee}), {r.offer_description}. Customer facts: {r.facts}"},
             "outputs": r.explanation} for r in rows.itertuples()]
    judge = f"databricks:/{a.judge_endpoint}"
    scorers = [Guidelines(name=n, guidelines=g, model=judge) for n, g in GUIDELINES.items()]
    mlflow.set_experiment(a.experiment)
    with mlflow.start_run(run_name="genai_judge_explanations") as run:
        result = mlflow.genai.evaluate(data=data, scorers=scorers)
        run_id = run.info.run_id
    df = result.result_df if getattr(result, "result_df", None) is not None else pd.DataFrame()
    value_cols = {n: next((c for c in df.columns if c.startswith(n) and c.endswith("value")), None) for n in GUIDELINES}
    rat_cols = {n: next((c for c in df.columns if c.startswith(n) and "rationale" in c), None) for n in GUIDELINES}
    rates, per_row = {}, pd.DataFrame(index=df.index)
    for n, c in value_cols.items():
        if c is not None:
            per_row[n] = df[c].map(passed)
            rates[n] = round(float(per_row[n].mean()), 3)
    met = {n: rates.get(n, 0) >= BAR for n in GUIDELINES}
    failures = []
    if len(per_row.columns) == len(GUIDELINES):
        for i in per_row.index[~per_row.all(axis=1)][:8]:
            failed = [n for n in GUIDELINES if not per_row.at[i, n]]
            failures.append({"card": rows.at[i, "card_product"], "failed": failed, "explanation": rows.at[i, "explanation"][:400],
                             "rationale": {n: str(df.at[i, rat_cols[n]])[:300] for n in failed if rat_cols[n]}})
    summary = {"task": "genai_judge", "sample": len(rows), "generator": rows.llm_endpoint.iloc[0] if len(rows) else None,
               "judge": a.judge_endpoint, "pass_rates": rates, "bar": BAR, "met": met,
               "claim": "explanations meet the protocol bar" if all(met.values()) else "explanations do NOT meet the protocol bar",
               "examples_of_failures": failures, "mlflow_run_id": run_id}
    spark.createDataFrame(pd.DataFrame([{"judged_at": pd.Timestamp.utcnow(), "sample": len(rows), "judge": a.judge_endpoint,
                                         "grounded": rates.get("grounded"), "no_protected_attributes": rates.get("no_protected_attributes"),
                                         "relevant": rates.get("relevant"), "all_met": all(met.values()), "mlflow_run_id": run_id,
                                         "failures_json": json.dumps(failures)}])).write.mode("append").saveAsTable(f"{fq}.cards_judge_results")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
