-- Access policies for c360_bank.cards (runs before the pipeline, which attaches them).
-- Personas come from an entitlement table, because Unity Catalog accepts only
-- account-level groups and this sandbox workspace cannot create them.
--   data_owner     everything
--   dna_analyst    all customer rows; address and SSN tokens masked; protected
--                  attributes only through the fairness view
--   campaign_team  target lists for their assigned campaign regions only; no protected attributes
--   cdo            totals by city, tier and cohort only; no customer-level rows
-- Safe to rerun.

CREATE TABLE IF NOT EXISTS c360_bank.cards.cards_entitlements (
  principal  STRING NOT NULL COMMENT 'User email or service principal application ID, exactly as current_user() returns it',
  persona    STRING NOT NULL COMMENT 'data_owner, dna_analyst, campaign_team or cdo',
  regions    ARRAY<STRING>   COMMENT 'Campaign regions a campaign_team member may see; NULL for other personas',
  updated_at TIMESTAMP       COMMENT 'When this entitlement was last set'
)
COMMENT 'Who may see what in the cards tables. Read by the mask, row filter and view functions.';

MERGE INTO c360_bank.cards.cards_entitlements t
USING (SELECT current_user() AS principal) s ON t.principal = s.principal
WHEN MATCHED THEN UPDATE SET persona = 'data_owner', regions = NULL, updated_at = current_timestamp()
WHEN NOT MATCHED THEN INSERT (principal, persona, regions, updated_at) VALUES (s.principal, 'data_owner', NULL, current_timestamp());

CREATE OR REPLACE FUNCTION c360_bank.cards.cards_current_persona()
RETURNS STRING
COMMENT 'Persona of the calling principal from cards_entitlements; NULL if not entitled'
RETURN (SELECT max(persona) FROM c360_bank.cards.cards_entitlements WHERE principal = current_user());

CREATE OR REPLACE FUNCTION c360_bank.cards.cards_mask_identifier(value STRING)
RETURNS STRING
COMMENT 'Column mask for address and SSN tokens: data owners see the value; everyone else sees ***MASKED***'
RETURN CASE WHEN c360_bank.cards.cards_current_persona() = 'data_owner' THEN value ELSE '***MASKED***' END;

CREATE OR REPLACE FUNCTION c360_bank.cards.cards_region_filter(campaign_region STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: data owners and D&A analysts see all rows; the campaign team sees its assigned regions; the CDO and anyone else see no customer-level rows'
RETURN CASE c360_bank.cards.cards_current_persona()
  WHEN 'data_owner' THEN TRUE
  WHEN 'dna_analyst' THEN TRUE
  WHEN 'campaign_team' THEN EXISTS (
    SELECT 1 FROM c360_bank.cards.cards_entitlements
    WHERE principal = current_user() AND array_contains(regions, campaign_region))
  ELSE FALSE
END;

CREATE OR REPLACE FUNCTION c360_bank.cards.cards_is_analyst()
RETURNS BOOLEAN
COMMENT 'TRUE for data owners and D&A analysts (used by the model and fairness views)'
RETURN c360_bank.cards.cards_current_persona() IN ('data_owner', 'dna_analyst');
