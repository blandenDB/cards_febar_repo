"""Apply src/serve/02_postgres_setup.sql to Lakebase, optionally grant the app's role, and verify
row-level access. Runs as the job owner; the OAuth credential is generated in memory and never
printed. Verification uses a temporary Postgres role with exactly the app's grants, so the checks
show what a reviewer session (and someone outside the roster) can see. Prints a JSON summary.
"""
import argparse
import json
import uuid

import psycopg
from psycopg import sql
from databricks.sdk import WorkspaceClient

APP_GRANTS = """
GRANT USAGE ON SCHEMA app TO {role};
GRANT SELECT ON app.my_regions, app.targets, app.selection_mix, app.city_summary, app.cohort_growth, app.latest_reviews TO {role};
GRANT SELECT, INSERT ON app.target_reviews TO {role};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="projects/cards-lakebase/branches/production/endpoints/primary")
    ap.add_argument("--database", default="cards")
    ap.add_argument("--sql-file", required=True)
    ap.add_argument("--app-role", default="")
    a = ap.parse_args()
    w = WorkspaceClient()
    me = w.current_user.me().user_name
    ep = w.postgres.get_endpoint(name=a.endpoint)
    cred = w.postgres.generate_database_credential(endpoint=a.endpoint)
    summary = {"task": "postgres_setup", "status": "ok"}
    with psycopg.connect(host=ep.status.hosts.host, dbname=a.database, user=me, password=cred.token,
                         sslmode="require", autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(open(a.sql_file).read())
        if a.app_role:
            cur.execute(APP_GRANTS.format(role=sql.Identifier(a.app_role).as_string(conn)))
            summary["app_role_granted"] = True
        role = f"cards_rls_check_{uuid.uuid4().hex[:8]}"
        cur.execute(f"CREATE ROLE {role} NOLOGIN")
        cur.execute(f"GRANT {role} TO CURRENT_USER")
        cur.execute(APP_GRANTS.format(role=role))
        try:
            cur.execute("SELECT count(*), string_agg(DISTINCT campaign_region, ',' ORDER BY campaign_region) FROM cards.pg_target_list")
            n, regs = cur.fetchone()
            checks = {"synced_targets_total": n, "synced_regions": regs}
            cur.execute(f"SET ROLE {role}")
            for label, who in [("roster_reviewer", me), ("not_in_roster", "someone.else@example.com"), ("no_identity_set", "")]:
                cur.execute("BEGIN")
                cur.execute("SELECT set_config('app.reviewer', %s, true)", (who,))
                cur.execute("SELECT count(*), string_agg(DISTINCT campaign_region, ',' ORDER BY campaign_region) FROM app.targets")
                nt, rg = cur.fetchone()
                cur.execute("SELECT count(*) FROM app.city_summary")
                ncs = cur.fetchone()[0]
                checks[label] = {"targets": nt, "regions": rg, "city_summary_rows": ncs}
                cur.execute("ROLLBACK")
            try:
                cur.execute("SELECT 1 FROM cards.pg_target_list LIMIT 1")
                checks["synced_table_direct_access"] = "ALLOWED (unexpected)"
            except psycopg.errors.InsufficientPrivilege:
                checks["synced_table_direct_access"] = "denied"
            cur.execute("BEGIN")
            cur.execute("SELECT set_config('app.reviewer', %s, true)", (me,))
            cur.execute("SELECT target_id, campaign_region, card_product, offer_code FROM app.targets LIMIT 1")
            t = cur.fetchone()
            cur.execute("INSERT INTO app.target_reviews (target_id, campaign_region, card_product, offer_code, decision, reason) "
                        "VALUES (%s, %s, %s, %s, 'accept', 'rls check (rolled back)')", t)
            checks["review_insert_own_region"] = "allowed"
            cur.execute("ROLLBACK")
            cur.execute("BEGIN")
            cur.execute("SELECT set_config('app.reviewer', %s, true)", (me,))
            try:
                cur.execute("INSERT INTO app.target_reviews (target_id, campaign_region, card_product, offer_code, decision) "
                            "VALUES ('x-CB_ALL3', 'Coast', 'Cashback', 'CB_ALL3', 'accept')")
                checks["review_insert_other_region"] = "ALLOWED (unexpected)"
            except psycopg.errors.InsufficientPrivilege:
                checks["review_insert_other_region"] = "rejected by row-level security"
            cur.execute("ROLLBACK")
        finally:
            cur.execute("RESET ROLE")
            cur.execute(f"REASSIGN OWNED BY {role} TO CURRENT_USER")
            cur.execute(f"DROP OWNED BY {role}")
            cur.execute(f"DROP ROLE {role}")
    summary["checks"] = checks
    print(json.dumps(summary).replace(me, "<owner>"))


if __name__ == "__main__":
    main()
