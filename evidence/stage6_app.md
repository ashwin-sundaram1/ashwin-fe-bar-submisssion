# Stage 6 Evidence — Databricks App

Streamlit app **"Meridian Trade — Growth Intelligence"** deployed to Databricks Apps and
validated live in the browser. Code: [`app/`](../app/). (Screenshots in
[`app_screenshots/`](app_screenshots/) are for human reviewers; the text below is the evidence.)

- App: `meridian-trade` — compute **ACTIVE**, deployment **SUCCEEDED** ("App started successfully")
- URL: `https://meridian-trade-7474645316951439.aws.databricksapps.com` (returns HTTP 302 → Databricks OAuth, i.e. a running, access-controlled app)
- Service principal `62961d8e-ff7b-4713-9d4a-9ce9183c57e9` granted USE CATALOG/SCHEMA + SELECT on the gold tables, CAN_USE on the warehouse, and CAN_RUN on the Genie space.

## Live UI validation (all three tabs — no console errors)

### Executive Overview
- KPI tiles: **Users scored 10,000**, **Avg experiment lift +14.3 pp**, **Expected annual value $441K**, **Top recommended product: Crypto**
- Grouped bar chart (control vs treatment adoption) renders for all three products
- Lift table: agentic Control 22.68% / Treatment 39.67% / **+16.99 pp**; crypto 26.58% / 41.58% / **+15.0 pp**; options 23.3% / 34.13% / **+10.83 pp**
- Recommendation-mix donut: crypto 39.6%, agentic 35%, options 25.4%
- Expected-value bar: crypto $187K, agentic $164K, options $90K
- Value-concentration table (top 30% targeted vs remaining 70%)

### User Targeting
- **Data source: Lakebase** — the latency badge confirms the per-user lookup is served from
  Lakebase (operational Postgres), not the SQL-warehouse fallback.
- Example user MER106423: Recommended **Options**, Propensity **96%**, Expected value **$72/yr**,
  Targeting decile **#1**; propensity bar chart (crypto 92% / options 96% / agentic 18%);
  profile (gold tier, US-East, 26-35, aggressive); personalized nudge rendered in the nudge box.

### Ask Genie
- Question "What is the adoption lift for each product?" → answer returned in ~30–40 s:
  *"adoption lift is highest for agentic at 16.99 percentage points, followed by crypto at
  15.00 points and options at 10.83 points."* — matches the data.
- "SQL Genie generated" expander present (shows the backing SQL).

**Overall:** fully operational end-to-end — the app surfaces the entire data journey
(Lakeflow → UC → ML/GenAI → Lakebase → Genie) to the business in one place.
