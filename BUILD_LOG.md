# Build Log

| Date | What I tried | What failed | What I changed and why |
|---|---|---|---|
| 2026-11-20 | Wrote FEBAR_CONTEXT.md, CLAUDE.md pointer and .gitignore in the cloned repo; read-only access check with profile febar | (none) | Confirmed: workspace fevm-febar-c360-bank, catalog c360_bank (ALL_PRIVILEGES), schema `cards` to be created by the bundle; bank renamed from Orbit Bank to Arkterus Bank (fictional) |
| 2026-11-20 | Swapped roles at the user's request | (none) | Executive sponsor is now the CDO; domain owner is the EVP Data & Analytics |
| 2026-11-20 | Profiled the authored demographic table read-only (aggregate queries only, profile E2) | The E2 CLI login had expired (re-authenticated); a count query missed Winston-Salem because the source spells it "Winston-salem" | Recorded card tier rules, the metric definition, the story and market definitions in DECISIONS.md; wrote the synthetic data rules in DATA_DESIGN.md; city spelling to be standardized in the pipeline |
| 2026-11-20 | Drafted USE_CASE.md from the discovery answers (Q6 unanswered, so marked as assumptions) | (none) | Draft awaiting the author's approval and rewrite |
| 2026-11-20 | Applied the author's answers to the use case challenge | (none) | Win tied to beating the vendor's targets; parallel vendor cycle; Lakebase review step; protected attributes excluded from the model; two-system conforming; city-first views |
| 2026-11-20 | Harmonized the entry card name | (none) | "Standard" removed; both systems use Silver; customer key mismatch remains the conforming step |
| 2026-11-20 | Wrote build decisions, EVAL_PROTOCOL.md (committed before any data) and BUILD_PLAN.md | (none) | Awaiting the author's approval of BUILD_PLAN.md |
| 2026-11-20 | Downloaded public price data (BLS CPI South region, 11 series; EIA Lower Atlantic gasoline; FHFA HPI for 14 metros) with tools/download_public_data.py | BLS has no October 2025 value for 8 of 11 series (not published) | Committed the CSVs; campaign window set to the latest 24 complete months, November 2024 to October 2026; the pipeline will fill the October 2025 gap by interpolation and flag it |
