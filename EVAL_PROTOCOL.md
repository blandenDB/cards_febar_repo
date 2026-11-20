# Evaluation protocol

Written and committed on 2026-11-20, before any data was generated or any result produced. Any later change is added as a dated note at the end; original results are kept.

## 1. Question

Do in-house acceptance scores pick card targets that accept more often than a vendor-style rule list, by tier, on customers and months the model never saw? Does public cost-of-living data add to that? Which cohorts are consistently growing above 10% a year?

## 2. Data split

- **Customers:** a fixed hash of `customer_id` assigns 80% to train and 20% to test.
- **Time:** campaign months 1 to 18 are the training period; months 19 to 24 are the test period.
- **Training set:** solicitations to train customers in months 1 to 18.
- **Test set:** solicitations to test customers in months 19 to 24. Nothing from the test set is used for training, tuning or feature design.
- Only qualified solicitations (customer met the tier rules on the solicitation date) count toward the measures, matching the metric definition.

## 3. Timing rule

Every feature for a solicitation uses only what was known the day before its solicitation date:
- balances and account counts up to the prior month end;
- public price data shifted by one month to allow for publication delay;
- no information from the response or anything after the solicitation date;
- the customer's own earlier solicitations and responses only if they happened before that date.

## 4. Fair lending rule

The model's features exclude age, generation, date of birth, marital status and gender. The feature list is printed in the evidence. These attributes are used only in the fairness monitor (section 8).

## 5. Baseline

**Vendor-style rule score:** for each tier, among qualified customers, the sum of standardized income, credit score and 6-month average deposit balance. Higher is targeted first. It follows the same timing rule.

## 6. Main measure and bar

- **Main measure:** acceptance rate among the top 20% of test-set qualified solicitations ranked by each method, per tier (Silver, Gold, Platinum, Cashback), and pooled across tiers.
- **Claim "in-house targets beat the vendor-style list" only if:** the pooled top-20% acceptance rate is at least 1.2 times the baseline's, and at least 3 of the 4 tiers are at or above 1.0 times the baseline.
- **Secondary (reported, no bar):** area under the ROC curve per offer; acceptance-rate lift by decile.

## 7. Cost-of-living claim

- Train the same model without the public price features.
- **Claim "cost-of-living data improves targeting" only if** the pooled test-set ROC AUC with price features is at least 0.01 higher than without.
- Otherwise the cost-of-living story is described as context only.

## 8. Cohort growth claim

- **Cohort (descriptive, not used for targeting):** generation x market type x mass affluent flag x tier.
- **Growth:** acceptance rate in one 6-month period divided by the rate in the same months a year earlier, minus 1.
- **Claim "cohort is consistently growing above 10% a year" only if** growth is above 10% for months 13 to 18 versus 1 to 6 (training period) and again for months 19 to 24 versus 7 to 12 (test period), with at least 200 qualified solicitations in each period.

## 9. Fairness monitor (reported, flagged)

For each age group and marital status, the share selected into the top 20% divided by the share of the most-selected group (adverse impact ratio). Any ratio below 0.8 is flagged in the evidence and the README. This is a monitor, not a pass bar.

## 10. Explanations (GenAI)

- A random sample of 200 generated explanations is scored by an LLM judge on: grounded (uses only the listed facts), no protected attributes mentioned, relevant to the offer.
- **Bar:** at least 95% on each check.
- Any rerun after a prompt fix is recorded with the reason; every run's result is kept.

## 11. No claim

A result below any bar means no claim for that question. The result is recorded in `evidence/` and stated as such in the README and deck. The bars in this file are not changed after results are seen; any change is a dated note below, and the original results stay.

## Change notes

(none)
