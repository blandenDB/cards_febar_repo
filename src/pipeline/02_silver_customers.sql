-- Silver customers, accounts and balances (customer system, ecif).
-- Cleanup: city spelling, Chapel Hill payment fill, derived generation, market type and
-- mass affluent flag. Customers with an impossible credit score go to quarantine.

CREATE OR REFRESH MATERIALIZED VIEW silver_city_dim
COMMENT 'City reference: market type, cost-of-living band and FHFA metro area'
AS SELECT * FROM VALUES
  ('Raleigh', 'urban_core', false, 'Raleigh-Cary'),
  ('Durham', 'urban_core', false, 'Durham-Chapel Hill'),
  ('Charlotte', 'urban_core', false, 'Charlotte-Concord-Gastonia'),
  ('Columbia', 'urban_core', true, 'Columbia'),
  ('Wilmington', 'urban_core', false, 'Wilmington'),
  ('Charleston', 'urban_core', false, 'Charleston-North Charleston'),
  ('Cary', 'suburban', false, 'Raleigh-Cary'),
  ('Apex', 'suburban', false, 'Raleigh-Cary'),
  ('Holly Springs', 'suburban', false, 'Raleigh-Cary'),
  ('Chapel Hill', 'suburban', false, 'Durham-Chapel Hill'),
  ('Greensboro', 'suburban_style_metro', true, 'Greensboro-High Point'),
  ('Winston-Salem', 'suburban_style_metro', true, 'Winston-Salem'),
  ('Mebane', 'exurban', true, 'Burlington'),
  ('Burlington', 'exurban', true, 'Burlington'),
  ('Salisbury', 'exurban', true, 'Charlotte-Concord-Gastonia'),
  ('Greenville', 'fast_growing_mid_size', true, 'Greenville-Anderson'),
  ('Florence', 'highway_corridor', true, 'Florence'),
  ('Myrtle Beach', 'coastal_resort', false, 'Myrtle Beach-Conway-North Myrtle Beach'),
  ('Hilton Head Island', 'coastal_resort', false, 'Hilton Head Island-Bluffton-Port Royal'),
  ('Pawleys Island', 'coastal_resort', false, 'Myrtle Beach-Conway-North Myrtle Beach'),
  ('Asheville', 'mountain_tourism', false, 'Asheville')
AS t(city, market_type, low_cost_market, metro_area);

CREATE TEMPORARY VIEW customers_checked AS
WITH typed AS (
  SELECT DISTINCT
    customer_id,
    CAST(date_of_birth AS DATE) AS date_of_birth,
    CASE WHEN lower(city) = 'winston-salem' THEN 'Winston-Salem' ELSE city END AS city,
    city AS city_as_received,
    state, LPAD(zip_code, 5, '0') AS zip_code, gender, marital_status, employment_status, own_rent_home,
    CAST(residency_duration_yrs AS INT) AS residency_duration_yrs, CAST(residence_year AS INT) AS residence_year,
    CAST(annual_income AS BIGINT) AS annual_income,
    CAST(monthly_household_pmt AS DECIMAL(12,2)) AS monthly_household_pmt_raw,
    CAST(credit_score AS INT) AS credit_score,
    CAST(customer_since AS DATE) AS customer_since,
    preferred_channel, CAST(consent_email AS BOOLEAN) AS consent_email, CAST(consent_sms AS BOOLEAN) AS consent_sms,
    CAST(consent_push AS BOOLEAN) AS consent_push, record_origin, origin_group, address_token, ssn_last4_token
  FROM bronze_ecif_customers
),
raleigh AS (  -- Raleigh median payment by employment status, used to fill Chapel Hill
  SELECT employment_status, percentile_approx(monthly_household_pmt_raw, 0.5) AS raleigh_median
  FROM typed WHERE city = 'Raleigh' AND monthly_household_pmt_raw > 0 GROUP BY employment_status
)
SELECT
  t.* EXCEPT (monthly_household_pmt_raw),
  CASE WHEN t.city = 'Chapel Hill' AND t.monthly_household_pmt_raw = 0
       THEN CAST(r.raleigh_median * (0.8 + 0.4 * (abs(xxhash64(t.customer_id, 'pmt')) % 10000) / 10000.0) AS DECIMAL(12,2))
       ELSE t.monthly_household_pmt_raw END AS monthly_household_pmt,
  (t.city = 'Chapel Hill' AND t.monthly_household_pmt_raw = 0) AS payment_filled,
  floor(datediff(DATE'2026-11-01', t.date_of_birth) / 365) AS age,
  CASE WHEN floor(datediff(DATE'2026-11-01', t.date_of_birth) / 365) <= 28 THEN 'gen_z'
       WHEN floor(datediff(DATE'2026-11-01', t.date_of_birth) / 365) <= 45 THEN 'millennial'
       WHEN floor(datediff(DATE'2026-11-01', t.date_of_birth) / 365) <= 58 THEN 'gen_x'
       WHEN floor(datediff(DATE'2026-11-01', t.date_of_birth) / 365) <= 68 THEN 'boomer'
       ELSE 'silent' END AS generation,
  d.market_type, d.low_cost_market, d.metro_area,
  CASE WHEN d.low_cost_market THEN t.annual_income BETWEEN 50000 AND 150000
       ELSE t.annual_income BETWEEN 75000 AND 250000 END AS mass_affluent,
  d.market_type IN ('urban_core', 'suburban', 'suburban_style_metro') AS urban_suburban,
  CASE WHEN t.credit_score NOT BETWEEN 300 AND 850 THEN 'credit_score_out_of_range' END AS quarantine_reason
FROM typed t
LEFT JOIN raleigh r ON r.employment_status = t.employment_status
LEFT JOIN silver_city_dim d ON d.city = t.city;

CREATE OR REFRESH MATERIALIZED VIEW silver_customers (
  CONSTRAINT employed_income_plausible EXPECT (NOT (employment_status = 'employed' AND annual_income < 10000)),
  CONSTRAINT payment_present EXPECT (monthly_household_pmt IS NOT NULL),
  CONSTRAINT known_city EXPECT (market_type IS NOT NULL)
)
COMMENT 'One row per customer: cleaned and conformed ecif profile with derived generation, market type and mass affluent flag'
AS SELECT * EXCEPT (quarantine_reason) FROM customers_checked WHERE quarantine_reason IS NULL;

CREATE OR REFRESH MATERIALIZED VIEW silver_customers_quarantine
COMMENT 'Customers held aside by a quality rule, with the rule that failed'
AS SELECT customer_id, city, credit_score, record_origin, quarantine_reason FROM customers_checked WHERE quarantine_reason IS NOT NULL;

CREATE OR REFRESH MATERIALIZED VIEW silver_accounts
COMMENT 'One row per deposit account (checking, savings, money market)'
AS SELECT DISTINCT account_id, customer_id, product, CAST(open_date AS DATE) AS open_date, status
FROM bronze_ecif_accounts;

CREATE OR REFRESH MATERIALIZED VIEW silver_balances_monthly
COMMENT 'One row per customer per month: month-end balances by product, total, deposits and primary deposit type'
AS SELECT DISTINCT
  customer_id,
  CAST(month_end AS DATE) AS month_end,
  trunc(CAST(month_end AS DATE), 'MM') AS month,
  CAST(checking_balance AS DECIMAL(14,2)) AS checking_balance,
  CAST(savings_balance AS DECIMAL(14,2)) AS savings_balance,
  CAST(money_market_balance AS DECIMAL(14,2)) AS money_market_balance,
  CAST(checking_balance AS DECIMAL(14,2)) + CAST(savings_balance AS DECIMAL(14,2)) + CAST(money_market_balance AS DECIMAL(14,2)) AS total_balance,
  CAST(monthly_deposits AS DECIMAL(14,2)) AS monthly_deposits,
  primary_deposit_type
FROM bronze_ecif_balances;
