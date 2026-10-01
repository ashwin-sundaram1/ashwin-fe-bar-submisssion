"""
Meridian Trade — Growth Experimentation & Next-Best-Feature app (Databricks App).

Surfaces the whole data journey to the business:
  • Executive Overview  — experiment lift, recommendation mix, expected value, funnel
  • User Targeting       — per-user next-best-feature lookup served from Lakebase (low latency)
  • Ask Genie            — natural-language Q&A over the gold tables via the Genie API

Data plane:
  - Aggregates/charts  -> SQL warehouse over ashwin_tvf_testing_catalog.meridian_trade.*
  - Per-user lookup    -> Lakebase (Postgres) point lookup, with SQL-warehouse fallback
  - NL questions       -> Genie Conversation API
"""
import time
import uuid
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from databricks import sql as dbsql
from databricks.sdk.core import Config

# ----------------------------------------------------------------- config
CATALOG = "ashwin_tvf_testing_catalog"
SCHEMA = "meridian_trade"
CS = f"{CATALOG}.{SCHEMA}"
WAREHOUSE_ID = "cf801b29c96051ee"
LAKEBASE_INSTANCE = "meridian-lakebase"
LAKEBASE_DB = "databricks_postgres"
GENIE_SPACE_ID = "01f1bbfeaa791ef6be696bdc95f71237"

BRAND_GREEN = "#0B6E4F"
BRAND_GOLD = "#F2A900"
BRAND_SLATE = "#1C2B33"
PROD_COLORS = {"crypto": BRAND_GREEN, "options": BRAND_GOLD, "agentic": "#3B7DD8"}

cfg = Config()

st.set_page_config(page_title="Meridian Trade — Growth Intelligence",
                   page_icon="📈", layout="wide")

st.markdown(
    f"""
    <style>
    .stApp {{ background: #F7F9F8; }}
    .block-container {{ padding-top: 2rem; }}
    h1, h2, h3 {{ color: {BRAND_SLATE}; }}
    .mt-header {{
        background: linear-gradient(90deg, {BRAND_SLATE} 0%, {BRAND_GREEN} 100%);
        padding: 1.1rem 1.4rem; border-radius: 12px; color: white; margin-bottom: 1.2rem;
    }}
    .mt-header h1 {{ color: white; margin: 0; font-size: 1.6rem; }}
    .mt-header p {{ color: #CFE8DE; margin: .2rem 0 0; font-size: .95rem; }}
    div[data-testid="stMetric"] {{
        background: white; border: 1px solid #E4EAE7; border-radius: 12px;
        padding: 1rem 1.1rem; box-shadow: 0 1px 2px rgba(0,0,0,.04);
    }}
    div[data-testid="stMetricValue"] {{ color: {BRAND_GREEN}; }}
    .nudge-box {{
        background: #FFF8E7; border-left: 4px solid {BRAND_GOLD};
        padding: 1rem 1.2rem; border-radius: 8px; font-size: 1.02rem; color: #3a3a3a;
    }}
    .lat-badge {{ display:inline-block; background:{BRAND_GREEN}; color:white;
        padding:2px 10px; border-radius:20px; font-size:.78rem; font-weight:600; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------- data access
@st.cache_resource
def warehouse_conn():
    return dbsql.connect(
        server_hostname=cfg.host.replace("https://", ""),
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


@st.cache_data(ttl=300)
def q(sql_text: str) -> pd.DataFrame:
    with warehouse_conn().cursor() as cur:
        cur.execute(sql_text)
        cols = [c[0] for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def lakebase_lookup(user_id: str):
    """Low-latency point lookup from Lakebase Postgres. Returns (row_dict, latency_ms)."""
    import psycopg2
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    inst = w.api_client.do("GET", f"/api/2.0/database/instances/{LAKEBASE_INSTANCE}")
    cred = w.api_client.do("POST", "/api/2.0/database/credentials",
                           body={"request_id": str(uuid.uuid4()),
                                 "instance_names": [LAKEBASE_INSTANCE]})
    conn = psycopg2.connect(host=inst["read_write_dns"], port=5432, dbname=LAKEBASE_DB,
                            user=w.current_user.me().user_name, password=cred["token"],
                            sslmode="require", connect_timeout=10)
    t0 = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT user_id, tier, region, age_band, risk_profile, recommended_product, "
            "propensity_score, expected_annual_value_usd, targeting_decile, "
            "prob_crypto, prob_options, prob_agentic, nudge_text, nudge_source "
            "FROM user_recommendations WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        cols = [c[0] for c in cur.description]
    ms = (time.perf_counter() - t0) * 1000
    conn.close()
    return (dict(zip(cols, row)) if row else None), ms


def genie_ask(question: str):
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    start = w.api_client.do("POST", f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}/start-conversation",
                            body={"content": question})
    cid, mid = start["conversation_id"], start["message_id"]
    for _ in range(30):
        m = w.api_client.do(
            "GET", f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}/conversations/{cid}/messages/{mid}")
        if m.get("status") in ("COMPLETED", "FAILED"):
            break
        time.sleep(2)
    answer, sql_text = None, None
    for a in m.get("attachments", []):
        if a.get("text"):
            answer = a["text"].get("content")
        if a.get("query"):
            sql_text = a["query"].get("query")
    return answer, sql_text


# ----------------------------------------------------------------- header
st.markdown(
    """
    <div class="mt-header">
      <h1>📈 Meridian Trade — Growth Intelligence</h1>
      <p>Next-best-feature targeting &amp; experimentation for crypto, options, and the AI agentic assistant</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["  Executive Overview  ", "  User Targeting  ", "  Ask Genie  "])

# ============================================================ TAB 1: OVERVIEW
with tab1:
    exp = q(f"SELECT product, variant, users, adopters, adoption_rate_pct "
            f"FROM {CS}.gold_experiment_results ORDER BY product, variant")
    mix = q(f"SELECT recommended_product, COUNT(*) users, ROUND(AVG(propensity_score),3) avg_score, "
            f"ROUND(SUM(expected_annual_value_usd),0) exp_value "
            f"FROM {CS}.user_recommendations GROUP BY recommended_product ORDER BY exp_value DESC")
    tot_users = int(mix["users"].sum())
    tot_value = float(mix["exp_value"].sum())

    lift = (exp.pivot_table(index="product", columns="variant", values="adoption_rate_pct")
            .assign(lift=lambda d: d["treatment"] - d["control"]))
    avg_lift = lift["lift"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Users scored", f"{tot_users:,}")
    c2.metric("Avg experiment lift", f"+{avg_lift:.1f} pp")
    c3.metric("Expected annual value", f"${tot_value/1000:,.0f}K")
    top_prod = mix.iloc[0]["recommended_product"]
    c4.metric("Top recommended product", top_prod.capitalize())

    st.markdown("### Experiment results — treatment vs. control adoption")
    cc1, cc2 = st.columns([3, 2])
    with cc1:
        fig = go.Figure()
        for variant, color in [("control", "#B8C4C0"), ("treatment", BRAND_GREEN)]:
            d = exp[exp.variant == variant]
            fig.add_bar(x=d["product"], y=d["adoption_rate_pct"], name=variant.capitalize(),
                        marker_color=color, text=d["adoption_rate_pct"].map(lambda v: f"{v:.1f}%"),
                        textposition="outside")
        fig.update_layout(barmode="group", height=360, plot_bgcolor="white",
                          yaxis_title="Adoption rate (%)", legend_title="",
                          margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        st.markdown("#### Lift by product")
        ld = lift.reset_index()[["product", "control", "treatment", "lift"]]
        ld.columns = ["Product", "Control %", "Treatment %", "Lift (pp)"]
        st.dataframe(ld.style.format({"Control %": "{:.1f}", "Treatment %": "{:.1f}",
                                      "Lift (pp)": "+{:.1f}"}),
                     hide_index=True, use_container_width=True)
        st.caption("Randomized control/treatment experiments per product launch.")

    st.markdown("### Recommendation mix & expected annual fee value")
    m1, m2 = st.columns(2)
    with m1:
        figm = go.Figure(go.Pie(labels=mix["recommended_product"].str.capitalize(),
                                values=mix["users"], hole=.5,
                                marker_colors=[PROD_COLORS[p] for p in mix["recommended_product"]]))
        figm.update_layout(height=320, margin=dict(t=10, b=10), title="Users by recommended product")
        st.plotly_chart(figm, use_container_width=True)
    with m2:
        figv = go.Figure(go.Bar(x=mix["recommended_product"].str.capitalize(), y=mix["exp_value"],
                                marker_color=[PROD_COLORS[p] for p in mix["recommended_product"]],
                                text=mix["exp_value"].map(lambda v: f"${v/1000:,.0f}K"),
                                textposition="outside"))
        figv.update_layout(height=320, margin=dict(t=10, b=10), plot_bgcolor="white",
                           title="Expected annual value ($)", yaxis_title="USD")
        st.plotly_chart(figv, use_container_width=True)

    st.markdown("### Value concentration — the case for propensity targeting")
    conc = q(f"SELECT CASE WHEN targeting_decile<=3 THEN 'Top 30% (targeted)' ELSE 'Remaining 70%' END seg, "
             f"COUNT(*) users, ROUND(SUM(expected_annual_value_usd),0) exp_value "
             f"FROM {CS}.user_recommendations GROUP BY 1 ORDER BY 1")
    st.dataframe(conc.rename(columns={"seg": "Segment", "users": "Users", "exp_value": "Expected value ($)"}),
                 hide_index=True, use_container_width=True)

# ============================================================ TAB 2: TARGETING
with tab2:
    st.markdown("### Per-user next-best-feature")
    st.caption("Served from **Lakebase** (operational Postgres) for low-latency lookup.")
    ids = q(f"SELECT user_id FROM {CS}.user_recommendations ORDER BY propensity_score DESC LIMIT 200")
    cola, colb = st.columns([2, 3])
    with cola:
        user_id = st.selectbox("Select a user (top 200 by propensity)", ids["user_id"].tolist())
        manual = st.text_input("…or enter a user_id (e.g. MER104283)")
        if manual.strip():
            user_id = manual.strip()

    if user_id:
        row, latency = None, None
        served_by = "Lakebase"
        try:
            row, latency = lakebase_lookup(user_id)
        except Exception as e:
            served_by = "SQL warehouse (Lakebase unavailable)"
            df = q(f"SELECT * FROM {CS}.user_recommendations WHERE user_id='{user_id}'")
            row = df.iloc[0].to_dict() if len(df) else None

        if not row:
            st.warning("No recommendation found for that user_id.")
        else:
            if latency is not None:
                st.markdown(f'<span class="lat-badge">⚡ {served_by} · {latency:.0f} ms</span>',
                            unsafe_allow_html=True)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Recommended", str(row["recommended_product"]).capitalize())
            k2.metric("Propensity", f"{float(row['propensity_score'])*100:.0f}%")
            k3.metric("Expected value", f"${float(row['expected_annual_value_usd']):,.0f}/yr")
            k4.metric("Targeting decile", f"#{int(row['targeting_decile'])}")

            pc1, pc2 = st.columns([2, 3])
            with pc1:
                probs = {"Crypto": float(row["prob_crypto"]), "Options": float(row["prob_options"]),
                         "Agentic": float(row["prob_agentic"])}
                figp = go.Figure(go.Bar(
                    x=list(probs.values()), y=list(probs.keys()), orientation="h",
                    marker_color=[BRAND_GREEN, BRAND_GOLD, "#3B7DD8"],
                    text=[f"{v*100:.0f}%" for v in probs.values()], textposition="outside"))
                figp.update_layout(height=230, margin=dict(t=10, b=10, l=10),
                                   xaxis=dict(range=[0, 1], tickformat=".0%"),
                                   plot_bgcolor="white", title="Model propensity by product")
                st.plotly_chart(figp, use_container_width=True)
            with pc2:
                st.markdown("#### Profile")
                st.write({"Tier": row["tier"], "Region": row["region"], "Age band": row["age_band"],
                          "Risk profile": row["risk_profile"]})
            st.markdown("#### Personalized outreach nudge")
            st.markdown(f'<div class="nudge-box">{row["nudge_text"]}</div>', unsafe_allow_html=True)
            st.caption(f"Nudge source: {row['nudge_source']}")

# ============================================================ TAB 3: GENIE
with tab3:
    st.markdown("### Ask the data a question")
    st.caption("Natural-language analytics via the Meridian Trade Genie space.")
    default_q = "What is the adoption lift for each product?"
    question = st.text_input("Your question", value=default_q)
    if st.button("Ask Genie", type="primary"):
        with st.spinner("Genie is thinking…"):
            try:
                answer, sql_text = genie_ask(question)
                if answer:
                    st.success(answer)
                if sql_text:
                    with st.expander("SQL Genie generated"):
                        st.code(sql_text, language="sql")
            except Exception as e:
                st.error(f"Genie query failed: {e}")
    st.markdown("**Try:** *How many users are recommended each product?* · "
                "*Which variant had the highest crypto adoption?* · "
                "*Total expected value from the top targeting decile?*")
