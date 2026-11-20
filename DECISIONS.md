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
