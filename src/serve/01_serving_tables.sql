-- Serving copies for Lakebase sync (runs after explanations). Unity Catalog cannot sync tables with
-- row filters or masks, so these are owner-only copies: no persona is granted them in UC, and access
-- in Lakebase is enforced again by Postgres views and row-level security (src/serve/02_postgres_setup.sql).
-- No protected attributes are copied at customer level. CREATE OR REPLACE keeps reruns idempotent.

-- App roster: which campaign team members (app users) review which regions. Separate from
-- cards_entitlements so app access never changes Lakehouse access.
CREATE TABLE IF NOT EXISTS c360_bank.cards.cards_campaign_roster (
  reviewer_principal STRING NOT NULL COMMENT 'App user identity (email) as the Databricks App forwards it',
  regions ARRAY<STRING> NOT NULL COMMENT 'Campaign regions this reviewer works in the app',
  updated_at TIMESTAMP COMMENT 'When the assignment was last set'
)
COMMENT 'Campaign team region assignments used by Postgres row-level security in the app';

-- Demo assignment: the person deploying the build reviews the Triangle and Triad regions.
MERGE INTO c360_bank.cards.cards_campaign_roster t
USING (SELECT current_user() AS reviewer_principal) s ON t.reviewer_principal = s.reviewer_principal
WHEN MATCHED THEN UPDATE SET regions = ARRAY('Triangle', 'Triad'), updated_at = current_timestamp()
WHEN NOT MATCHED THEN INSERT (reviewer_principal, regions, updated_at) VALUES (s.reviewer_principal, ARRAY('Triangle', 'Triad'), current_timestamp());

CREATE OR REPLACE TABLE c360_bank.cards.serving_target_list
COMMENT 'Owner-only serving copy of the top 20% targets per tier for the next campaign, for Lakebase sync (access enforced in Postgres)'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS SELECT s.target_id, s.customer_id, s.campaign_region, s.city, s.market_type, s.mass_affluent, s.card_product, s.offer_code,
          c.offer_description, CAST(r.annual_fee AS INT) AS annual_fee, CAST(s.score AS DOUBLE) AS score, s.rank_in_tier, s.tier_size,
          s.reason_1, s.reason_2, s.reason_3, s.explanation, s.model_version, s.scored_at
   FROM c360_bank.cards.gold_target_scores s
   JOIN c360_bank.cards.silver_campaigns c ON c.offer_code = s.offer_code
   JOIN c360_bank.cards.silver_card_rules r ON r.card_product = s.card_product
   WHERE s.top20;

CREATE OR REPLACE TABLE c360_bank.cards.serving_campaign_roster
COMMENT 'Owner-only serving copy of cards_campaign_roster for Lakebase sync (drives Postgres row-level security)'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS SELECT reviewer_principal, regions FROM c360_bank.cards.cards_campaign_roster;

-- Age-group mix of the selected targets versus the qualified pool, per region and tier (totals only),
-- so reviewers see the fairness monitor's age skew before approving a list.
CREATE OR REPLACE TABLE c360_bank.cards.serving_selection_mix
COMMENT 'Totals only: share of selected (top 20%) targets and of all qualified customers by age group, per campaign region and tier'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS WITH j AS (
  SELECT s.campaign_region, s.card_product, f.generation, s.top20
  FROM c360_bank.cards.gold_target_scores s JOIN c360_bank.cards.gold_next_campaign_features f ON f.target_id = s.target_id
),
g AS (SELECT campaign_region, card_product, generation, count(*) AS qualified, count_if(top20) AS selected FROM j GROUP BY ALL)
SELECT concat(campaign_region, '|', card_product, '|', generation) AS mix_id, campaign_region, card_product, generation AS age_group,
       qualified, selected,
       qualified / sum(qualified) OVER (PARTITION BY campaign_region, card_product) AS share_of_qualified,
       selected / nullif(sum(selected) OVER (PARTITION BY campaign_region, card_product), 0) AS share_of_selected,
       (selected / qualified) / nullif(max(selected / qualified) OVER (PARTITION BY campaign_region, card_product), 0) AS adverse_impact_ratio
FROM g;

CREATE OR REPLACE TABLE c360_bank.cards.serving_city_summary
COMMENT 'Totals only: new cards (accepted offers from qualified customers) and qualified targets by month, city, tier and cohort, for the app'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS SELECT concat(CAST(month AS STRING), '|', city, '|', tier, '|', generation, '|', CAST(mass_affluent AS STRING)) AS summary_id,
          month, city, market_type, tier, generation AS cohort_generation, mass_affluent,
          targeted, qualified_targeted, accepted_qualified AS new_cards, accepted_qualified
   FROM c360_bank.cards.gold_penetration_by_tier;

CREATE OR REPLACE TABLE c360_bank.cards.serving_cohort_growth
COMMENT 'Totals only: cohort growth with the above-10% flag (from gold_cohort_growth), for the app'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS SELECT concat(generation, '|', market_type, '|', CAST(mass_affluent AS STRING), '|', tier) AS cohort_id, *
   FROM c360_bank.cards.gold_cohort_growth;

ALTER TABLE c360_bank.cards.serving_target_list SET TAGS ('cards_sensitivity' = 'serving_copy_owner_only');
ALTER TABLE c360_bank.cards.serving_campaign_roster SET TAGS ('cards_sensitivity' = 'access_control');

-- Review outcomes for the CDO and Genie (totals only). target_reviews carries the region row filter,
-- so totals are kept in their own table (rewritten by reviews_to_uc.py) and exposed through a gated view.
CREATE TABLE IF NOT EXISTS c360_bank.cards.target_review_totals (
  campaign_region STRING COMMENT 'Campaign region', tier STRING COMMENT 'Card tier', decision STRING COMMENT 'accept or exclude',
  reviews BIGINT COMMENT 'Number of review decisions', last_review_at TIMESTAMP COMMENT 'Most recent decision'
) COMMENT 'Totals of campaign team review decisions, rewritten nightly from target_reviews';

CREATE OR REPLACE VIEW c360_bank.cards.v_review_summary
COMMENT 'Campaign team review decisions on next campaign targets by region, tier and decision (totals only); data owners, D&A analysts and the CDO'
AS SELECT * FROM c360_bank.cards.target_review_totals
WHERE c360_bank.cards.cards_current_persona() IN ('data_owner', 'dna_analyst', 'cdo');
