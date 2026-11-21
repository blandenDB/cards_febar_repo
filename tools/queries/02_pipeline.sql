-- title: Row counts by layer
SELECT 'bronze_ecif_customers' t, count(*) n FROM c360_bank.cards.bronze_ecif_customers UNION ALL
SELECT 'silver_customers', count(*) FROM c360_bank.cards.silver_customers UNION ALL
SELECT 'silver_customers_quarantine', count(*) FROM c360_bank.cards.silver_customers_quarantine UNION ALL
SELECT 'bronze_ecif_accounts', count(*) FROM c360_bank.cards.bronze_ecif_accounts UNION ALL
SELECT 'silver_accounts', count(*) FROM c360_bank.cards.silver_accounts UNION ALL
SELECT 'bronze_ecif_balances', count(*) FROM c360_bank.cards.bronze_ecif_balances UNION ALL
SELECT 'silver_balances_monthly', count(*) FROM c360_bank.cards.silver_balances_monthly UNION ALL
SELECT 'bronze_crm_solicitations', count(*) FROM c360_bank.cards.bronze_crm_solicitations UNION ALL
SELECT 'silver_solicitations', count(*) FROM c360_bank.cards.silver_solicitations UNION ALL
SELECT 'silver_solicitations_quarantine', count(*) FROM c360_bank.cards.silver_solicitations_quarantine UNION ALL
SELECT 'bronze_crm_xref', count(*) FROM c360_bank.cards.bronze_crm_xref UNION ALL
SELECT 'silver_macro_monthly', count(*) FROM c360_bank.cards.silver_macro_monthly UNION ALL
SELECT 'gold_features', count(*) FROM c360_bank.cards.gold_features UNION ALL
SELECT 'gold_penetration_by_tier', count(*) FROM c360_bank.cards.gold_penetration_by_tier UNION ALL
SELECT 'gold_cohort_growth', count(*) FROM c360_bank.cards.gold_cohort_growth;
-- title: Solicitation files landed (resent June 2025 file present; March 2026 not yet arrived)
SELECT regexp_extract(_source_file, '([^/]+)$', 1) file, count(*) rows FROM c360_bank.cards.bronze_crm_solicitations GROUP BY 1 ORDER BY 1;
-- title: Duplicates removed from the resent file
SELECT count(*) solicitations_received_twice, sum(copies_received) - count(*) duplicate_rows_dropped FROM c360_bank.cards.silver_solicitations WHERE copies_received > 1;
-- title: Quarantine by rule
SELECT 'customers' entity, quarantine_reason, count(*) n FROM c360_bank.cards.silver_customers_quarantine GROUP BY 2 UNION ALL
SELECT 'solicitations', quarantine_reason, count(*) FROM c360_bank.cards.silver_solicitations_quarantine GROUP BY 2 ORDER BY 1, 2;
-- title: Load checks (fail-the-update rules)
SELECT * FROM c360_bank.cards.silver_load_checks;
-- title: Cleanup: city spelling and Chapel Hill payment fill
SELECT city_as_received, city, count(*) n FROM c360_bank.cards.silver_customers WHERE lower(city) LIKE 'winston%' GROUP BY ALL;
SELECT employment_status, count(*) filled, min(monthly_household_pmt) low, percentile_approx(monthly_household_pmt, 0.5) median, max(monthly_household_pmt) high
FROM c360_bank.cards.silver_customers WHERE payment_filled GROUP BY 1 ORDER BY 1;
-- title: Customers by record origin
SELECT record_origin, count(*) n FROM c360_bank.cards.silver_customers GROUP BY 1 ORDER BY 1;
-- title: Public price data: interpolated month and coverage
SELECT min(month) first_month, max(month) last_month, count(DISTINCT metro_area) metros, count_if(cpi_interpolated) / count(DISTINCT metro_area) interpolated_months,
  max(CASE WHEN cpi_interpolated THEN month END) interpolated_month FROM c360_bank.cards.silver_macro_monthly;
-- title: Qualified solicitations and acceptance (metric inputs)
SELECT count(*) solicitations, count_if(qualified) qualified, round(avg(CAST(accepted AS INT)), 4) acceptance_all,
  round(avg(CASE WHEN qualified THEN CAST(accepted AS INT) END), 4) penetration_rate_qualified FROM c360_bank.cards.silver_solicitations;
-- title: Card Product Penetration Rate by Tier (accepted / qualified targeted)
SELECT tier, sum(qualified_targeted) qualified_targeted, sum(accepted_qualified) accepted, round(sum(accepted_qualified) / sum(qualified_targeted), 4) penetration_rate
FROM c360_bank.cards.gold_penetration_by_tier GROUP BY 1 ORDER BY 1;
-- title: Expectation results from the pipeline event log (latest update)
WITH u AS (SELECT origin.update_id FROM c360_bank.cards.cards_pipeline_event_log WHERE event_type = 'create_update' ORDER BY timestamp DESC LIMIT 1),
e AS (SELECT origin.flow_name flow, explode(from_json(details:flow_progress:data_quality:expectations, 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) x
      FROM c360_bank.cards.cards_pipeline_event_log WHERE event_type = 'flow_progress' AND origin.update_id = (SELECT update_id FROM u) AND details:flow_progress:data_quality IS NOT NULL)
SELECT x.dataset, x.name expectation, sum(x.passed_records) passed, sum(x.failed_records) failed FROM e GROUP BY ALL ORDER BY 1, 2;
-- title: Reconciliation with generator ground truth (seed volume; never read by the pipeline)
WITH t AS (SELECT * FROM read_files('/Volumes/c360_bank/cards/seed/ground_truth/customer_truth.csv', format => 'csv', header => true))
SELECT
  (SELECT count(*) FROM t WHERE xref_unmapped = 'True') planted_unmapped_xref,
  (SELECT count(*) FROM c360_bank.cards.silver_solicitations_quarantine WHERE quarantine_reason = 'crm_key_not_in_xref') quarantined_unmapped_xref,
  (SELECT count(*) FROM t WHERE bad_credit_score = 'True') planted_bad_credit_scores,
  (SELECT count(*) FROM c360_bank.cards.silver_customers_quarantine) quarantined_customers,
  (SELECT count(*) FROM c360_bank.cards.silver_solicitations s JOIN t ON t.customer_id = s.customer_id WHERE s.qualified = (t.qualified = 'True')) qualified_flag_agrees,
  (SELECT count(*) FROM c360_bank.cards.silver_solicitations) solicitations_compared,
  (SELECT count(*) FROM c360_bank.cards.silver_solicitations s JOIN t ON t.customer_id = s.customer_id WHERE s.accepted = (t.accepted = 'True')) accepted_flag_agrees;
