-- Lakebase (Postgres) setup for the campaign review app. Safe to rerun.
--
-- Identity: the app sets the signed-in reviewer for each transaction with
--   SELECT set_config('app.reviewer', '<email from the Databricks Apps forwarded header>', true)
-- Synced tables (schema cards, pg_*) are owned by the sync, so access to them goes through
-- security_barrier views that keep only the reviewer's regions. target_reviews is owned by us and
-- uses Postgres row-level security. The app's role is granted only the app schema.

CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE VIEW app.my_regions WITH (security_barrier = true) AS
SELECT jsonb_array_elements_text(r.regions) AS region
FROM cards.pg_campaign_roster r
WHERE r.reviewer_principal = current_setting('app.reviewer', true);

CREATE OR REPLACE VIEW app.targets WITH (security_barrier = true) AS
SELECT t.* FROM cards.pg_target_list t
WHERE t.campaign_region IN (SELECT region FROM app.my_regions);

CREATE OR REPLACE VIEW app.selection_mix WITH (security_barrier = true) AS
SELECT m.* FROM cards.pg_selection_mix m
WHERE m.campaign_region IN (SELECT region FROM app.my_regions);

-- Totals only (no customer rows): visible to any signed-in reviewer on the roster.
CREATE OR REPLACE VIEW app.city_summary WITH (security_barrier = true) AS
SELECT s.* FROM cards.pg_city_summary s WHERE EXISTS (SELECT 1 FROM app.my_regions);

CREATE OR REPLACE VIEW app.cohort_growth WITH (security_barrier = true) AS
SELECT g.* FROM cards.pg_cohort_growth g WHERE EXISTS (SELECT 1 FROM app.my_regions);

CREATE TABLE IF NOT EXISTS app.target_reviews (
  review_id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  target_id          text        NOT NULL,
  campaign_region    text        NOT NULL,
  card_product       text        NOT NULL,
  offer_code         text        NOT NULL,
  decision           text        NOT NULL CHECK (decision IN ('accept', 'exclude')),
  reason             text        CHECK (char_length(reason) <= 500),
  reviewer_principal text        NOT NULL DEFAULT current_setting('app.reviewer', true),
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS target_reviews_target_idx ON app.target_reviews (target_id, created_at DESC);

ALTER TABLE app.target_reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS reviews_read_own_regions ON app.target_reviews;
CREATE POLICY reviews_read_own_regions ON app.target_reviews FOR SELECT
  USING (campaign_region IN (SELECT region FROM app.my_regions));

DROP POLICY IF EXISTS reviews_insert_own_regions ON app.target_reviews;
CREATE POLICY reviews_insert_own_regions ON app.target_reviews FOR INSERT
  WITH CHECK (campaign_region IN (SELECT region FROM app.my_regions)
              AND reviewer_principal = current_setting('app.reviewer', true)
              AND target_id IN (SELECT target_id FROM app.targets));

-- Latest decision per target, for the app.
CREATE OR REPLACE VIEW app.latest_reviews WITH (security_barrier = true) AS
SELECT DISTINCT ON (target_id) target_id, decision, reason, created_at
FROM app.target_reviews ORDER BY target_id, created_at DESC;
