-- Meridian Trade — GenAI personalized outreach nudges
-- Uses the Databricks-hosted foundation model databricks-claude-sonnet-4-5 (via ai_query)
-- to write a personalized, compliant in-app nudge for each user's recommended product.
-- LLM spend is reserved for the TARGETED cohort (top propensity); everyone else gets a
-- sensible templated message. Produces the final serving table user_recommendations.

CREATE OR REPLACE TABLE ashwin_tvf_testing_catalog.meridian_trade.user_recommendations AS
WITH ranked AS (
  SELECT
    *,
    row_number() OVER (ORDER BY propensity_score DESC) AS overall_rank,
    CASE recommended_product
      WHEN 'crypto'  THEN 'crypto trading'
      WHEN 'options' THEN 'options trading'
      WHEN 'agentic' THEN 'the AI agentic trading assistant'
    END AS product_label
  FROM ashwin_tvf_testing_catalog.meridian_trade.user_recommendations_base
)
SELECT
  * EXCEPT (overall_rank),
  CASE
    WHEN overall_rank <= 750 THEN
      ai_query(
        'databricks-claude-sonnet-4-5',
        CONCAT(
          'You are a growth marketing specialist at Meridian Trade, a retail investing app. ',
          'Write ONE friendly, compliant, two-sentence in-app nudge encouraging this user to try ',
          product_label, '. ',
          'User profile: ', tier, ' tier, ', risk_profile, ' risk appetite, age ', age_band,
          ', ', CAST(trades_total AS STRING), ' lifetime trades, ', CAST(active_days AS STRING),
          ' active days. Rules: do NOT promise returns, give no financial advice, no emojis, ',
          'address them as "you", keep it under 45 words.'
        )
      )
    ELSE CONCAT('Based on your recent activity, ', product_label,
                ' on Meridian Trade may be a good fit. Explore it in the app when you are ready.')
  END AS nudge_text,
  CASE WHEN overall_rank <= 750 THEN 'llm_personalized' ELSE 'templated' END AS nudge_source
FROM ranked;
