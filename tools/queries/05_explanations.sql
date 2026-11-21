-- title: Explanation generation
SELECT count(*) AS targets_in_scope, count(explanation) AS generated, count(generation_error) AS errors, max(llm_endpoint) AS llm_endpoint, max(generated_at) AS generated_at FROM c360_bank.cards.gold_target_explanations;
-- title: Sample explanations (synthetic customers)
SELECT target_id, card_product, facts, explanation FROM c360_bank.cards.gold_target_explanations ORDER BY xxhash64(target_id) LIMIT 6;
-- title: Judge runs (all kept)
SELECT judged_at, sample, judge, grounded, no_protected_attributes, relevant, all_met, mlflow_run_id FROM c360_bank.cards.cards_judge_results ORDER BY judged_at;
-- title: Retry results
SELECT count(*) n, count(explanation) generated, count_if(generation_error = 'retried once') retried_once, count_if(generation_error = 'incomplete after retry') left_blank, count_if(explanation NOT RLIKE '[.!?)]$') still_incomplete FROM c360_bank.cards.gold_target_explanations;
SELECT count(*) AS scores_with_explanation FROM c360_bank.cards.gold_target_scores WHERE explanation IS NOT NULL;
