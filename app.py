"""
Weekly Seasonality Lab
----------------------
Interactive Streamlit dashboard that computes historical calendar-week
seasonality for any Yahoo Finance ticker and highlights the current ISO week.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------------
# Page / theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Weekly Seasonality Lab",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRESETS = {
    "S&P 500": "^GSPC",
    "Nasdaq-100": "^NDX",
    "Nasdaq-100 ETF (QQQ)": "QQQ",
    "Dow Jones": "^DJI",
    "Russell 2000": "^RUT",
    "S&P 500 ETF (SPY)": "SPY",
    "Nasdaq Composite": "^IXIC",
    "FTSE 100": "^FTSE",
    "DAX": "^GDAXI",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "Gold": "GC=F",
    "Bitcoin": "BTC-USD",
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(11,16,32,0.6)",
    font=dict(color="#d7deea", family="Inter, Segoe UI, sans-serif", size=13),
    margin=dict(l=40, r=20, t=50, b=40),
    hoverlabel=dict(bgcolor="#0f172a", font_size=13, font_color="#f8fafc"),
)

st.markdown(
    """
    <style>
    @import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap");

    html, body, [class*="css"] {
        font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    }
    .stApp {
        background:
            radial-gradient(1200px 500px at 10% -10%, rgba(34,197,94,0.08), transparent 50%),
            radial-gradient(900px 400px at 100% 0%, rgba(56,189,248,0.08), transparent 45%),
            #070b14;
        color: #e5eaf3;
    }
    [data-testid="stSidebar"] {
        background: #0b1220;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {
        color: #d7deea !important;
    }
    .hero {
        padding: 0.2rem 0 0.8rem 0;
    }
    .hero h1 {
        font-size: 2.05rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        margin: 0 0 0.25rem 0;
        color: #f8fafc;
    }
    .hero p {
        color: #94a3b8;
        margin: 0;
        font-size: 0.98rem;
    }
    .week-banner {
        background: linear-gradient(135deg, #111827 0%, #0b3b2e 55%, #102033 100%);
        border: 1px solid #1f4d3d;
        border-radius: 16px;
        padding: 1.05rem 1.25rem;
        margin: 0.4rem 0 1rem 0;
        box-shadow: 0 10px 40px rgba(0,0,0,0.25);
    }
    .week-kicker {
        color: #86efac;
        font-size: 0.72rem;
        letter-spacing: 0.14em;
        font-weight: 600;
        text-transform: uppercase;
    }
    .week-title {
        font-size: 1.55rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0.15rem 0 0.15rem 0;
    }
    .week-sub {
        color: #94a3b8;
        font-size: 0.88rem;
    }
    .metric-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 14px;
        padding: 0.9rem 1rem 0.85rem 1rem;
        height: 100%;
    }
    .metric-label {
        color: #94a3b8;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 600;
    }
    .metric-value {
        font-family: "IBM Plex Mono", ui-monospace, monospace;
        font-size: 1.55rem;
        font-weight: 600;
        margin-top: 0.2rem;
        color: #f8fafc;
    }
    .metric-hint {
        color: #64748b;
        font-size: 0.78rem;
        margin-top: 0.15rem;
    }
    .pos { color: #34d399; }
    .neg { color: #fb7185; }
    .neu { color: #fbbf24; }
    .pill {
        display: inline-block;
        padding: 0.18rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.04em;
    }
    .pill-good { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.35); }
    .pill-bad { background: rgba(244,63,94,0.15); color: #fb7185; border: 1px solid rgba(244,63,94,0.35); }
    .pill-ok { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.35); }
    div[data-testid="stMetricValue"] {
        font-family: "IBM Plex Mono", ui-monospace, monospace;
    }
    .stDataFrame { border-radius: 12px; overflow: hidden; }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------
def _flatten_ohlc(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normalize yfinance output (single or MultiIndex columns) to a Close series frame."""
    if raw is None or raw.empty:
        return pd.DataFrame()

    close = None
    if isinstance(raw.columns, pd.MultiIndex):
        # Typical shape: level 0 = field, level 1 = ticker
        fields = raw.columns.get_level_values(0)
        if "Close" in fields:
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):
                if ticker in close.columns:
                    close = close[ticker]
                else:
                    close = close.iloc[:, 0]
        elif "Adj Close" in fields:
            close = raw["Adj Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
    else:
        if "Close" in raw.columns:
            close = raw["Close"]
        elif "Adj Close" in raw.columns:
            close = raw["Adj Close"]
        else:
            close = raw.iloc[:, 0]

    out = pd.DataFrame({"Close": pd.to_numeric(close, errors="coerce")})
    out = out.dropna()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    return out


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_prices(ticker: str) -> pd.DataFrame:
    """Download maximum daily history. Cached for 24 hours per ticker."""
    raw = yf.download(
        ticker,
        period="max",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    return _flatten_ohlc(raw, ticker)


def iso_now(as_of: Optional[pd.Timestamp] = None) -> tuple[int, int]:
    if as_of is None:
        as_of = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None)
    iso = as_of.isocalendar()
    return int(iso.year), int(iso.week)


def build_weekly_returns(daily: pd.DataFrame) -> pd.DataFrame:
    """Last close of each ISO week → sequential weekly return."""
    if daily.empty:
        return pd.DataFrame(columns=["iso_year", "iso_week", "Close", "ret", "week_end"])

    frame = daily.copy()
    iso = frame.index.isocalendar()
    frame["iso_year"] = iso.year.astype(int)
    frame["iso_week"] = iso.week.astype(int)

    weekly = (
        frame.groupby(["iso_year", "iso_week"], sort=True)
        .agg(Close=("Close", "last"), week_end=("Close", lambda s: s.index.max()))
        .reset_index()
        .sort_values(["iso_year", "iso_week"])
    )
    weekly["ret"] = weekly["Close"].pct_change()
    weekly = weekly.dropna(subset=["ret"])
    return weekly


def seasonality_table(weekly: pd.DataFrame, lookback_years: Optional[int], now_year: int, now_week: int) -> pd.DataFrame:
    """Aggregate weekly returns into calendar-week statistics. Drops the in-progress week."""
    data = weekly.copy()
    if lookback_years is not None:
        data = data[data["iso_year"] >= now_year - lookback_years]

    # Exclude the unfinished current ISO week from historical averages
    data = data[~((data["iso_year"] == now_year) & (data["iso_week"] == now_week))]

    if data.empty:
        return pd.DataFrame()

    grouped = data.groupby("iso_week")["ret"]

    stats = pd.DataFrame(
        {
            "week": grouped.mean().index.astype(int),
            "observations": grouped.size().values,
            "avg_return": grouped.mean().values,
            "median_return": grouped.median().values,
            "win_rate": grouped.apply(lambda s: float((s > 0).mean())).values,
            "volatility": grouped.std(ddof=1).values,
            "max_gain": grouped.max().values,
            "max_drawdown": grouped.min().values,
            "p25": grouped.quantile(0.25).values,
            "p75": grouped.quantile(0.75).values,
        }
    )
    stats = stats.sort_values("week").reset_index(drop=True)
    stats["is_current"] = stats["week"] == now_week
    return stats


def year_week_matrix(weekly: pd.DataFrame, lookback_years: Optional[int], now_year: int) -> pd.DataFrame:
    data = weekly.copy()
    if lookback_years is not None:
        data = data[data["iso_year"] >= now_year - lookback_years]
    if data.empty:
        return pd.DataFrame()
    pivot = data.pivot_table(index="iso_year", columns="iso_week", values="ret", aggfunc="last")
    pivot = pivot.reindex(columns=range(1, int(pivot.columns.max()) + 1))
    return pivot.sort_index(ascending=False)


def risk_rating(avg_return: float, win_rate: float, vol: float) -> tuple[str, str, str]:
    """Return (label, css_class, one-line rationale)."""
    if np.isnan(avg_return) or np.isnan(win_rate):
        return "N/A", "pill-ok", "Insufficient history"

    edge = avg_return / vol if vol and not np.isnan(vol) and vol > 0 else avg_return

    if win_rate >= 0.60 and avg_return > 0 and edge > 0.15:
        return "Favorable", "pill-good", "Historically positive drift with a majority of up-weeks"
    if win_rate <= 0.42 or avg_return < -0.0015:
        return "Caution", "pill-bad", "Below-average hit rate or negative mean week"
    return "Neutral", "pill-ok", "Mixed historical edge — treat as noise unless confirmed"


def fmt_pct(x: float, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x * 100:+.{digits}f}%"


def fmt_pct_plain(x: float, digits: int = 1) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x * 100:.{digits}f}%"


def color_class(x: float) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "neu"
    if x > 0:
        return "pos"
    if x < 0:
        return "neg"
    return "neu"


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def bar_seasonality(stats: pd.DataFrame, now_week: int) -> go.Figure:
    df = stats.copy()
    colors = np.where(df["avg_return"] >= 0, "#34d399", "#fb7185")
    colors = [
        "#fbbf24" if bool(cur) else c
        for c, cur in zip(colors, df["is_current"])
    ]

    custom = np.stack(
        [
            df["week"],
            df["avg_return"] * 100,
            df["median_return"] * 100,
            df["win_rate"] * 100,
            df["volatility"] * 100,
            df["max_gain"] * 100,
            df["max_drawdown"] * 100,
            df["observations"],
        ],
        axis=1,
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["week"],
            y=df["avg_return"] * 100,
            marker_color=colors,
            marker_line_width=0,
            name="Avg return",
            customdata=custom,
            hovertemplate=(
                "<b>Week %{customdata[0]:.0f}</b><br>"
                "Avg return: %{customdata[1]:+.2f}%<br>"
                "Median: %{customdata[2]:+.2f}%<br>"
                "Win rate: %{customdata[3]:.1f}%<br>"
                "Volatility: %{customdata[4]:.2f}%<br>"
                "Max gain: %{customdata[5]:+.2f}%<br>"
                "Max loss: %{customdata[6]:+.2f}%<br>"
                "N = %{customdata[7]:.0f}"
                "<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=0, line_color="#334155", line_width=1)
    fig.add_vline(
        x=now_week,
        line_dash="dash",
        line_color="#fbbf24",
        line_width=2,
        annotation_text=f"Current week {now_week}",
        annotation_position="top",
        annotation_font_color="#fbbf24",
    )
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Average weekly return by ISO week", font=dict(size=16)),
        xaxis=dict(
            title="ISO week",
            dtick=1,
            gridcolor="#1e293b",
            zeroline=False,
            range=[0.5, 53.5],
        ),
        yaxis=dict(title="Average return (%)", gridcolor="#1e293b", zeroline=False),
        bargap=0.12,
        height=430,
    )
    return fig


def heatmap_returns(matrix: pd.DataFrame, now_week: int) -> go.Figure:
    z = matrix.values * 100
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=list(matrix.columns),
            y=[str(i) for i in matrix.index],
            colorscale="RdYlGn",
            zmid=0,
            colorbar=dict(title="Return %", ticksuffix="%"),
            hovertemplate="Year %{y} · Week %{x}<br>Return: %{z:+.2f}%<extra></extra>",
            xgap=1,
            ygap=1,
        )
    )
    fig.add_vline(x=now_week - 0.5, line_color="#fbbf24", line_width=2, line_dash="dot")
    fig.add_vline(x=now_week + 0.5, line_color="#fbbf24", line_width=2, line_dash="dot")
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Year × week return heatmap", font=dict(size=16)),
        xaxis=dict(title="ISO week", dtick=1, gridcolor="#1e293b", side="top"),
        yaxis=dict(title="ISO year", autorange="reversed", gridcolor="#1e293b"),
        height=max(360, 22 * len(matrix.index) + 80),
    )
    return fig


def current_week_distribution(weekly: pd.DataFrame, week: int, lookback_years: Optional[int], now_year: int) -> go.Figure:
    data = weekly[weekly["iso_week"] == week].copy()
    if lookback_years is not None:
        data = data[data["iso_year"] >= now_year - lookback_years]
    data = data[data["iso_year"] != now_year] if data["iso_year"].eq(now_year).any() else data

    fig = go.Figure()
    if data.empty:
        fig.update_layout(**PLOTLY_LAYOUT, title="No history for this week", height=320)
        return fig

    fig.add_trace(
        go.Histogram(
            x=data["ret"] * 100,
            nbinsx=min(24, max(8, len(data) // 2)),
            marker_color="#38bdf8",
            opacity=0.85,
            name="Weekly return",
        )
    )
    mean_x = float(data["ret"].mean() * 100)
    fig.add_vline(x=mean_x, line_color="#34d399", line_dash="dash", annotation_text=f"mean {mean_x:+.2f}%")
    fig.add_vline(x=0, line_color="#64748b", line_width=1)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text=f"Return distribution · week {week}", font=dict(size=16)),
        xaxis=dict(title="Weekly return (%)", gridcolor="#1e293b"),
        yaxis=dict(title="Years", gridcolor="#1e293b"),
        bargap=0.05,
        height=320,
        showlegend=False,
    )
    return fig


def winrate_chart(stats: pd.DataFrame, now_week: int) -> go.Figure:
    colors = np.where(stats["win_rate"] >= 0.5, "#34d399", "#fb7185")
    fig = go.Figure(
        go.Bar(
            x=stats["week"],
            y=stats["win_rate"] * 100,
            marker_color=colors,
            hovertemplate="Week %{x}<br>Win rate: %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_hline(y=50, line_color="#fbbf24", line_dash="dot", line_width=1)
    fig.add_vline(x=now_week, line_dash="dash", line_color="#fbbf24", line_width=1)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Historical win rate by week", font=dict(size=16)),
        xaxis=dict(title="ISO week", dtick=1, gridcolor="#1e293b", range=[0.5, 53.5]),
        yaxis=dict(title="Win rate (%)", gridcolor="#1e293b", range=[0, 100]),
        height=320,
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Controls")
    preset_name = st.selectbox("Index / asset", list(PRESETS.keys()), index=0)
    custom = st.text_input(
        "Custom ticker (overrides preset)",
        value="",
        placeholder="e.g. AAPL, ^GSPC, QQQ",
        help="Any Yahoo Finance symbol. Indices usually start with ^.",
    )
    ticker = custom.strip().upper() if custom.strip() else PRESETS[preset_name]

    lookback_label = st.selectbox(
        "Lookback window",
        ["10 years", "15 years", "20 years", "30 years", "All available history"],
        index=2,
    )
    lookback_map = {
        "10 years": 10,
        "15 years": 15,
        "20 years": 20,
        "30 years": 30,
        "All available history": None,
    }
    lookback_years = lookback_map[lookback_label]

    metric_choice = st.radio(
        "Bar chart metric",
        ["Average return", "Median return"],
        horizontal=True,
    )

    st.markdown("---")
    st.caption(
        "Data: Yahoo Finance via yfinance. Prices are auto-adjusted. "
        "Weeks follow the ISO calendar (Mon–Sun). Returns use the last "
        "trading close of each ISO week. Cache refreshes every 24 hours."
    )


# ---------------------------------------------------------------------------
# Load + compute
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <h1>Weekly Seasonality Lab</h1>
      <p>Historical ISO-week edge for major indices — refreshed from live market data, no CSV required.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.spinner(f"Fetching maximum history for {ticker}…"):
    try:
        daily = fetch_prices(ticker)
    except Exception as exc:
        st.error(f"Download failed for `{ticker}`: {exc}")
        st.stop()

if daily.empty:
    st.error(
        f"No price history returned for `{ticker}`. "
        "Check the symbol on Yahoo Finance (indices often need a leading `^`)."
    )
    st.stop()

weekly = build_weekly_returns(daily)
if weekly.empty:
    st.error("Not enough weekly observations to compute seasonality.")
    st.stop()

last_close_ts = pd.Timestamp(daily.index.max())
now_year, now_week = iso_now(last_close_ts)
# Prefer wall-clock week if last close is recent (within 10 days)
wall_year, wall_week = iso_now()
if abs((pd.Timestamp(datetime.now()) - last_close_ts).days) <= 10:
    now_year, now_week = wall_year, wall_week

stats = seasonality_table(weekly, lookback_years, now_year, now_week)
if stats.empty:
    st.warning("Lookback window is too short for this ticker. Expand the window.")
    st.stop()

# If the chosen metric is median, swap the bar series visually by cloning
plot_stats = stats.copy()
if metric_choice == "Median return":
    plot_stats = plot_stats.rename(columns={"avg_return": "_avg_bak"})
    plot_stats["avg_return"] = plot_stats["median_return"]

matrix = year_week_matrix(weekly, lookback_years, now_year)
current_row = stats.loc[stats["week"] == now_week]
# Week 53 may be missing in some windows
if current_row.empty:
    # Fall back to nearest available week display
    fallback_week = int(stats.iloc[(stats["week"] - now_week).abs().argsort()[:1]]["week"])
    current_row = stats.loc[stats["week"] == fallback_week]
    shown_week = fallback_week
    week_note = f"No sample for ISO week {now_week} in this window — showing week {fallback_week}."
else:
    shown_week = now_week
    week_note = ""

row = current_row.iloc[0]
rating_label, rating_cls, rating_why = risk_rating(
    float(row["avg_return"]), float(row["win_rate"]), float(row["volatility"])
)

first_dt = daily.index.min().strftime("%Y-%m-%d")
last_dt = daily.index.max().strftime("%Y-%m-%d")
n_years_used = int(weekly["iso_year"].nunique()) if lookback_years is None else min(
    lookback_years, int(weekly["iso_year"].nunique())
)

# ---------------------------------------------------------------------------
# Current-week banner + metrics
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="week-banner">
      <div class="week-kicker">Active calendar week · {ticker}</div>
      <div class="week-title">ISO Week {now_week} · {now_year}
        &nbsp;<span class="pill {rating_cls}">{rating_label}</span>
      </div>
      <div class="week-sub">
        Last daily close {last_dt} · History from {first_dt} · Lookback: {lookback_label.lower()}
        {" · " + week_note if week_note else ""}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5 = st.columns(5)
cards = [
    (
        c1,
        "Win rate",
        fmt_pct_plain(float(row["win_rate"]), 1),
        color_class(float(row["win_rate"]) - 0.5),
        f"{int(row['observations'])} completed weeks",
    ),
    (
        c2,
        "Average return",
        fmt_pct(float(row["avg_return"])),
        color_class(float(row["avg_return"])),
        "Mean Friday-to-Friday week",
    ),
    (
        c3,
        "Median return",
        fmt_pct(float(row["median_return"])),
        color_class(float(row["median_return"])),
        "Less sensitive to outliers",
    ),
    (
        c4,
        "Volatility (σ)",
        fmt_pct_plain(float(row["volatility"]), 2),
        "neu",
        "Std. dev. of weekly returns",
    ),
    (
        c5,
        "Max gain / loss",
        f"{fmt_pct(float(row['max_gain']), 1)} / {fmt_pct(float(row['max_drawdown']), 1)}",
        color_class(float(row["avg_return"])),
        rating_why,
    ),
]
for col, label, value, cls, hint in cards:
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
              <div class="metric-label">{label}</div>
              <div class="metric-value {cls}">{value}</div>
              <div class="metric-hint">{hint}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("")

# ---------------------------------------------------------------------------
# Main charts
# ---------------------------------------------------------------------------
st.plotly_chart(bar_seasonality(plot_stats, now_week), use_container_width=True)

left, right = st.columns((1.15, 1))
with left:
    st.plotly_chart(winrate_chart(stats, now_week), use_container_width=True)
with right:
    st.plotly_chart(
        current_week_distribution(weekly, shown_week, lookback_years, now_year),
        use_container_width=True,
    )

st.plotly_chart(heatmap_returns(matrix, now_week), use_container_width=True)

# ---------------------------------------------------------------------------
# Ranked extremes + table
# ---------------------------------------------------------------------------
st.markdown("### Week rankings")
best = stats.nlargest(5, "avg_return")[["week", "avg_return", "win_rate", "observations"]]
worst = stats.nsmallest(5, "avg_return")[["week", "avg_return", "win_rate", "observations"]]
r1, r2 = st.columns(2)
with r1:
    st.caption("Strongest average weeks")
    show = best.copy()
    show["avg_return"] = (show["avg_return"] * 100).map(lambda x: f"{x:+.2f}%")
    show["win_rate"] = (show["win_rate"] * 100).map(lambda x: f"{x:.1f}%")
    show.columns = ["Week", "Avg return", "Win rate", "N"]
    st.dataframe(show, hide_index=True, use_container_width=True)
with r2:
    st.caption("Weakest average weeks")
    show = worst.copy()
    show["avg_return"] = (show["avg_return"] * 100).map(lambda x: f"{x:+.2f}%")
    show["win_rate"] = (show["win_rate"] * 100).map(lambda x: f"{x:.1f}%")
    show.columns = ["Week", "Avg return", "Win rate", "N"]
    st.dataframe(show, hide_index=True, use_container_width=True)

st.markdown("### Full seasonality table")
table = stats.copy()
table["Avg return %"] = table["avg_return"] * 100
table["Median return %"] = table["median_return"] * 100
table["Win rate %"] = table["win_rate"] * 100
table["Volatility %"] = table["volatility"] * 100
table["Max gain %"] = table["max_gain"] * 100
table["Max drawdown %"] = table["max_drawdown"] * 100
display = table[
    [
        "week",
        "observations",
        "Avg return %",
        "Median return %",
        "Win rate %",
        "Volatility %",
        "Max gain %",
        "Max drawdown %",
        "is_current",
    ]
].rename(
    columns={
        "week": "Week",
        "observations": "N",
        "is_current": "Current week",
    }
)

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    height=420,
    column_config={
        "Week": st.column_config.NumberColumn(format="%d"),
        "N": st.column_config.NumberColumn(format="%d"),
        "Avg return %": st.column_config.NumberColumn(format="%+.2f%%"),
        "Median return %": st.column_config.NumberColumn(format="%+.2f%%"),
        "Win rate %": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
        "Volatility %": st.column_config.NumberColumn(format="%.2f%%"),
        "Max gain %": st.column_config.NumberColumn(format="%+.2f%%"),
        "Max drawdown %": st.column_config.NumberColumn(format="%+.2f%%"),
        "Current week": st.column_config.CheckboxColumn(disabled=True),
    },
)

csv_bytes = display.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download table as CSV",
    data=csv_bytes,
    file_name=f"{ticker.replace('^', '')}_weekly_seasonality.csv",
    mime="text/csv",
)

with st.expander("Methodology"):
    st.markdown(
        f"""
        - **Source:** Yahoo Finance daily bars (`auto_adjust=True`) for `{ticker}`.
        - **Week definition:** ISO-8601 week (Monday–Sunday). Week 53 appears only in years that contain 53 Thursdays.
        - **Weekly return:** last available session close of ISO week *t* versus last close of ISO week *t−1*.
        - **Current week:** ISO week {now_week} of {now_year}. The in-progress week is excluded from the averages so a partial bar does not bias the sample.
        - **Win rate:** share of historical weeks with a strictly positive return.
        - **Max drawdown** here is the worst single-week loss observed for that calendar week — not a multi-week peak-to-trough.
        - **Risk rating:** heuristic from win rate, mean return, and mean/vol. It is **not** a trading signal.
        - **Cache:** `@st.cache_data(ttl=86400)` so a refresh within 24 hours does not re-hit the API.
        """
    )
