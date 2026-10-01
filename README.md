# Meridian Trade — FE Bar Submission

An end-to-end Databricks data journey for a (fictional) retail financial-trading platform.
**Meridian Trade** runs an experimentation pipeline that tracks per-user behavior and decides
which new product — **crypto, options, or the AI "agentic" trading assistant** — to put in
front of each user, and measures the lift.

Built across all six required components, integrated (not siloed):

| # | Component | What it does here | Code |
|---|-----------|-------------------|------|
| 1 | **Lakeflow** | Declarative Pipeline ingests raw event/user/experiment files from a UC Volume with Auto Loader → Bronze → Silver → Gold | [`pipelines/`](pipelines/) |
| 2 | **Unity Catalog** | 3-level namespaces, PII column masks, tags, least-privilege grants, auto lineage | [`governance/`](governance/) |
| 3 | **Lakebase** | Postgres serving of `user_recommendations` for ~3 ms per-user lookup | [`lakebase/`](lakebase/) |
| 4 | **ML + GenAI** | MLflow propensity models (registered to UC) score every user; `databricks-claude-sonnet-4-5` writes the personalized nudge | [`ml/`](ml/), [`genai/`](genai/) |
| 5 | **Genie** | NL Q&A space over the gold + experiment tables | [`genie/`](genie/) |
| 6 | **Databricks App** | Streamlit app: exec KPIs, per-user targeting (from Lakebase), embedded Genie | [`app/`](app/) |

Full design and rationale: [`DEMO.md`](DEMO.md). Task log: [`TASKS.md`](TASKS.md).

## The headline results (all real, captured from the workspace)

- Experiment adoption **lift**: crypto **+15.0 pp**, agentic **+17.0 pp**, options **+10.8 pp** (treatment vs control)
- **$441K** expected annual fee value identified across 10,000 users; **42%** concentrated in the top 30% by propensity
- 10,000 users, **1.55M** events ingested through the medallion pipeline
- Propensity models holdout AUC **0.65–0.73**, registered to Unity Catalog
- PII masked in Unity Catalog; ~3 ms Lakebase point lookups; Genie answers NL questions with correct SQL

## Execution evidence (text-readable — start here)

The evaluator reads text only; every stage commits its actual output, not screenshots:

- [`evidence/stage1_lakeflow_medallion.md`](evidence/stage1_lakeflow_medallion.md) — data gen job log, pipeline run, row counts, experiment lift
- [`evidence/stage2_unity_catalog_governance.md`](evidence/stage2_unity_catalog_governance.md) — masked vs raw output, tags, grants, lineage DAG
- [`evidence/stage3_lakebase.md`](evidence/stage3_lakebase.md) — Lakebase sync + measured ~3 ms lookups
- [`evidence/stage4_ml_genai.md`](evidence/stage4_ml_genai.md) — model metrics, UC registry, recommendation mix, sample nudges
- [`genie/genie_transcript.md`](genie/genie_transcript.md) — Genie NL → SQL → answer transcript
- [`evidence/stage6_app.md`](evidence/stage6_app.md) — deployed app validation

Business deck: [`deck/meridian_trade_deck.pdf`](deck/meridian_trade_deck.pdf) (Databricks-branded, 9 slides) · source outline [`deck/meridian_trade_deck.md`](deck/meridian_trade_deck.md).

## Architecture

```
 Raw synthetic files (UC Volume: landing/)
        │  (1) LAKEFLOW Declarative Pipeline — Auto Loader
        ▼
 BRONZE  bronze_users / bronze_events / bronze_experiment_assignments / bronze_product_catalog
        │
 SILVER  cleaned, typed, de-duplicated, pre/post-launch flag
        │
 GOLD    gold_user_features (features + derived adoption labels + variants)
         gold_experiment_results (per-variant adoption + lift)
        │
        ├─(2) UNITY CATALOG governs all of the above (masks, tags, grants, lineage)
        │
        ├─(4) ML: MLflow propensity models (UC registry) → user_recommendations
        │      GenAI: databricks-claude-sonnet-4-5 → personalized nudge_text
        │            │
        │            ▼
        ├─(3) LAKEBASE (Postgres) ← synced user_recommendations (low-latency serving)
        │
        ├─(5) GENIE space over gold + experiment tables (NL Q&A)
        │
        └─(6) DATABRICKS APP (Streamlit) — surfaces all of it to the Growth team
```

Everything runs in workspace `fevm-ashwin-tvf-testing`, catalog
`ashwin_tvf_testing_catalog`, schema `meridian_trade`.

## How to run

Prereqs: Databricks CLI authenticated to the target workspace (profile below), a SQL
warehouse, and permission to create pipelines/jobs/apps/Lakebase.

```bash
export P=fevm-ashwin-tvf-testing        # your workspace profile

# 0. Create schema + landing volume (once)
#    CREATE SCHEMA ...meridian_trade; CREATE VOLUME ...meridian_trade.landing;

# 1. Deploy the bundle (jobs + Lakeflow pipeline)
databricks bundle deploy -p $P -t dev

# 2. Generate data, then run the medallion pipeline
databricks bundle run generate_synthetic_data -p $P -t dev
databricks bundle run meridian_medallion     -p $P -t dev

# 3. Governance (masks, tags, grants) — run governance/governance.sql on the warehouse

# 4. Train + score models, then generate GenAI nudges
databricks bundle run train_propensity -p $P -t dev
#    then run genai/generate_nudges.sql on the warehouse

# 5. Lakebase: create instance `meridian-lakebase`, then
databricks bundle run sync_to_lakebase -p $P -t dev

# 6. Genie: POST genie/create_genie_space.json to /api/2.0/genie/spaces

# 7. App: sync app/ to the workspace and `databricks apps deploy meridian-trade`
```

All datasets are **synthetic** (generated by `data_generation/generate_synthetic_data.py`).
No real customer data is used anywhere in this repository.
