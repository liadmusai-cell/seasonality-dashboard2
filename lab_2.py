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
    colors = [
        "#fbbf24" if bool(cur) else c
        for c, cur in zip(colors, df["is_current"])
    ]

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
        ],
        axis=1,
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["week"],
            y=np.round(df["avg_return"] * 100, 2),
            marker_color=colors,
            marker_line_width=0,
            name="Avg return",
            customdata=custom,
            hovertemplate=(
                "<b>Week %{customdata[0]:.0f}</b><br>"
                "Avg return: %{customdata[1]:+.2f}%<br>"
                "Median: %{customdata[2]:+.2f}%<br>"
                "Win rate: %{customdata[3]:.2f}%<br>"
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
        yaxis=dict(title="Average return (%)", gridcolor="#1e293b", zeroline=False, hoverformat=".2f", tickformat=".2f"),
        bargap=0.12,
        height=430,
    )
    return fig


def heatmap_returns(matrix: pd.DataFrame, now_week: int) -> go.Figure:
    z = np.round(matrix.values * 100, 2)
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
            x=np.round(data["ret"] * 100, 2),
            nbinsx=min(24, max(8, len(data) // 2)),
            marker_color="#38bdf8",
            opacity=0.85,
            name="Weekly return",
            hovertemplate="Return: %{x:+.2f}%<br>Count: %{y:.0f}<extra></extra>",
        )
    )
    mean_x = float(data["ret"].mean() * 100)
    fig.add_vline(x=mean_x, line_color="#34d399", line_dash="dash", annotation_text=f"mean {mean_x:+.2f}%")
    fig.add_vline(x=0, line_color="#64748b", line_width=1)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text=f"Return distribution · week {week}", font=dict(size=16)),
        xaxis=dict(title="Weekly return (%)", gridcolor="#1e293b", hoverformat=".2f", tickformat=".2f"),
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
            y=np.round(stats["win_rate"] * 100, 2),
            marker_color=colors,
            hovertemplate="Week %{x}<br>Win rate: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_hline(y=50, line_color="#fbbf24", line_dash="dot", line_width=1)
    fig.add_vline(x=now_week, line_dash="dash", line_color="#fbbf24", line_width=1)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Historical win rate by week", font=dict(size=16)),
        xaxis=dict(title="ISO week", dtick=1, gridcolor="#1e293b", range=[0.5, 53.5]),
        yaxis=dict(title="Win rate (%)", gridcolor="#1e293b", range=[0, 100], hoverformat=".2f", tickformat=".2f"),
        height=320,
    )
    return fig

