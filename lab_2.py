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


def bar_seasonality(stats: pd.DataFrame, now_week: int) -> go.Figure:
    df = stats.copy()
    colors = np.where(df["avg_return"] >= 0, "#34d399", "#fb7185")
    colors = ["#fbbf24" if bool(cur) else c for c, cur in zip(colors, df["is_current"])]
    n = len(df)
    tstat = np.round(df["tstat"].fillna(0), 2) if "tstat" in df.columns else np.zeros(n)
    pval = np.round(df["pval"].fillna(1), 3) if "pval" in df.columns else np.ones(n)
    edge = np.round(df["edge_vs_avg"].fillna(0) * 100, 2) if "edge_vs_avg" in df.columns else np.zeros(n)
    ci_lo = np.round(df["ci90_low"].fillna(0) * 100, 2) if "ci90_low" in df.columns else np.zeros(n)
    ci_hi = np.round(df["ci90_high"].fillna(0) * 100, 2) if "ci90_high" in df.columns else np.zeros(n)
    custom = np.stack(
        [
            df["week"],
            np.round(df["avg_return"] * 100, 2),
            np.round(df["median_return"] * 100, 2),
            np.round(df["win_rate"] * 100, 2),
            np.round(df["volatility"] * 100, 2),
            np.round(df["max_gain"] * 100, 2),
            np.round(df["max_drawdown"] * 100, 2),
            df["observations"],
            tstat, pval, edge, ci_lo, ci_hi,
        ],
        axis=1,
    )
    line_w = [1.8 if (p == p and p < 0.10) else 0 for p in pval]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["week"],
            y=np.round(df["avg_return"] * 100, 2),
            marker_color=colors,
            marker_line_width=line_w,
            marker_line_color="#f8fafc",
            name="Avg return",
            customdata=custom,
            hovertemplate=(
                "<b>Week %{customdata[0]:.0f}</b><br>"
                "Avg return: %{customdata[1]:+.2f}%<br>"
                "90% CI: %{customdata[11]:+.2f} to %{customdata[12]:+.2f}%<br>"
                "Median: %{customdata[2]:+.2f}%<br>"
                "Win rate: %{customdata[3]:.2f}%<br>"
                "t-stat: %{customdata[8]:+.2f}<br>"
                "p-value: %{customdata[9]:.3f}<br>"
                "Edge vs typical: %{customdata[10]:+.2f}%<br>"
                "N = %{customdata[7]:.0f}"
                "<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=0, line_color="#334155", line_width=1)
    if "typical_week" in df.columns and len(df):
        typ = float(df["typical_week"].iloc[0]) * 100
        fig.add_hline(y=typ, line_color="#38bdf8", line_dash="dot", line_width=1,
                      annotation_text=f"typical week {typ:+.2f}%", annotation_font_color="#38bdf8")
    fig.add_vline(
        x=now_week, line_dash="dash", line_color="#fbbf24", line_width=2,
        annotation_text=f"Current week {now_week}", annotation_position="top",
        annotation_font_color="#fbbf24",
    )
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Average weekly return by ISO week · outline = p<10%", font=dict(size=16)),
        xaxis=dict(title="ISO week", dtick=1, gridcolor="#1e293b", zeroline=False, range=[0.5, 53.5]),
        yaxis=dict(title="Average return (%)", gridcolor="#1e293b", zeroline=False, hoverformat=".2f", tickformat=".2f"),
        bargap=0.12, height=430,
    )
    return fig


def heatmap_returns(matrix: pd.DataFrame, now_week: int) -> go.Figure:
    z = np.round(matrix.values * 100, 2)
    fig = go.Figure(
        data=go.Heatmap(
            z=z, x=list(matrix.columns), y=[str(i) for i in matrix.index],
            colorscale="RdYlGn", zmid=0, colorbar=dict(title="Return %", ticksuffix="%"),
            hovertemplate="Year %{y} · Week %{x}<br>Return: %{z:+.2f}%<extra></extra>",
            xgap=1, ygap=1,
        )
    )
    fig.add_vline(x=now_week - 0.5, line_color="#fbbf24", line_width=2, line_dash="dot")
    fig.add_vline(x=now_week + 0.5, line_color="#fbbf24", line_width=2, line_dash="dot")
    fig.update_layout(
        **PLOTLY_LAYOUT, title=dict(text="Year × week return heatmap", font=dict(size=16)),
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
    fig.add_trace(go.Histogram(
        x=np.round(data["ret"] * 100, 2), nbinsx=min(24, max(8, len(data) // 2)),
        marker_color="#38bdf8", opacity=0.85, name="Weekly return",
        hovertemplate="Return: %{x:+.2f}%<br>Count: %{y:.0f}<extra></extra>",
    ))
    mean_x = float(data["ret"].mean() * 100)
    fig.add_vline(x=mean_x, line_color="#34d399", line_dash="dash", annotation_text=f"mean {mean_x:+.2f}%")
    fig.add_vline(x=0, line_color="#64748b", line_width=1)
    fig.update_layout(
        **PLOTLY_LAYOUT, title=dict(text=f"Return distribution · week {week}", font=dict(size=16)),
        xaxis=dict(title="Weekly return (%)", gridcolor="#1e293b", hoverformat=".2f", tickformat=".2f"),
        yaxis=dict(title="Years", gridcolor="#1e293b"), bargap=0.05, height=320, showlegend=False,
    )
    return fig


def winrate_chart(stats: pd.DataFrame, now_week: int) -> go.Figure:
    colors = np.where(stats["win_rate"] >= 0.5, "#34d399", "#fb7185")
    fig = go.Figure(go.Bar(
        x=stats["week"], y=np.round(stats["win_rate"] * 100, 2),
        marker_color=colors, hovertemplate="Week %{x}<br>Win rate: %{y:.2f}%<extra></extra>",
    ))
    fig.add_hline(y=50, line_color="#fbbf24", line_dash="dot", line_width=1)
    fig.add_vline(x=now_week, line_dash="dash", line_color="#fbbf24", line_width=1)
    fig.update_layout(
        **PLOTLY_LAYOUT, title=dict(text="Historical win rate by week", font=dict(size=16)),
        xaxis=dict(title="ISO week", dtick=1, gridcolor="#1e293b", range=[0.5, 53.5]),
        yaxis=dict(title="Win rate (%)", gridcolor="#1e293b", range=[0, 100], hoverformat=".2f", tickformat=".2f"),
        height=320,
    )
    return fig


def walk_forward_seasonal(weekly: pd.DataFrame, lookback_years: Optional[int], min_n: int = 8) -> pd.DataFrame:
    w = weekly.sort_values(["iso_year", "iso_week"]).reset_index(drop=True)
    buckets = {k: [] for k in range(1, 54)}
    rows = []
    for rec in w.itertuples(index=False):
        iso_y = int(rec.iso_year)
        iso_w = int(rec.iso_week)
        realized = float(rec.ret)
        hist = buckets[iso_w]
        if lookback_years is not None:
            floor = iso_y - int(lookback_years)
            hist = [x for x in hist if x[0] >= floor]
            buckets[iso_w] = hist
        if len(hist) >= min_n:
            rets = np.array([x[1] for x in hist], dtype=float)
            n = int(len(rets))
            mean = float(rets.mean())
            std = float(rets.std(ddof=1))
            wr = float((rets > 0).mean())
            se = std / math.sqrt(n) if std == std and std > 0 else float("nan")
            tstat = mean / se if se == se and se > 0 else float("nan")
            pval = _p_from_t(tstat, n - 1) if tstat == tstat else float("nan")
            score = float(np.clip(mean * 4500.0 + (wr - 0.5) * 180.0, -100, 100))
            if score >= 20:
                call, pnl = "Long", realized
            elif score <= -20:
                call, pnl = "Short", -realized
            else:
                call, pnl = "Flat", 0.0
            hit = None if call == "Flat" else bool((call == "Long" and realized > 0) or (call == "Short" and realized < 0))
            rows.append({
                "iso_year": iso_y, "iso_week": iso_w, "n": n,
                "tstat": tstat, "pval": pval, "score": score, "call": call,
                "realized": realized, "pnl": pnl, "hit": hit,
            })
        buckets[iso_w].append((iso_y, realized))
    return pd.DataFrame(rows)


def journal_equity_figure(jf: pd.DataFrame) -> go.Figure:
    d = jf.reset_index(drop=True)
    nav = 100.0 * (1.0 + d["pnl"].astype(float)).cumprod()
    xs = list(range(len(d)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=[100.0] * len(d), mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=xs, y=np.round(nav, 2), mode="lines", name="NAV",
        line=dict(color="#34d399", width=2.4), fill="tonexty", fillcolor="rgba(52,211,153,0.14)",
        customdata=np.stack([d["iso_year"], d["iso_week"], np.round(d["pnl"] * 100, 2), d["call"]], axis=1),
        hovertemplate="%{customdata[0]:.0f}-W%{customdata[1]:.0f} · %{customdata[3]}<br>NAV %{y:.2f}<br>Week PnL %{customdata[2]:+.2f}%<extra></extra>",
    ))
    fig.add_hline(y=100, line_color="#64748b", line_dash="dot", line_width=1)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Walk-forward NAV · Long +week / Short −week / Flat 0", font=dict(size=16)),
        xaxis=dict(title="Completed weeks (chronological)", gridcolor="#1e293b"),
        yaxis=dict(title="NAV (start 100)", gridcolor="#1e293b", hoverformat=".2f", tickformat=".1f"),
        height=360, showlegend=False,
    )
    return fig


def journal_scatter_figure(jf: pd.DataFrame) -> go.Figure:
    d = jf[jf["call"] != "Flat"].copy()
    fig = go.Figure()
    if d.empty:
        fig.update_layout(**PLOTLY_LAYOUT, title="No directional weeks yet", height=320)
        return fig
    colors = ["#34d399" if bool(h) else "#fb7185" for h in d["hit"]]
    fig.add_trace(go.Scatter(
        x=np.round(d["score"], 1), y=np.round(d["realized"] * 100, 2),
        mode="markers", marker=dict(color=colors, size=9, opacity=0.82, line=dict(width=0)),
        customdata=np.stack([d["iso_year"], d["iso_week"], d["call"]], axis=1),
        hovertemplate="%{customdata[0]:.0f}-W%{customdata[1]:.0f} · %{customdata[2]}<br>Score %{x:.1f}<br>Realized %{y:+.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#334155", line_width=1)
    fig.add_vline(x=0, line_color="#334155", line_width=1)
    fig.add_vline(x=20, line_color="#34d399", line_dash="dot", line_width=1)
    fig.add_vline(x=-20, line_color="#fb7185", line_dash="dot", line_width=1)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Seasonal score vs realized week · green = hit", font=dict(size=16)),
        xaxis=dict(title="Walk-forward seasonal score", gridcolor="#1e293b", hoverformat=".1f"),
        yaxis=dict(title="Realized week return (%)", gridcolor="#1e293b", hoverformat=".2f", tickformat=".2f"),
        height=360,
    )
    return fig


def _journal_file() -> Path:
    here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    return here / "outlook_journal.json"


def load_live_journal() -> dict:
    if "_live_journal" in st.session_state and isinstance(st.session_state["_live_journal"], dict):
        mem = st.session_state["_live_journal"]
    else:
        mem = {}
    try:
        disk = json.loads(_journal_file().read_text(encoding="utf-8"))
        if isinstance(disk, dict):
            mem = {**mem, **disk}
    except Exception:
        pass
    st.session_state["_live_journal"] = mem
    return mem


def upsert_live_journal(entry: dict) -> dict:
    data = load_live_journal()
    key = "{}|{}|{}".format(entry.get("ticker"), entry.get("iso_year"), entry.get("iso_week"))
    data[key] = entry
    st.session_state["_live_journal"] = data
    try:
        _journal_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass
    return data
