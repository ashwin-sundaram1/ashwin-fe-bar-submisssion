# Stage 5 Evidence — Genie Agent (NL → SQL → Answer)

Genie space **"Meridian Trade — Growth Experimentation Genie"** (`01f1bbfeaa791ef6be696bdc95f71237`)
over `gold_experiment_results`, `gold_user_features`, and `user_recommendations`. Created via
`POST /api/2.0/genie/spaces` (payload: `genie/create_genie_space.json`). Below is a real
transcript captured through the Genie Conversation API — the questions, the SQL Genie
generated, and the natural-language answers it returned.

## Q1 — "What is the adoption lift (treatment minus control) for each product?"

Genie-generated SQL:
```sql
SELECT
  `product`,
  MAX(CASE WHEN `variant` = 'treatment' THEN `adoption_rate_pct` END)
  - MAX(CASE WHEN `variant` = 'control' THEN `adoption_rate_pct` END) AS `lift_pp`
FROM `ashwin_tvf_testing_catalog`.`meridian_trade`.`gold_experiment_results`
WHERE `product` IS NOT NULL
GROUP BY `product`
ORDER BY `lift_pp` DESC
```

Genie answer:
> At the **product** level across all non-null products, the adoption lift (treatment minus
> control) is highest for **agentic** at **16.99 percentage points**, followed by **crypto**
> at **15.00 points** and **options** at **10.83 points**. Across the 3 products shown,
> agentic has the strongest lift and options the lowest.

(Matches Stage 1 experiment results exactly.)

## Q2 — "How many users are recommended each product, and what is the average propensity score?"

Genie-generated SQL:
```sql
SELECT
  `recommended_product`,
  COUNT(*) AS `users`,
  AVG(`propensity_score`) AS `avg_propensity_score`
FROM `ashwin_tvf_testing_catalog`.`meridian_trade`.`user_recommendations`
WHERE `recommended_product` IS NOT NULL
GROUP BY `recommended_product`
ORDER BY `users` DESC
```

Genie answer:
> At the recommended-product level, there are **3,960** users recommended **crypto** (avg
> propensity **0.4719**), **3,500** recommended **agentic** (**0.3741**), and **2,540**
> recommended **options** (**0.4748**). Crypto has the largest recommended audience, options
> the highest average propensity, agentic the lowest.

(Matches Stage 4 scoring output exactly.)

## Space configuration

- **Instructions:** describe the three tables, when to use each, and define "lift".
- **Sample questions** (4) + **example SQL** (2) seeded for the business user.
- Serialized definition committed at `genie/serialized_space.json`.
