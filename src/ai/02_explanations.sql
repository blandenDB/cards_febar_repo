-- Plain-English explanations for the top targets of the next campaign, written by a foundation
-- model from the listed facts only (offer, card and the model's top three reasons).
-- Scope: top 20% of each tier, first 1,000 per tier. Idempotent: the table is rebuilt each run and
-- the explanation column of gold_target_scores is refreshed from it.

CREATE OR REPLACE TABLE c360_bank.cards.gold_target_explanations
COMMENT 'Explanation for each top target of the next campaign, written by databricks-claude-haiku-5-5 from the facts column only. Row filter by campaign region.'
AS
WITH t AS (
  SELECT s.target_id, s.campaign_region, s.card_product, s.offer_code, c.offer_description, r.annual_fee,
         concat_ws('; ', s.reason_1, s.reason_2, s.reason_3) AS facts
  FROM c360_bank.cards.gold_target_scores s
  JOIN c360_bank.cards.silver_campaigns c ON c.offer_code = s.offer_code
  JOIN c360_bank.cards.silver_card_rules r ON r.card_product = s.card_product
  WHERE s.top20 AND s.rank_in_tier <= 1000
),
prompts AS (
  SELECT *, concat(
    'You are briefing the credit card campaign team at a regional bank, who review each target before an offer is sent. ',
    'Offer: ', card_product, ' card (annual fee $', annual_fee, '), ', offer_description, '. ',
    'Facts about the customer (use only these; do not invent rates, amounts, promotions or other details): ', facts, '. ',
    'Reply in exactly this format and nothing else:\n',
    'Why: <one or two sentences explaining why this offer fits the customer; refer to the person as "the customer">\n',
    'Rules: Do not mention or hint at age, generation, life stage, marital status, family, children or gender. ',
    'Do not mention models, scores or probabilities. Do not say the customer is approved or creditworthy. ',
    'Do not infer anything beyond the facts: nothing about ability to pay, affordability, absorbing the fee, spending habits, ',
    'existing balances or debts, financial needs or goals, or what the offer would help the customer do. ',
    'State the offer and the facts, and connect them only with words like "with" or "and". ',
    'If a fact is about prices in the area, present it only as context (for example "prices have risen in the area"), ',
    'never as the reason the customer will accept. If the facts are few, write a shorter reason that only restates them.') AS prompt
  FROM t
),
gen AS (
  SELECT *, ai_query('databricks-claude-haiku-5-5', prompt, modelParameters => named_struct('max_tokens', 1000), failOnError => false) AS response
  FROM prompts
)
SELECT target_id, campaign_region, card_product, offer_code, facts,
       NULLIF(TRIM(response.result), '') AS explanation, response.errorMessage AS generation_error,
       'databricks-claude-haiku-5-5' AS llm_endpoint, current_timestamp() AS generated_at
FROM gen;

ALTER TABLE c360_bank.cards.gold_target_explanations SET ROW FILTER c360_bank.cards.cards_region_filter ON (campaign_region);
ALTER TABLE c360_bank.cards.gold_target_explanations ALTER COLUMN facts COMMENT 'Facts given to the model; the explanation must not go beyond these';

MERGE INTO c360_bank.cards.gold_target_scores s
USING c360_bank.cards.gold_target_explanations e ON s.target_id = e.target_id
WHEN MATCHED THEN UPDATE SET s.explanation = e.explanation;

-- Fail the task if more than 5% of generations errored, so a silent failure cannot pass as success.
SELECT IF(sum(IF(explanation IS NULL, 1, 0)) > 0.05 * count(*),
          raise_error(concat('Explanation generation failed for ', sum(IF(explanation IS NULL, 1, 0)), ' of ', count(*), ' rows')),
          concat('ok: ', count(explanation), ' of ', count(*), ' explanations generated')) AS generation_check
FROM c360_bank.cards.gold_target_explanations;
