-- Access policy on the ML output table (runs after train_and_score). Safe to rerun.
ALTER TABLE c360_bank.cards.gold_target_scores SET ROW FILTER c360_bank.cards.cards_region_filter ON (campaign_region);
ALTER TABLE c360_bank.cards.gold_target_scores SET TAGS ('cards_sensitivity' = 'targeting_output');
ALTER TABLE c360_bank.cards.gold_fairness_monitor SET TAGS ('cards_sensitivity' = 'fairness_monitor');
