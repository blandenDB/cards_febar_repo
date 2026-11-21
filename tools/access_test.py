"""Access test with a real non-admin identity (service principal cards-access-tester).

The data owner (CLI user) grants the principal read access to the shared objects and sets
its persona in cards_entitlements; the principal then runs the same queries as each persona
and with no entitlement. A short-lived OAuth secret is created for the principal, used only
in memory, and deleted at the end. Nothing secret is printed or stored.

Usage: .venv/bin/python tools/access_test.py --profile febar > evidence/12_access_test.txt
"""
import argparse
import datetime as dt
import re
import time

import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.iam import AccessControlRequest, PermissionLevel

FQ = "c360_bank.cards"
SP_NAME = "cards-access-tester"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@databricks\.com")
GRANTED = ["silver_customer_identifiers", "v_model_features", "v_fairness_features", "v_cdo_summary", "v_cohort_growth"]
OPTIONAL = ["gold_target_scores"]  # added once the ML stage exists

QUERIES = [
    ("who am I", "SELECT current_user() AS principal"),
    ("identifiers: rows, regions and sample (masks and region filter)", f"""SELECT
        (SELECT count(*) FROM {FQ}.silver_customer_identifiers) AS rows_visible,
        (SELECT concat_ws(',', array_sort(collect_set(campaign_region))) FROM {FQ}.silver_customer_identifiers) AS regions,
        (SELECT max(address_token) FROM {FQ}.silver_customer_identifiers) AS address_token_sample,
        (SELECT max(ssn_last4_token) FROM {FQ}.silver_customer_identifiers) AS ssn_token_sample"""),
    ("model view: rows, and whether any protected column exists", f"""SELECT (SELECT count(*) FROM {FQ}.v_model_features) AS rows_visible,
        (SELECT count(*) FROM {FQ.split('.')[0]}.information_schema.columns WHERE table_schema = 'cards' AND table_name = 'v_model_features'
           AND column_name IN ('age_at_solicitation', 'generation', 'marital_status', 'gender', 'date_of_birth', 'age')) AS protected_columns_in_model_view"""),
    ("fairness view rows (protected attributes, analysts only)", f"SELECT count(*) AS rows_visible FROM {FQ}.v_fairness_features"),
    ("CDO totals view", f"SELECT count(*) AS rows_visible, sum(new_cards) AS new_cards FROM {FQ}.v_cdo_summary"),
    ("CDO cohort growth view", f"SELECT count(*) AS cohorts_visible, count_if(growing_above_10pct) AS growing_cohorts FROM {FQ}.v_cohort_growth"),
    ("read gold_penetration_by_tier directly (not granted)", f"SELECT count(*) AS n FROM {FQ}.gold_penetration_by_tier"),
    ("target list rows by region", f"SELECT campaign_region, count(*) AS rows_visible FROM {FQ}.gold_target_scores GROUP BY 1 ORDER BY 1"),
    ("read gold_features directly (not granted)", f"SELECT count(*) AS n FROM {FQ}.gold_features"),
    ("read silver_customers directly (not granted)", f"SELECT count(*) AS n FROM {FQ}.silver_customers"),
    ("read the entitlement table (not granted)", f"SELECT count(*) AS n FROM {FQ}.cards_entitlements"),
    ("change own entitlement (not granted)", f"UPDATE {FQ}.cards_entitlements SET persona = 'data_owner' WHERE principal = current_user()"),
]


def run_sql(host, token, warehouse, sql):
    r = requests.post(f"{host}/api/2.0/sql/statements", headers={"Authorization": f"Bearer {token}"},
                      json={"warehouse_id": warehouse, "statement": sql, "wait_timeout": "50s"}, timeout=120)
    d = r.json()
    while d.get("status", {}).get("state") in ("PENDING", "RUNNING"):
        time.sleep(2)
        d = requests.get(f"{host}/api/2.0/sql/statements/{d['statement_id']}", headers={"Authorization": f"Bearer {token}"}, timeout=60).json()
    return d


def fmt(d):
    st = d.get("status", {})
    if st.get("state") != "SUCCEEDED":
        return "DENIED/ERROR: " + st.get("error", {}).get("message", str(d)).splitlines()[0][:220]
    cols = [c["name"] for c in d.get("manifest", {}).get("schema", {}).get("columns", [])]
    rows = [["NULL" if v is None else str(v) for v in r] for r in d.get("result", {}).get("data_array", []) or []]
    if not cols:
        return "OK"
    w = [max([len(c)] + [len(r[i]) for r in rows]) for i, c in enumerate(cols)]
    line = lambda vals: "  ".join(v.ljust(w[i]) for i, v in enumerate(vals))
    return "\n".join([line(cols), line(["-" * x for x in w])] + [line(r) for r in rows])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="")
    ap.add_argument("--warehouse", default="7252b2dd64dc2427")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()
    host = w.config.host.rstrip("/")
    sp = next(iter(w.service_principals.list(filter=f'displayName eq "{SP_NAME}"')))
    app_id = sp.application_id
    owner_token = w.config.authenticate()["Authorization"].split(" ", 1)[1]  # in memory only

    def as_owner(sql, check=True):
        d = run_sql(host, owner_token, a.warehouse, sql)
        if check:
            assert d["status"]["state"] == "SUCCEEDED", (sql, d["status"])
        return d

    w.permissions.update("warehouses", a.warehouse, access_control_list=[AccessControlRequest(service_principal_name=app_id, permission_level=PermissionLevel.CAN_USE)])
    as_owner(f"GRANT USE CATALOG ON CATALOG c360_bank TO `{app_id}`")
    as_owner(f"GRANT USE SCHEMA ON SCHEMA {FQ} TO `{app_id}`")
    for t in ("gold_cohort_growth", "gold_penetration_by_tier"):
        as_owner(f"REVOKE SELECT ON TABLE {FQ}.{t} FROM `{app_id}`", check=False)
    granted = list(GRANTED)
    for t in GRANTED + OPTIONAL:
        d = as_owner(f"GRANT SELECT ON TABLE {FQ}.{t} TO `{app_id}`", check=t in GRANTED)
        if t in OPTIONAL and d["status"]["state"] == "SUCCEEDED":
            granted.append(t)

    is_admin = any(g.display == "admins" for g in (sp.groups or []))
    print("# Evidence 12: access test with a real non-admin identity")
    print(f"# Captured {dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} by tools/access_test.py. Synthetic data; user identities redacted.")
    print(f"\nPrincipal: service principal '{SP_NAME}' (application ID {app_id}); workspace admin: {is_admin}; workspace entitlements: {[e.value for e in (sp.entitlements or [])]}")
    print(f"UC grants: USE CATALOG c360_bank, USE SCHEMA cards, SELECT on {', '.join(granted)}. SQL warehouse: CAN_USE.")
    print("Personas are set by the data owner in cards_entitlements, not by the principal.")

    secret = w.service_principal_secrets_proxy.create(service_principal_id=sp.id)
    try:
        tok = requests.post(f"{host}/oidc/v1/token", auth=(app_id, secret.secret),
                            data={"grant_type": "client_credentials", "scope": "all-apis"}, timeout=60).json()["access_token"]
        upsert = lambda persona, regions: f"""MERGE INTO {FQ}.cards_entitlements t USING (SELECT '{app_id}' AS p) s ON t.principal = s.p
            WHEN MATCHED THEN UPDATE SET persona = '{persona}', regions = {regions}, updated_at = current_timestamp()
            WHEN NOT MATCHED THEN INSERT (principal, persona, regions, updated_at) VALUES (s.p, '{persona}', {regions}, current_timestamp())"""
        scenarios = [
            ("dna_analyst", upsert("dna_analyst", "NULL")),
            ("campaign_team (region Triangle)", upsert("campaign_team", "ARRAY('Triangle')")),
            ("cdo", upsert("cdo", "NULL")),
            ("no entitlement (row removed)", f"DELETE FROM {FQ}.cards_entitlements WHERE principal = '{app_id}'"),
        ]
        for label, setup in scenarios:
            as_owner(setup)
            print(f"\n==================== {label} ====================")
            for title, sql in QUERIES:
                print(f"\n## {title}")
                print(fmt(run_sql(host, tok, a.warehouse, sql)))
        print("\n==================== data owner check (expected counts) ====================")
        print(fmt(as_owner(f"""SELECT campaign_region, count(*) AS customers FROM {FQ}.silver_customer_identifiers GROUP BY 1 ORDER BY 1""")))
        print(fmt(as_owner(f"SELECT min(address_token) AS owner_sees_address_token FROM {FQ}.silver_customer_identifiers")))
    finally:
        as_owner(f"DELETE FROM {FQ}.cards_entitlements WHERE principal = '{app_id}'")
        w.service_principal_secrets_proxy.delete(service_principal_id=sp.id, secret_id=secret.id)
        print("\nCleanup: test entitlement removed; the principal's OAuth secret was deleted after the test.")


if __name__ == "__main__":
    import contextlib, io, sys
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main()
    sys.stdout.write(EMAIL.sub("<user>", buf.getvalue()))
