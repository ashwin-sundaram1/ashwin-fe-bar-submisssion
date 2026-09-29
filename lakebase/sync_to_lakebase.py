"""
Meridian Trade — sync recommendations into Lakebase (Postgres) for operational serving.

Loads the gold `user_recommendations` table into a native Postgres table in the Lakebase
instance `meridian-lakebase`, indexed on user_id, so the Databricks App can do low-latency
point lookups ("show me this user's next-best-feature + nudge") instead of scanning Delta.

Runs on Databricks serverless (needs psycopg2-binary in the environment).
"""
import time
import uuid
import psycopg2
from psycopg2.extras import execute_values
from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient

INSTANCE = "meridian-lakebase"
LOGICAL_DB = "databricks_postgres"
PG_TABLE = "user_recommendations"
SOURCE = "ashwin_tvf_testing_catalog.meridian_trade.user_recommendations"

COLUMNS = [
    "user_id", "tier", "region", "age_band", "risk_profile",
    "recommended_product", "propensity_score", "expected_annual_value_usd",
    "targeting_decile", "prob_crypto", "prob_options", "prob_agentic",
    "nudge_text", "nudge_source",
]


def main():
    spark = SparkSession.builder.getOrCreate()
    w = WorkspaceClient()

    # The `database` SDK surface may be absent on older serverless SDKs; call REST directly.
    inst = w.api_client.do("GET", f"/api/2.0/database/instances/{INSTANCE}")
    host = inst["read_write_dns"]
    user = w.current_user.me().user_name
    cred = w.api_client.do(
        "POST", "/api/2.0/database/credentials",
        body={"request_id": str(uuid.uuid4()), "instance_names": [INSTANCE]},
    )
    token = cred["token"]
    print(f"Lakebase host: {host}  db: {LOGICAL_DB}  user: {user}")

    pdf = spark.table(SOURCE).select(*COLUMNS).toPandas()
    print(f"Loaded {len(pdf):,} recommendations from {SOURCE}")

    conn = psycopg2.connect(
        host=host, port=5432, dbname=LOGICAL_DB, user=user,
        password=token, sslmode="require",
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(f"DROP TABLE IF EXISTS {PG_TABLE}")
    cur.execute(
        f"""
        CREATE TABLE {PG_TABLE} (
            user_id TEXT PRIMARY KEY,
            tier TEXT, region TEXT, age_band TEXT, risk_profile TEXT,
            recommended_product TEXT,
            propensity_score DOUBLE PRECISION,
            expected_annual_value_usd DOUBLE PRECISION,
            targeting_decile INT,
            prob_crypto DOUBLE PRECISION,
            prob_options DOUBLE PRECISION,
            prob_agentic DOUBLE PRECISION,
            nudge_text TEXT,
            nudge_source TEXT
        )
        """
    )

    rows = [tuple(None if (isinstance(v, float) and v != v) else v for v in r)
            for r in pdf[COLUMNS].itertuples(index=False, name=None)]
    execute_values(
        cur,
        f"INSERT INTO {PG_TABLE} ({','.join(COLUMNS)}) VALUES %s",
        rows, page_size=1000,
    )
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_reco_product ON {PG_TABLE}(recommended_product)")
    cur.execute(f"SELECT count(*) FROM {PG_TABLE}")
    print(f"Rows in Postgres {PG_TABLE}: {cur.fetchone()[0]:,}")

    # ---- demonstrate low-latency point lookups (operational serving) ----
    sample_ids = [r[0] for r in rows[:5]]
    print("\n=== LOW-LATENCY POINT LOOKUPS (Lakebase Postgres) ===")
    for uid in sample_ids:
        t0 = time.perf_counter()
        cur.execute(
            f"SELECT user_id, recommended_product, round(propensity_score::numeric,3), nudge_source "
            f"FROM {PG_TABLE} WHERE user_id = %s", (uid,)
        )
        row = cur.fetchone()
        ms = (time.perf_counter() - t0) * 1000
        print(f"  {row[0]}  -> {row[1]:8s}  score={row[2]}  ({row[3]})  [{ms:.1f} ms]")

    print("\n=== TARGETING QUERY (top crypto prospects, indexed) ===")
    t0 = time.perf_counter()
    cur.execute(
        f"SELECT user_id, round(propensity_score::numeric,3) FROM {PG_TABLE} "
        f"WHERE recommended_product='crypto' ORDER BY propensity_score DESC LIMIT 5"
    )
    top = cur.fetchall()
    ms = (time.perf_counter() - t0) * 1000
    for r in top:
        print(f"  {r[0]}  score={r[1]}")
    print(f"  (query {ms:.1f} ms)")

    cur.close()
    conn.close()
    print("\nLakebase sync complete.")


if __name__ == "__main__":
    main()
