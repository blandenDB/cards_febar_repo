-- Governed views and tags for c360_bank.cards (runs after the pipeline). Safe to rerun.

-- The targeting model reads only this view: no age, generation, marital status, gender
-- or date of birth (fair lending rule, EVAL_PROTOCOL.md section 4). Analysts and owners only.
CREATE OR REPLACE VIEW c360_bank.cards.v_model_features
COMMENT 'Model input: gold_features without protected attributes (age, generation, marital status, gender) or lineage flags; data owners and D&A analysts only'
AS SELECT solicitation_id, customer_id, offer_code, card_product, sent_date, sent_month, campaign_month, qualified, accepted,
  city, state, zip_code, campaign_region, market_type, low_cost_market, urban_suburban, mass_affluent,
  annual_income, credit_score, monthly_household_pmt, own_rent_home, employment_status, residence_year, years_at_residence,
  tenure_years, preferred_channel, channel, n_accounts, has_savings, has_money_market, avg6_total_balance,
  food_at_home_3m_change, gasoline_3m_change, cpi_all_items_yoy, used_vehicles_yoy, new_vehicles_yoy,
  gasoline_usd_per_gallon, cpi_interpolated, house_price_yoy
FROM c360_bank.cards.gold_features
WHERE c360_bank.cards.cards_is_analyst();

CREATE OR REPLACE VIEW c360_bank.cards.v_next_campaign_features
COMMENT 'Next campaign scoring input: gold_next_campaign_features without protected attributes; data owners and D&A analysts only'
AS SELECT target_id, customer_id, offer_code, card_product, sent_month, campaign_month,
  city, state, zip_code, campaign_region, market_type, low_cost_market, urban_suburban, mass_affluent,
  annual_income, credit_score, monthly_household_pmt, own_rent_home, employment_status, residence_year, years_at_residence,
  tenure_years, preferred_channel, n_accounts, has_savings, has_money_market, avg6_total_balance,
  food_at_home_3m_change, gasoline_3m_change, cpi_all_items_yoy, used_vehicles_yoy, new_vehicles_yoy,
  gasoline_usd_per_gallon, cpi_interpolated, house_price_yoy
FROM c360_bank.cards.gold_next_campaign_features
WHERE c360_bank.cards.cards_is_analyst();

-- Protected attributes, for the fairness monitor only. Analysts and owners only.
CREATE OR REPLACE VIEW c360_bank.cards.v_fairness_features
COMMENT 'Protected attributes per solicitation for fairness monitoring only (never a model input); data owners and D&A analysts only'
AS SELECT solicitation_id, customer_id, card_product, offer_code, campaign_month, qualified, accepted,
  age_at_solicitation, generation, marital_status, gender
FROM c360_bank.cards.gold_features
WHERE c360_bank.cards.cards_is_analyst();

-- The CDO's view: totals only.
CREATE OR REPLACE VIEW c360_bank.cards.v_cdo_summary
COMMENT 'New cards and Card Product Penetration Rate by month, city and tier (totals only, no customer rows); data owners, D&A analysts and the CDO'
AS SELECT month, city, market_type, tier,
  sum(targeted) AS targeted, sum(qualified_targeted) AS qualified_targeted, sum(new_cards) AS new_cards,
  sum(accepted_qualified) AS accepted_qualified,
  try_divide(sum(accepted_qualified), sum(qualified_targeted)) AS penetration_rate
FROM c360_bank.cards.gold_penetration_by_tier
WHERE c360_bank.cards.cards_current_persona() IN ('data_owner', 'dna_analyst', 'cdo')
GROUP BY ALL;

CREATE OR REPLACE VIEW c360_bank.cards.v_cohort_growth
COMMENT 'Cohort acceptance growth (generation x market type x mass affluent x tier), totals only; data owners, D&A analysts and the CDO'
AS SELECT * FROM c360_bank.cards.gold_cohort_growth
WHERE c360_bank.cards.cards_current_persona() IN ('data_owner', 'dna_analyst', 'cdo');

-- Tags. The shared metastore governs `pii` (allowed: ssn, address) and `data_classification`
-- (allowed: u-nnpi, cui, pii); protected attributes use our own key `cards_protected_attribute`.
ALTER MATERIALIZED VIEW c360_bank.cards.silver_customer_identifiers SET TAGS ('data_classification' = 'pii');
ALTER MATERIALIZED VIEW c360_bank.cards.silver_customer_identifiers ALTER COLUMN address_token SET TAGS ('pii' = 'address');
ALTER MATERIALIZED VIEW c360_bank.cards.silver_customer_identifiers ALTER COLUMN ssn_last4_token SET TAGS ('pii' = 'ssn');
ALTER MATERIALIZED VIEW c360_bank.cards.silver_customers ALTER COLUMN date_of_birth SET TAGS ('cards_protected_attribute' = 'age');
ALTER MATERIALIZED VIEW c360_bank.cards.silver_customers ALTER COLUMN age SET TAGS ('cards_protected_attribute' = 'age');
ALTER MATERIALIZED VIEW c360_bank.cards.silver_customers ALTER COLUMN generation SET TAGS ('cards_protected_attribute' = 'age');
ALTER MATERIALIZED VIEW c360_bank.cards.silver_customers ALTER COLUMN marital_status SET TAGS ('cards_protected_attribute' = 'marital_status');
ALTER MATERIALIZED VIEW c360_bank.cards.silver_customers ALTER COLUMN gender SET TAGS ('cards_protected_attribute' = 'gender');
ALTER MATERIALIZED VIEW c360_bank.cards.gold_features ALTER COLUMN age_at_solicitation SET TAGS ('cards_protected_attribute' = 'age');
ALTER MATERIALIZED VIEW c360_bank.cards.gold_features ALTER COLUMN generation SET TAGS ('cards_protected_attribute' = 'age');
ALTER MATERIALIZED VIEW c360_bank.cards.gold_features ALTER COLUMN marital_status SET TAGS ('cards_protected_attribute' = 'marital_status');
ALTER MATERIALIZED VIEW c360_bank.cards.gold_features ALTER COLUMN gender SET TAGS ('cards_protected_attribute' = 'gender');
ALTER MATERIALIZED VIEW c360_bank.cards.gold_next_campaign_features ALTER COLUMN age_at_solicitation SET TAGS ('cards_protected_attribute' = 'age');
ALTER MATERIALIZED VIEW c360_bank.cards.gold_next_campaign_features ALTER COLUMN generation SET TAGS ('cards_protected_attribute' = 'age');
ALTER MATERIALIZED VIEW c360_bank.cards.gold_next_campaign_features ALTER COLUMN marital_status SET TAGS ('cards_protected_attribute' = 'marital_status');
ALTER MATERIALIZED VIEW c360_bank.cards.gold_next_campaign_features ALTER COLUMN gender SET TAGS ('cards_protected_attribute' = 'gender');
ALTER TABLE c360_bank.cards.cards_entitlements SET TAGS ('cards_sensitivity' = 'access_control');
