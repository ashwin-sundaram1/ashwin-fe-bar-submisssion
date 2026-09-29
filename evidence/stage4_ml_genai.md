# Stage 4 Evidence — ML Propensity Models + GenAI Nudges

Captured live from `fevm-ashwin-tvf-testing`. Code: `ml/train_propensity.py`, `genai/generate_nudges.sql`.

## 1. Model training + MLflow (job: [meridian] Train Propensity Models + Score)

One GradientBoosting propensity model per new product, trained on organic pre-launch
behavioral features + user attributes (experiment variant EXCLUDED — no leakage).
Test-set metrics (20% holdout, stratified):

```
product       AUC  AvgPrec    Acc  BaseRate
crypto      0.680    0.511  0.683     0.341
options     0.730    0.515  0.745     0.286
agentic     0.647    0.448  0.696     0.312
```

All runs logged to MLflow experiment `/Users/ashwin.sundaram@databricks.com/meridian_propensity`
(params, metrics, signature, input example) and registered to the **Unity Catalog model registry**:

```
ashwin_tvf_testing_catalog.meridian_trade.propensity_crypto     (v1)
ashwin_tvf_testing_catalog.meridian_trade.propensity_options    (v1)
ashwin_tvf_testing_catalog.meridian_trade.propensity_agentic    (v1)
```

## 2. Batch scoring — user_recommendations (10,000 rows)

Every user scored by all three models; the top-propensity product is the recommendation.
`expected_annual_value_usd = propensity × assumed annual notional × product fee`.

Recommendation mix + expected annual fee value:
```
recommended_product  users  avg_score  total_expected_value_usd
crypto               3960   0.472      186,871
agentic              3500   0.374      163,676
options              2540   0.475       90,446
                                        --------
                              TOTAL     440,993
```

**Targeting concentration** (the business case for propensity-based targeting): the top 30%
of users by propensity carry **$184,280** of expected value — ~42% of the total in ~30% of
users, so incentive spend can be concentrated where it converts.

## 3. GenAI personalized nudges (databricks-claude-sonnet-4-5 via ai_query)

LLM-written, compliant, 2-sentence nudges for the targeted cohort (top 750 by propensity);
templated fallback for the rest. Split: `llm_personalized` 750, `templated` 9,250.

Sample LLM output (highest-propensity users):

```
MER106423  options  0.957  "Ready to explore new strategies? You can now access options
                            trading to potentially diversify your approach—check out our
                            educational resources to learn if it fits your investing style."
MER103284  crypto   0.952  "Ready to explore something new? You can now trade crypto on
                            Meridian Trade—consider adding it to your portfolio mix if you're
                            interested in diversifying beyond your current holdings."
```

Note the guardrails held: no promised returns, no financial advice, no emojis — enforced via
the prompt. `user_recommendations` columns include the per-product probabilities, the
recommendation, `propensity_score`, `expected_annual_value_usd`, `targeting_decile`,
`nudge_text`, and `nudge_source`.
