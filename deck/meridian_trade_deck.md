# Meridian Trade
## Turning experimentation into targeted growth

**Next-best-feature targeting for crypto, options, and the AI agentic assistant**
Presented to: VP of Growth (executive sponsor) · Growth Product Lead (domain owner)

---

## Slide 1 — The business problem

Meridian Trade launches new products constantly — **crypto, options, an AI agentic
assistant** — and has to decide *which product to put in front of which of our millions of
users, and when.*

Today that decision runs on **hand-maintained rules** ("traded >10× last month → show the
options banner"). The cost of guessing:

- **Low conversion** — the right offer rarely reaches the right user
- **Wasted incentive spend** — promos and fee credits go to users who would never convert
- **Unmeasured experiments** — we can't cleanly attribute a nudge to adoption, so we don't learn

> We are spending real marketing dollars on untargeted campaigns and flying blind on what works.

---

## Slide 2 — The outcome (what we proved)

A governed, data-driven experimentation + recommendation platform, built end-to-end on Databricks:

| Result | Number |
|--------|--------|
| Adoption lift, treatment vs. control (agentic) | **+17.0 pp** (22.7% → 39.7%) |
| Adoption lift (crypto) | **+15.0 pp** (26.6% → 41.6%) |
| Adoption lift (options) | **+10.8 pp** (23.3% → 34.1%) |
| Expected annual fee value identified | **$441K** across 10K users |
| Value concentration in top 30% of users | **42%** of expected value |

**The experiments work, and the model tells us exactly who to target next.**

---

## Slide 3 — How it works (one picture)

```
 Raw activity  →  Lakeflow  →  Bronze/Silver/Gold  →  Propensity ML  →  Recommendation
 (trades,          ingest        (governed in           (per-user ×        + GenAI nudge
  logins,          + clean        Unity Catalog,          product score)         │
  experiments)                    PII masked)                                     ▼
                                        │                                   Lakebase (fast
                                        └─────────────→  Genie (ask in       per-user serving)
                                                          plain English)           │
                                                                                   ▼
                                                                          Growth app (this)
```

One integrated journey — from raw events to a business app the Growth team uses daily.
No data silos, PII governed and masked end-to-end, every step measurable.

---

## Slide 4 — For the executive sponsor (VP Growth)

**You care about conversion lift and incentive ROI.**

- **Measured, attributable lift**: randomized control/treatment experiments show
  **+10–17 pp** adoption on targeted cohorts — not anecdotes, real causal lift.
- **Spend where it converts**: the top 30% of users by propensity carry **42% of expected
  value**. Concentrate incentives there and cut wasted spend on the rest.
- **A revenue number, not a vibe**: **$441K** in expected annual fee value identified and
  prioritized across the current base — and it grows with every new product launch.

---

## Slide 5 — For the domain owner (Growth PM)

**You care about targeting the right user and reading results without waiting on data eng.**

- **Per-user next-best-feature**: every user scored across all three products; the app returns
  the recommendation, propensity, expected value, and targeting priority in **~3 ms**.
- **Personalized, compliant outreach**: GenAI writes the nudge copy for the targeted cohort —
  no promised returns, no financial advice, on-brand.
- **Self-serve answers**: ask Genie *"what's the crypto lift?"* or *"who should we target?"* in
  plain English and get SQL-grade answers in seconds. No ticket, no dashboard backlog.

---

## Slide 6 — Proof it's real

- **Experiments**: 30,000 assignments across 3 product launches; lift measured per variant.
- **Models**: 3 propensity models (crypto/options/agentic), MLflow-tracked, registered to
  Unity Catalog. Holdout AUC **0.65–0.73** on realistic behavioral signal.
- **Scale**: 10,000 users, **1.55M** activity events, ingested and governed through a
  Lakeflow medallion pipeline.
- **Governance**: PII (email, account number) **masked** in Unity Catalog; least-privilege
  grants; full lineage captured automatically.

---

## Slide 7 — What's next

1. **Close the loop**: feed live adoption back as labels; retrain weekly; auto-promote the
   best model version in Unity Catalog.
2. **Expand the catalog**: score every future product launch on day one against the whole base.
3. **Activate**: push the targeted cohort + nudges to the marketing platform automatically.
4. **Guardrails**: suitability/eligibility rules for options and crypto enforced in the
   recommendation layer.

**Meridian Trade turns every launch into a measured, targeted, self-serve growth motion.**
