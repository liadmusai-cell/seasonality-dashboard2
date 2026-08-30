"""Weekly Seasonality Lab."""
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Weekly Seasonality Lab", page_icon="📈", layout="wide")

PRESETS = {
    "S&P 500": "^GSPC",
    "Nasdaq-100": "^NDX",
    "Nasdaq-100 ETF (QQQ)": "QQQ",
    "Dow Jones": "^DJI",
    "Russell 2000": "^RUT",
    "S&P 500 ETF (SPY)": "SPY",
}

DARK = "<style>.stApp{background:#070b14;color:#e5eaf3}[data-testid='stSidebar']{background:#0b1220}</style>"
LIGHT = "<style>.stApp{background:#f3f6fb;color:#0f172a}[data-testid='stSidebar']{background:#fff}</style>"

def flatten(raw, ticker):
    if raw is None or raw.empty:
        return pd.DataFrame()
    close = raw["Close"]
    if isinstance(close, pd.DataFrame):
        close = close[ticker] if ticker in close.columns else close.iloc[:, 0]
    out = pd.DataFrame({"Close": pd.to_numeric(close, errors="coerce")}).dropna()
    out.index = pd.to_datetime(out.index)
    return out.sort_index()

@st.cache_data(ttl=86400, show_spinner=False)
def fetch(ticker):
    raw = yf.download(ticker, period="max", interval="1d", auto_adjust=True, progress=False, threads=False)
    return flatten(raw, ticker)

def weekly_rets(daily):
    iso = daily.index.isocalendar()
    d = daily.copy()
    d["y"] = iso.year.astype(int)
    d["w"] = iso.week.astype(int)
    w = d.groupby(["y", "w"])["Close"].last().reset_index().sort_values(["y", "w"])
    w["ret"] = w["Close"].pct_change()
    return w.dropna()

def stats_table(w, years, ny, nw):
    d = w.copy()
    if years is not None:
        d = d[d["y"] >= ny - years]
    d = d[~((d["y"] == ny) & (d["w"] == nw))]
    g = d.groupby("w")["ret"]
    s = pd.DataFrame({
        "week": g.mean().index.astype(int),
        "n": g.size().values,
        "avg": g.mean().values,
        "med": g.median().values,
        "win": g.apply(lambda x: float((x > 0).mean())).values,
        "vol": g.std(ddof=1).values,
        "mx": g.max().values,
        "mn": g.min().values,
    })
    s["cur"] = s["week"] == nw
    return s.sort_values("week")

def layout(theme):
    if theme == "Light":
        return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff", font=dict(color="#0f172a", size=13), margin=dict(l=40, r=20, t=40, b=40))
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(11,16,32,0.6)", font=dict(color="#d7deea", size=13), margin=dict(l=40, r=20, t=40, b=40))

def pct(x):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:+.2f}%"

def pctn(x):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.2f}%"

with st.sidebar:
    st.markdown("### Controls")
    name = st.selectbox("Index / asset", list(PRESETS), index=0)
    custom = st.text_input("Custom ticker", value="")
    ticker = custom.strip().upper() if custom.strip() else PRESETS[name]
    look = st.selectbox("Lookback", ["10 years", "15 years", "20 years", "30 years", "All available history"], index=2)
    years = {"10 years": 10, "15 years": 15, "20 years": 20, "30 years": 30, "All available history": None}[look]
    metric = st.radio("Bar chart metric", ["Average return", "Median return"], horizontal=True)
    theme = st.radio("Background", ["Dark", "Light"], horizontal=True)

st.markdown(LIGHT if theme == "Light" else DARK, unsafe_allow_html=True)
st.title("Weekly Seasonality Lab")

daily = fetch(ticker)
if daily.empty:
    st.error(f"No data for {ticker}")
    st.stop()

w = weekly_rets(daily)
iso = pd.Timestamp(datetime.now()).isocalendar()
ny, nw = int(iso.year), int(iso.week)
s = stats_table(w, years, ny, nw)
if s.empty:
    st.warning("Not enough history")
    st.stop()

row = s.loc[s["week"] == nw]
row = s.iloc[(s["week"] - nw).abs().argsort()[:1]] if row.empty else row
r = row.iloc[0]
st.subheader(f"ISO Week {nw} · {ny} · {ticker}")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Win rate", pctn(float(r["win"])))
c2.metric("Average return", pct(float(r["avg"])))
c3.metric("Median return", pct(float(r["med"])))
c4.metric("Volatility", pctn(float(r["vol"])))
c5.metric("Max gain / loss", f"{pct(float(r['mx']))} / {pct(float(r['mn']))}")

ycol = "med" if metric == "Median return" else "avg"
colors = ["#fbbf24" if cur else ("#34d399" if v >= 0 else "#fb7185") for v, cur in zip(s[ycol], s["cur"])]
grid = "#e2e8f0" if theme == "Light" else "#1e293b"
fig = go.Figure(go.Bar(
    x=s["week"], y=s[ycol] * 100, marker_color=colors,
    customdata=np.stack([s["week"], s["avg"]*100, s["med"]*100, s["win"]*100, s["vol"]*100, s["mx"]*100, s["mn"]*100, s["n"]], axis=1),
    hovertemplate="<b>Week %{customdata[0]:.0f}</b><br>Avg: %{customdata[1]:+.2f}%<br>Median: %{customdata[2]:+.2f}%<br>Win: %{customdata[3]:.2f}%<br>Vol: %{customdata[4]:.2f}%<br>Max: %{customdata[5]:+.2f}%<br>Min: %{customdata[6]:+.2f}%<br>N=%{customdata[7]:.0f}<extra></extra>",
))
fig.add_vline(x=nw, line_dash="dash", line_color="#fbbf24")
fig.update_layout(**layout(theme), title="Weekly return by ISO week", xaxis=dict(dtick=1, gridcolor=grid), yaxis=dict(title="Return (%)", tickformat=".2f", gridcolor=grid), height=400)
st.plotly_chart(fig, use_container_width=True)

fig2 = go.Figure(go.Bar(x=s["week"], y=s["win"]*100, marker_color=np.where(s["win"]>=0.5, "#34d399", "#fb7185"), hovertemplate="Week %{x}<br>Win rate: %{y:.2f}%<extra></extra>"))
fig2.add_hline(y=50, line_dash="dot", line_color="#fbbf24")
fig2.update_layout(**layout(theme), title="Win rate by week", xaxis=dict(dtick=1, gridcolor=grid), yaxis=dict(tickformat=".2f", range=[0, 100], gridcolor=grid), height=300)
st.plotly_chart(fig2, use_container_width=True)

mat = w.copy()
if years is not None:
    mat = mat[mat["y"] >= ny - years]
pv = mat.pivot_table(index="y", columns="w", values="ret", aggfunc="last")
fig3 = go.Figure(go.Heatmap(z=pv.values*100, x=list(pv.columns), y=[str(i) for i in pv.index], colorscale="RdYlGn", zmid=0, colorbar=dict(ticksuffix="%", tickformat=".2f"), hovertemplate="Year %{y} Week %{x}<br>%{z:+.2f}%<extra></extra>"))
fig3.update_layout(**layout(theme), title="Year x week heatmap", height=max(360, 18*len(pv.index)+80), yaxis=dict(autorange="reversed"))
st.plotly_chart(fig3, use_container_width=True)

table = pd.DataFrame({
    "Week": s["week"], "N": s["n"],
    "Avg return %": (s["avg"]*100).round(2),
    "Median return %": (s["med"]*100).round(2),
    "Win rate %": (s["win"]*100).round(2),
    "Volatility %": (s["vol"]*100).round(2),
    "Max gain %": (s["mx"]*100).round(2),
    "Max drawdown %": (s["mn"]*100).round(2),
    "Current week": s["cur"],
})
st.dataframe(table, hide_index=True, use_container_width=True, height=400, column_config={
    "Avg return %": st.column_config.NumberColumn(format="%+.2f%%"),
    "Median return %": st.column_config.NumberColumn(format="%+.2f%%"),
    "Win rate %": st.column_config.NumberColumn(format="%.2f%%"),
    "Volatility %": st.column_config.NumberColumn(format="%.2f%%"),
    "Max gain %": st.column_config.NumberColumn(format="%+.2f%%"),
    "Max drawdown %": st.column_config.NumberColumn(format="%+.2f%%"),
})
st.download_button("Download CSV", table.to_csv(index=False).encode("utf-8"), f"{ticker.replace('^','')}_weekly_seasonality.csv", "text/csv")
