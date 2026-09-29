"""
Meridian Trade — Lakeflow Declarative Pipeline (medallion: Bronze -> Silver -> Gold).

Ingests the raw synthetic files landed in the UC Volume with Auto Loader, cleans and
conforms them in Silver, and builds the Gold analytics/ML tables:

  gold_user_features    one row per user: pre-launch behavioral features + experiment
                        variant + DERIVED adoption labels (post-launch trades on the new
                        products). This is the training table for the propensity model.
  gold_experiment_results   per experiment/variant adoption rates + lift (for Genie/BI).

Bronze uses Auto Loader (cloudFiles) streaming tables; Silver/Gold are materialized.
Run on serverless.
"""
import dlt
from pyspark.sql import functions as F

CATALOG = "ashwin_tvf_testing_catalog"
SCHEMA = "meridian_trade"
BASE = f"/Volumes/{CATALOG}/{SCHEMA}/landing"
LAUNCH = "2026-06-01"                      # experiment launch / pre-vs-post cutoff
NEW_PRODUCTS = ["crypto", "options", "agentic"]


# --------------------------------------------------------------- BRONZE (Auto Loader)
@dlt.table(comment="Raw user/account records as landed (CSV via Auto Loader).")
def bronze_users():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(f"{BASE}/users")
        .withColumn("_ingested_at", F.current_timestamp())
    )


@dlt.table(comment="Raw activity/trade event stream as landed (JSON via Auto Loader).")
def bronze_events():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(f"{BASE}/events")
        .withColumn("_ingested_at", F.current_timestamp())
    )


@dlt.table(comment="Raw experiment assignment records as landed (CSV via Auto Loader).")
def bronze_experiment_assignments():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(f"{BASE}/experiment_assignments")
        .withColumn("_ingested_at", F.current_timestamp())
    )


@dlt.table(comment="Product catalog reference (JSON via Auto Loader).")
def bronze_product_catalog():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(f"{BASE}/product_catalog")
    )


# --------------------------------------------------------------- SILVER (clean/conform)
@dlt.table(comment="Cleaned, de-duplicated users. email/account_ref are PII (masked in UC).")
@dlt.expect_or_drop("valid_user", "user_id IS NOT NULL")
def silver_users():
    w = "row_number() over (partition by user_id order by _ingested_at desc)"
    return (
        dlt.read("bronze_users")
        .withColumn("_rn", F.expr(w))
        .filter("_rn = 1")
        .drop("_rn")
        .withColumn("signup_date", F.to_date("signup_date"))
        .withColumn("account_balance_usd", F.col("account_balance_usd").cast("double"))
    )


@dlt.table(comment="Typed, de-duplicated events with pre/post-launch flag.")
@dlt.expect_or_drop("valid_event", "event_id IS NOT NULL AND user_id IS NOT NULL")
def silver_events():
    w = "row_number() over (partition by event_id order by _ingested_at desc)"
    return (
        dlt.read("bronze_events")
        .withColumn("_rn", F.expr(w))
        .filter("_rn = 1")
        .drop("_rn")
        .withColumn("event_ts", F.to_timestamp("event_ts"))
        .withColumn("amount_usd", F.col("amount_usd").cast("double"))
        .withColumn("is_post_launch", (F.col("event_ts") >= F.lit(LAUNCH)).cast("boolean"))
    )


@dlt.table(comment="De-duplicated experiment assignments (one row per user per experiment).")
def silver_experiment_assignments():
    w = "row_number() over (partition by experiment_id, user_id order by _ingested_at desc)"
    return (
        dlt.read("bronze_experiment_assignments")
        .withColumn("_rn", F.expr(w))
        .filter("_rn = 1")
        .drop("_rn")
        .withColumn("assigned_ts", F.to_timestamp("assigned_ts"))
    )


# --------------------------------------------------------------- GOLD (features + labels)
@dlt.table(
    comment="One row per user: pre-launch behavioral features, experiment variants, and "
    "DERIVED adoption labels. Training table for the next-best-feature propensity model."
)
def gold_user_features():
    events = dlt.read("silver_events")
    users = dlt.read("silver_users")
    assign = dlt.read("silver_experiment_assignments")

    pre = events.filter("is_post_launch = false")
    post = events.filter("is_post_launch = true")

    # ---- pre-launch behavioral features (the model inputs) ----
    feats = pre.groupBy("user_id").agg(
        F.count("*").alias("events_total"),
        F.sum(F.when(F.col("event_type") == "trade", 1).otherwise(0)).alias("trades_total"),
        F.sum(F.when(F.col("event_type") == "login", 1).otherwise(0)).alias("logins_total"),
        F.sum(F.when(F.col("event_type") == "deposit", F.col("amount_usd")).otherwise(0.0)).alias("deposit_total_usd"),
        F.countDistinct("session_id").alias("sessions_total"),
        F.countDistinct(F.to_date("event_ts")).alias("active_days"),
        F.max("event_ts").alias("last_activity_ts"),
    )
    # per-new-product pre-launch affinity (view/trade/interaction counts)
    for p in NEW_PRODUCTS:
        pc = (
            pre.filter(F.col("product") == p)
            .groupBy("user_id")
            .agg(F.count("*").alias(f"pre_{p}_interactions"))
        )
        feats = feats.join(pc, "user_id", "left")

    # ---- derived adoption labels (post-launch trade on the new product) ----
    for p in NEW_PRODUCTS:
        ad = (
            post.filter((F.col("product") == p) & (F.col("event_type") == "trade"))
            .groupBy("user_id")
            .agg((F.count("*") > 0).cast("int").alias(f"adopted_{p}"))
        )
        feats = feats.join(ad, "user_id", "left")

    # ---- experiment variant per new product (pivot) ----
    variants = (
        assign.groupBy("user_id")
        .pivot("product", NEW_PRODUCTS)
        .agg(F.first("variant"))
    )
    for p in NEW_PRODUCTS:
        variants = variants.withColumnRenamed(p, f"variant_{p}")

    out = (
        users.join(feats, "user_id", "left")
        .join(variants, "user_id", "left")
        .withColumn("tenure_days", F.datediff(F.lit(LAUNCH), F.col("signup_date")))
    )
    # null-fill numeric feature/label columns
    fill_cols = ["events_total", "trades_total", "logins_total", "deposit_total_usd",
                 "sessions_total", "active_days"]
    fill_cols += [f"pre_{p}_interactions" for p in NEW_PRODUCTS]
    fill_cols += [f"adopted_{p}" for p in NEW_PRODUCTS]
    out = out.fillna(0, subset=fill_cols)
    return out


@dlt.table(comment="Per-experiment / per-variant adoption rate and treatment lift (for BI/Genie).")
def gold_experiment_results():
    feats = dlt.read("gold_user_features")
    frames = []
    for p in NEW_PRODUCTS:
        f = (
            feats.groupBy(F.col(f"variant_{p}").alias("variant"))
            .agg(
                F.lit(f"{p}_launch_2026q2").alias("experiment_id"),
                F.lit(p).alias("product"),
                F.count("*").alias("users"),
                F.sum(F.col(f"adopted_{p}")).alias("adopters"),
                F.round(F.avg(F.col(f"adopted_{p}")) * 100, 2).alias("adoption_rate_pct"),
            )
            .filter("variant IS NOT NULL")
        )
        frames.append(f)
    res = frames[0]
    for f in frames[1:]:
        res = res.unionByName(f)
    return res.select("experiment_id", "product", "variant", "users", "adopters", "adoption_rate_pct")
