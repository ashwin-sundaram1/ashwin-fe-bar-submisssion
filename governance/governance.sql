-- Meridian Trade — Unity Catalog governance
-- Idempotent; run after the Lakeflow pipeline materializes the medallion.
-- Demonstrates: PII column masking, tags, comments, grants, and least-privilege access.
--
-- NOTE on object types: the Lakeflow pipeline produces Bronze STREAMING TABLES and
-- Silver/Gold MATERIALIZED VIEWS, which are pipeline-managed and do not accept
-- `ALTER ... SET MASK`. We therefore expose a governed, managed consumer dimension
-- (`dim_users_secure`) that carries the PII column masks and is what analysts/the app
-- are granted — while the raw silver_users (unmasked) is NOT granted broadly.

-- =====================================================================
-- 1. PII COLUMN MASK FUNCTIONS
-- A reader sees the raw value only if they belong to the `pii_readers` account
-- group; everyone else gets a redacted value. Masks run for all readers.
-- =====================================================================
CREATE OR REPLACE FUNCTION ashwin_tvf_testing_catalog.meridian_trade.mask_email(email STRING)
  RETURN CASE
    WHEN is_account_group_member('pii_readers') THEN email
    ELSE regexp_replace(email, '^[^@]+', '****')
  END;

CREATE OR REPLACE FUNCTION ashwin_tvf_testing_catalog.meridian_trade.mask_account_ref(acct STRING)
  RETURN CASE
    WHEN is_account_group_member('pii_readers') THEN acct
    ELSE concat('ACCT-****', substr(acct, -4))
  END;

-- =====================================================================
-- 2. GOVERNED, MASKED CONSUMER DIMENSION (managed Delta table)
-- =====================================================================
CREATE OR REPLACE TABLE ashwin_tvf_testing_catalog.meridian_trade.dim_users_secure
  COMMENT 'Governed, PII-masked user dimension for analysts and the app.'
  AS SELECT * FROM ashwin_tvf_testing_catalog.meridian_trade.silver_users;

ALTER TABLE ashwin_tvf_testing_catalog.meridian_trade.dim_users_secure
  ALTER COLUMN email SET MASK ashwin_tvf_testing_catalog.meridian_trade.mask_email;
ALTER TABLE ashwin_tvf_testing_catalog.meridian_trade.dim_users_secure
  ALTER COLUMN account_ref SET MASK ashwin_tvf_testing_catalog.meridian_trade.mask_account_ref;

ALTER TABLE ashwin_tvf_testing_catalog.meridian_trade.dim_users_secure
  ALTER COLUMN email COMMENT 'PII — email. Masked unless caller is in pii_readers.';
ALTER TABLE ashwin_tvf_testing_catalog.meridian_trade.dim_users_secure
  ALTER COLUMN account_ref COMMENT 'PII — account number. Masked unless caller is in pii_readers.';

-- =====================================================================
-- 3. TAGS — free-form keys (medallion_layer, contains_pii, business_domain)
-- =====================================================================
ALTER TABLE ashwin_tvf_testing_catalog.meridian_trade.dim_users_secure
  SET TAGS ('medallion_layer' = 'gold', 'contains_pii' = 'true');
ALTER TABLE ashwin_tvf_testing_catalog.meridian_trade.silver_users
  SET TAGS ('medallion_layer' = 'silver', 'contains_pii' = 'true');
ALTER TABLE ashwin_tvf_testing_catalog.meridian_trade.silver_events
  SET TAGS ('medallion_layer' = 'silver');

-- Column-level governed tag (pii_category='email' is an allowed value in this workspace's
-- tag taxonomy; account_ref is protected via its mask + column comment above).
ALTER TABLE ashwin_tvf_testing_catalog.meridian_trade.dim_users_secure
  ALTER COLUMN email SET TAGS ('pii_category' = 'email');

-- =====================================================================
-- 4. GRANTS — analysts/BI read the governed layer only (least privilege).
--    Raw silver_users (unmasked PII) is intentionally NOT granted here.
-- =====================================================================
GRANT USE CATALOG ON CATALOG ashwin_tvf_testing_catalog TO `account users`;
GRANT USE SCHEMA ON SCHEMA ashwin_tvf_testing_catalog.meridian_trade TO `account users`;
GRANT SELECT ON TABLE ashwin_tvf_testing_catalog.meridian_trade.dim_users_secure TO `account users`;
GRANT SELECT ON TABLE ashwin_tvf_testing_catalog.meridian_trade.gold_experiment_results TO `account users`;
GRANT SELECT ON TABLE ashwin_tvf_testing_catalog.meridian_trade.gold_user_features TO `account users`;
