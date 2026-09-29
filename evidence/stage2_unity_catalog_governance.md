# Stage 2 Evidence — Unity Catalog Governance

All output captured live from `fevm-ashwin-tvf-testing`. Governance SQL: `governance/governance.sql`.

## 1. PII column masking (the headline governance control)

Two masking functions gate `email` and `account_ref` behind the `pii_readers` account group.
They are applied to the governed managed dimension `dim_users_secure`, which analysts and the
app are granted; the raw `silver_users` (unmasked) is **not** granted to `account users`.

Caller context:
```
in_pii_readers | me
false          | ashwin.sundaram@databricks.com
```

**Masked** view (`dim_users_secure` — what a non-privileged analyst/app sees):
```
user_id    email                             account_ref     tier
MER100000  ****@meridiantrade-example.com    ACCT-****6949   gold
MER100001  ****@meridiantrade-example.com    ACCT-****5723   bronze
MER100002  ****@meridiantrade-example.com    ACCT-****2287   gold
```

**Raw** source (`silver_users` — restricted; shown here only because I own the source):
```
user_id    email                                  account_ref
MER100000  user100000@meridiantrade-example.com   ACCT-1945446949
MER100001  user100001@meridiantrade-example.com   ACCT-2225925723
MER100002  user100002@meridiantrade-example.com   ACCT-6523482287
```

Mask assignments (`information_schema.column_masks`):
```
table_name        column_name   mask_name
dim_users_secure  email         ashwin_tvf_testing_catalog.meridian_trade.mask_email
dim_users_secure  account_ref   ashwin_tvf_testing_catalog.meridian_trade.mask_account_ref
```

## 2. Tags (classification / discovery)

`information_schema.table_tags` + `column_tags`:
```
table            tag_name          tag_value
silver_users     contains_pii      true
silver_users     medallion_layer   silver
silver_events    medallion_layer   silver
dim_users_secure medallion_layer   gold          (+ contains_pii=true)

column tag:  dim_users_secure.email  pii_category=email
```
> Note: this FEVM workspace enforces a **governed tag taxonomy**. Free keys
> (`medallion_layer`, `contains_pii`) and the allowed governed value `pii_category=email`
> apply; disallowed governed values (e.g. `business_domain=growth`) are rejected by policy —
> itself a demonstration of Unity Catalog tag governance in action.

## 3. Grants (least privilege)

`SHOW GRANTS ON TABLE dim_users_secure`:
```
Principal       ActionType   ObjectType   ObjectKey
account users   SELECT       TABLE        ...meridian_trade.dim_users_secure
```
Analysts (`account users`) can read the **masked** dimension and the gold tables, but the raw
unmasked `silver_users` is intentionally not granted to them.

## 4. End-to-end lineage (auto-captured by Unity Catalog)

`system.access.table_lineage` — the full medallion DAG, captured automatically:
```
bronze_users                  -> silver_users
bronze_events                 -> silver_events
bronze_experiment_assignments -> silver_experiment_assignments
silver_users                  -> gold_user_features
silver_events                 -> gold_user_features
silver_experiment_assignments -> gold_user_features
gold_user_features            -> gold_experiment_results
```
Column-level lineage is likewise available in Catalog Explorer for every table above.
