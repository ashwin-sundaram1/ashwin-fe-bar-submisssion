# Meridian Trade — Experimentation & Next-Best-Feature Platform

> FE Bar submission — an end-to-end Databricks data journey for a retail financial trading platform.

## 1. The Customer Problem

**Meridian Trade** is a (fictional) commission-free retail trading platform with millions of
users. Its Growth & Product team constantly launches new products — **crypto trading,
options trading, and an AI "agentic" trading assistant** — and needs to decide **which new
product to put in front of which user, and when.**

Today that decision is made with crude, hand-maintained rules ("users who traded >10x last
month get the options banner"). The result:

- **Low conversion** on cross-sell campaigns — the right offer rarely reaches the right user.
- **Wasted incentive spend** — promos and fee credits go to users who would never convert.
- **Slow, unmeasured experimentation** — the team can't cleanly tie a product nudge to
  adoption or incremental revenue, so learning is anecdotal.

**The business needs:** a governed, data-driven **experimentation + recommendation system**
that tracks per-user behavior, measures experiment lift, scores each user's propensity to
adopt each new product, personalizes the outreach, and lets the business self-serve the
insight — without waiting on data engineering.

## 2. Business Outcome & KPIs (what we optimize)

| KPI | Baseline (rules-based) | Target (this platform) |
|-----|------------------------|------------------------|
| New-product adoption / conversion rate | ~2–3% | 2–3× lift on targeted cohort |
| Incremental revenue per targeted user | flat | measurable, attributable |
| Wasted incentive spend | high (untargeted) | cut by targeting top-propensity users |
| Time to read an experiment result | days (manual) | seconds (Genie + app) |

Framed for **two buyers**: the **executive sponsor** (VP Growth) cares about conversion lift
and incentive ROI; the **domain owner** (Growth PM / experimentation lead) cares about
per-user targeting and self-serve experiment readouts.

## 3. Architecture — End-to-End Data Journey

```
                       RAW (synthetic)                    MEDALLION (Unity Catalog)
  ┌─────────────────────────────┐        ┌──────────────────────────────────────────┐
  │ user activity events (JSON) │        │  BRONZE  raw as-landed (Auto Loader)       │
  │ users / accounts (CSV)      │  ───▶  │  SILVER  cleaned, typed, sessionized,      │
  │ experiment assignments      │        │          PII-masked, exposure joined       │
  │ product catalog             │        │  GOLD    per-user features + labels,       │
  └─────────────────────────────┘        │          experiment results               │
         │                                └──────────────────────────────────────────┘
         │ (1) LAKEFLOW                              │            │
         │  Declarative Pipeline                     │            │
         ▼                                           ▼            ▼
   UC Volume (landing)                    (4) ML/GenAI       (5) GENIE
                                          MLflow propensity   NL Q&A space
   (2) UNITY CATALOG governs everything   model → per-user    over gold +
       grants · tags · column masks ·     adoption scores;    experiment tables
       lineage                            LLM writes nudge         │
                                               │                   │
                                               ▼                   │
                                    (3) LAKEBASE (Postgres)        │
                                    synced recommendations    ┌────┴─────────────┐
                                    for low-latency lookup ─▶ │ (6) DATABRICKS   │
                                                              │     APP          │
                                                              │  KPIs · funnel · │
                                                              │  per-user rec ·  │
                                                              │  Genie embed     │
                                                              └──────────────────┘
```

### Stage mapping to the six required components

| # | Required component | How Meridian Trade uses it |
|---|--------------------|----------------------------|
| 1 | **Lakeflow** | Lakeflow Declarative Pipeline ingests raw event/user/experiment files from a UC Volume with Auto Loader → Bronze → Silver → Gold. |
| 2 | **Unity Catalog** | All assets in `ashwin_tvf_testing_catalog.meridian_trade`. 3-level namespaces, table/column comments & tags, **column mask on PII** (email/SSN-like), grants, and end-to-end lineage. |
| 3 | **Lakebase** | Postgres instance serving the `user_recommendations` table for **low-latency per-user lookup** by the app (operational serving, not analytics). |
| 4 | **ML / Gen AI** | **ML:** MLflow propensity model scoring each user × candidate product, registered to UC, batch-scored. **GenAI:** `databricks-claude-sonnet-4-5` generates the personalized nudge copy per top recommendation. |
| 5 | **Genie Agent** | Genie space over Gold + experiment tables so the Growth PM asks NL questions ("Which cohort has the highest crypto propensity?", "What's the options experiment lift?"). |
| 6 | **Databricks App** | Streamlit app: exec KPI/funnel view, per-user recommendation lookup (from Lakebase) with the generated nudge, and embedded Genie for NL Q&A. |

## 4. Data Model (synthetic)

- **`raw_user_events`** — event stream: `event_id, user_id, event_ts, event_type` (login,
  view_product, trade, deposit, withdrawal, feature_interaction), `product, amount, session_id`.
- **`raw_users`** — `user_id, signup_date, tier, region, age_band, risk_profile, kyc_status,
  email, account_ref` (email/account_ref are the masked PII columns).
- **`raw_experiment_assignments`** — `experiment_id, user_id, variant (control/treatment),
  assigned_ts` for the three product experiments (crypto, options, agentic).
- **`product_catalog`** — the candidate products with eligibility rules.

Gold `user_features` carries engagement/trading aggregates (trades_30d, deposit_velocity,
active_days, product_holdings, session depth, etc.) + per-product adoption label for training.

All data is **synthetic**, generated on serverless — no real customer data anywhere.

## 5. Brand / Visual Guidelines

Fictional brand "Meridian Trade" — modern fintech look. Primary `#0B6E4F` (deep green,
"markets up"), accent `#F2A900` (gold), dark slate `#1C2B33`, neutral backgrounds. Clean,
data-dense, executive-ready. (No real company branding — this is a fictional platform.)

## 6. Repository Layout

```
data_generation/   synthetic data generator (serverless notebook + script)
pipelines/         Lakeflow Declarative Pipeline (bronze/silver/gold)
governance/        UC grants, tags, column-mask, lineage capture
ml/                MLflow propensity training + batch scoring
genai/             LLM nudge generation
lakebase/          Lakebase provisioning + sync of recommendations
genie/             Genie space definition + example Q&A transcript
app/               Databricks App (Streamlit)
evidence/          committed, text-readable run outputs (the "it ran" proof)
deck/              business presentation deck
```

## 7. Execution Evidence Strategy (grading-critical)

The evaluator reads **text only**. For every stage we commit the *output itself*, not a
picture of it:

- Notebooks committed **with cell outputs** (executed `.ipynb`) and/or exported run logs.
- Query results dumped to CSV/markdown in `evidence/`.
- MLflow run metrics/params exported as JSON/text.
- Lakeflow pipeline run + event-log excerpts as text.
- A committed sample of the `user_recommendations` table and a Lakebase query result.
- A Genie question→SQL→answer transcript in `genie/`.

## 8. Out of Scope

- Real customer data (strictly synthetic).
- Production hardening (HA, CI/CD, secrets rotation) beyond what demonstrates the pattern.
- Real payment/brokerage integrations.
