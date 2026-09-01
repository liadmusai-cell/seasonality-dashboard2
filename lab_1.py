"""
Weekly Seasonality Lab
----------------------
Interactive Streamlit dashboard that computes historical calendar-week
seasonality for any Yahoo Finance ticker and highlights the current ISO week.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

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
    html, body, [class*="css"] { font-family: "IBM Plex Sans", "Segoe UI", sans-serif; }
    .stApp {
        background:
            radial-gradient(1200px 500px at 10% -10%, rgba(34,197,94,0.08), transparent 50%),
            radial-gradient(900px 400px at 100% 0%, rgba(56,189,248,0.08), transparent 45%),
            #070b14;
        color: #e5eaf3;
    }
    [data-testid="stSidebar"] { background: #0b1220; border-right: 1px solid #1e293b; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color: #d7deea !important; }
    .hero { padding: 0.2rem 0 0.8rem 0; }
    .hero h1 { font-size: 2.05rem; font-weight: 700; letter-spacing: -0.03em; margin: 0 0 0.25rem 0; color: #f8fafc; }
    .hero p { color: #94a3b8; margin: 0; font-size: 0.98rem; }
    .week-banner {
        background: linear-gradient(135deg, #111827 0%, #0b3b2e 55%, #102033 100%);
        border: 1px solid #1f4d3d; border-radius: 16px; padding: 1.05rem 1.25rem;
        margin: 0.4rem 0 1rem 0; box-shadow: 0 10px 40px rgba(0,0,0,0.25);
    }
    .week-kicker { color: #86efac; font-size: 0.72rem; letter-spacing: 0.14em; font-weight: 600; text-transform: uppercase; }
    .week-title { font-size: 1.55rem; font-weight: 700; color: #f8fafc; margin: 0.15rem 0; }
    .week-sub { color: #94a3b8; font-size: 0.88rem; }
    .metric-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 14px; padding: 0.9rem 1rem; height: 100%; }
    .metric-label { color: #94a3b8; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 600; }
    .metric-value { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 1.55rem; font-weight: 600; margin-top: 0.2rem; color: #f8fafc; }
    .metric-hint { color: #64748b; font-size: 0.78rem; margin-top: 0.15rem; }
    .pos { color: #34d399; } .neg { color: #fb7185; } .neu { color: #fbbf24; }
    .pill { display: inline-block; padding: 0.18rem 0.6rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
    .pill-good { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.35); }
    .pill-bad { background: rgba(244,63,94,0.15); color: #fb7185; border: 1px solid rgba(244,63,94,0.35); }
    .pill-ok { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.35); }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _flatten_ohlc(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    close = None
    if isinstance(raw.columns, pd.MultiIndex):
        fields = raw.columns.get_level_values(0)
        if "Close" in fields:
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):
                close = close[ticker] if ticker in close.columns else close.iloc[:, 0]
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
    out = pd.DataFrame({"Close": pd.to_numeric(close, errors="coerce")}).dropna()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    return out.sort_index()


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_prices(ticker: str) -> pd.DataFrame:
    raw = yf.download(ticker, period="max", interval="1d", auto_adjust=True, progress=False, threads=False)
    return _flatten_ohlc(raw, ticker)


def iso_now(as_of: Optional[pd.Timestamp] = None) -> tuple[int, int]:
    if as_of is None:
        as_of = pd.Timestamp.now()
    as_of = pd.Timestamp(as_of)
    if getattr(as_of, "tzinfo", None) is not None:
        as_of = as_of.tz_convert("UTC").tz_localize(None)
    iso = as_of.isocalendar()
    return int(iso.year), int(iso.week)


def build_weekly_returns(daily: pd.DataFrame) -> pd.DataFrame:
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
    return weekly.dropna(subset=["ret"])


def _t_crit_90(df: int) -> float:
    table = {
        1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943,
        7: 1.895, 8: 1.860, 9: 1.833, 10: 1.812, 12: 1.782, 15: 1.753,
        20: 1.725, 30: 1.697, 40: 1.684, 60: 1.671,
    }
    if df <= 1:
        return 6.314
    for k in sorted(table):
        if df <= k:
            return table[k]
    return 1.645


def _p_from_t(t: float, df: int) -> float:
    z = abs(float(t))
    if df < 30:
        z = z * (1.0 - 1.0 / max(4.0 * df, 4.0))
    return float(min(1.0, max(0.0, math.erfc(z / math.sqrt(2.0)))))


def significance_pill(pval: float, avg: float, n: int) -> tuple[str, str]:
    if n < 8 or pval != pval:
        return "Low sample", "pill-ok"
    if pval < 0.10:
        if avg > 0:
            return "Significant up-week", "pill-good"
        return "Significant down-week", "pill-bad"
    return "Not significant (90%)", "pill-ok"


def seasonality_table(weekly: pd.DataFrame, lookback_years: Optional[int], now_year: int, now_week: int) -> pd.DataFrame:
    data = weekly.copy()
    if lookback_years is not None:
        data = data[data["iso_year"] >= now_year - lookback_years]
    data = data[~((data["iso_year"] == now_year) & (data["iso_week"] == now_week))]
    if data.empty:
        return pd.DataFrame()
    grouped = data.groupby("iso_week")["ret"]
    stats = pd.DataFrame({
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
    })
    stats = stats.sort_values("week").reset_index(drop=True)
    n = stats["observations"].astype(float)
    se = stats["volatility"] / np.sqrt(n.clip(lower=1.0))
    se = se.replace(0, np.nan)
    stats["tstat"] = stats["avg_return"] / se
    tcrit = np.array([_t_crit_90(int(x) - 1) if x >= 3 else np.nan for x in n])
    stats["ci90_low"] = stats["avg_return"] - tcrit * se
    stats["ci90_high"] = stats["avg_return"] + tcrit * se
    stats["pval"] = [
        _p_from_t(float(t), int(nn) - 1) if nn >= 3 and t == t else np.nan
        for t, nn in zip(stats["tstat"], n)
    ]
    overall = float(data["ret"].mean())
    stats["typical_week"] = overall
    stats["edge_vs_avg"] = stats["avg_return"] - overall
    stats["is_current"] = stats["week"] == now_week
    return stats
