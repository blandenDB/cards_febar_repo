-- Bronze: each source file set as landed, read with Auto Loader (streaming tables).
-- Each file is processed once, so rerunning the pipeline adds no duplicate rows.
-- All columns land as strings; typing happens in silver.

CREATE OR REFRESH STREAMING TABLE bronze_ecif_customers
COMMENT 'Customer system (ecif) customer extract, as landed'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${raw_root}/ecif_customers', format => 'csv', header => true, inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_ecif_accounts
COMMENT 'Customer system (ecif) deposit accounts, as landed'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${raw_root}/ecif_accounts', format => 'csv', header => true, inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_ecif_balances
COMMENT 'Customer system (ecif) month-end balances, one file per month, as landed'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${raw_root}/ecif_balances', format => 'csv', header => true, inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_crm_campaigns
COMMENT 'Campaign system (crm) campaigns and offers, as landed'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${raw_root}/crm_campaigns', format => 'csv', header => true, inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_crm_xref
COMMENT 'Campaign system (crm) customer key to ecif customer ID cross-reference, as landed'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${raw_root}/crm_customer_xref', format => 'csv', header => true, inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_crm_solicitations
COMMENT 'Campaign system (crm) solicitations and responses, one file per month (resent and late files included), as landed'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${raw_root}/crm_solicitations', format => 'csv', header => true, inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_macro_prices
COMMENT 'Public price series (BLS CPI South region, EIA Lower Atlantic gasoline, FHFA metro house price index), as downloaded'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${raw_root}/macro_prices', format => 'csv', header => true, inferColumnTypes => false);
