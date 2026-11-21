# Synthetic data design

How the synthetic Arkterus Bank dataset is built. All customers are synthetic; there are no names, email addresses or phone numbers. The generator in `src/data/` implements these rules, and `evidence/` records the counts from each run.

## 1. Population

- **Base:** a synthetic demographic profile table authored for this demo (175,885 customers in North Carolina and South Carolina, 21 cities, 51 ZIPs). Every customer has a checking account and no bank credit card, and was targeted by a card campaign in the last 24 months.
- **Added customers:** 6,250, generated to give the key segments enough rows to learn from:

  | Group | Customers | Profile |
  |---|---|---|
  | Platinum balance transfer | 2,159 (Raleigh 650, Charlotte 1,020, Durham 489) | Millennial and Gen X; Platinum-qualified; household payment above $1,400 |
  | Greensboro homeowners | 1,000 | Mixed profiles (about 30% fit the Gold grocery segment); payment by move-in year (below) |
  | Apex and Holly Springs Gold | 700 and 600 | Gold grocery segment profile; income $75,000 to $125,000; moved in 2020 to 2025; marital status mixed |
  | Gold segment boost | 1,491 (Greensboro 120, Winston-Salem 120, Apex 682, Holly Springs 569) | Gold grocery segment profile; moved in 2020 to 2025 (Greensboro 2021 to 2025, payments by its yearly medians); income $75,000 to $125,000 in Apex and Holly Springs; marital status mixed |
| High payers | 300 | Payment $7,000 to $15,000 a month; income $250,000 to $600,000; credit score 720 to 850; mostly Millennial and Gen X homeowners; moved in 2021 to 2025; ZIPs 27609, 28211, 28207, 28405, 28411, 29401, 29407 |

  Greensboro payment medians by move-in year (drawn within plus or minus 20%): 2021 $1,250, 2022 $1,588, 2023 $1,996, 2024 $2,035, 2025 $2,185. Residency duration = 2025 minus move-in year.
- **Adjusted customers:** in Winston-Salem, 45% of homeowners who moved in 0 to 5 years ago, aged 30 to 50, earning $50,000 to $125,000 with credit scores at 700 or below (about 226) get scores of 701 to 760 and payments of $1,000 to $1,500 by move-in year.
- **Total:** 182,135 customers. Column `record_origin` (`source`, `added_synthetic`, `adjusted`) and `origin_group` mark every row.

- **Generations** use the source table's age bands (age in 2026): Gen Z 18 to 28, Millennials 29 to 45, Gen X 46 to 58, Boomers 59 to 68, Silent 69 and over.

## 2. Cleanup

- City spelling standardized ("Winston-Salem").
- Chapel Hill household payments (missing) filled from Raleigh's median for the same employment status, within plus or minus 20% (student $405 to $607, employed $732 to $1,098, self-employed $746 to $1,120, unemployed $1,075 to $1,613, retired $1,101 to $1,651).
- Other zero payments stay at 0: these customers have no mortgage or rent payment (home paid off, or someone else pays their rent).

## 2a. Two source systems

- Customer data comes from the customer system (ecif) and campaign data from the campaign system (crm), each landing as daily files at 12:01 am.
- crm uses its own customer key; a cross-reference table maps it to the ecif customer ID.
- Both systems use the same card names: Silver, Gold, Platinum, Cashback.

## 3. Accounts and balances

- Account mix by generation (checking only / checking and savings / checking, savings and money market): Gen Z 90/8/2, Millennials 86/10/4, Gen X 68/25/7, Boomers 58/33/9, Silent 48/40/12.
- Monthly balances for 12 months, proportional to income and employment status. Retired customers receive Social Security, pension and retirement distributions; students receive a steady monthly deposit (family support) covering the household payment. Older cohorts hold more in savings and money market.
- Eligibility uses the 6-month average balance (or since opening if newer); the reported balance column is the 12-month average.

## 4. Campaigns

| Card | Offer |
|---|---|
| Silver | 0% balance transfer for 6 months |
| Gold | 5% cashback on groceries for 12 months |
| Platinum | 0% balance transfer for 12 months; separate 5% cashback on travel and entertainment |
| Cashback | 3% cashback on all purchases for 6 months |

Columns generated per solicitation: date sent, card, offer, accepted or declined. Solicitations span the last 24 months; the training set is 80% of customers.

## 5. Acceptance patterns

Overall acceptance is about 6%; segments not listed are set so the total lands there.

| Segment | Offer | Year 1 | Year 2 | Notes |
|---|---|---|---|---|
| Millennial and Gen X, Platinum-qualified, payment above $1,400, in Cary, Raleigh, Charlotte, Greenville, Durham, Wilmington, Charleston | Platinum 0% balance transfer | 18% to 24% (March to September), 15% to 17% other months | 15% to 24% | |
| Same segment | Platinum travel and entertainment | 1% to 3% | under 1% | |
| Homeowners who moved in 0 to 5 years ago (residency 0 to 5 years), aged 30 to 50, income $50,000 to $125,000, credit score 700+, payment above $1,000, in Apex, Holly Springs, Greensboro, Winston-Salem | Gold groceries | 14% to 16% | 17% to 19% | Rising April to September and again November to early December |
| Renters aged 28 to 35, credit score 680 to 740, in Charleston, Wilmington, Myrtle Beach | Silver balance transfer | 18% to 22% | 18% to 22% | |
| Over 58, 2+ accounts, credit score above 700 | Any | 1% to 1.5% | 1% to 1.5% | |
| Other Boomers | Any | 4% to 6% | 4% to 6% | High end in Raleigh and Charlotte |
| Silent | Any | 2% to 4% | 2% to 4% | |

- Millennials and Gen X convert above older cohorts everywhere, with a further 30% to 50% relative uplift in cities where household payments grew most from 2021 to 2025. Older cohorts stay flat.
- Cost of living: for urban and suburban mass affluent customers, monthly acceptance of balance transfer and grocery cashback offers rises with the trailing 3-month change in metro food-at-home and gasoline prices and with housing payment growth; travel and entertainment acceptance falls as those prices rise. The Cashback 3% offer gets a milder uptick than Gold groceries.

- No planted segment is defined by marital status (fair lending review). Recent home buyers stand in for the rising cost of buying a home: the median payment for homeowners in the Gold cities rises from $459 (moved in 2020) to $1,113 (2025).

## 6. Public macro data

Monthly series for the 24 months at metro or state level: gasoline prices, new and used vehicle prices, food at home, and other staples and discretionary price indexes. Source and download method are set in `BUILD_PLAN.md`.
