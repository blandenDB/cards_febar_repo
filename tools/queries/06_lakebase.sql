-- title: Serving copies in Unity Catalog (sources of the synced tables)
SELECT 'serving_target_list' t, count(*) n FROM c360_bank.cards.serving_target_list UNION ALL
SELECT 'serving_campaign_roster', count(*) FROM c360_bank.cards.serving_campaign_roster UNION ALL
SELECT 'serving_selection_mix', count(*) FROM c360_bank.cards.serving_selection_mix UNION ALL
SELECT 'serving_city_summary', count(*) FROM c360_bank.cards.serving_city_summary UNION ALL
SELECT 'serving_cohort_growth', count(*) FROM c360_bank.cards.serving_cohort_growth;
-- title: Target list by region and tier (what the campaign team reviews)
SELECT campaign_region, card_product, count(*) targets, count(explanation) with_explanation FROM c360_bank.cards.serving_target_list GROUP BY 1, 2 ORDER BY 1, 2;
-- title: Age-group selection mix shown on the review screen (Triangle, Gold)
SELECT age_group, qualified, selected, round(share_of_qualified, 3) share_of_qualified, round(share_of_selected, 3) share_of_selected, round(adverse_impact_ratio, 3) adverse_impact_ratio
FROM c360_bank.cards.serving_selection_mix WHERE campaign_region = 'Triangle' AND card_product = 'Gold' ORDER BY age_group;
