"""
Meridian Trade — next-best-feature propensity models (ML) + batch scoring.

Trains one binary propensity model per NEW product (crypto/options/agentic) that predicts
organic adoption from pre-launch behavioral features + user attributes. Experiment variant
is deliberately EXCLUDED from features (no experiment leakage) — the model scores the whole
user base for the *next* rollout wave. Models are logged to MLflow and registered to Unity
Catalog, then every user is scored and the results written to a Delta table for serving.

Runs on Databricks serverless.
"""
import mlflow
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

CATALOG = "ashwin_tvf_testing_catalog"
SCHEMA = "meridian_trade"
PRODUCTS = ["crypto", "options", "agentic"]
FEE_BPS = {"crypto": 40, "options": 30, "agentic": 50}

CAT_FEATURES = ["tier", "region", "age_band", "risk_profile", "kyc_status"]
NUM_FEATURES = [
    "account_balance_usd", "events_total", "trades_total", "logins_total",
    "deposit_total_usd", "sessions_total", "active_days", "tenure_days",
    "pre_crypto_interactions", "pre_options_interactions", "pre_agentic_interactions",
]
FEATURES = CAT_FEATURES + NUM_FEATURES


def build_pipeline():
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
            ("num", "passthrough", NUM_FEATURES),
        ]
    )
    return Pipeline(
        [("prep", pre),
         ("clf", GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.1,
                                            random_state=42))]
    )


def main():
    spark = SparkSession.builder.getOrCreate()
    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_experiment(f"/Users/ashwin.sundaram@databricks.com/meridian_propensity")

    pdf = spark.table(f"{CATALOG}.{SCHEMA}.gold_user_features").toPandas()
    print(f"Loaded gold_user_features: {len(pdf):,} rows")
    for c in NUM_FEATURES:
        pdf[c] = pd.to_numeric(pdf[c], errors="coerce").fillna(0)

    scores = pdf[["user_id"]].copy()
    summary = []

    for product in PRODUCTS:
        label = f"adopted_{product}"
        X = pdf[FEATURES]
        y = pdf[label].astype(int)
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        pipe = build_pipeline()
        with mlflow.start_run(run_name=f"propensity_{product}") as run:
            pipe.fit(X_tr, y_tr)
            p_te = pipe.predict_proba(X_te)[:, 1]
            auc = roc_auc_score(y_te, p_te)
            ap = average_precision_score(y_te, p_te)
            acc = accuracy_score(y_te, (p_te >= 0.5).astype(int))
            base_rate = float(y.mean())

            mlflow.log_params({"product": product, "n_estimators": 200, "max_depth": 3,
                               "n_features": len(FEATURES), "n_train": len(X_tr)})
            mlflow.log_metrics({"roc_auc": auc, "avg_precision": ap, "accuracy": acc,
                                "base_rate": base_rate})
            model_name = f"{CATALOG}.{SCHEMA}.propensity_{product}"
            mlflow.sklearn.log_model(
                pipe, artifact_path="model", registered_model_name=model_name,
                input_example=X_tr.head(3),
                # models are produced in-pipeline by us, so these sklearn internals are trusted
                skops_trusted_types=[
                    "sklearn.tree._tree.Tree",
                    "sklearn.compose._column_transformer._RemainderColsList",
                ],
            )
            print(f"[{product}] AUC={auc:.3f}  AP={ap:.3f}  acc={acc:.3f}  "
                  f"base_rate={base_rate:.3f}  -> registered {model_name}")
            summary.append((product, auc, ap, acc, base_rate))

        # score ALL users with this product's model
        scores[f"prob_{product}"] = pipe.predict_proba(pdf[FEATURES])[:, 1]

    # ---- assemble recommendations: top product per user + business value ----
    prob_cols = [f"prob_{p}" for p in PRODUCTS]
    scores["recommended_product"] = scores[prob_cols].idxmax(axis=1).str.replace("prob_", "", regex=False)
    scores["propensity_score"] = scores[prob_cols].max(axis=1)
    # simple expected annual value: propensity * assumed annual traded notional * fee
    ASSUMED_ANNUAL_NOTIONAL = 25000.0
    fee_by_row = scores["recommended_product"].map(lambda p: FEE_BPS[p] / 10000.0)
    scores["expected_annual_value_usd"] = (
        scores["propensity_score"] * ASSUMED_ANNUAL_NOTIONAL * fee_by_row
    ).round(2)

    # attach a few context columns for the app / nudge generation
    ctx = pdf[["user_id", "tier", "region", "age_band", "risk_profile",
               "pre_crypto_interactions", "pre_options_interactions",
               "pre_agentic_interactions", "trades_total", "active_days"]]
    out = ctx.merge(scores, on="user_id", how="inner")

    # targeting priority: 1 = highest propensity decile
    out["targeting_decile"] = (
        11 - pd.qcut(out["propensity_score"].rank(method="first"), 10, labels=False) - 1
    ).astype(int)

    sdf = spark.createDataFrame(out)
    (sdf.write.mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(f"{CATALOG}.{SCHEMA}.user_recommendations_base"))
    print(f"\nWrote user_recommendations_base: {sdf.count():,} rows")

    print("\n=== MODEL SUMMARY ===")
    print(f"{'product':10s} {'AUC':>6s} {'AvgPrec':>8s} {'Acc':>6s} {'BaseRate':>9s}")
    for p, auc, ap, acc, br in summary:
        print(f"{p:10s} {auc:6.3f} {ap:8.3f} {acc:6.3f} {br:9.3f}")

    print("\n=== RECOMMENDATION MIX ===")
    print(out["recommended_product"].value_counts().to_string())
    print("\nDone.")


if __name__ == "__main__":
    main()
