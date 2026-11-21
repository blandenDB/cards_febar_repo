-- title: EVAL_PROTOCOL.md results (sections 6 and 7), table cards_eval_results
SELECT tier, n_test, top20_n, base_rate, model_top20_rate, baseline_top20_rate, model_no_macro_top20_rate, ratio_vs_baseline FROM c360_bank.cards.cards_eval_results ORDER BY tier;
SELECT DISTINCT pooled_model_top20_rate, pooled_baseline_top20_rate, pooled_ratio, tiers_at_or_above_baseline, auc_pooled, auc_pooled_no_macro,
  round(auc_pooled - auc_pooled_no_macro, 4) AS auc_gain_from_prices, claim_beats_vendor_style_list, claim_cost_of_living, mlflow_run_id, evaluated_at FROM c360_bank.cards.cards_eval_results;
-- title: Cohort growth claim (section 8): cohorts growing above 10% a year in both the training and test periods, at least 200 qualified solicitations each
SELECT generation, market_type, mass_affluent, tier, n_p1, n_p2, n_p3, n_p4, round(rate_p1,4) rate_p1, round(rate_p2,4) rate_p2, round(rate_p3,4) rate_p3, round(rate_p4,4) rate_p4,
  round(growth_train,3) growth_train, round(growth_test,3) growth_test FROM c360_bank.cards.gold_cohort_growth WHERE growing_above_10pct ORDER BY tier, generation, market_type;
SELECT count(*) AS cohorts, count_if(least(n_p1, n_p2, n_p3, n_p4) >= 200) AS cohorts_with_enough_volume, count_if(growing_above_10pct) AS growing_above_10pct FROM c360_bank.cards.gold_cohort_growth;
