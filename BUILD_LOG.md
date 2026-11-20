# Build Log

| Date | What I tried | What failed | What I changed and why |
|---|---|---|---|
| 2026-11-20 | Wrote FEBAR_CONTEXT.md, CLAUDE.md pointer and .gitignore in the cloned repo; read-only access check with profile febar | (none) | Confirmed: workspace fevm-febar-c360-bank, catalog c360_bank (ALL_PRIVILEGES), schema `cards` to be created by the bundle; bank renamed from Orbit Bank to Arkterus Bank (fictional) |
| 2026-11-20 | Swapped roles at the user's request | (none) | Executive sponsor is now the CDO; domain owner is the EVP Data & Analytics |
| 2026-11-20 | Profiled the authored demographic table read-only (aggregate queries only, profile E2) | The E2 CLI login had expired (re-authenticated); a count query missed Winston-Salem because the source spells it "Winston-salem" | Recorded card tier rules, the metric definition, the story and market definitions in DECISIONS.md; wrote the synthetic data rules in DATA_DESIGN.md; city spelling to be standardized in the pipeline |
