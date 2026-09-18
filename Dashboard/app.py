"""
Sakila DVD Rental — Interactive Dashboard
Reads ONLY from the main_marts schema (Fact_Rental, Fact_Inventory, and dimensions) —
never touches main_raw / main_staging, per the assignment's dashboard requirement.

Self-building: if sakila_dw.duckdb doesn't exist yet (e.g. a fresh clone on
Streamlit Community Cloud), this app runs `dbt seed` + `dbt run` itself using a
project-local dbt profile, so it works with zero manual setup.
"""

import calendar as cal
import math
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

# ── palette — brand 4-tone theme, white background ──────────────────────────
# Built from 4 given brand colors: navy #425B9A (darkest/most prominent),
# sky blue #76C0EC, cream #FFF6DC (lightest, recedes toward the white page),
# and pink #FF95A5. The sequential ramp threads all four as one path
# (cream -> sky blue -> pink -> navy, light -> dark) so it still reads as a
# single graduated family; SERIES samples that path at spread-out (not
# adjacent) positions for categorical charts. Every chart still ships
# visible value labels as the mitigation for the one-family trade-off.
PAGE_BG = "#ffffff"
CARD_BG = "#ffffff"
TEXT_PRIMARY = "#1f2b4d"
TEXT_SECONDARY = "#5b6b93"
GRID_COLOR = "#eaf6fc"
AXIS_COLOR = "#d6ecf9"

# 8-slot categorical order, sampled from the gradient at spread-out (not
# adjacent) positions so consecutive slots jump across the family rather than
# drifting through it. Never reorder past slot 8.
SERIES = ["#cfe3e2", "#ec9baf", "#85bbe4", "#8a719e", "#9bcfe8", "#d187a2", "#b9abca", "#425b9a"]

# The gradient itself, as a 13-step ramp: cream (recedes toward the white
# page, low values) -> sky blue -> pink -> navy (most contrast against
# white, high values) — light -> dark, same convention _sequential_shades()
# was written against originally.
SEQUENTIAL = [
    "#fff6dc", "#dde8e0", "#badbe4", "#98cee8", "#76c0ec", "#98b5da",
    "#baaac8", "#dda0b7", "#ff95a5", "#d086a2", "#a078a0", "#716a9d", "#425b9a",
]

# Softer variants — SERIES lightened toward white.
PASTEL5 = ["#e0edec", "#f3becb", "#b0d3ed", "#b3a3c0", "#bee0f0"]
PASTEL7 = PASTEL5 + ["#e1b1c3", "#d2c8dd"]

# Diverging pair on the family's own cool (navy) and warm (pink) ends, for
# "which side of zero" charts.
DIVERGE_NEG = "#425B9A"  # early / negative side
DIVERGE_POS = "#FF95A5"  # late / positive side

# ── country -> continent lookup (used by BQ04's map drill-down) ─────────────
# Plotly has no built-in "continent" geometry, so the continent level of the
# BQ04 map is built by aggregating countries and re-coloring every country
# in that continent by the continent's total — there is no field for this in
# Dim_Customer, and none is added; the mapping lives only in this UI layer,
# per the prompt's constraint that dimension tables stay untouched.
CONTINENT_MAP = {
    "Afghanistan": "Asia", "Algeria": "Africa", "American Samoa": "Oceania", "Angola": "Africa",
    "Anguilla": "North America", "Argentina": "South America", "Armenia": "Asia", "Austria": "Europe",
    "Azerbaijan": "Asia", "Bahrain": "Asia", "Bangladesh": "Asia", "Belarus": "Europe",
    "Bolivia": "South America", "Brazil": "South America", "Brunei": "Asia", "Bulgaria": "Europe",
    "Cambodia": "Asia", "Cameroon": "Africa", "Canada": "North America", "Chad": "Africa",
    "Chile": "South America", "China": "Asia", "Colombia": "South America",
    "Congo, The Democratic Republic of the": "Africa", "Czech Republic": "Europe",
    "Dominican Republic": "North America", "Ecuador": "South America", "Egypt": "Africa",
    "Estonia": "Europe", "Ethiopia": "Africa", "Faroe Islands": "Europe", "Finland": "Europe",
    "France": "Europe", "French Guiana": "South America", "French Polynesia": "Oceania",
    "Gambia": "Africa", "Germany": "Europe", "Greece": "Europe", "Greenland": "North America",
    "Holy See (Vatican City State)": "Europe", "Hong Kong": "Asia", "Hungary": "Europe",
    "India": "Asia", "Indonesia": "Asia", "Iran": "Asia", "Iraq": "Asia", "Israel": "Asia",
    "Italy": "Europe", "Japan": "Asia", "Kazakstan": "Asia", "Kenya": "Africa", "Kuwait": "Asia",
    "Latvia": "Europe", "Liechtenstein": "Europe", "Lithuania": "Europe", "Madagascar": "Africa",
    "Malawi": "Africa", "Malaysia": "Asia", "Mexico": "North America", "Moldova": "Europe",
    "Morocco": "Africa", "Mozambique": "Africa", "Myanmar": "Asia", "Nauru": "Oceania",
    "Nepal": "Asia", "Netherlands": "Europe", "New Zealand": "Oceania", "Nigeria": "Africa",
    "North Korea": "Asia", "Oman": "Asia", "Pakistan": "Asia", "Paraguay": "South America",
    "Peru": "South America", "Philippines": "Asia", "Poland": "Europe", "Puerto Rico": "North America",
    "Romania": "Europe", "Runion": "Africa", "Russian Federation": "Europe",
    "Saint Vincent and the Grenadines": "North America", "Saudi Arabia": "Asia", "Senegal": "Africa",
    "Slovakia": "Europe", "South Africa": "Africa", "South Korea": "Asia", "Spain": "Europe",
    "Sri Lanka": "Asia", "Sudan": "Africa", "Sweden": "Europe", "Switzerland": "Europe",
    "Taiwan": "Asia", "Tanzania": "Africa", "Thailand": "Asia", "Tonga": "Oceania",
    "Tunisia": "Africa", "Turkey": "Asia", "Turkmenistan": "Asia", "Tuvalu": "Oceania",
    "Ukraine": "Europe", "United Arab Emirates": "Asia", "United Kingdom": "Europe",
    "United States": "North America", "Venezuela": "South America", "Vietnam": "Asia",
    "Virgin Islands, U.S.": "North America", "Yemen": "Asia", "Yugoslavia": "Europe",
    "Zambia": "Africa",
}
# A handful of Dim_Customer.country spellings don't match Plotly's built-in
# "country names" geometry set (Natural Earth) — remap just those for the map;
# the underlying data/table keeps the original Sakila spelling everywhere else.
PLOTLY_NAME_FIX = {
    "Congo, The Democratic Republic of the": "Democratic Republic of the Congo",
    "Russian Federation": "Russia",
    "Kazakstan": "Kazakhstan",
}

# ── approximate geo coordinates — used ONLY by the BQ24 distance radar ──────
# The source data has no lat/long or PostGIS "location" column (confirmed),
# so real address-to-address distance can't be computed. Instead we
# approximate every customer's location by their country's capital/centroid,
# and each store's location by its real-world Sakila fixture address
# (address_id 1 = Lethbridge, Canada; address_id 2 = Woodridge, Australia —
# the two stores' actual addresses in the standard Sakila sample data).
# This gives a directionally-correct, roughly-scaled radar, not survey-grade
# distances — good enough for "which regions are near/far from which store"
# at a glance, which is what the radar is for.
STORE_COORDS = {
    1: {"city": "Lethbridge", "country": "Canada", "lat": 49.6935, "lon": -112.8418},
    2: {"city": "Woodridge", "country": "Australia", "lat": -27.6203, "lon": 153.0866},
}

# country -> (lat, lon) of capital/centroid. Keys match Dim_Customer.country
# spelling exactly (same source list as CONTINENT_MAP above).
COUNTRY_COORDS = {
    "Afghanistan": (34.5553, 69.2075), "Algeria": (36.7538, 3.0588),
    "American Samoa": (-14.2781, -170.7025), "Angola": (-8.8399, 13.2894),
    "Anguilla": (18.2206, -63.0686), "Argentina": (-34.6037, -58.3816),
    "Armenia": (40.1792, 44.4991), "Austria": (48.2082, 16.3738),
    "Azerbaijan": (40.4093, 49.8671), "Bahrain": (26.2285, 50.5860),
    "Bangladesh": (23.8103, 90.4125), "Belarus": (53.9006, 27.5590),
    "Bolivia": (-16.4897, -68.1193), "Brazil": (-15.7939, -47.8828),
    "Brunei": (4.9031, 114.9398), "Bulgaria": (42.6977, 23.3219),
    "Cambodia": (11.5564, 104.9282), "Cameroon": (3.8480, 11.5021),
    "Canada": (45.4215, -75.6972), "Chad": (12.1348, 15.0557),
    "Chile": (-33.4489, -70.6693), "China": (39.9042, 116.4074),
    "Colombia": (4.7110, -74.0721), "Congo, The Democratic Republic of the": (-4.4419, 15.2663),
    "Czech Republic": (50.0755, 14.4378), "Dominican Republic": (18.4861, -69.9312),
    "Ecuador": (-0.1807, -78.4678), "Egypt": (30.0444, 31.2357),
    "Estonia": (59.4370, 24.7536), "Ethiopia": (9.0300, 38.7400),
    "Faroe Islands": (62.0079, -6.7909), "Finland": (60.1699, 24.9384),
    "France": (48.8566, 2.3522), "French Guiana": (4.9224, -52.3135),
    "French Polynesia": (-17.5516, -149.5585), "Gambia": (13.4549, -16.5790),
    "Germany": (52.5200, 13.4050), "Greece": (37.9838, 23.7275),
    "Greenland": (64.1836, -51.7214), "Holy See (Vatican City State)": (41.9029, 12.4534),
    "Hong Kong": (22.3193, 114.1694), "Hungary": (47.4979, 19.0402),
    "India": (28.6139, 77.2090), "Indonesia": (-6.2088, 106.8456),
    "Iran": (35.6892, 51.3890), "Iraq": (33.3152, 44.3661),
    "Israel": (31.7683, 35.2137), "Italy": (41.9028, 12.4964),
    "Japan": (35.6762, 139.6503), "Kazakstan": (51.1694, 71.4491),
    "Kenya": (-1.2921, 36.8219), "Kuwait": (29.3759, 47.9774),
    "Latvia": (56.9496, 24.1052), "Liechtenstein": (47.1410, 9.5209),
    "Lithuania": (54.6872, 25.2797), "Madagascar": (-18.8792, 47.5079),
    "Malawi": (-13.9626, 33.7741), "Malaysia": (3.1390, 101.6869),
    "Mexico": (19.4326, -99.1332), "Moldova": (47.0105, 28.8638),
    "Morocco": (34.0209, -6.8416), "Mozambique": (-25.9692, 32.5732),
    "Myanmar": (16.8409, 96.1735), "Nauru": (-0.5477, 166.9209),
    "Nepal": (27.7172, 85.3240), "Netherlands": (52.3676, 4.9041),
    "New Zealand": (-41.2865, 174.7762), "Nigeria": (9.0765, 7.3986),
    "North Korea": (39.0392, 125.7625), "Oman": (23.5859, 58.4059),
    "Pakistan": (33.6844, 73.0479), "Paraguay": (-25.2637, -57.5759),
    "Peru": (-12.0464, -77.0428), "Philippines": (14.5995, 120.9842),
    "Poland": (52.2297, 21.0122), "Puerto Rico": (18.4655, -66.1057),
    "Romania": (44.4268, 26.1025), "Runion": (-20.8789, 55.4481),
    "Russian Federation": (55.7558, 37.6173),
    "Saint Vincent and the Grenadines": (13.1600, -61.2248),
    "Saudi Arabia": (24.7136, 46.6753), "Senegal": (14.7167, -17.4677),
    "Slovakia": (48.1486, 17.1077), "South Africa": (-25.7461, 28.1881),
    "South Korea": (37.5665, 126.9780), "Spain": (40.4168, -3.7038),
    "Sri Lanka": (6.9271, 79.8612), "Sudan": (15.5007, 32.5599),
    "Sweden": (59.3293, 18.0686), "Switzerland": (46.9480, 7.4474),
    "Taiwan": (25.0330, 121.5654), "Tanzania": (-6.1630, 35.7516),
    "Thailand": (13.7563, 100.5018), "Tonga": (-21.1789, -175.1982),
    "Tunisia": (36.8065, 10.1815), "Turkey": (39.9334, 32.8597),
    "Turkmenistan": (37.9601, 58.3261), "Tuvalu": (-8.5211, 179.1983),
    "Ukraine": (50.4501, 30.5234), "United Arab Emirates": (24.4539, 54.3773),
    "United Kingdom": (51.5074, -0.1278), "United States": (38.9072, -77.0369),
    "Venezuela": (10.4806, -66.9036), "Vietnam": (21.0278, 105.8342),
    "Virgin Islands, U.S.": (18.3419, -64.9307), "Yemen": (15.3694, 44.1910),
    "Yugoslavia": (44.7866, 20.4489), "Zambia": (-15.3875, 28.3228),
}


def _haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _bearing_deg(lat1, lon1, lat2, lon2):
    """Initial compass bearing in degrees (0=North, clockwise) from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _lerp_hex(a, b, t):
    ar, ag, ab_ = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    br, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    bch = round(ab_ + (bb - ab_) * t)
    return f"#{r:02x}{g:02x}{bch:02x}"


def _contrast_text(hex_color):
    """Pick a readable label color for text drawn on top of hex_color —
    dark navy text on light slices, pale cream text on dark slices (e.g.
    the navy end of the palette), so pie-chart labels stay legible no
    matter which brand color a slice lands on."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return TEXT_PRIMARY if luminance > 0.55 else SEQUENTIAL[0]


def _sequential_shades(n, dark_first=True):
    """Sample n shades from the gold->violet SEQUENTIAL ramp — for
    genuinely ORDERED data only (rank on a value-sorted axis, or true
    chronological order).
    dark_first=True  -> row 0 gets the darkest (deep violet) shade — row 0 is
                         the highest value / earliest point in a
                         descending-sorted df.
    dark_first=False -> row 0 gets the lightest (pale gold) shade — df sorted
                         ascending.
    """
    if n <= 1:
        return [SEQUENTIAL[9]]
    lo, hi = 2, len(SEQUENTIAL) - 1  # stay clear of the palest near-white step
    shades = []
    for i in range(n):
        idx = lo + (hi - lo) * i / (n - 1)
        i0, i1 = int(idx), min(int(idx) + 1, hi)
        shades.append(_lerp_hex(SEQUENTIAL[i0], SEQUENTIAL[i1], idx - i0))
    return shades[::-1] if dark_first else shades


def _plain_layout(fig, title=None, y_title=None, x_title=None, showlegend=False):
    # Every chart in this dashboard is a single series unless noted — per the
    # dataviz skill, a single series needs no legend box (the subheader above
    # it names it). showlegend is exposed for charts with a real second series.
    fig.update_layout(
        # Plotly.js renders the literal string "undefined" as the title if
        # `title` is passed as Python None (it becomes JSON null, and
        # plotly.js stringifies the missing .text). Pass "" instead so no
        # title renders at all when one wasn't requested.
        title=title or "",
        showlegend=showlegend,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        plot_bgcolor=CARD_BG,
        paper_bgcolor=CARD_BG,
        font=dict(family="Inter, sans-serif", size=13, color=TEXT_SECONDARY),
        xaxis=dict(title=x_title, showgrid=False, showline=True, linecolor=AXIS_COLOR, color=TEXT_SECONDARY),
        yaxis=dict(title=y_title, showgrid=True, gridcolor=GRID_COLOR, zeroline=False, color=TEXT_SECONDARY),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=TEXT_SECONDARY)),
        hoverlabel=dict(bgcolor=CARD_BG, font=dict(color=TEXT_PRIMARY), bordercolor=AXIS_COLOR),
        title_font=dict(color=TEXT_PRIMARY),
    )
    return fig


def _click_index(event):
    """Pull the clicked point's index out of a st.plotly_chart(on_select=...)
    event, for 1-D charts (bar/scatter/word-cloud-scatter). Returns None if
    nothing is selected this run."""
    if event and event.selection and event.selection.points:
        return event.selection.points[0]["point_index"]
    return None


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
def q(sql, params=None):
    con = get_connection()
    if params:
        return con.execute(sql, params).df()
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
    "กลุ่มที่ 1: รายได้",
    "กลุ่มที่ 2: ลูกค้า",
    "กลุ่มที่ 3: กลุ่มลูกค้า & การเช่าซ้ำ",
    "กลุ่มที่ 4: เนื้อหาภาพยนตร์",
    "กลุ่มที่ 5: ร้าน/พนักงาน",
])

# ════════════════════════════════════════════════════════════════════════
# กลุ่มที่ 1: การวิเคราะห์รายได้ (Revenue Analysis) — ข้อ 1-3
# ════════════════════════════════════════════════════════════════════════
with tabs[0]:
    # "รายวัน" and "รายสัปดาห์" are PATTERNS, not calendar timelines: รายวัน
    # sums revenue by day-of-week (Mon..Sun, 7 bars total, across the whole
    # dataset) and รายสัปดาห์ sums revenue by week-of-month (week 1-5, across
    # every month in the dataset) — a "typical week" / "typical month" shape.
    # รายเดือน stays the one real chronological timeline (every calendar
    # month in the data, in order).
    GRANULARITY_UNITS = {
        "รายวัน (วันในสัปดาห์)": "weekday",
        "รายสัปดาห์ (สัปดาห์ที่ 1-5 ของเดือน)": "week_of_month",
        "รายเดือน": "month",
    }
    WEEKDAY_TH = {
        "Monday": "จันทร์", "Tuesday": "อังคาร", "Wednesday": "พุธ", "Thursday": "พฤหัสบดี",
        "Friday": "ศุกร์", "Saturday": "เสาร์", "Sunday": "อาทิตย์",
    }

    @st.cache_data(show_spinner=False)
    def get_revenue_series(unit: str) -> pd.DataFrame:
        """Zero-filled revenue by store, at one of three granularities.
        Returns columns: sort_key (for x-axis ordering), store_id, revenue, period (x-axis label).
        """
        if unit == "weekday":
            sql = """
                with days(day_of_week_name, sort_key) as (
                    values ('Monday', 0), ('Tuesday', 1), ('Wednesday', 2), ('Thursday', 3),
                           ('Friday', 4), ('Saturday', 5), ('Sunday', 6)
                ),
                stores as (select store_id from main_marts.dim_store),
                actual as (
                    select d.day_of_week_name, ds.store_id, round(sum(f.payment_amount), 2) as revenue
                    from main_marts.fact_rental f
                    join main_marts.dim_date d on f.rental_date_key = d.date_key
                    join main_marts.dim_store ds on f.store_key = ds.store_key
                    group by 1, 2
                )
                select dy.day_of_week_name, dy.sort_key, s.store_id, coalesce(a.revenue, 0) as revenue
                from days dy
                cross join stores s
                left join actual a
                       on a.day_of_week_name = dy.day_of_week_name and a.store_id = s.store_id
                order by dy.sort_key, s.store_id
            """
            df = q(sql)
            df["period"] = df["day_of_week_name"].map(WEEKDAY_TH)

        elif unit == "week_of_month":
            sql = """
                with weeks(week_num) as (values (1), (2), (3), (4), (5)),
                stores as (select store_id from main_marts.dim_store),
                actual as (
                    select cast(floor((extract(day from d.full_date) - 1) / 7.0) as integer) + 1 as week_num,
                           ds.store_id, round(sum(f.payment_amount), 2) as revenue
                    from main_marts.fact_rental f
                    join main_marts.dim_date d on f.rental_date_key = d.date_key
                    join main_marts.dim_store ds on f.store_key = ds.store_key
                    group by 1, 2
                )
                select w.week_num as sort_key, s.store_id, coalesce(a.revenue, 0) as revenue
                from weeks w
                cross join stores s
                left join actual a on a.week_num = w.week_num and a.store_id = s.store_id
                order by w.week_num, s.store_id
            """
            df = q(sql)
            df["period"] = "สัปดาห์ที่ " + df["sort_key"].astype(str)

        else:  # month — the one real chronological timeline, zero-filled via a date spine
            sql = """
                with bounds as (
                    select min(full_date) as min_d, max(full_date) as max_d
                    from main_marts.dim_date
                    where date_key != -1
                ),
                spine as (
                    select distinct date_trunc('month', t.d) as period_start
                    from bounds, generate_series(bounds.min_d, bounds.max_d, interval 1 day) as t(d)
                ),
                stores as (select store_id from main_marts.dim_store),
                actual as (
                    select date_trunc('month', d.full_date) as period_start, ds.store_id,
                           round(sum(f.payment_amount), 2) as revenue
                    from main_marts.fact_rental f
                    join main_marts.dim_date d on f.rental_date_key = d.date_key
                    join main_marts.dim_store ds on f.store_key = ds.store_key
                    group by 1, 2
                )
                select sp.period_start as sort_key, s.store_id, coalesce(a.revenue, 0) as revenue
                from spine sp
                cross join stores s
                left join actual a
                       on a.period_start = sp.period_start and a.store_id = s.store_id
                order by sp.period_start, s.store_id
            """
            df = q(sql)
            df["sort_key"] = pd.to_datetime(df["sort_key"])
            df["period"] = df["sort_key"].dt.strftime("%b %Y")

        return df[["sort_key", "store_id", "revenue", "period"]]

    st.subheader("ข้อ 1-3 — รายได้รวมมีแนวโน้มอย่างไร, เปรียบเทียบรายสาขา, และเปรียบเทียบรายวันในสัปดาห์")
    st.caption("กราฟเดียวตอบได้ 2 คำถาม: สลับมุมมองรวม/แยกสาขา และเลือกมุมมองแกน X ได้ที่ตัวเลือกด้านล่าง")

    ctrl0, ctrl1, ctrl2 = st.columns([1.4, 1, 2])
    with ctrl0:
        gran_label = st.radio("มุมมองแกน X", list(GRANULARITY_UNITS.keys()), key="bq0102_gran")
    gran_unit = GRANULARITY_UNITS[gran_label]
    if gran_unit == "weekday":
        st.caption("ผลรวมรายได้ของวันจันทร์–อาทิตย์ ทุกสัปดาห์ในชุดข้อมูลรวมกัน (ไม่ใช่เส้นเวลาต่อเนื่อง)")
    elif gran_unit == "week_of_month":
        st.caption("ผลรวมรายได้ของสัปดาห์ที่ 1–5 ของเดือน จากทุกเดือนในชุดข้อมูลรวมกัน (ไม่ใช่เส้นเวลาต่อเนื่อง)")

    revenue_series = get_revenue_series(gran_unit)
    ordered_periods = (
        revenue_series[["sort_key", "period"]].drop_duplicates().sort_values("sort_key")["period"].tolist()
    )

    with ctrl1:
        mode = st.radio("มุมมอง", ["รวมทุกสาขา", "แยกตามสาขา"], horizontal=True, key="bq0102_mode")
    store_ids = sorted(revenue_series["store_id"].unique().tolist())
    picked_stores = store_ids
    if mode == "แยกตามสาขา":
        with ctrl2:
            picked_stores = st.multiselect(
                "เลือกสาขาที่จะแสดง (เลือก 1 สาขา = เส้นเดียว, เลือกทั้งหมด = แยกเส้นครบทุกสาขา)",
                store_ids, default=store_ids, format_func=lambda s: f"Store {s}", key="bq0102_stores",
            )

    plot_df = revenue_series[revenue_series["store_id"].isin(picked_stores or store_ids)]

    fig = go.Figure()
    if mode == "รวมทุกสาขา":
        combined = plot_df.groupby(["sort_key", "period"], as_index=False)["revenue"].sum()
        combined = combined.sort_values("sort_key")
        fig.add_trace(go.Scatter(
            x=combined["period"], y=combined["revenue"], mode="lines+markers", name="ทุกสาขารวมกัน",
            line=dict(width=3, color=SEQUENTIAL[9]),
            marker=dict(size=9, color=SEQUENTIAL[9], line=dict(width=2, color=CARD_BG)),
            fill="tozeroy", fillcolor="rgba(128,50,108,0.14)",
        ))
    else:
        for i, sid in enumerate(sorted(picked_stores)):
            s_df = plot_df[plot_df["store_id"] == sid].sort_values("sort_key")
            fig.add_trace(go.Scatter(
                x=s_df["period"], y=s_df["revenue"], mode="lines+markers", name=f"Store {sid}",
                line=dict(width=3, color=SERIES[i % len(SERIES)]),
                marker=dict(size=8, color=SERIES[i % len(SERIES)]),
            ))
    _plain_layout(fig, y_title="รายได้ ($)", x_title=None, showlegend=(mode == "แยกตามสาขา" and len(picked_stores) > 1))
    fig.update_xaxes(categoryorder="array", categoryarray=ordered_periods)
    st.plotly_chart(fig, use_container_width=True, key=f"bq0102_chart_{gran_unit}")

    zero_periods = int((revenue_series.groupby("sort_key")["revenue"].sum() == 0).sum())
    if zero_periods:
        unit_word = {"weekday": "วัน", "week_of_month": "สัปดาห์", "month": "เดือน"}[gran_unit]
        st.caption(f"ช่วงที่รายได้ 0 ({zero_periods} {unit_word}) คือไม่มีรายการเช่าบันทึกไว้ในช่วงนั้นเลยจริงๆ ในชุดข้อมูลนี้ ไม่ใช่ข้อมูลหาย")

    totals_by_store = plot_df.groupby("store_id", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
    if len(totals_by_store) >= 2:
        top, second = totals_by_store.iloc[0], totals_by_store.iloc[1]
        diff_baht = top["revenue"] - second["revenue"]
        diff_pct = (diff_baht / second["revenue"] * 100) if second["revenue"] else 0
        st.info(
            f"**ข้อ 2:** Store {int(top['store_id'])} ทำรายได้รวมสูงสุด (${top['revenue']:,.0f}) "
            f"มากกว่า Store {int(second['store_id'])} อยู่ ${diff_baht:,.0f} ({diff_pct:,.1f}%)"
        )

# ════════════════════════════════════════════════════════════════════════
# กลุ่มที่ 2: การวิเคราะห์ลูกค้า (Customer Analysis) — ข้อ 4-6
# ════════════════════════════════════════════════════════════════════════
with tabs[1]:
    country_geo = q("""
        select dc.country, round(sum(f.payment_amount), 2) as revenue, count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_customer dc on f.customer_key = dc.customer_key
        group by 1
    """)
    country_geo["continent"] = country_geo["country"].map(CONTINENT_MAP).fillna("Other")
    country_geo["map_name"] = country_geo["country"].map(lambda c: PLOTLY_NAME_FIX.get(c, c))
    continent_agg = country_geo.groupby("continent", as_index=False).agg(
        revenue=("revenue", "sum"), rentals=("rentals", "sum"),
    )

    top_customers = q("""
        select dc.customer_key, dc.full_name, dc.city, dc.country,
               round(sum(f.payment_amount), 2) as total_spend,
               count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_customer dc on f.customer_key = dc.customer_key
        group by 1, 2, 3, 4 order by total_spend desc limit 20
    """)

    st.subheader("ข้อ 4 — จำนวนการเช่าภาพยนตร์ของลูกค้าในแต่ละภูมิภาค (คลิกเพื่อ drill ทวีป → ประเทศ)")
    if "bq04_continent" not in st.session_state:
        st.session_state.bq04_continent = None

    cctrl1, cctrl2 = st.columns([3, 1])
    with cctrl2:
        manual_pick = st.selectbox(
            "หรือเลือกทวีปจากเมนู", ["ทั้งหมด (ระดับทวีป)"] + sorted(continent_agg["continent"].unique()),
            key="bq04_manual_select",
        )
        if st.session_state.bq04_continent and st.button("⬅ กลับไปดูระดับทวีป", key="bq04_back"):
            st.session_state.bq04_continent = None
            st.rerun()

    view_continent = st.session_state.bq04_continent or (
        None if manual_pick == "ทั้งหมด (ระดับทวีป)" else manual_pick
    )

    with cctrl1:
        if view_continent is None:
            plot_df = country_geo.merge(continent_agg, on="continent", suffixes=("_country", "_continent"))
            fig = go.Figure(go.Choropleth(
                locations=plot_df["map_name"], locationmode="country names",
                z=plot_df["revenue_continent"],
                colorscale=[[0, SEQUENTIAL[1]], [1, SEQUENTIAL[9]]],
                customdata=plot_df[["continent", "revenue_continent", "rentals_continent"]],
                hovertemplate="ทวีป %{customdata[0]}<br>รายได้รวม $%{customdata[1]:,.0f}"
                              "<br>จำนวนครั้งเช่ารวม %{customdata[2]:,}<extra></extra>",
                marker_line_color=CARD_BG, marker_line_width=0.5, showscale=False,
            ))
            fig.update_geos(showframe=False, showcoastlines=False, bgcolor=CARD_BG)
            _plain_layout(fig)
            event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="bq04_map_continent")
            idx = _click_index(event)
            if idx is not None:
                st.session_state.bq04_continent = plot_df.iloc[idx]["continent"]
                st.rerun()
            st.caption("คลิกที่ประเทศใดก็ได้บนแผนที่เพื่อดูรายละเอียดของทวีปนั้น (สีตอนนี้ = ผลรวมทั้งทวีป)")
        else:
            sub = country_geo[country_geo["continent"] == view_continent]
            fig = go.Figure(go.Choropleth(
                locations=sub["map_name"], locationmode="country names",
                z=sub["revenue"], colorscale=[[0, SEQUENTIAL[1]], [1, SEQUENTIAL[9]]],
                customdata=sub[["country", "revenue", "rentals"]],
                hovertemplate="%{customdata[0]}<br>รายได้ $%{customdata[1]:,.0f}"
                              "<br>จำนวนครั้งเช่า %{customdata[2]:,}<extra></extra>",
                marker_line_color=CARD_BG, marker_line_width=0.5, showscale=False,
            ))
            fig.update_geos(fitbounds="locations", visible=True, showframe=False, showcoastlines=False, bgcolor=CARD_BG)
            _plain_layout(fig)
            st.plotly_chart(fig, use_container_width=True, key="bq04_map_country")
            st.caption(f"กำลังดูระดับประเทศของทวีป {view_continent} — เอาเมาส์ชี้ประเทศเพื่อดูยอดรายได้และจำนวนครั้งเช่าของประเทศนั้น")
    st.caption("หมายเหตุ: ดินแดนขนาดเล็กมาก/ชื่อประเทศเก่า (เช่น Yugoslavia) อาจไม่มีรูปทรงในแผนที่มาตรฐาน แต่ยังถูกนับรวมในตัวเลขทุกที่ที่ไม่ใช่ตัวแผนที่")

    st.divider()
    st.subheader("ข้อ 5 — ลูกค้า 5 อันดับแรกที่มียอดใช้จ่ายและจำนวนครั้งการเช่ามากที่สุด")
    highlighted = st.session_state.get("bq05_highlight")

    def _spiral_positions(n):
        pts = []
        theta = 0.0
        for i in range(n):
            r = 0.95 * math.sqrt(i + 1)
            theta += 2.399963  # golden angle -> even spread, no clean rings
            pts.append((r * math.cos(theta), r * math.sin(theta)))
        return pts

    positions = _spiral_positions(len(top_customers))
    top_customers = top_customers.copy()
    top_customers["x"] = [p[0] for p in positions]
    top_customers["y"] = [p[1] for p in positions]
    mx, mn = top_customers["total_spend"].max(), top_customers["total_spend"].min()
    span = (mx - mn) or 1
    top_customers["font_size"] = 15 + (top_customers["total_spend"] - mn) / span * 33
    colors_wc = [
        TEXT_PRIMARY if name == highlighted else SERIES[i % len(SERIES)]
        for i, name in enumerate(top_customers["full_name"])
    ]
    sizes_wc = [
        sz * 1.15 if name == highlighted else sz
        for sz, name in zip(top_customers["font_size"], top_customers["full_name"])
    ]

    wc_fig = go.Figure(go.Scatter(
        x=top_customers["x"], y=top_customers["y"], mode="text", text=top_customers["full_name"],
        textfont=dict(size=sizes_wc, color=colors_wc),
        customdata=top_customers[["total_spend", "rentals"]],
        hovertemplate="%{text}<br>ยอดใช้จ่ายสะสม $%{customdata[0]:,.0f}<br>จำนวนครั้งที่เช่า %{customdata[1]:,}<extra></extra>",
    ))
    wc_fig.update_xaxes(visible=False, showgrid=False, zeroline=False)
    wc_fig.update_yaxes(visible=False, showgrid=False, zeroline=False)
    _plain_layout(wc_fig)
    wc_fig.update_layout(height=420)

    wcol, tcol = st.columns([3, 2])
    with wcol:
        event = st.plotly_chart(wc_fig, use_container_width=True, on_select="rerun", key="bq05_wc")
        idx = _click_index(event)
        if idx is not None:
            st.session_state["bq05_highlight"] = top_customers.iloc[idx]["full_name"]
            st.rerun()
    with tcol:
        top5 = top_customers.head(5)[["full_name", "city", "country", "total_spend", "rentals"]].rename(columns={
            "full_name": "ลูกค้า", "city": "เมือง", "country": "ประเทศ",
            "total_spend": "ยอดใช้จ่าย ($)", "rentals": "จำนวนครั้งที่เช่า",
        })

        def _hl(row):
            is_hl = row["ลูกค้า"] == highlighted
            return [f"background-color: {SEQUENTIAL[0]}" if is_hl else "" for _ in row]

        st.dataframe(top5.style.apply(_hl, axis=1), hide_index=True, use_container_width=True)
        if highlighted:
            st.caption(f"กำลังไฮไลต์: **{highlighted}** (คลิกชื่ออื่นใน word cloud เพื่อเปลี่ยน)")

    st.divider()
    st.subheader("ข้อ 6 — เรดาร์ระยะทาง: ร้านอยู่ตรงกลาง ลูกค้ากระจายออกไปตามระยะทางและทิศจริง")
    st.caption(
        "ข้อมูลไม่มีพิกัดละติจูด-ลองจิจูดของที่อยู่จริง จึงประมาณตำแหน่งลูกค้าจากพิกัดศูนย์กลาง/เมืองหลวงของประเทศที่ลูกค้าอยู่ "
        "และตำแหน่งร้านจากที่อยู่จริงของร้าน (Store 1 = Lethbridge, Canada · Store 2 = Woodridge, Australia) "
        "— ระยะทางและทิศทางจึงเป็นค่าประมาณระดับประเทศ ไม่ใช่ระยะทางระหว่างบ้านลูกค้ากับร้านจริงเป๊ะๆ"
    )

    rc1, rc2 = st.columns([1, 3])
    with rc1:
        store_choice = st.radio(
            "เลือกที่ตั้งร้าน (address_id)",
            list(STORE_COORDS.keys()),
            format_func=lambda sid: f"Store {sid} ({STORE_COORDS[sid]['city']}, {STORE_COORDS[sid]['country']})",
            key="bq24_store",
        )
    store_origin = STORE_COORDS[store_choice]

    country_for_store = q("""
        select dc.country, count(distinct dc.customer_key) as customers,
               count(*) as rentals, round(sum(f.payment_amount), 2) as revenue
        from main_marts.fact_rental f
        join main_marts.dim_customer dc on f.customer_key = dc.customer_key
        join main_marts.dim_store ds on f.store_key = ds.store_key
        where ds.store_id = ?
        group by 1
    """, [store_choice])

    country_for_store["coords"] = country_for_store["country"].map(COUNTRY_COORDS)
    unmapped = country_for_store[country_for_store["coords"].isna()]
    country_for_store = country_for_store.dropna(subset=["coords"]).copy()
    country_for_store["lat"] = country_for_store["coords"].map(lambda c: c[0])
    country_for_store["lon"] = country_for_store["coords"].map(lambda c: c[1])
    country_for_store["distance_km"] = country_for_store.apply(
        lambda r: _haversine_km(store_origin["lat"], store_origin["lon"], r["lat"], r["lon"]), axis=1,
    )
    country_for_store["bearing_deg"] = country_for_store.apply(
        lambda r: _bearing_deg(store_origin["lat"], store_origin["lon"], r["lat"], r["lon"]), axis=1,
    )

    with rc2:
        if len(country_for_store):
            max_cust = country_for_store["customers"].max()
            min_cust = country_for_store["customers"].min()
            fig24 = go.Figure(go.Scatterpolar(
                r=country_for_store["distance_km"],
                theta=country_for_store["bearing_deg"],
                mode="markers",
                marker=dict(
                    size=country_for_store["customers"],
                    sizemode="area",
                    sizeref=2.0 * max_cust / (34 ** 2) if max_cust else 1,
                    sizemin=6,
                    color=country_for_store["customers"],
                    colorscale=[[0, SEQUENTIAL[1]], [1, SEQUENTIAL[9]]],
                    showscale=True,
                    colorbar=dict(title="จำนวน<br>ลูกค้า", thickness=14),
                    line=dict(width=1, color=CARD_BG),
                ),
                customdata=country_for_store[["country", "customers", "rentals", "revenue", "distance_km"]],
                hovertemplate="%{customdata[0]}<br>ระยะทางโดยประมาณ %{customdata[4]:,.0f} กม."
                              "<br>ลูกค้า %{customdata[1]:,} คน · เช่า %{customdata[2]:,} ครั้ง"
                              "<br>รายได้ $%{customdata[3]:,.0f}<extra></extra>",
            ))
            fig24.update_layout(
                polar=dict(
                    bgcolor=CARD_BG,
                    radialaxis=dict(title="ระยะทางโดยประมาณ (กม.)", showline=True, gridcolor=GRID_COLOR,
                                     color=TEXT_SECONDARY, linecolor=AXIS_COLOR),
                    angularaxis=dict(direction="clockwise", rotation=90,
                                      tickmode="array", tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                                      ticktext=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                                      gridcolor=GRID_COLOR, color=TEXT_SECONDARY, linecolor=AXIS_COLOR),
                ),
                showlegend=False,
                margin=dict(l=30, r=30, t=20, b=20),
                paper_bgcolor=CARD_BG,
                font=dict(family="Inter, sans-serif", size=13, color=TEXT_SECONDARY),
            )
            st.plotly_chart(fig24, use_container_width=True, key="bq24_chart")
            st.caption(
                f"จุดศูนย์กลาง = Store {store_choice} ({store_origin['city']}) · "
                "แต่ละจุด = 1 ประเทศที่มีลูกค้า · ระยะจากจุดศูนย์กลาง = ระยะทางโดยประมาณ · "
                "ทิศ (N/NE/E/…) = ทิศทางโดยประมาณจากร้าน · ขนาด/สีเข้ม = จำนวนลูกค้ามาก"
            )
        else:
            st.caption("ไม่มีข้อมูลลูกค้าที่เช่าจากร้านนี้")

    if len(unmapped):
        st.caption(
            "หมายเหตุ: ประเทศที่ยังไม่มีพิกัดในตารางอ้างอิงของแดชบอร์ด ("
            + ", ".join(sorted(unmapped["country"].unique())) + ") จะไม่ปรากฏในเรดาร์นี้"
        )

# ════════════════════════════════════════════════════════════════════════
# กลุ่มที่ 3: การแบ่งกลุ่มลูกค้าและพฤติกรรมการเช่าซ้ำ
# (Customer Segmentation & Retention) — ข้อ 7-10
# ════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("ข้อ 7 — แบ่งลูกค้าออกเป็น 4 กลุ่มตามความถี่และยอดใช้จ่าย (RFM-style)")
    rfm_raw = q("""
        with agg as (
            select f.customer_key, max(d.full_date) as last_rental,
                   count(*) as frequency, sum(f.payment_amount) as monetary
            from main_marts.fact_rental f
            join main_marts.dim_date d on f.rental_date_key = d.date_key
            group by 1
        ), bounds as (select max(last_rental) as ref_date from agg)
        select a.customer_key, date_diff('day', a.last_rental, b.ref_date) as recency_days,
               a.frequency, a.monetary
        from agg a, bounds b
    """)
    rfm_raw["r_score"] = pd.qcut(rfm_raw["recency_days"].rank(method="first"), 4, labels=[4, 3, 2, 1]).astype(int)
    rfm_raw["f_score"] = pd.qcut(rfm_raw["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm_raw["m_score"] = pd.qcut(rfm_raw["monetary"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)

    def _segment(row):
        if row.r_score >= 3 and row.f_score >= 3 and row.m_score >= 3:
            return "VIP"
        if row.r_score <= 2 and row.f_score <= 2:
            return "กลุ่มที่หายไปแล้ว"
        if row.r_score <= 2:
            return "กลุ่มเสี่ยงหาย"
        return "ลูกค้าประจำ"

    rfm_raw["segment"] = rfm_raw.apply(_segment, axis=1)
    seg_order = ["VIP", "ลูกค้าประจำ", "กลุ่มเสี่ยงหาย", "กลุ่มที่หายไปแล้ว"]
    seg_summary = rfm_raw.groupby("segment", as_index=False).agg(
        customers=("customer_key", "count"), total_monetary=("monetary", "sum"),
    )
    seg_summary["segment"] = pd.Categorical(seg_summary["segment"], categories=seg_order, ordered=True)
    seg_summary = seg_summary.sort_values("segment")

    sc1, sc2 = st.columns([3, 2])
    seg_colors = [SERIES[0], SERIES[2], SERIES[4], SERIES[7]][:len(seg_summary)]
    with sc1:
        fig18a = go.Figure(go.Pie(
            labels=seg_summary["segment"], values=seg_summary["customers"],
            marker=dict(colors=seg_colors, line=dict(color=CARD_BG, width=2)),
            textinfo="label+percent", textfont=dict(color=[_contrast_text(c) for c in seg_colors]),
            hovertemplate="%{label}<br>ลูกค้า %{value:,} คน (%{percent})<extra></extra>",
        ))
        _plain_layout(fig18a)
        st.plotly_chart(fig18a, use_container_width=True, key="bq18_pie")
    with sc2:
        fig18b = px.bar(seg_summary, x="segment", y="total_monetary", text="total_monetary")
        fig18b.update_traces(marker_color=seg_colors, texttemplate="$%{text:,.0f}", textposition="outside")
        _plain_layout(fig18b, y_title="ยอดใช้จ่ายรวมของกลุ่ม ($)")
        st.plotly_chart(fig18b, use_container_width=True, key="bq18_monetary_chart")
    st.caption(
        "เกณฑ์แบ่งกลุ่ม: R/F/M แต่ละตัวแบ่งเป็น 4 ระดับด้วยควอร์ไทล์ (คะแนน 1=ต่ำสุด, 4=สูงสุด) "
        "VIP = R,F,M สูงทั้งหมด (≥3 ทุกตัว), กลุ่มเสี่ยงหาย = Recency ต่ำ (ห่างหายไปนาน) แต่ยังมี Frequency พอใช้ได้, "
        "กลุ่มที่หายไปแล้ว = ทั้ง Recency และ Frequency ต่ำ, ที่เหลือคือลูกค้าประจำ"
    )

    st.divider()
    st.subheader("ข้อ 8 — หมวดหมู่ภาพยนตร์ที่แต่ละกลุ่มลูกค้าเช่ามากที่สุด")
    selected_segment = st.selectbox(
        "เลือกกลุ่มลูกค้า (จาก pie chart ในข้อ 7)",
        seg_order, key="bq19_segment_select",
    )
    rentals_cat = q("""
        select f.customer_key, df.category
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
    """)
    merged = rentals_cat.merge(rfm_raw[["customer_key", "segment"]], on="customer_key", how="inner")
    seg_cat = (
        merged[merged["segment"] == selected_segment]
        .groupby("category").size().reset_index(name="rentals")
        .sort_values("rentals", ascending=False)
    )
    fig19 = px.bar(seg_cat, x="category", y="rentals", text="rentals")
    fig19.update_traces(marker_color=_sequential_shades(len(seg_cat), dark_first=True), textposition="outside")
    _plain_layout(fig19, y_title="จำนวนครั้งที่เช่า")
    st.plotly_chart(fig19, use_container_width=True, key=f"bq19_chart_{selected_segment}")
    if len(seg_cat):
        top_cat = seg_cat.iloc[0]
        st.caption(f'หมวดที่กลุ่ม "{selected_segment}" เช่ามากที่สุดคือ {top_cat["category"]} ({int(top_cat["rentals"]):,} ครั้ง)')

    st.divider()
    st.subheader("ข้อ 9 — ลูกค้ากลับมาเช่าซ้ำภายในกี่สัปดาห์ (คลิกแท่งเพื่อดูข้อ 10)")
    st.caption("วัดระยะห่างจากรอบเช่าที่ 1 ถึงรอบเช่าที่ 2 ของลูกค้าแต่ละคน (ปัดลงเป็นหน่วยสัปดาห์เต็ม) — 1 แท่ง = 1 สัปดาห์")
    repeat_gap = q("""
        with ranked as (
            select f.customer_key, f.rental_id, d.full_date as rental_date, df.category,
                   row_number() over (partition by f.customer_key order by d.full_date, f.rental_id) as rn
            from main_marts.fact_rental f
            join main_marts.dim_date d on f.rental_date_key = d.date_key
            join main_marts.dim_film df on f.film_key = df.film_key
        ),
        first_two as (
            select customer_key,
                   max(case when rn = 1 then rental_date end) as first_date,
                   max(case when rn = 1 then category end) as first_category,
                   max(case when rn = 2 then rental_date end) as second_date,
                   max(case when rn = 2 then category end) as second_category
            from ranked
            where rn <= 2
            group by customer_key
        )
        select customer_key, first_category, second_category,
               date_diff('day', first_date, second_date) as days_gap
        from first_two
        where second_date is not null
    """)
    repeat_gap["week_bucket"] = (repeat_gap["days_gap"] // 7).astype(int)
    repeat_gap["same_category"] = repeat_gap["first_category"] == repeat_gap["second_category"]

    if len(repeat_gap):
        week_counts = repeat_gap.groupby("week_bucket").size().reset_index(name="customers")
        full_weeks = pd.DataFrame({"week_bucket": range(0, int(week_counts["week_bucket"].max()) + 1)})
        week_counts = full_weeks.merge(week_counts, on="week_bucket", how="left")
        week_counts["customers"] = week_counts["customers"].fillna(0).astype(int)
        week_counts["label"] = "สัปดาห์ที่ " + week_counts["week_bucket"].astype(str)

        shades25 = _sequential_shades(len(week_counts), dark_first=True)  # chronological, week 0 first
        fig25 = go.Figure(go.Bar(
            x=week_counts["label"], y=week_counts["customers"], marker_color=shades25,
            text=week_counts["customers"], textposition="outside",
        ))
        _plain_layout(fig25, y_title="จำนวนลูกค้าที่กลับมาเช่าซ้ำ")
        event = st.plotly_chart(fig25, use_container_width=True, on_select="rerun", key="bq25_chart")
        idx = _click_index(event)
        if idx is not None:
            st.session_state["bq26_week"] = int(week_counts.iloc[idx]["week_bucket"])
        st.caption("นับเฉพาะลูกค้าที่มีรายการเช่าอย่างน้อย 2 ครั้ง")

        st.divider()
        selected_week = st.session_state.get("bq26_week", int(week_counts["week_bucket"].iloc[0]))
        st.subheader(f"ข้อ 10 — ลูกค้าที่กลับมาเช่าซ้ำในสัปดาห์ที่ {selected_week} เลือกหมวดหมู่เดิมหรือไม่")
        st.caption("คลิกแท่งใน ข้อ 9 ด้านบนเพื่อเปลี่ยนสัปดาห์ที่ดูตรงนี้")
        week_df = repeat_gap[repeat_gap["week_bucket"] == selected_week]
        if len(week_df):
            same_counts = week_df["same_category"].value_counts()
            same_n = int(same_counts.get(True, 0))
            diff_n = int(same_counts.get(False, 0))
            fig26 = go.Figure(go.Pie(
                labels=["หมวดเดิม", "หมวดใหม่"], values=[same_n, diff_n],
                marker=dict(colors=[DIVERGE_POS, SEQUENTIAL[4]], line=dict(color=CARD_BG, width=2)),
                textinfo="label+percent", textfont=dict(color=[_contrast_text(DIVERGE_POS), _contrast_text(SEQUENTIAL[4])]),
                hovertemplate="%{label}<br>%{value:,} คน (%{percent})<extra></extra>",
            ))
            _plain_layout(fig26)
            st.plotly_chart(fig26, use_container_width=True, key=f"bq26_chart_{selected_week}")
            total_wk = same_n + diff_n
            pct_same = (same_n / total_wk * 100) if total_wk else 0
            st.caption(f"ลูกค้าที่กลับมาเช่าซ้ำในสัปดาห์ที่ {selected_week}: {pct_same:.1f}% เลือกหมวดหมู่เดิมกับรอบแรก จากทั้งหมด {total_wk:,} คน")
        else:
            st.caption("ไม่มีลูกค้าที่กลับมาเช่าซ้ำในสัปดาห์นี้")
    else:
        st.caption("ไม่มีลูกค้าที่มีรายการเช่าตั้งแต่ 2 ครั้งขึ้นไปในชุดข้อมูลนี้")

# ════════════════════════════════════════════════════════════════════════
# กลุ่มที่ 4: การวิเคราะห์เนื้อหาภาพยนตร์ (Content/Movie Analysis) — ข้อ 11-13
# ════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("ข้อ 11 — จำนวนการเช่าแยกตามหมวดหมู่หนัง (คลิกแท่งเพื่อดูข้อ 12)")
    category_rentals = q("""
        select df.category, count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        group by 1 order by rentals desc
    """)
    shades27 = _sequential_shades(len(category_rentals), dark_first=True)  # already sorted desc by rentals
    fig27 = go.Figure(go.Bar(
        x=category_rentals["rentals"], y=category_rentals["category"], orientation="h",
        marker_color=shades27, text=category_rentals["rentals"], textposition="outside",
    ))
    fig27.update_yaxes(autorange="reversed")  # highest count on top
    _plain_layout(fig27, x_title="จำนวนครั้งที่เช่า")
    fig27.update_xaxes(showgrid=True, gridcolor=GRID_COLOR)
    fig27.update_yaxes(showgrid=False, showline=True, linecolor=AXIS_COLOR, autorange="reversed")
    event = st.plotly_chart(fig27, use_container_width=True, on_select="rerun", key="bq27_chart")
    idx = _click_index(event)
    if idx is not None:
        st.session_state["bq28_category"] = category_rentals.iloc[idx]["category"]
    st.caption("ไล่สีเข้ม (มากสุด) → อ่อน (น้อยสุด) ตามจำนวนครั้งที่เช่า ไม่ได้ใช้คนละสีต่อหมวด")

    st.divider()
    selected_cat27 = st.session_state.get("bq28_category", category_rentals.iloc[0]["category"])
    st.subheader(f"ข้อ 12 — จำนวนการเช่าแยกตามเรทหนัง (หมวด: {selected_cat27})")
    st.caption("คลิกแท่งใน ข้อ 11 ด้านบนเพื่อเปลี่ยนหมวดหมู่ที่ดูตรงนี้")
    rating_rentals = q("""
        select df.rating, count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        where df.category = ?
        group by 1 order by rentals desc
    """, [selected_cat27])
    shades28 = _sequential_shades(len(rating_rentals), dark_first=True)
    fig28 = go.Figure(go.Bar(
        x=rating_rentals["rentals"], y=rating_rentals["rating"], orientation="h",
        marker_color=shades28, text=rating_rentals["rentals"], textposition="outside",
    ))
    _plain_layout(fig28, x_title="จำนวนครั้งที่เช่า")
    fig28.update_xaxes(showgrid=True, gridcolor=GRID_COLOR)
    fig28.update_yaxes(showgrid=False, showline=True, linecolor=AXIS_COLOR, autorange="reversed")
    st.plotly_chart(fig28, use_container_width=True, key=f"bq28_chart_{selected_cat27}")

    st.divider()
    actor_rank = q("""
        select da.actor_id, da.first_name || ' ' || da.last_name as actor_name, count(*) as times_rented
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        join main_marts.bridge_film_actor bfa on df.film_key = bfa.film_key
        join main_marts.dim_actor da on bfa.actor_key = da.actor_key
        group by 1, 2 order by times_rented desc limit 20
    """)

    st.subheader("ข้อ 13 — นักแสดงที่ถูกเช่าบ่อยที่สุด (คลิกแถวเพื่อดูรายละเอียดผลงาน)")
    event = st.dataframe(
        actor_rank.rename(columns={"actor_name": "นักแสดง", "times_rented": "จำนวนครั้งที่ถูกเช่ารวม"})[["นักแสดง", "จำนวนครั้งที่ถูกเช่ารวม"]],
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", key="bq12_table",
    )
    rows = event.selection.rows if event and event.selection else []
    if rows:
        picked = actor_rank.iloc[rows[0]]

        @st.dialog(f"ผลงานของ {picked['actor_name']}")
        def _show_actor_popup(actor_id, actor_name):
            films = q("""
                select df.title, count(*) as times_rented
                from main_marts.fact_rental f
                join main_marts.dim_film df on f.film_key = df.film_key
                join main_marts.bridge_film_actor bfa on df.film_key = bfa.film_key
                join main_marts.dim_actor da on bfa.actor_key = da.actor_key
                where da.actor_id = ?
                group by 1 order by times_rented desc
            """, [int(actor_id)])
            st.dataframe(
                films.rename(columns={"title": "ชื่อเรื่อง", "times_rented": "จำนวนครั้งที่ถูกเช่า"}),
                hide_index=True, use_container_width=True,
            )
            st.metric("รวมทุกเรื่อง", f"{int(films['times_rented'].sum()):,} ครั้ง")

        _show_actor_popup(picked["actor_id"], picked["actor_name"])
    else:
        st.caption("คลิกเลือกแถวนักแสดงในตารางด้านบนเพื่อเปิดดูรายชื่อภาพยนตร์ทั้งหมดที่แสดง")

# ════════════════════════════════════════════════════════════════════════
# กลุ่มที่ 5: การดำเนินงานร้าน/พนักงาน (Store Operations & Staff) — ข้อ 14-16
# ════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("ข้อ 14 — จำนวนลูกค้าที่คืนหนังในแต่ละวัน พร้อมชื่อและรหัสลูกค้า")
    st.caption(
        "วันคืนจริงคำนวณจาก วันที่เช่า + จำนวนวันเช่าจริง (rental_duration_actual_days) นับเฉพาะรายการที่คืนแล้ว "
        "— filter ตามเดือนได้ด้านล่าง คลิกวันที่เพื่อดูรายชื่อ+รหัสลูกค้าที่คืนวันนั้น"
    )
    returns_actual = q("""
        select f.rental_id, dc.customer_key, dc.full_name,
               d.full_date + (f.rental_duration_actual_days * interval 1 day) as return_date
        from main_marts.fact_rental f
        join main_marts.dim_date d on f.rental_date_key = d.date_key
        join main_marts.dim_customer dc on f.customer_key = dc.customer_key
        where f.is_returned
    """)
    returns_actual["return_date"] = pd.to_datetime(returns_actual["return_date"])

    if len(returns_actual):
        month_periods29 = sorted(returns_actual["return_date"].dt.to_period("M").unique())
        month_options29 = [str(p) for p in month_periods29]
        picked_month29 = st.selectbox("เลือกเดือน", month_options29, index=len(month_options29) - 1, key="bq29_month")
        year29, mon29 = map(int, picked_month29.split("-"))
        month_returns = returns_actual[returns_actual["return_date"].dt.to_period("M").astype(str) == picked_month29]
        counts29 = month_returns.groupby(month_returns["return_date"].dt.day).size()

        weeks29 = cal.Calendar(firstweekday=0).monthdayscalendar(year29, mon29)
        z29 = [[counts29.get(day) if day != 0 else None for day in week] for week in weeks29]
        text29 = [[str(day) if day != 0 else "" for day in week] for week in weeks29]

        fig29 = go.Figure(go.Heatmap(
            z=z29, text=text29, texttemplate="%{text}",
            colorscale=[[0, SEQUENTIAL[0]], [1, SEQUENTIAL[4]]],
            hovertemplate="วันที่ %{text}<br>จำนวนลูกค้าที่คืนหนัง %{z}<extra></extra>",
            showscale=False, xgap=3, ygap=3,
        ))
        fig29.update_yaxes(autorange="reversed", showticklabels=False)
        fig29.update_xaxes(tickvals=list(range(7)), ticktext=["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"], side="top")
        fig29.update_layout(height=320)
        _plain_layout(fig29)
        event29 = st.plotly_chart(fig29, use_container_width=True, on_select="rerun", key="bq29_chart")

        clicked_day29 = None
        if event29 and event29.selection and event29.selection.points:
            pt = event29.selection.points[0]
            wk, dw = pt.get("y"), pt.get("x")
            if wk is not None and dw is not None:
                day_num = weeks29[int(wk)][int(dw)]
                if day_num:
                    clicked_day29 = day_num

        if clicked_day29:
            sel_date29 = pd.Timestamp(year=year29, month=mon29, day=clicked_day29).date()
            todays29 = month_returns[month_returns["return_date"].dt.date == sel_date29]
            st.write(f"**ลูกค้าที่คืนหนังวันที่ {sel_date29}:** ({len(todays29)} รายการ)")
            st.dataframe(
                todays29[["customer_key", "full_name"]].rename(
                    columns={"customer_key": "รหัสลูกค้า", "full_name": "ลูกค้า"}
                ),
                hide_index=True, use_container_width=True,
            )
        else:
            st.caption("คลิกวันที่ในปฏิทินด้านบนเพื่อดูรายชื่อและรหัสลูกค้าที่คืนหนังวันนั้น")
    else:
        st.caption("ไม่มีรายการที่คืนแล้วในชุดข้อมูลนี้")

    st.divider()
    st.subheader("ข้อ 15 — จำนวนการปล่อยเช่าของพนักงานแต่ละคน")
    staff_rentals = q("""
        select dst.staff_id, dst.full_name, count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_staff dst on f.staff_key = dst.staff_key
        group by 1, 2 order by 1
    """)
    staff_colors = [SERIES[i % len(SERIES)] for i in range(len(staff_rentals))]
    fig21 = go.Figure(go.Pie(
        labels=staff_rentals["full_name"], values=staff_rentals["rentals"],
        marker=dict(colors=staff_colors, line=dict(color=CARD_BG, width=2)),
        textinfo="label+percent", textfont=dict(color=[_contrast_text(c) for c in staff_colors]),
        hovertemplate="%{label}<br>ปล่อยเช่า %{value:,} ครั้ง (%{percent})<extra></extra>",
    ))
    _plain_layout(fig21)
    st.plotly_chart(fig21, use_container_width=True, key="bq21_chart")

    st.divider()
    st.subheader("ข้อ 16 — จำนวนการปล่อยเช่าของพนักงานแยกตามหมวดหมู่หนัง")
    sel_staff_name = st.selectbox(
        "เลือกพนักงาน (จาก pie chart ในข้อ 15)",
        staff_rentals["full_name"].tolist(), key="bq21_staff_select",
    )
    sel_staff = staff_rentals.loc[staff_rentals["full_name"] == sel_staff_name, "staff_id"].iloc[0]
    staff_cat = q("""
        select df.category, count(*) as rentals
        from main_marts.fact_rental f
        join main_marts.dim_film df on f.film_key = df.film_key
        join main_marts.dim_staff dst on f.staff_key = dst.staff_key
        where dst.staff_id = ?
        group by 1 order by rentals desc
    """, [int(sel_staff)])
    fig21b = px.bar(staff_cat, x="category", y="rentals", text="rentals")
    fig21b.update_traces(marker_color=_sequential_shades(len(staff_cat), dark_first=True), textposition="outside")
    _plain_layout(fig21b, y_title="จำนวนครั้งที่ปล่อยเช่า")
    st.plotly_chart(fig21b, use_container_width=True, key="bq21b_chart")

st.divider()
st.caption(
    "ข้อมูล: Sakila DVD Rental · แหล่งข้อมูล main_marts.fact_rental / fact_inventory / dim_* "
    "· pipeline: dbt + DuckDB (ดู sakila_dw_duckdb/)"
)
