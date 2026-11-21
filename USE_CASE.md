# Use case: credit card adoption by tier at Arkterus Bank

[YOUR WORDS] Every section below is a draft for you to rewrite. Items marked [ASSUMPTION] are my estimates; items marked [CHECK] need a source before you present them. All data in the build is synthetic.

## 1. One-line outcome

[YOUR WORDS] Arkterus Bank finds, in-house and every morning, the customer cohorts whose card acceptance is growing more than 10% a year, and shows they convert better than the vendor's targets: Card Product Penetration Rate by Tier rises from about 6% to 7.2% [ASSUMPTION], worth about $7M a year more toward the expansion plan.

## 2. The problem, in the customer's words

[YOUR WORDS] "Card spend is one of the few high-margin businesses we have, and new cards fund up to 35% of the $100 million we need to grow: new branches and banking centers, deposit campaigns, hiring. But we don't choose our own targets. We pay a premium to an outside vendor whose models we can't see, and my data team spends most of its month pulling and validating data from two systems just to meet the vendor's input requirements. All I can report upward is new cards by city, after the fact. I can't tell the executive committee which customers are choosing which card, or why."

Quantified pain: most of the Data & Analytics team's time goes into preparing vendor input files, about 60% of a 6-person team, or about 7,500 hours a year [ASSUMPTION], plus the vendor fee, about $1.2M a year [ASSUMPTION].

## 3. Why now

[YOUR WORDS]
1. **Executive pressure for non-deposit revenue.** The bank has made card acquisition a priority, and the expansion plan depends on it (up to 35% of $100M).
2. **Cost of living is changing what customers choose.** Food, fuel and housing costs rose sharply from 2021 to 2025 in North Carolina and South Carolina metros [CHECK: BLS CPI and EIA gasoline series], pushing households toward balance transfers and everyday cashback rather than travel rewards. A vendor model trained on older behavior may miss the shift.
3. **Third-party model risk.** Regulators expect banks to understand and validate the models they rely on, including vendor models, and to show credit-marketing targeting is fair [CHECK: interagency model risk guidance and fair lending expectations]. A black-box target list is hard to defend.

## 4. Personas

[YOUR WORDS]
- **CDO (executive sponsor).** Owns the monthly report of new card acquisitions by city to the executive committee. KPI: Card Product Penetration Rate by Tier and card acquisition growth. Needs to say which cohorts are growing, which offers work for them, and why, not just how many cards each city added.
- **EVP Data & Analytics (domain owner).** Runs the team that collects, analyzes and validates data from ecif and crm to meet the vendor's input requirements. KPI: on-time, validated campaign inputs; time from data refresh to insight [ASSUMPTION]. Wants that time back for analysis the bank owns.

## 5. Today versus tomorrow

[YOUR WORDS]

| | Today | Tomorrow |
|---|---|---|
| Who picks the targets | A third-party vendor's proprietary model | An in-house model on governed bank data, with reasons for each score |
| Getting the data ready | Manual pulls from ecif and crm, validated by hand to meet vendor input rules | A pipeline lands the 12:01 am refresh, applies quality rules and conforms both systems automatically |
| What the CDO reports | New card acquisitions by city, monthly, after the fact | Penetration by tier and by cohort, with which cohorts are growing more than 10% a year, every morning |
| Answering a new question | A request to the data team or the vendor, days later | Ask Genie in plain English ("which cohorts accepted 0% balance transfers as grocery prices rose?") |

## 6. Value hypothesis in Card Product Penetration Rate by Tier

Illustrative, on the synthetic dataset. Every number carries its assumption.

| Value driver | Current baseline | Expected change | Assumption | Illustrative value |
|---|---|---|---|---|
| Card Product Penetration Rate by Tier (accepted / qualified targeted) | about 6% overall; by tier measured in the build | to 7.2% overall | [ASSUMPTION] targeting the growing cohorts lifts acceptance by 20% relative | 20% more new cards from the same campaign volume |
| Card revenue toward expansion | up to $35M (35% of $100M) | plus 20% | [ASSUMPTION] card revenue scales with new cards | about $7M a year more toward expansion |
| Vendor fee | about $1.2M a year [ASSUMPTION] | run alongside the vendor for one campaign cycle and compare; retire it only if the in-house targets win | [ASSUMPTION] in-house model beats the vendor's targets on the out-of-time test | up to about $1.2M a year, after the parallel cycle |
| Data team time on vendor inputs | about 7,500 hours a year [ASSUMPTION] | down 70% | [ASSUMPTION] pipeline replaces manual pulls and validation | about 5,000 hours a year returned to analysis (capacity, not cash) |

The 6-month win: the bank finds the demographic cohorts whose acceptance is consistently growing above 10% a year, and shows they convert better than the vendor's targets, worth about $7M a year more toward expansion [ASSUMPTION]. The test also compares the model with and without the public cost-of-living data, so the cost-of-living story is measured, not asserted. Stop if the in-house targets cannot beat the vendor-style baseline on held-out months (rules set in `EVAL_PROTOCOL.md` before any results).

## 7. The data

| Source | What it holds | Tables (rows, synthetic) | Refresh |
|---|---|---|---|
| ecif (customer system) | Customer demographics, income, credit score, household payment, residence | customer profile (about 180,000), accounts (about 230,000), monthly balances (about 2.7M) [ASSUMPTION on counts] | Daily at 12:01 am |
| crm (campaign system) | Campaigns, offers, solicitations, responses | campaigns and offers (5), solicitations and responses (about 180,000 over 24 months) | Daily at 12:01 am |
| Public macro data | Monthly metro and state prices: gasoline, vehicles, food at home, other staples and discretionary | about 24 months x 8 metros x 6 series | Monthly |

What is messy:
- The two systems key customers differently: crm uses its own customer key, mapped to the ecif customer ID through a cross-reference. Today analysts reconcile this by hand before every vendor file. Both systems name the cards the same way (Silver, Gold, Platinum, Cashback).
- City spellings are inconsistent ("Winston-salem"), and one city has no household payment data.
- Some customers have a zero household payment (paid-off home or rent paid by someone else), which must not be read as missing.
- Daily files can arrive late or be resent, which creates duplicates [ASSUMPTION].
- Names and contact details are not needed and are kept out of the build.

## 8. How the six stages serve the story

[YOUR WORDS]
- **Lakeflow:** lands the 12:01 am ecif and crm files and the macro data, conforms the two systems and applies quality rules, replacing the manual pulls.
- **Unity Catalog:** governs who sees what (analysts see cohorts, not identifiers), tags personal data, and supports fair lending practice: protected attributes (age, marital status, gender) are tagged and excluded from the targeting model's features, and are used only to monitor outcomes across groups [CHECK: ECOA and Regulation B guidance on prescreened credit offers].
- **Lakebase:** serves the daily target list to the campaign team's app and stores their accept or exclude decisions on each target before a campaign goes out. That human review step is the reason for an operational database: the decisions are written back, audited and fed into the next day's analysis.
- **ML or GenAI:** scores each qualified customer's likelihood to accept each offer without using protected attributes, explains the top reasons in plain English, and flags cohorts growing more than 10% a year. Tested on later months it never saw, against a vendor-style baseline, with and without the cost-of-living data.
- **Genie:** opens on the CDO's familiar view, new cards by city, then lets the CDO and analysts drill into penetration by tier and cohort and ask how it tracks the cost of living.
- **App:** opens on new cards by city (the CDO's monthly report today), then breaks it down by tier and cohort to show the growing cohorts; the campaign team reviews the next campaign's target list by tier and offer, with reasons, and accepts or excludes each target.

## 9. What we will NOT build

- Credit decisioning, underwriting or APR pricing (the build uses the published tier rules only).
- Sending real campaigns, mail or email; integration with a real vendor.
- Card spend, revenue or profitability per customer after acceptance.
- Real-time scoring; the build follows the daily 12:01 am refresh.
- Any real customer data, names or contact details.
