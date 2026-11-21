"""Acceptance model per offer, evaluated by EVAL_PROTOCOL.md, then scoring of the next campaign.

1. Reads v_model_features (no protected attributes). Split (protocol section 2): a fixed hash of
   customer_id puts 80% of customers in train; train = train customers x campaign months 1-18,
   test = other customers x months 19-24. Only qualified solicitations are used.
2. Per offer, trains a gradient-boosted classifier with and without public price features, and
   scores the vendor-style baseline (standardized income + credit score + 6-month balance).
3. Measures (sections 6, 7): top-20% acceptance per tier and pooled, versus the baseline;
   test ROC AUC with and without price features. Writes cards_eval_results.
4. Fairness monitor (section 9): selection into the top 20% by age group and marital status,
   from v_fairness_features; adverse impact ratio; writes gold_fairness_monitor.
5. Retrains each offer on all qualified history, registers one routing model in Unity Catalog
   (alias champion), scores v_next_campaign_features and writes gold_target_scores with the
   top three reasons per target (largest score drop when a feature is set to a typical value).
Prints a JSON run summary as the last line.
"""
import argparse
import json

import mlflow
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

OFFERS = ["SIL_BT6", "GLD_GROC5", "PLT_BT12", "PLT_TE5", "CB_ALL3"]
TIERS = ["Silver", "Gold", "Platinum", "Cashback"]
NUM = ["annual_income", "credit_score", "monthly_household_pmt", "residence_year", "years_at_residence", "tenure_years",
       "n_accounts", "has_savings", "has_money_market", "avg6_total_balance", "mass_affluent", "urban_suburban",
       "low_cost_market"]  # month of year removed before run 2 (EVAL_PROTOCOL.md change note)
MACRO = ["food_at_home_3m_change", "gasoline_3m_change", "cpi_all_items_yoy", "used_vehicles_yoy", "new_vehicles_yoy",
         "gasoline_usd_per_gallon", "house_price_yoy"]
CAT = ["city", "market_type", "own_rent_home", "employment_status", "preferred_channel", "campaign_region"]
PROTECTED = {"age", "age_at_solicitation", "generation", "marital_status", "gender", "date_of_birth"}
REASON_GROUPS = {
    "credit_score": ["credit_score"], "annual_income": ["annual_income"], "avg6_total_balance": ["avg6_total_balance"],
    "monthly_household_pmt": ["monthly_household_pmt"], "cost_of_living": ["food_at_home_3m_change", "gasoline_3m_change"],
    "house_prices": ["house_price_yoy"], "city": ["city", "campaign_region", "market_type"], "mass_affluent": ["mass_affluent"],
    "accounts": ["n_accounts", "has_savings", "has_money_market"], "home": ["own_rent_home", "years_at_residence", "residence_year"],
    "employment": ["employment_status"], "tenure": ["tenure_years"],
}


def to_float(df):
    """Spark DECIMAL columns arrive as Python Decimal objects; make them floats."""
    for c in df.columns:
        if df[c].dtype == object and len(df) and type(df[c].dropna().iloc[0]).__name__ == "Decimal":
            df[c] = df[c].astype(float)
    return df


def prep(df, cats=None):
    X = df.copy()
    X["month_of_year"] = pd.to_datetime(X["sent_month"]).dt.month
    for c in ["has_savings", "has_money_market", "mass_affluent", "urban_suburban", "low_cost_market"]:
        X[c] = X[c].astype(float)
    for c in NUM + MACRO:
        X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
    cats = cats or {c: sorted(X[c].dropna().astype(str).unique()) for c in CAT}
    for c in CAT:
        X[c] = pd.Categorical(X[c].astype(str), categories=cats[c]).codes.astype(float)
        X.loc[X[c] < 0, c] = np.nan
    return X, cats


def model(feats):
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40,
                                          l2_regularization=1.0, categorical_features=[f in CAT for f in feats], random_state=7)


def top_rate(df, score, frac=0.2):
    k = max(1, int(round(len(df) * frac)))
    return float(df.nlargest(k, score)["accepted"].mean()), k


class Router(mlflow.pyfunc.PythonModel):
    """One classifier per offer; routes each row by offer_code."""
    def __init__(self, models, feats, cats):
        self.models, self.feats, self.cats = models, feats, cats

    def predict(self, context, df):
        X, _ = prep(df, self.cats)
        out = np.zeros(len(X))
        for o, m in self.models.items():
            idx = (df["offer_code"] == o).values
            if idx.any():
                out[idx] = m.predict_proba(X.loc[idx, self.feats])[:, 1]
        return out


def fact(group, r):
    money = lambda v: f"${v:,.0f}"
    pct = lambda v: f"{v * 100:+.1f}%"
    return {
        "credit_score": f"credit score {int(r.credit_score)}",
        "annual_income": f"annual income {money(r.annual_income)}",
        "avg6_total_balance": f"6-month average deposit balance {money(r.avg6_total_balance)}",
        "monthly_household_pmt": f"monthly household payment {money(r.monthly_household_pmt)}",
        "cost_of_living": (f"prices have {'risen' if (r.food_at_home_3m_change + r.gasoline_3m_change) > 0 else 'fallen'} in the area: "
                           f"groceries {pct(r.food_at_home_3m_change)} and gasoline {pct(r.gasoline_3m_change)} over the last 3 months (South region figures; context, not a proven driver)"),
        "house_prices": (f"home prices in the area have {'risen' if r.house_price_yoy > 0 else 'fallen'} {pct(r.house_price_yoy)} over the last year "
                         f"(context, not a proven driver)"),
        "city": f"lives in {r.city} ({r.market_type.replace('_', ' ')} market)",
        "mass_affluent": "in the mass affluent income band for the local cost of living" if r.mass_affluent else "below the mass affluent band for the local cost of living",
        "accounts": f"{int(r.n_accounts)} deposit account(s) with the bank",
        "home": f"{'owns' if r.own_rent_home == 'own' else 'rents'} the home, {int(r.years_at_residence)} year(s) at the address",
        "employment": f"employment status {r.employment_status.replace('_', ' ')}",
        "tenure": f"customer for {r.tenure_years:.0f} year(s)",
    }[group]


def main(a):
    spark = SparkSession.builder.getOrCreate()
    fq = f"{a.catalog}.{a.schema}"
    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_experiment(a.experiment)
    df = to_float(spark.sql(f"SELECT * FROM {fq}.v_model_features WHERE qualified").toPandas())
    assert not PROTECTED & set(df.columns), "protected attribute in model input"
    df["accepted"] = df["accepted"].astype(int)
    h = pd.util.hash_pandas_object(df["customer_id"], index=False).values % 10
    df["is_train_customer"] = h < 8
    train = df[df.is_train_customer & (df.campaign_month <= 18)]
    test = df[~df.is_train_customer & (df.campaign_month >= 19)].copy()
    Xtr, cats = prep(train)
    Xte, _ = prep(test, cats)
    full_feats, base_feats = NUM + MACRO + CAT, NUM + CAT
    # Vendor-style rule baseline (section 5), standardized on training data
    for c in ["annual_income", "credit_score", "avg6_total_balance"]:
        mu, sd = train[c].astype(float).mean(), train[c].astype(float).std()
        test[f"z_{c}"] = (test[c].astype(float) - mu) / sd
    test["baseline"] = test[["z_annual_income", "z_credit_score", "z_avg6_total_balance"]].sum(axis=1)
    test["model"], test["model_no_macro"] = np.nan, np.nan
    auc = {}
    with mlflow.start_run(run_name="eval_protocol") as run:
        mlflow.log_params({"train_rows": len(train), "test_rows": len(test), "features": ",".join(full_feats),
                           "split": "hash(customer_id)%10<8 train; train months 1-18; test months 19-24"})
        for o in OFFERS:
            tr, te = train.offer_code == o, test.offer_code == o
            for name, feats in (("model", full_feats), ("model_no_macro", base_feats)):
                m = model(feats).fit(Xtr.loc[tr, feats], train.loc[tr, "accepted"])
                test.loc[te, name] = m.predict_proba(Xte.loc[te, feats])[:, 1]
            auc[o] = {k: round(float(roc_auc_score(test.loc[te, "accepted"], test.loc[te, k])), 4) for k in ("model", "model_no_macro", "baseline")}
            auc[o]["n_test"], auc[o]["accepts_test"] = int(te.sum()), int(test.loc[te, "accepted"].sum())
            mlflow.log_metrics({f"auc_{o}": auc[o]["model"], f"auc_no_macro_{o}": auc[o]["model_no_macro"]})
        # Top-20% acceptance by tier and pooled (section 6)
        rows, sel = [], []
        for t in TIERS:
            d = test[test.card_product == t]
            mr, k = top_rate(d, "model")
            br, _ = top_rate(d, "baseline")
            nr, _ = top_rate(d, "model_no_macro")
            rows.append({"tier": t, "n_test": len(d), "top20_n": k, "base_rate": round(float(d.accepted.mean()), 4),
                         "model_top20_rate": round(mr, 4), "baseline_top20_rate": round(br, 4), "model_no_macro_top20_rate": round(nr, 4),
                         "ratio_vs_baseline": round(mr / br, 3) if br else None})
            sel.append(d.nlargest(k, "model").solicitation_id)
            test.loc[d.nlargest(k, "baseline").index, "baseline_selected"] = True
        sel_ids = set(pd.concat(sel))
        test["selected"] = test.solicitation_id.isin(sel_ids)
        test["baseline_selected"] = test["baseline_selected"].fillna(False).astype(bool)
        pooled_model = float(test[test.selected].accepted.mean())
        pooled_base = float(test[test.baseline_selected].accepted.mean())
        pooled_ratio = pooled_model / pooled_base
        tiers_ok = sum(1 for r in rows if r["ratio_vs_baseline"] and r["ratio_vs_baseline"] >= 1.0)
        auc_with = float(roc_auc_score(test.accepted, test.model))
        auc_without = float(roc_auc_score(test.accepted, test.model_no_macro))
        claims = {
            "beats_vendor_style_list": bool(pooled_ratio >= 1.2 and tiers_ok >= 3),
            "cost_of_living_improves_targeting": bool(auc_with - auc_without >= 0.01),
        }
        mlflow.log_metrics({"pooled_top20_ratio": pooled_ratio, "auc_pooled": auc_with, "auc_pooled_no_macro": auc_without})
        ev = pd.DataFrame(rows)
        ev["pooled_model_top20_rate"], ev["pooled_baseline_top20_rate"], ev["pooled_ratio"] = round(pooled_model, 4), round(pooled_base, 4), round(pooled_ratio, 3)
        ev["tiers_at_or_above_baseline"], ev["auc_pooled"], ev["auc_pooled_no_macro"] = tiers_ok, round(auc_with, 4), round(auc_without, 4)
        ev["claim_beats_vendor_style_list"], ev["claim_cost_of_living"] = claims["beats_vendor_style_list"], claims["cost_of_living_improves_targeting"]
        ev["mlflow_run_id"] = run.info.run_id
        spark.createDataFrame(ev).createOrReplaceTempView("ev")
        spark.sql(f"CREATE OR REPLACE TABLE {fq}.cards_eval_results COMMENT 'EVAL_PROTOCOL.md results per tier (sections 6 and 7), latest run' AS SELECT current_timestamp() AS evaluated_at, * FROM ev")

        # Fairness monitor (section 9): analysts-only view joined on solicitation_id
        fair = spark.sql(f"SELECT solicitation_id, generation, marital_status FROM {fq}.v_fairness_features").toPandas()
        f = test[["solicitation_id", "card_product", "selected"]].merge(fair, on="solicitation_id")
        fr = []
        for attr in ("generation", "marital_status"):
            g = f.groupby(attr).agg(n=("selected", "size"), selected=("selected", "sum")).reset_index()
            g["selection_share"] = g.selected / g.n
            g["adverse_impact_ratio"] = g.selection_share / g.selection_share.max()
            for _, r in g.iterrows():
                fr.append({"attribute": attr, "group_value": r[attr], "n_test_qualified": int(r.n), "selected_top20": int(r.selected),
                           "selection_share": round(float(r.selection_share), 4), "adverse_impact_ratio": round(float(r.adverse_impact_ratio), 3),
                           "flag_below_0_8": bool(r.adverse_impact_ratio < 0.8)})
        spark.createDataFrame(pd.DataFrame(fr)).createOrReplaceTempView("fr")
        spark.sql(f"CREATE OR REPLACE TABLE {fq}.gold_fairness_monitor COMMENT 'Fairness monitor (EVAL_PROTOCOL.md section 9): share selected into the top 20% by protected group on the test set; adverse impact ratio; flag below 0.8. A monitor, not a pass bar.' AS SELECT current_timestamp() AS evaluated_at, * FROM fr")

    # Final models on all qualified history, registered as one routing model
    Xall, cats_all = prep(df)
    final = {o: model(full_feats).fit(Xall.loc[df.offer_code == o, full_feats], df.loc[df.offer_code == o, "accepted"]) for o in OFFERS}
    nxt = to_float(spark.sql(f"SELECT * FROM {fq}.v_next_campaign_features").toPandas())
    router = Router(final, full_feats, cats_all)
    sample = nxt.head(50)
    with mlflow.start_run(run_name="final_model") as frun:
        info = mlflow.pyfunc.log_model(name="model", python_model=router, input_example=sample,
                                       signature=infer_signature(sample, router.predict(None, sample)),
                                       registered_model_name=f"{fq}.cards_acceptance_model", pip_requirements=["scikit-learn", "pandas", "numpy"])
    from mlflow import MlflowClient
    client = MlflowClient(registry_uri="databricks-uc")
    version = info.registered_model_version
    client.set_registered_model_alias(f"{fq}.cards_acceptance_model", "champion", version)

    nxt["score"] = router.predict(None, nxt)
    Xn, _ = prep(nxt, cats_all)
    ref = {c: (Xall[c].median() if c not in CAT else Xall[c].mode().iloc[0]) for c in full_feats}
    drops = {}
    for gname, cols in REASON_GROUPS.items():
        Xp = Xn.copy()
        for c in cols:
            Xp[c] = ref[c]
        s = np.zeros(len(Xp))
        for o, m in final.items():
            idx = (nxt.offer_code == o).values
            if idx.any():
                s[idx] = m.predict_proba(Xp.loc[idx, full_feats])[:, 1]
        drops[gname] = nxt["score"].values - s
    D = pd.DataFrame(drops)
    order = np.argsort(-D.values, axis=1)[:, :3]
    names = np.array(list(REASON_GROUPS))
    for i in range(3):
        nxt[f"reason_{i + 1}_code"] = names[order[:, i]]
    for i in range(3):
        nxt[f"reason_{i + 1}"] = [fact(g, r) for g, r in zip(nxt[f"reason_{i + 1}_code"], nxt.itertuples())]
    for c in ["annual_income", "credit_score", "avg6_total_balance"]:
        mu, sd = df[c].astype(float).mean(), df[c].astype(float).std()
        nxt[f"z_{c}"] = (nxt[c].astype(float) - mu) / sd
    nxt["baseline_score"] = nxt[["z_annual_income", "z_credit_score", "z_avg6_total_balance"]].sum(axis=1)
    nxt["rank_in_tier"] = nxt.groupby("card_product")["score"].rank(ascending=False, method="first").astype(int)
    nxt["tier_size"] = nxt.groupby("card_product")["score"].transform("size")
    nxt["top20"] = nxt.rank_in_tier <= (nxt.tier_size * 0.2).round()
    out = nxt[["target_id", "customer_id", "offer_code", "card_product", "campaign_region", "city", "market_type", "mass_affluent",
               "annual_income", "credit_score", "avg6_total_balance", "monthly_household_pmt", "score", "baseline_score",
               "rank_in_tier", "tier_size", "top20", "reason_1_code", "reason_1", "reason_2_code", "reason_2", "reason_3_code", "reason_3"]].copy()
    out["avg6_total_balance"] = out.avg6_total_balance.astype(float)
    out["monthly_household_pmt"] = out.monthly_household_pmt.astype(float)
    out["model_version"] = str(version)
    spark.createDataFrame(out).createOrReplaceTempView("scores")
    spark.sql(f"""CREATE TABLE IF NOT EXISTS {fq}.gold_target_scores
        COMMENT 'Next campaign (November 2026) target list: one row per customer x qualified offer, acceptance score, vendor-style baseline score, rank within tier, top three reasons and a plain-English explanation (added by the explanations task). Row filter by campaign region.'
        AS SELECT *, CAST(NULL AS STRING) AS explanation, current_timestamp() AS scored_at FROM scores WHERE false""")
    spark.sql(f"INSERT OVERWRITE {fq}.gold_target_scores SELECT *, CAST(NULL AS STRING) AS explanation, current_timestamp() AS scored_at FROM scores")

    summary = {
        "task": "train_and_score", "train_rows": len(train), "test_rows": len(test), "auc_by_offer": auc,
        "top20_by_tier": rows, "pooled_model_top20_rate": round(pooled_model, 4), "pooled_baseline_top20_rate": round(pooled_base, 4),
        "pooled_ratio": round(pooled_ratio, 3), "tiers_at_or_above_baseline": tiers_ok,
        "auc_pooled": round(auc_with, 4), "auc_pooled_no_macro": round(auc_without, 4), "auc_gain_from_prices": round(auc_with - auc_without, 4),
        "claims": claims, "fairness_flags": [r for r in fr if r["flag_below_0_8"]],
        "registered_model": f"{fq}.cards_acceptance_model", "model_version": str(version), "eval_run_id": run.info.run_id,
        "targets_scored": len(out), "top20_targets": int(out.top20.sum()),
        "reason_1_mix": out.reason_1_code.value_counts().to_dict(), "features": full_feats,
    }
    print(json.dumps(summary, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="c360_bank")
    ap.add_argument("--schema", default="cards")
    ap.add_argument("--experiment", required=True)
    main(ap.parse_args())
