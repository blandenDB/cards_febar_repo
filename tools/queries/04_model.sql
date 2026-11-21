-- title: Target list for the next campaign (gold_target_scores)
SELECT card_product, offer_code, count(*) AS targets, count_if(top20) AS top20_targets, round(avg(score), 4) AS avg_score, round(avg(CASE WHEN top20 THEN score END), 4) AS avg_score_top20, max(model_version) AS model_version
FROM c360_bank.cards.gold_target_scores GROUP BY 1, 2 ORDER BY 1, 2;
-- title: Top reason mix (reason_1_code)
SELECT reason_1_code, count(*) AS targets FROM c360_bank.cards.gold_target_scores GROUP BY 1 ORDER BY 2 DESC;
-- title: Sample top targets (synthetic customers)
SELECT target_id, card_product, offer_code, city, round(score, 4) score, rank_in_tier, reason_1, reason_2, reason_3 FROM c360_bank.cards.gold_target_scores WHERE rank_in_tier <= 2 ORDER BY card_product, offer_code, rank_in_tier;
-- title: Row filter attached
SELECT table_name, filter_name, target_columns FROM c360_bank.information_schema.row_filters WHERE table_schema = 'cards' AND table_name = 'gold_target_scores';
