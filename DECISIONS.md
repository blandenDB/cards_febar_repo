# Decisions

[YOUR WORDS] Rewrite each entry in your own words.

## 2026-11-20: Workspace, catalog and bank name

- **Decision:** reuse the FEVM workspace from the CLV build (profile `febar`); catalog `c360_bank`, schema `cards`; the fictional bank is named Arkterus Bank (renamed from Orbit Bank).
- **Options considered:** a new FEVM workspace; reusing the existing one. For the name: keep Orbit Bank, or use a name that is clearly fictional.
- **Why:** [YOUR WORDS]

## 2026-11-20: Sponsor and domain owner

- **Decision:** the executive sponsor is the CDO; the domain owner is the EVP Data & Analytics (swapped from the original prompt).
- **Options considered:** EVP Data & Analytics as sponsor and CDO as domain owner; the reverse.
- **Why:** [YOUR WORDS]

## 2026-11-20: Card tiers and qualification rules

- **Decision:** four cards. APR within a tier falls as credit score, income and 6-month average deposit balance rise.

  | Card | Annual fee | Rewards | Min credit score | Min income | Min 6-month avg deposit | APR |
  |---|---|---|---|---|---|---|
  | Silver | $0 | (none) | 650 | $40,000 | $1,000 | 18.99% to 25.99% |
  | Gold | $95 | Everyday cashback and points (groceries, non-luxury retail) | 700 | $50,000 | $2,500 | 14.99% to 25.99% |
  | Platinum | $195 | 4% to 6% cashback on travel, entertainment and luxury retail | 750 | $125,000 | $5,000 | 12.99% to 25.99% |
  | Cashback | $50 | 2% on all purchases | 650 | $50,000 | (none) | 15.99% to 25.99% |

- **Options considered:** Platinum minimum credit score of 720, 740 or 750; Platinum minimum income of $150,000 or $125,000; Gold minimum income of $85,000, $65,000 or $50,000.
- **Why:** [YOUR WORDS]

## 2026-11-20: Success metric definition

- **Decision:** Card Product Penetration Rate by Tier = accepted offers / qualified customers who were targeted, per tier.
- **Options considered:** accepts / qualified targeted; cardholders / all eligible customers; cardholders / all customers.
- **Why:** [YOUR WORDS]

## 2026-11-20: Personal columns

- **Decision:** the build carries no names, email addresses or phone numbers; it keeps customer ID, city, state and ZIP, and uses generated tokens for street address and SSN last 4 so masking can still be shown.
- **Options considered:** drop names, email and phone; drop every personal column; keep everything and mask it.
- **Why:** [YOUR WORDS]

## 2026-11-20: The story

- **Decision:** the story is that urban and suburban mass affluent households choose 0% balance transfer and consumer-staples cashback offers because the general cost of living rose, while travel and entertainment offers and older customers lag. Public cost-of-living data (metro food, gasoline, vehicle and housing costs) sits alongside the campaign results so the link can be tested.
- **Options considered:** cost of living tied to the campaign results; campaign results only, with macro data as context.
- **Why:** [YOUR WORDS]

## 2026-11-20: Mass affluent and market type definitions

- **Decision:** mass affluent is adjusted for local cost of living: income $50,000 to $150,000 in lower-cost markets (Columbia, Greensboro, Winston-Salem, the exurbs, Greenville, Florence) and $75,000 to $250,000 elsewhere. Market types:

  | Market type | Cities |
  |---|---|
  | Urban core | Raleigh, Durham, Charlotte, Columbia, Wilmington, Charleston |
  | Suburban | Cary, Apex, Holly Springs, Chapel Hill |
  | Suburban-style metro | Greensboro, Winston-Salem |
  | Exurban | Mebane, Burlington, Salisbury |
  | Fast-growing mid-size city | Greenville |
  | Highway corridor town | Florence (Interstate 95) |
  | Coastal and resort | Myrtle Beach, Hilton Head Island, Pawleys Island |
  | Mountain and tourism city | Asheville |

  The headline group is urban core, suburban and suburban-style metro. One mass affluent flag drives every chart, Genie answer and the app.
- **Options considered:** cost-adjusted bands; 1.5x to 4x city median income; one $50,000 to $150,000 band. Three market types (urban core, suburban, other) or the finer labels above.
- **Why:** [YOUR WORDS]

## 2026-11-20: Use case framing

- **Decision:** the 6-month win is finding cohorts growing above 10% a year and showing they convert better than the vendor's targets, worth about $7M a year toward expansion. The in-house model runs alongside the vendor for one campaign cycle before any vendor change. The test compares the model with and without public cost-of-living data. The app and Genie open on new cards by city, then break it down by tier and cohort.
- **Options considered:** win as cohort identification only; win tied to vendor comparison and value. Replace the vendor outright, or a parallel cycle first.
- **Why:** [YOUR WORDS]

## 2026-11-20: Lakebase role

- **Decision:** Lakebase serves the daily target list to the campaign team and stores their accept or exclude decisions per target before each campaign; decisions flow back into the next day's analysis.
- **Options considered:** a read-only synced serving table; serving plus a human review step written back.
- **Why:** [YOUR WORDS]

## 2026-11-20: Fair lending

- **Decision:** protected attributes (age, marital status, gender) are tagged in Unity Catalog and excluded from the targeting model's features; they are used only to monitor outcomes across groups. Evidence proves the exclusion.
- **Options considered:** use all attributes in the model; exclude protected attributes from targeting and monitor outcomes.
- **Why:** [YOUR WORDS]

## 2026-11-20: Two source systems with conforming

- **Decision:** customer data from ecif and campaign data from crm, with different customer keys (mapped through a cross-reference), conformed by the pipeline. Card names are harmonized: both systems call the entry card Silver (no "Standard").
- **Options considered:** one source; two sources with a real conforming step.
- **Why:** [YOUR WORDS]

## 2026-11-20: Build design decisions (Prompt 3)

[REWRITE IN YOUR WORDS] Each entry below records the choice, the alternative and the reason as drafted; rewrite the reasons yourself.

### Ingestion
- **Decision:** daily ecif and crm files land in a Unity Catalog volume (12:01 am) and are read with Auto Loader into Lakeflow streaming tables.
- **Alternative:** a managed connector reading the source databases directly.
- **Why:** [REWRITE IN YOUR WORDS] Files replay late and resent deliveries, are quick to build, and match how the bank receives extracts today.

### Sources
- **Decision:** two sources merged (ecif customer data, crm campaign data through a customer key cross-reference) plus public price data.
- **Alternative:** one source.
- **Why:** [REWRITE IN YOUR WORDS] Conforming two systems is the manual work the data team does today.

### Public price data
- **Decision:** real public series downloaded once and committed: BLS CPI South region (food at home, gasoline, new and used vehicles, other staples and discretionary), EIA Lower Atlantic gasoline prices, FHFA house price index by metro.
- **Alternative:** generated series.
- **Why:** [REWRITE IN YOUR WORDS] Real public data makes the cost-of-living link credible; city differences come from the house price index because federal price indexes are not published for these metros.

### Data quality
- **Decision:** quarantine unmatched crm keys, unknown card or offer codes, solicitation dates outside the window and credit scores outside 300 to 850; warn on employed customers with income under $10,000 and on missing payments outside Chapel Hill; fail the update on an empty file, a changed layout or more than 5% unmatched crm keys; drop duplicates from resent files. Planted issues: a resent crm file, about 1% unmatched crm keys, a few impossible credit scores, one late file.
- **Alternative:** warn on everything.
- **Why:** [REWRITE IN YOUR WORDS]

### Governance personas
- **Decision:** D&A analysts see all rows with address and SSN tokens masked, and protected attributes only in the fairness view; the campaign team sees target lists for their assigned region only, without protected attributes; the CDO sees totals by city, tier and cohort only. The model reads a view that excludes age, marital status and gender.
- **Alternative:** two personas (analysts and campaign team).
- **Why:** [REWRITE IN YOUR WORDS]

### Access test identity
- **Decision:** a dedicated non-admin service principal runs the access test.
- **Alternative:** a second human user.
- **Why:** [REWRITE IN YOUR WORDS] Workspace accounts cannot be created on this sandbox; a service principal worked in the previous build.

### Lakebase pattern
- **Decision:** a synced table serves the target list (owner-only serving copy, access enforced again in Postgres); the app writes accept or exclude decisions to a Postgres table; a job task copies decisions back to Delta nightly.
- **Alternative:** a job task upserts the target list into Postgres and keeps human edits.
- **Why:** [REWRITE IN YOUR WORDS]

### Intelligent step
- **Decision:** both: one trained acceptance model per offer without protected attributes, plus ai_query explanations of each target's top reasons, plus a cohort growth flag above 10% a year.
- **Alternative:** an explainable points score with explanations, no model.
- **Why:** [REWRITE IN YOUR WORDS]

### AI output evaluation
- **Decision:** an LLM judge scores 200 explanations for groundedness, no mention of protected attributes and relevance; 95% each, set in advance.
- **Alternative:** manual review of 50 against a checklist.
- **Why:** [REWRITE IN YOUR WORDS]

### How results are judged
- **Decision:** `EVAL_PROTOCOL.md`, committed before any data or results: customer and time holdout, vendor-style rule baseline, top-20% acceptance by tier, 1.2x bar, cost-of-living and cohort growth claim rules.
- **Alternative:** (as recommended; no alternative chosen).
- **Why:** [REWRITE IN YOUR WORDS]

### App
- **Decision:** Streamlit with four screens: new cards by city with drill-down to tier and cohort; growing cohorts; campaign target review with accept or exclude; customer detail with reasons.
- **Alternative:** FastAPI with a React front end.
- **Why:** [REWRITE IN YOUR WORDS]

### Trigger
- **Decision:** a daily schedule at 12:30 am, 30 minutes after the files land.
- **Alternative:** a file arrival trigger with manual fallback.
- **Why:** [REWRITE IN YOUR WORDS] The file arrival trigger never fired in this workspace in the previous build.

### Campaign window
- **Decision:** the latest 24 complete months covered by the public price data (for example December 2024 to November 2026); year 1 and year 2 follow that window.
- **Alternative:** calendar years 2024 and 2025.
- **Why:** [REWRITE IN YOUR WORDS]
