-- Silver campaigns and solicitations (campaign system, crm), plus public macro data.
-- Conforming: crm customer key -> ecif customer ID through the cross-reference.
-- Duplicates from resent files are dropped; failing rows go to quarantine with the rule.

CREATE OR REFRESH MATERIALIZED VIEW silver_campaigns
COMMENT 'One row per campaign offer'
AS SELECT DISTINCT campaign_code, offer_code, card_product, offer_description,
  CAST(start_date AS DATE) AS start_date, CAST(end_date AS DATE) AS end_date
FROM bronze_crm_campaigns;

CREATE OR REFRESH MATERIALIZED VIEW silver_card_rules
COMMENT 'Card tier qualification rules (published tier rules)'
AS SELECT * FROM VALUES
  ('Silver', 650, 40000, 1000, 0, 18.99, 25.99),
  ('Gold', 700, 50000, 2500, 95, 14.99, 25.99),
  ('Platinum', 750, 125000, 5000, 195, 12.99, 25.99),
  ('Cashback', 650, 50000, 0, 50, 15.99, 25.99)
AS t(card_product, min_credit_score, min_income, min_avg6_deposit, annual_fee, apr_min, apr_max);

CREATE TEMPORARY VIEW solicitations_checked AS
WITH dedup AS (  -- a resent file repeats rows exactly; keep one copy, remember the first file seen
  SELECT solicitation_id, crm_customer_key, offer_code, card_product, campaign_code,
         CAST(sent_date AS DATE) AS sent_date, response, CAST(response_date AS DATE) AS response_date, channel,
         min(_source_file) AS _source_file, count(*) AS copies_received
  FROM bronze_crm_solicitations
  GROUP BY ALL
),
joined AS (
  SELECT s.*, x.ecif_customer_id AS customer_id, c.offer_code AS known_offer, cu.customer_id AS valid_customer
  FROM dedup s
  LEFT JOIN (SELECT DISTINCT crm_customer_key, ecif_customer_id FROM bronze_crm_xref) x ON x.crm_customer_key = s.crm_customer_key
  LEFT JOIN silver_campaigns c ON c.offer_code = s.offer_code AND c.card_product = s.card_product
  LEFT JOIN silver_customers cu ON cu.customer_id = x.ecif_customer_id
)
SELECT *,
  CASE WHEN customer_id IS NULL THEN 'crm_key_not_in_xref'
       WHEN known_offer IS NULL THEN 'unknown_card_or_offer'
       WHEN sent_date NOT BETWEEN DATE'2024-11-01' AND DATE'2026-10-31' THEN 'sent_date_outside_window'
       WHEN valid_customer IS NULL THEN 'customer_quarantined'
  END AS quarantine_reason
FROM joined;

CREATE OR REFRESH MATERIALIZED VIEW silver_solicitations_quarantine
COMMENT 'Solicitations held aside by a quality rule, with the rule that failed'
AS SELECT solicitation_id, crm_customer_key, offer_code, card_product, sent_date, response, _source_file, quarantine_reason
FROM solicitations_checked WHERE quarantine_reason IS NOT NULL;

CREATE OR REFRESH MATERIALIZED VIEW silver_solicitations
COMMENT 'One row per solicitation: deduplicated, mapped to the ecif customer, with tier qualification on the solicitation date'
AS
WITH s AS (
  SELECT solicitation_id, customer_id, crm_customer_key, offer_code, card_product, campaign_code, sent_date,
         trunc(sent_date, 'MM') AS sent_month, response = 'ACCEPTED' AS accepted, response_date, channel,
         copies_received, _source_file
  FROM solicitations_checked WHERE quarantine_reason IS NULL
),
avg6 AS (  -- 6-month average total deposit balance before the solicitation month
  SELECT s.solicitation_id, avg(b.total_balance) AS avg6_total_balance, count(*) AS avg6_months
  FROM s JOIN silver_balances_monthly b
    ON b.customer_id = s.customer_id AND b.month >= add_months(s.sent_month, -6) AND b.month < s.sent_month
  GROUP BY s.solicitation_id
)
SELECT s.*, a.avg6_total_balance, a.avg6_months,
  (c.credit_score >= r.min_credit_score AND c.annual_income >= r.min_income AND coalesce(a.avg6_total_balance, 0) >= r.min_avg6_deposit) AS qualified,
  months_between(s.sent_month, DATE'2024-11-01') + 1 AS campaign_month
FROM s
JOIN silver_customers c ON c.customer_id = s.customer_id
JOIN silver_card_rules r ON r.card_product = s.card_product
LEFT JOIN avg6 a ON a.solicitation_id = s.solicitation_id;

CREATE OR REFRESH MATERIALIZED VIEW silver_load_checks (
  CONSTRAINT no_empty_files EXPECT (min_rows_per_file > 0) ON VIOLATION FAIL UPDATE,
  CONSTRAINT layout_unchanged EXPECT (rescued_rows = 0) ON VIOLATION FAIL UPDATE,
  CONSTRAINT xref_match_rate EXPECT (unmatched_pct <= 5.0) ON VIOLATION FAIL UPDATE
)
COMMENT 'Load-level checks that stop the update: empty file, changed file layout, too many unmatched crm keys'
AS
WITH f AS (SELECT _source_file, count(*) AS n, count_if(_rescued_data IS NOT NULL) AS rescued FROM bronze_crm_solicitations GROUP BY _source_file)
SELECT
  (SELECT count(*) FROM f) AS solicitation_files,
  (SELECT min(n) FROM f) AS min_rows_per_file,
  (SELECT sum(rescued) FROM f) + (SELECT count_if(_rescued_data IS NOT NULL) FROM bronze_ecif_customers) AS rescued_rows,
  (SELECT round(100.0 * count_if(quarantine_reason = 'crm_key_not_in_xref') / count(*), 2) FROM solicitations_checked) AS unmatched_pct;

CREATE OR REFRESH MATERIALIZED VIEW silver_macro_monthly
COMMENT 'One row per metro area per month: South region CPI, Lower Atlantic gasoline and metro house price index; October 2025 CPI (not published) interpolated and flagged'
AS
WITH raw AS (
  SELECT area, series, CAST(month AS DATE) AS month, CAST(value AS DOUBLE) AS value FROM bronze_macro_prices
),
months AS (SELECT explode(sequence(DATE'2019-01-01', DATE'2026-10-01', INTERVAL 1 MONTH)) AS month),
cpi_series AS (SELECT DISTINCT series FROM raw WHERE area = 'South region'),
cpi_grid AS (
  SELECT m.month, s.series, r.value
  FROM months m CROSS JOIN cpi_series s
  LEFT JOIN raw r ON r.area = 'South region' AND r.series = s.series AND r.month = m.month
),
cpi_filled AS (
  SELECT month, series, value IS NULL AS interpolated,
    coalesce(value, (lag(value) OVER w + lead(value) OVER w) / 2) AS value
  FROM cpi_grid WINDOW w AS (PARTITION BY series ORDER BY month)
),
cpi AS (
  SELECT month,
    max(CASE WHEN series = 'all_items' THEN value END) AS cpi_all_items,
    max(CASE WHEN series = 'food_at_home' THEN value END) AS cpi_food_at_home,
    max(CASE WHEN series = 'food_away_from_home' THEN value END) AS cpi_food_away,
    max(CASE WHEN series = 'gasoline' THEN value END) AS cpi_gasoline,
    max(CASE WHEN series = 'new_vehicles' THEN value END) AS cpi_new_vehicles,
    max(CASE WHEN series = 'used_vehicles' THEN value END) AS cpi_used_vehicles,
    max(CASE WHEN series = 'shelter' THEN value END) AS cpi_shelter,
    max(CASE WHEN series = 'household_energy' THEN value END) AS cpi_household_energy,
    max(CASE WHEN series = 'recreation' THEN value END) AS cpi_recreation,
    max(CASE WHEN series = 'apparel' THEN value END) AS cpi_apparel,
    max(CASE WHEN series = 'medical_care' THEN value END) AS cpi_medical,
    bool_or(interpolated) AS cpi_interpolated
  FROM cpi_filled GROUP BY month
),
gas AS (SELECT month, value AS gasoline_usd_per_gallon FROM raw WHERE series = 'gasoline_usd_per_gallon'),
metros AS (SELECT DISTINCT area AS metro_area FROM raw WHERE series = 'house_price_index'),
hpi AS (  -- quarterly index carried forward to each month of the quarter
  SELECT mt.metro_area, m.month,
    last_value(r.value, true) OVER (PARTITION BY mt.metro_area ORDER BY m.month ROWS UNBOUNDED PRECEDING) AS house_price_index
  FROM metros mt CROSS JOIN months m
  LEFT JOIN raw r ON r.series = 'house_price_index' AND r.area = mt.metro_area AND r.month = m.month
),
j AS (SELECT h.metro_area, h.month, h.house_price_index, c.*  EXCEPT (month), g.gasoline_usd_per_gallon
      FROM hpi h JOIN cpi c ON c.month = h.month LEFT JOIN gas g ON g.month = h.month)
SELECT *,
  cpi_food_at_home / lag(cpi_food_at_home, 3) OVER w - 1 AS food_at_home_3m_change,
  cpi_gasoline / lag(cpi_gasoline, 3) OVER w - 1 AS gasoline_3m_change,
  cpi_all_items / lag(cpi_all_items, 12) OVER w - 1 AS cpi_all_items_yoy,
  cpi_used_vehicles / lag(cpi_used_vehicles, 12) OVER w - 1 AS used_vehicles_yoy,
  cpi_new_vehicles / lag(cpi_new_vehicles, 12) OVER w - 1 AS new_vehicles_yoy,
  house_price_index / lag(house_price_index, 12) OVER w - 1 AS house_price_yoy
FROM j WINDOW w AS (PARTITION BY metro_area ORDER BY month);
