"""Copy campaign team review decisions from Lakebase (app.target_reviews) into Unity Catalog so
analysts and Genie can see what was accepted or excluded. MERGE on review_id keeps reruns idempotent.
The target carries the campaign region row filter. Reviewer identities are replaced by a stable
pseudonymous key. Prints a JSON summary as the last line."""
import argparse
import hashlib
import json

import pandas as pd
import psycopg
from databricks.sdk import WorkspaceClient
from pyspark.sql import SparkSession


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="c360_bank")
    ap.add_argument("--schema", default="cards")
    ap.add_argument("--endpoint", default="projects/cards-lakebase/branches/production/endpoints/primary")
    ap.add_argument("--database", default="cards")
    a = ap.parse_args()
    fq = f"{a.catalog}.{a.schema}"
    w = WorkspaceClient()
    ep = w.postgres.get_endpoint(name=a.endpoint)
    cred = w.postgres.generate_database_credential(endpoint=a.endpoint)
    with psycopg.connect(host=ep.status.hosts.host, dbname=a.database, user=w.current_user.me().user_name,
                         password=cred.token, sslmode="require") as conn, conn.cursor() as cur:
        cur.execute("SELECT review_id::text, target_id, campaign_region, card_product, offer_code, decision, reason, "
                    "reviewer_principal, created_at FROM app.target_reviews")
        cols = [d.name for d in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)
    df["reviewer_key"] = df["reviewer_principal"].map(lambda s: "reviewer_" + hashlib.sha256(s.encode()).hexdigest()[:10])
    df = df.drop(columns=["reviewer_principal"])
    spark = SparkSession.builder.getOrCreate()
    spark.sql(f"""CREATE TABLE IF NOT EXISTS {fq}.target_reviews (
        review_id STRING COMMENT 'Review ID from the app', target_id STRING COMMENT 'Target (customer x offer) reviewed',
        campaign_region STRING COMMENT 'Campaign region (drives the row filter)', card_product STRING COMMENT 'Card tier',
        offer_code STRING COMMENT 'Offer', decision STRING COMMENT 'accept or exclude', reason STRING COMMENT 'Reviewer note',
        created_at TIMESTAMP COMMENT 'When the reviewer decided', reviewer_key STRING COMMENT 'Pseudonymous reviewer identifier')
      WITH ROW FILTER {fq}.cards_region_filter ON (campaign_region)
      COMMENT 'Campaign team accept or exclude decisions on next campaign targets, copied nightly from Lakebase'""")
    before = spark.table(f"{fq}.target_reviews").count()
    if len(df):
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True).dt.tz_localize(None)
        spark.createDataFrame(df).createOrReplaceTempView("rv")
        spark.sql(f"MERGE INTO {fq}.target_reviews t USING rv s ON t.review_id = s.review_id WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *")
    after = spark.table(f"{fq}.target_reviews").count()
    print(json.dumps({"task": "reviews_to_uc", "status": "ok", "lakebase_rows": int(len(df)), "uc_rows_before": before,
                      "uc_rows_after": after, "decisions": df["decision"].value_counts().to_dict() if len(df) else {}}))


if __name__ == "__main__":
    main()
