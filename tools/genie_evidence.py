"""Write evidence/07_genie.txt: Genie space summary, all benchmark eval runs, and per-question results of the latest run.
Usage: python3 tools/genie_evidence.py --profile febar"""
import argparse
import datetime as dt
import json
import subprocess


def cli(p, *args):
    out = subprocess.run(["databricks", *args, "--profile", p, "-o", "json"], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


ap = argparse.ArgumentParser()
ap.add_argument("--profile", required=True)
a = ap.parse_args()
space = cli(a.profile, "bundle", "summary")["resources"]["genie_spaces"]["cards_cdo"]["id"]
spec = json.load(open("src/genie/cards_cdo.geniespace.json"))
runs = cli(a.profile, "genie", "genie-list-eval-runs", space)
runs = sorted(runs.get("eval_runs", runs if isinstance(runs, list) else []), key=lambda r: r.get("created_timestamp", 0))
body = (f"# Evidence 07: Genie space (CDO and Data & Analytics) and benchmark evaluations\n"
        f"# Captured {dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} by tools/genie_evidence.py\n\n"
        f"Genie space {space}: tables {', '.join(t['identifier'] for t in spec['data_sources']['tables'])}; "
        f"{len(spec['config']['sample_questions'])} sample questions, {len(spec['instructions']['example_question_sqls'])} example SQLs, "
        f"{len(spec['benchmarks']['questions'])} benchmark questions. Bar: 8 of 10 correct.\n\n## Benchmark evaluation runs (oldest first)\n")
for r in runs:
    t = dt.datetime.fromtimestamp(r["created_timestamp"] / 1000, dt.timezone.utc)
    body += f"{r['eval_run_id']}  {t:%Y-%m-%dT%H:%M:%SZ}  {r.get('eval_run_status')}  correct {r.get('num_correct')}/{r.get('num_questions')}  needs_review {r.get('num_needs_review', 0)}\n"
last = runs[-1]["eval_run_id"]
body += f"\n## Latest run {last}: per question\n"
for x in cli(a.profile, "genie", "genie-list-eval-results", space, last).get("eval_results", []):
    d = cli(a.profile, "genie", "genie-get-eval-result-details", space, last, x["result_id"])
    act = (d.get("actual_response") or [{}])[0].get("response", "").strip()
    body += f"\nQ: {x.get('question')}\nassessment: {d.get('assessment')} {d.get('assessment_reasons') or ''}\nGenie SQL:\n{act}\n"
open("evidence/07_genie.txt", "w").write(body)
print(body[:1500])
