-- Gold: business-ready tables for the CDO, Genie, the model and the app.

CREATE OR REFRESH MATERIALIZED VIEW gold_features
COMMENT 'One row per solicitation: point-in-time features and the accepted label. Includes protected attributes for fairness monitoring only; the model reads v_model_features, which excludes them.'
AS
SELECT
  s.solicitation_id, s.customer_id, s.offer_code, s.card_product, s.sent_date, s.sent_month, s.campaign_month,
  s.qualified, s.accepted,
  -- profile (static ecif attributes)
  c.city, c.state, c.zip_code, c.campaign_region, c.market_type, c.low_cost_market, c.urban_suburban, c.mass_affluent,
  c.annual_income, c.credit_score, c.monthly_household_pmt, c.own_rent_home, c.employment_status,
  c.residence_year, year(s.sent_date) - c.residence_year AS years_at_residence,
  datediff(s.sent_date, c.customer_since) / 365.25 AS tenure_years,
  c.preferred_channel, s.channel,
  -- accounts and balances known before the solicitation month
  coalesce(acc.n_accounts, 0) AS n_accounts, coalesce(acc.has_savings, false) AS has_savings,
  coalesce(acc.has_money_market, false) AS has_money_market,
  s.avg6_total_balance,
  -- public prices, as published one month before the solicitation month
  m.food_at_home_3m_change, m.gasoline_3m_change, m.cpi_all_items_yoy, m.used_vehicles_yoy, m.new_vehicles_yoy,
  m.gasoline_usd_per_gallon, m.cpi_interpolated,
  -- house prices, three months behind (quarterly publication)
  h.house_price_yoy,
  -- protected attributes (fairness monitor only)
  c.age - floor(datediff(DATE'2026-11-01', s.sent_date) / 365) AS age_at_solicitation,
  c.generation, c.marital_status, c.gender,
  c.record_origin
FROM silver_solicitations s
JOIN silver_customers c ON c.customer_id = s.customer_id
LEFT JOIN (
  SELECT s2.solicitation_id, count(*) AS n_accounts, count_if(a.product = 'savings') > 0 AS has_savings,
         count_if(a.product = 'money_market') > 0 AS has_money_market
  FROM silver_solicitations s2 JOIN silver_accounts a ON a.customer_id = s2.customer_id AND a.open_date < s2.sent_month
  GROUP BY s2.solicitation_id
) acc ON acc.solicitation_id = s.solicitation_id
LEFT JOIN silver_macro_monthly m ON m.metro_area = c.metro_area AND m.month = add_months(s.sent_month, -1)
LEFT JOIN silver_macro_monthly h ON h.metro_area = c.metro_area AND h.month = add_months(s.sent_month, -3);

CREATE OR REFRESH MATERIALIZED VIEW gold_penetration_by_tier
COMMENT 'Card Product Penetration Rate by Tier: one row per month x city x tier x generation x market type x mass affluent; accepted offers / qualified customers targeted'
AS SELECT
  s.sent_month AS month, c.city, c.market_type, s.card_product AS tier, c.generation, c.mass_affluent,
  count(*) AS targeted,
  count_if(s.qualified) AS qualified_targeted,
  count_if(s.accepted) AS new_cards,
  count_if(s.accepted AND s.qualified) AS accepted_qualified,
  try_divide(count_if(s.accepted AND s.qualified), count_if(s.qualified)) AS penetration_rate
FROM silver_solicitations s JOIN silver_customers c ON c.customer_id = s.customer_id
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW gold_cohort_growth
COMMENT 'One row per cohort (generation x market type x mass affluent x tier): qualified acceptance by 6-month period and growth versus a year earlier; growing_above_10pct when growth exceeds 10% in both the training and test periods with at least 200 qualified solicitations each (EVAL_PROTOCOL.md section 8)'
AS
WITH p AS (
  SELECT c.generation, c.market_type, c.mass_affluent, s.card_product AS tier,
         CAST(ceil(s.campaign_month / 6.0) AS INT) AS period,
         count(*) AS n, avg(CAST(s.accepted AS INT)) AS rate
  FROM silver_solicitations s JOIN silver_customers c ON c.customer_id = s.customer_id
  WHERE s.qualified
  GROUP BY ALL
),
w AS (
  SELECT generation, market_type, mass_affluent, tier,
    max(CASE WHEN period = 1 THEN n END) AS n_p1, max(CASE WHEN period = 1 THEN rate END) AS rate_p1,
    max(CASE WHEN period = 2 THEN n END) AS n_p2, max(CASE WHEN period = 2 THEN rate END) AS rate_p2,
    max(CASE WHEN period = 3 THEN n END) AS n_p3, max(CASE WHEN period = 3 THEN rate END) AS rate_p3,
    max(CASE WHEN period = 4 THEN n END) AS n_p4, max(CASE WHEN period = 4 THEN rate END) AS rate_p4
  FROM p GROUP BY ALL
)
SELECT *,
  try_divide(rate_p3, rate_p1) - 1 AS growth_train,
  try_divide(rate_p4, rate_p2) - 1 AS growth_test,
  coalesce(try_divide(rate_p3, rate_p1) - 1 > 0.10 AND try_divide(rate_p4, rate_p2) - 1 > 0.10
           AND least(n_p1, n_p2, n_p3, n_p4) >= 200, false) AS growing_above_10pct
FROM w;

CREATE OR REFRESH MATERIALIZED VIEW gold_next_campaign_features
COMMENT 'Next campaign (November 2026): one row per customer x offer the customer qualifies for today, with the same point-in-time features as gold_features. Includes protected attributes for fairness monitoring only; the model reads v_next_campaign_features.'
AS
WITH c AS (SELECT * FROM silver_customers),
avg6 AS (
  SELECT customer_id, avg(total_balance) AS avg6_total_balance FROM silver_balances_monthly
  WHERE month >= DATE'2026-05-01' AND month < DATE'2026-11-01' GROUP BY customer_id
),
acc AS (
  SELECT customer_id, count(*) AS n_accounts, count_if(product = 'savings') > 0 AS has_savings,
         count_if(product = 'money_market') > 0 AS has_money_market
  FROM silver_accounts WHERE open_date < DATE'2026-11-01' GROUP BY customer_id
),
offers AS (SELECT DISTINCT offer_code, card_product FROM silver_campaigns)
SELECT
  concat(c.customer_id, '-', o.offer_code) AS target_id, c.customer_id, o.offer_code, o.card_product,
  DATE'2026-11-01' AS sent_month, 25 AS campaign_month,
  c.city, c.state, c.zip_code, c.campaign_region, c.market_type, c.low_cost_market, c.urban_suburban, c.mass_affluent,
  c.annual_income, c.credit_score, c.monthly_household_pmt, c.own_rent_home, c.employment_status,
  c.residence_year, 2026 - c.residence_year AS years_at_residence,
  datediff(DATE'2026-11-01', c.customer_since) / 365.25 AS tenure_years, c.preferred_channel,
  coalesce(acc.n_accounts, 0) AS n_accounts, coalesce(acc.has_savings, false) AS has_savings,
  coalesce(acc.has_money_market, false) AS has_money_market, a.avg6_total_balance,
  m.food_at_home_3m_change, m.gasoline_3m_change, m.cpi_all_items_yoy, m.used_vehicles_yoy, m.new_vehicles_yoy,
  m.gasoline_usd_per_gallon, m.cpi_interpolated, h.house_price_yoy,
  c.age AS age_at_solicitation, c.generation, c.marital_status, c.gender
FROM c
CROSS JOIN offers o
JOIN silver_card_rules r ON r.card_product = o.card_product
LEFT JOIN avg6 a ON a.customer_id = c.customer_id
LEFT JOIN acc ON acc.customer_id = c.customer_id
LEFT JOIN silver_macro_monthly m ON m.metro_area = c.metro_area AND m.month = DATE'2026-10-01'
LEFT JOIN silver_macro_monthly h ON h.metro_area = c.metro_area AND h.month = DATE'2026-08-01'
WHERE c.credit_score >= r.min_credit_score AND c.annual_income >= r.min_income AND coalesce(a.avg6_total_balance, 0) >= r.min_avg6_deposit;
