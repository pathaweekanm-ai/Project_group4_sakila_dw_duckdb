"""
Sakila DVD Rental — Interactive Dashboard
Reads ONLY from the main_marts schema (Fact_Rental, Fact_Inventory, and dimensions) —
never touches main_raw / main_staging, per the assignment's dashboard requirement.

Self-building: if sakila_dw.duckdb doesn't exist yet (e.g. a fresh clone on
Streamlit Community Cloud), this app runs `dbt seed` + `dbt run` itself using a
project-local dbt profile, so it works with zero manual setup.
"""

import os
import subprocess
import sys

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── paths ──────────────────────────────────────────────────────────────────
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

# ── palette (validated — dataviz skill, references/palette.md) ─────────────
# Full 8-slot categorical order. The order is the CVD-safety mechanism —
# never reorder or cycle past slot 8.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

# Single-hue sequential ramp (blue), light -> dark, the 13 documented steps
# (100..700). Used only for genuinely ORDERED data — a value-sorted axis or
# true chronological order — never as a second encoding of an unordered
# nominal axis (that double-encodes what bar length already shows).
SEQUENTIAL = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
]

# Pastel categorical variants — light tints of the documented hues, checked
# with the dataviz skill's palette validator (node scripts/validate_palette.js):
# all slots clear the lightness band, chroma floor, and CVD checks in light
# mode; contrast lands in the WARN band, so every chart using these ships
# visible value labels on the bars (the required "relief" channel).
PASTEL5 = ["#4a8cdc", "#ee7f52", "#3dbb8e", "#eda100", "#eb8fb2"]
PASTEL7 = PASTEL5 + ["#59ae59", "#897fc6"]

# Documented diverging pair (blue <-> red) for "which side of zero" charts.
DIVERGE_NEG = "#2a78d6"  # early / negative side
DIVERGE_POS = "#e34948"  # late / positive side


def _lerp_hex(a, b, t):
    ar, ag, ab_ = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    br, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    bch = round(ab_ + (bb - ab_) * t)
    return f"#{r:02x}{g:02x}{bch:02x}"


def _sequential_shades(n, dark_first=True):
    """Sample n shades from the documented blue SEQUENTIAL ramp — for
    genuinely ORDERED data only (rank on a value-sorted axis, or true
    chronological order).
    dark_first=True  -> row 0 gets the darkest shade (row 0 is the highest
                         value / earliest point in a descending-sorted df).
    dark_first=False -> row 0 gets the lightest shade (df sorted ascending).
    """
    if n <= 1:
        return [SEQUENTIAL[9]]
    lo, hi = 2, len(SEQUENTIAL) - 1  # stay clear of the near-white steps
    shades = []
    for i in range(n):
        idx = lo + (hi - lo) * i / (n - 1)
        i0, i1 = int(idx), min(int(idx) + 1, hi)
        shades.append(_lerp_hex(SEQUENTIAL[i0], SEQUENTIAL[i1], idx - i0))
    return shades[::-1] if dark_first else shades


def _plain_layout(fig, title=None, y_title=None, x_title=None, showlegend=False):
    # Every chart in this dashboard is a single series unless noted — per the
    # dataviz skill, a single series needs no legend box (the subheader above
    # it names it). showlegend is exposed for the one chart that has a real
    # second series (the BQ06 donut).
    fig.update_layout(
        # Plotly.js renders the literal string "undefined" as the title if
        # `title` is passed as Python None (it becomes JSON null, and
        # plotly.js stringifies the missing .text). Pass "" instead so no
        # title renders at all when one wasn't requested.
        title=title or "",
        showlegend=showlegend,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=13),
        xaxis=dict(title=x_title, showgrid=False, showline=True, linecolor="#d8d6ce"),
        yaxis=dict(title=y_title, showgrid=True, gridcolor="#eeece5", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="white"),
    )
    return fig


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
def q(sql):
    con = get_connection()
    return con.sql(sql).df()


st.set_page_config(page_title="Sakila DVD Rental — Data Warehouse", layout="wide")

with st.spinner("กำลังเตรียมคลังข้อมูล (สร้างครั้งแรกอาจใช้เวลาสักครู่)..."):
    build_status = ensure_warehouse_built()

st.title("🎞️ Sakila DVD Rental — Data Warehouse Dashboard")
st.caption(
    "ทุกกราฟในหน้านี้ดึงข้อมูลจาก schema `main_marts` เท่านั้น "
    "(Fact_Rental, Fact_Inventory, และ Dimension ทั้งหมด) ไม่แตะตาราง OLTP ต้นทางโดยตรง"
)

tabs = st.tabs([
    "รายได้และผลประกอบการ",
    "พฤติกรรมลูกค้า",
    "ประสิทธิภาพสินค้า",
    "สินค้าคงคลัง",
    "นักแสดง",
    "ฤดูกาล/เวลา",
])

# ════════════════════════════════════════════════════════════════════════
# TAB 1 — รายได้และผลประกอบการ (BQ01-03)
# ════════════════════════════════════════════════════════════════════════
with tabs[0]:
    revenue_month = q("""
        with months as (
            -- full calendar-month scale spanning the dataset's date range
            -- (main_marts.dim_date), not just months that happen to have rentals
            select distinct year, month, month_name
            from main_marts.dim_date
            where date_key != -1
        ),
        monthly as (
            select d.year, d.month,
                   round(sum(f.payment_amount), 2) as revenue,
                   count(*) as rentals
            from main_marts.fact_rental f
            join main_marts.dim_date d on f.rental_date_key = d.date_key
            group by 1, 2
        )
        select m.year, m.month, m.month_name,
               coalesce(mo.revenue, 0) as revenue,
               coalesce(mo.rentals, 0) as rentals
        from months m
        left join monthly mo on m.year = mo.year and m.month = mo.month
        order by m.year, m.month
    """)
    revenue_month["period"] = revenue_month["month_name"].str.slice(0, 3) + " " + revenue_month["year"].astype(str)

    revenue_store = q("""
        select ds.store_id, round(sum(f.payment_amount), 2) as revenue
        from main_marts.fact_rental f
        join main_marts.dim_store ds on f.store_key = ds.store_key
        group by 1 order by 1
    """)
    revenue_store["store_label"] = "Store " + revenue_store["store_id"].astype(str)

    revenue_staff = q("""
        select dst.full_name, round(sum(f.payment_amount), 2) as revenue, count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_staff dst on f.staff_key = dst.staff_key
        group by 1 order by revenue desc
    """)

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("BQ01 — รายได้รวมรายเดือน")
        fig = px.line(revenue_month, x="period", y="revenue", markers=True)
        fig.update_traces(
            line=dict(width=3, color=SEQUENTIAL[9]),
            marker=dict(size=9, color=SEQUENTIAL[9], line=dict(width=2, color="white")),
            fill="tozeroy",
            fillcolor="rgba(42,120,214,0.14)",
        )
        _plain_layout(fig, y_title="รายได้ (บาท)", x_title=None)
        st.plotly_chart(fig, use_container_width=True)
        zero_months = int((revenue_month["revenue"] == 0).sum())
        if zero_months:
            st.caption(f"เดือนที่รายได้ 0 บาท ({zero_months} เดือน) คือไม่มีรายการเช่าบันทึกไว้ในช่วงนั้นเลยจริงๆ ในชุดข้อมูลนี้ ไม่ใช่ข้อมูลหาย")

    with c2:
        st.subheader("BQ02 — รายได้ต่อสาขา")
        colors = [SERIES[i % len(SERIES)] for i in range(len(revenue_store))]
        fig = px.bar(revenue_store, x="store_label", y="revenue", text="revenue")
        fig.update_traces(marker_color=colors, texttemplate="%{text:,.0f}", textposition="outside")
        _plain_layout(fig, y_title="รายได้ (บาท)", x_title=None)
        st.plotly_chart(fig, use_container_width=True)
        diff = abs(revenue_store["revenue"].iloc[0] - revenue_store["revenue"].iloc[1]) if len(revenue_store) == 2 else 0
        st.caption(
            f"ต่างกันแค่ {diff:,.2f} บาท ระหว่าง 2 สาขา — แท่งจึงสูงใกล้เคียงกันโดยธรรมชาติ "
            "(แกน Y เริ่มที่ 0 เสมอ ไม่ตัดขอบล่างออก เพื่อไม่ให้ความต่างที่จริงๆ น้อยมากดูเกินจริง)"
        )

    st.subheader("BQ03 — พนักงานที่สร้างรายได้เข้าร้านมากที่สุด")
    colors = [SERIES[i % len(SERIES)] for i in range(len(revenue_staff))]
    fig = px.bar(revenue_staff, x="full_name", y="revenue", text="revenue")
    fig.update_traces(marker_color=colors, texttemplate="%{text:,.0f}", textposition="outside")
    _plain_layout(fig, y_title="รายได้ (บาท)", x_title=None)
    st.plotly_chart(fig, use_container_width=True)
    if len(revenue_staff) == 2:
        diff2 = abs(revenue_staff["revenue"].iloc[0] - revenue_staff["revenue"].iloc[1])
        st.caption(f"ต่างกัน {diff2:,.2f} บาท ระหว่าง 2 คน")

# ════════════════════════════════════════════════════════════════════════
# TAB 2 — พฤติกรรมลูกค้า (BQ04-06)
# ════════════════════════════════════════════════════════════════════════
with tabs[1]:
    revenue_country = q("""
        select dc.country, round(sum(f.payment_amount), 2) as revenue, count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_customer dc on f.customer_key = dc.customer_key
        group by 1 order by revenue desc limit 10
    """)

    top_customers = q("""
        select dc.full_name, dc.city, dc.country,
               round(sum(f.payment_amount), 2) as total_spend,
               count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_customer dc on f.customer_key = dc.customer_key
        group by 1, 2, 3 order by total_spend desc limit 10
    """)

    repeat_rate = q("""
        with per_customer as (
            select customer_key, count(*) as rentals
            from main_marts.fact_rental
            group by 1
        )
        select
            count(*) filter (where rentals > 1) as repeat_customers,
            count(*) as total_customers,
            round(100.0 * count(*) filter (where rentals > 1) / count(*), 1) as repeat_rate_pct,
            min(rentals) as min_rentals,
            max(rentals) as max_rentals
        from per_customer
    """)

    rentals_per_customer = q("""
        select customer_key, count(*) as rentals
        from main_marts.fact_rental
        group by 1
    """)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("BQ04 — 10 ประเทศที่ใช้จ่ายสูงสุด")
        rc_sorted = revenue_country.sort_values("revenue")  # ascending — matches horizontal-bar draw order
        shades = _sequential_shades(len(rc_sorted), dark_first=False)  # row0=lowest->lightest, last=highest->darkest
        fig = px.bar(rc_sorted, x="revenue", y="country", orientation="h")
        fig.update_traces(marker_color=shades)
        _plain_layout(fig, x_title="รายได้ (บาท)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("สีเข้ม = รายได้สูง, สีอ่อน = รายได้ต่ำ (ไล่สีโทนเดียวกันตามอันดับ)")

    with c2:
        st.subheader("BQ05 — Top 10 ลูกค้าตามยอดใช้จ่ายสะสม")
        st.dataframe(
            top_customers.rename(columns={
                "full_name": "ลูกค้า", "city": "เมือง", "country": "ประเทศ",
                "total_spend": "ยอดใช้จ่าย (บาท)", "rentals": "จำนวนครั้งที่เช่า",
            }),
            hide_index=True, use_container_width=True,
        )

    st.divider()
    st.subheader("BQ06 — Repeat Customer Rate")
    total_c = int(repeat_rate["total_customers"][0])
    repeat_c = int(repeat_rate["repeat_customers"][0])
    min_r, max_r = int(repeat_rate["min_rentals"][0]), int(repeat_rate["max_rentals"][0])
    cc1, cc2 = st.columns(2)
    cc1.metric("ลูกค้าทั้งหมด", f"{total_c:,}")
    cc2.metric("ลูกค้าที่เช่าซ้ำ (>1 ครั้ง)", f"{repeat_c:,} ({repeat_rate['repeat_rate_pct'][0]}%)")
    if repeat_rate["repeat_rate_pct"][0] == 100:
        st.caption(
            f"ลูกค้าทุกคนเช่าซ้ำมากกว่า 1 ครั้ง (ต่ำสุด {min_r} ครั้ง, สูงสุด {max_r} ครั้ง/คน ในชุดข้อมูลนี้) "
            "— repeat rate แบบ % จึงไม่มีความต่างให้ดู กราฟด้านล่างเปลี่ยนมาดูการกระจายของ 'จำนวนครั้งที่เช่าต่อคน' แทน "
            "ซึ่งเป็นจุดที่ลูกค้าแต่ละคนต่างกันจริง"
        )
    fig = px.histogram(rentals_per_customer, x="rentals", nbins=20)
    fig.update_traces(marker_color=SERIES[0])
    _plain_layout(fig, y_title="จำนวนลูกค้า", x_title="จำนวนครั้งที่เช่าต่อคน")
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# TAB 3 — ประสิทธิภาพสินค้า (BQ07-08)
# ════════════════════════════════════════════════════════════════════════
with tabs[2]:
    category_perf = q("""
        select df.category, round(sum(f.payment_amount), 2) as revenue, count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        group by 1 order by revenue desc
    """)

    rating_perf = q("""
        select df.rating, count(*) as rentals, round(avg(df.length), 1) as avg_length
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        group by 1 order by 1
    """)

    st.subheader("BQ07 — หมวดหนังที่ถูกเช่าบ่อยที่สุด / ทำรายได้สูงสุด")
    shades = _sequential_shades(len(category_perf), dark_first=True)  # already sorted desc by revenue
    fig = go.Figure()
    fig.add_bar(x=category_perf["category"], y=category_perf["revenue"], marker_color=shades)
    _plain_layout(fig, y_title="รายได้ (บาท)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("สีเข้ม = รายได้สูง ไล่ไปสีอ่อน = รายได้ต่ำ (โทนเดียวกันทั้งหมด) — ตัวเลขจำนวนครั้งเช่าดูได้จากตารางด้านล่าง")
    st.dataframe(
        category_perf.rename(columns={"category": "หมวดหนัง", "revenue": "รายได้ (บาท)", "rentals": "จำนวนครั้งที่เช่า"}),
        hide_index=True, use_container_width=True,
    )

    st.subheader("BQ08 — Rating ของหนังมีผลต่อความถี่การเช่าไหม")
    colors8 = [PASTEL5[i % len(PASTEL5)] for i in range(len(rating_perf))]
    fig = px.bar(rating_perf, x="rating", y="rentals", text="rentals")
    fig.update_traces(marker_color=colors8, textposition="outside")
    _plain_layout(fig, y_title="จำนวนครั้งที่เช่า", x_title="Rating")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("ความยาวเฉลี่ยของหนังในแต่ละ rating (นาที): " + ", ".join(
        f"{r.rating}={r.avg_length}" for r in rating_perf.itertuples()
    ))

# ════════════════════════════════════════════════════════════════════════
# TAB 4 — สินค้าคงคลัง (BQ09-11)
# ════════════════════════════════════════════════════════════════════════
with tabs[3]:
    utilization_store = q("""
        select ds.store_id,
               sum(fi.inventory_count) as inventory_count,
               sum(fi.rental_count_to_date) as rental_count,
               round(sum(fi.rental_count_to_date)::decimal / nullif(sum(fi.inventory_count), 0), 2) as utilization_ratio
        from main_marts.fact_inventory fi
        join main_marts.dim_store ds on fi.store_key = ds.store_key
        group by 1 order by 1
    """)
    utilization_store["store_label"] = "Store " + utilization_store["store_id"].astype(str)

    shortage = q("""
        select df.title, ds.store_id, fi.inventory_count, fi.rental_count_to_date, fi.utilization_ratio
        from main_marts.fact_inventory fi
        join main_marts.dim_film df on fi.film_key = df.film_key
        join main_marts.dim_store ds on fi.store_key = ds.store_key
        order by fi.utilization_ratio desc
        limit 15
    """)

    days_late = q("""
        select df.rating, round(avg(f.days_late), 2) as avg_days_late, count(*) as n
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        where f.is_returned
        group by 1 order by 1
    """)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("BQ09 — อัตราการใช้งานสินค้าคงคลังต่อสาขา")
        colors9 = [SERIES[i % len(SERIES)] for i in range(len(utilization_store))]
        fig = px.bar(utilization_store, x="store_label", y="utilization_ratio", text="utilization_ratio")
        fig.update_traces(marker_color=colors9, texttemplate="%{text:.2f}x", textposition="outside")
        _plain_layout(fig, y_title="อัตราการเช่า / สต๊อก 1 ชุด")
        st.plotly_chart(fig, use_container_width=True)
        if len(utilization_store) == 2:
            u_diff = abs(utilization_store["utilization_ratio"].iloc[0] - utilization_store["utilization_ratio"].iloc[1])
            st.caption(f"ต่างกัน {u_diff:.2f}x ระหว่าง 2 สาขา")

    with c2:
        st.subheader("BQ11 — วันคืนช้า/เร็วเฉลี่ย แยกตาม Rating")
        st.caption(
            "อ่านกราฟนี้ยังไง: แต่ละแท่งคือค่าเฉลี่ยจำนวนวันที่คืนช้า/เร็วกว่ากำหนด ของการเช่าหนัง Rating นั้น "
            "คำนวณจาก (วันที่คืนจริง − วันที่เช่า) ลบด้วยจำนวนวันเช่ามาตรฐานของหนังเรื่องนั้น (rental_duration) — "
            "แท่งสีแดง (ค่าบวก) = โดยเฉลี่ยคืนช้ากว่ากำหนด, แท่งสีน้ำเงิน (ค่าลบ) = โดยเฉลี่ยคืนเร็วกว่ากำหนด "
            "(นับเฉพาะรายการที่คืนแล้ว) เช่น ถ้า R = +0.22 แปลว่าลูกค้าที่เช่าหนัง Rating R คืนช้ากว่ากำหนดเฉลี่ย 0.22 วัน (~5 ชม.)"
        )
        colors11 = [DIVERGE_POS if v > 0 else DIVERGE_NEG for v in days_late["avg_days_late"]]
        fig = go.Figure(go.Bar(
            x=days_late["rating"], y=days_late["avg_days_late"], marker_color=colors11,
            text=days_late["avg_days_late"], texttemplate="%{text:+.2f}", textposition="outside",
        ))
        _plain_layout(fig, y_title="วันคืนช้า (+) / เร็ว (-) เฉลี่ย")
        fig.update_yaxes(zeroline=True, zerolinecolor="#c3c2b7", zerolinewidth=1.5)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("BQ10 — หนังที่มี stock ไม่เพียงพอเทียบกับความต้องการเช่า (utilization สูงสุด)")
    st.dataframe(
        shortage.rename(columns={
            "title": "ชื่อหนัง", "store_id": "สาขา", "inventory_count": "จำนวนสต๊อก",
            "rental_count_to_date": "จำนวนครั้งที่เช่า", "utilization_ratio": "อัตราการใช้งาน",
        }),
        hide_index=True, use_container_width=True,
    )

# ════════════════════════════════════════════════════════════════════════
# TAB 5 — นักแสดง (BQ12)
# ════════════════════════════════════════════════════════════════════════
with tabs[4]:
    top_films = q("""
        select df.film_key, df.title, round(sum(f.payment_amount), 2) as revenue
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        group by 1, 2 order by revenue desc limit 10
    """)
    actor_credit = q("""
        select df.title, round(sum(f.payment_amount), 2) as revenue,
               string_agg(distinct da.first_name || ' ' || da.last_name, ', ') as actors
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        join main_marts.bridge_film_actor bfa on df.film_key = bfa.film_key
        join main_marts.dim_actor da on bfa.actor_key = da.actor_key
        group by 1 order by revenue desc limit 10
    """)

    st.subheader("BQ12 — นักแสดงในหนังที่ทำรายได้รวมสูงสุด (Top 10 เรื่อง)")
    st.dataframe(
        actor_credit.rename(columns={"title": "ชื่อหนัง", "revenue": "รายได้รวม (บาท)", "actors": "นักแสดง"}),
        hide_index=True, use_container_width=True,
    )
    st.caption("ผ่าน Bridge_Film_Actor เพราะ 1 หนังมีนักแสดงหลายคน (many-to-many)")

# ════════════════════════════════════════════════════════════════════════
# TAB 6 — ฤดูกาล/เวลา (BQ13-15)
# ════════════════════════════════════════════════════════════════════════
with tabs[5]:
    weekday = q("""
        select d.day_of_week_name,
               (d.is_weekend) as is_weekend,
               count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_date d on f.rental_date_key = d.date_key
        group by 1, 2
    """)
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday["day_of_week_name"] = pd.Categorical(weekday["day_of_week_name"], categories=order, ordered=True)
    weekday = weekday.sort_values("day_of_week_name")

    revenue_month2 = q("""
        with months as (
            select distinct year, month, month_name
            from main_marts.dim_date
            where date_key != -1
        ),
        monthly as (
            select d.year, d.month, round(sum(f.payment_amount), 2) as revenue
            from main_marts.fact_rental f
            join main_marts.dim_date d on f.rental_date_key = d.date_key
            group by 1, 2
        )
        select m.year, m.month, m.month_name, coalesce(mo.revenue, 0) as revenue
        from months m
        left join monthly mo on m.year = mo.year and m.month = mo.month
        order by m.year, m.month
    """)
    revenue_month2["period"] = revenue_month2["month_name"].str.slice(0, 3) + " " + revenue_month2["year"].astype(str)

    # BQ15 (replaced) — the original "payment lag" question turned out to have
    # zero variance in this dataset: every single payment happens the same day
    # as the rental (verified: 16,044/16,044 rows = 0 days lag), so there was
    # nothing to chart. Swapped for a real question in the same theme.
    weekend_duration = q("""
        select d.is_weekend, round(avg(f.rental_duration_actual_days), 2) as avg_days, count(*) as n
        from main_marts.fact_rental f
        join main_marts.dim_date d on f.rental_date_key = d.date_key
        where f.is_returned
        group by 1 order by 1
    """)
    weekend_duration["label"] = weekend_duration["is_weekend"].map({False: "วันธรรมดา", True: "วันหยุดสุดสัปดาห์"})

    st.subheader("BQ13 — วันในสัปดาห์ไหนมีการเช่าสูงสุด")
    colors13 = [PASTEL7[i % len(PASTEL7)] for i in range(len(weekday))]
    fig = go.Figure(go.Bar(
        x=weekday["day_of_week_name"], y=weekday["rentals"], marker_color=colors13,
        text=weekday["rentals"], textposition="outside",
    ))
    _plain_layout(fig, y_title="จำนวนครั้งที่เช่า")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("เสาร์-อาทิตย์ เป็นวันหยุดสุดสัปดาห์ — แต่ละวันให้สีของตัวเองเพื่อแยกให้เห็นชัดทีละวัน")

    st.subheader("BQ14 — Seasonality: รายได้แยกตามเดือน")
    shades14 = _sequential_shades(len(revenue_month2), dark_first=True)  # by chronological order, not by value
    fig = px.bar(revenue_month2, x="period", y="revenue", text="revenue")
    fig.update_traces(marker_color=shades14, texttemplate="%{text:,.0f}", textposition="outside")
    _plain_layout(fig, y_title="รายได้ (บาท)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("ไล่สีตามลำดับเวลา (เดือนแรก → เดือนสุดท้าย) โทนเดียวกับกราฟอื่นๆ ในหน้านี้")

    st.subheader("BQ15 — วันเช่าเป็นวันธรรมดาหรือวันหยุด มีผลต่อระยะเวลาที่ลูกค้าเก็บหนังไว้ไหม")
    st.caption(
        "คำถามเดิม (payment lag — ระยะห่างระหว่างวันเช่ากับวันชำระเงิน) พบว่าลูกค้าชำระเงินวันเดียวกับวันเช่าทุกรายการ "
        "(16,044/16,044 แถว = 0 วันทุกกรณี) ไม่มี variance ให้วิเคราะห์ จึงเปลี่ยนเป็นคำถามใหม่ในหมวดฤดูกาล/เวลาเดียวกัน"
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        colors15 = [SERIES[0], SERIES[1]]
        fig = go.Figure(go.Bar(
            x=weekend_duration["label"], y=weekend_duration["avg_days"], marker_color=colors15,
            text=weekend_duration["avg_days"], texttemplate="%{text:.2f} วัน", textposition="outside",
        ))
        _plain_layout(fig, y_title="ระยะเวลาเช่าจริงเฉลี่ย (วัน)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        wd_diff = abs(weekend_duration["avg_days"].iloc[0] - weekend_duration["avg_days"].iloc[1]) if len(weekend_duration) == 2 else 0
        st.metric("ต่างกัน", f"{wd_diff:.2f} วัน")
        st.caption(
            "ระยะเวลาเช่าจริง (วันที่คืน − วันที่เช่า) เฉลี่ย ของรายการที่เช่าวันธรรมดา เทียบกับวันหยุดสุดสัปดาห์ "
            "(นับเฉพาะรายการที่คืนแล้ว) — ต่างกันเล็กน้อยมาก แสดงว่าพฤติกรรมการเก็บหนังไว้ไม่ได้ขึ้นกับวันที่เช่ามากนัก"
        )

st.divider()
st.caption(
    "ข้อมูล: Sakila DVD Rental · แหล่งข้อมูล main_marts.fact_rental / fact_inventory / dim_* "
    "· pipeline: dbt + DuckDB (ดู sakila_dw_duckdb/)"
)