# TASKS — Meridian Trade FE Bar Build

Status legend: ⬜ todo · 🔄 in progress · ✅ done · ⏸️ blocked

Workspace: `fevm-ashwin-tvf-testing` · Catalog: `ashwin_tvf_testing_catalog` · Schema: `meridian_trade`
Repo: https://github.com/ashwin-sundaram1/ashwin-fe-bar-submisssion

## Stage 0 — Plan & scaffold
- ✅ Read prompt, confirm use case & approach
- ✅ Discover workspace (catalog, warehouse, lakebase)
- ✅ Clone repo, create directory structure
- ✅ Write DEMO.md + TASKS.md → **CHECKPOINT 1: plan approved**

## Stage 1 — Synthetic data + Bronze/Silver/Gold (Lakeflow)
- ✅ Write serverless synthetic data generator (users, events, experiments, catalog)
- ✅ Land raw files to UC Volume `ashwin_tvf_testing_catalog.meridian_trade.landing`
- ✅ Build Lakeflow Declarative Pipeline: Bronze (Auto Loader) → Silver → Gold
- ✅ Run pipeline, verify row counts & data quality
- ✅ Commit executed notebooks + evidence → **CHECKPOINT 2**

## Stage 2 — Unity Catalog governance
- ✅ Table/column comments + tags on medallion tables
- ✅ Column mask on PII (email, account_ref)
- ✅ Grants to demonstrate governed access
- ✅ Capture lineage (raw → bronze → silver → gold → recs)
- ✅ Commit governance SQL + evidence → **CHECKPOINT 3**

## Stage 3 — Lakebase operational serving
- ✅ Create Lakebase (Postgres) instance
- ✅ Sync/write `user_recommendations` to Lakebase
- ✅ Verify low-latency lookup by user_id
- ✅ Commit provisioning + query evidence → **CHECKPOINT 4**

## Stage 4 — ML propensity + GenAI nudge
- ✅ Feature prep from Gold
- ✅ Train MLflow propensity model (user × product adoption), log metrics
- ✅ Register model to UC model registry
- ✅ Batch-score all users → per-product scores → top recommendation
- ✅ GenAI: databricks-claude-sonnet-4-5 generates personalized nudge per top rec
- ✅ Write `user_recommendations` gold table
- ✅ Commit executed notebooks + MLflow metrics + sample output → **CHECKPOINT 5**

## Stage 5 — Genie agent
- ✅ Create Genie space over Gold + experiment tables
- ✅ Add sample questions + instructions
- ✅ Capture NL question → SQL → answer transcript as text
- ✅ Commit genie config + transcript → **CHECKPOINT 6**

## Stage 6 — Databricks App
- ✅ Build Streamlit app (KPIs/funnel, per-user rec lookup from Lakebase, Genie embed)
- ✅ Local devloop test (N/A: PyPI blocked locally; validated on the live deployed app instead)
- ✅ Deploy app to workspace, verify running
- ✅ Commit app code + run evidence → **CHECKPOINT 7**

## Stage 7 — Deck + finalize
- ✅ Presentation deck (business outcome, KPIs, both buyers) → export PDF/md to deck/
- ✅ Finalize README with architecture + how-to-run + evidence index
- ✅ Verify repo is public & readable end-to-end
- ✅ Final commit + push → **DONE**
