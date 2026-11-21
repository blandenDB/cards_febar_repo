-- title: Fairness monitor (section 9): share of test-set qualified customers selected into the top 20%, by protected group
SELECT attribute, group_value, n_test_qualified, selected_top20, selection_share, adverse_impact_ratio, flag_below_0_8, evaluated_at FROM c360_bank.cards.gold_fairness_monitor ORDER BY attribute, adverse_impact_ratio;
-- title: Model input contains no protected attribute (columns of v_model_features named like a protected attribute)
SELECT count(*) AS protected_columns_in_model_input FROM c360_bank.information_schema.columns WHERE table_schema = 'cards' AND table_name = 'v_model_features'
  AND column_name IN ('age', 'age_at_solicitation', 'generation', 'marital_status', 'gender', 'date_of_birth');
