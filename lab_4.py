from pathlib import Path
import json
import html as _html
import time as _time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

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
_X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
_X_QID = "V7H0Ap3_Hh2FyS75OCDO3Q"
_X_FEAT = json.dumps({
    "hidden_profile_likes_enabled": False,
    "hidden_profile_subscriptions_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": False,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
})
_X_MEMO = {}

def _parse_handles(raw):
    parts, seen, out = [], set(), []
    for chunk in str(raw or "").replace("\n", ",").split(","):
        h = chunk.strip().lstrip("@")
        if h:
            parts.append(h)
    for h in parts:
        k = h.lower()
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out or list(DEFAULT_X_HANDLES)

def _load_snapshot():
    here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    for p in (here / "x_snapshot.json", Path.cwd() / "x_snapshot.json"):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {"as_of": "", "calendar": [], "posts": []}

def _memo(key, ttl, fn):
    now = _time.time()
    hit = _X_MEMO.get(key)
    if ttl > 0 and hit and (now - hit[0]) < ttl:
        return hit[1]
    val = fn()
    _X_MEMO[key] = (now, val)
    return val

def _http_json(url, method="GET", headers=None, data=None, timeout=12):
    h = {"User-Agent": "Mozilla/5.0 SeasonalityLab/1.0"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def _x_guest():
    def _g():
        d = _http_json(
            "https://api.twitter.com/1.1/guest/activate.json",
            method="POST",
            headers={"Authorization": "Bearer " + _X_BEARER},
            data=b"",
        )
        return d["guest_token"]
    return _memo("guest", 1200, _g)

def _x_uid(handle):
    h = handle.lstrip("@")
    def _g():
        d = _http_json("https://api.fxtwitter.com/" + h, timeout=10)
        return str(d["user"]["id"])
    return _memo("uid:" + h.lower(), 86400, _g)

def _x_cat(text):
    t = (text or "").lower()
    if any(k in t for k in ("fomc", "cpi", "nfp", "payroll", "pce", "ism", "yield", "fed", "warsh", "hike", "jackson hole")):
        return "macro"
    if any(k in t for k in ("gamma", "dealer", "vix", "skew", "options", "put ", "call ")):
        return "structure"
    return "bias"

def _x_tweets(handle, uid, guest, n=6):
    variables = json.dumps({
        "userId": str(uid),
        "count": int(n),
        "includePromotedContent": False,
        "withQuickPromoteEligibilityTweetFields": False,
        "withVoice": False,
        "withV2Timeline": True,
    })
    url = "https://twitter.com/i/api/graphql/" + _X_QID + "/UserTweets?" + urllib.parse.urlencode(
        {"variables": variables, "features": _X_FEAT}
    )
    data = _http_json(
        url,
        headers={
            "Authorization": "Bearer " + _X_BEARER,
            "x-guest-token": guest,
            "Cookie": "gt=" + guest,
            "Referer": "https://x.com/" + handle,
            "x-twitter-active-user": "yes",
        },
        timeout=14,
    )
    found = []
    def walk(o):
        if isinstance(o, dict):
            leg = o.get("legacy")
            if isinstance(leg, dict) and "full_text" in leg:
                found.append(leg)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    out, seen = [], set()
    cutoff = datetime.utcnow() - __import__("datetime").timedelta(days=10)
    for leg in found:
        text = _html.unescape(str(leg.get("full_text") or "")).replace("\n", " ").strip()
        if (not text) or text.startswith("RT @") or text in seen:
            continue
        seen.add(text)
        ts_raw = str(leg.get("created_at") or "")
        try:
            ts = datetime.strptime(ts_raw, "%a %b %d %H:%M:%S %z %Y")
            if ts.replace(tzinfo=None) < cutoff:
                continue
            day = ts.strftime("%Y-%m-%d")
        except Exception:
            day = ts_raw[:10]
        out.append({
            "handle": handle,
            "ts": day,
            "likes": int(leg.get("favorite_count") or 0),
            "cat": _x_cat(text),
            "text": text[:400],
        })
        if len(out) >= 5:
            break
    return out

def _fetch_live_x(handles):
    handles = [h.lstrip("@") for h in handles[:10]]
    guest = _x_guest()
    posts, errors, ok = [], [], 0
    def one(h):
        return h, _x_tweets(h, _x_uid(h), guest)
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(one, h) for h in handles]
        for fut in as_completed(futs):
            try:
                h, tw = fut.result()
                posts.extend(tw)
                if tw:
                    ok += 1
            except Exception as e:
                errors.append(str(e)[:90])
    meta = {
        "source": "live X",
        "as_of": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "accounts_ok": ok,
        "accounts_tried": len(handles),
        "n_posts": len(posts),
        "error": (errors[0] if errors else ""),
    }
    return posts, meta

def live_posts_for_visit(handles, snapshot):
    key = tuple(h.lower() for h in handles[:10])
    force = bool(st.session_state.pop("_x_force_refresh", False))
    if (not force) and st.session_state.get("_x_visit_key") == key and "_x_visit_posts" in st.session_state:
        return st.session_state["_x_visit_posts"], st.session_state["_x_visit_meta"]
    def _do():
        return _fetch_live_x(list(key))
    memo_key = "tweets:" + ",".join(key)
    try:
        with st.spinner("Fetching live X posts for this visit..."):
            posts, meta = _do() if force else _memo(memo_key, 90, _do)
    except Exception as e:
        posts, meta = [], {"source": "error", "as_of": "", "error": str(e)[:120], "accounts_ok": 0, "accounts_tried": len(key), "n_posts": 0}
    if not posts:
        posts = list(snapshot.get("posts") or [])
        meta = dict(meta or {})
        meta["source"] = "snapshot fallback"
        meta["n_posts"] = len(posts)
    st.session_state["_x_visit_key"] = key
    st.session_state["_x_visit_posts"] = posts
    st.session_state["_x_visit_meta"] = meta
    return posts, meta

def _lexicon_score(text):
    t = (text or "").lower()
    b = sum(1 for w in BULL_TERMS if w in t)
    e = sum(1 for w in BEAR_TERMS if w in t)
    if b + e == 0:
        return 0.0
    return float(np.clip((b - e) / (b + e) * 80, -80, 80))

def _num(x, default=0.0):
    try:
        v = float(x)
        if v != v:
            return default
        return v
    except Exception:
        return default

def historical_component(row):
    avg = _num(row.get("avg_return") if hasattr(row, "get") else row["avg_return"])
    wr = _num(row["win_rate"], 0.5)
    vol = _num(row["volatility"], 0.015)
    score = avg * 4500.0 + (wr - 0.5) * 180.0
    if vol > 0.025:
        score *= 0.85
    score = float(np.clip(score, -100, 100))
    why = "ISO-week baseline: avg {:+.2f}%, win rate {:.1f}%, vol {:.2f}% -> seasonal tilt {:+.0f}.".format(
        avg * 100, wr * 100, vol * 100, score
    )
    return score, why

def macro_component(calendar, now_year, now_week):
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
        total += _num(ev.get("bias")) * w
        wsum += w
        scored.append(ev)
    if wsum == 0:
        return 0.0, list(calendar)[:6]
    return float(np.clip(total / wsum * 3.2, -100, 100)), scored

def x_component(posts, handles):
    allow = {str(h).lower() for h in (handles or [])}
    picked = [p for p in (posts or []) if str(p.get("handle", "")).lower() in allow] or list(posts or [])
    if not picked:
        return 0.0, []
    scores, weights, out = [], [], []
    for p in picked:
        s = _lexicon_score(p.get("text", ""))
        w = 1.0 + float(np.log1p(_num(p.get("likes")) / 40.0))
        q = dict(p)
        q["sent"] = s
        out.append(q)
        scores.append(s * w)
        weights.append(w)
    score = float(np.clip(float(np.sum(scores)) / max(float(np.sum(weights)), 1e-9), -100, 100))
    out.sort(key=lambda x: -_num(x.get("likes")))
    return score, out

def conviction_label(score):
    if score >= 55:
        return "Extremely bullish", "pill-good"
    if score >= 20:
        return "Bullish", "pill-good"
    if score <= -55:
        return "Extremely bearish", "pill-bad"
    if score <= -20:
        return "Bearish", "pill-bad"
    return "Neutral / mixed", "pill-ok"

def alignment_flag(hist, live):
    if abs(hist) < 8 or abs(live) < 8:
        return "Insufficient contrast", "pill-ok"
    if (hist > 0 and live > 0) or (hist < 0 and live < 0):
        return "Aligns with seasonal trend", "pill-good"
    return "Diverges from seasonal trend", "pill-bad"

def gauge_figure(score):
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

def _row_for_week(stats, week, fallback):
    try:
        if stats is None or len(stats) == 0:
            return fallback
        hit = stats.loc[stats["week"].astype(int) == int(week)]
        if hit is None or len(hit) == 0:
            return fallback
        return hit.iloc[0]
    except Exception:
        return fallback

def _week_ahead():
    ts = pd.Timestamp.now()
    wd = int(ts.weekday())
    days = (7 - wd) % 7 or 7
    nxt = (ts + pd.Timedelta(days=days)).isocalendar()
    return int(nxt.year), int(nxt.week), wd >= 5

def render_live_outlook(row, ticker, now_week, now_year, handles, stats=None, next_week=None, next_year=None, is_weekend=None):
    auto_y, auto_w, auto_we = _week_ahead()
    nxt_w = int(next_week) if next_week is not None else auto_w
    nxt_y = int(next_year) if next_year is not None else auto_y
    if is_weekend is None:
        is_weekend = auto_we
    if is_weekend:
        st.info(
            "Sunday/Saturday: ISO week {} is still on the calendar (Mon-Sun), but US cash already closed Friday. "
            "Outlook defaults to week {} (opens Monday).".format(now_week, nxt_w)
        )
    top_l, top_r = st.columns([4, 1])
    with top_r:
        if st.button("Refresh X now", use_container_width=True):
            st.session_state["_x_force_refresh"] = True
            st.rerun()
    labels = [
        "ISO {} - still on the calendar".format(int(now_week)),
        "ISO {} - week ahead (opens Monday)".format(nxt_w),
    ]
    choice = st.radio(
        "Which week should the Outlook score?",
        labels,
        index=1 if is_weekend else 0,
        horizontal=True,
        key="outlook_week_choice",
    )
    use_ahead = "week ahead" in str(choice)
    target_week = nxt_w if use_ahead else int(now_week)
    target_year = nxt_y if use_ahead else int(now_year)
    row = _row_for_week(stats, target_week, row)

    snap = _load_snapshot()
    x_posts, x_meta = live_posts_for_visit(handles, snap)
    hist_s, hist_why = historical_component(row)
    mac_s, cal = macro_component(snap.get("calendar") or [], target_year, target_week)
    x_s, posts = x_component(x_posts, handles)
    conv = float(np.clip(0.40 * hist_s + 0.35 * mac_s + 0.25 * x_s, -100, 100))
    flag, flag_cls = alignment_flag(hist_s, 0.35 * mac_s + 0.25 * x_s)
    label, lab_cls = conviction_label(conv)
    scope = "week ahead (Mon open)" if use_ahead else "calendar ISO week (ends Sun)"
    src = str(x_meta.get("source") or "X")
    asof = str(x_meta.get("as_of") or "")
    n_ok = x_meta.get("accounts_ok", "?")
    n_try = x_meta.get("accounts_tried", "?")
    n_posts = x_meta.get("n_posts", len(posts))
    st.markdown(
        """
        <div class="week-banner">
          <div class="week-kicker">Live outlook &middot; {ticker} &middot; {scope}</div>
          <div class="week-title">ISO Week {tw} &middot; {ty} &middot; conviction {conv:+.0f}
            &nbsp;<span class="pill {lab_cls}">{label}</span>
            &nbsp;<span class="pill {flag_cls}">{flag}</span>
          </div>
          <div class="week-sub">
            40% historical ({hist_s:+.0f}) &middot; 35% macro ({mac_s:+.0f}) &middot; 25% X ({x_s:+.0f})
            &middot; {src} {asof} &middot; {n_posts} posts from {n_ok}/{n_try} accounts &middot; not a trading signal
          </div>
        </div>
        """.format(
            ticker=ticker, scope=scope, tw=target_week, ty=target_year, conv=conv,
            lab_cls=lab_cls, label=label, flag_cls=flag_cls, flag=flag,
            hist_s=hist_s, mac_s=mac_s, x_s=x_s, src=src, asof=asof,
            n_posts=n_posts, n_ok=n_ok, n_try=n_try,
        ),
        unsafe_allow_html=True,
    )
    if src == "snapshot fallback":
        st.warning("Live X did not return posts this visit (blocked or timed out). Using the last saved snapshot so the score still computes.")
    g, m = st.columns((1.05, 1.35))
    with g:
        try:
            st.plotly_chart(gauge_figure(conv), use_container_width=True)
        except Exception:
            st.metric("Conviction", "{:+.1f}".format(conv))
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
            "Week {} history: avg {:+.2f}%  win {:.1f}%  n={}".format(
                target_week,
                _num(row["avg_return"]) * 100,
                _num(row["win_rate"]) * 100,
                int(_num(row["observations"])),
            )
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
            st.markdown("**{}**".format(title))
            if extra:
                for ev in extra[:5]:
                    st.markdown("- `{}`  {}  {}".format(str(ev.get("date", ""))[5:], ev.get("impact", ""), ev.get("name", "")))
            for p in buckets[key][:4]:
                st.markdown("- **@{}** ({}): {}".format(p.get("handle", ""), p.get("ts", ""), str(p.get("text", ""))[:220]))
            if not extra and not buckets[key]:
                st.caption("No items in this sleeve for the selected handles.")
    st.markdown("#### Scenario matrix")
    if abs(conv) < 25:
        base = "Event-driven range into the next cash session. Size for NFP/AVGO, not for a seasonal slam-dunk."
    elif (hist_s > 0) == (conv > 0):
        base = "Seasonal edge and live sleeves point the same way."
    else:
        base = "Live catalysts fight the seasonal baseline - size down into NFP/AVGO."
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
            "- **Handles this run (first 10 are fetched live):** {}\n"
            "- **X feed:** live posts on each new visit; Streamlit clicks reuse this visit. Server memo 90s. Fallback snapshot if X blocks.\n"
            "- **Formula:** `0.40 * H + 0.35 * M + 0.25 * X`.\n"
            "- Weekend rule: after Friday cash close, default Outlook = next Monday week.\n"
            "- This is a **synthesis dashboard**, not advice.".format(
                ", ".join("@" + h for h in handles)
            )
        )

try:
    with tab_live:
        render_live_outlook(
            row,
            ticker,
            now_week,
            now_year,
            _parse_handles(x_handles_raw),
            stats=stats,
            next_week=globals().get("next_week"),
            next_year=globals().get("next_year"),
            is_weekend=globals().get("is_weekend"),
        )
except Exception as _live_err:
    st.error("Live Outlook hit an error; historical seasonality above is unchanged.")
    st.exception(_live_err)
