"""Local test of the campaign app with Streamlit's AppTest, against the real Lakebase views.
Runs as the CLI user acting as the roster reviewer (CARDS_DEV_REVIEWER): renders all four screens,
then records one review decision through the app's form and reads it back.

Usage: DATABRICKS_CONFIG_PROFILE=febar CARDS_DEV_REVIEWER=<your email> .venv/bin/python tools/test_app.py
"""
import json
import os

from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "app", "app.py")
out = {"step": "app_test"}
at = AppTest.from_file(APP, default_timeout=180).run()
assert not at.exception, at.exception
out["city_page"] = {"metrics": {m.label: m.value for m in at.metric}, "charts": len(at.get("vega_lite_chart")), "tables": len(at.dataframe)}
at.sidebar.radio[0].set_value("Growing cohorts").run()
out["cohorts_page"] = {"rows": at.dataframe[0].value.shape[0] if at.dataframe else 0, "charts": len(at.get("vega_lite_chart"))}
at.sidebar.radio[0].set_value("Target review").run()
at.selectbox(key="rv_region").select("Triangle").run()
at.selectbox(key="rv_tier").select("Gold").run()
mix = at.dataframe[0].value
targets = at.dataframe[1].value
out["review_page"] = {"mix_rows": len(mix), "mix_flags": mix[mix["flag"] != ""]["age group"].tolist(), "targets_listed": len(targets)}
tid = targets.iloc[2]["target_id"]
label = next(o for o in at.selectbox(key="rv_pick").options if o.endswith(tid))
at.selectbox(key="rv_pick").select(label).run()
next(r for r in at.radio if r.label == "Decision").set_value("exclude")
at.text_input[0].input("demo review: already holds a competitor card (synthetic)")
at.button[0].click().run()
out["decision_recorded"] = any("Recorded: exclude" in s.value for s in at.success)
at.sidebar.radio[0].set_value("Target detail").run()
hist = at.dataframe[0].value if at.dataframe else None
out["detail_page"] = {"target_id": tid, "reasons_listed": sum(1 for m in at.markdown if m.value.startswith("- ")),
                      "history_rows": 0 if hist is None else len(hist), "latest_decision": None if hist is None else hist.iloc[0]["decision"]}
out["exceptions"] = len(at.exception)
ok = (not at.exception and out["city_page"]["charts"] >= 1 and out["cohorts_page"]["rows"] > 0 and out["decision_recorded"]
      and out["detail_page"]["latest_decision"] == "exclude")
out["status"] = "ok" if ok else "failed"
print(json.dumps(out, default=str))
raise SystemExit(0 if ok else 1)
