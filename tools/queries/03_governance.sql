-- title: Policy functions
SELECT routine_name, routine_definition IS NOT NULL AS has_body, comment FROM c360_bank.information_schema.routines WHERE routine_schema = 'cards' ORDER BY 1;
-- title: Column masks
SELECT table_name, column_name, mask_name FROM c360_bank.information_schema.column_masks WHERE table_schema = 'cards' ORDER BY 1, 2;
-- title: Row filters
SELECT table_name, filter_name, target_columns FROM c360_bank.information_schema.row_filters WHERE table_schema = 'cards' ORDER BY 1;
-- title: Column tags (PII and protected attributes)
SELECT table_name, column_name, tag_name, tag_value FROM c360_bank.information_schema.column_tags WHERE schema_name = 'cards' ORDER BY 1, 2;
-- title: Table tags
SELECT table_name, tag_name, tag_value FROM c360_bank.information_schema.table_tags WHERE schema_name = 'cards' ORDER BY 1;
-- title: Fair lending: columns of the model input view (no age, generation, marital status, gender, date of birth)
SELECT ordinal_position, column_name, data_type FROM c360_bank.information_schema.columns WHERE table_schema = 'cards' AND table_name = 'v_model_features' ORDER BY 1;
-- title: Protected columns present in the model view (expected 0)
SELECT count(*) AS protected_columns FROM c360_bank.information_schema.columns WHERE table_schema = 'cards' AND table_name = 'v_model_features'
  AND column_name IN ('age', 'age_at_solicitation', 'generation', 'marital_status', 'gender', 'date_of_birth');
-- title: Entitlements (data owner identity redacted by the evidence collector)
SELECT persona, regions FROM c360_bank.cards.cards_entitlements ORDER BY 1;
