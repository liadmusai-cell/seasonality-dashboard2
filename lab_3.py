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
    st.markdown("### X / FinTwit monitors")
    if "x_handles_raw_v2" not in st.session_state:
        st.session_state.x_handles_raw_v2 = (
            "KobeissiLetter, unusual_whales, spotgamma, zerohedge,\n"
            "DeItaone, FirstSquawk, LiveSquawk, Fxhedgers, financialjuice,\n"
            "NickTimiraos, Lisaabramowicz1, TheStalwart, FedGuy12, biancoresearch,\n"
            "charliebilello, RyanDetrick, awealthofcs, allstarcharts, JC_ParetsX,\n"
            "MacroAlf, NorthmanTrader, SantiagoAuFund, elerianm,\n"
            "LynAldenContact, lukeGromen, RaoulGMI, jsmian,\n"
            "WSJmarkets, business, TheTranscript_, EricBalchunas,\n"
            "Calcalist, globesnews"
        )
    x_handles_raw = st.text_area(
        "Accounts to score (comma or newline)",
        value=st.session_state.x_handles_raw_v2,
        height=140,
        help="Curated macro / flow / news handles. Saved in this session. Used by Live Outlook.",
    )
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Save list", use_container_width=True):
            st.session_state.x_handles_raw_v2 = x_handles_raw
            st.success("Saved")
    with b2:
        if st.button("Reset list", use_container_width=True):
            del st.session_state.x_handles_raw_v2
            st.rerun()

    st.markdown("---")
    st.caption(
        "Data: Yahoo Finance via yfinance. Prices are auto-adjusted. "
        "ISO weeks run Mon-Sun. Cash session returns use the last trading close of each ISO week. "
        "On Sat/Sun the Live Outlook tab defaults to the week that opens Monday."
    )


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
if getattr(last_close_ts, "tzinfo", None) is not None:
    last_close_ts = last_close_ts.tz_convert("UTC").tz_localize(None)
now_year, now_week = iso_now(last_close_ts)
wall_year, wall_week = iso_now()
if abs((pd.Timestamp(datetime.now()) - last_close_ts).days) <= 10:
    now_year, now_week = wall_year, wall_week

_now_ts = pd.Timestamp.now()
_wd = int(_now_ts.weekday())
_days_to_mon = (7 - _wd) % 7 or 7
next_year, next_week = iso_now(_now_ts + pd.Timedelta(days=_days_to_mon))
is_weekend = _wd >= 5

stats = seasonality_table(weekly, lookback_years, now_year, now_week)
if stats.empty:
    st.warning("Lookback window is too short for this ticker. Expand the window.")
    st.stop()

plot_stats = stats.copy()
if metric_choice == "Median return":
    plot_stats = plot_stats.rename(columns={"avg_return": "_avg_bak"})
    plot_stats["avg_return"] = plot_stats["median_return"]

matrix = year_week_matrix(weekly, lookback_years, now_year)
current_row = stats.loc[stats["week"] == now_week]
if current_row.empty:
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
wk_clock = (
    f"Weekend: ISO {now_week} still on the calendar (ends tonight). "
    f"US cash already closed Friday. Trading Outlook defaults to week {next_week} (opens Monday)."
    if is_weekend
    else f"In-week: ISO {now_week} is the active trading week. Next ISO week is {next_week}."
)

tab_hist, tab_live = st.tabs(["Historical Seasonality", "Live Outlook"])
with tab_hist:
    st.markdown(
        f"""
        <div class="week-banner">
          <div class="week-kicker">Calendar ISO week · {ticker}</div>
          <div class="week-title">ISO Week {now_week} · {now_year}
            &nbsp;<span class="pill {rating_cls}">{rating_label}</span>
          </div>
          <div class="week-sub">
            Last daily close {last_dt} · History from {first_dt} · Lookback: {lookback_label.lower()}
            {" · " + week_note if week_note else ""}<br/>{wk_clock}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Win rate", fmt_pct_plain(float(row["win_rate"]), 1), color_class(float(row["win_rate"]) - 0.5), f"{int(row['observations'])} completed weeks"),
        (c2, "Average return", fmt_pct(float(row["avg_return"])), color_class(float(row["avg_return"])), "Mean Friday-to-Friday week"),
        (c3, "Median return", fmt_pct(float(row["median_return"])), color_class(float(row["median_return"])), "Less sensitive to outliers"),
        (c4, "Volatility (σ)", fmt_pct_plain(float(row["volatility"]), 2), "neu", "Std. dev. of weekly returns"),
        (c5, "Max gain / loss", f"{fmt_pct(float(row['max_gain']), 1)} / {fmt_pct(float(row['max_drawdown']), 1)}", color_class(float(row["avg_return"])), rating_why),
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
    st.plotly_chart(bar_seasonality(plot_stats, now_week), use_container_width=True)
    left, right = st.columns((1.15, 1))
    with left:
        st.plotly_chart(winrate_chart(stats, now_week), use_container_width=True)
    with right:
        st.plotly_chart(current_week_distribution(weekly, shown_week, lookback_years, now_year), use_container_width=True)
    st.plotly_chart(heatmap_returns(matrix, now_week), use_container_width=True)

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
    display = table[["week", "observations", "Avg return %", "Median return %", "Win rate %", "Volatility %", "Max gain %", "Max drawdown %", "is_current"]].rename(columns={"week": "Week", "observations": "N", "is_current": "Current week"})

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

    st.download_button(
        "Download table as CSV",
        data=display.to_csv(index=False).encode("utf-8"),
        file_name=f"{ticker.replace('^', '')}_weekly_seasonality.csv",
        mime="text/csv",
    )
