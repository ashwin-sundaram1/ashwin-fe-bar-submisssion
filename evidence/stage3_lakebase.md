# Stage 3 Evidence — Lakebase Operational Serving

Captured live from `fevm-ashwin-tvf-testing`. Code: `lakebase/sync_to_lakebase.py`.

## Instance

Lakebase (managed Postgres) instance `meridian-lakebase`, capacity `CU_1`, state **AVAILABLE**.
Endpoint: `ep-autumn-feather-d82ovqxy.database.us-east-2.cloud.databricks.com`.

## Why Lakebase here

The app needs **low-latency per-user lookups** ("what should we show *this* user right now?"),
which is an operational/transactional access pattern — not an analytical scan. The gold
`user_recommendations` Delta table is synced into a native Postgres table (PK on `user_id`,
secondary index on `recommended_product`) that the Databricks App queries directly.

## Sync + serving proof (job: [meridian] Sync Recommendations to Lakebase → SUCCESS)

```
Lakebase host: ep-autumn-feather-d82ovqxy.database.us-east-2.cloud.databricks.com
  db: databricks_postgres  user: ashwin.sundaram@databricks.com
Loaded 10,000 recommendations from ashwin_tvf_testing_catalog.meridian_trade.user_recommendations
Rows in Postgres user_recommendations: 10,000

=== LOW-LATENCY POINT LOOKUPS (Lakebase Postgres) ===
  MER106423  -> options   score=0.957  (llm_personalized)  [3.0 ms]
  MER103284  -> crypto    score=0.952  (llm_personalized)  [2.9 ms]
  MER108995  -> options   score=0.941  (llm_personalized)  [2.8 ms]
  MER105716  -> options   score=0.934  (llm_personalized)  [2.9 ms]
  MER107454  -> options   score=0.931  (llm_personalized)  [4.3 ms]

=== TARGETING QUERY (top crypto prospects, indexed) ===
  MER103284  score=0.952
  MER102739  score=0.927
  MER106825  score=0.905
  MER103934  score=0.899
  MER104283  score=0.891
  (query 6.4 ms)

Lakebase sync complete.
```

Point lookups return in **~3 ms**; the indexed targeting query in **~6 ms** — the low-latency
serving layer the app relies on. Authentication uses a short-lived Lakebase credential
generated via the Databricks REST API (`/api/2.0/database/credentials`); no static secrets.
