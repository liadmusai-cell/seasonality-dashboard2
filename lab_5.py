def render_journal(ticker, weekly, lookback_years, now_year, now_week):
    st.markdown(
        """
        <div class=\"week-banner\">
          <div class=\"week-kicker\">Journal &middot; walk-forward seasonal sleeve &middot; {ticker}</div>
          <div class=\"week-title\">Did the seasonal edge actually pay?</div>
          <div class=\"week-sub\">
            Each week is scored using only history available <em>before</em> that week (no peeking).
            Long if score &ge; +20, Short if &le; &minus;20, else Flat. NAV starts at 100.
          </div>
        </div>
        """.format(ticker=ticker),
        unsafe_allow_html=True,
    )
    wf = walk_forward_seasonal(weekly, lookback_years, 8)
    if wf is None or wf.empty:
        st.info("Need more history before a walk-forward journal can be scored (min 8 prior observations of the same ISO week).")
        return
    directed = wf[wf["call"] != "Flat"]
    hits = directed["hit"].dropna() if len(directed) else pd.Series(dtype=float)
    hit_rate = float(hits.mean()) if len(hits) else float("nan")
    nav = float((1.0 + wf["pnl"].astype(float)).cumprod().iloc[-1] * 100)
    longs = wf.loc[wf["call"] == "Long", "realized"]
    shorts = wf.loc[wf["call"] == "Short", "realized"]
    gp = float(wf.loc[wf["pnl"] > 0, "pnl"].sum())
    gl = float((-wf.loc[wf["pnl"] < 0, "pnl"]).sum())
    pf = (gp / gl) if gl > 0 else float("nan")

    def _fmt_pct(x):
        return "—" if x != x else "{:+.2f}%".format(x * 100)

    cards = [
        ("Directional hit rate",
         ("{:.1f}%".format(hit_rate * 100) if hit_rate == hit_rate else "—"),
         color_class((hit_rate - 0.5) if hit_rate == hit_rate else 0),
         "{} long/short weeks".format(len(directed))),
        ("Walk-forward NAV", "{:.1f}".format(nav), color_class(nav - 100),
         "Start 100 · {} weeks".format(len(wf))),
        ("Avg realized | Long",
         _fmt_pct(float(longs.mean()) if len(longs) else float("nan")),
         color_class(float(longs.mean()) if len(longs) else 0),
         "{} weeks".format(len(longs))),
        ("Avg realized | Short",
         _fmt_pct(float(shorts.mean()) if len(shorts) else float("nan")),
         color_class(float(shorts.mean()) if len(shorts) else 0),
         "Raw week return when short"),
        ("Profit factor",
         ("{:.2f}".format(pf) if pf == pf else "—"),
         color_class((pf - 1) if pf == pf else 0),
         "Gross wins / gross losses"),
    ]
    cols = st.columns(5)
    for col, (lab, val, cls, hint) in zip(cols, cards):
        with col:
            st.markdown(
                '<div class="metric-card"><div class="metric-label">{}</div>'
                '<div class="metric-value {}">{}</div>'
                '<div class="metric-hint">{}</div></div>'.format(lab, cls, val, hint),
                unsafe_allow_html=True,
            )
    st.caption("Flat weeks are neither hits nor misses. 52 weeks are tested every year — a few will look significant by chance.")
    a, b = st.columns(2)
    with a:
        st.plotly_chart(journal_equity_figure(wf), use_container_width=True)
    with b:
        st.plotly_chart(journal_scatter_figure(wf), use_container_width=True)

    show = wf.tail(80).copy()
    show["Score"] = show["score"].map(lambda x: round(float(x), 1))
    show["t-stat"] = show["tstat"].map(lambda x: round(float(x), 2) if x == x else None)
    show["p-value"] = show["pval"].map(lambda x: round(float(x), 3) if x == x else None)
    show["Realized %"] = show["realized"] * 100
    show["PnL %"] = show["pnl"] * 100
    show["Hit"] = show["hit"].map(lambda x: "Yes" if x is True else ("No" if x is False else "—"))
    table = show[["iso_year", "iso_week", "n", "Score", "t-stat", "p-value", "call", "Realized %", "PnL %", "Hit"]].rename(
        columns={"iso_year": "Year", "iso_week": "Week", "n": "N", "call": "Call"}
    )
    st.markdown("### Last 80 scored weeks")
    st.dataframe(
        table, hide_index=True, use_container_width=True, height=380,
        column_config={
            "Year": st.column_config.NumberColumn(format="%d"),
            "Week": st.column_config.NumberColumn(format="%d"),
            "N": st.column_config.NumberColumn(format="%d"),
            "Score": st.column_config.NumberColumn(format="%+.1f"),
            "t-stat": st.column_config.NumberColumn(format="%+.2f"),
            "p-value": st.column_config.NumberColumn(format="%.3f"),
            "Realized %": st.column_config.NumberColumn(format="%+.2f%%"),
            "PnL %": st.column_config.NumberColumn(format="%+.2f%%"),
        },
    )
    st.download_button(
        "Download walk-forward journal CSV",
        data=table.to_csv(index=False).encode("utf-8"),
        file_name="{}_seasonal_journal.csv".format(str(ticker).replace("^", "")),
        mime="text/csv",
    )

    st.markdown("### Live weighted Outlook log")
    live = load_live_journal()
    rows = [v for v in live.values() if str(v.get("ticker", "")).upper() == str(ticker).upper()]
    if not rows:
        st.caption("Open the Live Outlook tab once to stamp this week's weighted conviction. Realized return fills after the ISO week completes.")
        return
    lr = pd.DataFrame(rows)
    key = weekly[["iso_year", "iso_week", "ret"]].drop_duplicates()
    lr["iso_year"] = lr["iso_year"].astype(int)
    lr["iso_week"] = lr["iso_week"].astype(int)
    lr = lr.merge(key, how="left", on=["iso_year", "iso_week"])
    lr["status"] = ["Closed" if (int(y), int(w)) < (int(now_year), int(now_week)) else "Open" for y, w in zip(lr["iso_year"], lr["iso_week"])]
    lr["Realized %"] = lr["ret"] * 100
    lr["Hit"] = [
        ("Yes" if ((c == "Long" and r > 0) or (c == "Short" and r < 0)) else ("—" if (s == "Open" or c == "Flat" or r != r) else "No"))
        for c, r, s in zip(lr["call"], lr["ret"], lr["status"])
    ]
    out = lr.sort_values(["iso_year", "iso_week"], ascending=False)[
        ["iso_year", "iso_week", "conviction", "hist", "macro", "x", "call", "status", "Realized %", "Hit", "as_of"]
    ].rename(columns={"iso_year": "Year", "iso_week": "Week", "conviction": "Conviction", "hist": "H", "macro": "M", "x": "X", "call": "Call", "status": "Status", "as_of": "Logged"})
    st.dataframe(
        out, hide_index=True, use_container_width=True,
        column_config={
            "Conviction": st.column_config.NumberColumn(format="%+.1f"),
            "H": st.column_config.NumberColumn(format="%+.1f"),
            "M": st.column_config.NumberColumn(format="%+.1f"),
            "X": st.column_config.NumberColumn(format="%+.1f"),
            "Realized %": st.column_config.NumberColumn(format="%+.2f%%"),
        },
    )

try:
    hist_s, _why = historical_component(row)
    snap = _load_snapshot()
    handles = _parse_handles(x_handles_raw)
    x_posts, x_meta = live_posts_for_visit(handles, snap)
    mac_s, _cal = macro_component(snap.get("calendar") or [], now_year, now_week)
    x_s, _p = x_component(x_posts, handles)
    conv = float(np.clip(0.40 * hist_s + 0.35 * mac_s + 0.25 * x_s, -100, 100))
    upsert_live_journal({
        "ticker": str(ticker),
        "iso_year": int(now_year),
        "iso_week": int(now_week),
        "conviction": round(float(conv), 1),
        "hist": round(float(hist_s), 1),
        "macro": round(float(mac_s), 1),
        "x": round(float(x_s), 1),
        "call": ("Long" if conv >= 20 else ("Short" if conv <= -20 else "Flat")),
        "as_of": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": str((x_meta or {}).get("source") or ""),
    })
except Exception:
    pass

try:
    with tab_journal:
        render_journal(ticker, weekly, lookback_years, now_year, now_week)
except Exception as _jerr:
    st.error("Journal hit an error; other tabs are unchanged.")
    st.exception(_jerr)
