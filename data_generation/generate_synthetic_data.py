"""
Meridian Trade — synthetic raw data generator (runs on Databricks serverless).

Generates a realistic, *synthetic* retail-trading dataset with learnable signal for the
downstream propensity model, and lands it as raw files in a Unity Catalog Volume so the
Lakeflow Declarative Pipeline can ingest it with Auto Loader.

Raw outputs (landing zone):
  landing/users/               users_*.csv        (account dim; email/account_ref are PII)
  landing/events/              events_*.json      (activity/trade event stream)
  landing/experiment_assignments/  assignments_*.csv
  landing/product_catalog/     product_catalog.json

NO real customer data is used. Everything here is generated from numpy RNG.
"""
import os
import json
import datetime as dt
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession

# ---------------------------------------------------------------- config
CATALOG = "ashwin_tvf_testing_catalog"
SCHEMA = "meridian_trade"
VOLUME = "landing"
BASE = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

N_USERS = 10_000
SEED = 42
# Observation window: history "as of" experiment launch, then a post-launch window
NOW = dt.date(2026, 9, 1)
EXPERIMENT_LAUNCH = dt.date(2026, 6, 1)      # experiments assigned here
POST_WINDOW_DAYS = 90                         # adoption observed in launch..launch+90d
HISTORY_START = dt.date(2023, 1, 1)

PRODUCTS_CORE = ["equities", "etf", "mutual_funds"]        # already-owned staples
PRODUCTS_NEW = ["crypto", "options", "agentic"]            # the three launches
EVENT_TYPES = ["login", "view_product", "trade", "deposit", "withdrawal", "feature_interaction"]

rng = np.random.default_rng(SEED)


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def build_users(n):
    uids = np.array([f"MER{100000 + i}" for i in range(n)])
    tiers = rng.choice(["bronze", "silver", "gold", "platinum"], size=n, p=[0.45, 0.30, 0.18, 0.07])
    regions = rng.choice(
        ["US-West", "US-East", "US-Central", "US-South"], size=n, p=[0.3, 0.3, 0.2, 0.2]
    )
    age_bands = rng.choice(
        ["18-25", "26-35", "36-50", "51-65", "65+"], size=n, p=[0.22, 0.30, 0.26, 0.15, 0.07]
    )
    risk = rng.choice(["conservative", "moderate", "aggressive"], size=n, p=[0.35, 0.45, 0.20])
    kyc = rng.choice(["verified", "pending"], size=n, p=[0.9, 0.1])
    signup_offsets = rng.integers(0, (EXPERIMENT_LAUNCH - HISTORY_START).days, size=n)
    signup_dates = [HISTORY_START + dt.timedelta(days=int(o)) for o in signup_offsets]
    # synthetic PII (to be masked in Unity Catalog)
    emails = np.array([f"user{100000 + i}@meridiantrade-example.com" for i in range(n)])
    account_ref = np.array([f"ACCT-{rng.integers(10**9, 10**10 - 1)}" for _ in range(n)])
    balances = np.round(
        np.maximum(500, rng.lognormal(mean=9.2, sigma=1.1, size=n)), 2
    )  # account balance USD

    df = pd.DataFrame(
        {
            "user_id": uids,
            "signup_date": [d.isoformat() for d in signup_dates],
            "tier": tiers,
            "region": regions,
            "age_band": age_bands,
            "risk_profile": risk,
            "kyc_status": kyc,
            "account_balance_usd": balances,
            "email": emails,
            "account_ref": account_ref,
        }
    )
    return df, signup_dates


def build_events_and_labels(users, signup_dates):
    """Generate the pre-launch activity stream plus post-launch adoption trades.

    Adoption of each NEW product is a Bernoulli draw whose probability depends on user
    attributes + pre-period affinity + an experiment treatment lift. That gives the gold
    layer a genuine, learnable signal (labels are DERIVED from events in silver/gold).
    """
    n = len(users)
    tier_rank = users["tier"].map({"bronze": 0, "silver": 1, "gold": 2, "platinum": 3}).to_numpy()
    risk_rank = users["risk_profile"].map(
        {"conservative": 0, "moderate": 1, "aggressive": 2}
    ).to_numpy()
    age_young = users["age_band"].isin(["18-25", "26-35"]).to_numpy().astype(float)
    bal = users["account_balance_usd"].to_numpy()
    bal_z = (np.log(bal) - np.log(bal).mean()) / np.log(bal).std()

    # base engagement (events per day) rises with tier + a per-user random factor
    engagement = np.clip(0.15 + 0.12 * tier_rank + rng.normal(0, 0.05, n), 0.03, None)

    # per-user affinity for each NEW product (latent, drives pre-period views AND adoption)
    affinity = {
        "crypto": 0.9 * risk_rank + 1.1 * age_young + 0.2 * bal_z + rng.normal(0, 0.6, n),
        "options": 0.7 * risk_rank + 0.9 * bal_z + 0.5 * tier_rank + rng.normal(0, 0.6, n),
        "agentic": 0.6 * age_young + 0.5 * tier_rank + 0.4 * risk_rank + rng.normal(0, 0.6, n),
    }

    # experiment treatment assignment (control/treatment) per NEW product
    assign = {p: rng.choice(["control", "treatment"], size=n, p=[0.5, 0.5]) for p in PRODUCTS_NEW}
    treat_lift = {"crypto": 0.8, "options": 0.7, "agentic": 0.9}

    # adoption probability + draw
    adopt = {}
    for p in PRODUCTS_NEW:
        logit = -2.3 + 0.85 * affinity[p]
        logit = logit + treat_lift[p] * (assign[p] == "treatment").astype(float)
        prob = _sigmoid(logit)
        adopt[p] = rng.random(n) < prob

    events = []
    launch = EXPERIMENT_LAUNCH
    hist_days = (launch - HISTORY_START).days

    for i in range(n):
        uid = users["user_id"].iat[i]
        su = signup_dates[i]
        active_from = max(su, HISTORY_START)
        span = (launch - active_from).days
        if span <= 0:
            span = 1
        # number of pre-launch events for this user
        n_ev = int(rng.poisson(engagement[i] * span))
        n_ev = min(n_ev, 400)  # cap
        # pre-launch events
        for _ in range(n_ev):
            day = active_from + dt.timedelta(days=int(rng.integers(0, span)))
            secs = int(rng.integers(0, 86400))
            ts = dt.datetime.combine(day, dt.time()) + dt.timedelta(seconds=secs)
            et = rng.choice(
                EVENT_TYPES, p=[0.34, 0.26, 0.18, 0.09, 0.05, 0.08]
            )
            # product distribution: core-heavy pre-launch, some affinity-driven new-product views
            if et in ("view_product", "trade", "feature_interaction"):
                if rng.random() < 0.25:
                    # bias toward the user's highest-affinity new product
                    aff_scores = np.array([affinity[p][i] for p in PRODUCTS_NEW])
                    prod = PRODUCTS_NEW[int(np.argmax(aff_scores + rng.normal(0, 0.5, 3)))]
                else:
                    prod = rng.choice(PRODUCTS_CORE)
            else:
                prod = None
            amt = None
            if et == "trade":
                amt = round(float(np.abs(rng.normal(2000, 1500))), 2)
            elif et in ("deposit", "withdrawal"):
                amt = round(float(np.abs(rng.normal(1200, 900))), 2)
            events.append(
                {
                    "event_id": f"E{i:06d}{len(events):09d}",
                    "user_id": uid,
                    "event_ts": ts.isoformat(sep=" ", timespec="seconds"),
                    "event_type": str(et),
                    "product": prod,
                    "amount_usd": amt,
                    "session_id": f"S{i:06d}-{int(rng.integers(0, 9999)):04d}",
                }
            )
        # post-launch adoption trades (the outcome signal)
        for p in PRODUCTS_NEW:
            if adopt[p][i]:
                n_adopt_ev = int(1 + rng.poisson(2))
                for _ in range(n_adopt_ev):
                    day = launch + dt.timedelta(days=int(rng.integers(1, POST_WINDOW_DAYS)))
                    ts = dt.datetime.combine(day, dt.time()) + dt.timedelta(
                        seconds=int(rng.integers(0, 86400))
                    )
                    events.append(
                        {
                            "event_id": f"E{i:06d}{len(events):09d}",
                            "user_id": uid,
                            "event_ts": ts.isoformat(sep=" ", timespec="seconds"),
                            "event_type": "trade",
                            "product": p,
                            "amount_usd": round(float(np.abs(rng.normal(1500, 1200))), 2),
                            "session_id": f"S{i:06d}-{int(rng.integers(0, 9999)):04d}",
                        }
                    )

    events_df = pd.DataFrame(events)

    # experiment assignment rows (long format: one row per user per experiment)
    arows = []
    for p in PRODUCTS_NEW:
        for i in range(n):
            arows.append(
                {
                    "experiment_id": f"{p}_launch_2026q2",
                    "product": p,
                    "user_id": users["user_id"].iat[i],
                    "variant": assign[p][i],
                    "assigned_ts": dt.datetime.combine(launch, dt.time()).isoformat(sep=" "),
                }
            )
    assignments_df = pd.DataFrame(arows)
    return events_df, assignments_df


def product_catalog():
    return [
        {"product": "equities", "category": "core", "launch": "legacy", "fee_bps": 0,
         "description": "Commission-free US equities."},
        {"product": "etf", "category": "core", "launch": "legacy", "fee_bps": 0,
         "description": "Exchange-traded funds."},
        {"product": "mutual_funds", "category": "core", "launch": "legacy", "fee_bps": 25,
         "description": "Managed mutual funds."},
        {"product": "crypto", "category": "new_launch", "launch": "2026-06-01", "fee_bps": 40,
         "description": "Spot crypto trading (BTC, ETH, + majors)."},
        {"product": "options", "category": "new_launch", "launch": "2026-06-01", "fee_bps": 30,
         "description": "Equity options with tiered approval."},
        {"product": "agentic", "category": "new_launch", "launch": "2026-06-01", "fee_bps": 50,
         "description": "AI agentic trading assistant (auto-strategies)."},
    ]


def main():
    spark = SparkSession.builder.getOrCreate()
    print(f"Spark version: {spark.version}")
    print(f"Landing base: {BASE}")

    users_df, signup_dates = build_users(N_USERS)
    print(f"Generated users: {len(users_df):,}")

    events_df, assignments_df = build_events_and_labels(users_df, signup_dates)
    print(f"Generated events: {len(events_df):,}")
    print(f"Generated experiment assignment rows: {len(assignments_df):,}")

    # ---- write raw files to the UC Volume (Auto Loader will pick these up) ----
    # users -> CSV
    (
        spark.createDataFrame(users_df)
        .repartition(2)
        .write.mode("overwrite")
        .option("header", True)
        .csv(f"{BASE}/users")
    )
    # events -> JSON (amount_usd/product nullable)
    (
        spark.createDataFrame(events_df)
        .repartition(6)
        .write.mode("overwrite")
        .json(f"{BASE}/events")
    )
    # experiment assignments -> CSV
    (
        spark.createDataFrame(assignments_df)
        .repartition(2)
        .write.mode("overwrite")
        .option("header", True)
        .csv(f"{BASE}/experiment_assignments")
    )
    # product catalog -> single JSON file written via driver
    cat = product_catalog()
    cat_path = f"{BASE}/product_catalog/product_catalog.json"
    os.makedirs(f"{BASE}/product_catalog", exist_ok=True)
    with open(cat_path, "w") as f:
        for row in cat:
            f.write(json.dumps(row) + "\n")
    print(f"Wrote product catalog: {len(cat)} products -> {cat_path}")

    # ---- quick sanity summary (shows in job logs = execution evidence) ----
    # adoption = a POST-launch trade on a new product (this is the derived label signal)
    launch_ts = str(EXPERIMENT_LAUNCH)
    post = events_df[events_df["event_ts"] >= launch_ts]
    print("\n=== ADOPTION SIGNAL SANITY (post-launch trades on new products) ===")
    for p in PRODUCTS_NEW:
        mask = (post["product"] == p) & (post["event_type"] == "trade")
        adopters = post.loc[mask, "user_id"].nunique()
        print(f"  {p:8s}: {adopters:,} adopters ({100 * adopters / N_USERS:.1f}% of users)")
    print("\nData generation completed successfully.")


if __name__ == "__main__":
    main()
