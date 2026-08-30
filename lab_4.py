from pathlib import Path
import json

DEFAULT_X_HANDLES = [
    "KobeissiLetter", "unusual_whales", "spotgamma", "zerohedge",
    "FirstSquawk", "LiveSquawk", "DeItaone", "MacroAlf",
    "TheStalwart", "charliebilello", "NickTimiraos",
]
BULL_TERMS = (
    "bullish", "risk-on", "risk on", "buy dips", "buy the dip", "positive gamma",
    "dealers should buy", "long positioning", "extremely bullish", "call stance",
    "support", "rally", "beat", "held the tape", "bull market",
)
BEAR_TERMS = (
    "bearish", "risk-off", "risk off", "put skew", "hawkish", "hike",
    "disappointment", "downturn", "hotter", "hot inflation", "fear",
    "shorts", "sell", "crowded", "complacency",
)

def _parse_handles(raw: str) -> list[str]:
    parts, seen, out = [], set(), []
    for chunk in raw.replace("\n", ",").split(","):
        h = chunk.strip().lstrip("@")
        if h:
            parts.append(h)
    for h in parts:
        k = h.lower()
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out or list(DEFAULT_X_HANDLES)

def _load_snapshot() -> dict:
    path = Path(__file__).resolve().parent / "x_snapshot.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"as_of": "", "calendar": [], "posts": []}

def _lexicon_score(text: str) -> float:
    t = (text or "").lower()
    b = sum(1 for w in BULL_TERMS if w in t)
    e = sum(1 for w in BEAR_TERMS if w in t)
    if b + e == 0:
        return 0.0
    return float(np.clip((b - e) / (b + e) * 80, -80, 80))

def historical_component(row: pd.Series) -> tuple[float, str]:
    avg = float(row["avg_return"])
    wr = float(row["win_rate"])
    vol = float(row["volatility"]) if not np.isnan(row["volatility"]) else 0.015
    score = avg * 4500.0 + (wr - 0.5) * 180.0
    if vol > 0.025:
        score *= 0.85
    score = float(np.clip(score, -100, 100))
    why = f"ISO-week baseline: avg {avg*100:+.2f}%, win rate {wr*100:.1f}%, vol {vol*100:.2f}% -> seasonal tilt {score:+.0f}."
    return score, why

def macro_component(calendar: list, now_year: int, now_week: int) -> tuple[float, list]:
    if not calendar:
        return 0.0, []
    today = datetime.now().date()
    w_end = today + __import__("datetime").timedelta(days=14)
    scored, total, wsum = [], 0.0, 0.0
    for ev in calendar:
        try:
            d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if d < today or d > w_end:
            continue
        w = 1.6 if ev.get("impact") == "HIGH" else 1.0
        total += float(ev.get("bias") or 0) * w
        wsum += w
        scored.append(ev)
    if wsum == 0:
        return 0.0, calendar[:6]
    return float(np.clip(total / wsum * 3.2, -100, 100)), scored

def x_component(posts: list, handles: list[str]) -> tuple[float, list]:
    allow = {h.lower() for h in handles}
    picked = [p for p in posts if str(p.get("handle", "")).lower() in allow] or list(posts)
    if not picked:
        return 0.0, []
    scores, weights, out = [], [], []
    for p in picked:
        s = _lexicon_score(p.get("text", ""))
        w = 1.0 + float(np.log1p(float(p.get("likes") or 0) / 40.0))
        q = dict(p)
        q["sent"] = s
        out.append(q)
        scores.append(s * w)
        weights.append(w)
    score = float(np.clip(float(np.sum(scores)) / max(float(np.sum(weights)), 1e-9), -100, 100))
    out.sort(key=lambda x: -float(x.get("likes") or 0))
    return score, out

def conviction_label(score: float) -> tuple[str, str]:
    if score >= 55:
        return "Extremely bullish", "pill-good"
    if score >= 20:
        return "Bullish", "pill-good"
    if score <= -55:
        return "Extremely bearish", "pill-bad"
    if score <= -20:
        return "Bearish", "pill-bad"
    return "Neutral / mixed", "pill-ok"

def alignment_flag(hist: float, live: float) -> tuple[str, str]:
    if abs(hist) < 8 or abs(live) < 8:
        return "Insufficient contrast", "pill-ok"
    if (hist > 0 and live > 0) or (hist < 0 and live < 0):
        return "Aligns with seasonal trend", "pill-good"
    return "Diverges from seasonal trend", "pill-bad"

def gauge_figure(score: float) -> go.Figure:
    s = float(score)
    color = "#34d399" if s >= 20 else "#fb7185" if s <= -20 else "#fbbf24"
    fig = go.Figure()
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=s,
            number={"valueformat": ".1f"},
            gauge={
                "axis": {"range": [-100, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [-100, -20], "color": "#4a2030"},
                    {"range": [-20, 20], "color": "#3d3418"},
                    {"range": [20, 100], "color": "#16382c"},
                ],
            },
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#d7deea", "size": 13},
        height=280,
        margin=dict(t=30, b=10, l=20, r=20),
    )
    return fig

def _row_for_week(stats: pd.DataFrame, week: int, fallback: pd.Series) -> pd.Series:
    hit = stats.loc[stats["week"] == int(week)] if stats is not None and not stats.empty else pd.DataFrame()
    if hit is None or hit.empty:
        return fallback
    return hit.iloc[0]

def render_live_outlook(
    row: pd.Series,
    ticker: str,
    now_week: int,
    now_year: int,
    handles: list[str],
    stats: pd.DataFrame | None = None,
    next_week: int | None = None,
    next_year: int | None = None,
    is_weekend: bool = False,
) -> None:
    nxt_w = int(next_week or now_week)
    nxt_y = int(next_year or now_year)
    if is_weekend:
        st.info(
            f"Sunday/Saturday: ISO week {now_week} is still on the calendar (Mon-Sun) but the US cash session "
            f"already closed Friday. The Outlook below defaults to **week {nxt_w}** — the week that opens Monday."
        )
    choice = st.radio(
        "Which week should the Outlook score?",
        (
            f"ISO {now_week} · still on the calendar",
            f"ISO {nxt_w} · week ahead (opens Monday)",
        ),
        index=1 if is_weekend else 0,
        horizontal=True,
    )
    use_ahead = "week ahead" in choice
    target_week = nxt_w if use_ahead else int(now_week)
    target_year = nxt_y if use_ahead else int(now_year)
    row = _row_for_week(stats if stats is not None else pd.DataFrame(), target_week, row)

    snap = _load_snapshot()
    hist_s, hist_why = historical_component(row)
    mac_s, cal = macro_component(snap.get("calendar") or [], target_year, target_week)
    x_s, posts = x_component(snap.get("posts") or [], handles)
    conv = float(np.clip(0.40 * hist_s + 0.35 * mac_s + 0.25 * x_s, -100, 100))
    flag, flag_cls = alignment_flag(hist_s, 0.35 * mac_s + 0.25 * x_s)
    label, lab_cls = conviction_label(conv)
    scope = "week ahead (Mon open)" if use_ahead else "calendar ISO week (ends Sun)"
    st.markdown(
        f"""
        <div class="week-banner">
          <div class="week-kicker">Live outlook · {ticker} · {scope}</div>
          <div class="week-title">ISO Week {target_week} · {target_year} · conviction {conv:+.0f}
            &nbsp;<span class="pill {lab_cls}">{label}</span>
            &nbsp;<span class="pill {flag_cls}">{flag}</span>
          </div>
          <div class="week-sub">
            40% historical seasonality of week {target_week} ({hist_s:+.0f}) · 35% macro calendar ({mac_s:+.0f})
            · 25% curated X ({x_s:+.0f}) · Snapshot {snap.get("as_of","")} · not a trading signal
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    g, m = st.columns((1.05, 1.35))
    with g:
        try:
            st.plotly_chart(gauge_figure(conv), use_container_width=True)
        except Exception:
            st.metric("Conviction", f"{conv:+.1f}")
        st.caption("Score maps -100 extremely bearish to +100 extremely bullish.")
    with m:
        st.markdown("#### Factor stack")
        stack = pd.DataFrame({
            "Sleeve": ["Historical seasonality", "Macro & catalysts", "X sentiment / positioning"],
            "Weight": ["40%", "35%", "25%"],
            "Score": [round(float(hist_s), 1), round(float(mac_s), 1), round(float(x_s), 1)],
            "Weighted": [round(0.40 * float(hist_s), 1), round(0.35 * float(mac_s), 1), round(0.25 * float(x_s), 1)],
        })
        st.dataframe(stack, hide_index=True, use_container_width=True)
        st.caption(hist_why)
        st.caption(
            f"Week {target_week} history: avg {float(row['avg_return'])*100:+.2f}% · "
            f"win {float(row['win_rate'])*100:.1f}% · n={int(row['observations'])}"
        )
    st.markdown("#### Catalyst breakdown")
    c_macro, c_flow, c_bias = st.columns(3)
    buckets = {"macro": [], "structure": [], "bias": []}
    for p in posts:
        buckets.get(p.get("cat") or "bias", buckets["bias"]).append(p)
    titles = [
        (c_macro, "Macro & economic data", "macro", cal),
        (c_flow, "Market structure & flow", "structure", None),
        (c_bias, "Directional bias (FinTwit)", "bias", None),
    ]
    for col, title, key, extra in titles:
        with col:
            st.markdown(f"**{title}**")
            if extra:
                for ev in extra[:5]:
                    st.markdown(f"- `{ev['date'][5:]}` · {ev['impact']} · {ev['name']}")
            for p in buckets[key][:4]:
                st.markdown(f"- **@{p['handle']}** ({p.get('ts','')}): {p['text'][:220]}")
            if not extra and not buckets[key]:
                st.caption("No items in this sleeve for the selected handles.")
    st.markdown("#### Scenario matrix")
    base = (
        "Event-driven range into the next cash session. Size for NFP/AVGO, not for a seasonal slam-dunk."
        if abs(conv) < 25
        else (
            "Seasonal edge and live sleeves point the same way."
            if (hist_s > 0) == (conv > 0)
            else "Live catalysts fight the seasonal baseline — size down into NFP/AVGO."
        )
    )
    scenarios = pd.DataFrame({
        "Scenario": ["Base case", "Bull case", "Bear case", "Invalidation"],
        "What has to happen": [
            "NFP not hot, yields digest Warsh, AVGO does not break the AI bid.",
            "Soft NFP + cooling wages; AVGO confirms capex; dealers stay long-gamma.",
            "Hot NFP/AHE or hawkish Fed-speak; put skew deepens; small caps lead lower.",
            "Break of the 13 Aug SPX region on a hike-odds spike, or VIX off year-lows.",
        ],
        "Weekly implication": [
            base,
            "Seasonal long bias can be expressed; dips more buyable than usual.",
            "Ignore a positive seasonal print; hedge or stay light into Friday.",
            "If broken, the 40% historical sleeve is subordinated until next ISO week.",
        ],
    })
    st.dataframe(scenarios, hide_index=True, use_container_width=True)
    with st.expander("Monitored X accounts and methodology"):
        st.markdown(
            f"""
            - **Handles this run:** {", ".join("@"+h for h in handles)}
            - **X feed:** bundled FinTwit snapshot (`x_snapshot.json`), lexicon-scored and engagement-weighted.
            - **Formula:** `0.40 * H + 0.35 * M + 0.25 * X`, each sleeve clipped to [-100, +100].
            - Weekend rule: ISO weeks are Mon-Sun. After Friday cash close, default Outlook = next Monday's week.
            - This is a **synthesis dashboard**, not advice.
            """
        )

with tab_live:
    render_live_outlook(
        row,
        ticker,
        now_week,
        now_year,
        _parse_handles(x_handles_raw),
        stats=stats,
        next_week=next_week,
        next_year=next_year,
        is_weekend=is_weekend,
    )
