"""
XRPRadar v1.0 — XRPRadar.com
Everything XRP. All the time.
Built on Railway | Flask + Python
Same patterns as Scorpion Universal
"""

import os, json, time, threading, hashlib, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import feedparser
import requests
from flask import Flask, jsonify, Response

app = Flask(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
BOT_FILE          = "XRPRadar_v1.0a"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SCAN_INTERVAL     = 600   # 10 minutes — news refresh
PRICE_INTERVAL    = 60    # 60 seconds — price refresh
AI_INTERVAL       = 600   # 10 minutes — AI briefing
MAX_STORIES       = 300   # max stories in memory
QA_INTERVAL       = 14400 # 4 hours — preflight QA check

# ── XRP Keyword Filter ────────────────────────────────────────────────────────
XRP_KEYWORDS = [
    "xrp","ripple","xrpl","garlinghouse","david schwartz","joelkatz",
    "ripplenet","rlusd","on-demand liquidity","odl","sbi ripple","xrp ledger"
]

# ── Breaking News Keywords ────────────────────────────────────────────────────
BREAKING_KEYWORDS = [
    "sec","etf","lawsuit","hack","ban","arrested","sanction","escrow",
    "rlusd","occ","crash","surge","ruling","verdict","settlement","injunction",
    "delisted","partnership","approved","rejected","seized"
]

# ── Sentiment Keywords ─────────────────────────────────────────────────────────
BULL_WORDS = [
    "surge","rally","rise","pump","bull","gain","high","ath","partnership",
    "approval","bullish","positive","launch","adoption","buy","soar","spike",
    "jump","up","approved","milestone","record","win","victory","integration"
]
BEAR_WORDS = [
    "drop","crash","fall","dump","bear","loss","low","lawsuit","ban","sell",
    "bearish","negative","hack","reject","fud","plunge","decline","down",
    "arrest","seized","delisted","suspended","warning","risk","fear","concern"
]

# ── Category Keywords ──────────────────────────────────────────────────────────
CAT_KEYWORDS = {
    "Legal":      ["sec","lawsuit","court","ruling","regulatory","cftc","legal","judge","verdict","settlement","appeal"],
    "Regulatory": ["regulation","law","bill","act","policy","government","congress","senate","mica","fsb","mica"],
    "Whale":      ["whale","large transaction","transfer","escrow","million xrp","billion xrp","moved"],
    "Ecosystem":  ["partnership","bank","adoption","launch","integration","ripplenet","odl","liquidity","sbi"],
    "Technical":  ["xrpl","protocol","ledger","developer","update","release","code","github","amend","validator"],
    "Price":      ["price","market","trading","ath","rally","drop","value","usd","chart","analysis","prediction"],
}

# ── RSS Feed List (v1 — 25 highest-signal feeds) ─────────────────────────────
RSS_FEEDS = [
    # XRP-dedicated
    {"name": "U.Today XRP",       "url": "https://u.today/rss/ripple.rss",                                             "type": "xrp",           "filter": False},
    {"name": "Crypto News Flash",  "url": "https://crypto-news-flash.com/tag/ripple/feed",                              "type": "xrp",           "filter": False},
    # Official
    {"name": "Ripple Insights",    "url": "https://ripple.com/insights/feed",                                           "type": "official",      "filter": False},
    {"name": "XRPL.org Blog",      "url": "https://xrpl.org/blog/feed.xml",                                             "type": "official",      "filter": False},
    # Major Crypto
    {"name": "CoinTelegraph XRP",  "url": "https://cointelegraph.com/rss/tag/ripple",                                   "type": "major",         "filter": False},
    {"name": "CoinDesk",           "url": "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",             "type": "major",         "filter": True},
    {"name": "Decrypt",            "url": "https://decrypt.co/feed",                                                    "type": "major",         "filter": True},
    {"name": "The Block",          "url": "https://www.theblock.co/rss.xml",                                            "type": "major",         "filter": True},
    {"name": "Blockworks",         "url": "https://blockworks.co/feed",                                                 "type": "major",         "filter": True},
    {"name": "Daily Hodl",         "url": "https://dailyhodl.com/feed",                                                 "type": "major",         "filter": True},
    {"name": "AMBCrypto",          "url": "https://ambcrypto.com/feed",                                                 "type": "major",         "filter": True},
    {"name": "BeInCrypto",         "url": "https://beincrypto.com/feed",                                                "type": "major",         "filter": True},
    {"name": "NewsBTC",            "url": "https://www.newsbtc.com/feed",                                               "type": "major",         "filter": True},
    {"name": "Finbold",            "url": "https://finbold.com/feed",                                                   "type": "major",         "filter": True},
    {"name": "CryptoSlate",        "url": "https://cryptoslate.com/feed",                                               "type": "major",         "filter": True},
    # Google News Filters
    {"name": "Google News: XRP",   "url": "https://news.google.com/rss/search?q=XRP+Ripple&hl=en-US&gl=US&ceid=US:en", "type": "aggregator",    "filter": False},
    {"name": "Google News: Legal", "url": "https://news.google.com/rss/search?q=XRP+SEC+Ripple+lawsuit",                "type": "legal",         "filter": False},
    {"name": "Google News: ETF",   "url": "https://news.google.com/rss/search?q=XRP+ETF+institutional+2026",            "type": "institutional", "filter": False},
    {"name": "Google News: RLUSD", "url": "https://news.google.com/rss/search?q=RLUSD+stablecoin+Ripple",               "type": "xrp",           "filter": False},
    # Community
    {"name": "Reddit r/Ripple",    "url": "https://www.reddit.com/r/Ripple/.rss",                                       "type": "community",     "filter": False},
    {"name": "Reddit r/XRP",       "url": "https://www.reddit.com/r/XRP/.rss",                                          "type": "community",     "filter": False},
    # International
    {"name": "CoinPost Japan",     "url": "https://coinpost.jp/?tag=ripple&feed=rss2",                                  "type": "international", "filter": False},
    {"name": "Forkast Asia",       "url": "https://forkast.news/feed",                                                  "type": "international", "filter": True},
    # Mainstream
    {"name": "Yahoo Finance Crypto","url": "https://finance.yahoo.com/rss/topic/crypto",                                "type": "mainstream",    "filter": True},
    {"name": "Forbes Crypto",      "url": "https://www.forbes.com/crypto-blockchain/feed2",                             "type": "mainstream",    "filter": True},
]

# ── State ──────────────────────────────────────────────────────────────────────
STATE = {
    "price":         {},
    "secondary":     {},
    "fear_greed":    {},
    "escrow":        {},
    "stories":       [],
    "ai_us":         {"pulse": "Fetching US intelligence...", "regulatory": "Loading...", "institutional": "Loading...", "ts": ""},
    "ai_global":     {"pulse": "Fetching global intelligence...", "signals": {}, "thesis": "Analyzing...", "ts": ""},
    "feed_health":   {},
    "breaking":      None,
    "story_stats":   {"today": 0, "bullish": 0, "bearish": 0, "neutral": 0},
    "version":       BOT_FILE,
    "last_updated":  None,
    "qa_status":     "PENDING",
    "qa_last":       None,
    "qa_details":    [],
    "last_error":    None,
    "last_error_ts": None,
    "feeds_active":  0,
    "maintenance":   "OK",
    "start_time":    datetime.now(timezone.utc).isoformat(),
    "upgrade_log":   [
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v1.0a — XRPRadar initial build. 25 RSS feeds, price data, AI briefing panels, System Health Bar."}
    ]
}

DATA_PATH = Path("/tmp/xrpradar_state.json")

# ── Persist ────────────────────────────────────────────────────────────────────
def save_state():
    try:
        tmp = DATA_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(STATE, default=str))
        tmp.replace(DATA_PATH)
    except Exception as e:
        log_error(f"save_state: {e}")

def load_state():
    try:
        if DATA_PATH.exists():
            d = json.loads(DATA_PATH.read_text())
            for k in ["stories","feed_health","story_stats","upgrade_log"]:
                if k in d: STATE[k] = d[k]
    except Exception as e:
        log_error(f"load_state: {e}")

def log_error(msg):
    STATE["last_error"]    = str(msg)[:200]
    STATE["last_error_ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# ── Helpers ────────────────────────────────────────────────────────────────────
def is_xrp(title, summary=""):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in XRP_KEYWORDS)

def detect_sentiment(title, summary=""):
    text = (title + " " + summary).lower()
    b = sum(1 for w in BULL_WORDS if w in text)
    r = sum(1 for w in BEAR_WORDS if w in text)
    if b > r:   return "bullish"
    if r > b:   return "bearish"
    return "neutral"

def detect_category(title, summary=""):
    text = (title + " " + summary).lower()
    for cat, words in CAT_KEYWORDS.items():
        if any(w in text for w in words):
            return cat
    return "General"

def detect_breaking(title):
    text = title.lower()
    return any(kw in text for kw in BREAKING_KEYWORDS)

def story_id(title, link):
    return hashlib.md5((title + link).encode()).hexdigest()[:12]

def fmt_ts(ts):
    if not ts: return "Unknown"
    try:
        now  = datetime.now(timezone.utc)
        diff = now - ts
        s    = int(diff.total_seconds())
        if s < 60:   return f"{s}s ago"
        if s < 3600: return f"{s//60}m ago"
        if s < 86400:return f"{s//3600}h ago"
        return f"{s//86400}d ago"
    except: return ""

# ── Price Fetch ────────────────────────────────────────────────────────────────
def fetch_price():
    try:
        hdr = {"User-Agent": "XRPRadar/1.0"}
        # Primary: CoinGecko
        cg = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple"
            "?localization=false&tickers=false&community_data=false&developer_data=false",
            headers=hdr, timeout=10).json()
        md = cg.get("market_data", {})
        STATE["price"] = {
            "usd":        md.get("current_price", {}).get("usd", 0),
            "btc":        md.get("current_price", {}).get("btc", 0),
            "change_24h": md.get("price_change_percentage_24h", 0),
            "change_7d":  md.get("price_change_percentage_7d",  0),
            "change_30d": md.get("price_change_percentage_30d", 0),
            "mcap":       md.get("market_cap",      {}).get("usd", 0),
            "volume_24h": md.get("total_volume",    {}).get("usd", 0),
            "ath":        md.get("ath",              {}).get("usd", 0),
            "ath_pct":    md.get("ath_change_percentage", {}).get("usd", 0),
            "supply_circ":md.get("circulating_supply", 0),
            "supply_total":cg.get("market_data", {}).get("total_supply", 100000000000),
            "rank":       cg.get("market_cap_rank", 0),
        }
    except Exception as e:
        log_error(f"fetch_price CoinGecko: {e}")
        # Fallback: Binance
        try:
            b = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=XRPUSDT",
                             timeout=5).json()
            STATE["price"]["usd"]        = float(b.get("lastPrice", 0))
            STATE["price"]["change_24h"] = float(b.get("priceChangePercent", 0))
            STATE["price"]["volume_24h"] = float(b.get("quoteVolume", 0))
        except Exception as e2:
            log_error(f"fetch_price Binance fallback: {e2}")

    # Fear & Greed
    try:
        fg = requests.get("https://api.alternative.me/fng/", timeout=8).json()
        d  = fg.get("data", [{}])[0]
        STATE["fear_greed"] = {
            "score": int(d.get("value", 50)),
            "label": d.get("value_classification", "Neutral")
        }
    except Exception as e:
        log_error(f"fetch_fear_greed: {e}")

    # Escrow (XRPScan)
    try:
        xs = requests.get("https://api.xrpscan.com/api/v1/account/rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
                          timeout=8).json()
        STATE["escrow"] = {
            "next_date":   "1st of next month",
            "amount_b":    1.0,
            "note":        "Ripple releases 1B XRP monthly from escrow"
        }
    except:
        STATE["escrow"] = {"next_date": "~1st monthly", "amount_b": 1.0, "note": "1B XRP monthly release"}

    # Vol/Mcap ratio
    try:
        p = STATE["price"]
        if p.get("mcap") and p.get("volume_24h"):
            STATE["price"]["vol_mcap_ratio"] = round(p["volume_24h"] / p["mcap"] * 100, 2)
    except: pass

    STATE["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# ── News Fetch ─────────────────────────────────────────────────────────────────
def fetch_news():
    seen_ids   = {s["id"] for s in STATE["stories"]}
    new_stories= []
    active     = 0
    health     = {}

    for feed_cfg in RSS_FEEDS:
        name = feed_cfg["name"]
        url  = feed_cfg["url"]
        ftype= feed_cfg["type"]
        do_filter = feed_cfg["filter"]
        try:
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                health[name] = "DOWN"
                continue
            health[name] = "UP"
            active += 1
            for entry in parsed.entries[:15]:
                title   = getattr(entry, "title",   "")
                link    = getattr(entry, "link",    "")
                summary = getattr(entry, "summary", "")
                summary = re.sub(r"<[^>]+>", "", summary)[:300]

                if not title or not link: continue
                if do_filter and not is_xrp(title, summary): continue

                sid = story_id(title, link)
                if sid in seen_ids: continue

                # Parse published time
                pub = None
                try:
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except: pass

                # Only stories from last 7 days
                if pub:
                    age = (datetime.now(timezone.utc) - pub).total_seconds()
                    if age > 604800: continue

                sentiment= detect_sentiment(title, summary)
                category = detect_category(title, summary)
                breaking = detect_breaking(title)

                story = {
                    "id":        sid,
                    "title":     title,
                    "link":      link,
                    "summary":   summary,
                    "source":    name,
                    "type":      ftype,
                    "sentiment": sentiment,
                    "category":  category,
                    "breaking":  breaking,
                    "pub":       pub.isoformat() if pub else None,
                    "age":       fmt_ts(pub) if pub else "Recent",
                }
                new_stories.append(story)
                seen_ids.add(sid)
        except Exception as e:
            health[name] = "DOWN"
            log_error(f"feed {name}: {e}")

    # Merge + sort
    all_stories = new_stories + STATE["stories"]
    all_stories.sort(key=lambda s: s.get("pub") or "", reverse=True)
    STATE["stories"]      = all_stories[:MAX_STORIES]
    STATE["feed_health"]  = health
    STATE["feeds_active"] = active

    # Stats
    today_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    today_s = [s for s in STATE["stories"] if (s.get("pub") or "") >= today_cutoff]
    STATE["story_stats"] = {
        "today":   len(today_s),
        "bullish": sum(1 for s in today_s if s["sentiment"] == "bullish"),
        "bearish": sum(1 for s in today_s if s["sentiment"] == "bearish"),
        "neutral": sum(1 for s in today_s if s["sentiment"] == "neutral"),
    }

    # Breaking news: most recent breaking story < 2h old
    for s in STATE["stories"]:
        if s.get("breaking") and s.get("pub"):
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(s["pub"])).total_seconds() / 3600
            if age_h < 2:
                STATE["breaking"] = s
                break
    else:
        STATE["breaking"] = None

# ── Claude AI Briefing ─────────────────────────────────────────────────────────
def call_claude(prompt, system_prompt, max_tokens=400):
    if not ANTHROPIC_API_KEY:
        return "Add ANTHROPIC_API_KEY to Railway Variables to enable AI briefings."
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model":      "claude-sonnet-4-6",
                "max_tokens": max_tokens,
                "system":     system_prompt,
                "messages":   [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        data = r.json()
        return data.get("content", [{}])[0].get("text", "No response")
    except Exception as e:
        log_error(f"Claude API: {e}")
        return f"AI briefing temporarily unavailable."

def fetch_ai_briefing():
    stories = STATE["stories"][:60]
    if not stories:
        return

    # Bundle story titles for prompt
    titles_all = "\n".join([f"- [{s['source']}] {s['title']} ({s['sentiment'].upper()})"
                            for s in stories])

    us_types = {"major","official","institutional","legal","mainstream","aggregator"}
    us_stories = [s for s in stories if s["type"] in us_types]
    titles_us  = "\n".join([f"- [{s['source']}] {s['title']} ({s['sentiment'].upper()})"
                            for s in us_stories[:30]])

    # ── US Briefing ──
    sys_us = ("You are an XRP market intelligence analyst specializing in US markets. "
              "Be concise, factual, and forward-looking. No disclaimers. No emojis.")

    prompt_us = (f"Based on these recent US XRP/Ripple news stories:\n{titles_us}\n\n"
                 "Respond in JSON only (no markdown, no backticks):\n"
                 '{"pulse":"2 sentence US market intelligence summary","'
                 'regulatory":"1 sentence on US regulatory landscape (SEC/CFTC/legislation)","'
                 'institutional":"1 sentence on US institutional XRP activity (ETFs/banks)"}')

    try:
        raw = call_claude(prompt_us, sys_us, 300)
        raw = raw.strip().lstrip("```json").rstrip("```").strip()
        d   = json.loads(raw)
        STATE["ai_us"] = {
            "pulse":         d.get("pulse", ""),
            "regulatory":    d.get("regulatory", ""),
            "institutional": d.get("institutional", ""),
            "ts":            datetime.now(timezone.utc).strftime("%H:%M UTC")
        }
    except Exception as e:
        log_error(f"AI US parse: {e}")

    # ── Global Briefing ──
    sys_gl = ("You are a global XRP intelligence analyst. Synthesize news from all regions. "
              "Be concise, analytical, forward-looking. No disclaimers. No emojis.")

    regions = ["Japan","Korea","UAE","Europe","LatAm","Africa","India"]
    region_signals = {}
    for reg in regions:
        reg_stories = [s for s in stories if s["type"] == "international"
                       or reg.lower() in s["title"].lower()]
        if reg_stories:
            bulls = sum(1 for s in reg_stories if s["sentiment"] == "bullish")
            bears = sum(1 for s in reg_stories if s["sentiment"] == "bearish")
            if bulls > bears:      region_signals[reg] = "bullish"
            elif bears > bulls:    region_signals[reg] = "bearish"
            else:                  region_signals[reg] = "neutral"
        else:
            region_signals[reg] = "quiet"

    prompt_gl = (f"Based on these recent global XRP/Ripple news stories:\n{titles_all}\n\n"
                 "Respond in JSON only (no markdown, no backticks):\n"
                 '{"pulse":"2 sentence global XRP market synthesis","'
                 'thesis":"1 paragraph forward-looking read on what all global signals mean for XRP right now"}')

    try:
        raw = call_claude(prompt_gl, sys_gl, 400)
        raw = raw.strip().lstrip("```json").rstrip("```").strip()
        d   = json.loads(raw)
        STATE["ai_global"] = {
            "pulse":   d.get("pulse",  ""),
            "signals": region_signals,
            "thesis":  d.get("thesis", ""),
            "ts":      datetime.now(timezone.utc).strftime("%H:%M UTC")
        }
    except Exception as e:
        log_error(f"AI Global parse: {e}")

# ── Preflight QA ───────────────────────────────────────────────────────────────
def run_qa():
    checks = []
    def chk(name, ok, detail=""):
        checks.append({"name": name, "ok": ok, "detail": detail})

    chk("Price data present",    bool(STATE["price"].get("usd")),
        f"${STATE['price'].get('usd', 'MISSING')}")
    chk("Fear & Greed present",  bool(STATE["fear_greed"].get("score")),
        f"{STATE['fear_greed'].get('score','MISSING')}/100")
    chk("Stories collected",     len(STATE["stories"]) > 0,
        f"{len(STATE['stories'])} stories")
    chk("Active feeds > 15",     STATE["feeds_active"] >= 15,
        f"{STATE['feeds_active']}/{len(RSS_FEEDS)} feeds UP")
    chk("AI briefings present",  bool(STATE["ai_global"].get("pulse","").strip()),
        "Global pulse OK" if STATE["ai_global"].get("pulse") else "Empty")
    chk("Anthropic key set",     bool(ANTHROPIC_API_KEY),
        "Set" if ANTHROPIC_API_KEY else "MISSING — add to Railway Variables")

    all_ok = all(c["ok"] for c in checks)
    STATE["qa_status"]  = "PASS" if all_ok else "FAIL"
    STATE["qa_last"]    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    STATE["qa_details"] = checks

# ── Main Loops ─────────────────────────────────────────────────────────────────
def price_loop():
    while True:
        try: fetch_price()
        except Exception as e: log_error(f"price_loop: {e}")
        time.sleep(PRICE_INTERVAL)

def news_loop():
    time.sleep(5)
    last_ai = 0
    last_qa = 0
    while True:
        try:
            fetch_news()
            now = time.time()
            if now - last_ai >= AI_INTERVAL:
                fetch_ai_briefing()
                last_ai = now
            if now - last_qa >= QA_INTERVAL:
                run_qa()
                last_qa = now
            save_state()
        except Exception as e:
            log_error(f"news_loop: {e}")
        time.sleep(SCAN_INTERVAL)

# ── Format Helpers ─────────────────────────────────────────────────────────────
def fmt_usd(v):
    if not v: return "$0.00"
    v = float(v)
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    if v >= 1e3:  return f"${v/1e3:.2f}K"
    return f"${v:.4f}"

def fmt_price(v):
    if not v: return "$0.0000"
    return f"${float(v):.4f}"

def fmt_pct(v):
    if v is None: return "0.00%"
    return f"{float(v):+.2f}%"

def pct_color(v):
    return "#00FF87" if float(v or 0) >= 0 else "#FF4444"

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/ping")
def ping():
    return "XRPRadar OK", 200

@app.route("/api/data")
def api_data():
    p  = STATE["price"]
    fg = STATE["fear_greed"]
    ex = STATE["escrow"]
    st = STATE["story_stats"]
    return jsonify({
        "price":       p,
        "fear_greed":  fg,
        "escrow":      ex,
        "ai_us":       STATE["ai_us"],
        "ai_global":   STATE["ai_global"],
        "story_stats": st,
        "breaking":    STATE["breaking"],
        "feeds_active":STATE["feeds_active"],
        "feeds_total": len(RSS_FEEDS),
        "feed_health": STATE["feed_health"],
        "last_updated":STATE["last_updated"],
        "version":     STATE["version"],
        "qa_status":   STATE["qa_status"],
        "qa_last":     STATE["qa_last"],
        "qa_details":  STATE["qa_details"],
        "last_error":  STATE["last_error"],
        "last_error_ts":STATE["last_error_ts"],
        "maintenance": STATE["maintenance"],
        "start_time":  STATE["start_time"],
        "upgrade_log": STATE["upgrade_log"],
    })

@app.route("/api/news")
def api_news():
    cat = requests.args.get("cat","all") if False else "all"
    from flask import request
    cat  = request.args.get("cat",  "all")
    sent = request.args.get("sent", "all")
    q    = request.args.get("q",    "").lower()
    stories = STATE["stories"]
    if cat  != "all": stories = [s for s in stories if s["category"] == cat]
    if sent != "all": stories = [s for s in stories if s["sentiment"] == sent]
    if q:             stories = [s for s in stories if q in s["title"].lower()]
    return jsonify({"stories": stories[:100], "total": len(stories)})

@app.route("/")
def index():
    return Response(DASHBOARD, mimetype="text/html")

# ── Dashboard HTML ─────────────────────────────────────────────────────────────
DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XRPRadar — Everything XRP. All the time.</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  :root{
    --dark:#050F0A;--mid:#0A1A10;--panel:#0D2118;--card:#0F2A1A;
    --grn:#00FF87;--sgrn:#7DFFB3;--org:#FF6B35;--gold:#C9A84C;
    --wht:#FFFFFF;--gray:#A0AEC0;--red:#FF4444;--ylw:#FFD700;
    --legal:#1A0A00;--whale:#0A1500;--ai:#0D1F2E;
  }
  body{background:var(--dark);color:var(--wht);font-family:Arial,sans-serif;font-size:14px}
  a{color:var(--grn);text-decoration:none}
  a:hover{text-decoration:underline}

  /* NAV */
  #nav{position:sticky;top:0;z-index:100;background:var(--dark);border-bottom:1px solid var(--grn);
    display:flex;align-items:center;justify-content:space-between;padding:0 20px;height:52px}
  .nav-logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:bold;color:var(--grn)}
  .nav-logo .sat{font-size:26px;animation:spin 8s linear infinite}
  @keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
  .nav-tagline{font-size:11px;color:var(--sgrn);font-style:italic}
  .nav-links{display:flex;gap:20px}
  .nav-links a{color:var(--gray);font-size:13px;font-weight:bold;transition:color .2s}
  .nav-links a:hover{color:var(--grn);text-decoration:none}
  .nav-live{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--gray)}
  .live-dot{width:8px;height:8px;border-radius:50%;background:var(--grn);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

  /* BREAKING */
  #breaking{background:#3D0000;border-top:2px solid var(--red);border-bottom:2px solid var(--red);
    padding:10px 20px;display:none;align-items:center;gap:12px;overflow:hidden}
  .breaking-icon{font-size:20px;flex-shrink:0}
  .breaking-label{color:var(--red);font-weight:bold;font-size:13px;flex-shrink:0}
  .breaking-text{color:#FFB3B3;font-size:13px;white-space:nowrap;overflow:hidden;
    animation:scroll 30s linear infinite}
  @keyframes scroll{0%{transform:translateX(100%)}100%{transform:translateX(-100%)}}

  /* CARDS */
  .row{padding:12px 16px;background:var(--mid);border-bottom:1px solid #1A3D28}
  .card-grid{display:grid;gap:12px}
  .g4{grid-template-columns:repeat(4,1fr)}
  .g3{grid-template-columns:repeat(3,1fr)}
  .g2{grid-template-columns:repeat(2,1fr)}
  .card{background:var(--panel);border:1px solid #1A4030;border-radius:8px;padding:14px;
    position:relative;overflow:hidden}
  .card::before{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:var(--grn)}
  .card-label{font-size:10px;color:var(--sgrn);font-weight:bold;text-transform:uppercase;
    letter-spacing:1px;margin-bottom:6px}
  .card-value{font-size:28px;font-weight:bold;color:var(--wht);line-height:1.1}
  .card-sub{font-size:13px;color:var(--gray);margin-top:4px}
  .card-change{font-size:16px;font-weight:bold;margin-top:4px}
  .card-sm .card-value{font-size:20px}

  /* PRICE HERO */
  #price-row{background:var(--dark);padding:16px}
  .price-hero .card-value{font-size:42px}

  /* CHART ROW */
  #chart-row{background:var(--dark);padding:8px 16px}
  #tv-chart{width:100%;height:480px;border-radius:8px;overflow:hidden;border:1px solid #1A4030}

  /* AI ROW */
  .ai-row{background:var(--ai);border:1px solid var(--gold);border-radius:0}
  .ai-label{background:var(--gold);color:#000;font-size:10px;font-weight:bold;
    padding:4px 10px;letter-spacing:1px;display:inline-block;border-radius:4px;margin-bottom:8px}
  .ai-us-label{background:#0050AA;color:#fff;font-size:10px;font-weight:bold;
    padding:4px 10px;letter-spacing:1px;display:inline-block;border-radius:4px;margin-bottom:8px}
  .ai-text{font-size:13px;color:#D0E8FF;line-height:1.6}
  .ai-thesis{font-size:13px;color:var(--sgrn);line-height:1.7}
  .signal-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:6px}
  .signal-chip{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--wht);
    background:#0A2020;padding:4px 6px;border-radius:4px}
  .sig-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
  .sig-bull{background:var(--grn)}.sig-bear{background:var(--red)}
  .sig-neut{background:var(--ylw)}.sig-quiet{background:#444}
  .ai-meta{font-size:11px;color:#556;line-height:1.8}

  /* INSIGHTS / NEWS */
  #insights-hdr{background:#091A10;padding:8px 16px;border-bottom:1px solid #1A3D28;
    display:flex;gap:20px;align-items:center}
  .insights-label{font-size:12px;font-weight:bold;color:var(--grn);text-transform:uppercase;
    letter-spacing:1px}
  #main-content{display:grid;grid-template-columns:1fr 340px;gap:0;background:var(--dark)}

  /* NEWS FEED */
  #news-panel{background:var(--dark);border-right:1px solid #1A3D28;padding:12px}
  .news-controls{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center}
  .search-box{flex:1;min-width:160px;background:#0A1A10;border:1px solid #1A4030;
    color:var(--wht);padding:6px 10px;border-radius:4px;font-size:12px;outline:none}
  .search-box:focus{border-color:var(--grn)}
  .filter-btn{background:#0A1A10;border:1px solid #1A4030;color:var(--gray);
    padding:5px 10px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:bold;transition:all .2s}
  .filter-btn:hover,.filter-btn.active{background:var(--grn);color:#000;border-color:var(--grn)}
  .story-card{background:var(--panel);border:1px solid #1A4030;border-radius:6px;
    padding:10px;margin-bottom:8px;cursor:pointer;transition:border-color .2s}
  .story-card:hover{border-color:var(--grn)}
  .story-header{display:flex;align-items:center;gap:6px;margin-bottom:5px;flex-wrap:wrap}
  .src-badge{font-size:10px;font-weight:bold;padding:2px 6px;border-radius:3px}
  .src-official {background:#0050AA;color:#fff}
  .src-major    {background:#1A4030;color:var(--sgrn)}
  .src-xrp      {background:#003330;color:var(--grn)}
  .src-community{background:#2A1A00;color:#FFA500}
  .src-international{background:#1A0030;color:#CC99FF}
  .src-aggregator{background:#1A1A00;color:#FFFF00}
  .src-legal    {background:#3D0000;color:#FF9999}
  .src-mainstream{background:#001A2E;color:#99CCFF}
  .src-institutional{background:#001A2E;color:var(--gold)}
  .story-title{font-size:13px;font-weight:bold;color:var(--wht);line-height:1.4;margin-bottom:4px}
  .story-summary{font-size:11px;color:var(--gray);line-height:1.5;margin-bottom:5px}
  .story-footer{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .sentiment-tag{font-size:10px;font-weight:bold;padding:2px 6px;border-radius:3px}
  .sent-bullish{background:#0A3A20;color:var(--grn)}
  .sent-bearish{background:#3A0A0A;color:var(--red)}
  .sent-neutral{background:#1A1A1A;color:var(--gray)}
  .cat-tag{font-size:10px;color:#556;background:#0A1410;padding:2px 5px;border-radius:3px}
  .story-age{font-size:10px;color:#3A5A40;margin-left:auto}
  #news-count{font-size:11px;color:#3A6A40;padding:4px 0 8px}

  /* RIGHT PANEL */
  #right-panel{background:var(--mid)}
  .right-card{padding:12px;border-bottom:1px solid #1A3D28}
  .right-title{font-size:11px;font-weight:bold;color:var(--sgrn);text-transform:uppercase;
    letter-spacing:1px;margin-bottom:8px}
  .stat-row{display:flex;justify-content:space-between;align-items:center;
    padding:3px 0;border-bottom:1px solid #0A2018;font-size:12px}
  .stat-label{color:var(--gray)}
  .stat-val{color:var(--wht);font-weight:bold}
  .stat-val.grn{color:var(--grn)}

  /* SCOREBOARD */
  #scoreboard{background:var(--mid);padding:12px 16px;border-top:1px solid #1A3D28}
  .score-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
  .score-card{background:var(--panel);border-radius:6px;padding:10px;text-align:center}
  .score-num{font-size:24px;font-weight:bold;color:var(--wht)}
  .score-lbl{font-size:10px;color:var(--gray);text-transform:uppercase;letter-spacing:1px}
  .score-sub{font-size:11px;color:#3A6A40;margin-top:2px}

  /* FOOTER */
  #footer{background:#020805;padding:14px 20px;border-top:2px solid #1A3D28;
    display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-items:center}
  .footer-section{font-size:11px;color:#3A5A40;line-height:1.8}
  .footer-section strong{color:var(--sgrn)}
  .footer-disclaimer{font-size:10px;color:#555}

  /* SYSTEM HEALTH BAR */
  #sys-health{background:#0A0A05;border-top:2px solid var(--ylw);
    display:grid;grid-template-columns:repeat(4,1fr);gap:0}
  .sys-zone{padding:10px 14px;border-right:1px solid #2A2A00}
  .sys-zone:last-child{border-right:none}
  .sys-title{font-size:9px;font-weight:bold;color:var(--ylw);text-transform:uppercase;
    letter-spacing:1px;margin-bottom:4px}
  .sys-val{font-size:12px;color:var(--wht);font-weight:bold}
  .sys-sub{font-size:10px;color:#666;margin-top:2px;line-height:1.5}
  .pass{color:var(--grn)}.fail{color:var(--red)}.warn{color:var(--ylw)}

  /* MISC */
  .row-title{font-size:10px;font-weight:bold;color:var(--sgrn);text-transform:uppercase;
    letter-spacing:1px;margin-bottom:10px}
  .loading{color:#1A4030;font-size:12px;font-style:italic}
  .tradingview-widget-container{width:100%;height:100%}
</style>
</head>
<body>

<!-- ROW 0: NAV BAR -->
<div id="nav">
  <div class="nav-logo">
    <span class="sat">🛰️</span>
    <div>
      <div>XRPRadar</div>
      <div class="nav-tagline">Everything XRP. All the time.</div>
    </div>
  </div>
  <div class="nav-links">
    <a href="#price-row">MARKETS</a>
    <a href="#news-panel">NEWS</a>
    <a href="#ai-briefing-us">INTELLIGENCE</a>
    <a href="#sys-health">SYSTEM</a>
  </div>
  <div class="nav-live">
    <div class="live-dot"></div>
    <span>LIVE</span>
    <span id="nav-updated" style="margin-left:6px">Connecting...</span>
  </div>
</div>

<!-- ROW 1: BREAKING NEWS BANNER -->
<div id="breaking">
  <span class="breaking-icon">📰</span>
  <span class="breaking-label">⚡ BREAKING</span>
  <div class="breaking-text" id="breaking-text"></div>
</div>

<!-- ROW 2: PRICE AND VALUE -->
<div id="price-row">
  <div class="row-title">💲 PRICE AND VALUE</div>
  <div class="card-grid g4">
    <div class="card price-hero">
      <div class="card-label">XRP / USD</div>
      <div class="card-value" id="p-price">--</div>
      <div class="card-change" id="p-change24">--</div>
      <div class="card-sub" id="p-change7">7D: --</div>
    </div>
    <div class="card">
      <div class="card-label">Market Cap</div>
      <div class="card-value card-sm" id="p-mcap">--</div>
      <div class="card-sub" id="p-rank">Rank --</div>
      <div class="card-sub" id="p-supply">-- circulating</div>
    </div>
    <div class="card">
      <div class="card-label">24h Trading Volume</div>
      <div class="card-value card-sm" id="p-vol">--</div>
      <div class="card-sub" id="p-volratio">Vol/MCap: --%</div>
      <div class="card-sub" id="p-btc">BTC: --</div>
    </div>
    <div class="card">
      <div class="card-label">Fear &amp; Greed</div>
      <div class="card-value card-sm" id="fg-score">--</div>
      <div class="card-sub" id="fg-label">--</div>
      <div class="card-sub" style="margin-top:8px">
        <span style="font-size:10px;color:#3A6A40">Extreme Fear ← → Extreme Greed</span>
      </div>
    </div>
  </div>
</div>

<!-- ROW 3: SECONDARY PRICE ROW -->
<div class="row">
  <div class="card-grid g4">
    <div class="card card-sm">
      <div class="card-label">Price Change</div>
      <div class="card-sub">7 Day: <span id="s-7d" style="font-weight:bold">--</span></div>
      <div class="card-sub" style="margin-top:4px">30 Day: <span id="s-30d" style="font-weight:bold">--</span></div>
    </div>
    <div class="card card-sm">
      <div class="card-label">All-Time High</div>
      <div class="card-value" id="s-ath" style="font-size:22px">--</div>
      <div class="card-sub" id="s-ath-pct">--% below ATH</div>
    </div>
    <div class="card card-sm">
      <div class="card-label">XRP / BTC</div>
      <div class="card-value" id="s-btc" style="font-size:18px;word-break:break-all">--</div>
      <div class="card-sub" style="color:#3A6A40;font-size:10px">BTC pair — altseason signal</div>
    </div>
    <div class="card card-sm">
      <div class="card-label">⏳ Next Ripple Escrow</div>
      <div class="card-value" id="esc-date" style="font-size:14px">--</div>
      <div class="card-sub" id="esc-note">1B XRP monthly release</div>
    </div>
  </div>
</div>

<!-- ROW 4: LIVE CHART -->
<div id="chart-row">
  <div class="row-title">📊 LIVE XRP/USD CHART</div>
  <div id="tv-chart">
    <div class="tradingview-widget-container">
      <div id="tradingview_xrp"></div>
      <script type="text/javascript"
        src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {
        "autosize": true,
        "symbol": "BITSTAMP:XRPUSD",
        "interval": "60",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "backgroundColor": "#050F0A",
        "gridColor": "#0A1A10",
        "hide_top_toolbar": false,
        "hide_legend": false,
        "save_image": false,
        "calendar": false,
        "support_host": "https://www.tradingview.com"
      }
      </script>
    </div>
  </div>
</div>

<!-- ROW 5-A: AI BRIEFING — US FOCUS -->
<div id="ai-briefing-us" class="row ai-row" style="padding:14px 16px">
  <div class="card-grid g4">
    <div>
      <div class="ai-us-label">🇺🇸 US INTELLIGENCE</div>
      <div class="ai-text" id="ai-us-pulse"><span class="loading">Analyzing US sources...</span></div>
    </div>
    <div>
      <div class="ai-us-label">US REGULATORY</div>
      <div class="ai-text" id="ai-us-regulatory"><span class="loading">Loading...</span></div>
    </div>
    <div>
      <div class="ai-us-label">US INSTITUTIONAL</div>
      <div class="ai-text" id="ai-us-institutional"><span class="loading">Loading...</span></div>
    </div>
    <div>
      <div class="ai-us-label">📍 US DATA</div>
      <div class="ai-meta" id="ai-us-meta">Waiting for data...</div>
    </div>
  </div>
</div>

<!-- ROW 5-B: AI BRIEFING — GLOBAL -->
<div class="row ai-row" style="padding:14px 16px;border-top:1px solid #1A3A0A">
  <div class="card-grid g4">
    <div>
      <div class="ai-label">🌐 GLOBAL PULSE</div>
      <div class="ai-text" id="ai-gl-pulse"><span class="loading">Synthesizing global signals...</span></div>
    </div>
    <div>
      <div class="ai-label">🗺️ REGIONAL SIGNALS</div>
      <div id="ai-signals" class="signal-grid">
        <div class="loading">Loading...</div>
      </div>
    </div>
    <div>
      <div class="ai-label">🧠 CUMULATIVE THESIS</div>
      <div class="ai-thesis" id="ai-gl-thesis"><span class="loading">Building analysis...</span></div>
    </div>
    <div>
      <div class="ai-label">📍 GLOBAL DATA</div>
      <div class="ai-meta" id="ai-gl-meta">Waiting for data...</div>
    </div>
  </div>
</div>

<!-- ROW 6: INSIGHTS HEADER -->
<div id="insights-hdr">
  <span class="insights-label">📡 INSIGHTS</span>
  <span style="color:#1A4030;font-size:11px">|</span>
  <span class="insights-label" style="color:var(--sgrn)">📰 GLOBAL NEWS FEED</span>
  <span style="color:#1A4030;font-size:11px;margin-left:auto">🔗 ON-CHAIN &amp; MARKET DATA ▶</span>
</div>

<!-- ROW 7: MAIN CONTENT -->
<div id="main-content">

  <!-- NEWS PANEL (left) -->
  <div id="news-panel">
    <div class="news-controls">
      <input class="search-box" id="search-box" placeholder="🔍 Search XRP news..." oninput="filterNews()">
      <button class="filter-btn active" onclick="setFilter(this,'all')">ALL</button>
      <button class="filter-btn" onclick="setFilter(this,'Price')">PRICE</button>
      <button class="filter-btn" onclick="setFilter(this,'Legal')">LEGAL</button>
      <button class="filter-btn" onclick="setFilter(this,'Regulatory')">REG</button>
      <button class="filter-btn" onclick="setFilter(this,'Ecosystem')">ECOSYSTEM</button>
      <button class="filter-btn" onclick="setFilter(this,'Technical')">TECH</button>
      <button class="filter-btn" onclick="setFilter(this,'Whale')">WHALE</button>
    </div>
    <div id="news-count" class="loading">Loading news...</div>
    <div id="news-feed"></div>
  </div>

  <!-- RIGHT PANEL -->
  <div id="right-panel">
    <!-- XRPL Network -->
    <div class="right-card">
      <div class="right-title">🔗 XRPL NETWORK</div>
      <div class="stat-row"><span class="stat-label">Network</span><span class="stat-val grn">● Live</span></div>
      <div class="stat-row"><span class="stat-label">Consensus</span><span class="stat-val">Federated Byzantine</span></div>
      <div class="stat-row"><span class="stat-label">Avg Close Time</span><span class="stat-val">~3-5 sec</span></div>
      <div class="stat-row"><span class="stat-label">Transaction Fee</span><span class="stat-val">~0.00001 XRP</span></div>
      <div class="stat-row"><span class="stat-label">Circulating Supply</span><span class="stat-val" id="rc-supply">--</span></div>
      <div class="stat-row"><span class="stat-label">Escrow Locked</span><span class="stat-val" id="rc-escrow">~43B XRP</span></div>
    </div>
    <!-- Market Structure -->
    <div class="right-card">
      <div class="right-title">📊 MARKET STRUCTURE</div>
      <div class="stat-row"><span class="stat-label">Global Rank</span><span class="stat-val" id="rm-rank">--</span></div>
      <div class="stat-row"><span class="stat-label">Market Cap</span><span class="stat-val" id="rm-mcap">--</span></div>
      <div class="stat-row"><span class="stat-label">24h Volume</span><span class="stat-val" id="rm-vol">--</span></div>
      <div class="stat-row"><span class="stat-label">Vol / MCap</span><span class="stat-val" id="rm-ratio">--</span></div>
      <div class="stat-row"><span class="stat-label">ATH</span><span class="stat-val" id="rm-ath">--</span></div>
      <div class="stat-row"><span class="stat-label">% Below ATH</span><span class="stat-val" id="rm-ath-pct">--</span></div>
    </div>
    <!-- Feed Health -->
    <div class="right-card">
      <div class="right-title">📡 FEED STATUS</div>
      <div class="stat-row">
        <span class="stat-label">Active Feeds</span>
        <span class="stat-val grn" id="feed-active">--/25</span>
      </div>
      <div id="feed-health-list" style="margin-top:6px;max-height:200px;overflow-y:auto"></div>
    </div>
    <!-- Upgrade Log -->
    <div class="right-card">
      <div class="right-title">📋 UPGRADE LOG</div>
      <div id="upgrade-log" style="font-size:11px;color:#3A6A40;line-height:1.8"></div>
    </div>
  </div>
</div>

<!-- ROW 16: SCOREBOARD -->
<div id="scoreboard">
  <div class="row-title">🦂 XRPRADAR SCOREBOARD</div>
  <div class="score-grid">
    <div class="score-card">
      <div class="score-num" id="sc-total">--</div>
      <div class="score-lbl">Stories Today</div>
      <div class="score-sub" id="sc-feeds">-- sources active</div>
    </div>
    <div class="score-card" style="border-top:2px solid var(--grn)">
      <div class="score-num" style="color:var(--grn)" id="sc-bull">--</div>
      <div class="score-lbl">🟢 Bullish</div>
      <div class="score-sub" id="sc-bull-pct">--%</div>
    </div>
    <div class="score-card" style="border-top:2px solid var(--red)">
      <div class="score-num" style="color:var(--red)" id="sc-bear">--</div>
      <div class="score-lbl">🔴 Bearish</div>
      <div class="score-sub" id="sc-bear-pct">--%</div>
    </div>
    <div class="score-card">
      <div class="score-num" style="color:var(--gray)" id="sc-neut">--</div>
      <div class="score-lbl">⚪ Neutral</div>
      <div class="score-sub" id="sc-net">Net: --</div>
    </div>
  </div>
</div>

<!-- ROW 17: FOOTER -->
<div id="footer">
  <div class="footer-section">
    <div>🛰️ <strong>XRPRadar.com</strong></div>
    <div>Version: <strong id="ft-ver">--</strong></div>
    <div>Built on Railway + Flask</div>
  </div>
  <div class="footer-section footer-disclaimer">
    <strong>⚠️ Not Financial Advice</strong><br>
    XRPRadar is for informational<br>
    purposes only. DYOR.
  </div>
  <div class="footer-section">
    🔄 All data refreshes automatically<br>
    Price: every 60 seconds<br>
    News &amp; AI: every 10 minutes
  </div>
  <div class="footer-section">
    © 2026 XRPRadar.com<br>
    Powered by Flask + Claude API<br>
    <span id="ft-uptime" style="color:#1A4030">--</span>
  </div>
</div>

<!-- ROW 18: SYSTEM HEALTH BAR -->
<div id="sys-health">
  <div class="sys-zone">
    <div class="sys-title">📦 VERSION / LAST UPDATED</div>
    <div class="sys-val" id="sh-version">--</div>
    <div class="sys-sub" id="sh-updated">--</div>
  </div>
  <div class="sys-zone">
    <div class="sys-title">✅ PREFLIGHT / QA CHECK (every 4h)</div>
    <div class="sys-val" id="sh-qa-status">--</div>
    <div class="sys-sub" id="sh-qa-last">Last run: --</div>
    <div id="sh-qa-detail" class="sys-sub" style="margin-top:4px"></div>
  </div>
  <div class="sys-zone">
    <div class="sys-title">🔴 DEBUG / FEED INTEGRITY</div>
    <div class="sys-val" id="sh-feeds">--/25 feeds active</div>
    <div class="sys-sub" id="sh-error">No errors</div>
    <div class="sys-sub" id="sh-error-ts"></div>
  </div>
  <div class="sys-zone">
    <div class="sys-title">🔧 MAINTENANCE REQUEST</div>
    <div class="sys-val pass" id="sh-maint">✅ OK</div>
    <div class="sys-sub">Start: <span id="sh-start">--</span></div>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────
let allStories   = [];
let activeCat    = "all";
let activeSearch = "";
let lastDataHash = "";

// ── Data Fetch ──────────────────────────────────────────────────────────
async function fetchData() {
  try {
    const r = await fetch("/api/data");
    const d = await r.json();
    updatePrice(d);
    updateAI(d);
    updateScoreboard(d);
    updateSystemHealth(d);
    updateSidePanels(d);
    if (d.last_updated) {
      document.getElementById("nav-updated").textContent = d.last_updated.replace(" UTC","") + " UTC";
    }
    if (d.upgrade_log) {
      document.getElementById("upgrade-log").innerHTML =
        d.upgrade_log.map(u => `<div style="margin-bottom:4px"><span style="color:var(--gold)">${u.ts}</span><br>${u.note}</div>`).join("");
    }
    if (d.version) {
      document.getElementById("ft-ver").textContent = d.version;
    }
    if (d.start_time) {
      const st = new Date(d.start_time);
      const now = new Date();
      const hrs = Math.floor((now - st) / 3600000);
      document.getElementById("ft-uptime").textContent = `Uptime: ${hrs}h`;
    }
  } catch(e) { console.error("fetchData:", e); }
}

async function fetchNews() {
  try {
    const r = await fetch("/api/news");
    const d = await r.json();
    allStories = d.stories || [];
    renderNews();
  } catch(e) { console.error("fetchNews:", e); }
}

// ── Price Update ────────────────────────────────────────────────────────
function updatePrice(d) {
  const p  = d.price || {};
  const fg = d.fear_greed || {};
  const ex = d.escrow || {};

  function c(id, val) { const el = document.getElementById(id); if(el) el.textContent = val; }
  function col(id, v) { const el = document.getElementById(id); if(el) el.style.color = v >= 0 ? "var(--grn)" : "var(--red)"; }

  const price = p.usd || 0;
  c("p-price",   `$${price.toFixed(4)}`);

  const ch24 = p.change_24h || 0;
  const el24 = document.getElementById("p-change24");
  if (el24) { el24.textContent = `${ch24 >= 0 ? "▲" : "▼"} ${Math.abs(ch24).toFixed(2)}% (24h)`; el24.style.color = ch24 >= 0 ? "var(--grn)" : "var(--red)"; }

  const ch7 = p.change_7d || 0;
  c("p-change7", `7D: ${ch7 >= 0 ? "+" : ""}${ch7.toFixed(2)}%`);
  col("p-change7", ch7);

  c("p-mcap",    fmtUSD(p.mcap));
  c("p-rank",    `Rank #${p.rank || "--"}`);
  c("p-supply",  p.supply_circ ? `${(p.supply_circ/1e9).toFixed(1)}B circulating` : "--");
  c("p-vol",     fmtUSD(p.volume_24h));
  c("p-volratio",p.vol_mcap_ratio ? `Vol/MCap: ${p.vol_mcap_ratio}%` : "Vol/MCap: --");
  c("p-btc",     p.btc ? `BTC: ${p.btc.toFixed(8)}` : "BTC: --");

  c("fg-score",  fg.score !== undefined ? fg.score : "--");
  c("fg-label",  fg.label || "--");
  const fgEl = document.getElementById("fg-score");
  if (fgEl && fg.score !== undefined) {
    fgEl.style.color = fg.score < 30 ? "var(--red)" : fg.score > 70 ? "var(--grn)" : "var(--ylw)";
  }

  const ch7b  = p.change_7d || 0;
  const ch30  = p.change_30d || 0;
  const el7   = document.getElementById("s-7d");
  const el30  = document.getElementById("s-30d");
  if (el7)  { el7.textContent  = `${ch7b >= 0 ? "+" : ""}${ch7b.toFixed(2)}%`;  el7.style.color  = ch7b >= 0 ? "var(--grn)" : "var(--red)"; }
  if (el30) { el30.textContent = `${ch30 >= 0 ? "+" : ""}${ch30.toFixed(2)}%`; el30.style.color = ch30 >= 0 ? "var(--grn)" : "var(--red)"; }

  c("s-ath",    p.ath ? `$${p.ath.toFixed(4)}` : "--");
  const athPct = p.ath_pct || 0;
  const athEl  = document.getElementById("s-ath-pct");
  if (athEl) { athEl.textContent = `${athPct.toFixed(1)}% below ATH`; athEl.style.color = "var(--org)"; }

  c("s-btc",    p.btc ? `₿ ${p.btc.toFixed(8)}` : "--");
  c("esc-date", ex.next_date || "--");
  c("esc-note", ex.note || "1B XRP monthly release");

  // Side panel mirrors
  c("rc-supply", p.supply_circ ? `${(p.supply_circ/1e9).toFixed(1)}B XRP` : "--");
  c("rm-rank",   `#${p.rank || "--"}`);
  c("rm-mcap",   fmtUSD(p.mcap));
  c("rm-vol",    fmtUSD(p.volume_24h));
  c("rm-ratio",  p.vol_mcap_ratio ? `${p.vol_mcap_ratio}%` : "--");
  c("rm-ath",    p.ath ? `$${p.ath.toFixed(4)}` : "--");
  c("rm-ath-pct",athPct ? `${Math.abs(athPct).toFixed(1)}% below` : "--");

  // Breaking news
  if (d.breaking) {
    const bb = document.getElementById("breaking");
    const bt = document.getElementById("breaking-text");
    if (bb && bt) {
      bt.textContent = `${d.breaking.title} — via ${d.breaking.source}`;
      bb.style.display = "flex";
    }
  } else {
    const bb = document.getElementById("breaking");
    if (bb) bb.style.display = "none";
  }
}

// ── AI Update ────────────────────────────────────────────────────────────
function updateAI(d) {
  const us = d.ai_us || {};
  const gl = d.ai_global || {};

  function c(id, val) { const el = document.getElementById(id); if(el && val) el.textContent = val; }

  c("ai-us-pulse",         us.pulse || "");
  c("ai-us-regulatory",    us.regulatory || "");
  c("ai-us-institutional", us.institutional || "");
  if (us.ts) {
    const m = document.getElementById("ai-us-meta");
    if (m) m.innerHTML = `Last analysis: <strong style="color:var(--sgrn)">${us.ts}</strong><br>US sources monitored`;
  }

  c("ai-gl-pulse",  gl.pulse || "");
  c("ai-gl-thesis", gl.thesis || "");

  // Regional signals
  const sg = gl.signals || {};
  const sigContainer = document.getElementById("ai-signals");
  if (sigContainer && Object.keys(sg).length) {
    const dotClass = {"bullish":"sig-bull","bearish":"sig-bear","neutral":"sig-neut","quiet":"sig-quiet"};
    const flags    = {"Japan":"🇯🇵","Korea":"🇰🇷","UAE":"🇦🇪","Europe":"🇪🇺","LatAm":"🌎","Africa":"🌍","India":"🇮🇳"};
    sigContainer.innerHTML = Object.entries(sg).map(([region, status]) =>
      `<div class="signal-chip">
        <div class="sig-dot ${dotClass[status]||"sig-quiet"}"></div>
        <span>${flags[region]||""} ${region}</span>
       </div>`
    ).join("");
  }

  if (gl.ts) {
    const m = document.getElementById("ai-gl-meta");
    if (m) m.innerHTML = `Last analysis: <strong style="color:var(--sgrn)">${gl.ts}</strong><br>217 sources monitored<br>All regions active`;
  }
}

// ── Scoreboard ────────────────────────────────────────────────────────────
function updateScoreboard(d) {
  const st = d.story_stats || {};
  function c(id,v){ const el=document.getElementById(id); if(el) el.textContent=v; }
  c("sc-total",  st.today || 0);
  c("sc-feeds",  `${d.feeds_active||0}/${d.feeds_total||25} sources active`);
  c("sc-bull",   st.bullish || 0);
  c("sc-bear",   st.bearish || 0);
  c("sc-neut",   st.neutral || 0);
  const t = st.today || 1;
  c("sc-bull-pct", `${Math.round((st.bullish||0)/t*100)}%`);
  c("sc-bear-pct", `${Math.round((st.bearish||0)/t*100)}%`);
  const net = (st.bullish||0)-(st.bearish||0);
  const netEl = document.getElementById("sc-net");
  if (netEl) { netEl.textContent = `Net: ${net>=0?"+":""}${net}`; netEl.style.color = net>=0?"var(--grn)":"var(--red)"; }
}

// ── System Health ─────────────────────────────────────────────────────────
function updateSystemHealth(d) {
  function c(id,v){ const el=document.getElementById(id); if(el) el.textContent=v; }

  c("sh-version",  d.version || "--");
  c("sh-updated",  d.last_updated || "--");
  c("sh-feeds",    `${d.feeds_active||0}/${d.feeds_total||25} feeds active`);

  const qaEl = document.getElementById("sh-qa-status");
  if (qaEl) {
    qaEl.textContent  = d.qa_status || "PENDING";
    qaEl.className    = "sys-val " + (d.qa_status==="PASS"?"pass":d.qa_status==="FAIL"?"fail":"warn");
  }
  c("sh-qa-last", `Last run: ${d.qa_last||"Not yet run"}`);

  if (d.qa_details && d.qa_details.length) {
    const detail = document.getElementById("sh-qa-detail");
    if (detail) detail.innerHTML = d.qa_details.map(chk =>
      `<span style="color:${chk.ok?"var(--grn)":"var(--red)"}">${chk.ok?"✓":"✗"} ${chk.name}</span>`
    ).join(" &nbsp;");
  }

  if (d.last_error) {
    c("sh-error",    `Last error: ${d.last_error}`);
    c("sh-error-ts", d.last_error_ts || "");
    const errEl = document.getElementById("sh-error");
    if (errEl) errEl.style.color = "var(--red)";
  } else {
    c("sh-error", "No errors logged");
  }

  const maintEl = document.getElementById("sh-maint");
  if (maintEl) {
    const m = d.maintenance || "OK";
    maintEl.textContent = m === "OK" ? "✅ OK" : m === "ACTIVE" ? "🔧 ACTIVE" : "⏳ PENDING";
    maintEl.className   = "sys-val " + (m==="OK"?"pass":m==="ACTIVE"?"warn":"warn");
  }

  if (d.start_time) {
    const st = new Date(d.start_time);
    c("sh-start", st.toISOString().replace("T"," ").substring(0,16)+" UTC");
  }

  // Feed health list
  const fhl = document.getElementById("feed-health-list");
  const fha = document.getElementById("feed-active");
  if (fhl && d.feed_health) {
    const entries = Object.entries(d.feed_health);
    const upCount = entries.filter(([,v])=>v==="UP").length;
    if (fha) fha.textContent = `${upCount}/${entries.length}`;
    fhl.innerHTML = entries.map(([name, status]) =>
      `<div class="stat-row">
        <span class="stat-label" style="font-size:10px">${name}</span>
        <span style="font-size:10px;color:${status==="UP"?"var(--grn)":"var(--red)"}">${status==="UP"?"●":"✗"}</span>
       </div>`
    ).join("");
  }
}

function updateSidePanels(d) {
  // Already handled in updatePrice
}

// ── News Render ───────────────────────────────────────────────────────────
const srcColors = {
  official:"src-official", major:"src-major", xrp:"src-xrp",
  community:"src-community", international:"src-international",
  aggregator:"src-aggregator", legal:"src-legal",
  mainstream:"src-mainstream", institutional:"src-institutional"
};

function renderNews() {
  let stories = allStories;
  if (activeCat !== "all")   stories = stories.filter(s => s.category === activeCat);
  if (activeSearch)          stories = stories.filter(s => s.title.toLowerCase().includes(activeSearch));

  const feed = document.getElementById("news-feed");
  const cnt  = document.getElementById("news-count");
  if (!feed) return;

  if (cnt) cnt.textContent = `${stories.length} stories — click to open`;

  if (!stories.length) {
    feed.innerHTML = `<div class="loading" style="padding:20px 0">No stories match your filter. Feeds refresh every 10 minutes.</div>`;
    return;
  }

  feed.innerHTML = stories.slice(0,80).map(s => {
    const srcClass = srcColors[s.type] || "src-major";
    const sentClass = `sent-${s.sentiment}`;
    const sentLabel = s.sentiment === "bullish" ? "🟢 Bullish" : s.sentiment === "bearish" ? "🔴 Bearish" : "⚪ Neutral";
    const summary   = s.summary ? `<div class="story-summary">${s.summary.substring(0,180)}${s.summary.length>180?"...":""}</div>` : "";
    return `<div class="story-card" onclick="window.open('${s.link}','_blank')">
      <div class="story-header">
        <span class="src-badge ${srcClass}">${s.source}</span>
        <span class="cat-tag">${s.category}</span>
        ${s.breaking ? '<span style="color:var(--red);font-size:10px;font-weight:bold">⚡ BREAKING</span>' : ""}
      </div>
      <div class="story-title">${s.title}</div>
      ${summary}
      <div class="story-footer">
        <span class="sentiment-tag ${sentClass}">${sentLabel}</span>
        <span class="story-age">${s.age || ""}</span>
      </div>
    </div>`;
  }).join("");
}

function setFilter(btn, cat) {
  activeCat = cat;
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  renderNews();
}

function filterNews() {
  activeSearch = document.getElementById("search-box").value.toLowerCase();
  renderNews();
}

// ── Utilities ─────────────────────────────────────────────────────────────
function fmtUSD(v) {
  if (!v) return "--";
  v = parseFloat(v);
  if (v >= 1e12) return `$${(v/1e12).toFixed(2)}T`;
  if (v >= 1e9)  return `$${(v/1e9).toFixed(2)}B`;
  if (v >= 1e6)  return `$${(v/1e6).toFixed(2)}M`;
  if (v >= 1e3)  return `$${(v/1e3).toFixed(2)}K`;
  return `$${v.toFixed(2)}`;
}

// ── Init & Timers ──────────────────────────────────────────────────────────
fetchData();
fetchNews();
setInterval(fetchData,  60000);   // price + system every 60s
setInterval(fetchNews,  600000);  // news every 10 min
</script>
</body>
</html>"""

# ── Startup ────────────────────────────────────────────────────────────────────
load_state()
threading.Thread(target=price_loop, daemon=True).start()
threading.Thread(target=news_loop,  daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
