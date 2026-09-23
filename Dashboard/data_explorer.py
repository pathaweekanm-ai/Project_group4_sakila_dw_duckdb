"""
Sakila DW — Data Explorer
Browses EVERY table/view actually present in the warehouse, across all three
schemas: main_raw (16 source tables loaded via dbt seed), main_staging
(views — cleaned/typed staging layer), and main_marts (the 6 dimensions +
bridge + 2 facts that Dashboard/app.py's business-question charts read from).

This is a companion to app.py, not a replacement: app.py answers the 16
business questions from main_marts only; this app is a general-purpose
browser so the team can inspect any table at any layer of the pipeline
(row counts, columns/types, a live preview, quick filters, CSV export).

Same self-building behaviour as app.py: if sakila_dw.duckdb doesn't exist
yet (e.g. a fresh clone), this runs `dbt seed` + `dbt run` itself.
"""

import os
import subprocess

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

# ── paths — identical convention to app.py ──────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DBT_PROJECT_DIR = os.path.normpath(os.path.join(APP_DIR, "..", "sakila_dw_duckdb"))
DB_PATH = os.path.join(DBT_PROJECT_DIR, "sakila_dw.duckdb")
PROFILES_DIR = os.path.join(DBT_PROJECT_DIR, ".dashboard_profile")

PROFILES_YML = """sakila_dw_duckdb:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: sakila_dw.duckdb
      threads: 4
"""

# ── brand palette — same 4-tone theme as app.py (navy/sky/cream/pink) ───────
PAGE_BG = "#ffffff"
CARD_BG = "#ffffff"
TEXT_PRIMARY = "#1f2b4d"
TEXT_SECONDARY = "#5b6b93"
GRID_COLOR = "#eaf6fc"
AXIS_COLOR = "#d6ecf9"
SERIES = ["#cfe3e2", "#ec9baf", "#85bbe4", "#8a719e", "#9bcfe8", "#d187a2", "#b9abca", "#425b9a"]

SCHEMA_COLOR = {
    "main_raw": "#76c0ec",       # sky blue — raw source data
    "main_staging": "#ff95a5",   # pink — cleaned/typed views
    "main_marts": "#425b9a",     # navy — final dimensional model
    "main": "#8a719e",           # violet — misc (e.g. analyses views)
}
SCHEMA_LABEL_TH = {
    "main_raw": "Raw (ต้นฉบับจาก dbt seed)",
    "main_staging": "Staging (view ทำความสะอาด/แปลงชนิดข้อมูล)",
    "main_marts": "Marts (Dimension/Fact พร้อมใช้งาน)",
    "main": "อื่นๆ",
}


@st.cache_resource(show_spinner=False)
def ensure_warehouse_built():
    """Build the DuckDB warehouse (seed -> staging -> marts) if it isn't there yet."""
    if os.path.exists(DB_PATH):
        return "already built"

    os.makedirs(PROFILES_DIR, exist_ok=True)
    profiles_path = os.path.join(PROFILES_DIR, "profiles.yml")
    if not os.path.exists(profiles_path):
        with open(profiles_path, "w") as f:
            f.write(PROFILES_YML)

    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = PROFILES_DIR

    for cmd in (["dbt", "seed"], ["dbt", "run"]):
        result = subprocess.run(
            cmd, cwd=DBT_PROJECT_DIR, env=env,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"`{' '.join(cmd)}` failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
            )
    return "built now"


@st.cache_resource(show_spinner=False)
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


@st.cache_data(show_spinner=False)
def list_tables() -> pd.DataFrame:
    """Every base table/view in the warehouse, one row per (schema, table)."""
    con = get_connection()
    return con.sql("""
        select table_schema as "schema", table_name as "table", table_type as "type"
        from information_schema.tables
        where table_schema not in ('information_schema', 'pg_catalog')
        order by table_schema, table_name
    """).df()


@st.cache_data(show_spinner=False)
def table_row_count(schema: str, table: str) -> int:
    con = get_connection()
    return con.sql(f'select count(*) from "{schema}"."{table}"').fetchone()[0]


@st.cache_data(show_spinner=False)
def table_columns(schema: str, table: str) -> pd.DataFrame:
    con = get_connection()
    return con.execute("""
        select column_name as "คอลัมน์", data_type as "ชนิดข้อมูล", is_nullable as "Nullable"
        from information_schema.columns
        where table_schema = ? and table_name = ?
        order by ordinal_position
    """, [schema, table]).df()


@st.cache_data(show_spinner=False)
def table_preview(schema: str, table: str, limit: int) -> pd.DataFrame:
    con = get_connection()
    return con.sql(f'select * from "{schema}"."{table}" limit {int(limit)}').df()


@st.cache_data(show_spinner=False)
def full_table(schema: str, table: str) -> pd.DataFrame:
    con = get_connection()
    return con.sql(f'select * from "{schema}"."{table}"').df()


def _plain_layout(fig, title=None, y_title=None, x_title=None):
    fig.update_layout(
        title=title or "",
        showlegend=False,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        plot_bgcolor=CARD_BG,
        paper_bgcolor=CARD_BG,
        font=dict(family="Inter, sans-serif", size=13, color=TEXT_SECONDARY),
        xaxis=dict(title=x_title, showgrid=False, showline=True, linecolor=AXIS_COLOR, color=TEXT_SECONDARY),
        yaxis=dict(title=y_title, showgrid=True, gridcolor=GRID_COLOR, zeroline=False, color=TEXT_SECONDARY),
        title_font=dict(color=TEXT_PRIMARY),
    )
    return fig


st.set_page_config(page_title="Sakila DW — Data Explorer", layout="wide", page_icon="🗂️")

with st.spinner("กำลังเตรียมคลังข้อมูล (สร้างครั้งแรกอาจใช้เวลาสักครู่)..."):
    build_status = ensure_warehouse_built()

st.title("🗂️ Sakila DW — Data Explorer")
st.caption(
    "แสดงตารางทั้งหมดที่มีอยู่จริงในคลังข้อมูล ทั้ง 3 ชั้น: **main_raw** (ต้นฉบับ 16 ตารางจาก dbt seed) → "
    "**main_staging** (view ทำความสะอาด/แปลงชนิดข้อมูล) → **main_marts** (Dimension/Fact พร้อมใช้งานจริง — "
    "ชุดเดียวกับที่แดชบอร์ดคำถามธุรกิจใน app.py ใช้)"
)

tables_df = list_tables()
counts = []
for _, r in tables_df.iterrows():
    try:
        counts.append(table_row_count(r["schema"], r["table"]))
    except Exception:
        counts.append(None)
tables_df["จำนวนแถว"] = counts
tables_df["schema_label"] = tables_df["schema"].map(lambda s: SCHEMA_LABEL_TH.get(s, s))

# ── overview metrics ─────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("จำนวนตาราง/วิวทั้งหมด", len(tables_df))
for col, schema in zip((m2, m3, m4), ("main_raw", "main_staging", "main_marts")):
    n = len(tables_df[tables_df["schema"] == schema])
    col.metric(SCHEMA_LABEL_TH[schema].split(" (")[0], n)

st.divider()

overview_tab, detail_tab = st.tabs(["📋 ภาพรวมทุกตาราง", "🔍 ดูรายละเอียดทีละตาราง"])

# ════════════════════════════════════════════════════════════════════════
# ภาพรวม — bar chart จำนวนแถวของทุกตาราง แยกสีตาม schema
# ════════════════════════════════════════════════════════════════════════
with overview_tab:
    schema_filter = st.multiselect(
        "กรองตาม schema", sorted(tables_df["schema"].unique()),
        default=sorted(tables_df["schema"].unique()),
        format_func=lambda s: SCHEMA_LABEL_TH.get(s, s),
    )
    view_df = tables_df[tables_df["schema"].isin(schema_filter)].sort_values(["schema", "table"])

    fig = px.bar(
        view_df, x="table", y="จำนวนแถว", color="schema",
        color_discrete_map=SCHEMA_COLOR, text="จำนวนแถว",
        labels={"table": "", "schema": "Schema"},
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    _plain_layout(fig, y_title="จำนวนแถว")
    fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    fig.update_xaxes(tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        view_df[["schema", "table", "type", "จำนวนแถว"]].rename(
            columns={"schema": "Schema", "table": "ตาราง", "type": "ประเภท"}
        ),
        hide_index=True, use_container_width=True,
    )

# ════════════════════════════════════════════════════════════════════════
# รายละเอียดทีละตาราง — เลือก schema/ตาราง แล้วดู columns + preview + export
# ════════════════════════════════════════════════════════════════════════
with detail_tab:
    c1, c2 = st.columns([1, 2])
    with c1:
        pick_schema = st.selectbox(
            "1) เลือก schema", sorted(tables_df["schema"].unique()),
            format_func=lambda s: SCHEMA_LABEL_TH.get(s, s),
        )
    table_options = sorted(tables_df.loc[tables_df["schema"] == pick_schema, "table"].tolist())
    with c2:
        pick_table = st.selectbox("2) เลือกตาราง", table_options)

    row_count = table_row_count(pick_schema, pick_table)
    cols_df = table_columns(pick_schema, pick_table)

    d1, d2 = st.columns(2)
    d1.metric("จำนวนแถว", f"{row_count:,}")
    d2.metric("จำนวนคอลัมน์", len(cols_df))

    st.markdown(f"**โครงสร้างคอลัมน์ของ `{pick_schema}.{pick_table}`**")
    st.dataframe(cols_df, hide_index=True, use_container_width=True)

    st.markdown("**ตัวอย่างข้อมูล (Preview)**")
    limit = st.select_slider("จำนวนแถวที่จะแสดง", options=[10, 25, 50, 100, 500, 1000], value=25)
    preview_df = table_preview(pick_schema, pick_table, limit)

    search_term = st.text_input("ค้นหาคำในตาราง (ค้นหาแบบข้อความในทุกคอลัมน์ของแถวที่แสดงอยู่)", "")
    if search_term:
        mask = preview_df.astype(str).apply(
            lambda col: col.str.contains(search_term, case=False, na=False)
        ).any(axis=1)
        preview_df = preview_df[mask]

    st.dataframe(preview_df, use_container_width=True)
    st.caption(f"แสดง {len(preview_df):,} จาก {row_count:,} แถวทั้งหมด")

    st.download_button(
        "⬇️ ดาวน์โหลดทั้งตารางเป็น CSV",
        data=full_table(pick_schema, pick_table).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{pick_schema}.{pick_table}.csv",
        mime="text/csv",
    )