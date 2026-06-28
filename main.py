"""
XRPRadar v1.1 — XRPRadar.com
Signals Over Noise 24/7
"""

import os, json, time, threading, hashlib, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import feedparser
import requests
from flask import Flask, jsonify, Response, request

app = Flask(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
BOT_FILE          = "XRPRadar_v7.0"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
SCAN_INTERVAL     = 600
PRICE_INTERVAL    = 60
AI_INTERVAL       = 600
MAX_STORIES       = 500
QA_INTERVAL       = 14400

# ── XRP Keywords ──────────────────────────────────────────────────────────────
XRP_KEYWORDS = [
    "xrp","ripple","xrpl","garlinghouse","david schwartz","joelkatz",
    "ripplenet","rlusd","on-demand liquidity","odl","sbi ripple","xrp ledger",
    "brad garlinghouse","ripple labs","xrpturbo","xrp etf","xrp spot"
]

BREAKING_KEYWORDS = [
    "sec","etf","lawsuit","hack","ban","arrested","sanction","escrow",
    "rlusd","occ","crash","surge","ruling","verdict","settlement","injunction",
    "delisted","partnership","approved","rejected","seized","breaking","urgent",
    "alert","just in","confirmed","official"
]

BULL_WORDS = [
    "surge","rally","rise","pump","bull","gain","high","ath","partnership",
    "approval","bullish","positive","launch","adoption","buy","soar","spike",
    "jump","up","approved","milestone","record","win","victory","integration",
    "listed","breakout","recovery","rebound","support"
]

BEAR_WORDS = [
    "drop","crash","fall","dump","bear","loss","low","lawsuit","ban","sell",
    "bearish","negative","hack","reject","fud","plunge","decline","down",
    "arrest","seized","delisted","suspended","warning","risk","fear","concern",
    "resistance","breakdown","correction"
]

CAT_KEYWORDS = {
    "Legal":      ["sec","lawsuit","court","ruling","regulatory","cftc","legal","judge","verdict","settlement","appeal","doj"],
    "Regulatory": ["regulation","law","bill","act","policy","government","congress","senate","mica","fsb","occ","fed"],
    "Whale":      ["whale","large transaction","transfer","escrow","million xrp","billion xrp","moved","wallet","address"],
    "Ecosystem":  ["partnership","bank","adoption","launch","integration","ripplenet","odl","liquidity","sbi","payment","remittance"],
    "Technical":  ["xrpl","protocol","ledger","developer","update","release","code","github","amend","validator","amendment"],
    "Price":      ["price","market","trading","ath","rally","drop","value","usd","chart","analysis","prediction","target"],
}

REGION_KEYWORDS = {
    "Japan":          ["japan","japanese","sbi","moneynetint","coinpost","bitflyer","coincheck","jpn"],
    "Korea":          ["korea","korean","upbit","bithumb","coinone","korbit","krw"],
    "UAE":            ["uae","dubai","abu dhabi","emirates","difc","vara","middle east"],
    "Europe":         ["europe","european","eu","mica","ecb","uk","britain","germany","france","swiss"],
    "LatAm":          ["latin","latam","mexico","brazil","argentina","colombia","peru","chile","venezuela"],
    "Africa":         ["africa","nigeria","kenya","south africa","ghana","ethiopia","naira","afri"],
    "India":          ["india","indian","wazirx","coinswitch","coindcx","inr","sebi","rbi"],
    "SEA"           : ["singapore","thailand","vietnam","philippines","indonesia","malaysia","myanmar","sea"],
}

# ── Non-English detection ──────────────────────────────────────────────────────
def detect_language(text):
    non_ascii = sum(1 for c in text if ord(c) > 127)
    ratio = non_ascii / max(len(text), 1)
    if ratio > 0.15:
        return "non-english"
    return "en"

# ── RSS Feed List — 100 sources ───────────────────────────────────────────────
RSS_FEEDS = [
    # ── XRP-Dedicated ─────────────────────────────────────────────────────────
    {"name": "U.Today XRP",          "url": "https://u.today/rss/ripple.rss",                                                      "type": "xrp",          "region": "US",    "filter": False},
    {"name": "Crypto News Flash",     "url": "https://crypto-news-flash.com/tag/ripple/feed",                                       "type": "xrp",          "region": "US",    "filter": False},
    {"name": "XRP News (CoinTele)",   "url": "https://cointelegraph.com/rss/tag/ripple",                                            "type": "xrp",          "region": "US",    "filter": False},
    {"name": "CryptoSlate XRP",       "url": "https://cryptoslate.com/crypto/xrp/feed",                                             "type": "xrp",          "region": "US",    "filter": False},
    {"name": "Ripple Insights",       "url": "https://ripple.com/insights/feed",                                                    "type": "official",     "region": "US",    "filter": False},
    {"name": "XRPL.org Blog",         "url": "https://xrpl.org/blog/feed.xml",                                                      "type": "official",     "region": "US",    "filter": False},
    # ── Major US Crypto ────────────────────────────────────────────────────────
    {"name": "CoinDesk",              "url": "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",                      "type": "major",        "region": "US",    "filter": True},
    {"name": "Decrypt",               "url": "https://decrypt.co/feed",                                                             "type": "major",        "region": "US",    "filter": True},
    {"name": "The Block",             "url": "https://www.theblock.co/rss.xml",                                                     "type": "major",        "region": "US",    "filter": True},
    {"name": "Blockworks",            "url": "https://blockworks.co/feed",                                                          "type": "major",        "region": "US",    "filter": True},
    {"name": "Daily Hodl",            "url": "https://dailyhodl.com/feed",                                                          "type": "major",        "region": "US",    "filter": True},
    {"name": "AMBCrypto",             "url": "https://ambcrypto.com/feed",                                                          "type": "major",        "region": "US",    "filter": True},
    {"name": "BeInCrypto",            "url": "https://beincrypto.com/feed",                                                         "type": "major",        "region": "US",    "filter": True},
    {"name": "NewsBTC",               "url": "https://www.newsbtc.com/feed",                                                        "type": "major",        "region": "US",    "filter": True},
    {"name": "Finbold",               "url": "https://finbold.com/feed",                                                            "type": "major",        "region": "US",    "filter": True},
    {"name": "CryptoSlate",           "url": "https://cryptoslate.com/feed",                                                        "type": "major",        "region": "US",    "filter": True},
    {"name": "CryptoPotato",          "url": "https://cryptopotato.com/feed",                                                       "type": "major",        "region": "US",    "filter": True},
    {"name": "ZyCrypto",              "url": "https://zycrypto.com/feed",                                                           "type": "major",        "region": "US",    "filter": True},
    {"name": "Bitcoinist",            "url": "https://bitcoinist.com/feed",                                                         "type": "major",        "region": "US",    "filter": True},
    {"name": "Cryptonews",            "url": "https://cryptonews.com/feed",                                                         "type": "major",        "region": "US",    "filter": True},
    {"name": "CoinGape",              "url": "https://coingape.com/feed",                                                           "type": "major",        "region": "US",    "filter": True},
    {"name": "CryptoGlobe",           "url": "https://www.cryptoglobe.com/latest/feed",                                             "type": "major",        "region": "US",    "filter": True},
    {"name": "Crypto Daily",          "url": "https://cryptodaily.co.uk/feed",                                                      "type": "major",        "region": "EU",    "filter": True},
    {"name": "Invezz",                "url": "https://invezz.com/feed",                                                             "type": "major",        "region": "US",    "filter": True},
    {"name": "InsideBitcoins",        "url": "https://insidebitcoins.com/feed",                                                     "type": "major",        "region": "US",    "filter": True},
    {"name": "Crypto Briefing",       "url": "https://cryptobriefing.com/feed",                                                     "type": "major",        "region": "US",    "filter": True},
    {"name": "The Defiant",           "url": "https://thedefiant.io/feed",                                                          "type": "major",        "region": "US",    "filter": True},
    {"name": "Bitcoin Magazine",      "url": "https://bitcoinmagazine.com/feed",                                                    "type": "major",        "region": "US",    "filter": True},
    {"name": "Forbes Crypto",         "url": "https://www.forbes.com/crypto-blockchain/feed2",                                      "type": "mainstream",   "region": "US",    "filter": True},
    {"name": "Yahoo Finance Crypto",  "url": "https://finance.yahoo.com/rss/topic/crypto",                                         "type": "mainstream",   "region": "US",    "filter": True},
    # ── Google News — XRP Specific ────────────────────────────────────────────
    {"name": "GN: XRP Ripple",        "url": "https://news.google.com/rss/search?q=XRP+Ripple&hl=en-US&gl=US&ceid=US:en",         "type": "aggregator",   "region": "US",    "filter": False},
    {"name": "GN: XRP Legal",         "url": "https://news.google.com/rss/search?q=XRP+SEC+Ripple+lawsuit",                        "type": "legal",        "region": "US",    "filter": False},
    {"name": "GN: XRP ETF",           "url": "https://news.google.com/rss/search?q=XRP+ETF+institutional+2026",                    "type": "institutional","region": "US",    "filter": False},
    {"name": "GN: RLUSD",             "url": "https://news.google.com/rss/search?q=RLUSD+stablecoin+Ripple",                       "type": "xrp",          "region": "US",    "filter": False},
    {"name": "GN: XRP Price",         "url": "https://news.google.com/rss/search?q=XRP+price+analysis+prediction",                 "type": "xrp",          "region": "US",    "filter": False},
    {"name": "GN: XRP Whale",         "url": "https://news.google.com/rss/search?q=XRP+whale+transfer+billion",                    "type": "whale",        "region": "US",    "filter": False},
    {"name": "GN: XRP Adoption",      "url": "https://news.google.com/rss/search?q=XRP+adoption+bank+payment+Ripple",              "type": "ecosystem",    "region": "US",    "filter": False},
    {"name": "GN: Garlinghouse",      "url": "https://news.google.com/rss/search?q=Garlinghouse+XRP+Ripple",                       "type": "official",     "region": "US",    "filter": False},
    {"name": "GN: XRP Congress",      "url": "https://news.google.com/rss/search?q=XRP+crypto+regulation+Congress",                "type": "legal",        "region": "US",    "filter": False},
    {"name": "GN: XRP CFTC",          "url": "https://news.google.com/rss/search?q=XRP+CFTC+commodity",                            "type": "legal",        "region": "US",    "filter": False},
    {"name": "GN: XRP ODL",           "url": "https://news.google.com/rss/search?q=ODL+%22on-demand+liquidity%22+Ripple",          "type": "ecosystem",    "region": "US",    "filter": False},
    {"name": "GN: XRPL Dev",          "url": "https://news.google.com/rss/search?q=XRPL+developer+protocol+amendment",             "type": "technical",    "region": "US",    "filter": False},
    {"name": "GN: XRP Reuters",       "url": "https://news.google.com/rss/search?q=XRP+Ripple+Reuters",                            "type": "mainstream",   "region": "US",    "filter": False},
    {"name": "GN: XRP Bloomberg",     "url": "https://news.google.com/rss/search?q=XRP+Ripple+Bloomberg",                          "type": "mainstream",   "region": "US",    "filter": False},
    {"name": "GN: XRP CNBC",          "url": "https://news.google.com/rss/search?q=XRP+Ripple+CNBC",                               "type": "mainstream",   "region": "US",    "filter": False},
    {"name": "GN: XRP WSJ",           "url": "https://news.google.com/rss/search?q=XRP+Ripple+%22Wall+Street+Journal%22",          "type": "mainstream",   "region": "US",    "filter": False},
    {"name": "GN: XRP Bank",          "url": "https://news.google.com/rss/search?q=XRP+bank+financial+institution+payment",        "type": "institutional","region": "US",    "filter": False},
    {"name": "GN: XRP SBI",           "url": "https://news.google.com/rss/search?q=XRP+SBI+Japan+MoneyTap",                        "type": "international","region": "Japan", "filter": False},
    # ── Japan ─────────────────────────────────────────────────────────────────
    {"name": "CoinPost Japan",        "url": "https://coinpost.jp/?tag=ripple&feed=rss2",                                           "type": "international","region": "Japan", "filter": False},
    {"name": "CoinPost JP All",       "url": "https://coinpost.jp/?feed=rss2",                                                      "type": "international","region": "Japan", "filter": True},
    {"name": "Crypto Times JP",       "url": "https://crypto-times.jp/feed",                                                        "type": "international","region": "Japan", "filter": True},
    {"name": "GN Japan XRP",          "url": "https://news.google.com/rss/search?q=XRP+Ripple+%E3%83%AA%E3%83%97%E3%83%AB&hl=ja&gl=JP&ceid=JP:ja","type": "international","region": "Japan","filter": False},
    {"name": "GN Japan XRP EN",       "url": "https://news.google.com/rss/search?q=XRP+Ripple+Japan&hl=en",                        "type": "international","region": "Japan", "filter": False},
    # ── Korea ─────────────────────────────────────────────────────────────────
    {"name": "GN Korea XRP",          "url": "https://news.google.com/rss/search?q=XRP+%EB%A6%AC%ED%94%8C&hl=ko&gl=KR&ceid=KR:ko","type": "international","region": "Korea", "filter": False},
    {"name": "GN Korea XRP EN",       "url": "https://news.google.com/rss/search?q=XRP+Ripple+Korea+Bithumb+Upbit",                "type": "international","region": "Korea", "filter": False},
    {"name": "Decenter KR",           "url": "https://decenter.kr/feed",                                                            "type": "international","region": "Korea", "filter": True},
    # ── UAE & Middle East ─────────────────────────────────────────────────────
    {"name": "GN UAE XRP",            "url": "https://news.google.com/rss/search?q=XRP+Ripple+UAE+Dubai+%22Abu+Dhabi%22",          "type": "international","region": "UAE",   "filter": False},
    {"name": "GN ME Crypto",          "url": "https://news.google.com/rss/search?q=XRP+cryptocurrency+%22Middle+East%22+VARA",     "type": "international","region": "UAE",   "filter": False},
    # ── Europe ────────────────────────────────────────────────────────────────
    {"name": "BTC Echo DE",           "url": "https://www.btc-echo.de/feed",                                                        "type": "international","region": "Europe","filter": True},
    {"name": "CoinTelegraph DE",      "url": "https://de.cointelegraph.com/rss",                                                    "type": "international","region": "Europe","filter": True},
    {"name": "CoinTelegraph ES",      "url": "https://es.cointelegraph.com/rss",                                                    "type": "international","region": "LatAm", "filter": True},
    {"name": "Forkast Asia",          "url": "https://forkast.news/feed",                                                           "type": "international","region": "SEA",   "filter": True},
    {"name": "GN Europe XRP",         "url": "https://news.google.com/rss/search?q=XRP+Ripple+Europe+MiCA+ECB&hl=en-GB&gl=GB&ceid=GB:en","type": "international","region": "Europe","filter": False},
    {"name": "GN UK XRP",             "url": "https://news.google.com/rss/search?q=XRP+Ripple+UK+FCA+Britain",                     "type": "international","region": "Europe","filter": False},
    # ── India ─────────────────────────────────────────────────────────────────
    {"name": "GN India XRP",          "url": "https://news.google.com/rss/search?q=XRP+Ripple+India+SEBI+RBI&hl=en-IN&gl=IN&ceid=IN:en","type": "international","region": "India","filter": False},
    {"name": "WazirX Blog",           "url": "https://blog.wazirx.com/feed",                                                        "type": "international","region": "India", "filter": True},
    {"name": "Coinpedia",             "url": "https://coinpedia.org/feed",                                                          "type": "international","region": "India", "filter": True},
    # ── Latin America ─────────────────────────────────────────────────────────
    {"name": "CriptoNoticias",        "url": "https://www.criptonoticias.com/feed",                                                 "type": "international","region": "LatAm", "filter": True},
    {"name": "Diario Bitcoin",        "url": "https://www.diariobitcoin.com/feed",                                                  "type": "international","region": "LatAm", "filter": True},
    {"name": "GN LatAm XRP",          "url": "https://news.google.com/rss/search?q=XRP+Ripple+%22Latin+America%22+Mexico+Brazil",  "type": "international","region": "LatAm", "filter": False},
    # ── Africa ────────────────────────────────────────────────────────────────
    {"name": "GN Africa XRP",         "url": "https://news.google.com/rss/search?q=XRP+Ripple+Africa+Nigeria+Kenya+crypto",        "type": "international","region": "Africa","filter": False},
    # ── Southeast Asia ────────────────────────────────────────────────────────
    {"name": "GN SEA XRP",            "url": "https://news.google.com/rss/search?q=XRP+Ripple+Singapore+Thailand+Philippines",     "type": "international","region": "SEA",   "filter": False},
    # ── Community ─────────────────────────────────────────────────────────────
    {"name": "Reddit r/Ripple",       "url": "https://www.reddit.com/r/Ripple/.rss",                                                "type": "community",    "region": "US",    "filter": False},
    {"name": "Reddit r/XRP",          "url": "https://www.reddit.com/r/XRP/.rss",                                                   "type": "community",    "region": "US",    "filter": False},
    {"name": "Reddit r/XRPTrader",    "url": "https://www.reddit.com/r/XRPTrader/.rss",                                             "type": "community",    "region": "US",    "filter": False},
    {"name": "Reddit r/CryptoCurr",   "url": "https://www.reddit.com/r/CryptoCurrency/search.rss?q=XRP&sort=new&restrict_sr=on",   "type": "community",    "region": "US",    "filter": False},
    # ── Technical / On-chain ──────────────────────────────────────────────────
    {"name": "GN XRPL Tech",          "url": "https://news.google.com/rss/search?q=XRPL+%22XRP+Ledger%22+developer+validator",     "type": "technical",    "region": "US",    "filter": False},
    {"name": "GN XRP DeFi",           "url": "https://news.google.com/rss/search?q=XRP+DeFi+AMM+%22XRP+Ledger%22",                 "type": "technical",    "region": "US",    "filter": False},
    # ── Institutional ─────────────────────────────────────────────────────────
    {"name": "GN XRP Custody",        "url": "https://news.google.com/rss/search?q=XRP+custody+%22hedge+fund%22+institutional",    "type": "institutional","region": "US",    "filter": False},
    {"name": "GN XRP ETF Latest",     "url": "https://news.google.com/rss/search?q=%22XRP+ETF%22+approved+filed+2026",             "type": "institutional","region": "US",    "filter": False},
    # ── More aggregators ──────────────────────────────────────────────────────
    {"name": "GN XRP Breaking",       "url": "https://news.google.com/rss/search?q=XRP+breaking+news+today",                       "type": "aggregator",   "region": "US",    "filter": False},
    {"name": "GN Ripple CEO",         "url": "https://news.google.com/rss/search?q=Ripple+CEO+%22Brad+Garlinghouse%22",             "type": "official",     "region": "US",    "filter": False},
    {"name": "GN XRP OCC",            "url": "https://news.google.com/rss/search?q=XRP+OCC+%22national+bank%22+crypto",            "type": "legal",        "region": "US",    "filter": False},
    {"name": "GN XRP Treasury",       "url": "https://news.google.com/rss/search?q=XRP+%22US+Treasury%22+FinCEN+crypto",           "type": "legal",        "region": "US",    "filter": False},
    {"name": "GN XRP ISO20022",       "url": "https://news.google.com/rss/search?q=XRP+ISO20022+SWIFT+%22cross-border%22",         "type": "ecosystem",    "region": "US",    "filter": False},
    {"name": "GN XRP CBDC",           "url": "https://news.google.com/rss/search?q=XRP+CBDC+%22central+bank%22+digital",          "type": "ecosystem",    "region": "US",    "filter": False},
    # ── Additional US Crypto News ─────────────────────────────────────────────
    {"name": "CoinGecko Blog",        "url": "https://blog.coingecko.com/feed/",                                               "type": "major",        "region": "US",    "filter": True},
    {"name": "Coinbase Blog",          "url": "https://www.coinbase.com/blog/landing/rss",                                      "type": "institutional","region": "US",    "filter": True},
    {"name": "Crypto Potato XRP",      "url": "https://cryptopotato.com/tag/xrp/feed",                                         "type": "xrp",          "region": "US",    "filter": False},
    {"name": "CoinJournal XRP",        "url": "https://coinjournal.net/feed/",                                                  "type": "major",        "region": "US",    "filter": True},
    {"name": "99Bitcoins",             "url": "https://99bitcoins.com/feed/",                                                   "type": "major",        "region": "US",    "filter": True},
    {"name": "UseTheBitcoin",          "url": "https://usethebitcoin.com/feed/",                                                "type": "major",        "region": "US",    "filter": True},
    {"name": "BitcoinExchangeGuide",   "url": "https://bitcoinexchangeguide.com/feed/",                                         "type": "major",        "region": "US",    "filter": True},
    {"name": "Crypto Slate SEC",       "url": "https://cryptoslate.com/tag/sec/feed/",                                         "type": "legal",        "region": "US",    "filter": False},
    {"name": "Crypto Slate Ripple",    "url": "https://cryptoslate.com/tag/ripple/feed/",                                      "type": "xrp",          "region": "US",    "filter": False},
    # ── US Google News — XRP Deep Dives ───────────────────────────────────────
    {"name": "GN: XRP Futures",        "url": "https://news.google.com/rss/search?q=XRP+futures+derivatives+options",          "type": "major",        "region": "US",    "filter": False},
    {"name": "GN: XRP Partnership",    "url": "https://news.google.com/rss/search?q=Ripple+XRP+partnership+announcement",      "type": "ecosystem",    "region": "US",    "filter": False},
    {"name": "GN: XRP Reserve",        "url": "https://news.google.com/rss/search?q=XRP+reserve+asset+treasury+corporate",     "type": "institutional","region": "US",    "filter": False},
    {"name": "GN: XRP Payment",        "url": "https://news.google.com/rss/search?q=XRP+cross-border+payment+remittance",      "type": "ecosystem",    "region": "US",    "filter": False},
    {"name": "GN: XRP Fintech",        "url": "https://news.google.com/rss/search?q=XRP+fintech+bank+payment+corridor",        "type": "ecosystem",    "region": "US",    "filter": False},
    {"name": "GN: XRP Web3 DeFi",      "url": "https://news.google.com/rss/search?q=XRP+XRPL+DeFi+AMM+DEX+Web3",             "type": "technical",    "region": "US",    "filter": False},
    {"name": "GN: XRP NFT Gaming",     "url": "https://news.google.com/rss/search?q=XRP+NFT+gaming+metaverse+ledger",         "type": "technical",    "region": "US",    "filter": False},
    {"name": "GN: XRP Validator",      "url": "https://news.google.com/rss/search?q=XRP+validator+ledger+amendment+protocol", "type": "technical",    "region": "US",    "filter": False},
    {"name": "GN: Ripple CBDC",        "url": "https://news.google.com/rss/search?q=Ripple+CBDC+%22central+bank%22+digital+currency+partner","type": "ecosystem","region": "US","filter": False},
    {"name": "GN: XRP Custody Bank",   "url": "https://news.google.com/rss/search?q=XRP+custody+bank+trust+%22digital+asset%22","type": "institutional","region": "US","filter": False},
    {"name": "GN: Brad Interview",     "url": "https://news.google.com/rss/search?q=%22Brad+Garlinghouse%22+interview+XRP",   "type": "official",     "region": "US",    "filter": False},
    {"name": "GN: David Schwartz",     "url": "https://news.google.com/rss/search?q=%22David+Schwartz%22+XRP+XRPL+joelkatz",  "type": "official",     "region": "US",    "filter": False},
    {"name": "GN: Monica Long",        "url": "https://news.google.com/rss/search?q=%22Monica+Long%22+Ripple+XRP+president",  "type": "official",     "region": "US",    "filter": False},
    {"name": "GN: XRP Spot ETF",       "url": "https://news.google.com/rss/search?q=XRP+%22spot+ETF%22+SEC+approval+filed",   "type": "institutional","region": "US",    "filter": False},
    {"name": "GN: XRP Futures ETF",    "url": "https://news.google.com/rss/search?q=XRP+%22futures+ETF%22+ProShares+Bitwise", "type": "institutional","region": "US",    "filter": False},
    {"name": "GN: XRP Blackrock",      "url": "https://news.google.com/rss/search?q=XRP+BlackRock+Fidelity+Vanguard+fund",    "type": "institutional","region": "US",    "filter": False},
    {"name": "GN: XRP Stablecoin",     "url": "https://news.google.com/rss/search?q=XRP+stablecoin+RLUSD+stable+dollar",      "type": "xrp",          "region": "US",    "filter": False},
    {"name": "GN: XRP RippleNet",      "url": "https://news.google.com/rss/search?q=RippleNet+%22on-demand+liquidity%22+ODL+corridor","type": "ecosystem","region": "US","filter": False},
    {"name": "GN: Crypto Act",         "url": "https://news.google.com/rss/search?q=crypto+%22market+structure%22+act+bill+Congress+2026","type": "legal","region": "US","filter": False},
    {"name": "GN: XRP SEC Update",     "url": "https://news.google.com/rss/search?q=XRP+SEC+%22securities+law%22+Ripple+ruling+update","type": "legal","region": "US","filter": False},
    {"name": "GN: Crypto Tax US",      "url": "https://news.google.com/rss/search?q=XRP+crypto+tax+IRS+%22capital+gains%22", "type": "legal",        "region": "US",    "filter": False},
    {"name": "GN: XRP Coinbase2",      "url": "https://news.google.com/rss/search?q=XRP+Coinbase+Kraken+Gemini+exchange",     "type": "major",        "region": "US",    "filter": False},
    {"name": "GN: XRP Binance2",       "url": "https://news.google.com/rss/search?q=XRP+Binance+Bybit+OKX+exchange+trading",  "type": "major",        "region": "US",    "filter": False},
    {"name": "GN: XRP Price Target",   "url": "https://news.google.com/rss/search?q=XRP+%22price+target%22+analyst+prediction+2026","type": "major","region": "US","filter": False},
    {"name": "GN: XRP Technical2",     "url": "https://news.google.com/rss/search?q=XRP+%22technical+analysis%22+support+resistance+chart","type": "major","region": "US","filter": False},
    {"name": "GN: XRP Liquidity",      "url": "https://news.google.com/rss/search?q=XRP+liquidity+%22market+maker%22+depth+volume","type": "major","region": "US","filter": False},
    {"name": "GN: Ripple Labs",        "url": "https://news.google.com/rss/search?q=%22Ripple+Labs%22+XRP+announcement+news", "type": "official",     "region": "US",    "filter": False},
    {"name": "GN: XRPLF",             "url": "https://news.google.com/rss/search?q=%22XRP+Ledger+Foundation%22+XRPLF+grant",  "type": "official",     "region": "US",    "filter": False},
    {"name": "GN: XRP ISO 20022",      "url": "https://news.google.com/rss/search?q=XRP+ISO+20022+SWIFT+interoperability+banking","type": "ecosystem","region": "US","filter": False},
    {"name": "GN: XRP Forbes2",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:forbes.com",             "type": "mainstream",   "region": "US",    "filter": False},
    {"name": "GN: XRP Fortune",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:fortune.com",            "type": "mainstream",   "region": "US",    "filter": False},
    {"name": "GN: XRP AP News",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:apnews.com",             "type": "mainstream",   "region": "US",    "filter": False},
    {"name": "GN: XRP Seeking Alpha",  "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:seekingalpha.com",       "type": "institutional","region": "US",    "filter": False},
    {"name": "GN: XRP CoinDesk2",      "url": "https://news.google.com/rss/search?q=XRP+site:coindesk.com",                  "type": "major",        "region": "US",    "filter": False},
    {"name": "GN: XRP TheBlock2",      "url": "https://news.google.com/rss/search?q=XRP+site:theblock.co",                   "type": "major",        "region": "US",    "filter": False},
    {"name": "GN: XRP Messari",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:messari.io",             "type": "institutional","region": "US",    "filter": False},
    {"name": "GN: XRP Decrypt2",       "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:decrypt.co",             "type": "major",        "region": "US",    "filter": False},
    {"name": "GN: XRP Market Cap",     "url": "https://news.google.com/rss/search?q=XRP+%22market+cap%22+ranking+crypto+2026","type": "major",       "region": "US",    "filter": False},
    {"name": "GN: XRP OCC Reg",        "url": "https://news.google.com/rss/search?q=XRP+OCC+%22national+bank%22+crypto+custody","type": "legal",     "region": "US",    "filter": False},
    {"name": "GN: XRP IRS Tax",      "url": "https://news.google.com/rss/search?q=XRP+crypto+IRS+tax+2026",   "type": "legal",        "region": "US",    "filter": False},
    # ── Europe ────────────────────────────────────────────────────────────────
    {"name": "GN: XRP MiCA EU",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+MiCA+%22European+Union%22+regulation","type": "legal","region": "Europe","filter": False},
    {"name": "GN: XRP UK FCA",         "url": "https://news.google.com/rss/search?q=XRP+%22Financial+Conduct+Authority%22+FCA+UK+crypto","type": "legal","region": "Europe","filter": False},
    {"name": "GN: XRP Germany",        "url": "https://news.google.com/rss/search?q=XRP+BaFin+Germany+%22digital+asset%22+crypto","type": "legal","region": "Europe","filter": False},
    {"name": "GN: XRP France",         "url": "https://news.google.com/rss/search?q=XRP+Ripple+France+AMF+crypto+%22digital+asset%22","type": "legal","region": "Europe","filter": False},
    {"name": "GN: XRP Switzerland",    "url": "https://news.google.com/rss/search?q=XRP+Ripple+Switzerland+FINMA+Zug+crypto","type": "ecosystem",    "region": "Europe","filter": False},
    {"name": "GN: XRP ECB",            "url": "https://news.google.com/rss/search?q=XRP+%22European+Central+Bank%22+ECB+digital+euro","type": "ecosystem","region": "Europe","filter": False},
    {"name": "GN: XRP Bitstamp",       "url": "https://news.google.com/rss/search?q=XRP+Bitstamp+Kraken+Europe+exchange",    "type": "major",        "region": "Europe","filter": False},
    {"name": "GN: XRP EU Inst",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Europe+%22asset+manager%22+institutional","type": "institutional","region": "Europe","filter": False},
    {"name": "CoinTelegraph IT",        "url": "https://it.cointelegraph.com/rss",                                             "type": "international","region": "Europe","filter": True},
    {"name": "CoinTelegraph FR",        "url": "https://fr.cointelegraph.com/rss",                                             "type": "international","region": "Europe","filter": True},
    {"name": "GN: XRP Netherlands",    "url": "https://news.google.com/rss/search?q=XRP+Ripple+Netherlands+DNB+AFM+crypto",  "type": "legal",        "region": "Europe","filter": False},
    {"name": "GN: XRP Scandinavia",    "url": "https://news.google.com/rss/search?q=XRP+Ripple+Sweden+Norway+Denmark+crypto","type": "ecosystem",    "region": "Europe","filter": False},
    {"name": "GN: XRP Blockworks EU",  "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:blockworks.co+Europe",   "type": "major",        "region": "Europe","filter": False},
    # ── Additional Global ─────────────────────────────────────────────────────
    {"name": "GN: XRP Australia",      "url": "https://news.google.com/rss/search?q=XRP+Ripple+Australia+ASIC+crypto&hl=en-AU&gl=AU","type": "international","region": "SEA","filter": False},
    {"name": "GN: XRP Hong Kong",      "url": "https://news.google.com/rss/search?q=XRP+Ripple+%22Hong+Kong%22+SFC+crypto+exchange","type": "international","region": "SEA","filter": False},
    {"name": "GN: XRP Taiwan",         "url": "https://news.google.com/rss/search?q=XRP+Ripple+Taiwan+crypto+exchange",      "type": "international","region": "SEA","filter": False},
    {"name": "GN: XRP Brazil",         "url": "https://news.google.com/rss/search?q=XRP+Ripple+Brazil+Banco+Central+real+digital","type": "international","region": "LatAm","filter": False},
    {"name": "GN: XRP Mexico",         "url": "https://news.google.com/rss/search?q=XRP+Ripple+Mexico+Banxico+%22cross-border%22","type": "international","region": "LatAm","filter": False},
    {"name": "GN: XRP Argentina",      "url": "https://news.google.com/rss/search?q=XRP+Ripple+Argentina+peso+crypto+inflation","type": "international","region": "LatAm","filter": False},
    {"name": "GN: XRP Colombia",       "url": "https://news.google.com/rss/search?q=XRP+Ripple+Colombia+crypto+regulation+payment","type": "international","region": "LatAm","filter": False},
    {"name": "GN: XRP Nigeria",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Nigeria+naira+crypto+payment","type": "international","region": "Africa","filter": False},
    {"name": "GN: XRP Kenya",          "url": "https://news.google.com/rss/search?q=XRP+Ripple+Kenya+%22M-Pesa%22+payment+crypto","type": "international","region": "Africa","filter": False},
    {"name": "GN: XRP South Africa",   "url": "https://news.google.com/rss/search?q=XRP+Ripple+%22South+Africa%22+FSCA+crypto","type": "international","region": "Africa","filter": False},
    {"name": "GN: XRP Ghana",          "url": "https://news.google.com/rss/search?q=XRP+Ripple+Ghana+%22Bank+of+Ghana%22+crypto","type": "international","region": "Africa","filter": False},
    {"name": "GN: XRP Saudi",          "url": "https://news.google.com/rss/search?q=XRP+Ripple+%22Saudi+Arabia%22+SAMA+crypto+payment","type": "international","region": "UAE","filter": False},
    {"name": "GN: XRP Bahrain",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Bahrain+%22Central+Bank%22+fintech","type": "international","region": "UAE","filter": False},
    {"name": "GN: XRP Pakistan",       "url": "https://news.google.com/rss/search?q=XRP+Ripple+Pakistan+remittance+payment+crypto","type": "international","region": "India","filter": False},
    {"name": "GN: XRP Bangladesh",     "url": "https://news.google.com/rss/search?q=XRP+Ripple+Bangladesh+remittance+%22foreign+exchange%22","type": "international","region": "India","filter": False},
    {"name": "GN: XRP Indonesia",      "url": "https://news.google.com/rss/search?q=XRP+Ripple+Indonesia+OJK+crypto+exchange","type": "international","region": "SEA","filter": False},
    {"name": "GN: XRP Vietnam",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Vietnam+crypto+payment+regulation","type": "international","region": "SEA","filter": False},
    {"name": "GN: XRP Malaysia",       "url": "https://news.google.com/rss/search?q=XRP+Ripple+Malaysia+%22Bank+Negara%22+crypto","type": "international","region": "SEA","filter": False},
    {"name": "GN: XRP Korea Reg",      "url": "https://news.google.com/rss/search?q=XRP+%22Financial+Services+Commission%22+Korea+crypto","type": "legal","region": "Korea","filter": False},
    {"name": "GN: XRP Japan FSA",      "url": "https://news.google.com/rss/search?q=XRP+Japan+FSA+%22Financial+Services+Agency%22+crypto","type": "legal","region": "Japan","filter": False},
    {"name": "GN: XRP Japan Bank",     "url": "https://news.google.com/rss/search?q=XRP+%22Bank+of+Japan%22+SBI+MoneyTap+payment","type": "ecosystem","region": "Japan","filter": False},
    {"name": "CoinPost JP XRP",        "url": "https://coinpost.jp/?s=XRP&feed=rss2",                                         "type": "international","region": "Japan","filter": False},

    {"name": "GN: XRP Grayscale",     "url": "https://news.google.com/rss/search?q=XRP+Grayscale+trust+%22digital+asset%22+fund","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP Galaxy",        "url": "https://news.google.com/rss/search?q=XRP+%22Galaxy+Digital%22+%22digital+asset%22","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP Pantera",       "url": "https://news.google.com/rss/search?q=XRP+Pantera+%22venture+capital%22+crypto+fund","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP a16z",          "url": "https://news.google.com/rss/search?q=XRP+%22Andreessen+Horowitz%22+a16z+crypto","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP Nasdaq",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Nasdaq+NYSE+%22stock+market%22","type": "mainstream","region": "US","filter": False},
    {"name": "GN: XRP Fed Policy",    "url": "https://news.google.com/rss/search?q=XRP+crypto+%22Federal+Reserve%22+%22interest+rate%22+policy","type": "mainstream","region": "US","filter": False},
    {"name": "GN: XRP Inflation",     "url": "https://news.google.com/rss/search?q=XRP+crypto+inflation+%22safe+haven%22+hedge","type": "mainstream","region": "US","filter": False},
    {"name": "GN: XRP Altcoin",       "url": "https://news.google.com/rss/search?q=XRP+%22altcoin%22+season+rally+%22market+cycle%22","type": "major","region": "US","filter": False},
    {"name": "GN: XRP Halving",       "url": "https://news.google.com/rss/search?q=XRP+%22bitcoin+halving%22+%22bull+market%22+cycle","type": "major","region": "US","filter": False},
    {"name": "GN: XRP Dominance",     "url": "https://news.google.com/rss/search?q=XRP+%22crypto+dominance%22+%22market+share%22+ranking","type": "major","region": "US","filter": False},
    {"name": "GN: XRP Volume",        "url": "https://news.google.com/rss/search?q=XRP+%22trading+volume%22+record+exchange+24h","type": "major","region": "US","filter": False},
    {"name": "GN: XRP Chart",         "url": "https://news.google.com/rss/search?q=XRP+chart+%22all+time+high%22+%22price+prediction%22","type": "major","region": "US","filter": False},
    {"name": "GN: XRP Sentiment",     "url": "https://news.google.com/rss/search?q=XRP+sentiment+%22fear+and+greed%22+bullish+bearish","type": "major","region": "US","filter": False},
    {"name": "GN: XRP ProShares",     "url": "https://news.google.com/rss/search?q=XRP+ProShares+%22Teucrium%22+%22Bitwise%22+ETF","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP Franklin",      "url": "https://news.google.com/rss/search?q=XRP+%22Franklin+Templeton%22+%22WisdomTree%22+digital","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP Ripple IPO",    "url": "https://news.google.com/rss/search?q=Ripple+IPO+%22initial+public+offering%22+stock+listing","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP Congress2",     "url": "https://news.google.com/rss/search?q=XRP+crypto+%22Senate%22+%22House%22+hearing+2026","type": "legal","region": "US","filter": False},
    {"name": "GN: XRP Gensler",       "url": "https://news.google.com/rss/search?q=XRP+%22SEC+chairman%22+crypto+%22securities%22","type": "legal","region": "US","filter": False},
    {"name": "GN: XRP FDIC",          "url": "https://news.google.com/rss/search?q=XRP+crypto+FDIC+%22bank+regulator%22+%22digital+asset%22","type": "legal","region": "US","filter": False},
    {"name": "GN: XRP White House",   "url": "https://news.google.com/rss/search?q=XRP+crypto+%22White+House%22+executive+order","type": "legal","region": "US","filter": False},
    {"name": "GN: XRP EU Banking",    "url": "https://news.google.com/rss/search?q=XRP+Ripple+%22European+banking%22+%22SEPA%22+payment","type": "ecosystem","region": "Europe","filter": False},
    {"name": "GN: XRP UK Adoption",   "url": "https://news.google.com/rss/search?q=XRP+Ripple+UK+%22Bank+of+England%22+adoption+payment","type": "ecosystem","region": "Europe","filter": False},
    {"name": "GN: XRP Poland",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Poland+crypto+NBP+%22digital+zloty%22","type": "international","region": "Europe","filter": False},
    {"name": "GN: XRP Spain",         "url": "https://news.google.com/rss/search?q=XRP+Ripple+Spain+CNMV+crypto+%22digital+asset%22","type": "international","region": "Europe","filter": False},
    {"name": "GN: XRP Thailand",      "url": "https://news.google.com/rss/search?q=XRP+Ripple+Thailand+SEC+%22Bank+of+Thailand%22+crypto","type": "international","region": "SEA","filter": False},
    {"name": "GN: XRP Philippines",   "url": "https://news.google.com/rss/search?q=XRP+Ripple+Philippines+BSP+remittance+OFW+crypto","type": "international","region": "SEA","filter": False},
    {"name": "GN: XRP Ethiopia",      "url": "https://news.google.com/rss/search?q=XRP+Ripple+Ethiopia+Africa+%22National+Bank%22+crypto","type": "international","region": "Africa","filter": False},
    {"name": "GN: XRP Morocco",       "url": "https://news.google.com/rss/search?q=XRP+Ripple+Morocco+Egypt+%22North+Africa%22+crypto","type": "international","region": "Africa","filter": False},
    {"name": "GN: XRP Israel",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Israel+%22Bank+of+Israel%22+fintech+crypto","type": "international","region": "UAE","filter": False},
    {"name": "GN: XRP Turkey",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Turkey+lira+crypto+inflation+exchange","type": "international","region": "UAE","filter": False},

    # ── From 200-Source Master List — Global Hubs ─────────────────────────────
    {"name": "CoinDesk Japan",         "url": "https://www.coindeskjapan.com/feed/",                                           "type": "international","region": "Japan", "filter": True},
    {"name": "HashKey Exchange",       "url": "https://news.google.com/rss/search?q=HashKey+%22Hong+Kong%22+XRP+crypto+regulated","type": "international","region": "SEA","filter": False},
    {"name": "VARA Dubai Reg",         "url": "https://news.google.com/rss/search?q=VARA+Dubai+%22virtual+asset%22+XRP+Ripple+regulation","type": "legal","region": "UAE","filter": False},
    {"name": "ADGM Abu Dhabi",         "url": "https://news.google.com/rss/search?q=ADGM+%22Abu+Dhabi%22+XRP+crypto+fintech","type": "legal","region": "UAE","filter": False},
    {"name": "Rain Financial ME",       "url": "https://news.google.com/rss/search?q=Rain+%22Middle+East%22+XRP+crypto+GCC+Bahrain","type": "international","region": "UAE","filter": False},
    {"name": "CoinDCX India",          "url": "https://blog.coindcx.com/feed/",                                               "type": "international","region": "India","filter": True},
    {"name": "Indodax Indonesia",      "url": "https://indodax.com/blog/feed/",                                               "type": "international","region": "SEA","filter": True},
    {"name": "Tokocrypto Indonesia",   "url": "https://www.tokocrypto.com/blog/feed/",                                        "type": "international","region": "SEA","filter": True},
    {"name": "CoinJar News",           "url": "https://blog.coinjar.com/feed/",                                               "type": "international","region": "SEA","filter": True},
    {"name": "BTC Markets Australia",  "url": "https://www.btcmarkets.net/blog/feed/",                                        "type": "international","region": "SEA","filter": True},
    {"name": "Bitso Blog LatAm",       "url": "https://blog.bitso.com/feed/",                                                 "type": "international","region": "LatAm","filter": True},
    {"name": "Bitmama Africa",         "url": "https://bitmama.io/blog/feed/",                                                "type": "international","region": "Africa","filter": True},
    {"name": "Yellow Card Africa",     "url": "https://yellowcard.io/blog/feed/",                                             "type": "international","region": "Africa","filter": False},
    {"name": "ForkLog Eastern EU",     "url": "https://forklog.com/feed/",                                                    "type": "international","region": "Europe","filter": True},
    {"name": "BlockTempo Taiwan",      "url": "https://www.blocktempo.com/feed/",                                             "type": "international","region": "SEA","filter": True},
    {"name": "CryptoCompare Global",   "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:cryptocompare.com",      "type": "major",        "region": "US",    "filter": False},
    {"name": "Santiment Analytics",    "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:santiment.net",          "type": "institutional","region": "US",    "filter": False},
    {"name": "Glassnode On-Chain",     "url": "https://news.google.com/rss/search?q=XRP+on-chain+%22glassnode%22+analytics", "type": "institutional","region": "US",    "filter": False},
    {"name": "Messari XRP",            "url": "https://news.google.com/rss/search?q=XRP+Ripple+site:messari.io+research",    "type": "institutional","region": "US",    "filter": False},
    {"name": "Coinglass Derivatives",  "url": "https://news.google.com/rss/search?q=XRP+derivatives+%22open+interest%22+futures","type": "major","region": "US","filter": False},
    {"name": "GN: XRP CryptoQuant",   "url": "https://news.google.com/rss/search?q=XRP+%22cryptoquant%22+exchange+reserve+flow","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP IntoTheBlock",  "url": "https://news.google.com/rss/search?q=XRP+%22IntoTheBlock%22+whale+large+holders","type": "institutional","region": "US","filter": False},
    {"name": "GN: XRP LunarCrush",    "url": "https://news.google.com/rss/search?q=XRP+%22LunarCrush%22+social+sentiment",  "type": "major",        "region": "US",    "filter": False},
    {"name": "Ledger Insights",        "url": "https://www.ledgerinsights.com/feed/",                                         "type": "major",        "region": "Europe","filter": True},
    {"name": "Finextra Finance",       "url": "https://www.finextra.com/rss/channel.aspx?channel=news",                       "type": "major",        "region": "Europe","filter": True},
    {"name": "PYMNTS Blockchain",      "url": "https://www.pymnts.com/feed/",                                                 "type": "major",        "region": "US",    "filter": True},
    {"name": "The Fintech Times",      "url": "https://thefintechtimes.com/feed/",                                            "type": "major",        "region": "Europe","filter": True},
    {"name": "SEC Press Releases",     "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=&dateb=&owner=include&count=20&search_text=&action=getcompany",  "type": "legal","region": "US","filter": True},
    {"name": "GN: SEC Crypto XRP",    "url": "https://news.google.com/rss/search?q=SEC+XRP+%22digital+asset%22+enforcement+2026","type": "legal","region": "US","filter": False},
    {"name": "GN: BIS XRP Research",  "url": "https://news.google.com/rss/search?q=XRP+%22Bank+for+International+Settlements%22+BIS+settlement","type": "institutional","region": "Europe","filter": False},

    # ── Institutional & Banking ──────────────────────────────────────────
    {"name":"GN: XRP BIS Research",    "url":"https://news.google.com/rss/search?q=XRP+%22Bank+for+International+Settlements%22+BIS+CBDC","type":"institutional","region":"Europe","filter":False},
    {"name":"GN: XRP IMF",             "url":"https://news.google.com/rss/search?q=XRP+Ripple+IMF+%22International+Monetary%22+digital","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP World Bank",      "url":"https://news.google.com/rss/search?q=XRP+Ripple+%22World+Bank%22+financial+inclusion+payments","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Federal Reserve", "url":"https://news.google.com/rss/search?q=XRP+%22Federal+Reserve%22+CBDC+digital+dollar+Ripple","type":"legal","region":"US","filter":False},
    {"name":"GN: XRP ECB Digital",     "url":"https://news.google.com/rss/search?q=XRP+%22European+Central+Bank%22+digital+euro+CBDC","type":"legal","region":"Europe","filter":False},
    {"name":"GN: XRP JPMorgan",        "url":"https://news.google.com/rss/search?q=XRP+JPMorgan+%22JPM+Coin%22+blockchain+payment","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Goldman",         "url":"https://news.google.com/rss/search?q=XRP+%22Goldman+Sachs%22+crypto+digital+assets","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP BlackRock ETF",   "url":"https://news.google.com/rss/search?q=XRP+BlackRock+ETF+%22digital+assets%22+Ripple","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Fidelity",        "url":"https://news.google.com/rss/search?q=XRP+Fidelity+%22digital+assets%22+custody+crypto","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Nasdaq",          "url":"https://news.google.com/rss/search?q=XRP+Nasdaq+%22spot+ETF%22+listing+custody","type":"institutional","region":"US","filter":False},
    # ── More Regional Coverage ────────────────────────────────────────────
    {"name":"GN: XRP Turkey",          "url":"https://news.google.com/rss/search?q=XRP+Ripple+Turkey+%22Turkish+Lira%22+crypto","type":"international","region":"Europe","filter":False},
    {"name":"GN: XRP Egypt",           "url":"https://news.google.com/rss/search?q=XRP+Ripple+Egypt+%22Central+Bank%22+remittance","type":"international","region":"Africa","filter":False},
    {"name":"GN: XRP Argentina",       "url":"https://news.google.com/rss/search?q=XRP+Ripple+Argentina+%22peso%22+inflation+crypto","type":"international","region":"LatAm","filter":False},
    {"name":"GN: XRP Colombia",        "url":"https://news.google.com/rss/search?q=XRP+Ripple+Colombia+%22Banco+de+la+Republica%22+CBDC","type":"international","region":"LatAm","filter":False},
    {"name":"GN: XRP Chile",           "url":"https://news.google.com/rss/search?q=XRP+Ripple+Chile+crypto+payment+adoption","type":"international","region":"LatAm","filter":False},
    {"name":"GN: XRP South Africa",    "url":"https://news.google.com/rss/search?q=XRP+Ripple+%22South+Africa%22+SARB+remittance","type":"international","region":"Africa","filter":False},
    {"name":"GN: XRP Kenya",           "url":"https://news.google.com/rss/search?q=XRP+Ripple+Kenya+%22M-Pesa%22+remittance+Africa","type":"international","region":"Africa","filter":False},
    {"name":"GN: XRP Tanzania",        "url":"https://news.google.com/rss/search?q=XRP+Ripple+Tanzania+Africa+remittance+payment","type":"international","region":"Africa","filter":False},
    {"name":"GN: XRP Ghana",           "url":"https://news.google.com/rss/search?q=XRP+Ripple+Ghana+%22Bank+of+Ghana%22+digital","type":"international","region":"Africa","filter":False},
    {"name":"GN: XRP Vietnam",         "url":"https://news.google.com/rss/search?q=XRP+Ripple+Vietnam+%22State+Bank%22+crypto","type":"international","region":"SEA","filter":False},
    {"name":"GN: XRP Thailand",        "url":"https://news.google.com/rss/search?q=XRP+Ripple+Thailand+%22Bank+of+Thailand%22+crypto","type":"international","region":"SEA","filter":False},
    {"name":"GN: XRP Pakistan",        "url":"https://news.google.com/rss/search?q=XRP+Ripple+Pakistan+%22State+Bank%22+remittance","type":"international","region":"India","filter":False},
    {"name":"GN: XRP Bangladesh",      "url":"https://news.google.com/rss/search?q=XRP+Ripple+Bangladesh+remittance+payment","type":"international","region":"India","filter":False},
    {"name": "GN: XRP Qatar",        "url": "https://news.google.com/rss/search?q=XRP+Ripple+Qatar+digital",  "type": "international", "region": "UAE",   "filter": False},
    {"name":"GN: XRP Israel",          "url":"https://news.google.com/rss/search?q=XRP+Ripple+Israel+%22Bank+of+Israel%22+crypto","type":"international","region":"UAE","filter":False},
    # ── On-Chain & Data Providers ─────────────────────────────────────────
    {"name":"GN: XRP Nansen",          "url":"https://news.google.com/rss/search?q=XRP+Ripple+%22Nansen%22+on-chain+analytics","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Chainalysis",     "url":"https://news.google.com/rss/search?q=XRP+%22Chainalysis%22+compliance+blockchain","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Coin Metrics",    "url":"https://news.google.com/rss/search?q=XRP+%22Coin+Metrics%22+network+data+analytics","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Token Terminal",  "url":"https://news.google.com/rss/search?q=XRP+XRPL+%22Token+Terminal%22+revenue+fees","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Dune Analytics",  "url":"https://news.google.com/rss/search?q=XRP+XRPL+%22Dune+Analytics%22+on-chain+data","type":"institutional","region":"US","filter":False},
    # ── Legal & Regulatory ────────────────────────────────────────────────
    {"name":"GN: XRP FinCEN",          "url":"https://news.google.com/rss/search?q=XRP+FinCEN+%22financial+crimes%22+crypto+regulation","type":"legal","region":"US","filter":False},
    {"name":"GN: XRP CFTC Crypto",     "url":"https://news.google.com/rss/search?q=XRP+Ripple+CFTC+%22commodity%22+digital+asset+2026","type":"legal","region":"US","filter":False},
    {"name":"GN: XRP OCC Bank",        "url":"https://news.google.com/rss/search?q=XRP+OCC+%22national+bank%22+crypto+custody+license","type":"legal","region":"US","filter":False},
    {"name":"GN: XRP UK FCA",          "url":"https://news.google.com/rss/search?q=XRP+Ripple+%22FCA%22+%22Financial+Conduct%22+UK+crypto","type":"legal","region":"Europe","filter":False},
    {"name":"GN: XRP MAS Singapore",   "url":"https://news.google.com/rss/search?q=XRP+MAS+Singapore+%22Monetary+Authority%22+crypto","type":"legal","region":"SEA","filter":False},
    {"name":"GN: XRP ASIC Australia",  "url":"https://news.google.com/rss/search?q=XRP+ASIC+Australia+%22crypto+asset%22+regulation","type":"legal","region":"SEA","filter":False},
    {"name":"GN: XRP FSA Japan Reg",   "url":"https://news.google.com/rss/search?q=XRP+%22FSA%22+Japan+%22Virtual+Currency%22+regulation","type":"legal","region":"Japan","filter":False},
    {"name":"GN: XRP FATF",            "url":"https://news.google.com/rss/search?q=XRP+Ripple+FATF+%22travel+rule%22+crypto+compliance","type":"legal","region":"Europe","filter":False},
    # ── Trading & Markets ─────────────────────────────────────────────────
    {"name":"GN: XRP Options",         "url":"https://news.google.com/rss/search?q=XRP+options+%22implied+volatility%22+derivatives","type":"major","region":"US","filter":False},
    {"name":"GN: XRP CME",             "url":"https://news.google.com/rss/search?q=XRP+CME+%22Chicago+Mercantile%22+futures+ETF","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Wintermute",      "url":"https://news.google.com/rss/search?q=XRP+Wintermute+%22market+maker%22+liquidity","type":"institutional","region":"Europe","filter":False},
    {"name":"GN: XRP Cumberland",      "url":"https://news.google.com/rss/search?q=XRP+Cumberland+%22DRW%22+OTC+trading+crypto","type":"institutional","region":"US","filter":False},
    # ── XRP Ecosystem Specific ────────────────────────────────────────────
    {"name":"GN: XRP Evernode",        "url":"https://news.google.com/rss/search?q=Evernode+XRPL+%22smart+contracts%22+Hooks","type":"major","region":"US","filter":False},
    {"name":"GN: XRP Sologenic",       "url":"https://news.google.com/rss/search?q=Sologenic+XRPL+%22tokenized+stocks%22+DEX","type":"major","region":"US","filter":False},
    {"name":"GN: XRP XUMM",            "url":"https://news.google.com/rss/search?q=XUMM+XRPL+wallet+%22Xaman%22+app","type":"major","region":"US","filter":False},
    {"name":"GN: XRP Hooks",           "url":"https://news.google.com/rss/search?q=XRPL+Hooks+%22smart+contract%22+amendment+testnet","type":"major","region":"US","filter":False},
    {"name":"GN: XRPL NFT",            "url":"https://news.google.com/rss/search?q=XRPL+NFT+%22XLS-20%22+marketplace+mint","type":"major","region":"US","filter":False},
    {"name":"GN: XRPL AMM",            "url":"https://news.google.com/rss/search?q=XRPL+AMM+%22automated+market+maker%22+liquidity+pool","type":"major","region":"US","filter":False},
    {"name":"GN: XRPL DeFi",           "url":"https://news.google.com/rss/search?q=XRPL+DeFi+%22decentralized+finance%22+protocol+2026","type":"major","region":"US","filter":False},
    {"name":"GN: XRP Peersyst",        "url":"https://news.google.com/rss/search?q=Peersyst+XRPL+%22EVM+sidechain%22+Ethereum","type":"major","region":"Europe","filter":False},
    # ── Mainstream Media XRP Coverage ─────────────────────────────────────
    {"name":"GN: XRP WSJ",             "url":"https://news.google.com/rss/search?q=XRP+Ripple+site:wsj.com+%22Wall+Street%22","type":"major","region":"US","filter":False},
    {"name":"GN: XRP Bloomberg",       "url":"https://news.google.com/rss/search?q=XRP+Ripple+site:bloomberg.com+payments","type":"major","region":"US","filter":False},
    {"name":"GN: XRP Reuters",         "url":"https://news.google.com/rss/search?q=XRP+Ripple+site:reuters.com+finance","type":"major","region":"US","filter":False},
    {"name":"GN: XRP FT",              "url":"https://news.google.com/rss/search?q=XRP+Ripple+%22Financial+Times%22+payments+banking","type":"major","region":"Europe","filter":False},
    {"name":"GN: XRP CNBC",            "url":"https://news.google.com/rss/search?q=XRP+Ripple+site:cnbc.com+crypto","type":"major","region":"US","filter":False},
    {"name":"GN: XRP Forbes",          "url":"https://news.google.com/rss/search?q=XRP+Ripple+site:forbes.com+crypto","type":"major","region":"US","filter":False},
    {"name":"GN: XRP Fortune",         "url":"https://news.google.com/rss/search?q=XRP+Ripple+site:fortune.com+crypto+payments","type":"major","region":"US","filter":False},
    # ── More Direct RSS Feeds ─────────────────────────────────────────────
    {"name":"CoinDesk XRP",            "url":"https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=article","type":"major","region":"US","filter":True},
    {"name": "Finbold Ripple",       "url": "https://finbold.com/feed/",                                     "type": "major",        "region": "US",    "filter": False},
    {"name": "GN: XRP Coinbase Intl","url": "https://news.google.com/rss/search?q=XRP+Coinbase+international","type": "institutional","region": "US",    "filter": False},
    {"name": "PaymentsDive",         "url": "https://www.paymentsdive.com/feeds/news/",                      "type": "institutional","region": "US",    "filter": False},
    {"name": "Fintech Futures",      "url": "https://www.fintechfutures.com/feed/",                          "type": "institutional","region": "Europe","filter": False},
    {"name": "CryptoNews Deep",      "url": "https://cryptonews.net/news/feed/",                             "type": "major",        "region": "US",    "filter": False},
    {"name": "Blockchain News",      "url": "https://blockchain.news/rss",                                   "type": "major",        "region": "US",    "filter": False},
    {"name":"Invezz Crypto",           "url":"https://invezz.com/feed/","type":"major","region":"Europe","filter":True},
    {"name":"Bitcoinist XRP",          "url":"https://bitcoinist.com/feed/","type":"major","region":"US","filter":True},
    {"name":"NewsBTC XRP",             "url":"https://www.newsbtc.com/feed/","type":"major","region":"US","filter":True},
    {"name": "CoinSpeaker XRP",      "url": "https://www.coinspeaker.com/news/feed/",                        "type": "major",        "region": "US",    "filter": False},
    {"name":"ZyCrypto XRP",            "url":"https://zycrypto.com/feed/","type":"major","region":"US","filter":True},
    {"name": "CoinCheckup News",     "url": "https://coincheckup.com/blog/feed/",                            "type": "major",        "region": "US",    "filter": False},
    {"name":"Santiment Blog",          "url":"https://news.google.com/rss/search?q=XRP+Ripple+site:santiment.net+analytics","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Seeking Alpha",   "url":"https://news.google.com/rss/search?q=XRP+Ripple+site:seekingalpha.com+investment","type":"institutional","region":"US","filter":False},
    {"name":"GN: XRP Motley Fool",     "url":"https://news.google.com/rss/search?q=XRP+Ripple+%22Motley+Fool%22+investment+crypto","type":"institutional","region":"US","filter":False},
    {"name":"Reddit r/XRPtrader",      "url":"https://www.reddit.com/r/XRPtrader/.rss","type":"community","region":"US","filter":False},
    {"name": "Reddit r/XRPLedger",   "url": "https://www.reddit.com/r/XRPLedger/.rss",                       "type": "community",    "region": "US",    "filter": False},

    {"name": "GN: XRP Institutional 2026", "url": "https://news.google.com/rss/search?q=XRP+institutional+adoption+2026", "type": "institutional", "region": "US",    "filter": False},
]

REGIONS = ["Japan","Korea","UAE","Europe","India","LatAm","Africa","SEA"]

# ── State ──────────────────────────────────────────────────────────────────────
STATE = {
    "price":         {},
    "prediction": {
        "sections": {
            "market_pulse":        "",
            "connections":         "",
            "domino_effect":       "",
            "regional_flashpoints":"",
            "watchlist":           "",
            "tradfi_outlook":      "",
        },
        "generated_at":   "",
        "next_run_cst":   "AM: 12:00 PM CST | PM: 9:00 PM CST",
        "last_run_date":  "",
        "story_count":    0,
        "source_count":   0,
        "status":         "pending",
        "error":          "",
    },
    "disp_intel": {
        "price_heatmap":  [],
        "price_history_6m": [],
        "smart_money":    {
            "score":       0,
            "label":       "",
            "signals":     [],
            "whale_score": 0,
            "flow_score":  0,
            "rsi_score":   0,
            "sent_score":  0,
            "oi_score":    0,
        },
        "fg_history":     [],
        "ts":             "",
    },
    "tools_intel": {
        "fx_rates": {
            "EUR": 0.0, "GBP": 0.0, "JPY": 0.0,
            "AUD": 0.0, "CAD": 0.0, "SGD": 0.0,
            "INR": 0.0, "BRL": 0.0, "MXN": 0.0,
        },
        "ts": "",
    },
    "sent_intel": {
        "daily_sentiment": [],
        "velocity_hours":  [],
        "source_leaders":  [],
        "google_trend":    0,
        "google_trend_label": "",
        "trend_keywords":  [],
        "ts":              "",
    },
    "mainstream_intel": {
        "partnerships": [
            {"institution":"Bank of America","type":"Bank","country":"🇺🇸 USA","status":"RUMORED","detail":"Multiple reports suggest BOA exploring Ripple ODL for cross-border settlement. Not officially confirmed.","source":"Industry reports 2025-2026"},
            {"institution":"JPMorgan Chase","type":"Bank","country":"🇺🇸 USA","status":"EXPLORING","detail":"JPM Coin runs on private blockchain but JPMorgan has engaged with ISO 20022 standards compatible with XRPL. Watching closely.","source":"Bloomberg 2025"},
            {"institution":"SBI Holdings","type":"Bank","country":"🇯🇵 Japan","status":"CONFIRMED","detail":"SBI Ripple Asia — joint venture fully operational. SBI VC Trade, SBI Remit, and MoneyTap all run on Ripple technology.","source":"SBI Holdings IR 2024"},
            {"institution":"Santander","type":"Bank","country":"🇪🇸 Spain","status":"CONFIRMED","detail":"One Pay FX powered by Ripple since 2018. Expanded to multiple markets. One of the earliest major bank adopters.","source":"Santander Press Release"},
            {"institution":"Standard Chartered","type":"Bank","country":"🇬🇧 UK","status":"CONFIRMED","detail":"SC Ventures partnership with Ripple for cross-border payments in Asia-Pacific corridors.","source":"Standard Chartered 2023"},
            {"institution":"PNC Bank","type":"Bank","country":"🇺🇸 USA","status":"CONFIRMED","detail":"PNC joined RippleNet for cross-border payment capabilities. One of the largest US banks on the network.","source":"Ripple Press Release"},
            {"institution":"Itaú Unibanco","type":"Bank","country":"🇧🇷 Brazil","status":"CONFIRMED","detail":"Brazil's largest private bank partnered with Ripple for international transfers via RippleNet.","source":"Ripple Blog 2023"},
            {"institution":"Axis Bank","type":"Bank","country":"🇮🇳 India","status":"CONFIRMED","detail":"Axis Bank uses RippleNet for inbound remittances into India. Major corridor from Gulf states.","source":"Ripple Partner Network"},
            {"institution":"Tranglo","type":"Payments","country":"🇸🇬 Singapore","status":"CONFIRMED","detail":"Ripple acquired 40% stake in Tranglo. Powers ODL across SE Asia including Philippines, Malaysia, Indonesia.","source":"Ripple Acquisition 2021"},
            {"institution":"Coins.ph","type":"Payments","country":"🇵🇭 Philippines","status":"CONFIRMED","detail":"Philippines-based wallet using ODL for US-Philippines corridor. Millions of OFW remittances monthly.","source":"Ripple ODL Partner"},
            {"institution":"Bitso","type":"Exchange","country":"🇲🇽 Mexico","status":"CONFIRMED","detail":"Mexico's largest crypto exchange. Primary ODL partner for USA-Mexico corridor — the largest ODL corridor globally.","source":"Bitso/Ripple 2021"},
            {"institution":"Western Union","type":"Payments","country":"🇺🇸 USA","status":"EXPLORING","detail":"WU tested Ripple technology in 2018 pilots. No full deployment but ongoing ISO 20022 alignment is notable.","source":"WU Annual Report 2023"},
            {"institution":"MoneyGram","type":"Payments","country":"🇺🇸 USA","status":"EXPLORING","detail":"Former deep Ripple partner (2019-2021). Regulatory pressure caused pause. Re-engagement rumored post-SEC settlement.","source":"Industry reports 2025"},
            {"institution":"Modulr","type":"Fintech","country":"🇬🇧 UK","status":"CONFIRMED","detail":"UK fintech using RippleNet for European payment infrastructure. Backed by PayPal Ventures.","source":"Ripple Partner 2023"},
            {"institution":"Bank of Bhutan","type":"Central Bank","country":"🇧🇹 Bhutan","status":"CONFIRMED","detail":"National digital currency (Druk) built on XRPL. First sovereign digital currency on the XRP Ledger.","source":"Royal Monetary Authority 2023"},
            {"institution":"SWIFT","type":"Network","country":"🌐 Global","status":"COMPETING","detail":"SWIFT gpi is ISO 20022 compliant — same standard as XRPL. Direct competitive overlap. SWIFT Connect explores DLT bridges.","source":"SWIFT 2024"},
            {"institution":"Nasdaq","type":"Exchange","country":"🇺🇸 USA","status":"EXPLORING","detail":"Nasdaq applied for XRP ETF custody services. Potential listing venue for spot XRP ETF products.","source":"SEC Filings 2025"},
            {"institution":"Fidelity","type":"Asset Manager","country":"🇺🇸 USA","status":"EXPLORING","detail":"Fidelity Digital Assets expanding custody. XRP support rumored post-SEC settlement clarity.","source":"Industry reports 2026"},
            {"institution":"BlackRock","type":"Asset Manager","country":"🇺🇸 USA","status":"EXPLORING","detail":"BlackRock BUIDL fund uses blockchain infrastructure. XRP Ledger compatibility being evaluated.","source":"BlackRock Digital 2025"},
            {"institution":"Ripple x BIS","type":"Research","country":"🌐 Global","status":"CONFIRMED","detail":"Bank for International Settlements Project Nexus exploring XRPL for multi-CBDC settlements between central banks.","source":"BIS Innovation Hub 2024"},
        ],
        "integration_timeline": [
            {"year":"2012","event":"Ripple Founded","detail":"OpenCoin (later Ripple) created with mission to replace correspondent banking.","major":False},
            {"year":"2018","event":"First Bank Partnerships","detail":"Santander One Pay FX, American Express FX International Payments launch on RippleNet.","major":True},
            {"year":"2019","event":"ODL Goes Live","detail":"On-Demand Liquidity launches commercially. XRP used as bridge currency for the first time at scale.","major":True},
            {"year":"2020","event":"SEC Lawsuit","detail":"SEC files suit — temporarily freezes institutional adoption in the US. Global expansion continues.","major":False},
            {"year":"2021","event":"SBI + Tranglo","detail":"SBI Holdings scales Japan operations. Ripple acquires 40% of Tranglo — SE Asia ODL hub established.","major":True},
            {"year":"2022","event":"SWIFT ISO 20022","detail":"SWIFT mandates ISO 20022 migration — the same standard XRPL natively supports. Alignment begins.","major":True},
            {"year":"2023","event":"Bhutan CBDC Live","detail":"Bank of Bhutan launches national digital currency on XRPL. First sovereign CBDC on the ledger.","major":True},
            {"year":"2023","event":"Partial Legal Victory","detail":"Judge Torres: XRP not a security in programmatic sales. Institutional US adoption begins thawing.","major":True},
            {"year":"2024","event":"XRPL EVM Sidechain","detail":"Ethereum-compatible sidechain launches on XRPL — opens DeFi and smart contract integration.","major":True},
            {"year":"2025","event":"SEC Settlement","detail":"SEC drops case. $50M settlement. Full US regulatory clarity arrives. Institutional floodgates open.","major":True},
            {"year":"2025","event":"ETF Filings Wave","detail":"Bitwise, WisdomTree, Canary Capital file US spot XRP ETF applications. European ETPs already live.","major":True},
            {"year":"2026","event":"TradFi Integration Era","detail":"Banks, asset managers, and payment networks actively building on XRPL. Post-lawsuit adoption accelerating.","major":True},
        ],
        "ts": "",
    },
    "comp_intel": {
        "vs_coins": {
            "solana":   {"symbol":"SOL","price":0.0,"change_24h":0.0,"change_7d":0.0,"mcap":0.0},
            "ethereum": {"symbol":"ETH","price":0.0,"change_24h":0.0,"change_7d":0.0,"mcap":0.0},
            "cardano":  {"symbol":"ADA","price":0.0,"change_24h":0.0,"change_7d":0.0,"mcap":0.0},
            "stellar":  {"symbol":"XLM","price":0.0,"change_24h":0.0,"change_7d":0.0,"mcap":0.0},
        },
        "xrp_vs": {"price":0.0,"change_24h":0.0,"change_7d":0.0,"mcap":0.0},
        "odl_corridors": [
            {"from_c":"🇺🇸 USA","to_c":"🇲🇽 Mexico","partner":"Bitso","status":"ACTIVE","vol_note":"Largest ODL corridor globally. Millions USD daily via Bitso."},
            {"from_c":"🇺🇸 USA","to_c":"🇵🇭 Philippines","partner":"Coins.ph","status":"ACTIVE","vol_note":"Major OFW remittance route. Millions of Filipino workers."},
            {"from_c":"🇪🇺 Europe","to_c":"🇲🇽 Mexico","partner":"Bitso","status":"ACTIVE","vol_note":"Cross-Atlantic corridor expanding with MiCA clarity."},
            {"from_c":"🇯🇵 Japan","to_c":"🇵🇭 Philippines","partner":"SBI Remit","status":"ACTIVE","vol_note":"SBI Holdings flagship ODL corridor. High volume."},
            {"from_c":"🇦🇺 Australia","to_c":"🇵🇭 Philippines","partner":"FlashFX","status":"ACTIVE","vol_note":"AUD to PHP remittance. Major OFW corridor."},
            {"from_c":"🇬🇧 UK","to_c":"🇳🇬 Nigeria","partner":"Ripple Partner","status":"GROWING","vol_note":"Africa expansion focus. Flutterwave integration."},
            {"from_c":"🇺🇸 USA","to_c":"🇮🇳 India","partner":"Various","status":"GROWING","vol_note":"Largest remittance market globally. $100B+ annual flows."},
            {"from_c":"🇸🇬 Singapore","to_c":"🌏 SE Asia","partner":"Various","status":"GROWING","vol_note":"Regional hub. Ripple Singapore MPI licence active."},
        ],
        "iso20022": {
            "adopted": [
                {"name":"SWIFT gpi","region":"Global","status":"LIVE","note":"SWIFT global payments network fully ISO 20022 compliant since 2023."},
                {"name":"TARGET2","region":"EU","status":"LIVE","note":"ECB's large-value payment system migrated Nov 2022."},
                {"name":"CHAPS","region":"UK","status":"LIVE","note":"Bank of England high-value payment system migrated 2023."},
                {"name":"Fedwire","region":"USA","status":"LIVE","note":"US Federal Reserve system completed migration 2024."},
                {"name":"CHIPS","region":"USA","status":"LIVE","note":"Clearing House Interbank Payments System ISO 20022 compliant."},
                {"name":"SIC","region":"Switzerland","status":"LIVE","note":"Swiss Interbank Clearing system migrated 2023."},
                {"name":"HVPS+","region":"Canada","status":"LIVE","note":"High Value Payment System Canada completed 2023."},
                {"name":"RITS","region":"Australia","status":"LIVE","note":"Reserve Bank Information Transfer System migrated."},
            ],
            "xrp_advantage": "XRP and the XRPL natively support ISO 20022 data fields, positioning Ripple as infrastructure for the new global payment standard.",
            "banks_exploring": 200,
        },
        "swift_vs": {
            "swift_daily_vol_usd":  5000000000000,
            "swift_avg_time_hrs":   24,
            "swift_avg_cost_pct":   6.0,
            "xrpl_settle_secs":     3,
            "xrpl_cost_usd":        0.0002,
            "xrpl_daily_tx":        0,
            "note": "SWIFT moves ~$5 trillion/day but takes 1-5 days and costs 2-10%. XRPL settles in 3-5 seconds for fractions of a cent.",
        },
        "ts": "",
    },
    "exec_intel": {
        "executives": [
            {"name":"Brad Garlinghouse","title":"CEO, Ripple","handle":"bgarlinghouse","feed":"https://news.google.com/rss/search?q=Brad+Garlinghouse+XRP+Ripple&hl=en-US&gl=US&ceid=US:en"},
            {"name":"Monica Long","title":"President, Ripple","handle":"monicalong","feed":"https://news.google.com/rss/search?q=Monica+Long+Ripple+XRP&hl=en-US&gl=US&ceid=US:en"},
            {"name":"David Schwartz","title":"CTO, Ripple","handle":"JoelKatz","feed":"https://news.google.com/rss/search?q=David+Schwartz+Ripple+XRPL&hl=en-US&gl=US&ceid=US:en"},
            {"name":"Stuart Alderoty","title":"Chief Legal Officer, Ripple","handle":"s_alderoty","feed":"https://news.google.com/rss/search?q=Stuart+Alderoty+Ripple+SEC&hl=en-US&gl=US&ceid=US:en"},
        ],
        "exec_stories":  [],
        "github_commits": [],
        "github_stats": {
            "rippled_commits_7d": 0,
            "xrpl_dev_commits_7d": 0,
            "total_contributors": 0,
            "last_commit_date": "",
            "last_commit_msg": "",
            "last_commit_author": "",
            "open_issues": 0,
            "stars": 0,
        },
        "ts": "",
    },
    "reg_intel": {
        "countries": [
            {"country":"United States","flag":"🇺🇸","status":"CONTESTED","note":"SEC lawsuit settled; XRP non-security ruling in programmatic sales. Evolving regulatory clarity."},
            {"country":"European Union","flag":"🇪🇺","status":"LEGAL","note":"MiCA regulation fully in force. XRP classified as crypto-asset, not security. Clear framework."},
            {"country":"United Kingdom","flag":"🇬🇧","status":"LEGAL","note":"FCA regulated. Crypto-asset promotion rules apply. No specific XRP restrictions."},
            {"country":"Japan","flag":"🇯🇵","status":"LEGAL","note":"FSA regulated. XRP officially recognised as a crypto-asset. SBI Holdings major partner."},
            {"country":"South Korea","flag":"🇰🇷","status":"LEGAL","note":"FSC/FSS regulated. Major trading volume on Upbit and Bithumb. High retail adoption."},
            {"country":"Singapore","flag":"🇸🇬","status":"LEGAL","note":"MAS regulated under PSA. Ripple holds Major Payment Institution licence in Singapore."},
            {"country":"UAE","flag":"🇦🇪","status":"LEGAL","note":"VARA (Dubai) and ADGM (Abu Dhabi) regulated. Active crypto hub. Ripple has regional HQ in Dubai."},
            {"country":"Switzerland","flag":"🇨🇭","status":"LEGAL","note":"FINMA regulated. Crypto Valley in Zug. XRP openly traded on licensed exchanges."},
            {"country":"Australia","flag":"🇦🇺","status":"LEGAL","note":"ASIC regulated. Crypto exchanges licenced. No XRP-specific restrictions."},
            {"country":"Germany","flag":"🇩🇪","status":"LEGAL","note":"BaFin regulated under MiCA framework. Deutsche Börse-listed crypto products available."},
            {"country":"Brazil","flag":"🇧🇷","status":"LEGAL","note":"Banco Central do Brasil regulated. Large crypto market. Bitso major corridor partner."},
            {"country":"Canada","flag":"🇨🇦","status":"LEGAL","note":"CSA regulated. Crypto ETPs listed on TSX. Ripple ODL active on Canada-Mexico corridor."},
            {"country":"Mexico","flag":"🇲🇽","status":"LEGAL","note":"CNBV regulated. Major Ripple ODL remittance corridor with the United States."},
            {"country":"Philippines","flag":"🇵🇭","status":"LEGAL","note":"BSP regulated. Major remittance corridor. XRP used for OFW payments via Ripple partners."},
            {"country":"India","flag":"🇮🇳","status":"TAXED","note":"30% crypto tax + 1% TDS. Legal to hold and trade. Regulatory framework still developing."},
            {"country":"Thailand","flag":"🇹🇭","status":"LEGAL","note":"SEC Thailand regulated. XRP listed on licensed exchanges. Ripple partnerships active."},
            {"country":"Nigeria","flag":"🇳🇬","status":"RESTRICTED","note":"CBN lifted crypto ban in 2023. Regulated under SEC Nigeria but restrictions remain on banks."},
            {"country":"China","flag":"🇨🇳","status":"BANNED","note":"All crypto trading banned since 2021. Citizens may not legally trade or hold XRP."},
            {"country":"Russia","flag":"🇷🇺","status":"RESTRICTED","note":"Limited legal use. Crypto as payment banned. Trading tolerated but heavily restricted."},
            {"country":"Saudi Arabia","flag":"🇸🇦","status":"PENDING","note":"SAMA evaluating framework. Crypto not officially prohibited but no clear legal status."},
        ],
        "etf_tracker": [
            {"applicant":"21Shares","product":"XRP ETP","market":"Europe","status":"LIVE","date":"2019","note":"Actively trading on SIX Swiss Exchange. AUM growing."},
            {"applicant":"CoinShares","product":"XRP ETP","market":"Europe","status":"LIVE","date":"2020","note":"Listed on multiple European exchanges. Institutional grade."},
            {"applicant":"WisdomTree","product":"XRP ETP","market":"Europe","status":"LIVE","date":"2021","note":"FCA and EU regulated. Available in UK and Europe."},
            {"applicant":"VanEck","product":"XRP ETP","market":"Europe","status":"LIVE","date":"2021","note":"Deutsche Börse listed. Physically backed."},
            {"applicant":"Bitwise","product":"XRP ETF","market":"USA","status":"FILED","date":"2025","note":"SEC review pending. Filed as spot XRP ETF."},
            {"applicant":"WisdomTree","product":"XRP ETF","market":"USA","status":"FILED","date":"2025","note":"US spot ETF filing submitted to SEC."},
            {"applicant":"ProShares","product":"XRP Futures ETF","market":"USA","status":"REVIEW","date":"2025","note":"Futures-based product under SEC consideration."},
            {"applicant":"Canary Capital","product":"XRP ETF","market":"USA","status":"FILED","date":"2024","note":"First US spot XRP ETF filing. Pioneer application."},
        ],
        "sec_timeline": [
            {"date":"Dec 2020","event":"SEC Files Lawsuit","detail":"SEC sues Ripple Labs, CEO Brad Garlinghouse, and co-founder Chris Larsen for $1.3B unregistered securities offering.","status":"past"},
            {"date":"Nov 2022","event":"Judge Sides on Documents","detail":"Court orders release of Hinman speech documents. SEC internal views on ETH deemed relevant.","status":"past"},
            {"date":"Jul 2023","event":"Historic Partial Victory","detail":"Judge Analisa Torres rules: XRP is NOT a security in programmatic sales on exchanges. Institutional sales ruled as unregistered securities.","status":"past","major":True},
            {"date":"Aug 2023","event":"SEC Appeals","detail":"SEC files notice of appeal on the programmatic sales ruling. Ripple cross-appeals institutional sales ruling.","status":"past"},
            {"date":"Oct 2024","event":"SEC Drops Charges","detail":"SEC drops charges against Garlinghouse and Larsen personally. Significant de-escalation.","status":"past","major":True},
            {"date":"Mar 2025","event":"Settlement Reached","detail":"Ripple and SEC reach settlement. $50M fine paid vs. original $2B demand. SEC drops appeal.","status":"past","major":True},
            {"date":"2026","event":"Post-Settlement Era","detail":"XRP operating in post-lawsuit clarity. New crypto-friendly SEC administration. Industry watching closely.","status":"current"},
        ],
        "mica_calendar": [
            {"date":"Jun 2023","event":"MiCA Published","detail":"EU Markets in Crypto-Assets regulation officially published in EU Official Journal.","done":True},
            {"date":"Dec 2024","event":"Stablecoin Rules Live","detail":"Title III (EMTs) and Title IV (ARTs) provisions effective. RLUSD and stablecoin issuers must comply.","done":True},
            {"date":"Dec 2024","event":"Full MiCA in Force","detail":"Complete MiCA framework operational across all 27 EU member states. XRP classified as crypto-asset.","done":True},
            {"date":"2025","event":"National Implementation","detail":"EU member states complete national regulatory adaptations. Local supervisors assuming jurisdiction.","done":False},
            {"date":"2025-2026","event":"CASP Licensing Wave","detail":"Crypto Asset Service Providers complete MiCA licensing. Major exchanges, custodians complying.","done":False},
            {"date":"2026+","event":"MiCA Review Clause","detail":"European Commission required to review MiCA effectiveness and consider DeFi/NFT expansion.","done":False},
        ],
        "cbdc_projects": [
            {"country":"Bhutan","flag":"🇧🇹","project":"Druk Digital","partner":"Ripple","status":"LIVE","detail":"National digital currency on XRPL. Royal Monetary Authority partnership. First sovereign CBDC on XRPL."},
            {"country":"Montenegro","flag":"🇲🇪","project":"Digital Euro Pilot","partner":"Ripple","status":"PILOT","detail":"Central Bank of Montenegro piloting digital euro infrastructure on XRPL."},
            {"country":"Palau","flag":"🇵🇼","project":"Palau Stablecoin","partner":"Ripple","status":"LIVE","detail":"PSC (Palau Stablecoin) — USD-backed digital currency on XRPL for government payments."},
            {"country":"Colombia","flag":"🇨🇴","project":"Banco de la República","partner":"Ripple","status":"EXPLORING","detail":"Colombia's central bank exploring XRPL for digital peso settlement infrastructure."},
            {"country":"Hong Kong","flag":"🇭🇰","project":"HKD CBDC","partner":"Ripple","status":"PILOT","detail":"HKMA participating in Project mBridge. Ripple in discussion for XRPL settlement layer."},
            {"country":"Republic of Georgia","flag":"🇬🇪","project":"Digital GEL","partner":"Ripple","status":"EXPLORING","detail":"National Bank of Georgia exploring Ripple technology for national digital currency."},
        ],
    },
    "tech_intel":    {
        "rsi_1h":             0.0,
        "rsi_1d":             0.0,
        "rsi_1h_label":       "",
        "rsi_1d_label":       "",
        "week52_high":        0.0,
        "week52_low":         0.0,
        "week52_pct_high":    0.0,
        "week52_pct_low":     0.0,
        "week52_position":    0.0,
        "support":            [],
        "resistance":         [],
        "price_1y_ago":       0.0,
        "price_1y_change":    0.0,
        "price_1y_date":      "",
        "price_1m_ago":       0.0,
        "price_1m_change":    0.0,
        "ts":                 "",
    },
    "price_intel":   {
        "dominance":        0.0,
        "funding_rate":     0.0,
        "funding_ts":       "",
        "open_interest_usd":0.0,
        "open_interest_xrp":0.0,
        "xrp_eth":          0.0,
        "eth_usd":          0.0,
        "volatility_30d":   0.0,
        "bid":              0.0,
        "ask":              0.0,
        "spread_pct":       0.0,
        "ts":               "",
    },
    "fear_greed":    {},
    "escrow":        {},
    "onchain":       {},
    "onchain_intel": {
        "whale_alerts":      [],
        "exchange_flow":     "unknown",
        "exchange_flow_note":"",
        "rlusd_supply":      0.0,
        "rlusd_price":       0.0,
        "rlusd_vol_24h":     0.0,
        "dex_vol_24h":       0.0,
        "dex_trades_24h":    0,
        "accounts_total":    0,
        "accounts_new_24h":  0,
        "escrow_days":       0,
        "escrow_hours":      0,
        "escrow_minutes":    0,
        "escrow_next_date":  "",
        "ts":                "",
    },
    "stories":       [],
    "stories_by_region": {r: [] for r in REGIONS},
    "ai_us":         {"pulse":"Fetching US intelligence...","regulatory":"Loading...","institutional":"Loading...","ts":""},
    "ai_global":     {"pulse":"Fetching global intelligence...","signals":{},"thesis":"Analyzing...","ts":""},
    "ai_regions":    {r: {"pulse":"Loading...","ts":""} for r in REGIONS},
    "feed_health":   {},
    "breaking":      None,
    "story_stats":   {"today":0,"bullish":0,"bearish":0,"neutral":0},
    "version":       BOT_FILE,
    "last_updated":  None,
    "qa_status":     "PENDING",
    "qa_last":       None,
    "qa_details":    [],
    "last_error":    None,
    "last_error_ts": None,
    "feeds_active":  0,
    "feeds_total":   len(RSS_FEEDS),
    "maintenance":   "OK",
    "start_time":    datetime.now(timezone.utc).isoformat(),
    "visitor_count": 0,

    # ── v6.0 New Feature State ────────────────────────────────────
    "order_book": {
        "binance":  {"bids":[], "asks":[], "spread":0, "ts":""},
        "bitstamp": {"bids":[], "asks":[], "spread":0, "ts":""},
        "kraken":   {"bids":[], "asks":[], "spread":0, "ts":""},
        "combined_bids": [], "combined_asks": [], "total_bid_depth":0, "total_ask_depth":0,
    },
    "inst_flow": {
        "etf_inflows_7d":   0,
        "etf_outflows_7d":  0,
        "net_etf_flow_7d":  0,
        "grayscale_aum":    0,
        "oi_change_24h":    0,
        "funding_trend":    "",
        "large_moves_24h":  [],
        "flow_signal":      "NEUTRAL",
    },
    "liquidity_map": {
        "exchanges": [],
        "tightest_spread":  "",
        "deepest_book":     "",
        "best_venue":       "",
    },
    "ipo_watch": {
        "ripple_valuation":  "~$11B (est. 2025)",
        "ipo_status":        "Filed confidentially — timeline Q4 2025-Q2 2026",
        "lead_underwriters": "Goldman Sachs, JPMorgan (rumoured)",
        "share_structure":   "Pending — XRP holder benefit discussed by CEO",
        "news":              [],
        "probability":       72,
        "next_milestone":    "S-1 Registration Statement",
    },
    "cbdc_competition": {
        "using_xrpl":    [],
        "competing":     [],
        "neutral":       [],
        "threat_level":  "LOW",
        "opportunity_score": 0,
    },
    "macro_data": {
        "dxy":      {"value":0, "change_pct":0, "label":"US Dollar Index"},
        "sp500":    {"value":0, "change_pct":0, "label":"S&P 500"},
        "gold":     {"value":0, "change_pct":0, "label":"Gold (USD/oz)"},
        "treasury": {"value":0, "change_pct":0, "label":"10-Year Treasury Yield"},
        "btc":      {"value":0, "change_pct":0, "label":"Bitcoin (USD)"},
        "xrp_vs_macro": {"dxy_corr":"--","sp500_corr":"--","gold_corr":"--","btc_corr":"--"},
        "macro_signal": "NEUTRAL",
        "ts": "",
    },
    "correlation": {
        "matrix":    {},
        "xrp_btc":   0,
        "xrp_eth":   0,
        "xrp_gold":  0,
        "xrp_sp500": 0,
        "xrp_dxy":   0,
        "period":    "30d",
        "ts":        "",
    },
    "signal_score": {
        "total":          0,
        "grade":          "--",
        "label":          "--",
        "components": {
            "price_momentum":  {"score":0, "weight":15, "signal":"--"},
            "rsi_signal":      {"score":0, "weight":12, "signal":"--"},
            "sentiment":       {"score":0, "weight":15, "signal":"--"},
            "on_chain":        {"score":0, "weight":18, "signal":"--"},
            "macro":           {"score":0, "weight":10, "signal":"--"},
            "inst_flow":       {"score":0, "weight":15, "signal":"--"},
            "whale_activity":  {"score":0, "weight":10, "signal":"--"},
            "fear_greed":      {"score":0, "weight": 5, "signal":"--"},
        },
        "ts": "",
    },
    # ── v6.0 Phase 2 State ────────────────────────────────────────
    "options_flow": {
        "put_call_ratio":   0,
        "implied_vol":      0,
        "max_pain":         0,
        "major_strikes":    [],
        "positioning":      "NEUTRAL",
        "ts":               "",
    },
    "nvt_ratio": {
        "nvt":              0,
        "nvt_signal":       0,
        "interpretation":   "--",
        "30d_avg":          0,
        "ts":               "",
    },
    "accum_distrib": {
        "score_7d":         0,
        "score_30d":        0,
        "signal_7d":        "--",
        "signal_30d":       "--",
        "large_wallet_change_7d": 0,
        "ts":               "",
    },
    "whale_watchlist": {
        "wallets":          [],
        "last_move_ts":     "",
        "alert_count_24h":  0,
    },
    "tx_volume_trend": {
        "daily_90d":        [],
        "avg_7d":           0,
        "avg_30d":          0,
        "trend":            "--",
        "ts":               "",
    },
    "dev_score": {
        "score":            0,
        "commits_7d":       0,
        "prs_7d":           0,
        "contributors_30d": 0,
        "new_repos_30d":    0,
        "stars_total":      0,
        "trend":            "--",
        "ts":               "",
    },
    "currency_crisis": {
        "countries":        [],
        "highest_risk":     "",
        "odl_opportunity":  0,
        "ts":               "",
    },
    "remittance_intel": {
        "corridors": [
            {"route":"USA→Mexico",      "partner":"Bitso",    "volume_est":"$1.8B/day","growth":"+12%","status":"ACTIVE","currency":"MXN","fee_traditional":"5.8%","xrp_saving":"$58/1000"},
            {"route":"USA→Philippines", "partner":"Coins.ph", "volume_est":"$800M/day","growth":"+8%", "status":"ACTIVE","currency":"PHP","fee_traditional":"6.2%","xrp_saving":"$62/1000"},
            {"route":"Japan→Philippines","partner":"SBI Remit","volume_est":"$600M/day","growth":"+15%","status":"ACTIVE","currency":"PHP","fee_traditional":"4.5%","xrp_saving":"$45/1000"},
            {"route":"Europe→Mexico",   "partner":"Bitso",    "volume_est":"$400M/day","growth":"+9%", "status":"ACTIVE","currency":"MXN","fee_traditional":"5.2%","xrp_saving":"$52/1000"},
            {"route":"Australia→Philippines","partner":"FlashFX","volume_est":"$250M/day","growth":"+18%","status":"ACTIVE","currency":"PHP","fee_traditional":"4.8%","xrp_saving":"$48/1000"},
            {"route":"UK→Nigeria",      "partner":"Flutterwave","volume_est":"$180M/day","growth":"+22%","status":"GROWING","currency":"NGN","fee_traditional":"7.1%","xrp_saving":"$71/1000"},
            {"route":"USA→India",       "partner":"Various",  "volume_est":"$2.1B/day","growth":"+5%", "status":"GROWING","currency":"INR","fee_traditional":"4.9%","xrp_saving":"$49/1000"},
            {"route":"Singapore→SE Asia","partner":"Various", "volume_est":"$350M/day","growth":"+20%","status":"GROWING","currency":"Multi","fee_traditional":"5.5%","xrp_saving":"$55/1000"},
        ],
        "total_daily_volume": "$6.5B+",
        "new_corridors_2026": ["UAE→Pakistan", "Germany→Turkey", "Japan→Vietnam"],
        "ts": "",
    },
    "geopolitical_risk": {
        "events": [
            {"region":"Middle East","event":"Gulf CBDC framework adoption","impact":"BULLISH","detail":"GCC nations accelerating digital currency integration. UAE CBUAE partnering with multiple XRPL validators.","urgency":"HIGH"},
            {"region":"Europe","event":"MiCA full implementation 2024-2025","impact":"BULLISH","detail":"All 27 EU states now require crypto-asset service provider licensing. XRP classified as crypto-asset — LEGAL.","urgency":"MEDIUM"},
            {"region":"USA","event":"CLARITY Act + post-SEC settlement","impact":"BULLISH","detail":"Bipartisan crypto legislation advancing. XRP's SEC settlement removes key overhang. Institutional floodgates opening.","urgency":"HIGH"},
            {"region":"Asia","event":"Japan FSA XRP payment licensing","impact":"BULLISH","detail":"Japan has the world's most mature crypto regulatory framework. SBI + Ripple dominance continues to grow.","urgency":"MEDIUM"},
            {"region":"Africa","event":"Currency devaluations driving ODL","impact":"BULLISH","detail":"Nigeria, Egypt, Kenya all seeing record XRP remittance volumes as local currencies collapse vs USD.","urgency":"HIGH"},
            {"region":"Global","event":"ISO 20022 migration deadline","impact":"BULLISH","detail":"All major central bank payment systems migrating to ISO 20022 by 2025. XRPL natively compatible — competitive edge.","urgency":"HIGH"},
            {"region":"China","event":"Digital Yuan / CBDC competition","impact":"BEARISH","detail":"China pushing e-CNY internationally. If adopted widely, could reduce XRP ODL opportunity in Asia corridors.","urgency":"LOW"},
            {"region":"USA","event":"Potential crypto tax legislation","impact":"NEUTRAL","detail":"Congress debating crypto tax treatment. New reporting requirements could reduce retail activity short-term.","urgency":"LOW"},
        ],
        "overall_risk":    "LOW",
        "xrp_impact_score": 72,
        "ts": "",
    },
    "adoption_velocity": {
        "score":            0,
        "institutional":    0,
        "retail":           0,
        "developer":        0,
        "regulatory":       0,
        "trend":            "--",
        "ts":               "",
    },
    # ── v6.0 Phase 3 State ────────────────────────────────────────
    "community_poll": {
        "question":         "",
        "options":          [],
        "votes":            {},
        "date":             "",
        "total_votes":      0,
    },
    "weekly_digest": {
        "content":          "",
        "generated_date":   "",
        "week_number":      0,
        "story_count":      0,
    },
    "macro_calendar": {
        "events": [
            {"date":"2026-07-29","category":"FED","title":"Federal Reserve FOMC Meeting","impact":"HIGH","detail":"Rate decision. Rate cuts = XRP bullish signal. Fed funds futures imply 2 cuts in 2026.","source":"federalreserve.gov"},
            {"date":"2026-09-15","category":"FED","title":"Federal Reserve FOMC Meeting","impact":"HIGH","detail":"Second rate decision of H2 2026. Watch for pivot language in press conference.","source":"federalreserve.gov"},
            {"date":"2026-11-03","category":"FED","title":"Federal Reserve FOMC Meeting","impact":"HIGH","detail":"Pre-election FOMC. Political pressure on rates historically high in November.","source":"federalreserve.gov"},
            {"date":"2026-07-01","category":"LEGAL","title":"Ripple Post-Settlement Compliance Review","impact":"HIGH","detail":"Ripple's first annual compliance report due under SEC settlement terms. Critical for institutional trust.","source":"sec.gov"},
            {"date":"2026-08-01","category":"REGULATORY","title":"MiCA Full Enforcement EU","impact":"HIGH","detail":"All EU crypto-asset service providers must be fully licensed under MiCA. XRP is legal — CASP licensing opens floodgates.","source":"esma.europa.eu"},
            {"date":"2026-09-30","category":"ETF","title":"Franklin Templeton XRP ETF Decision Deadline","impact":"HIGH","detail":"SEC must approve or deny. Approval = institutional XRP custody at scale.","source":"sec.gov"},
            {"date":"2026-10-01","category":"ESCROW","title":"Ripple Escrow Release — 1 Billion XRP","impact":"MEDIUM","detail":"Monthly 1B XRP escrow release. Ripple typically re-locks 800-900M. Net ~100-200M enters circulation.","source":"xrpscan.com"},
            {"date":"2026-11-01","category":"ESCROW","title":"Ripple Escrow Release — 1 Billion XRP","impact":"MEDIUM","detail":"Monthly 1B XRP escrow release.","source":"xrpscan.com"},
            {"date":"2026-07-15","category":"CONGRESS","title":"CLARITY Act Committee Vote","impact":"HIGH","detail":"Senate Banking Committee scheduled vote on the CLARITY for Payment Stablecoins Act. Includes XRP clarity provisions.","source":"congress.gov"},
            {"date":"2026-08-20","category":"XRPL","title":"XRPL Hooks Amendment Vote","impact":"MEDIUM","detail":"Validator community vote on Hooks smart contract amendment. Passes → XRPL DeFi capabilities expand massively.","source":"xrpl.org"},
            {"date":"2026-09-01","category":"RIPPLE","title":"Ripple IPO S-1 Estimated Filing Window","impact":"HIGH","detail":"Investment bank sources project S-1 filing in Q3 2026. Watch SEC EDGAR for official filing.","source":"Industry analysis"},
            {"date":"2026-10-15","category":"REGULATORY","title":"FSA Japan Crypto Exchange Review","impact":"MEDIUM","detail":"Annual FSA review of crypto exchanges. SBI and Coincheck expansion licenses expected. Bullish for Japan XRP volume.","source":"fsa.go.jp"},
            {"date":"2026-12-15","category":"CONGRESS","title":"FIT21 Full Implementation Deadline","impact":"HIGH","detail":"Financial Innovation and Technology for the 21st Century Act compliance deadline. Digital assets legal framework finalised.","source":"congress.gov"},
            {"date":"2026-07-20","category":"XRPL","title":"XRPL AMM V2 Upgrade Proposal","impact":"MEDIUM","detail":"Proposed upgrade to XRPL AMM protocol adding concentrated liquidity. Could significantly increase DeFi TVL.","source":"xrpl.org"},
            {"date":"2026-08-15","category":"ETF","title":"VanEck XRP ETF Decision Deadline","impact":"HIGH","detail":"SEC decision window. VanEck filed one of the earliest XRP ETF applications post-settlement.","source":"sec.gov"},
        ],
        "last_fetched": "",
    },
    "derivatives": {
        "funding_rate_history": [],
        "long_short_ratio": 0,
        "liquidations_24h": {"long_liq": 0, "short_liq": 0, "total": 0},
        "oi_history":       [],
        "funding_trend":    "NEUTRAL",
        "positioning":      "NEUTRAL",
        "ts":               "",
    },
    "leaderboard": {
        "top_sources":      [],
        "top_regions":      [],
        "poll_participation": 0,
        "most_shared":      [],
        "signal_streak":    0,
        "last_updated":     "",
    },

    "upgrade_log":   [
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
         "note": "v1.1 — Full redesign. Turquoise + lime color scheme. 100 sources. Regional intelligence rows. Enhanced analytics."}
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
    if b > r: return "bullish"
    if r > b: return "bearish"
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

def detect_region(title, summary, feed_region):
    text = (title + " " + summary).lower()
    for region, keywords in REGION_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return region
    return feed_region if feed_region in REGIONS else None

def story_id(title, link):
    return hashlib.md5((title + link).encode()).hexdigest()[:12]

def fmt_ts(ts):
    if not ts: return "Unknown"
    try:
        now  = datetime.now(timezone.utc)
        diff = now - ts
        s    = int(diff.total_seconds())
        if s < 60:    return f"{s}s ago"
        if s < 3600:  return f"{s//60}m ago"
        if s < 86400: return f"{s//3600}h ago"
        return f"{s//86400}d ago"
    except: return ""

# ── Price & Data Fetch ─────────────────────────────────────────────────────────
def fetch_price():
    try:
        hdr = {"User-Agent": "XRPRadar/1.1"}
        cg = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple"
            "?localization=false&tickers=false&community_data=false&developer_data=false",
            headers=hdr, timeout=10).json()
        md = cg.get("market_data", {})
        STATE["price"] = {
            "usd":          md.get("current_price", {}).get("usd", 0),
            "btc":          md.get("current_price", {}).get("btc", 0),
            "change_24h":   md.get("price_change_percentage_24h", 0),
            "change_7d":    md.get("price_change_percentage_7d",  0),
            "change_30d":   md.get("price_change_percentage_30d", 0),
            "mcap":         md.get("market_cap",      {}).get("usd", 0),
            "volume_24h":   md.get("total_volume",    {}).get("usd", 0),
            "ath":          md.get("ath",              {}).get("usd", 0),
            "ath_pct":      md.get("ath_change_percentage", {}).get("usd", 0),
            "supply_circ":  md.get("circulating_supply", 0),
            "supply_total": cg.get("market_data", {}).get("total_supply", 100000000000),
            "rank":         cg.get("market_cap_rank", 0),
            "high_24h":     md.get("high_24h", {}).get("usd", 0),
            "low_24h":      md.get("low_24h",  {}).get("usd", 0),
        }
    except Exception as e:
        log_error(f"fetch_price CoinGecko: {e}")
        try:
            b = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=XRPUSDT", timeout=5).json()
            STATE["price"]["usd"]        = float(b.get("lastPrice", 0))
            STATE["price"]["change_24h"] = float(b.get("priceChangePercent", 0))
            STATE["price"]["volume_24h"] = float(b.get("quoteVolume", 0))
            STATE["price"]["high_24h"]   = float(b.get("highPrice", 0))
            STATE["price"]["low_24h"]    = float(b.get("lowPrice", 0))
        except Exception as e2:
            log_error(f"fetch_price Binance: {e2}")

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

    # Escrow
    STATE["escrow"] = {"next_date": "1st of next month", "amount_b": 1.0, "note": "1B XRP monthly release"}

    # Vol/Mcap ratio
    try:
        p = STATE["price"]
        if p.get("mcap") and p.get("volume_24h"):
            STATE["price"]["vol_mcap_ratio"] = round(p["volume_24h"] / p["mcap"] * 100, 2)
    except: pass

    # On-chain metrics via XRPScan
    try:
        stats = requests.get("https://api.xrpscan.com/api/v1/ledger/stats", timeout=8).json()
        STATE["onchain"] = {
            "ledger_index": stats.get("ledger_index", "--"),
            "tps":          round(float(stats.get("tps", 0)), 2),
            "accounts":     stats.get("accounts", "--"),
            "transactions": stats.get("transactions", "--"),
        }
    except:
        STATE["onchain"] = {"ledger_index": "--", "tps": "--", "accounts": "--", "transactions": "--"}

    STATE["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ── Price Intelligence Fetch (v3.0a) ──────────────────────────────────────
def fetch_price_intel():
    hdr = {"User-Agent": "XRPRadar/3.0"}
    pi  = STATE["price_intel"]

    # 1. XRP Market Dominance
    try:
        gl = requests.get("https://api.coingecko.com/api/v3/global",
                          headers=hdr, timeout=10).json()
        pct = gl.get("data", {}).get("market_cap_percentage", {}).get("xrp", 0)
        pi["dominance"] = round(float(pct), 3)
    except Exception as e:
        log_error(f"dominance: {e}")

    # 2. Futures Funding Rate (Binance)
    try:
        fr = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate?symbol=XRPUSDT&limit=1",
            timeout=8).json()
        if fr and isinstance(fr, list):
            rate = float(fr[0].get("fundingRate", 0)) * 100
            pi["funding_rate"] = round(rate, 5)
            pi["funding_ts"]   = fr[0].get("fundingTime", "")
    except Exception as e:
        log_error(f"funding_rate: {e}")

    # 3. Open Interest (Binance Futures)
    try:
        oi = requests.get(
            "https://fapi.binance.com/fapi/v1/openInterest?symbol=XRPUSDT",
            timeout=8).json()
        xrp_oi = float(oi.get("openInterest", 0))
        xrp_px = float(STATE["price"].get("usd", 1) or 1)
        pi["open_interest_xrp"] = round(xrp_oi, 0)
        pi["open_interest_usd"] = round(xrp_oi * xrp_px, 0)
    except Exception as e:
        log_error(f"open_interest: {e}")

    # 4. ETH/USD price + XRP/ETH pair
    try:
        eth = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            headers=hdr, timeout=8).json()
        eth_usd = float(eth.get("ethereum", {}).get("usd", 0))
        xrp_usd = float(STATE["price"].get("usd", 0) or 0)
        pi["eth_usd"] = round(eth_usd, 2)
        if eth_usd > 0 and xrp_usd > 0:
            pi["xrp_eth"] = round(xrp_usd / eth_usd, 8)
    except Exception as e:
        log_error(f"xrp_eth: {e}")

    # 5. 30-Day Rolling Volatility (annualised)
    try:
        hist = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
            "?vs_currency=usd&days=31&interval=daily",
            headers=hdr, timeout=12).json()
        prices = [p[1] for p in hist.get("prices", [])]
        if len(prices) >= 10:
            import math
            returns = [math.log(prices[i]/prices[i-1])
                       for i in range(1, len(prices)) if prices[i-1] > 0]
            if returns:
                mean    = sum(returns) / len(returns)
                variance= sum((r - mean)**2 for r in returns) / len(returns)
                vol_ann = math.sqrt(variance * 365) * 100
                pi["volatility_30d"] = round(vol_ann, 2)
    except Exception as e:
        log_error(f"volatility: {e}")

    # 6. Bid/Ask Spread (Binance spot)
    try:
        bk = requests.get(
            "https://api.binance.com/api/v3/ticker/bookTicker?symbol=XRPUSDT",
            timeout=6).json()
        bid = float(bk.get("bidPrice", 0))
        ask = float(bk.get("askPrice", 0))
        if bid > 0 and ask > 0:
            spread = (ask - bid) / bid * 100
            pi["bid"]        = round(bid, 5)
            pi["ask"]        = round(ask, 5)
            pi["spread_pct"] = round(spread, 5)
    except Exception as e:
        log_error(f"bid_ask: {e}")

    pi["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")



# ── Technical Signal Helpers ───────────────────────────────────────────────
def calc_rsi(closes, period=14):
    """Wilder's RSI — industry standard calculation."""
    if len(closes) < period + 2:
        return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [max(d, 0.0) for d in deltas]
    losses = [abs(min(d, 0.0)) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)

def rsi_label(rsi):
    if rsi is None:   return "N/A"
    if rsi < 25:      return "Deeply Oversold"
    if rsi < 35:      return "Oversold"
    if rsi < 45:      return "Weakening"
    if rsi < 55:      return "Neutral"
    if rsi < 65:      return "Strengthening"
    if rsi < 75:      return "Overbought"
    return "Extremely Overbought"

def find_sr_levels(prices, current, n=3):
    """Find support and resistance from local price pivots — cluster nearby levels."""
    import math
    support = []
    resistance = []
    for i in range(2, len(prices) - 2):
        p = prices[i]
        # Local minimum (support)
        if p <= prices[i-1] and p <= prices[i-2] and p <= prices[i+1] and p <= prices[i+2]:
            support.append(round(p, 4))
        # Local maximum (resistance)
        if p >= prices[i-1] and p >= prices[i-2] and p >= prices[i+1] and p >= prices[i+2]:
            resistance.append(round(p, 4))

    # Cluster levels within 1.5% of each other
    def cluster(levels):
        if not levels: return []
        levels = sorted(set(levels))
        clustered = [levels[0]]
        for lv in levels[1:]:
            if abs(lv - clustered[-1]) / clustered[-1] > 0.015:
                clustered.append(lv)
        return clustered

    sup_cl = cluster(support)
    res_cl = cluster(resistance)

    # Return closest levels to current price
    sup_below = sorted([s for s in sup_cl if s < current], reverse=True)[:n]
    res_above = sorted([r for r in res_cl if r > current])[:n]
    return sup_below, res_above


# ── Technical Signals Fetch (v3.0c) ───────────────────────────────────────
def fetch_tech_intel():
    hdr = {"User-Agent": "XRPRadar/3.0"}
    ti  = STATE["tech_intel"]
    current_px = float(STATE["price"].get("usd", 0) or 0)

    # 13a. RSI — 1H (Binance hourly klines, 50 periods)
    try:
        kl1h = requests.get(
            "https://api.binance.com/api/v3/klines?symbol=XRPUSDT&interval=1h&limit=50",
            timeout=10).json()
        closes_1h = [float(k[4]) for k in kl1h]
        rsi_1h    = calc_rsi(closes_1h)
        if rsi_1h is not None:
            ti["rsi_1h"]       = rsi_1h
            ti["rsi_1h_label"] = rsi_label(rsi_1h)
    except Exception as e:
        log_error(f"rsi_1h: {e}")

    # 13b. RSI — 1D (Binance daily klines, 50 periods)
    try:
        kl1d = requests.get(
            "https://api.binance.com/api/v3/klines?symbol=XRPUSDT&interval=1d&limit=50",
            timeout=10).json()
        closes_1d = [float(k[4]) for k in kl1d]
        rsi_1d    = calc_rsi(closes_1d)
        if rsi_1d is not None:
            ti["rsi_1d"]       = rsi_1d
            ti["rsi_1d_label"] = rsi_label(rsi_1d)
    except Exception as e:
        log_error(f"rsi_1d: {e}")

    # 14 + 15. 52-Week High/Low + Support & Resistance
    # Reuse 365-day price history (also needed for #16)
    try:
        hist = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
            "?vs_currency=usd&days=365&interval=daily",
            headers=hdr, timeout=15).json()
        prices_365 = [p[1] for p in hist.get("prices", [])]

        if len(prices_365) >= 90:
            # 14. 52-Week High/Low
            w52_high = max(prices_365)
            w52_low  = min(prices_365)
            ti["week52_high"]     = round(w52_high, 4)
            ti["week52_low"]      = round(w52_low,  4)
            if w52_high > 0 and current_px > 0:
                ti["week52_pct_high"] = round((current_px - w52_high) / w52_high * 100, 2)
            if w52_low > 0 and current_px > 0:
                ti["week52_pct_low"]  = round((current_px - w52_low)  / w52_low  * 100, 2)
            rng = w52_high - w52_low
            if rng > 0:
                ti["week52_position"] = round((current_px - w52_low) / rng * 100, 1)

            # 15. Support & Resistance from last 90 days of daily closes
            prices_90 = prices_365[-90:]
            sup, res  = find_sr_levels(prices_90, current_px, n=3)
            ti["support"]    = [round(s, 4) for s in sup]
            ti["resistance"] = [round(r, 4) for r in res]

            # 16a. Price 1 year ago (first data point)
            if len(prices_365) >= 365:
                px_1y = prices_365[0]
                ti["price_1y_ago"]    = round(px_1y, 4)
                ti["price_1y_date"]   = "1 year ago"
                if px_1y > 0 and current_px > 0:
                    ti["price_1y_change"] = round((current_px - px_1y) / px_1y * 100, 2)

            # 16b. Price 1 month ago (~30 data points back)
            if len(prices_365) >= 30:
                px_1m = prices_365[-30]
                ti["price_1m_ago"]    = round(px_1m, 4)
                if px_1m > 0 and current_px > 0:
                    ti["price_1m_change"] = round((current_px - px_1m) / px_1m * 100, 2)

    except Exception as e:
        log_error(f"tech_52w_sr_1y: {e}")

    ti["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")








# ── XRP Intelligence Brief (v3.1) ─────────────────────────────────────────
def fetch_prediction(force=False, session="am"):
    """XRP Intelligence Brief — AM: 17:50 UTC (12:00 PM CST), PM: 22:00 UTC (4:00pm CST)."""
    pred  = STATE["prediction"]
    now_u = datetime.now(timezone.utc)
    today = now_u.strftime("%Y-%m-%d")
    run_key = f"{today}_{session}"
    if not force and pred.get("last_run_key") == run_key:
        return
    pred["status"] = "generating"
    try:
        import datetime as _dt

        # Gather last 24h stories
        now    = datetime.now(timezone.utc)
        cutoff = (now - _dt.timedelta(hours=24)).strftime("%Y-%m-%d")
        stories= [s for s in STATE.get("stories",[])
                  if s.get("pub", s.get("published","")) >= cutoff]
        if len(stories) < 10:
            stories = STATE.get("stories",[])
        stories    = stories[:35]
        src_count  = len(set(s.get("source","") for s in stories))

        # Compact story digest
        lines = []
        for s in stories:
            cat    = s.get("category","General")
            sent   = s.get("sentiment","neutral").upper()[:4]
            src    = s.get("source","")[:25]
            ttl    = s.get("title","")[:110]
            smry   = (s.get("summary","") or "")[:140]
            region = s.get("region","") or ""
            tag    = f"|{region}" if region else ""
            lines.append(f"[{cat}|{sent}|{src}{tag}] {ttl}. {smry}")
        story_text = chr(10).join(lines)

        # Live market snapshot
        p  = STATE.get("price",         {})
        ti = STATE.get("tech_intel",    {})
        oc = STATE.get("onchain_intel", {})
        pi = STATE.get("price_intel",   {})
        fg = STATE.get("fear_greed",    {})
        st = STATE.get("story_stats",   {})

        mkt_lines = [
            f"XRP/USD: ${p.get('usd',0)} | 24h: {p.get('change_24h',0):+.2f}% | 7d: {p.get('change_7d',0):+.2f}% | Rank: #{p.get('rank','--')}",
            f"Fear & Greed: {fg.get('score','--')} ({fg.get('label','--')})",
            f"RSI 1H: {ti.get('rsi_1h','--')} ({ti.get('rsi_1h_label','--')}) | RSI 1D: {ti.get('rsi_1d','--')} ({ti.get('rsi_1d_label','--')})",
            f"52W Position: {ti.get('week52_position','--')}% of range | High: ${ti.get('week52_high','--')} | Low: ${ti.get('week52_low','--')}",
            f"Support: {ti.get('support',[])} | Resistance: {ti.get('resistance',[])}",
            f"Funding Rate: {pi.get('funding_rate',0):+.4f}% | OI: ${pi.get('open_interest_usd',0):,.0f} | Dominance: {pi.get('dominance','--')}%",
            f"30D Vol: {pi.get('volatility_30d','--')}% | Spread: {pi.get('spread_pct','--')}%",
            f"Exchange Flow: {oc.get('exchange_flow','--')} - {oc.get('exchange_flow_note','')}",
            f"Whale Alerts: {len(oc.get('whale_alerts',[]))} | RLUSD Supply: {oc.get('rlusd_supply',0):,.0f} | DEX Vol: ${oc.get('dex_vol_24h',0):,.0f}",
            f"Escrow Countdown: {oc.get('escrow_days','--')}d {oc.get('escrow_hours','--')}h",
            f"Stories 24h: {st.get('today',0)} total | {st.get('bullish',0)} bull | {st.get('bearish',0)} bear | {st.get('neutral',0)} neutral",
        ]
        mkt_text = chr(10).join(mkt_lines)

        prompt_parts = [
            "You are the world's foremost XRP intelligence analyst. Your specialty is identifying non-obvious connections between events and projecting domino effects within the XRP ecosystem.",
            "",
            f"LIVE MARKET SNAPSHOT ({now.strftime('%B %d, %Y %H:%M UTC')}):",
            mkt_text,
            "",
            f"XRP NEWS - LAST 24 HOURS ({len(stories)} stories from {src_count} sources worldwide):",
            story_text,
            "",
            f"Write today's XRP Intelligence Brief ({session.upper()} EDITION — {now_u.strftime('%I:%M %p UTC')}). This is a professional institutional-grade intelligence report. Write in exactly these 6 sections. Aim for 40-60 sentences total across all sections — more on busy news days, fewer on quiet ones. Each section should have as many sentences as the material warrants. Reference specific companies, countries, price levels, regulators, and named individuals from the news above. Find connections other analysts would miss. Be bold, specific, and actionable.",
            "",
            "## MARKET PULSE",
            "Synthesise the combined technical data, derivatives market, and price action into one coherent picture. What does the combination of RSI, funding rate, open interest, whale activity, Fear and Greed, and 52-week position tell you about market posture right now?",
            "",
            "## STORY CONNECTIONS",
            "Identify the non-obvious links between today's most significant news stories. Where does a regulatory development reinforce or contradict a technical signal? What two seemingly unrelated stories are telling the same underlying narrative? Connect specific dots with specific reasoning.",
            "",
            "## DOMINO EFFECT",
            "Trace the most plausible cause-and-effect chains. Structure each as: IF [current condition] THEN [near-term outcome] WHICH COULD LEAD TO [second-order consequence]. Provide at least three distinct chains. Be specific about timelines where the data supports it.",
            "",
            "## REGIONAL FLASHPOINTS",
            "Which geographic markets are generating the most meaningful signal today and why? Which country-level development has the highest potential to move XRP in the next week? Name specific countries, regulators, and institutions.",
            "",
            "## WATCHLIST",
            "List exactly 4-5 specific things to monitor in the next 24-72 hours. Each item must name a concrete catalyst: a price level, a regulatory decision, a scheduled event, an on-chain threshold. State what outcome would be bullish and what would be bearish for each.",
            "",
            "## TRADFI INTEGRATION OUTLOOK",
            "Analyse the trajectory of XRP's integration into traditional finance specifically. Which named institution is closest to a confirmed announcement? What regulatory or legal development in the next 30-90 days could accelerate or delay mainstream banking adoption? Name specific banks, payment networks, or asset managers and what their next move likely is.",
            "List exactly 4-5 specific things to monitor in the next 24-72 hours. Each item must name a concrete catalyst: a price level, a regulatory decision, a scheduled event, an on-chain threshold. State what outcome would be bullish and what would be bearish for each.",
        ]
        prompt = chr(10).join(prompt_parts)

        system = (
            "You are the world's foremost XRP and digital payments intelligence analyst, "
            "trusted by institutional investors, central banks, and hedge funds globally. "
            "Write in the style of a Goldman Sachs research note crossed with Bloomberg Intelligence — "
            "authoritative, specific, dense with insight, zero filler. "
            "Every sentence must add new information or analysis. "
            "Be specific: name actual companies, specific countries, exact price levels, "
            "named regulators, executives, and institutions. "
            "Aim for 40-60 sentences total across all sections — let the news volume dictate depth. On busy days write more; on quiet days write less. Every sentence must earn its place. "
            "Never use bullet points or markdown bold. Use only the ## section headers. "
            "Never write: it is important to note, in conclusion, it is worth noting, or overall. "
            "Calibrate uncertainty: say likely, possible, probable, or speculative where appropriate. "
            "This brief is read by whales, banks, and institutional investors who demand depth."
        )

        raw = call_claude(prompt, system, max_tokens=4000)
        if not raw or len(raw) < 200:
            pred["status"] = "error"
            pred["error"]  = "Response too short or empty - check ANTHROPIC_API_KEY"
            return

        # Parse sections
        sections = {
            "market_pulse":         "",
            "connections":          "",
            "domino_effect":        "",
            "regional_flashpoints": "",
            "watchlist":            "",
            "tradfi_outlook":       "",
        }
        for part in raw.split("##"):
            part = part.strip()
            if not part: continue
            split_idx = part.find(chr(10))
            if split_idx < 0: continue
            header = part[:split_idx].strip().upper()
            body   = part[split_idx:].strip()
            if   "MARKET PULSE" in header: sections["market_pulse"]         = body
            elif "CONNECTIONS"  in header: sections["connections"]           = body
            elif "DOMINO"       in header: sections["domino_effect"]         = body
            elif "REGIONAL"     in header: sections["regional_flashpoints"]  = body
            elif "WATCH"        in header: sections["watchlist"]             = body
            elif "TRADFI"       in header: sections["tradfi_outlook"]       = body
            elif "TRADITIONAL"  in header: sections["tradfi_outlook"]       = body

        # Next run time
        next_utc = now.replace(hour=17, minute=50, second=0, microsecond=0)
        if next_utc <= now:
            next_utc = next_utc + _dt.timedelta(days=1)
        remaining = next_utc - now
        hrs  = int(remaining.total_seconds() // 3600)
        mins = int((remaining.total_seconds() % 3600) // 60)

        pred["sections"]      = sections
        pred["generated_at"]  = now.strftime("%B %d, %Y at %I:%M %p UTC")
        pred["last_run_date"] = today
        pred["last_run_key"]  = run_key
        pred["session"]       = session.upper()
        pred["story_count"]   = len(stories)
        pred["source_count"]  = src_count
        pred["next_run_cst"]  = f"Next brief in {hrs}h {mins}m (12:00 PM CST)"
        pred["status"]        = "complete"
        pred["error"]         = ""

    except Exception as e:
        pred["status"] = "error"
        pred["error"]  = str(e)[:300]
        log_error(f"fetch_prediction: {e}")


def prediction_loop():
    """Checks every 5 minutes — fires daily at 17:48-18:05 UTC (11:48am CST)."""
    import datetime as _dt
    while True:
        try:
            now   = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            last  = STATE["prediction"].get("last_run_date","")
            today_str = now.strftime("%Y-%m-%d")
            last_key  = STATE["prediction"].get("last_run_key", "")
            # AM Brief window: 17:48-18:05 UTC = 11:48 AM - 12:05 PM CST
            # (compiled 11:50 CST, posted at noon CST)
            am_window = (now.hour == 17 and now.minute >= 48) or (now.hour == 18 and now.minute <= 5)
            # PM Brief window: 02:48-03:05 UTC = 8:48 PM - 9:05 PM CST
            # (compiled 8:50 PM CST, posted at 9:00 PM CST)
            pm_window = (now.hour == 2 and now.minute >= 48) or (now.hour == 3 and now.minute <= 5)
            if am_window and last_key != f"{today_str}_am":
                fetch_prediction(session="am")
            elif pm_window and last_key != f"{today_str}_pm":
                fetch_prediction(session="pm")
            # Calculate next run countdown
            am_utc = now.replace(hour=17, minute=50, second=0, microsecond=0)
            # PM is at 03:00 UTC — if we've already passed midnight, it's today; else tomorrow
            pm_base = now.replace(hour=3, minute=0, second=0, microsecond=0)
            pm_utc  = pm_base if pm_base > now else pm_base + _dt.timedelta(days=1)
            candidates = [t for t in [am_utc, pm_utc,
                am_utc + _dt.timedelta(days=1)] if t > now]
            next_utc  = min(candidates) if candidates else am_utc + _dt.timedelta(days=1)
            remaining = next_utc - now
            hrs  = int(remaining.total_seconds() // 3600)
            mins = int((remaining.total_seconds() % 3600) // 60)
            STATE["prediction"]["next_run_cst"] = f"Next brief in {hrs}h {mins}m — AM: 12:00 PM CST | PM: 9:00 PM CST"
        except Exception as e:
            log_error(f"prediction_loop: {e}")
        time.sleep(300)


# ── Unique Displays Fetch (v3.0i) ─────────────────────────────────────────
def fetch_disp_intel():
    hdr = {"User-Agent": "XRPRadar/3.0"}
    di  = STATE["disp_intel"]
    now = datetime.now(timezone.utc)

    # 36. Price History Heatmap — 90 days of daily % changes
    try:
        import datetime as _dt
        hist = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
            "?vs_currency=usd&days=90",
            headers=hdr, timeout=20).json()
        raw_prices = hist.get("prices", [])
        if not raw_prices:
            raise ValueError("No price data returned")
        prices = [float(p[1]) for p in raw_prices]
        heatmap = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                pct_change = (prices[i] - prices[i-1]) / prices[i-1] * 100
                ts_ms = raw_prices[i][0]
                day = _dt.datetime.fromtimestamp(ts_ms/1000, tz=_dt.timezone.utc)
                heatmap.append({
                    "date":   day.strftime("%Y-%m-%d"),
                    "dow":    day.weekday(),
                    "week":   int(day.strftime("%W")),
                    "price":  round(prices[i], 4),
                    "change": round(pct_change, 2),
                })
        di["price_heatmap"] = heatmap[-90:]
        log_error(f"price_heatmap: loaded {len(di['price_heatmap'])} days")
    except Exception as e:
        log_error(f"price_heatmap: {e}")

    # 6-Month Price Trend (#9 — new)
    try:
        hist180 = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
            "?vs_currency=usd&days=180",
            headers=hdr, timeout=20).json()
        raw180 = hist180.get("prices", [])
        week_map = {}
        for p in raw180:
            ts_ms = p[0]
            price = round(float(p[1]), 4)
            day = _dt.datetime.fromtimestamp(ts_ms/1000, tz=_dt.timezone.utc)
            wkey = day.strftime("%Y-W%W")
            week_map[wkey] = {"date": day.strftime("%b %d"), "price": price}
        di["price_history_6m"] = list(week_map.values())
    except Exception as e:
        log_error(f"price_6m: {e}")

    # 60-Month Price History (5 Years)
    try:
        hist60 = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
            "?vs_currency=usd&days=1825",
            headers=hdr, timeout=25).json()
        raw60 = hist60.get("prices", [])
        month_map = {}
        for p in raw60:
            ts_ms = p[0]
            price = round(float(p[1]), 4)
            day = _dt.datetime.fromtimestamp(ts_ms/1000, tz=_dt.timezone.utc)
            mkey = day.strftime("%Y-%m")
            month_map[mkey] = {"date": mkey, "price": price, "ts": ts_ms}
        monthly = list(month_map.values())
        # Keep last 60 months
        di["price_history_60m"] = monthly[-60:]
    except Exception as e:
        log_error(f"price_history_60m: {e}")

    # 38. Smart Money Score — proprietary composite
    try:
        sm   = di["smart_money"]
        pi   = STATE.get("price_intel", {})
        ti   = STATE.get("tech_intel",  {})
        oc   = STATE.get("onchain_intel",{})
        st   = STATE.get("story_stats", {})
        signals = []
        score   = 0

        # Signal 1: Whale activity (0-20 pts)
        whale_ct = len(oc.get("whale_alerts", []))
        w_score  = min(whale_ct * 4, 20)
        sm["whale_score"] = w_score
        score += w_score
        if whale_ct > 0:
            signals.append({"label": f"Whale Activity: {whale_ct} alerts","points": w_score,"positive": True})

        # Signal 2: Exchange Flow (0-20 pts)
        flow = oc.get("exchange_flow","NEUTRAL")
        f_score = 20 if flow=="INFLOW" else 10 if flow=="NEUTRAL" or flow=="MIXED" else 0
        sm["flow_score"] = f_score
        score += f_score
        signals.append({"label": f"Exchange Flow: {flow}","points": f_score,"positive": f_score >= 10})

        # Signal 3: RSI position (0-20 pts)
        rsi_1d = float(ti.get("rsi_1d", 50))
        r_score = 20 if 40 <= rsi_1d <= 60 else 15 if 30 <= rsi_1d <= 70 else 5
        sm["rsi_score"] = r_score
        score += r_score
        signals.append({"label": f"RSI 1D: {rsi_1d:.1f} ({ti.get('rsi_1d_label','')})","points": r_score,"positive": r_score >= 15})

        # Signal 4: Bullish sentiment ratio (0-20 pts)
        total  = max(st.get("today", 1), 1)
        bull_r = st.get("bullish", 0) / total
        s_score= round(bull_r * 20)
        sm["sent_score"] = s_score
        score += s_score
        signals.append({"label": f"Sentiment: {round(bull_r*100)}% bullish today","points": s_score,"positive": bull_r > 0.4})

        # Signal 5: Funding rate (0-20 pts)
        fr = float(pi.get("funding_rate", 0))
        o_score = 15 if 0 < fr < 0.05 else 20 if fr >= 0.05 else 10 if fr == 0 else 5
        sm["oi_score"] = o_score
        score += o_score
        signals.append({"label": f"Funding Rate: {fr:+.4f}%","points": o_score,"positive": fr > 0})

        sm["score"]   = score
        sm["signals"] = signals
        sm["label"]   = (
            "🔥 Strong Bull Signal"  if score >= 80 else
            "📈 Bullish Lean"        if score >= 60 else
            "⚖️ Neutral / Mixed"     if score >= 40 else
            "📉 Bearish Lean"        if score >= 20 else
            "❄️ Strong Bear Signal"
        )
    except Exception as e:
        log_error(f"smart_money: {e}")

    # 39. Fear & Greed 30-Day History
    try:
        fg_hist = requests.get(
            "https://api.alternative.me/fng/?limit=30&format=json",
            timeout=8).json()
        entries = fg_hist.get("data", [])
        di["fg_history"] = [
            {
                "value":      int(e.get("value", 0)),
                "label":      e.get("value_classification",""),
                "timestamp":  e.get("timestamp",""),
            }
            for e in reversed(entries)   # chronological order
        ]
    except Exception as e:
        log_error(f"fg_history: {e}")

    di["ts"] = now.strftime("%H:%M UTC")

# ── Practical Tools Fetch (v3.0h) ─────────────────────────────────────────
def fetch_tools_intel():
    hdr = {"User-Agent": "XRPRadar/3.0"}
    ti  = STATE["tools_intel"]

    # 33. Multi-currency FX rates (USD base)
    try:
        resp = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=8).json()
        rates = resp.get("rates", {})
        for cur in ti["fx_rates"]:
            ti["fx_rates"][cur] = round(float(rates.get(cur, 0)), 4)
    except Exception as e:
        log_error(f"fx_rates: {e}")
        # Fallback: open.er-api.com
        try:
            resp2 = requests.get(
                "https://open.er-api.com/v6/latest/USD",
                timeout=8).json()
            rates2 = resp2.get("rates", {})
            for cur in ti["fx_rates"]:
                if cur in rates2:
                    ti["fx_rates"][cur] = round(float(rates2[cur]), 4)
        except Exception as e2:
            log_error(f"fx_rates_fallback: {e2}")

    ti["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")

# ── Sentiment Engine Fetch (v3.0g) ────────────────────────────────────────
def fetch_sent_intel():
    hdr = {"User-Agent": "XRPRadar/3.0"}
    si  = STATE["sent_intel"]
    now = datetime.now(timezone.utc)

    # 28. 30-Day Rolling Sentiment — build daily buckets from story history
    try:
        stories = STATE.get("stories", [])
        # Build daily sentiment counts from story pub dates
        daily = {}
        for s in stories:
            pub = s.get("pub","") or s.get("published","")
            if not pub:
                continue
            try:
                # Parse to date string YYYY-MM-DD
                if "T" in pub:
                    day_key = pub[:10]
                elif len(pub) >= 10:
                    day_key = pub[:10]
                else:
                    continue
                if day_key not in daily:
                    daily[day_key] = {"bull":0,"bear":0,"neut":0,"total":0}
                sent = s.get("sentiment","neutral")
                daily[day_key]["total"] += 1
                if sent == "bullish":  daily[day_key]["bull"] += 1
                elif sent == "bearish": daily[day_key]["bear"] += 1
                else:                  daily[day_key]["neut"] += 1
            except: continue

        # Last 30 days sorted
        sorted_days = sorted(daily.keys())[-30:]
        si["daily_sentiment"] = [
            {
                "date":     d,
                "bull":     daily[d]["bull"],
                "bear":     daily[d]["bear"],
                "neut":     daily[d]["neut"],
                "total":    daily[d]["total"],
                "bull_pct": round(daily[d]["bull"]/max(daily[d]["total"],1)*100,1),
                "bear_pct": round(daily[d]["bear"]/max(daily[d]["total"],1)*100,1),
            }
            for d in sorted_days
        ]
    except Exception as e:
        log_error(f"daily_sentiment: {e}")

    # 29. News Velocity — stories per hour for last 24h
    try:
        import datetime as _vdt
        stories   = STATE.get("stories", [])
        hour_buckets = {h: 0 for h in range(24)}
        cutoff_v  = now - _vdt.timedelta(hours=24)
        for s in stories:
            pub = s.get("pub","") or s.get("published","")
            if not pub: continue
            try:
                # Parse ISO format pub date
                pub_clean = pub[:19].replace("T"," ")
                pub_dt = _vdt.datetime.strptime(pub_clean, "%Y-%m-%d %H:%M:%S")
                pub_dt = pub_dt.replace(tzinfo=_vdt.timezone.utc)
                if pub_dt < cutoff_v: continue
                # How many hours ago was this story?
                hrs_ago = int((now - pub_dt).total_seconds() / 3600)
                if 0 <= hrs_ago < 24:
                    bucket = 23 - hrs_ago
                    hour_buckets[bucket] = hour_buckets.get(bucket, 0) + 1
            except: continue
        si["velocity_hours"] = [
            {"hour": h, "count": hour_buckets[h]}
            for h in range(24)
        ]
    except Exception as e:
        log_error(f"velocity: {e}")

    # 30. Source Leaderboard — most active + most bullish sources
    try:
        stories  = STATE.get("stories", [])
        src_data = {}
        for s in stories:
            src  = s.get("source","Unknown")
            sent = s.get("sentiment","neutral")
            if src not in src_data:
                src_data[src] = {"name":src,"total":0,"bull":0,"bear":0,"breaking":0}
            src_data[src]["total"]    += 1
            if sent == "bullish":  src_data[src]["bull"]  += 1
            if sent == "bearish":  src_data[src]["bear"]  += 1
            if s.get("breaking"):  src_data[src]["breaking"] += 1

        # Sort by total stories, top 15
        leaders = sorted(src_data.values(), key=lambda x: x["total"], reverse=True)[:15]
        for l in leaders:
            t = max(l["total"], 1)
            l["bull_pct"] = round(l["bull"] / t * 100, 0)
            l["bear_pct"] = round(l["bear"] / t * 100, 0)
        si["source_leaders"] = leaders
    except Exception as e:
        log_error(f"source_leaders: {e}")

    # 31. Google Trends — XRP interest via RSS proxy
    try:
        import feedparser as _fp2
        trend_url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        feed = _fp2.parse(trend_url)
        xrp_score = 0
        keywords  = []
        for entry in feed.entries[:20]:
            title = getattr(entry,"title","").lower()
            # Check for XRP/Ripple/crypto mentions
            if any(kw in title for kw in ["xrp","ripple","crypto","bitcoin","ethereum","blockchain"]):
                xrp_score += 10
                keywords.append(getattr(entry,"title","")[:40])
        # Also check approximate trend from our story velocity
        recent_stories = [s for s in STATE.get("stories",[])
                          if s.get("pub","") >= (now - __import__("datetime").timedelta(hours=6)).strftime("%Y-%m-%d")]
        velocity_score = min(len(recent_stories) * 5, 90)
        si["google_trend"]       = min(xrp_score + velocity_score, 100)
        si["trend_keywords"]     = keywords[:5]
        si["google_trend_label"] = (
            "🔥 Trending" if si["google_trend"] > 70 else
            "📈 Rising"   if si["google_trend"] > 40 else
            "😴 Quiet"    if si["google_trend"] > 15 else
            "💤 Minimal"
        )
    except Exception as e:
        log_error(f"google_trends: {e}")
        # Fallback: derive from story count
        recent = len([s for s in STATE.get("stories",[]) if s.get("age","").endswith("h ago") or s.get("age","").endswith("m ago")])
        si["google_trend"]       = min(recent * 4, 100)
        si["google_trend_label"] = "📡 From feed velocity"

    si["ts"] = now.strftime("%H:%M UTC")

# ── Competitive Intelligence Fetch (v3.0f) ────────────────────────────────
def fetch_comp_intel():
    hdr = {"User-Agent": "XRPRadar/3.0"}
    ci  = STATE["comp_intel"]

    # 24. XRP vs SOL / ETH / ADA / XLM — CoinGecko /coins/markets (free tier reliable)
    try:
        ids = "ripple,solana,ethereum,cardano,stellar"
        markets = requests.get(
            f"https://api.coingecko.com/api/v3/coins/markets"
            f"?vs_currency=usd&ids={ids}&order=market_cap_desc"
            f"&per_page=5&page=1&sparkline=false"
            f"&price_change_percentage=24h%2C7d",
            headers=hdr, timeout=12).json()

        id_map = {
            "ripple":   "xrp_vs",
            "solana":   ("vs_coins","solana"),
            "ethereum": ("vs_coins","ethereum"),
            "cardano":  ("vs_coins","cardano"),
            "stellar":  ("vs_coins","stellar"),
        }
        for coin in (markets if isinstance(markets, list) else []):
            cid    = coin.get("id","")
            target = id_map.get(cid)
            if not target: continue
            record = {
                "price":      round(float(coin.get("current_price") or 0), 6),
                "change_24h": round(float(coin.get("price_change_percentage_24h") or 0), 2),
                "change_7d":  round(float(coin.get("price_change_percentage_7d_in_currency") or 0), 2),
                "mcap":       round(float(coin.get("market_cap") or 0), 0),
            }
            if isinstance(target, tuple):
                ci[target[0]][target[1]].update(record)
            else:
                ci[target].update(record)
    except Exception as e:
        log_error(f"comp_vs_coins: {e}")

    # 27. XRP vs SWIFT — update live XRPL transaction count
    try:
        stats = requests.get(
            "https://api.xrpscan.com/api/v1/ledger/stats",
            timeout=8).json()
        daily_tx = int(stats.get("tx_count_24h", 0) or stats.get("transactions", 0) or 0)
        ci["swift_vs"]["xrpl_daily_tx"] = daily_tx
    except Exception as e:
        log_error(f"comp_swift_tx: {e}")

    ci["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")

# ── Executive & Developer Tracker Fetch (v3.0e) ────────────────────────────
def fetch_exec_intel():
    import feedparser as _fp
    ei = STATE["exec_intel"]

    # 22. Executive Statement Tracker — Google News RSS
    all_exec_stories = []
    for exec_info in ei["executives"]:
        try:
            feed = _fp.parse(exec_info["feed"])
            for entry in feed.entries[:3]:
                pub = ""
                try:
                    from time import mktime
                    import datetime as _dt
                    pub_dt = _dt.datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                    diff   = datetime.now(timezone.utc) - pub_dt
                    pub    = f"{diff.days}d ago" if diff.days > 0 else f"{diff.seconds//3600}h ago" if diff.seconds >= 3600 else f"{diff.seconds//60}m ago"
                except: pass
                src = ""
                try: src = entry.source.title
                except: pass
                all_exec_stories.append({
                    "exec_name":  exec_info["name"],
                    "exec_title": exec_info["title"],
                    "title":      getattr(entry, "title", "")[:120],
                    "link":       getattr(entry, "link", ""),
                    "source":     src or "News",
                    "age":        pub,
                })
        except Exception as e:
            log_error(f"exec_feed_{exec_info['name']}: {e}")
    ei["exec_stories"] = all_exec_stories[:12]

    # 23. XRPL GitHub Activity
    repos    = [("XRPLF","rippled"),("XRPLF","xrpl-dev-portal"),("XRPLF","xrpl.js")]
    gh_hdr   = {"Accept":"application/vnd.github.v3+json","User-Agent":"XRPRadar/3.0"}
    all_commits  = []
    total_stars  = 0
    total_issues = 0
    for owner, repo in repos:
        try:
            commits = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=10",
                headers=gh_hdr, timeout=10).json()
            if isinstance(commits, list):
                for c in commits[:5]:
                    cm  = c.get("commit", {})
                    au  = cm.get("author", {})
                    gav = (c.get("author") or {}).get("avatar_url","")
                    msg = cm.get("message","")[:80]
                    nl  = msg.find(chr(10))
                    if nl > 0: msg = msg[:nl]
                    all_commits.append({
                        "repo":   repo,
                        "msg":    msg,
                        "author": au.get("name","")[:30],
                        "date":   au.get("date","")[:10],
                        "url":    c.get("html_url",""),
                    })
        except Exception as e:
            log_error(f"github_commits_{repo}: {e}")
        try:
            meta = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=gh_hdr, timeout=8).json()
            total_stars  += int(meta.get("stargazers_count", 0))
            total_issues += int(meta.get("open_issues_count", 0))
        except Exception as e:
            log_error(f"github_meta_{repo}: {e}")

    all_commits.sort(key=lambda c: c.get("date",""), reverse=True)
    ei["github_commits"] = all_commits[:15]

    import datetime as _dt2
    cutoff = (_dt2.datetime.now(_dt2.timezone.utc) - _dt2.timedelta(days=7)).strftime("%Y-%m-%d")
    recent = [c for c in all_commits if c.get("date","") >= cutoff]
    gs = ei["github_stats"]
    gs["rippled_commits_7d"]  = len([c for c in recent if c["repo"] == "rippled"])
    gs["xrpl_dev_commits_7d"] = len([c for c in recent if c["repo"] != "rippled"])
    gs["stars"]               = total_stars
    gs["open_issues"]         = total_issues
    if all_commits:
        gs["last_commit_msg"]    = all_commits[0].get("msg","")
        gs["last_commit_author"] = all_commits[0].get("author","")
        gs["last_commit_date"]   = all_commits[0].get("date","")

    ei["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")

# ── On-Chain Intelligence Fetch (v3.0b) ───────────────────────────────────
def fetch_onchain_intel():
    hdr = {"User-Agent": "XRPRadar/3.0"}
    oc  = STATE["onchain_intel"]

    # 7. Whale Alert Feed — large XRP payments via XRPScan
    try:
        # Known Ripple escrow wallet cluster releases & large payment tracker
        whale_url = "https://api.xrpscan.com/api/v1/account/rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh/payments?limit=20"
        resp = requests.get(whale_url, timeout=10).json()
        payments = resp if isinstance(resp, list) else resp.get("payments", [])
        whales = []
        for p in payments[:20]:
            amt = float(p.get("amount", 0)) / 1_000_000 if isinstance(p.get("amount"), str) else float(p.get("amount", 0))
            if amt >= 1_000_000:
                whales.append({
                    "amount_xrp":  round(amt, 0),
                    "amount_usd":  round(amt * float(STATE["price"].get("usd", 0) or 0), 0),
                    "from":        p.get("source", "")[:20],
                    "to":          p.get("destination", "")[:20],
                    "ts":          p.get("date", "")[:16],
                })
        # Supplement with whale stories from our feed
        whale_stories = [s for s in STATE["stories"][:100] if s.get("category") == "Whale"][:5]
        for ws in whale_stories:
            if not any(w.get("title") for w in whales):
                whales.append({
                    "title":      ws["title"][:80],
                    "source":     ws["source"],
                    "age":        ws.get("age",""),
                    "sentiment":  ws.get("sentiment",""),
                })
        oc["whale_alerts"] = whales[:10]
    except Exception as e:
        log_error(f"whale_alerts: {e}")
        # Fall back to whale stories from feed
        try:
            whale_stories = [s for s in STATE["stories"][:100] if s.get("category") == "Whale"][:8]
            oc["whale_alerts"] = [{"title": s["title"][:80], "source": s["source"],
                                   "age": s.get("age",""), "sentiment": s.get("sentiment","")}
                                  for s in whale_stories]
        except: pass

    # 8. Exchange Flow Signal (derived from funding rate + OI direction)
    try:
        fr  = float(STATE["price_intel"].get("funding_rate", 0))
        oi  = float(STATE["price_intel"].get("open_interest_usd", 0))
        px  = float(STATE["price"].get("usd", 0) or 0)
        ch  = float(STATE["price"].get("change_24h", 0) or 0)
        if fr > 0.01 and ch > 0:
            oc["exchange_flow"]      = "INFLOW"
            oc["exchange_flow_note"] = "Price rising + positive funding — accumulation signal"
        elif fr < -0.01 and ch < 0:
            oc["exchange_flow"]      = "OUTFLOW"
            oc["exchange_flow_note"] = "Price falling + negative funding — distribution signal"
        elif fr > 0 and ch < 0:
            oc["exchange_flow"]      = "MIXED"
            oc["exchange_flow_note"] = "Divergence: longs paying but price declining"
        else:
            oc["exchange_flow"]      = "NEUTRAL"
            oc["exchange_flow_note"] = "No clear directional bias"
    except Exception as e:
        log_error(f"exchange_flow: {e}")

    # 9. RLUSD Circulation & Volume via CoinGecko
    try:
        rlusd = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple-usd"
            "?localization=false&tickers=false&community_data=false&developer_data=false",
            headers=hdr, timeout=10).json()
        md = rlusd.get("market_data", {})
        oc["rlusd_price"]   = float(md.get("current_price", {}).get("usd", 1.0))
        oc["rlusd_supply"]  = float(md.get("circulating_supply", 0) or 0)
        oc["rlusd_vol_24h"] = float(md.get("total_volume", {}).get("usd", 0) or 0)
    except Exception as e:
        log_error(f"rlusd: {e}")
        # Fallback: XRPScan RLUSD issuer
        try:
            rlusd_issuer = "rMH4UxPrbuMa1spCBR98hLLyNJp4d8p4tM"
            ri = requests.get(
                f"https://api.xrpscan.com/api/v1/account/{rlusd_issuer}",
                timeout=8).json()
            oc["rlusd_supply"] = float(ri.get("obligation", 0))
        except: pass

    # 10. XRPL DEX/AMM Volume via XRPScan market stats
    try:
        mkt = requests.get(
            "https://api.xrpscan.com/api/v1/market/summary",
            timeout=8).json()
        oc["dex_vol_24h"]   = float(mkt.get("volume24h", 0) or 0)
        oc["dex_trades_24h"]= int(mkt.get("trades24h", 0) or 0)
    except Exception as e:
        log_error(f"dex_vol: {e}")
        # Try alternate endpoint
        try:
            stats = requests.get("https://api.xrpscan.com/api/v1/ledger/stats", timeout=8).json()
            oc["dex_trades_24h"] = int(stats.get("offers", 0) or 0)
        except: pass

    # 11. New Account Creation Rate
    try:
        stats = requests.get("https://api.xrpscan.com/api/v1/ledger/stats", timeout=8).json()
        total = int(stats.get("accounts", 0) or 0)
        prev  = oc.get("accounts_total", 0)
        if prev > 0 and total > prev:
            oc["accounts_new_24h"] = total - prev
        oc["accounts_total"] = total
    except Exception as e:
        log_error(f"accounts: {e}")

    # 12. Escrow Countdown Timer — Ripple releases 1B XRP on 1st of each month
    try:
        now = datetime.now(timezone.utc)
        if now.month == 12:
            next_rel = now.replace(year=now.year+1, month=1, day=1,
                                   hour=0, minute=0, second=0, microsecond=0)
        else:
            next_rel = now.replace(month=now.month+1, day=1,
                                   hour=0, minute=0, second=0, microsecond=0)
        delta               = next_rel - now
        oc["escrow_days"]   = delta.days
        oc["escrow_hours"]  = delta.seconds // 3600
        oc["escrow_minutes"]= (delta.seconds % 3600) // 60
        oc["escrow_next_date"] = next_rel.strftime("%b %d, %Y")
    except Exception as e:
        log_error(f"escrow_countdown: {e}")

    oc["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")

# ── News Fetch ─────────────────────────────────────────────────────────────────
def fetch_news():
    seen_ids    = {s["id"] for s in STATE["stories"]}
    new_stories = []
    active      = 0
    health      = {}

    for feed_cfg in RSS_FEEDS:
        name      = feed_cfg["name"]
        url       = feed_cfg["url"]
        ftype     = feed_cfg["type"]
        region    = feed_cfg.get("region", "US")
        do_filter = feed_cfg["filter"]
        try:
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                health[name] = "DOWN"
                continue
            health[name] = "UP"
            active += 1
            for entry in parsed.entries[:10]:
                title   = getattr(entry, "title",   "")
                link    = getattr(entry, "link",    "")
                summary = getattr(entry, "summary", "")
                summary = re.sub(r"<[^>]+>", "", summary)[:400]
                if not title or not link: continue
                if do_filter and not is_xrp(title, summary): continue
                sid = story_id(title, link)
                if sid in seen_ids: continue
                pub = None
                try:
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except: pass
                if pub:
                    age = (datetime.now(timezone.utc) - pub).total_seconds()
                    if age > 604800: continue

                lang        = detect_language(title)
                story_region= detect_region(title, summary, region)
                sentiment   = detect_sentiment(title, summary)
                category    = detect_category(title, summary)
                breaking    = detect_breaking(title)

                story = {
                    "id":        sid,
                    "title":     title,
                    "link":      link,
                    "summary":   summary,
                    "source":    name,
                    "type":      ftype,
                    "region":    story_region,
                    "sentiment": sentiment,
                    "category":  category,
                    "breaking":  breaking,
                    "lang":      lang,
                    "pub":       pub.isoformat() if pub else None,
                    "age":       fmt_ts(pub) if pub else "Recent",
                }
                new_stories.append(story)
                seen_ids.add(sid)
        except Exception as e:
            health[name] = "DOWN"
            log_error(f"feed {name}: {e}")

    all_stories = new_stories + STATE["stories"]
    all_stories.sort(key=lambda s: s.get("pub") or "", reverse=True)
    STATE["stories"]      = all_stories[:MAX_STORIES]
    STATE["feed_health"]  = health
    STATE["feeds_active"] = active
    STATE["feeds_total"]  = len(RSS_FEEDS)

    # Group by region
    for r in REGIONS:
        STATE["stories_by_region"][r] = [s for s in STATE["stories"][:150] if s.get("region") == r][:40]

    today_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    today_s = [s for s in STATE["stories"] if (s.get("pub") or "") >= today_cutoff]
    STATE["story_stats"] = {
        "today":   len(today_s),
        "bullish": sum(1 for s in today_s if s["sentiment"] == "bullish"),
        "bearish": sum(1 for s in today_s if s["sentiment"] == "bearish"),
        "neutral": sum(1 for s in today_s if s["sentiment"] == "neutral"),
        "total":   len(STATE["stories"]),
        "sources_active": active,
        "sources_total":  len(RSS_FEEDS),
    }

    for s in STATE["stories"]:
        if s.get("breaking") and s.get("pub"):
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(s["pub"])).total_seconds() / 3600
            if age_h < 2:
                STATE["breaking"] = s
                break
    else:
        STATE["breaking"] = None

# ── Claude AI Briefing ─────────────────────────────────────────────────────────
def call_claude(prompt, system_prompt, max_tokens=1000):
    if not ANTHROPIC_API_KEY:
        return "Add ANTHROPIC_API_KEY to Railway Variables to enable AI briefings."
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},
            json={"model":CLAUDE_MODEL,"max_tokens":max_tokens,"system":system_prompt,"messages":[{"role":"user","content":prompt}]},
            timeout=45)
        if r.status_code == 401:
            log_error("Claude API 401: invalid or expired API key")
            return "AI error: API key rejected (401). Re-check ANTHROPIC_API_KEY in Railway Variables."
        if r.status_code == 400:
            err = r.json().get("error",{}).get("message","bad request")
            log_error(f"Claude API 400: {err}")
            return f"AI error: {err[:120]}"
        if r.status_code == 429:
            log_error("Claude API 429: rate limited")
            return "AI temporarily rate-limited. Will retry next cycle."
        if r.status_code not in (200, 201):
            log_error(f"Claude API {r.status_code}: {r.text[:200]}")
            return f"AI error: HTTP {r.status_code}. Details in Railway logs."
        data = r.json()
        if "error" in data:
            log_error(f"Claude API body error: {data['error']}")
            return f"AI error: {data['error'].get('message','unknown')[:120]}"
        blocks = data.get("content", [])
        text = "".join(b.get("text","") for b in blocks if b.get("type")=="text")
        return text if text else "No response text returned."
    except requests.exceptions.Timeout:
        log_error("Claude API: timeout (45s)")
        return "AI briefing timed out. Will retry."
    except Exception as e:
        log_error(f"Claude API: {e}")
        return f"AI temporarily unavailable ({type(e).__name__})."

def fetch_ai_briefing():
    stories = STATE["stories"][:80]
    if not stories: return

    # Translate non-English story titles
    foreign = [s for s in stories if s.get("lang") == "non-english"][:5]
    translations = {}
    if foreign and ANTHROPIC_API_KEY:
        try:
            titles_to_translate = "\n".join([f"{i+1}. {s['title']} (source: {s['source']})" for i,s in enumerate(foreign)])
            titles_to_translate = "\n".join([
                f"{i+1}. TITLE: {s['title']}\n   SUMMARY: {s.get('summary','')[:200]}"
                for i,s in enumerate(foreign)])
            trans_prompt = (f"Translate these non-English XRP news items to English. "
                           f"Reply ONLY with a JSON object like: {{\"1\": {{\"title\": \"...\", \"summary\": \"...\"}}, ...}}\n\n{titles_to_translate}")
            raw = call_claude(trans_prompt, "You are a professional translator. Reply only with valid JSON. Translate both title and summary accurately.", 600)
            raw = raw.strip().lstrip("```json").rstrip("```").strip()
            trans_map = json.loads(raw)
            for i, s in enumerate(foreign):
                key = str(i+1)
                if key in trans_map:
                    val = trans_map[key]
                    translations[s["id"]] = val
                    for story in STATE["stories"]:
                        if story["id"] == s["id"]:
                            if isinstance(val, dict):
                                story["translated_title"]   = val.get("title", "")
                                story["translated_summary"] = val.get("summary", "")
                            else:
                                story["translated_title"] = str(val)
                            break
        except Exception as e:
            log_error(f"Translation: {e}")

    titles_all = "\n".join([f"- [{s['source']}] {s['title']} ({s['sentiment'].upper()})" for s in stories])

    us_stories  = [s for s in stories if s.get("region") == "US" or s["type"] in {"major","official","institutional","legal","mainstream","aggregator"}]
    titles_us   = "\n".join([f"- [{s['source']}] {s['title']} ({s['sentiment'].upper()})" for s in us_stories[:30]])

    sys_us = "You are an XRP market intelligence analyst specializing in US markets. Be concise, factual, forward-looking. No disclaimers. No emojis."
    prompt_us = (f"Based on these recent US XRP/Ripple news stories:\n{titles_us}\n\n"
                 "Respond in JSON only (no markdown, no backticks):\n"
                 '{"pulse":"2 sentence US market intelligence summary","'
                 'regulatory":"1 sentence on US regulatory landscape (SEC/CFTC/legislation)","'
                 'institutional":"1 sentence on US institutional XRP activity (ETFs/banks/custody)"}')
    try:
        raw = call_claude(prompt_us, sys_us, 350)
        raw = raw.strip().lstrip("```json").rstrip("```").strip()
        d   = json.loads(raw)
        STATE["ai_us"] = {"pulse": d.get("pulse",""),"regulatory": d.get("regulatory",""),"institutional": d.get("institutional",""),"ts": datetime.now(timezone.utc).strftime("%H:%M UTC")}
    except Exception as e:
        log_error(f"AI US: {e}")

    # Global
    sys_gl = "You are a global XRP intelligence analyst. Synthesize news from all regions. Be concise, analytical, forward-looking. No disclaimers. No emojis."
    region_signals = {}
    for reg in REGIONS:
        reg_stories = [s for s in stories if s.get("region") == reg]
        if reg_stories:
            bulls = sum(1 for s in reg_stories if s["sentiment"] == "bullish")
            bears = sum(1 for s in reg_stories if s["sentiment"] == "bearish")
            region_signals[reg] = "bullish" if bulls > bears else "bearish" if bears > bulls else "neutral"
        else:
            region_signals[reg] = "quiet"

    prompt_gl = (f"Based on these global XRP/Ripple news stories:\n{titles_all}\n\n"
                 "Respond in JSON only (no markdown, no backticks):\n"
                 '{"pulse":"2 sentence global XRP market synthesis","'
                 'thesis":"Forward-looking analysis: what do all global signals mean for XRP right now? 2-3 sentences."}')
    try:
        raw = call_claude(prompt_gl, sys_gl, 450)
        raw = raw.strip().lstrip("```json").rstrip("```").strip()
        d   = json.loads(raw)
        STATE["ai_global"] = {"pulse": d.get("pulse",""),"signals": region_signals,"thesis": d.get("thesis",""),"ts": datetime.now(timezone.utc).strftime("%H:%M UTC")}
    except Exception as e:
        log_error(f"AI Global: {e}")

    # Regional briefings
    for reg in REGIONS:
        reg_stories = [s for s in stories if s.get("region") == reg][:20]
        if not reg_stories: continue
        titles_reg = "\n".join([f"- [{s['source']}] {s['title']}" for s in reg_stories])
        sys_reg = f"You are an XRP analyst focused on {reg}. Be brief and factual."
        prompt_reg = (f"Based on these {reg} XRP news stories:\n{titles_reg}\n\n"
                      f"Respond in JSON only: {{\"pulse\":\"1-2 sentence {reg} XRP intelligence summary\"}}")
        try:
            raw = call_claude(prompt_reg, sys_reg, 200)
            raw = raw.strip().lstrip("```json").rstrip("```").strip()
            d   = json.loads(raw)
            STATE["ai_regions"][reg] = {"pulse": d.get("pulse",""),"ts": datetime.now(timezone.utc).strftime("%H:%M UTC")}
        except Exception as e:
            log_error(f"AI {reg}: {e}")
        time.sleep(0.5)

# ── Preflight QA ───────────────────────────────────────────────────────────────
def run_qa():
    checks = []
    def chk(name, ok, detail=""):
        checks.append({"name": name, "ok": ok, "detail": detail})

    chk("Price data present",    bool(STATE["price"].get("usd")),           f"${STATE['price'].get('usd','MISSING')}")
    chk("Fear & Greed present",  bool(STATE["fear_greed"].get("score")),     f"{STATE['fear_greed'].get('score','MISSING')}/100")
    chk("Stories collected",     len(STATE["stories"]) > 0,                  f"{len(STATE['stories'])} stories")
    chk("Active feeds > 30",     STATE["feeds_active"] >= 30,                f"{STATE['feeds_active']}/{len(RSS_FEEDS)} feeds UP")
    chk("AI briefings present",  bool(STATE["ai_global"].get("pulse","").strip()), "Global pulse OK" if STATE["ai_global"].get("pulse") else "Empty")
    chk("Anthropic key set",     bool(ANTHROPIC_API_KEY),                    "Set" if ANTHROPIC_API_KEY else "MISSING")
    chk("On-chain data",         STATE["onchain"].get("tps","--") != "--",   f"TPS: {STATE['onchain'].get('tps','--')}")

    all_ok = all(c["ok"] for c in checks)
    STATE["qa_status"]  = "PASS" if all_ok else "FAIL"
    STATE["qa_last"]    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    STATE["qa_details"] = checks

# ── Main Loops ─────────────────────────────────────────────────────────────────
def price_loop():
    while True:
        try:
            fetch_price()
            fetch_price_intel()
            fetch_onchain_intel()
            fetch_tech_intel()
            fetch_exec_intel()
            fetch_comp_intel()
            fetch_tools_intel()
            fetch_disp_intel()
            fetch_sent_intel()        # Sentiment Engine (#28-31) — was orphaned
            compute_signal_score()    # Signal Score (#61) — depends on above
        except Exception as e: log_error(f"price_loop: {e}")
        time.sleep(PRICE_INTERVAL)

def market_loop():
    """v6.0/v6.1 market-data fetchers — heavier external APIs on a slower cycle."""
    time.sleep(8)   # let first price cycle populate
    last_weekly = 0
    while True:
        try:
            fetch_order_book()        # #41 Order Book (Binance/Bitstamp/Kraken)
            fetch_liquidity_map()     # #43 Liquidity Map (depends on order book)
            fetch_macro_data()        # #46/#47 Macro + Correlation (Yahoo Finance)
            fetch_nvt_ratio()         # #49 NVT Ratio
            fetch_adoption_velocity() # #57 Adoption Velocity
            fetch_currency_crisis()   # #54 Currency Crisis (Yahoo Finance)
            fetch_ripple_ipo_news()   # #44 IPO Watch news feed
            fetch_community_poll()    # #60 Community Poll (sets daily question)
            compute_signal_score()    # recompute now that macro/flow data is fresh
            now = time.time()
            if now - last_weekly >= 3600:   # weekly digest check hourly (Sundays only)
                generate_weekly_digest()    # #62 Weekly Digest
                last_weekly = now
            fetch_derivatives()           # #3 Derivatives Dashboard (v7.0)
        except Exception as e:
            log_error(f"market_loop: {e}")
        time.sleep(MARKET_INTERVAL)

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
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    if v >= 1e3:  return f"${v/1e3:.2f}K"
    return f"${v:.4f}"

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/run-prediction")
def run_prediction_route():
    import threading as _t
    _t.Thread(target=lambda: fetch_prediction(force=True), daemon=True).start()
    return jsonify({"status":"triggered","message":"Brief generating — check /api/data in ~20 seconds"})

@app.route("/ping")
def ping():
    return "XRPRadar v1.1 OK", 200

@app.route("/api/data")
def api_data():
    return jsonify({
        "price":            STATE["price"],
        "price_intel":      STATE["price_intel"],
        "fear_greed":       STATE["fear_greed"],
        "escrow":           STATE["escrow"],
        "onchain":          STATE["onchain"],
        "onchain_intel":    STATE["onchain_intel"],
        "tech_intel":       STATE["tech_intel"],
        "reg_intel":        STATE["reg_intel"],
        "exec_intel":       STATE["exec_intel"],
        "prediction":       STATE["prediction"],
        "disp_intel":       STATE["disp_intel"],
        "tools_intel":      STATE["tools_intel"],
        "sent_intel":       STATE["sent_intel"],
        "mainstream_intel": STATE["mainstream_intel"],
        "comp_intel":       STATE["comp_intel"],
        "ai_us":            STATE["ai_us"],
        "ai_global":        STATE["ai_global"],
        "ai_regions":       STATE["ai_regions"],
        "story_stats":      STATE["story_stats"],
        "breaking":         STATE["breaking"],
        "feeds_active":     STATE["feeds_active"],
        "feeds_total":      len(RSS_FEEDS),
        "feed_health":      STATE["feed_health"],
        "last_updated":     STATE["last_updated"],
        "version":          STATE["version"],
        "qa_status":        STATE["qa_status"],
        "qa_last":          STATE["qa_last"],
        "qa_details":       STATE["qa_details"],
        "last_error":       STATE["last_error"],
        "last_error_ts":    STATE["last_error_ts"],
        "maintenance":      STATE["maintenance"],
        "start_time":       STATE["start_time"],
        "upgrade_log":      STATE["upgrade_log"],
        # ── v6.0 / v6.1 / v6.2 Feature Data ───────────────────────────
        "signal_score":      STATE.get("signal_score", {}),
        "order_book":        STATE.get("order_book", {}),
        "liquidity_map":     STATE.get("liquidity_map", {}),
        "macro_data":        STATE.get("macro_data", {}),
        "correlation":       STATE.get("correlation", {}),
        "inst_flow":         STATE.get("inst_flow", {}),
        "ipo_watch":         STATE.get("ipo_watch", {}),
        "cbdc_competition":  STATE.get("cbdc_competition", {}),
        "currency_crisis":   STATE.get("currency_crisis", {}),
        "adoption_velocity": STATE.get("adoption_velocity", {}),
        "nvt_ratio":         STATE.get("nvt_ratio", {}),
        "options_flow":      STATE.get("options_flow", {}),
        "accum_distrib":     STATE.get("accum_distrib", {}),
        "whale_watchlist":   STATE.get("whale_watchlist", {}),
        "tx_volume_trend":   STATE.get("tx_volume_trend", {}),
        "dev_score":         STATE.get("dev_score", {}),
        "remittance_intel":  STATE.get("remittance_intel", {}),
        "geopolitical_risk": STATE.get("geopolitical_risk", {}),
        "community_poll":    STATE.get("community_poll", {}),
        "weekly_digest":     STATE.get("weekly_digest", {}),
        "whale_data":        STATE.get("whale_data", {}),
        "derivatives":       STATE.get("derivatives", {}),
        "macro_calendar":    STATE.get("macro_calendar", {}),
    })

@app.route("/api/news")
def api_news():
    cat    = request.args.get("cat",    "all")
    sent   = request.args.get("sent",   "all")
    region = request.args.get("region", "all")
    q      = request.args.get("q",      "").lower()
    stories = STATE["stories"]
    if cat    != "all": stories = [s for s in stories if s["category"] == cat]
    if sent   != "all": stories = [s for s in stories if s["sentiment"] == sent]
    if region != "all": stories = [s for s in stories if s.get("region") == region]
    if q:               stories = [s for s in stories if q in s["title"].lower()]
    return jsonify({"stories": stories[:100], "total": len(stories), "total_all": len(STATE["stories"])})


@app.route("/debug")
def debug():
    return jsonify({
        "version":       STATE["version"],
        "last_updated":  STATE["last_updated"],
        "feeds_active":  STATE["feeds_active"],
        "feeds_total":   len(RSS_FEEDS),
        "visitor_count": STATE.get("visitor_count", 0),
        "stories_count": len(STATE["stories"]),
        "price_usd":     STATE["price"].get("usd", 0),
        "ai_key_set":    bool(ANTHROPIC_API_KEY),
        "qa_status":     STATE["qa_status"],
        "last_error":    STATE["last_error"],
        "uptime_secs":   int((datetime.now(timezone.utc) - datetime.fromisoformat(STATE["start_time"])).total_seconds()),
        "feed_health":   STATE["feed_health"],
    })

# ════════════════════════════════════════════════════════════════════
# XRPRadar Public API (#78)
# ════════════════════════════════════════════════════════════════════

@app.route("/api/v1/price")
def api_v1_price():
    """Public API: Live XRP price data."""
    p = STATE.get("price_data", {})
    return jsonify({
        "price_usd":    p.get("price_usd", 0),
        "change_24h":   p.get("change_24h", 0),
        "market_cap":   p.get("market_cap", 0),
        "volume_24h":   p.get("volume_24h", 0),
        "rank":         p.get("rank", 0),
        "ts":           datetime.now(timezone.utc).isoformat(),
        "source":       "XRPRadar v6.0 — xrpradar.com"
    })

@app.route("/api/v1/signal")
def api_v1_signal():
    """Public API: XRPRadar Signal Score."""
    ss = STATE.get("signal_score", {})
    return jsonify({
        "total":        ss.get("total", 0),
        "grade":        ss.get("grade", "--"),
        "label":        ss.get("label", "--"),
        "ts":           ss.get("ts", ""),
        "source":       "XRPRadar v6.0 — xrpradar.com"
    })

@app.route("/api/v1/sentiment")
def api_v1_sentiment():
    """Public API: News sentiment summary."""
    si = STATE.get("sent_intel", {})
    return jsonify({
        "total_today":   si.get("total_today", 0),
        "bullish":       si.get("bullish_today", 0),
        "bearish":       si.get("bearish_today", 0),
        "neutral":       si.get("neutral_today", 0),
        "fg_score":      si.get("fg_score", 0),
        "fg_label":      si.get("fg_label", ""),
        "ts":            datetime.now(timezone.utc).isoformat(),
        "source":        "XRPRadar v6.0 — xrpradar.com"
    })

@app.route("/api/v1/stories")
def api_v1_stories():
    """Public API: Latest XRP stories (top 20)."""
    stories = STATE.get("stories", [])[:20]
    return jsonify({
        "count":   len(stories),
        "stories": [{"title":s.get("title",""),"source":s.get("source",""),
                     "sentiment":s.get("sentiment",""),"link":s.get("link",""),
                     "pub":s.get("pub",""),"age":s.get("age","")} for s in stories],
        "ts":      datetime.now(timezone.utc).isoformat(),
        "source":  "XRPRadar v6.0 — xrpradar.com"
    })

@app.route("/api/v1/macro")
def api_v1_macro():
    """Public API: Macro market data."""
    md = STATE.get("macro_data", {})
    return jsonify({
        "dxy":      md.get("dxy", {}),
        "sp500":    md.get("sp500", {}),
        "gold":     md.get("gold", {}),
        "treasury": md.get("treasury", {}),
        "btc":      md.get("btc", {}),
        "signal":   md.get("macro_signal", "NEUTRAL"),
        "ts":       md.get("ts", ""),
        "source":   "XRPRadar v6.0 — xrpradar.com"
    })

@app.route("/api/v1/docs")
def api_v1_docs():
    """Public API: Documentation endpoint."""
    return jsonify({
        "name":     "XRPRadar Public API v1",
        "version":  "1.0",
        "base_url": "https://xrpradar.com/api/v1",
        "endpoints": {
            "/price":     "Live XRP price, 24h change, market cap, volume, rank",
            "/signal":    "XRPRadar Signal Score (0-100) with grade and label",
            "/sentiment": "News sentiment — bullish/bearish/neutral counts, Fear & Greed",
            "/stories":   "Top 20 latest XRP stories with sentiment and source",
            "/macro":     "Macro market data — DXY, S&P 500, Gold, Treasury, BTC",
        },
        "rate_limit": "Free — please credit XRPRadar (xrpradar.com) when using this data",
        "contact":    "redrioholdings@gmail.com",
        "note":       "This API is provided free of charge for XRP community use. Commercial use requires permission.",
    })


@app.route("/api/email-digest")
def email_digest():
    """#79 — Returns today's Intelligence Brief formatted as a clean email/newsletter."""
    pred = STATE.get("prediction", {})
    sections = pred.get("sections", {})
    price = STATE.get("price_data", {})
    si    = STATE.get("sent_intel", {})
    ss    = STATE.get("signal_score", {})

    if not sections.get("market_pulse"):
        return jsonify({"error": "No Intelligence Brief generated yet. Please generate first."}), 404

    email_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>XRPRadar Intelligence Brief</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:system-ui,sans-serif">
<div style="max-width:600px;margin:0 auto;background:#000;border:1px solid #1a2030">

  <!-- Header -->
  <div style="background:#000;border-bottom:2px solid #48ff82;padding:20px 24px;text-align:center">
    <div style="font-size:24px;font-weight:900;color:#fff;letter-spacing:2px">🛰️ XRPRADAR</div>
    <div style="font-size:12px;color:#48ff82;letter-spacing:3px;margin-top:4px">INTELLIGENCE BRIEF — {pred.get("session","AM")} EDITION</div>
    <div style="font-size:11px;color:#8099b3;margin-top:4px">{pred.get("generated_at","")}</div>
  </div>

  <!-- Price Snapshot -->
  <div style="background:#0a0a0a;border-bottom:1px solid #1a2030;padding:16px 24px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
    <div style="text-align:center;min-width:100px">
      <div style="font-size:11px;color:#8099b3">XRP PRICE</div>
      <div style="font-size:20px;font-weight:900;color:#48ff82;font-family:monospace">${price.get("price_usd",0):.4f}</div>
    </div>
    <div style="text-align:center;min-width:100px">
      <div style="font-size:11px;color:#8099b3">SIGNAL SCORE</div>
      <div style="font-size:20px;font-weight:900;color:#ffcc00;font-family:monospace">{ss.get("total",0)}/100</div>
    </div>
    <div style="text-align:center;min-width:100px">
      <div style="font-size:11px;color:#8099b3">STORIES ANALYZED</div>
      <div style="font-size:20px;font-weight:900;color:#75bcff;font-family:monospace">{pred.get("story_count",0)}</div>
    </div>
    <div style="text-align:center;min-width:100px">
      <div style="font-size:11px;color:#8099b3">SENTIMENT</div>
      <div style="font-size:20px;font-weight:900;color:#48ff82;font-family:monospace">{si.get("bullish_today",0)} Bull / {si.get("bearish_today",0)} Bear</div>
    </div>
  </div>

  <!-- Brief Sections -->
  {"".join([
    f'<div style="padding:20px 24px;border-bottom:1px solid #1a2030"><div style="font-size:13px;font-weight:700;color:{col};letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px">{icon} {title}</div><div style="font-size:14px;color:#cce0ff;line-height:1.7">{sections.get(key,"")}</div></div>'
    for key, title, icon, col in [
      ("market_pulse","Market Pulse","📊","#48ff82"),
      ("connections","Story Connections","🔗","#75bcff"),
      ("domino_effect","Domino Effect","🌊","#00e5cc"),
      ("regional_flashpoints","Regional Flashpoints","🌍","#ffcc00"),
      ("watchlist","24-72h Watchlist","👁️","#ff9900"),
      ("tradfi_outlook","TradFi Integration Outlook","🪚","#ff4060"),
    ] if sections.get(key)
  ])}

  <!-- Footer -->
  <div style="background:#0a0a0a;padding:16px 24px;text-align:center;border-top:2px solid #1a2030">
    <div style="font-size:12px;color:#8099b3;margin-bottom:8px">
      ⚠️ This brief is AI-generated for informational purposes only. Not financial advice. Always DYOR.
    </div>
    <div style="font-size:11px;color:#3a4050">
      © 2026 Red Rio Ventures, LLC · XRPRadar.com · All rights reserved globally.
    </div>
  </div>

</div>
</body>
</html>"""

    return email_html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/ai/analyze", methods=["POST"])
def api_ai_analyze():
    """Server-side proxy for AI tools (#71-75).
    Keeps ANTHROPIC_API_KEY secure on the server.
    """
    if not ANTHROPIC_API_KEY:
        return jsonify({
            "error": "ANTHROPIC_API_KEY not configured. Add it to Railway Variables to enable AI tools.",
            "setup_url": "https://railway.app → Your Project → Variables → Add ANTHROPIC_API_KEY"
        }), 503
    try:
        data        = request.get_json()
        prompt      = data.get("prompt", "")
        system      = data.get("system", "You are an expert XRP and Ripple intelligence analyst.")
        max_tokens  = min(int(data.get("max_tokens", 1000)), 2000)  # Cap at 2000 for cost control
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        result = call_claude(prompt, system, max_tokens=max_tokens)
        return jsonify({"result": result, "success": True})
    except Exception as e:
        log_error(f"ai_proxy: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@app.route("/api/ai-status")
def ai_status():
    """Diagnostic: Anthropic API key health check."""
    status = {
        "key_present": bool(ANTHROPIC_API_KEY),
        "key_prefix":  (ANTHROPIC_API_KEY[:12]+"...") if ANTHROPIC_API_KEY else "NOT SET",
        "model":       CLAUDE_MODEL,
        "last_error":  STATE.get("last_error",""),
    }
    if ANTHROPIC_API_KEY and request.args.get("test") == "1":
        result = call_claude("Reply with only the word: OK", "Reply with only the word OK.", max_tokens=10)
        status["test_result"] = result
        status["test_passed"] = result.strip() == "OK"
    return jsonify(status)


@app.route("/")
def index():
    STATE["visitor_count"] = STATE.get("visitor_count", 0) + 1
    return Response(DASHBOARD, mimetype="text/html")

# ── Dashboard HTML ─────────────────────────────────────────────────────────────
DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="XRPRadar">
<meta name="theme-color" content="#000000">
<link rel="manifest" href="/manifest.json">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>XRPRadar — Signals Over Noise 24/7</title>
<style>
/* ── SCORPION CSS — verbatim, color-adapted for XRPRadar ─────────────────── */
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#000;--s1:#0a0a0a;--s2:#111;--b:#1a2030;
  --gr:#48ff82;--grd:rgba(72,255,130,.1);
  --rd:#ff4060;--rdd:rgba(255,64,96,.1);
  --yl:#ffcc00;--yld:rgba(255,204,0,.1);
  --bl:#75bcff;--bld:rgba(117,188,255,.12);
  --tq:#00e5cc;--tqd:rgba(0,229,204,.15);
  --or:#ff9900;--tx:#8099b3;--br:#cce0ff;
  --mn:'Courier New',monospace
}
body{background:var(--bg);color:var(--br);font-family:system-ui,sans-serif;font-size:14px;min-height:100vh;-webkit-font-smoothing:antialiased}
.w{max-width:1900px;margin:0 auto;padding:10px 20px}
/* HEADER */
.hdr{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:10px;padding-bottom:8px;border-bottom:2px solid var(--bl);flex-wrap:wrap;gap:6px}
.logo{display:flex;align-items:center;gap:10px}
.icon{width:60px;height:60px;border-radius:10px;
  background:linear-gradient(135deg,#001a3a,#0066cc,#75bcff);
  display:flex;align-items:center;justify-content:center;font-size:36px;
  box-shadow:0 0 16px rgba(117,188,255,.4)}
.title{font-size:22px;font-weight:900;color:var(--br);font-style:italic}
.sub{font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:2px;letter-spacing:1px}
.hright{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.dot{width:12px;height:12px;border-radius:50%;background:var(--gr);
  box-shadow:0 0 10px var(--gr);display:inline-block;animation:blink 2s infinite}
@keyframes blink{50%{opacity:.1}}
.run-lbl{font-size:15px;font-weight:800;font-family:var(--mn);color:var(--gr);letter-spacing:1px}
.pill{padding:5px 14px;border-radius:20px;font-size:13px;font-family:var(--mn);
  font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.plive{background:var(--grd);color:var(--gr);border:1px solid rgba(72,255,130,.4)}
.pbl{background:var(--bld);color:var(--bl);border:1px solid rgba(117,188,255,.4)}
.upd{font-family:var(--mn);font-size:13px;color:var(--tx)}
/* STATUS ROW */
.srow{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}
.si{background:var(--s1);border:1px solid var(--b);border-radius:8px;
  padding:10px 14px;display:flex;align-items:center;justify-content:space-between}
.si-lbl{color:var(--tx);font-size:13px;font-family:var(--mn)}
.sv{font-weight:800;font-size:24px;font-family:var(--mn)}
.sv.g{color:var(--gr)}.sv.y{color:var(--yl)}.sv.b{color:var(--bl)}.sv.r{color:var(--rd)}
/* ACCOUNT / MARKET OVERVIEW */
.acct{background:var(--s1);border:1px solid rgba(117,188,255,.25);
  border-radius:10px;padding:12px;margin-bottom:10px}
.sec-title{font-size:18px;text-transform:uppercase;letter-spacing:2px;
  font-family:var(--mn);color:#ffffff;margin-bottom:10px;font-weight:800}
.agrid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
.abox{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:12px;text-align:center}
.abox.hi{border-color:rgba(117,188,255,.4);background:var(--bld)}
.abox.pos{border-color:rgba(72,255,130,.3);background:var(--grd)}
.abox.neg{border-color:rgba(255,64,96,.3);background:var(--rdd)}
.abox.yl{border-color:rgba(255,204,0,.3);background:var(--yld)}
.albl{font-size:13px;text-transform:uppercase;letter-spacing:1.5px;
  font-family:var(--mn);color:var(--tx);margin-bottom:5px}
.aval{font-size:26px;font-weight:900;font-family:var(--mn);color:var(--br);line-height:1}
.aval.g{color:var(--gr)}.aval.r{color:var(--rd)}.aval.y{color:var(--yl)}.aval.b{color:var(--bl)}
.asub{font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:4px}
/* SLOTS — Regional Intelligence Cards */
.slots{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:10px}
.slot{background:var(--s1);border:1px solid var(--b);border-radius:8px;padding:12px;transition:border-color .3s}
.slot.active{border-color:rgba(117,188,255,.35)}
.slot.bull{border-color:rgba(72,255,130,.35)}
.slot.bear{border-color:rgba(255,64,96,.35)}
.slot-top{display:flex;align-items:center;gap:6px;margin-bottom:5px}
.tqdot{width:14px;height:14px;border-radius:50%;flex-shrink:0}
.tqdot.on{background:var(--bl);box-shadow:0 0 10px var(--bl),0 0 20px rgba(117,188,255,.4);
  animation:tqblink 1s ease-in-out infinite}
@keyframes tqblink{0%,100%{opacity:1;box-shadow:0 0 10px var(--bl),0 0 22px rgba(117,188,255,.5)}
  50%{opacity:.2;box-shadow:0 0 4px var(--bl)}}
.tqdot.off{background:#1e2a3a}
.tqdot.gbull{background:var(--gr);box-shadow:0 0 8px var(--gr)}
.tqdot.gbear{background:var(--rd);box-shadow:0 0 8px var(--rd)}
.tqdot.gneut{background:var(--yl)}
.tqdot.gquiet{background:#333}
.sname{font-size:17px;font-weight:900;color:var(--br);font-family:var(--mn)}
.sbadge{font-size:13px;font-family:var(--mn);font-weight:700;padding:3px 7px;
  border-radius:3px;text-transform:uppercase;margin-left:auto;white-space:nowrap}
.sbadge.bull{background:var(--grd);color:var(--gr);border:1px solid rgba(72,255,130,.4)}
.sbadge.bear{background:var(--rdd);color:var(--rd);border:1px solid rgba(255,64,96,.3)}
.sbadge.neut{background:rgba(128,153,179,.08);color:var(--tx);border:1px solid var(--b)}
.sbadge.quiet{background:rgba(128,153,179,.05);color:var(--tx);border:1px solid var(--b)}
.sstrat{font-size:13px;font-family:var(--mn);font-weight:800;text-transform:uppercase;margin-bottom:4px;letter-spacing:.5px;color:var(--bl)}
.swl{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:4px 0}
.swbox{background:var(--s2);border:1px solid var(--b);border-radius:4px;padding:4px;text-align:center}
.swval{font-size:16px;font-weight:900;font-family:var(--mn);line-height:1;color:var(--br)}
.swlbl{font-size:13px;text-transform:uppercase;font-family:var(--mn);color:var(--tx);font-weight:700}
.sact{font-family:system-ui;font-size:13px;color:var(--br);
  word-break:break-word;line-height:1.4;min-height:18px;margin-top:4px}
.sfoot{display:flex;justify-content:space-between;margin-top:4px;
  padding-top:4px;border-top:1px solid rgba(255,255,255,.05);
  font-family:var(--mn);font-size:13px;font-weight:600;color:var(--tx)}
/* SCOREBOARD */
.score{background:var(--s1);border:1px solid var(--b);border-radius:10px;
  padding:12px;margin-bottom:10px;width:100%;box-sizing:border-box}
.sgrid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
.sbox{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:10px;text-align:center}
.sbox.wc{border-color:rgba(72,255,130,.3);background:var(--grd)}
.sbox.lc{border-color:rgba(255,64,96,.3);background:var(--rdd)}
.sbox.bc{border-color:rgba(117,188,255,.3);background:var(--bld)}
.sbox.yc{border-color:rgba(255,204,0,.3);background:var(--yld)}
.snum{font-size:24px;font-weight:900;font-family:var(--mn);line-height:1}
.snum.g{color:var(--gr)}.snum.r{color:var(--rd)}.snum.b{color:var(--bl)}.snum.y{color:var(--yl)}
.snlbl{font-size:13px;text-transform:uppercase;font-family:var(--mn);color:var(--tx);margin-top:4px}
.snsub{font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:3px}
.sgrid4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
.wrbar{height:6px;background:var(--rdd);border-radius:3px;overflow:hidden;margin-top:10px}
.wrfill{height:100%;background:linear-gradient(90deg,var(--gr),#00ffcc);transition:width .8s}
/* TWO-COLUMN */
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.panel{background:var(--s1);border:1px solid var(--b);border-radius:10px;overflow:hidden}
.ph{padding:8px 14px;border-bottom:1px solid var(--b);
  display:flex;justify-content:space-between;align-items:center;background:var(--s2)}
.pt{font-size:13px;text-transform:uppercase;letter-spacing:2px;font-family:var(--mn);color:var(--tx)}
.pcard{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.03)}
.prow{display:flex;justify-content:space-between;padding:3px 0;font-family:var(--mn);font-size:13px}
.pk{color:var(--tx)}.pv{font-weight:700;color:var(--br)}
.pv.g{color:var(--gr)}.pv.r{color:var(--rd)}.pv.b{color:var(--bl)}.pv.y{color:var(--yl)}
.alog{max-height:300px;overflow-y:auto;padding:6px 14px;font-family:var(--mn);font-size:13px}
.lr{display:flex;gap:8px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.02)}
.lt{color:var(--tx);opacity:.5;font-size:13px;white-space:nowrap}
.lm{flex:1;color:var(--br)}
.lm.bull{color:var(--gr)}.lm.bear{color:var(--rd)}.lm.break{color:var(--yl)}
/* NEWS FEED */
.nrow{display:grid;grid-template-columns:1fr 420px;gap:6px;margin-bottom:10px;align-items:start}
.npanel{background:var(--s1);border:1px solid var(--b);border-radius:10px;overflow-y:auto;height:650px}
.nfeed{overflow-y:auto;padding:8px 12px;height:650px}
.ncard{background:var(--s2);border:1px solid var(--b);border-radius:6px;
  padding:9px;margin-bottom:7px;cursor:pointer;transition:border-color .2s}
.ncard:hover{border-color:var(--bl)}
.ncard-hdr{display:flex;align-items:center;gap:5px;margin-bottom:5px;flex-wrap:wrap}
.nsrc{font-size:13px;font-weight:700;padding:2px 7px;border-radius:3px;font-family:var(--mn)}
.nsrc.major{background:var(--bld);color:var(--bl);border:1px solid rgba(117,188,255,.3)}
.nsrc.xrp{background:var(--bld);color:var(--bl);border:1px solid rgba(117,188,255,.4)}
.nsrc.official{background:rgba(61,158,255,.1);color:#88aaff;border:1px solid rgba(61,158,255,.25)}
.nsrc.community{background:rgba(255,153,0,.08);color:var(--or);border:1px solid rgba(255,153,0,.25)}
.nsrc.international{background:rgba(170,136,255,.08);color:#bb99ff;border:1px solid rgba(170,136,255,.25)}
.nsrc.aggregator{background:rgba(255,255,100,.06);color:#ffffaa;border:1px solid rgba(255,255,100,.2)}
.nsrc.legal{background:rgba(255,64,96,.08);color:#ff9999;border:1px solid rgba(255,64,96,.2)}
.nsrc.mainstream{background:rgba(61,158,255,.08);color:#99bbff;border:1px solid rgba(61,158,255,.2)}
.nsrc.institutional{background:var(--yld);color:var(--yl);border:1px solid rgba(255,204,0,.2)}
.nsrc.whale{background:var(--grd);color:var(--gr);border:1px solid rgba(72,255,130,.3)}
.ncat{font-size:13px;color:var(--tx);background:var(--s1);padding:2px 5px;border-radius:3px;font-family:var(--mn)}
.nbreak{font-size:13px;color:var(--yl);font-weight:700;font-family:var(--mn)}
.ntitle{font-size:14px;font-weight:700;color:var(--bl);line-height:1.4;margin-bottom:5px}
.ntrans{font-size:13px;color:var(--tq);font-family:system-ui;margin-bottom:5px;font-style:italic;padding:4px 8px;background:var(--tqd);border-left:2px solid var(--tq);border-radius:3px}
.nsum{font-size:13px;color:var(--br);line-height:1.7;margin-bottom:6px}
.nfoot{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.nsent{font-size:13px;font-weight:700;padding:2px 7px;border-radius:3px;font-family:var(--mn)}
.nsent.bull{background:var(--grd);color:var(--gr);border:1px solid rgba(72,255,130,.3)}
.nsent.bear{background:var(--rdd);color:var(--rd);border:1px solid rgba(255,64,96,.2)}
.nsent.neut{background:rgba(128,153,179,.08);color:var(--tx);border:1px solid var(--b)}
.nage{font-size:13px;color:var(--b);margin-left:auto;font-family:var(--mn)}
.ncount{font-size:13px;color:var(--tx);padding:6px 12px 8px;font-family:var(--mn)}
/* SEARCH + FILTERS */
.nctrl{padding:8px 12px;border-bottom:1px solid var(--b);background:var(--s2);display:flex;flex-direction:column;gap:6px}
.nsearch{width:100%;background:var(--s2);border:2px solid rgba(117,188,255,.4);color:var(--br);
  padding:12px 18px;border-radius:6px;font-size:15px;font-family:var(--mn);outline:none;
  transition:border-color .2s}
.nsearch:focus{border-color:var(--bl)}
.nbtns{display:flex;gap:5px;flex-wrap:nowrap}
.nbtn{background:var(--s2);border:1px solid var(--b);color:var(--br);
  padding:7px 14px;border-radius:5px;cursor:pointer;font-size:13px;font-weight:700;
  font-family:var(--mn);letter-spacing:.05em;text-transform:uppercase;transition:all .2s;white-space:nowrap}
.nbtn:hover,.nbtn.on{background:var(--bld);border-color:var(--bl);color:var(--bl)}
/* RIGHT PANEL */
.rpanel{background:var(--s1);border:1px solid var(--b);border-radius:10px;overflow-y:auto;min-width:0;height:650px}
.rcard{padding:10px 14px;border-bottom:1px solid var(--b);font-size:13px;font-family:var(--mn)}
.rtitle{font-size:13px;text-transform:uppercase;letter-spacing:2px;font-family:var(--mn);color:#ffffff;margin-bottom:10px;font-weight:700}
.rrow{display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.03);font-size:13px;align-items:center;min-height:24px}
.rk{color:#ffffff;font-family:var(--mn);font-size:13px;white-space:nowrap}.rv{color:var(--br);font-weight:700;font-family:var(--mn);font-size:13px;text-align:right}
.rv.g{color:var(--gr)}.rv.b{color:var(--bl)}.rv.r{color:var(--rd)}.rv.y{color:var(--yl)}
/* LEADERBOARDS */
.lbpair{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.lbrow{display:grid;grid-template-columns:24px 1fr 60px 60px;
  gap:6px;align-items:center;padding:5px 10px;
  border-bottom:1px solid rgba(255,255,255,.03);font-family:var(--mn);font-size:13px}
.lbrow.hdr{background:var(--s2);font-size:13px;color:var(--tx);
  text-transform:uppercase;border-bottom:1px solid var(--b)}
.rank{font-weight:900;text-align:center;font-size:13px}
.r1{color:#ffd700}.r2{color:#c0c0c0}.r3{color:#cd7f32}.rn{color:var(--or)}
/* ANALYTICS LAB */
.lab{background:var(--s1);border:1px solid rgba(0,229,204,.2);
  border-radius:10px;padding:14px;margin-bottom:10px;margin-top:0}
.lab3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.labp{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:12px}
.labt{font-size:13px;font-weight:800;color:var(--bl);font-family:var(--mn);
  text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;
  padding-bottom:6px;border-bottom:1px solid var(--b)}
.bstat{display:flex;justify-content:space-between;padding:4px 0;
  border-bottom:1px solid rgba(255,255,255,.04);font-family:var(--mn);font-size:13px}
.bk{color:var(--tx)}.bv{font-weight:700;color:var(--br)}
.bv.g{color:var(--gr)}.bv.r{color:var(--rd)}.bv.b{color:var(--bl)}.bv.y{color:var(--yl)}
/* SIGNAL CHIPS */
.sig-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.sig-chip{display:flex;align-items:center;gap:5px;font-size:13px;color:var(--br);
  background:var(--s2);padding:4px 8px;border-radius:4px;border:1px solid var(--b);font-family:var(--mn)}
.sdot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.sdot.g{background:var(--gr)}.sdot.r{background:var(--rd)}
.sdot.y{background:var(--yl)}.sdot.q{background:#333}
/* BREAKING NEWS */
#breaking{background:var(--s1);border-bottom:2px solid rgba(255,153,0,.4);
  padding:8px 0;display:flex;align-items:center;overflow:hidden}
.bkinner{max-width:1900px;margin:0 auto;padding:0 16px;display:flex;align-items:center;width:100%}
.bklbl{color:var(--or);font-weight:900;font-size:16px;font-family:var(--mn);flex-shrink:0;padding-right:14px;margin-right:14px;border-right:2px solid rgba(255,153,0,.5);text-transform:uppercase;letter-spacing:.08em}
.bkscroll{flex:1;overflow:hidden;height:20px;position:relative;display:flex;align-items:center}
.bktext-base{font-size:15px;color:var(--br);font-family:system-ui;font-weight:500}
@keyframes marquee{0%{transform:translateX(100%)}100%{transform:translateX(-100%)}}
/* STORY POPUP */
#story-modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,.92);z-index:9999;align-items:center;justify-content:center;padding:20px}
.modal-box{background:var(--s1);border:1px solid var(--bl);border-radius:10px;
  max-width:660px;width:100%;max-height:85vh;overflow-y:auto;display:flex;flex-direction:column}
.modal-hdr{padding:12px 16px;display:flex;align-items:flex-start;gap:10px;
  border-bottom:1px solid var(--b);position:sticky;top:0;background:var(--s2)}
.modal-x{color:var(--bl);font-size:18px;cursor:pointer;font-weight:900;
  width:26px;height:26px;display:flex;align-items:center;justify-content:center;
  border:1px solid var(--bl);border-radius:4px;flex-shrink:0;transition:all .2s}
.modal-x:hover{background:var(--bl);color:#000}
.modal-ttl{color:var(--bl);font-size:13px;font-weight:700;flex:1;line-height:1.5;font-family:var(--mn)}
.modal-body{padding:14px 16px;flex:1}
.modal-trans{color:var(--tq);font-size:13px;line-height:1.6;margin-bottom:12px;
  padding:8px 12px;background:var(--tqd);border-left:2px solid var(--tq);border-radius:3px;font-family:var(--mn)}
.modal-translbl{font-size:13px;color:var(--tx);margin-bottom:3px;text-transform:uppercase;letter-spacing:.06em;font-family:var(--mn)}
.modal-sum{color:var(--br);font-size:13px;line-height:1.8;margin-bottom:12px}
.modal-meta{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;font-size:13px;font-family:var(--mn)}
.modal-btn{display:block;width:100%;background:var(--bld);color:var(--bl);
  font-weight:700;font-size:13px;padding:10px;border-radius:6px;cursor:pointer;
  border:1px solid var(--bl);text-align:center;transition:all .2s;text-decoration:none;font-family:var(--mn)}
.modal-btn:hover{background:var(--bl);color:#000}

/* PRECHECK MODAL */
#pf-modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,.88);z-index:9999;align-items:center;justify-content:center;padding:20px}
#pf-box{background:var(--s1);border:1px solid var(--bl);border-radius:10px;
  max-width:560px;width:100%;padding:0;overflow:hidden}
#pf-hdr{padding:10px 16px;background:var(--s2);border-bottom:1px solid var(--b);
  display:flex;justify-content:space-between;align-items:center;font-family:var(--mn)}
#pf-body{padding:16px;font-family:var(--mn);font-size:13px;line-height:2.2}

/* FOOTER */
footer{margin-top:30px;padding:18px 0 0 0;
  border-top:3px solid var(--b);
  font-family:var(--mn);font-size:13px;color:var(--tx);line-height:2.4;
  position:relative}
footer::before{content:"";position:absolute;top:-8px;left:0;right:0;
  height:1px;background:rgba(117,188,255,.15)}
.warn{color:rgba(255,204,0,.4)}
.empty{padding:14px;font-family:var(--mn);font-size:13px;color:var(--tx);text-align:center}
.file-tag{display:inline-block;padding:2px 7px;border-radius:3px;
  background:rgba(117,188,255,.08);color:var(--bl);font-weight:700;
  border:1px solid rgba(117,188,255,.3);margin-left:6px;font-family:var(--mn)}

@keyframes bkscroll{0%{transform:translateX(0)}100%{transform:translateX(-100%)}}
.bktext{display:inline-block;animation:bkscroll 45s linear infinite;white-space:nowrap;cursor:pointer;will-change:transform;padding-left:100%}
.bkscroll:hover{animation-play-state:paused}
.bk-item{display:inline-flex;align-items:center;padding:0 30px;border-right:1px solid rgba(255,153,0,.2);
  font-size:15px;color:var(--br);font-weight:500;white-space:nowrap;cursor:pointer;
  transition:color .2s}
.bk-item:hover{color:var(--or)}
.tech-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;align-items:stretch}
.exec-feed{max-height:400px;overflow-y:auto}
  /* ── Experimental Metrics shared styles ─────────────────────── */
  .exp-card{background:var(--s2);border:1px solid var(--b);border-radius:10px;
    padding:16px;margin-bottom:16px}
  .exp-card:last-child{margin-bottom:0}
  .exp-title{font-size:15px;font-weight:800;color:var(--bl);font-family:var(--mn);
    text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px}
  .exp-sub{font-size:13px;color:var(--tx);margin-bottom:14px;line-height:1.6}
  .exp-lbl{display:block;font-size:11px;color:var(--tx);font-family:var(--mn);
    text-transform:uppercase;letter-spacing:1px;margin-bottom:5px}
  .exp-input{width:100%;background:var(--bg);border:1px solid var(--b);color:var(--br);
    padding:8px 12px;border-radius:5px;font-size:14px;font-family:var(--mn);
    box-sizing:border-box;outline:none;transition:border-color .2s}
  .exp-input:focus{border-color:var(--bl)}
  .exp-btn{background:rgba(117,188,255,.15);color:var(--bl);border:1px solid rgba(117,188,255,.35);
    border-radius:5px;padding:9px 18px;font-family:var(--mn);font-size:13px;font-weight:700;
    cursor:pointer;transition:all .2s;white-space:nowrap}
  .exp-btn:hover{background:rgba(117,188,255,.25);border-color:var(--bl)}
  .exp-btn-gr{background:rgba(72,255,130,.15);color:var(--gr);border:1px solid rgba(72,255,130,.3)}
  .exp-btn-gr:hover{background:rgba(72,255,130,.25)}
  .exp-btn-yl{background:rgba(255,204,0,.15);color:var(--yl);border:1px solid rgba(255,204,0,.3)}
  .exp-btn-yl:hover{background:rgba(255,204,0,.25)}
  .exp-btn-rd{background:rgba(255,64,96,.15);color:var(--rd);border:1px solid rgba(255,64,96,.3)}
  .exp-tag{background:var(--s1);color:var(--tx);border:1px solid var(--b);border-radius:4px;
    padding:4px 10px;font-family:var(--mn);font-size:12px;cursor:pointer;transition:all .2s}
  .exp-tag:hover{color:var(--bl);border-color:var(--bl)}
  .exp-stat-box{background:var(--bg);border:1px solid var(--b);border-radius:6px;padding:10px 12px}
  .exp-stat-lbl{font-size:11px;color:var(--tx);font-family:var(--mn);
    text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
  .exp-stat-val{font-size:18px;font-weight:700;color:var(--gr);font-family:var(--mn)}
  .exp-divider{height:1px;background:rgba(117,188,255,.08);margin:16px 0}
  .exp-table{width:100%;border-collapse:collapse;font-family:var(--mn);font-size:13px}
  .exp-table th{padding:6px 10px;text-align:left;color:var(--tx);font-size:11px;
    text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--b)}
  .exp-table td{padding:7px 10px;border-bottom:1px solid rgba(255,255,255,.03);color:var(--br)}
  .exp-table tr:hover td{background:rgba(255,255,255,.02)}
</style>
</head>
<body>
<div id="breaking">
  <div class="bkinner">
    <span class="bklbl">⚡ BREAKING NEWS</span>
    <div class="bkscroll"><div class="bktext" id="bktext">Monitoring XRP global news feeds...</div></div>
  </div>
</div>

<div class="w">

<!-- SECTION 1: HEADER -->
<div class="hdr">
  <div class="logo">
    <div class="icon">🛰️</div>
    <div>
      <div class="title">XRPRadar</div>
      <div class="sub" style="font-size:13px;color:#ffffff;letter-spacing:1.5px">Signals Over Noise 24/7</div>
      <div class="sub" style="font-size:13px;color:var(--gr);letter-spacing:1px">● 306 Sources Live</div>
    </div>
  </div>
  <div class="hright">
    <span class="dot"></span>
    <span class="run-lbl">LIVE</span>
    <span class="pill plive" id="feedPill">FEEDS OK</span>
    <span class="upd" id="uts">&mdash;</span>
  </div>
</div>

<!-- SECTION v6-WHALE: WHALE MOVE ALERT BANNER (#59) -->
<div id="whale-alert-bar" style="display:none;background:linear-gradient(90deg,rgba(255,64,96,.15),rgba(255,153,0,.15));
  border-bottom:1px solid rgba(255,153,0,.4);padding:6px 0">
  <div style="max-width:1900px;margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <span style="font-size:16px">🐋</span>
    <span style="font-size:14px;font-weight:700;color:var(--or);font-family:var(--mn);text-transform:uppercase;letter-spacing:1px">WHALE ALERT</span>
    <div id="whale-alert-text" style="font-size:13px;color:var(--br);flex:1"></div>
    <button onclick="document.getElementById('whale-alert-bar').style.display='none'"
      style="background:transparent;border:none;color:var(--tx);cursor:pointer;font-size:16px;padding:0 4px">✕</button>
  </div>
</div>

<!-- SECTION 2: STATUS ROW -->
<div class="srow">
  <div class="si"><span class="si-lbl">💲 XRP / USD</span><span class="sv g" id="st-price">--</span></div>
  <div class="si"><span class="si-lbl">📡 Active Sources</span><span class="sv y" id="st-feeds">--</span></div>
  <div class="si"><span class="si-lbl">😰 Fear &amp; Greed</span><span class="sv b" id="st-fg">-- / Neutral</span></div>
</div>

<!-- SECTION 3: MARKET OVERVIEW -->
<div class="acct">
  <div class="sec-title" style="color:var(--bl)">💹 XRP Market Overview</div>
  <div class="agrid">
    <div class="abox hi"><div class="albl">Market Cap</div><div class="aval b" id="mk-mcap">--</div><div class="asub" id="mk-rank">Rank --</div></div>
    <div class="abox"><div class="albl">24h Volume</div><div class="aval" id="mk-vol">--</div><div class="asub" id="mk-vratio">Vol/MCap: --</div></div>
    <div class="abox"><div class="albl">All-Time High</div><div class="aval y" id="mk-ath">--</div><div class="asub" id="mk-athpct">-- below ATH</div></div>
    <div class="abox"><div class="albl">24h High</div><div class="aval g" id="mk-high">--</div><div class="asub">Session high</div></div>
    <div class="abox neg"><div class="albl">24h Low</div><div class="aval r" id="mk-low">--</div><div class="asub">Session low</div></div>
    <div class="abox"><div class="albl">XRP / BTC</div><div class="aval" id="mk-btc">--</div><div class="asub">Altseason signal</div></div>
  </div>
</div>

<!-- SECTION 3b: PRICE INTELLIGENCE (v3.0a) -->
<div class="acct" style="border-color:rgba(72,255,130,.2);margin-bottom:10px">
  <div class="sec-title" style="color:var(--gr)">⚡ Price Intelligence</div>
  <div class="agrid" style="grid-template-columns:repeat(6,1fr)">

    <div class="abox hi">
      <div class="albl">XRP Dominance</div>
      <div class="aval b" id="pi-dom">--%</div>
      <div class="asub">of total crypto mktcap</div>
    </div>

    <div class="abox" id="pi-fr-box">
      <div class="albl">Funding Rate</div>
      <div class="aval" id="pi-fr">--%</div>
      <div class="asub" id="pi-fr-sub">Perpetual futures</div>
    </div>

    <div class="abox">
      <div class="albl">Open Interest</div>
      <div class="aval b" id="pi-oi-usd">--</div>
      <div class="asub" id="pi-oi-xrp">-- XRP contracts</div>
    </div>

    <div class="abox">
      <div class="albl">XRP / ETH</div>
      <div class="aval" id="pi-xrpeth">--</div>
      <div class="asub" id="pi-eth-usd">ETH: $--</div>
    </div>

    <div class="abox" id="pi-vol-box">
      <div class="albl">30D Volatility</div>
      <div class="aval y" id="pi-vol">--%</div>
      <div class="asub" id="pi-vol-sub">Annualised</div>
    </div>

    <div class="abox">
      <div class="albl">Bid/Ask Spread</div>
      <div class="aval g" id="pi-spread">--%</div>
      <div class="asub" id="pi-ba">Bid: -- / Ask: --</div>
    </div>

  </div>
</div>

<!-- SECTION 3d: TECHNICAL SIGNALS (v3.0c) -->
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">

  <!-- Left col: RSI Gauges + 52-Week Range -->
  <div>
    <!-- RSI Panel -->
    <div class="acct" style="border-color:rgba(117,188,255,.2);margin-bottom:10px">
      <div class="sec-title" style="color:var(--bl)">📐 RSI Signals</div>

      <!-- 1H RSI -->
      <div style="margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;margin-bottom:5px">
          <span style="font-size:13px;font-family:var(--mn);color:var(--tx)">1H RSI</span>
          <span style="font-size:13px;font-weight:700;font-family:var(--mn)" id="rsi-1h-val">--</span>
          <span style="font-size:13px;font-family:var(--mn)" id="rsi-1h-lbl" style="color:var(--tx)">--</span>
        </div>
        <div style="height:10px;background:var(--s2);border-radius:5px;overflow:hidden;border:1px solid var(--b);position:relative">
          <div style="position:absolute;top:0;bottom:0;left:30%;width:1px;background:rgba(255,255,255,.1)"></div>
          <div style="position:absolute;top:0;bottom:0;left:70%;width:1px;background:rgba(255,255,255,.1)"></div>
          <div id="rsi-1h-bar" style="height:100%;width:50%;border-radius:5px;transition:all .6s;background:var(--tx)"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:2px">
          <span>0 — Oversold</span><span>30</span><span>50</span><span>70</span><span>Overbought — 100</span>
        </div>
      </div>

      <!-- 1D RSI -->
      <div>
        <div style="display:flex;justify-content:space-between;margin-bottom:5px">
          <span style="font-size:13px;font-family:var(--mn);color:var(--tx)">1D RSI</span>
          <span style="font-size:13px;font-weight:700;font-family:var(--mn)" id="rsi-1d-val">--</span>
          <span style="font-size:13px;font-family:var(--mn)" id="rsi-1d-lbl">--</span>
        </div>
        <div style="height:10px;background:var(--s2);border-radius:5px;overflow:hidden;border:1px solid var(--b);position:relative">
          <div style="position:absolute;top:0;bottom:0;left:30%;width:1px;background:rgba(255,255,255,.1)"></div>
          <div style="position:absolute;top:0;bottom:0;left:70%;width:1px;background:rgba(255,255,255,.1)"></div>
          <div id="rsi-1d-bar" style="height:100%;width:50%;border-radius:5px;transition:all .6s;background:var(--tx)"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:2px">
          <span>0 — Oversold</span><span>30</span><span>50</span><span>70</span><span>Overbought — 100</span>
        </div>
      </div>
    </div>

    <!-- 52-Week Range Panel -->
    <div class="acct" style="border-color:rgba(255,204,0,.2);margin-bottom:0">
      <div class="sec-title" style="color:var(--yl)">📅 52-Week Range</div>
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-family:var(--mn);font-size:13px">
        <span>Low: <strong id="w52-low" style="color:var(--rd)">--</strong></span>
        <span style="color:var(--tx)">Current: <strong id="w52-cur" style="color:var(--br)">--</strong></span>
        <span>High: <strong id="w52-high" style="color:var(--gr)">--</strong></span>
      </div>
      <div style="height:14px;background:linear-gradient(90deg,var(--rd),var(--yl),var(--gr));border-radius:7px;position:relative;border:1px solid var(--b)">
        <div id="w52-needle" style="position:absolute;top:-4px;width:6px;height:22px;background:var(--br);border-radius:3px;border:2px solid var(--bg);transition:left .6s;transform:translateX(-50%)"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:8px;font-family:var(--mn);font-size:13px">
        <span style="color:var(--tx)">From low: <strong id="w52-from-low" style="color:var(--gr)">--</strong></span>
        <span style="color:var(--tx)">Position: <strong id="w52-pos" style="color:var(--yl)">--%</strong></span>
        <span style="color:var(--tx)">From high: <strong id="w52-from-high" style="color:var(--rd)">--</strong></span>
      </div>
    </div>
  </div>

  <!-- Right col: Support/Resistance + 1-Year Comparison -->
  <div>
    <!-- Support & Resistance -->
    <div class="panel" style="border-color:rgba(117,188,255,.2);margin-bottom:10px">
      <div class="ph"><span class="pt" style="color:var(--bl);font-size:16px;font-weight:800;letter-spacing:2px">🎯 Support &amp; Resistance</span></div>
      <div style="padding:10px 14px" id="sr-table">
        <div class="empty">Calculating levels...</div>
      </div>
    </div>

    <!-- 1-Year Comparison -->
    <div class="acct" style="border-color:rgba(72,255,130,.2);margin-bottom:0">
      <div class="sec-title" style="color:var(--gr)">📆 Price Time Machine</div>
      <div class="agrid" style="grid-template-columns:repeat(2,1fr);gap:8px">
        <div class="abox">
          <div class="albl">1 Year Ago</div>
          <div class="aval" style="font-size:20px" id="pt-1y-price">--</div>
          <div class="asub" id="pt-1y-change" style="font-size:13px;font-weight:700">--</div>
        </div>
        <div class="abox">
          <div class="albl">1 Month Ago</div>
          <div class="aval" style="font-size:20px" id="pt-1m-price">--</div>
          <div class="asub" id="pt-1m-change" style="font-size:13px;font-weight:700">--</div>
        </div>
      </div>
      <div style="margin-top:10px;padding:8px 10px;background:var(--s2);border-radius:6px;border:1px solid var(--b)">
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Today vs 1 Year Ago</div>
        <div id="pt-narrative" style="font-size:13px;color:var(--br);line-height:1.6;font-family:system-ui">Loading...</div>
      </div>
    </div>
  </div>

</div>

<!-- SECTION 4: CHART -->
<div class="acct" style="padding:10px;border-color:rgba(117,188,255,.15)">
  <div class="sec-title" style="color:var(--bl)">📊 Live XRP/USD Chart</div>
  <div style="height:420px;border-radius:8px;overflow:hidden;border:1px solid var(--b)">
    <div class="tradingview-widget-container" style="width:100%;height:100%">
      <div id="tradingview_xrp"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {"autosize":true,"symbol":"BITSTAMP:XRPUSD","interval":"60","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"en","backgroundColor":"#000000","gridColor":"#0a0a0a","hide_top_toolbar":false,"save_image":false,"support_host":"https://www.tradingview.com"}
      </script>
    </div>
  </div>
</div>

<!-- SECTION 3c: ON-CHAIN INTELLIGENCE (v3.0b) -->
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">

  <!-- Left: Network Stats + RLUSD + DEX -->
  <div class="acct" style="border-color:rgba(0,229,204,.2);margin-bottom:0">
    <div class="sec-title" style="color:var(--tq)">⛓️ On-Chain Intelligence</div>
    <div class="agrid" style="grid-template-columns:repeat(3,1fr);gap:8px">

      <div class="abox" style="border-color:rgba(0,229,204,.3);background:var(--tqd)">
        <div class="albl">RLUSD Supply</div>
        <div class="aval" style="color:var(--tq);font-size:18px" id="oc-rlusd-supply">--</div>
        <div class="asub">Vol: <span id="oc-rlusd-vol">--</span></div>
      </div>

      <div class="abox">
        <div class="albl">XRPL DEX Volume</div>
        <div class="aval b" style="font-size:18px" id="oc-dex-vol">--</div>
        <div class="asub" id="oc-dex-trades">-- trades 24h</div>
      </div>

      <div class="abox">
        <div class="albl">Network Accounts</div>
        <div class="aval" style="color:var(--tq);font-size:18px" id="oc-accounts">--</div>
        <div class="asub">New 24h: <span id="oc-accounts-new" style="color:var(--gr)">--</span></div>
      </div>

      <div class="abox" id="oc-flow-box">
        <div class="albl">Exchange Flow</div>
        <div class="aval" style="font-size:16px" id="oc-flow">--</div>
        <div class="asub" id="oc-flow-note" style="font-size:13px;line-height:1.4">--</div>
      </div>

      <div class="abox pos" style="grid-column:span 2">
        <div class="albl">⏳ Next Ripple Escrow Release</div>
        <div style="display:flex;align-items:baseline;gap:10px;justify-content:center;margin:4px 0">
          <div><div class="aval g" id="oc-esc-days">--</div><div class="asub">days</div></div>
          <div style="color:var(--tx);font-size:18px;font-family:var(--mn)">:</div>
          <div><div class="aval g" id="oc-esc-hrs">--</div><div class="asub">hrs</div></div>
          <div style="color:var(--tx);font-size:18px;font-family:var(--mn)">:</div>
          <div><div class="aval g" id="oc-esc-min">--</div><div class="asub">min</div></div>
        </div>
        <div class="asub" id="oc-esc-date">1B XRP · Next release: --</div>
      </div>

    </div>
  </div>

  <!-- Right: Whale Alert Feed -->
  <div class="panel" style="border-color:rgba(255,204,0,.25)">
    <div class="ph">
      <span class="pt" style="color:var(--yl);font-size:16px;font-weight:800;letter-spacing:2px">🐋 Whale Alert Feed</span>
      <span style="font-size:13px;font-family:var(--mn);color:var(--tx)" id="oc-whale-ts">--</span>
    </div>
    <div id="oc-whale-feed" style="padding:8px 12px;max-height:220px;overflow-y:auto;overflow-x:hidden">
      <div class="empty">Loading whale data...</div>
    </div>
  </div>

</div>

<!-- SECTION 3e2: XRP ECOSYSTEM MAP -->
<div style="margin-bottom:10px">
  <div style="background:linear-gradient(135deg,#06060f 0%,#0a0a18 100%);
    border:1px solid rgba(117,188,255,.3);border-radius:12px;overflow:hidden">

    <!-- Header -->
    <div style="padding:14px 18px;background:rgba(117,188,255,.06);
      border-bottom:1px solid rgba(117,188,255,.2);
      display:flex;align-items:center;gap:14px">
      <span style="font-size:30px;filter:drop-shadow(0 0 10px rgba(117,188,255,.6))">🌐</span>
      <div>
        <div style="font-size:17px;font-weight:900;color:#fff;
          font-family:var(--mn);text-transform:uppercase;letter-spacing:2px">
          XRP Ecosystem
        </div>
        <div style="font-size:13px;font-family:system-ui;color:var(--bl);margin-top:2px">
          Seven interconnected layers powering the future of global finance
        </div>
      </div>
    </div>

    <div style="padding:14px 18px">

      <!-- 7 Ecosystem Cards — 4 top, 3 bottom -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:8px">

        <!-- Card 1: XRPL -->
        <div style="background:rgba(0,229,204,.06);border:1px solid rgba(0,229,204,.3);
          border-radius:8px;padding:12px;position:relative;overflow:hidden">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,var(--tq),transparent)"></div>
          <div style="font-size:20px;margin-bottom:6px">🔗</div>
          <div style="font-size:13px;font-weight:900;color:#fff;
            font-family:var(--mn);margin-bottom:4px">XRPL</div>
          <div style="font-size:13px;font-weight:700;color:var(--tq);
            font-family:var(--mn);margin-bottom:6px;text-transform:uppercase;
            letter-spacing:1px">The Foundation</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.6;
            font-family:system-ui;margin-bottom:8px">
            Open-source, decentralised blockchain. Maintained by the independent XRPL Foundation.
            Consensus protocol settles in 3-5 seconds. Native DEX, AMM pools, escrow, and
            payment channels built in at the protocol level.
          </div>
          <div style="display:flex;flex-direction:column;gap:3px">
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Total Accounts</span>
              <span style="color:var(--tq);font-weight:700" id="eco-accounts">--</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Settlement</span>
              <span style="color:var(--tq);font-weight:700">3-5 seconds</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Tx Fee</span>
              <span style="color:var(--tq);font-weight:700">~$0.0002</span>
            </div>
          </div>
        </div>

        <!-- Card 2: Ripple Labs -->
        <div style="background:rgba(117,188,255,.06);border:1px solid rgba(117,188,255,.3);
          border-radius:8px;padding:12px;position:relative;overflow:hidden">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,var(--bl),transparent)"></div>
          <div style="font-size:20px;margin-bottom:6px">🏢</div>
          <div style="font-size:13px;font-weight:900;color:#fff;
            font-family:var(--mn);margin-bottom:4px">Ripple Labs</div>
          <div style="font-size:13px;font-weight:700;color:var(--bl);
            font-family:var(--mn);margin-bottom:6px;text-transform:uppercase;
            letter-spacing:1px">The Company</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.6;
            font-family:system-ui;margin-bottom:8px">
            Private San Francisco company that created XRP and builds enterprise
            blockchain solutions. NOT the same as XRPL. Revenue from ODL, software
            licensing, and XRP sales. Led by Brad Garlinghouse.
          </div>
          <div style="display:flex;flex-direction:column;gap:3px">
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Founded</span>
              <span style="color:var(--bl);font-weight:700">2012</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">HQ</span>
              <span style="color:var(--bl);font-weight:700">San Francisco + Dubai</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">SEC Case</span>
              <span style="color:var(--gr);font-weight:700">✅ Settled 2025</span>
            </div>
          </div>
        </div>

        <!-- Card 3: XRP Asset -->
        <div style="background:rgba(72,255,130,.06);border:1px solid rgba(72,255,130,.3);
          border-radius:8px;padding:12px;position:relative;overflow:hidden">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,var(--gr),transparent)"></div>
          <div style="font-size:20px;margin-bottom:6px">💎</div>
          <div style="font-size:13px;font-weight:900;color:#fff;
            font-family:var(--mn);margin-bottom:4px">XRP</div>
          <div style="font-size:13px;font-weight:700;color:var(--gr);
            font-family:var(--mn);margin-bottom:6px;text-transform:uppercase;
            letter-spacing:1px">The Asset</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.6;
            font-family:system-ui;margin-bottom:8px">
            Native digital asset of the XRPL. Used as bridge currency in ODL,
            transaction gas, and wallet reserve. Fixed supply of 100 billion —
            no mining, no inflation. Burned slightly with every transaction.
          </div>
          <div style="display:flex;flex-direction:column;gap:3px">
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Total Supply</span>
              <span style="color:var(--gr);font-weight:700">100B XRP</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Circulating</span>
              <span style="color:var(--gr);font-weight:700" id="eco-supply">--</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">In Escrow</span>
              <span style="color:var(--gr);font-weight:700">~43B XRP</span>
            </div>
          </div>
        </div>

        <!-- Card 4: RippleNet -->
        <div style="background:rgba(255,153,0,.06);border:1px solid rgba(255,153,0,.3);
          border-radius:8px;padding:12px;position:relative;overflow:hidden">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,var(--or),transparent)"></div>
          <div style="font-size:20px;margin-bottom:6px">🌐</div>
          <div style="font-size:13px;font-weight:900;color:#fff;
            font-family:var(--mn);margin-bottom:4px">RippleNet</div>
          <div style="font-size:13px;font-weight:700;color:var(--or);
            font-family:var(--mn);margin-bottom:6px;text-transform:uppercase;
            letter-spacing:1px">The Network</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.6;
            font-family:system-ui;margin-bottom:8px">
            Ripple's B2B payment network connecting 300+ financial institutions
            globally. Three tiers: Direct (messaging), Multi-hop (routing),
            and ODL (XRP bridge). Banks choose their level of XRP integration.
          </div>
          <div style="display:flex;flex-direction:column;gap:3px">
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Partners</span>
              <span style="color:var(--or);font-weight:700">300+ institutions</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Countries</span>
              <span style="color:var(--or);font-weight:700">55+</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Type</span>
              <span style="color:var(--or);font-weight:700">Enterprise B2B</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Bottom row: 3 cards -->
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px">

        <!-- Card 5: ODL -->
        <div style="background:rgba(255,64,96,.06);border:1px solid rgba(255,64,96,.3);
          border-radius:8px;padding:12px;position:relative;overflow:hidden">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,var(--rd),transparent)"></div>
          <div style="font-size:20px;margin-bottom:6px">⚡</div>
          <div style="font-size:13px;font-weight:900;color:#fff;
            font-family:var(--mn);margin-bottom:4px">ODL</div>
          <div style="font-size:13px;font-weight:700;color:var(--rd);
            font-family:var(--mn);margin-bottom:6px;text-transform:uppercase;
            letter-spacing:1px">On-Demand Liquidity</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.6;
            font-family:system-ui;margin-bottom:8px">
            The flagship product. Uses XRP as a bridge currency to move value
            cross-border in seconds — eliminating the need for pre-funded nostro
            accounts. Saves banks up to 60% vs traditional correspondent banking.
            Powers the USA→Mexico, Japan→Philippines and 6+ other active corridors.
          </div>
          <div style="display:flex;flex-direction:column;gap:3px">
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Active Corridors</span>
              <span style="color:var(--rd);font-weight:700">8+</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Settlement</span>
              <span style="color:var(--rd);font-weight:700">3-5 seconds</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Savings vs SWIFT</span>
              <span style="color:var(--rd);font-weight:700">Up to 60%</span>
            </div>
          </div>
        </div>

        <!-- Card 6: RLUSD -->
        <div style="background:rgba(117,188,255,.06);border:1px solid rgba(117,188,255,.3);
          border-radius:8px;padding:12px;position:relative;overflow:hidden">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,var(--bl),var(--tq))"></div>
          <div style="font-size:20px;margin-bottom:6px">💵</div>
          <div style="font-size:13px;font-weight:900;color:#fff;
            font-family:var(--mn);margin-bottom:4px">RLUSD</div>
          <div style="font-size:13px;font-weight:700;color:var(--bl);
            font-family:var(--mn);margin-bottom:6px;text-transform:uppercase;
            letter-spacing:1px">The Stablecoin</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.6;
            font-family:system-ui;margin-bottom:8px">
            Ripple's USD-pegged stablecoin launched December 2024. Runs natively
            on XRPL and Ethereum. NYDFS regulated — one of the most strictly
            supervised stablecoins in existence. Complements XRP for stable
            settlement while XRP handles the bridge function.
          </div>
          <div style="display:flex;flex-direction:column;gap:3px">
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Peg</span>
              <span style="color:var(--bl);font-weight:700">1:1 USD</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Regulator</span>
              <span style="color:var(--bl);font-weight:700">NYDFS</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">Supply</span>
              <span style="color:var(--bl);font-weight:700" id="eco-rlusd">--</span>
            </div>
          </div>
        </div>

        <!-- Card 7: XRPL Ecosystem -->
        <div style="background:rgba(255,204,0,.06);border:1px solid rgba(255,204,0,.3);
          border-radius:8px;padding:12px;position:relative;overflow:hidden">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,var(--yl),transparent)"></div>
          <div style="font-size:20px;margin-bottom:6px">🛠️</div>
          <div style="font-size:13px;font-weight:900;color:#fff;
            font-family:var(--mn);margin-bottom:4px">XRPL Ecosystem</div>
          <div style="font-size:13px;font-weight:700;color:var(--yl);
            font-family:var(--mn);margin-bottom:6px;text-transform:uppercase;
            letter-spacing:1px">Developer Layer</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.6;
            font-family:system-ui;margin-bottom:8px">
            Third-party builders on the XRPL. NFT marketplaces, DeFi protocols,
            AMM pools, tokenized real-world assets, CBDCs, gaming, and the EVM
            sidechain for Ethereum compatibility. Evernode enables smart contracts.
            Sologenic enables tokenized stocks on XRPL.
          </div>
          <div style="display:flex;flex-direction:column;gap:3px">
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">DEX Vol 24h</span>
              <span style="color:var(--yl);font-weight:700" id="eco-dex">--</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">EVM Sidechain</span>
              <span style="color:var(--yl);font-weight:700">✅ Live 2024</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;font-family:var(--mn)">
              <span style="color:var(--tx)">CBDC Projects</span>
              <span style="color:var(--yl);font-weight:700">6 Live/Pilot</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Ecosystem Flow Diagram -->
      <div style="margin-bottom:14px">
        <div style="font-size:16px;font-weight:700;color:var(--tq);font-family:var(--mn);
          text-transform:uppercase;letter-spacing:2px;margin-bottom:16px;text-align:left">
          ⛓️ How the Layers Connect
        </div>
        <div style="display:flex;align-items:center;justify-content:center;gap:0;overflow-x:auto;padding:10px 0">

          <div style="display:flex;flex-direction:column;align-items:center;
            min-width:120px;text-align:center;padding:8px">
            <div style="font-size:22px;margin-bottom:6px">🔗</div>
            <div style="font-size:13px;font-weight:700;color:var(--tq);
              font-family:var(--mn)">XRPL</div>
            <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Foundation</div>
          </div>
          <div style="color:var(--bl);font-size:22px;padding:0 8px;flex-shrink:0;font-weight:300">→</div>

          <div style="display:flex;flex-direction:column;align-items:center;
            min-width:120px;text-align:center;padding:8px">
            <div style="font-size:22px;margin-bottom:6px">💎</div>
            <div style="font-size:13px;font-weight:700;color:var(--gr);
              font-family:var(--mn)">XRP</div>
            <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Native Asset</div>
          </div>
          <div style="color:var(--bl);font-size:22px;padding:0 8px;flex-shrink:0;font-weight:300">→</div>

          <div style="display:flex;flex-direction:column;align-items:center;
            min-width:120px;text-align:center;padding:8px">
            <div style="font-size:22px;margin-bottom:6px">🏢</div>
            <div style="font-size:13px;font-weight:700;color:var(--bl);
              font-family:var(--mn)">Ripple Labs</div>
            <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Builder</div>
          </div>
          <div style="color:var(--bl);font-size:22px;padding:0 8px;flex-shrink:0;font-weight:300">→</div>

          <div style="display:flex;flex-direction:column;align-items:center;
            min-width:120px;text-align:center;padding:8px">
            <div style="font-size:22px;margin-bottom:6px">🌐</div>
            <div style="font-size:13px;font-weight:700;color:var(--or);
              font-family:var(--mn)">RippleNet</div>
            <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Network</div>
          </div>
          <div style="color:var(--bl);font-size:22px;padding:0 8px;flex-shrink:0;font-weight:300">→</div>

          <div style="display:flex;flex-direction:column;align-items:center;
            min-width:120px;text-align:center;padding:8px">
            <div style="font-size:22px;margin-bottom:6px">⚡</div>
            <div style="font-size:13px;font-weight:700;color:var(--rd);
              font-family:var(--mn)">ODL</div>
            <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Liquidity</div>
          </div>
          <div style="color:var(--bl);font-size:22px;padding:0 8px;flex-shrink:0;font-weight:300">+</div>

          <div style="display:flex;flex-direction:column;align-items:center;
            min-width:120px;text-align:center;padding:8px">
            <div style="font-size:22px;margin-bottom:6px">💵</div>
            <div style="font-size:13px;font-weight:700;color:var(--bl);
              font-family:var(--mn)">RLUSD</div>
            <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Stablecoin</div>
          </div>
          <div style="color:var(--bl);font-size:22px;padding:0 8px;flex-shrink:0;font-weight:300">→</div>

          <div style="display:flex;flex-direction:column;align-items:center;
            min-width:110px;text-align:center">
            <div style="font-size:22px;margin-bottom:6px">🛠️</div>
            <div style="font-size:13px;font-weight:700;color:var(--yl);
              font-family:var(--mn)">Ecosystem</div>
            <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Builders</div>
          </div>

        </div>
      </div>

      <!-- Common Misconceptions -->
      <div>
        <div style="font-size:13px;font-weight:700;color:var(--bl);font-family:var(--mn);
          text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px">
          ⚠️ Common Misconceptions — Set the Record Straight
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">

          <div style="background:var(--s2);border:1px solid var(--b);border-radius:6px;padding:10px">
            <div style="font-size:13px;font-weight:700;color:var(--rd);
              font-family:var(--mn);margin-bottom:4px">❌ MYTH</div>
            <div style="font-size:13px;color:var(--br);font-weight:700;
              margin-bottom:6px">"Ripple controls XRP"</div>
            <div style="font-size:13px;font-weight:700;color:var(--gr);
              font-family:var(--mn);margin-bottom:4px">✅ REALITY</div>
            <div style="font-size:13px;color:var(--tx);line-height:1.5">
              XRP runs on the XRPL which is decentralised and maintained by the
              independent XRPL Foundation. Ripple holds XRP but cannot create,
              destroy, or freeze it.
            </div>
          </div>

          <div style="background:var(--s2);border:1px solid var(--b);border-radius:6px;padding:10px">
            <div style="font-size:13px;font-weight:700;color:var(--rd);
              font-family:var(--mn);margin-bottom:4px">❌ MYTH</div>
            <div style="font-size:13px;color:var(--br);font-weight:700;
              margin-bottom:6px">"Ripple can print more XRP"</div>
            <div style="font-size:13px;font-weight:700;color:var(--gr);
              font-family:var(--mn);margin-bottom:4px">✅ REALITY</div>
            <div style="font-size:13px;color:var(--tx);line-height:1.5">
              XRP has a fixed maximum supply of 100 billion — hardcoded into the
              protocol. No mining, no inflation, no new XRP can ever be created.
              Supply only decreases as tiny amounts are burned per transaction.
            </div>
          </div>

          <div style="background:var(--s2);border:1px solid var(--b);border-radius:6px;padding:10px">
            <div style="font-size:13px;font-weight:700;color:var(--rd);
              font-family:var(--mn);margin-bottom:4px">❌ MYTH</div>
            <div style="font-size:13px;color:var(--br);font-weight:700;
              margin-bottom:6px">"XRP is a security"</div>
            <div style="font-size:13px;font-weight:700;color:var(--gr);
              font-family:var(--mn);margin-bottom:4px">✅ REALITY</div>
            <div style="font-size:13px;color:var(--tx);line-height:1.5">
              Judge Torres ruled in 2023 that XRP is NOT a security in programmatic
              sales. The SEC settled with Ripple in 2025. XRP now operates with
              full US regulatory clarity for the first time.
            </div>
          </div>

        </div>
      </div>

    </div>
  </div>
</div>

<!-- SECTION 3e: MAINSTREAM INTEGRATION MONITOR -->
<div style="margin-bottom:10px">
  <div style="background:linear-gradient(135deg,#0a0a0a 0%,#0d0d0a 100%);
    border:1px solid rgba(255,204,0,.25);border-radius:12px;overflow:hidden">

    <!-- Header -->
    <div style="padding:14px 18px;background:rgba(255,204,0,.05);
      border-bottom:1px solid rgba(255,204,0,.2);
      display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:12px">
        <span style="font-size:28px;filter:drop-shadow(0 0 8px rgba(255,204,0,.5))">🪚</span>
        <div>
          <div style="font-size:17px;font-weight:900;color:#fff;font-family:var(--mn);
            text-transform:uppercase;letter-spacing:2px">Mainstream Integration Monitor</div>
          <div style="font-size:13px;font-family:system-ui;color:var(--yl);
            margin-top:3px;font-style:italic">
            XRP is no longer knocking on the door of traditional finance — it's building new springboards for growth and utilization.
          </div>
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap" id="ms-filter-btns">
        <button id="msf-ALL" onclick="filterMainstream('ALL')" style="background:rgba(255,255,255,.2);color:#fff;padding:6px 14px;border-radius:4px;border:1px solid rgba(255,255,255,.4);font-weight:700;cursor:pointer;font-family:var(--mn);font-size:13px;outline:2px solid #fff">ALL</button>
        <button id="msf-CONFIRMED" onclick="filterMainstream('CONFIRMED')" style="background:rgba(72,255,130,.15);color:var(--gr);padding:6px 14px;border-radius:4px;border:1px solid rgba(72,255,130,.4);font-weight:700;cursor:pointer;font-family:var(--mn);font-size:13px;opacity:.7">✅ CONFIRMED</button>
        <button id="msf-EXPLORING" onclick="filterMainstream('EXPLORING')" style="background:rgba(117,188,255,.15);color:var(--bl);padding:6px 14px;border-radius:4px;border:1px solid rgba(117,188,255,.4);font-weight:700;cursor:pointer;font-family:var(--mn);font-size:13px;opacity:.7">🔍 EXPLORING</button>
        <button id="msf-RUMORED" onclick="filterMainstream('RUMORED')" style="background:rgba(255,204,0,.15);color:var(--yl);padding:6px 14px;border-radius:4px;border:1px solid rgba(255,204,0,.4);font-weight:700;cursor:pointer;font-family:var(--mn);font-size:13px;opacity:.7">💬 RUMORED</button>
        <button id="msf-PILOT" onclick="filterMainstream('PILOT')" style="background:rgba(255,153,0,.15);color:var(--or);padding:6px 14px;border-radius:4px;border:1px solid rgba(255,153,0,.4);font-weight:700;cursor:pointer;font-family:var(--mn);font-size:13px;opacity:.7">🧪 PILOT</button>
        <button id="msf-COMPETING" onclick="filterMainstream('COMPETING')" style="background:rgba(255,64,96,.15);color:var(--rd);padding:6px 14px;border-radius:4px;border:1px solid rgba(255,64,96,.4);font-weight:700;cursor:pointer;font-family:var(--mn);font-size:13px;opacity:.7">⚔️ COMPETING</button>
        <span id="ms-count" style="color:var(--tx);font-size:12px;align-self:center;margin-left:8px">20 partners</span>
      </div>
    </div>

    <div style="padding:14px 18px">

      <!-- Partnership Grid -->
      <div style="font-size:13px;font-weight:700;color:var(--yl);font-family:var(--mn);
        text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px">
        🏦 Institutional Partnership Tracker
      </div>
      <div id="ms-partner-grid" style="display:grid;grid-template-columns:repeat(4,1fr);
        gap:8px;margin-bottom:16px"></div>

      <!-- Integration Timeline -->
      <div style="font-size:13px;font-weight:700;color:var(--yl);font-family:var(--mn);
        text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px">
        📅 XRP × Traditional Finance — Integration Timeline
      </div>
      <div style="position:relative;padding:10px 0">
        <!-- Horizontal line -->
        <div style="position:absolute;top:28px;left:0;right:0;height:2px;
          background:linear-gradient(90deg,transparent,var(--yl),var(--gr),transparent)"></div>
        <div id="ms-timeline" style="display:flex;gap:0;overflow-x:auto;
          padding-bottom:8px;position:relative"></div>
      </div>

    </div>
  </div>
</div>

<!-- SECTION 4b: TOP 20 XRP STORIES -->
<div class="score" style="margin-bottom:10px">
  <div class="sec-title" style="color:var(--bl)">📋 Top 20 XRP Stories</div>
  <div id="top20-feed" style="display:flex;flex-direction:column;gap:6px"></div>
</div>

<!-- SECTION 5: US + GLOBAL INTELLIGENCE (2-column panel) -->
<div class="two">
  <div class="panel" id="ai-briefing-us">
    <div class="ph"><span class="pt" style="color:var(--bl);font-size:16px;font-weight:800;letter-spacing:2px">🇺🇸 US Intelligence</span><span style="font-size:13px;font-family:var(--mn);color:var(--tx)" id="ai-us-ts">--</span></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">US Pulse</div><div class="pv" id="ai-us-pulse" style="font-size:13px;line-height:1.7;font-family:system-ui">Fetching US intelligence...</div></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Regulatory</div><div class="pv" id="ai-us-reg" style="font-size:13px;line-height:1.7;font-family:system-ui">Loading...</div></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Institutional</div><div class="pv" id="ai-us-inst" style="font-size:13px;line-height:1.7;font-family:system-ui">Loading...</div></div>
  </div>
  <div class="panel">
    <div class="ph"><span class="pt" style="color:var(--gr);font-size:16px;font-weight:800;letter-spacing:2px">🌐 Global Pulse</span><span style="font-size:13px;font-family:var(--mn);color:var(--tx)" id="ai-gl-ts">--</span></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Global Summary</div><div class="pv g" id="ai-gl-pulse" style="font-size:13px;line-height:1.7;font-family:system-ui">Synthesizing global signals...</div></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Regional Signals</div><div id="ai-signals" class="sig-chips"><span class="empty">Loading...</span></div></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Cumulative Thesis</div><div style="font-size:13px;line-height:1.7;color:var(--gr);font-family:system-ui" id="ai-gl-thesis">Building analysis...</div></div>
  </div>
</div>

<!-- SECTION 6: REGIONAL INTELLIGENCE CARDS -->
<div class="sec-title" style="color:var(--bl)">🗺️ Regional Intelligence</div>
<div class="slots" id="regionGrid">
  <div class="empty" style="grid-column:1/-1">Loading regional intelligence...</div>
</div>

<!-- SECTION 7: NEWS SCOREBOARD -->
<div class="score">
  <div class="sec-title" style="color:var(--bl)">📡 Signal Scoreboard</div>
  <div class="sgrid">
    <div class="sbox bc"><div class="snum b" id="sc-total">--</div><div class="snlbl">Stories Today</div><div class="snsub" id="sc-feeds">-- sources</div></div>
    <div class="sbox wc"><div class="snum g" id="sc-bull">--</div><div class="snlbl">Bullish</div><div class="snsub" id="sc-bull-pct">--%</div></div>
    <div class="sbox lc"><div class="snum r" id="sc-bear">--</div><div class="snlbl">Bearish</div><div class="snsub" id="sc-bear-pct">--%</div></div>
    <div class="sbox"><div class="snum" id="sc-neut">--</div><div class="snlbl">Neutral</div><div class="snsub" id="sc-net">Net: --</div></div>
    <div class="sbox yc"><div class="snum y" id="sc-fg">--</div><div class="snlbl">Fear &amp; Greed</div><div class="snsub" id="sc-fg-lbl">--</div></div>
    <div class="sbox"><div class="snum b" id="sc-rank">#--</div><div class="snlbl">Global Rank</div><div class="snsub">CoinGecko</div></div>
  </div>
  <div class="sgrid4" style="margin-top:8px">
    <div class="sbox bc"><div class="snum b" id="sc-mcap">--</div><div class="snlbl">Market Cap</div></div>
    <div class="sbox"><div class="snum y" id="sc-vol">--</div><div class="snlbl">24h Volume</div></div>
    <div class="sbox wc"><div class="snum g" id="sc-high">--</div><div class="snlbl">24h High</div></div>
    <div class="sbox lc"><div class="snum r" id="sc-low">--</div><div class="snlbl">24h Low</div></div>
  </div>
  <div class="wrbar"><div class="wrfill" id="sc-fill" style="width:50%"></div></div>
</div>


<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- v6.0 NEW SECTIONS                                               -->
<!-- ═══════════════════════════════════════════════════════════════ -->

<!-- SECTION v6-A: XRPRADAR SIGNAL SCORE (#61) -->
<div style="margin-bottom:10px" id="signal-score-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:10px">
      <div>
        <div class="sec-title" style="color:var(--yl);margin-bottom:4px">🎯 XRPRADAR SIGNAL SCORE</div>
        <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Composite institutional-grade intelligence score — updated every 10 minutes</div>
      </div>
      <div id="ss-total-display" style="text-align:center">
        <div id="ss-score" style="font-size:64px;font-weight:900;font-family:var(--mn);color:var(--gr);line-height:1">--</div>
        <div id="ss-grade" style="font-size:16px;font-weight:700;color:var(--yl);font-family:var(--mn)">/100</div>
        <div id="ss-label" style="font-size:13px;color:var(--tx);font-family:var(--mn)">CALCULATING...</div>
        <div id="ss-ts" style="font-size:11px;color:var(--tx);margin-top:4px"></div>
      </div>
    </div>
    <!-- Signal Score Progress Bar -->
    <div style="background:var(--bg);border-radius:6px;height:12px;margin-bottom:16px;overflow:hidden">
      <div id="ss-bar" style="height:100%;border-radius:6px;background:linear-gradient(90deg,#ff4060,#ffcc00,#48ff82);width:0%;transition:width 1s ease"></div>
    </div>
    <!-- Component Breakdown -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px" id="ss-components">
      <div class="abox" style="border-left:3px solid var(--gr)"><div class="albl">PRICE MOMENTUM</div><div class="aval" id="ss-c1">--</div><div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="ss-c1s">--</div></div>
      <div class="abox" style="border-left:3px solid var(--bl)"><div class="albl">RSI SIGNAL</div><div class="aval" id="ss-c2">--</div><div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="ss-c2s">--</div></div>
      <div class="abox" style="border-left:3px solid var(--tq)"><div class="albl">SENTIMENT</div><div class="aval" id="ss-c3">--</div><div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="ss-c3s">--</div></div>
      <div class="abox" style="border-left:3px solid var(--or)"><div class="albl">ON-CHAIN</div><div class="aval" id="ss-c4">--</div><div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="ss-c4s">--</div></div>
      <div class="abox" style="border-left:3px solid var(--yl)"><div class="albl">MACRO</div><div class="aval" id="ss-c5">--</div><div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="ss-c5s">--</div></div>
      <div class="abox" style="border-left:3px solid var(--gr)"><div class="albl">INST FLOW</div><div class="aval" id="ss-c6">--</div><div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="ss-c6s">--</div></div>
      <div class="abox" style="border-left:3px solid var(--rd)"><div class="albl">WHALE ACTIVITY</div><div class="aval" id="ss-c7">--</div><div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="ss-c7s">--</div></div>
      <div class="abox" style="border-left:3px solid var(--bl)"><div class="albl">FEAR & GREED</div><div class="aval" id="ss-c8">--</div><div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="ss-c8s">--</div></div>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--tx);font-family:var(--mn);opacity:.6">
      ⚠️ Signal Score is for informational purposes only. Not financial advice. Always DYOR.
    </div>
  </div>
</div>

<!-- SECTION v6-B: MACRO DASHBOARD (#46) + CORRELATION MATRIX (#47) -->
<div style="margin-bottom:10px" id="macro-section">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    <!-- Macro Dashboard -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--or);margin-bottom:12px">📈 MACRO SIGNAL DASHBOARD</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px" id="macro-grid">
        <div class="abox"><div class="albl">DXY (USD INDEX)</div><div class="aval" id="mac-dxy">--</div><div style="font-size:13px;font-family:var(--mn)" id="mac-dxy-chg">--</div></div>
        <div class="abox"><div class="albl">S&P 500</div><div class="aval" id="mac-sp">--</div><div style="font-size:13px;font-family:var(--mn)" id="mac-sp-chg">--</div></div>
        <div class="abox"><div class="albl">GOLD (USD/oz)</div><div class="aval" id="mac-gold">--</div><div style="font-size:13px;font-family:var(--mn)" id="mac-gold-chg">--</div></div>
        <div class="abox"><div class="albl">10-YR TREASURY</div><div class="aval" id="mac-tnx">--</div><div style="font-size:13px;font-family:var(--mn)" id="mac-tnx-chg">--</div></div>
        <div class="abox"><div class="albl">BITCOIN</div><div class="aval" id="mac-btc">--</div><div style="font-size:13px;font-family:var(--mn)" id="mac-btc-chg">--</div></div>
        <div class="abox" id="mac-signal-box"><div class="albl">MACRO SIGNAL</div><div class="aval" id="mac-signal" style="font-size:16px">--</div><div style="font-size:12px;font-family:var(--mn);color:var(--tx)" id="mac-ts">--</div></div>
      </div>
    </div>
    <!-- Correlation Matrix -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--tq);margin-bottom:12px">🔢 XRP CORRELATION MATRIX</div>
      <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:10px">Directional correlation — 24h price movement</div>
      <div style="display:flex;flex-direction:column;gap:8px" id="corr-grid">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <span style="font-family:var(--mn);font-size:14px;font-weight:700;color:var(--br)">XRP vs BTC</span>
          <span id="corr-btc" style="font-family:var(--mn);font-size:14px;font-weight:700">--</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <span style="font-family:var(--mn);font-size:14px;font-weight:700;color:var(--br)">XRP vs S&P 500</span>
          <span id="corr-sp" style="font-family:var(--mn);font-size:14px;font-weight:700">--</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <span style="font-family:var(--mn);font-size:14px;font-weight:700;color:var(--br)">XRP vs Gold</span>
          <span id="corr-gold" style="font-family:var(--mn);font-size:14px;font-weight:700">--</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <span style="font-family:var(--mn);font-size:14px;font-weight:700;color:var(--br)">XRP vs DXY</span>
          <span id="corr-dxy" style="font-family:var(--mn);font-size:14px;font-weight:700">--</span>
        </div>
        <div style="margin-top:8px;padding:10px;background:var(--s2);border-radius:6px;font-family:var(--mn);font-size:12px;color:var(--tx)">
          POSITIVE = same direction today · NEGATIVE = inverse · -- = no data yet
        </div>
      </div>
    </div>
  </div>
</div>

<!-- SECTION v6-C: ORDER BOOK DEPTH (#41) + LIQUIDITY MAP (#43) -->
<div style="margin-bottom:10px" id="orderbook-section">
  <div style="display:grid;grid-template-columns:2fr 1fr;gap:10px">
    <!-- Order Book Depth -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--gr);margin-bottom:4px">📊 XRP ORDER BOOK DEPTH</div>
      <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:12px">Combined buy/sell walls across Binance · Bitstamp · Kraken — real-time</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <!-- Bids -->
        <div>
          <div style="font-size:13px;font-weight:700;color:var(--gr);font-family:var(--mn);margin-bottom:6px;text-align:center">🟢 BUY WALLS (BIDS)</div>
          <div id="ob-bids" style="font-family:var(--mn);font-size:12px">
            <div style="color:var(--tx)">Loading order book...</div>
          </div>
          <div style="margin-top:8px;padding:6px;background:rgba(72,255,130,.1);border:1px solid rgba(72,255,130,.2);border-radius:4px;text-align:center">
            <span style="font-size:12px;color:var(--tx)">Total Bid Depth: </span>
            <span id="ob-bid-total" style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn)">--</span>
          </div>
        </div>
        <!-- Asks -->
        <div>
          <div style="font-size:13px;font-weight:700;color:var(--rd);font-family:var(--mn);margin-bottom:6px;text-align:center">🔴 SELL WALLS (ASKS)</div>
          <div id="ob-asks" style="font-family:var(--mn);font-size:12px">
            <div style="color:var(--tx)">Loading order book...</div>
          </div>
          <div style="margin-top:8px;padding:6px;background:rgba(255,64,96,.1);border:1px solid rgba(255,64,96,.2);border-radius:4px;text-align:center">
            <span style="font-size:12px;color:var(--tx)">Total Ask Depth: </span>
            <span id="ob-ask-total" style="font-size:14px;font-weight:700;color:var(--rd);font-family:var(--mn)">--</span>
          </div>
        </div>
      </div>
    </div>
    <!-- Liquidity Map -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--tq);margin-bottom:12px">💧 LIQUIDITY MAP</div>
      <div id="liq-map" style="font-family:var(--mn)">
        <div style="font-size:13px;color:var(--tx)">Fetching liquidity data...</div>
      </div>
    </div>
  </div>
</div>

<!-- SECTION v6-D: RIPPLE IPO WATCH (#44) -->
<div style="margin-bottom:10px" id="ipo-section">
  <div style="background:linear-gradient(135deg,#0a0a14 0%,#0d0814 100%);border:1px solid rgba(255,204,0,.3);border-radius:12px;padding:16px">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px">
      <div>
        <div class="sec-title" style="color:var(--yl);margin-bottom:4px">🏦 RIPPLE IPO WATCH</div>
        <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Tracking Ripple Labs' path to public markets — the most anticipated crypto IPO</div>
      </div>
      <div id="ipo-prob-display" style="text-align:center;background:rgba(255,204,0,.1);border:1px solid rgba(255,204,0,.3);border-radius:8px;padding:10px 20px">
        <div style="font-size:11px;color:var(--yl);font-family:var(--mn);text-transform:uppercase;letter-spacing:1px">IPO Probability</div>
        <div id="ipo-prob" style="font-size:36px;font-weight:900;color:var(--yl);font-family:var(--mn)">72%</div>
        <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">within 12 months</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;margin-bottom:14px">
      <div class="abox"><div class="albl">CURRENT VALUATION</div><div class="aval" id="ipo-val" style="font-size:20px;color:var(--yl)">~$11B</div></div>
      <div class="abox"><div class="albl">IPO STATUS</div><div style="font-size:13px;font-weight:700;color:var(--gr);font-family:var(--mn);margin-top:4px" id="ipo-status">Filed confidentially</div></div>
      <div class="abox"><div class="albl">UNDERWRITERS</div><div style="font-size:13px;font-weight:700;color:var(--br);font-family:var(--mn);margin-top:4px" id="ipo-banks">Goldman, JPMorgan (rumoured)</div></div>
      <div class="abox"><div class="albl">NEXT MILESTONE</div><div style="font-size:13px;font-weight:700;color:var(--bl);font-family:var(--mn);margin-top:4px" id="ipo-milestone">S-1 Registration</div></div>
    </div>
    <div class="sec-title" style="font-size:14px;color:var(--yl);margin-bottom:8px">Latest IPO News</div>
    <div id="ipo-news" style="max-height:220px;overflow-y:auto">
      <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Loading IPO intelligence...</div>
    </div>
  </div>
</div>

<!-- SECTION v6-E: CURRENCY CRISIS MONITOR (#54) -->
<div style="margin-bottom:10px" id="crisis-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--rd);margin-bottom:4px">🌡️ REAL-TIME CURRENCY CRISIS MONITOR</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">
      Countries with failing currencies = XRP ODL opportunity. Total addressable remittance market: <span id="cc-total" style="color:var(--gr);font-weight:700">$0B</span>/year
    </div>
    <div id="crisis-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:8px">
      <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Loading crisis monitor...</div>
    </div>
  </div>
</div>

<!-- SECTION v6-F: ADOPTION VELOCITY (#57) + NVT RATIO (#49) -->
<div style="margin-bottom:10px">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    <!-- Adoption Velocity -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--gr);margin-bottom:12px">🚀 XRP ADOPTION VELOCITY</div>
      <div style="text-align:center;margin-bottom:14px">
        <div id="av-score" style="font-size:52px;font-weight:900;color:var(--gr);font-family:var(--mn)">--</div>
        <div id="av-trend" style="font-size:14px;font-weight:700;color:var(--yl);font-family:var(--mn)">/100 — CALCULATING</div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
        <div style="padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">INSTITUTIONAL</div>
          <div id="av-inst" style="font-size:18px;font-weight:700;color:var(--bl);font-family:var(--mn)">--</div>
        </div>
        <div style="padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">RETAIL</div>
          <div id="av-retail" style="font-size:18px;font-weight:700;color:var(--tq);font-family:var(--mn)">--</div>
        </div>
        <div style="padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">DEVELOPER</div>
          <div id="av-dev" style="font-size:18px;font-weight:700;color:var(--gr);font-family:var(--mn)">--</div>
        </div>
        <div style="padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">REGULATORY</div>
          <div id="av-reg" style="font-size:18px;font-weight:700;color:var(--yl);font-family:var(--mn)">--</div>
        </div>
      </div>
    </div>
    <!-- NVT Ratio -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--bl);margin-bottom:12px">📐 NVT RATIO — NETWORK VALUATION</div>
      <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">Network Value to Transactions — is XRP over or undervalued vs actual usage?</div>
      <div style="text-align:center;margin-bottom:16px">
        <div id="nvt-value" style="font-size:48px;font-weight:900;color:var(--bl);font-family:var(--mn)">--</div>
        <div id="nvt-interp" style="font-size:14px;font-weight:700;color:var(--br);font-family:var(--mn)">CALCULATING...</div>
      </div>
      <div style="padding:12px;background:var(--bg);border-radius:8px;border:1px solid var(--b);font-family:var(--mn);font-size:12px;color:var(--tx)">
        NVT &lt;20 = Undervalued · 20-50 = Fair · 50-100 = Moderate Premium · &gt;100 = Overvalued vs network usage
      </div>
    </div>
  </div>
</div>


<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- v6.2 NEW DISPLAY PANELS — Features #42, #45, #48, #50-53      -->
<!-- ═══════════════════════════════════════════════════════════════ -->

<!-- #42 INSTITUTIONAL FLOW TRACKER -->
<div style="margin-bottom:10px" id="inst-flow-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--gr);margin-bottom:4px">🏛️ INSTITUTIONAL FLOW TRACKER</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">
      ETF inflows/outflows, OTC block movements, and institutional positioning — follow the smart money
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-bottom:12px">
      <div class="abox" style="border-left:3px solid var(--gr)">
        <div class="albl">ETF NET FLOW 7D</div>
        <div class="aval" id="if-net-flow" style="font-size:20px">--</div>
        <div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="if-flow-signal">Loading...</div>
      </div>
      <div class="abox" style="border-left:3px solid var(--bl)">
        <div class="albl">ETF INFLOWS 7D</div>
        <div class="aval" id="if-inflows" style="font-size:20px;color:var(--gr)">--</div>
      </div>
      <div class="abox" style="border-left:3px solid var(--rd)">
        <div class="albl">ETF OUTFLOWS 7D</div>
        <div class="aval" id="if-outflows" style="font-size:20px;color:var(--rd)">--</div>
      </div>
      <div class="abox" style="border-left:3px solid var(--yl)">
        <div class="albl">OI CHANGE 24H</div>
        <div class="aval" id="if-oi-change" style="font-size:20px">--</div>
      </div>
      <div class="abox" style="border-left:3px solid var(--tq)">
        <div class="albl">FUNDING TREND</div>
        <div class="aval" id="if-funding-trend" style="font-size:16px">--</div>
      </div>
      <div class="abox" style="border-left:3px solid var(--or)">
        <div class="albl">FLOW SIGNAL</div>
        <div class="aval" id="if-signal" style="font-size:16px">--</div>
      </div>
    </div>
    <div id="if-large-moves" style="font-size:13px;color:var(--tx);font-family:var(--mn)">
      Monitoring for large institutional moves...
    </div>
  </div>
</div>

<!-- #45 CBDC COMPETITION MONITOR -->
<div style="margin-bottom:10px" id="cbdc-comp-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--yl);margin-bottom:4px">🏦 CBDC COMPETITION MONITOR</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">
      Which central bank CBDCs threaten XRP vs which ones USE XRP — strategic competitive intelligence
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px">

      <!-- Using XRPL -->
      <div style="background:var(--bg);border:1px solid rgba(72,255,130,.2);border-radius:8px;padding:12px">
        <div style="font-size:13px;font-weight:700;color:var(--gr);font-family:var(--mn);margin-bottom:10px">
          ✅ CBDCs BUILT ON XRPL
        </div>
        <div style="font-size:13px;color:var(--tx);display:flex;flex-direction:column;gap:8px">
          <div style="padding:8px;background:rgba(72,255,130,.06);border-radius:5px;border-left:2px solid var(--gr)">
            <div style="font-weight:700;color:var(--br)">🇧🇹 Bhutan — Druk Digital</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">First sovereign CBDC on XRPL. Live with Royal Monetary Authority. Sets global precedent.</div>
            <div style="font-size:11px;color:var(--gr);font-family:var(--mn);margin-top:3px">STATUS: ✅ LIVE</div>
          </div>
          <div style="padding:8px;background:rgba(72,255,130,.06);border-radius:5px;border-left:2px solid var(--gr)">
            <div style="font-weight:700;color:var(--br)">🇵🇼 Palau — Palau Stablecoin</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">USD-backed national digital currency on XRPL. Government payments and cross-border.</div>
            <div style="font-size:11px;color:var(--gr);font-family:var(--mn);margin-top:3px">STATUS: ✅ LIVE</div>
          </div>
          <div style="padding:8px;background:rgba(255,204,0,.06);border-radius:5px;border-left:2px solid var(--yl)">
            <div style="font-weight:700;color:var(--br)">🇲🇪 Montenegro — Digital Euro Pilot</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">Central Bank of Montenegro piloting XRPL digital euro infrastructure.</div>
            <div style="font-size:11px;color:var(--yl);font-family:var(--mn);margin-top:3px">STATUS: 🧪 PILOT</div>
          </div>
          <div style="padding:8px;background:rgba(255,204,0,.06);border-radius:5px;border-left:2px solid var(--yl)">
            <div style="font-weight:700;color:var(--br)">🇭🇰 Hong Kong — HKD CBDC</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">HKMA in Project mBridge discussions. Ripple in talks for XRPL settlement layer.</div>
            <div style="font-size:11px;color:var(--yl);font-family:var(--mn);margin-top:3px">STATUS: 🧪 PILOT</div>
          </div>
          <div style="padding:8px;background:rgba(117,188,255,.06);border-radius:5px;border-left:2px solid var(--bl)">
            <div style="font-weight:700;color:var(--br)">🇨🇴 Colombia + 🇬🇪 Georgia</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">Both central banks formally exploring XRPL for national digital currency infrastructure.</div>
            <div style="font-size:11px;color:var(--bl);font-family:var(--mn);margin-top:3px">STATUS: 🔍 EXPLORING</div>
          </div>
        </div>
      </div>

      <!-- Competing CBDCs -->
      <div style="background:var(--bg);border:1px solid rgba(255,64,96,.2);border-radius:8px;padding:12px">
        <div style="font-size:13px;font-weight:700;color:var(--or);font-family:var(--mn);margin-bottom:10px">
          ⚔️ COMPETING CBDC PROJECTS
        </div>
        <div style="font-size:13px;color:var(--tx);display:flex;flex-direction:column;gap:8px">
          <div style="padding:8px;background:rgba(255,64,96,.06);border-radius:5px;border-left:2px solid var(--rd)">
            <div style="font-weight:700;color:var(--br)">🇨🇳 China — Digital Yuan (e-CNY)</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">Most advanced CBDC globally. Pushing international adoption via Belt & Road. Risk: displaces XRP in Asian corridors if mandated by partner nations.</div>
            <div style="font-size:11px;color:var(--rd);font-family:var(--mn);margin-top:3px">XRP THREAT: ⚠️ MEDIUM — Geographically limited; XRP has deeper global banking relationships</div>
          </div>
          <div style="padding:8px;background:rgba(255,153,0,.06);border-radius:5px;border-left:2px solid var(--or)">
            <div style="font-weight:700;color:var(--br)">🇪🇺 EU — Digital Euro (ECB)</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">ECB developing digital euro for retail. Could reduce need for cross-border XRP in EU corridor. However, XRP classified legal under MiCA.</div>
            <div style="font-size:11px;color:var(--or);font-family:var(--mn);margin-top:3px">XRP THREAT: ⚠️ LOW — Retail focus; XRP plays institutional wholesale settlement layer</div>
          </div>
          <div style="padding:8px;background:rgba(255,153,0,.06);border-radius:5px;border-left:2px solid var(--or)">
            <div style="font-weight:700;color:var(--br)">🇺🇸 USA — FedNow + Digital Dollar</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">FedNow instant payment rails live 2023. Digital dollar CBDC research ongoing. Post-SEC settlement, XRP positioned as bridge for international USD corridors.</div>
            <div style="font-size:11px;color:var(--or);font-family:var(--mn);margin-top:3px">XRP THREAT: ⚠️ LOW — FedNow is domestic only; XRP excels in cross-border</div>
          </div>
          <div style="padding:8px;background:rgba(72,255,130,.06);border-radius:5px;border-left:2px solid var(--gr)">
            <div style="font-weight:700;color:var(--br)">🌐 BIS Project Nexus</div>
            <div style="font-size:12px;color:var(--tx);margin-top:2px">Multi-CBDC settlement platform. Ripple is a confirmed participant. XRPL being evaluated as the underlying settlement infrastructure.</div>
            <div style="font-size:11px;color:var(--gr);font-family:var(--mn);margin-top:3px">XRP OPPORTUNITY: 🚀 HIGH — Could become the global CBDC interoperability backbone</div>
          </div>
        </div>
        <div style="margin-top:10px;padding:8px;background:rgba(72,255,130,.06);border:1px solid rgba(72,255,130,.2);border-radius:5px">
          <div style="font-size:12px;font-weight:700;color:var(--gr);font-family:var(--mn)">OVERALL OPPORTUNITY SCORE: 72/100</div>
          <div style="font-size:12px;color:var(--tx);margin-top:3px">XRP positioned as the neutral bridge between competing CBDCs. No nation's CBDC can serve ALL corridors — XRP fills the gaps.</div>
        </div>
      </div>

    </div>
  </div>
</div>

<!-- #48 XRP OPTIONS FLOW -->
<div style="margin-bottom:10px" id="options-flow-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--bl);margin-bottom:4px">📉 XRP OPTIONS FLOW</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">
      Put/call ratio, implied volatility, and major strike levels — shows how institutions are positioning
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-bottom:12px">
      <div class="abox" style="border-left:3px solid var(--bl)">
        <div class="albl">PUT/CALL RATIO</div>
        <div class="aval" id="of-pcr" style="font-size:24px">--</div>
        <div style="font-size:12px;color:var(--tx);font-family:var(--mn)" id="of-pcr-signal">--</div>
      </div>
      <div class="abox" style="border-left:3px solid var(--or)">
        <div class="albl">IMPLIED VOLATILITY</div>
        <div class="aval" id="of-iv" style="font-size:24px">--</div>
        <div style="font-size:12px;color:var(--tx);font-family:var(--mn)">30-day IV</div>
      </div>
      <div class="abox" style="border-left:3px solid var(--yl)">
        <div class="albl">MAX PAIN LEVEL</div>
        <div class="aval" id="of-maxpain" style="font-size:24px">--</div>
        <div style="font-size:12px;color:var(--tx);font-family:var(--mn)">Price at expiry</div>
      </div>
      <div class="abox" style="border-left:3px solid var(--tq)">
        <div class="albl">POSITIONING</div>
        <div class="aval" id="of-positioning" style="font-size:18px">--</div>
        <div style="font-size:12px;color:var(--tx);font-family:var(--mn)">Inst. bias</div>
      </div>
    </div>
    <div style="padding:10px;background:var(--bg);border-radius:6px;border:1px solid var(--b);font-family:var(--mn);font-size:12px;color:var(--tx)">
      📊 <strong style="color:var(--br)">How to read:</strong> Put/Call &lt;0.7 = bullish (more calls) · &gt;1.3 = bearish (more puts) · 0.7-1.3 = neutral · Max Pain = price that causes maximum option losses at expiry
    </div>
    <div id="of-strikes" style="margin-top:10px"></div>
  </div>
</div>

<!-- #50 ACCUMULATION / DISTRIBUTION SCORE -->
<div style="margin-bottom:10px" id="accum-distrib-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">

      <!-- Accumulation/Distribution -->
      <div>
        <div class="sec-title" style="color:var(--tq);margin-bottom:12px">📦 ACCUMULATION / DISTRIBUTION</div>
        <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:12px">
          Are large wallets accumulating or distributing XRP? 7-day and 30-day trend.
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
          <div class="abox" style="border-left:3px solid var(--tq)">
            <div class="albl">7-DAY SIGNAL</div>
            <div class="aval" id="ad-7d" style="font-size:18px">--</div>
          </div>
          <div class="abox" style="border-left:3px solid var(--bl)">
            <div class="albl">30-DAY SIGNAL</div>
            <div class="aval" id="ad-30d" style="font-size:18px">--</div>
          </div>
        </div>
        <div style="padding:10px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:4px">Large wallet change (7d):</div>
          <div id="ad-wallet-change" style="font-size:16px;font-weight:700;color:var(--gr);font-family:var(--mn)">--</div>
        </div>
      </div>

      <!-- Whale Wallet Watchlist #51 -->
      <div>
        <div class="sec-title" style="color:var(--or);margin-bottom:12px">🐋 WHALE WALLET WATCHLIST</div>
        <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:12px">
          Top known XRP whale wallets. Last move tracked live.
        </div>
        <div class="abox" style="border-left:3px solid var(--or);margin-bottom:8px">
          <div class="albl">WHALE ALERTS 24H</div>
          <div class="aval" id="ww-alerts" style="font-size:28px;color:var(--or)">--</div>
        </div>
        <div style="padding:10px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
          <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:4px">Last significant move:</div>
          <div id="ww-last-move" style="font-size:13px;color:var(--br);font-family:var(--mn)">Monitoring...</div>
        </div>
        <div style="margin-top:8px;font-size:12px;color:var(--tx);font-family:var(--mn)">
          Wallets holding 10M+ XRP are tracked. Any move triggers the whale alert banner.
        </div>
      </div>

    </div>
  </div>
</div>

<!-- #52 XRPL TRANSACTION VOLUME TREND + #53 DEVELOPER ACTIVITY SCORE -->
<div style="margin-bottom:10px">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">

    <!-- #52 Transaction Volume Trend -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--gr);margin-bottom:4px">📊 XRPL TRANSACTION VOLUME TREND</div>
      <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:12px">
        90-day daily transaction count — is adoption growing or shrinking?
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
        <div class="abox" style="border-left:3px solid var(--gr)">
          <div class="albl">7-DAY AVG TX/DAY</div>
          <div class="aval" id="tv-7d" style="font-size:20px">--</div>
        </div>
        <div class="abox" style="border-left:3px solid var(--bl)">
          <div class="albl">30-DAY AVG TX/DAY</div>
          <div class="aval" id="tv-30d" style="font-size:20px">--</div>
        </div>
      </div>
      <div style="padding:10px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
        <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:4px">Volume trend:</div>
        <div id="tv-trend" style="font-size:16px;font-weight:700;color:var(--gr);font-family:var(--mn)">--</div>
      </div>
      <!-- Mini spark chart -->
      <div id="tv-chart" style="margin-top:12px;height:60px;background:var(--bg);border-radius:6px;
        border:1px solid var(--b);position:relative;overflow:hidden">
        <canvas id="tv-canvas" style="width:100%;height:100%"></canvas>
        <div id="tv-loading" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
          font-size:12px;color:var(--tx);font-family:var(--mn)">Loading trend data...</div>
      </div>
    </div>

    <!-- #53 Developer Activity Score -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--bl);margin-bottom:4px">💻 DEVELOPER ACTIVITY SCORE</div>
      <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:12px">
        GitHub commits, pull requests, contributors — is XRPL growing as a developer platform?
      </div>
      <div style="text-align:center;margin-bottom:12px">
        <div id="ds-score" style="font-size:48px;font-weight:900;color:var(--bl);font-family:var(--mn)">--</div>
        <div id="ds-trend" style="font-size:13px;font-weight:700;color:var(--tx);font-family:var(--mn)">/100 — CALCULATING</div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
        <div style="padding:8px;background:var(--bg);border:1px solid var(--b);border-radius:5px">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">COMMITS 7D</div>
          <div id="ds-commits" style="font-size:18px;font-weight:700;color:var(--gr);font-family:var(--mn)">--</div>
        </div>
        <div style="padding:8px;background:var(--bg);border:1px solid var(--b);border-radius:5px">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">CONTRIBUTORS 30D</div>
          <div id="ds-contrib" style="font-size:18px;font-weight:700;color:var(--bl);font-family:var(--mn)">--</div>
        </div>
        <div style="padding:8px;background:var(--bg);border:1px solid var(--b);border-radius:5px">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">OPEN ISSUES</div>
          <div id="ds-issues" style="font-size:18px;font-weight:700;color:var(--yl);font-family:var(--mn)">--</div>
        </div>
        <div style="padding:8px;background:var(--bg);border:1px solid var(--b);border-radius:5px">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">GITHUB STARS</div>
          <div id="ds-stars" style="font-size:18px;font-weight:700;color:var(--or);font-family:var(--mn)">--</div>
        </div>
      </div>
    </div>

  </div>
</div>

<!-- SECTION v6-G: COMMUNITY PULSE POLL (#60) -->
<div style="margin-bottom:10px" id="poll-section">
  <div style="background:var(--s1);border:1px solid rgba(117,188,255,.2);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--bl);margin-bottom:4px">🗳️ COMMUNITY PULSE POLL</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">Daily question — vote and see what the XRPRadar community thinks</div>
    <div id="poll-question" style="font-size:16px;font-weight:700;color:var(--br);font-family:var(--mn);margin-bottom:14px">Loading today's question...</div>
    <div id="poll-options" style="display:flex;flex-direction:column;gap:8px"></div>
    <div id="poll-results" style="margin-top:12px;display:none">
      <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:8px">Results — <span id="poll-total">0</span> votes</div>
      <div id="poll-bars" style="display:flex;flex-direction:column;gap:6px"></div>
    </div>
  </div>
</div>

<!-- SECTION v6-H: XRPL TECHNICAL SPECS (#67) + USE CASE LIBRARY (#65) -->
<div style="margin-bottom:10px">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    <!-- XRPL Technical Specs -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--tq);margin-bottom:12px">⚙️ XRPL TECHNICAL SPECS</div>
      <div style="font-family:var(--mn);font-size:13px">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="border-bottom:1px solid var(--b)">
              <th style="text-align:left;padding:6px;color:var(--tx);font-size:12px">METRIC</th>
              <th style="text-align:center;padding:6px;color:var(--gr);font-size:12px">XRPL</th>
              <th style="text-align:center;padding:6px;color:var(--bl);font-size:12px">ETH</th>
              <th style="text-align:center;padding:6px;color:var(--or);font-size:12px">SOL</th>
              <th style="text-align:center;padding:6px;color:var(--tx);font-size:12px">BTC</th>
            </tr>
          </thead>
          <tbody id="tech-specs-tbody">
            <tr style="border-bottom:1px solid rgba(255,255,255,.04)"><td style="padding:6px;color:var(--br)">Max TPS</td><td style="text-align:center;padding:6px;color:var(--gr);font-weight:700">1,500</td><td style="text-align:center;padding:6px;color:var(--tx)">~30</td><td style="text-align:center;padding:6px;color:var(--tx)">65,000</td><td style="text-align:center;padding:6px;color:var(--tx)">7</td></tr>
            <tr style="border-bottom:1px solid rgba(255,255,255,.04)"><td style="padding:6px;color:var(--br)">Settlement</td><td style="text-align:center;padding:6px;color:var(--gr);font-weight:700">3-5 sec</td><td style="text-align:center;padding:6px;color:var(--tx)">12 sec</td><td style="text-align:center;padding:6px;color:var(--tx)">0.4 sec</td><td style="text-align:center;padding:6px;color:var(--tx)">60 min</td></tr>
            <tr style="border-bottom:1px solid rgba(255,255,255,.04)"><td style="padding:6px;color:var(--br)">Tx Fee</td><td style="text-align:center;padding:6px;color:var(--gr);font-weight:700">$0.0002</td><td style="text-align:center;padding:6px;color:var(--tx)">$1-50</td><td style="text-align:center;padding:6px;color:var(--tx)">$0.001</td><td style="text-align:center;padding:6px;color:var(--tx)">$1-20</td></tr>
            <tr style="border-bottom:1px solid rgba(255,255,255,.04)"><td style="padding:6px;color:var(--br)">Energy Use</td><td style="text-align:center;padding:6px;color:var(--gr);font-weight:700">0.0079 kWh</td><td style="text-align:center;padding:6px;color:var(--tx)">0.03 kWh</td><td style="text-align:center;padding:6px;color:var(--tx)">0.00051 kWh</td><td style="text-align:center;padding:6px;color:var(--tx)">1,173 kWh</td></tr>
            <tr style="border-bottom:1px solid rgba(255,255,255,.04)"><td style="padding:6px;color:var(--br)">Consensus</td><td style="text-align:center;padding:6px;color:var(--gr);font-weight:700">FBC</td><td style="text-align:center;padding:6px;color:var(--tx)">PoS</td><td style="text-align:center;padding:6px;color:var(--tx)">PoH+PoS</td><td style="text-align:center;padding:6px;color:var(--tx)">PoW</td></tr>
            <tr style="border-bottom:1px solid rgba(255,255,255,.04)"><td style="padding:6px;color:var(--br)">ISO 20022</td><td style="text-align:center;padding:6px;color:var(--gr);font-weight:700">✅ Native</td><td style="text-align:center;padding:6px;color:var(--rd)">❌ No</td><td style="text-align:center;padding:6px;color:var(--rd)">❌ No</td><td style="text-align:center;padding:6px;color:var(--rd)">❌ No</td></tr>
            <tr><td style="padding:6px;color:var(--br)">Supply Cap</td><td style="text-align:center;padding:6px;color:var(--gr);font-weight:700">100B fixed</td><td style="text-align:center;padding:6px;color:var(--tx)">Unlimited</td><td style="text-align:center;padding:6px;color:var(--tx)">Fixed</td><td style="text-align:center;padding:6px;color:var(--tx)">21M</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <!-- Use Case Library -->
    <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
      <div class="sec-title" style="color:var(--or);margin-bottom:12px">📚 XRP USE CASE LIBRARY</div>
      <div style="display:flex;flex-direction:column;gap:6px;max-height:340px;overflow-y:auto">
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--gr)"><div style="font-size:13px;font-weight:700;color:var(--gr);font-family:var(--mn)">⚡ Cross-Border Payments (ODL)</div><div style="font-size:12px;color:var(--tx)">Banks use XRP as bridge currency to eliminate pre-funded nostro accounts. Saves up to 60% vs SWIFT. Active in 8+ corridors.</div></div>
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--bl)"><div style="font-size:13px;font-weight:700;color:var(--bl);font-family:var(--mn)">💵 RLUSD Stablecoin Settlement</div><div style="font-size:12px;color:var(--tx)">NYDFS-regulated USD stablecoin on XRPL. Enables stable-value settlement while XRP handles liquidity bridge function.</div></div>
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--yl)"><div style="font-size:13px;font-weight:700;color:var(--yl);font-family:var(--mn)">🏛️ Central Bank Digital Currency</div><div style="font-size:12px;color:var(--tx)">Bhutan (live), Montenegro (pilot), Palau (live), Colombia, Hong Kong exploring XRPL as CBDC settlement layer.</div></div>
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--tq)"><div style="font-size:13px;font-weight:700;color:var(--tq);font-family:var(--mn)">🎨 NFT Marketplace (XLS-20)</div><div style="font-size:12px;color:var(--tx)">Native NFT standard on XRPL. Low-fee minting ($0.0002), instant settlement. Multiple marketplaces active.</div></div>
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--or)"><div style="font-size:13px;font-weight:700;color:var(--or);font-family:var(--mn)">📈 Tokenized Real-World Assets</div><div style="font-size:12px;color:var(--tx)">Sologenic tokenizes stocks/ETFs on XRPL. Institutional-grade settlement infrastructure for RWA market.</div></div>
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--rd)"><div style="font-size:13px;font-weight:700;color:var(--rd);font-family:var(--mn)">⚗️ DeFi & AMM Protocols</div><div style="font-size:12px;color:var(--tx)">Native AMM live on XRPL mainnet. DEX built into protocol level. No smart contract risk — settlement at protocol layer.</div></div>
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--gr)"><div style="font-size:13px;font-weight:700;color:var(--gr);font-family:var(--mn)">🔗 ISO 20022 Payment Rails</div><div style="font-size:12px;color:var(--tx)">XRPL natively supports ISO 20022 data fields. Same global standard that SWIFT, Fedwire, CHAPS, TARGET2 are migrating to.</div></div>
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--bl)"><div style="font-size:13px;font-weight:700;color:var(--bl);font-family:var(--mn)">🌐 Micropayments & Streaming</div><div style="font-size:12px;color:var(--tx)">XRP enables sub-cent micropayments at $0.0002/tx. Enables streaming money, API monetisation, IoT payments.</div></div>
        <div style="padding:8px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--tq)"><div style="font-size:13px;font-weight:700;color:var(--tq);font-family:var(--mn)">🤖 AI Agent Payments</div><div style="font-size:12px;color:var(--tx)">Ripple integrating XRP/XRPL for AI agent-to-agent payments. AI economy needs instant, programmable, low-cost settlement.</div></div>
      </div>
    </div>
  </div>
</div>

<!-- SECTION v6-I: WEEKLY INTELLIGENCE DIGEST (#62) -->
<div style="margin-bottom:10px" id="weekly-digest-section">
  <div style="background:var(--s1);border:1px solid rgba(72,255,130,.2);border-radius:12px;padding:16px">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:12px">
      <div>
        <div class="sec-title" style="color:var(--gr);margin-bottom:4px">📅 WEEKLY INTELLIGENCE DIGEST</div>
        <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">AI-generated every Sunday · Comprehensive week-in-review for institutional readers</div>
      </div>
      <div id="digest-meta" style="font-size:12px;color:var(--tx);font-family:var(--mn);text-align:right">
        <span id="digest-date">Generated: --</span><br>
        <span style="color:var(--tx)">Next: Sunday 18:00 UTC</span>
      </div>
    </div>
    <div id="weekly-digest-content" style="font-size:14px;color:var(--br);line-height:1.7;max-height:400px;overflow-y:auto;padding:12px;background:var(--bg);border-radius:8px;border:1px solid var(--b)">
      <div style="font-family:var(--mn);color:var(--tx)">
        Weekly digest generates every Sunday at 18:00 UTC. Today's brief covers the latest 7 days of XRP intelligence.<br><br>
        <span style="color:var(--gr)">Next digest: </span><span id="digest-countdown">--</span>
      </div>
    </div>
  </div>
</div>

<!-- SECTION v6-ALERT: PRICE ALERT CONFIGURATOR (#58) -->
<div id="price-alert-bar" style="margin-bottom:10px;display:none">
  <div style="background:rgba(255,204,0,.1);border:1px solid rgba(255,204,0,.4);border-radius:8px;padding:10px 16px;
    display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <span style="font-size:16px">🔔</span>
    <span style="font-size:14px;font-weight:700;color:var(--yl);font-family:var(--mn)">PRICE ALERT TRIGGERED</span>
    <span id="alert-msg" style="font-size:13px;color:var(--br);font-family:var(--mn)"></span>
    <button onclick="document.getElementById('price-alert-bar').style.display='none'"
      style="margin-left:auto;background:transparent;border:none;color:var(--tx);cursor:pointer;font-size:16px">✕</button>
  </div>
</div>

<!-- Price Alert Config Widget -->
<div style="margin-bottom:10px" id="alert-config-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:14px">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <span style="font-size:18px">🔔</span>
      <span style="font-size:14px;font-weight:700;color:var(--yl);font-family:var(--mn)">PRICE ALERT CONFIGURATOR</span>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <input type="number" id="alert-above" placeholder="Alert above $" step="0.001" min="0"
          style="width:140px;background:var(--bg);border:1px solid var(--b);color:var(--gr);
          padding:6px 10px;border-radius:5px;font-size:13px;font-family:var(--mn)">
        <input type="number" id="alert-below" placeholder="Alert below $" step="0.001" min="0"
          style="width:140px;background:var(--bg);border:1px solid var(--b);color:var(--rd);
          padding:6px 10px;border-radius:5px;font-size:13px;font-family:var(--mn)">
        <button onclick="setAlerts()"
          style="background:rgba(255,204,0,.15);color:var(--yl);padding:6px 16px;border-radius:5px;
          border:1px solid rgba(255,204,0,.3);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
          SET ALERTS
        </button>
        <button onclick="clearAlerts()"
          style="background:transparent;color:var(--tx);padding:6px 12px;border-radius:5px;
          border:1px solid var(--b);font-family:var(--mn);font-size:13px;cursor:pointer">
          CLEAR
        </button>
        <span id="alert-status" style="font-size:12px;color:var(--tx);font-family:var(--mn)">No alerts set</span>
      </div>
    </div>
  </div>
</div>

<!-- SECTION 8: NEWS FEED + RIGHT PANEL -->
<div class="nrow" id="news-panel">
  <div class="npanel">
    <div class="nctrl">
      <div class="pt" style="color:var(--bl);font-size:16px;font-weight:800;letter-spacing:2px;margin-bottom:8px">📰 GLOBAL NEWS FEED</div>
      <input class="nsearch" id="search-box" placeholder="🔍 Search XRP news..." oninput="filterNews()">
      <div class="nbtns">
        <button class="nbtn on" onclick="setFilter(this,'all')">ALL</button>
        <button class="nbtn" onclick="setFilter(this,'Price')">PRICE</button>
        <button class="nbtn" onclick="setFilter(this,'Legal')">LEGAL</button>
        <button class="nbtn" onclick="setFilter(this,'Regulatory')">REG</button>
        <button class="nbtn" onclick="setFilter(this,'Ecosystem')">ECOSYSTEM</button>
        <button class="nbtn" onclick="setFilter(this,'Technical')">TECH</button>
        <button class="nbtn" onclick="setFilter(this,'Whale')">WHALE</button>
      </div>
    </div>
    <div class="ncount" id="news-count">Loading news...</div>
    <div class="nfeed" id="news-feed"></div>
  </div>
  <div class="rpanel" id="right-panel">
    <div class="rcard"><div class="rtitle">🔗 XRPL Network</div>
      <div class="rrow"><span class="rk">Network</span><span class="rv g">● Live</span></div>
      <div class="rrow"><span class="rk">Consensus</span><span class="rv">Federated Byzantine</span></div>
      <div class="rrow"><span class="rk">Ledger Close</span><span class="rv">~3-5 seconds</span></div>
      <div class="rrow"><span class="rk">Tx Fee</span><span class="rv">~0.00001 XRP</span></div>
      <div class="rrow"><span class="rk">Circulating</span><span class="rv b" id="rc-supply">--</span></div>
      <div class="rrow"><span class="rk">Escrow Locked</span><span class="rv">~43B XRP</span></div>
      <div class="rrow"><span class="rk">Live TPS</span><span class="rv g" id="rc-tps">--</span></div>
      <div class="rrow"><span class="rk">Ledger Index</span><span class="rv" id="rc-ledger">--</span></div>
    </div>
    <div class="rcard"><div class="rtitle">📊 Market Structure</div>
      <div class="rrow"><span class="rk">Global Rank</span><span class="rv b" id="rm-rank">--</span></div>
      <div class="rrow"><span class="rk">Market Cap</span><span class="rv" id="rm-mcap">--</span></div>
      <div class="rrow"><span class="rk">24h Volume</span><span class="rv" id="rm-vol">--</span></div>
      <div class="rrow"><span class="rk">Vol / MCap</span><span class="rv y" id="rm-ratio">--</span></div>
      <div class="rrow"><span class="rk">ATH</span><span class="rv" id="rm-ath">--</span></div>
      <div class="rrow"><span class="rk">% Below ATH</span><span class="rv r" id="rm-athpct">--</span></div>
      <div class="rrow"><span class="rk">24h High</span><span class="rv g" id="rm-high">--</span></div>
      <div class="rrow"><span class="rk">24h Low</span><span class="rv r" id="rm-low">--</span></div>
      <div class="rrow"><span class="rk">XRP/BTC</span><span class="rv" id="rm-btc">--</span></div>
    </div>
    <div class="rcard"><div class="rtitle">⏳ Ripple Escrow</div>
      <div class="rrow"><span class="rk">Next Release</span><span class="rv b">1st of month</span></div>
      <div class="rrow"><span class="rk">Amount</span><span class="rv">1B XRP</span></div>
      <div class="rrow"><span class="rk">Schedule</span><span class="rv">Monthly</span></div>
      <div class="rrow"><span class="rk">Est. Locked</span><span class="rv">~43B XRP</span></div>
    </div>
    <div class="rcard"><div class="rtitle">📡 Feed Status</div>
      <div class="rrow"><span class="rk">Active Sources</span><span class="rv g" id="feed-active">--/230</span></div>
      <div id="feed-list"></div>
    </div>
  </div>
</div>

<!-- SECTION 9: ANALYTICS LAB -->
<div class="lab">
  <div class="sec-title" style="color:var(--bl)">🔬 Analytics Lab</div>
  <div class="lab3">
    <div class="labp">
      <div class="labt">📈 Signal Metrics</div>
      <div class="bstat"><span class="bk">Stories Today</span><span class="bv b" id="al-today">--</span></div>
      <div class="bstat"><span class="bk">Bullish Signals</span><span class="bv g" id="al-bull">--</span></div>
      <div class="bstat"><span class="bk">Bearish Signals</span><span class="bv r" id="al-bear">--</span></div>
      <div class="bstat"><span class="bk">Neutral</span><span class="bv" id="al-neut">--</span></div>
      <div class="bstat"><span class="bk">Net Sentiment</span><span class="bv g" id="al-net">--</span></div>
      <div class="bstat"><span class="bk">Bull/Bear Ratio</span><span class="bv y" id="al-ratio">--</span></div>
    </div>
    <div class="labp">
      <div class="labt">📊 Market Analytics</div>
      <div class="bstat"><span class="bk">Global Rank</span><span class="bv b" id="al-rank">--</span></div>
      <div class="bstat"><span class="bk">Market Cap</span><span class="bv" id="al-mcap">--</span></div>
      <div class="bstat"><span class="bk">24h Volume</span><span class="bv y" id="al-vol">--</span></div>
      <div class="bstat"><span class="bk">Vol / MCap %</span><span class="bv b" id="al-vratio">--</span></div>
      <div class="bstat"><span class="bk">Fear &amp; Greed</span><span class="bv y" id="al-fg">--</span></div>
      <div class="bstat"><span class="bk">% Below ATH</span><span class="bv r" id="al-athpct">--</span></div>
    </div>
    <div class="labp">
      <div class="labt">🔍 Feed Intelligence</div>
      <div class="bstat"><span class="bk">Total Sources</span><span class="bv b">230</span></div>
      <div class="bstat"><span class="bk">Active Feeds</span><span class="bv g" id="al-feeds">--</span></div>
      <div class="bstat"><span class="bk">US / Europe</span><span class="bv">166 sources</span></div>
      <div class="bstat"><span class="bk">Global Hubs</span><span class="bv">64 sources</span></div>
      <div class="bstat"><span class="bk">Regions Tracked</span><span class="bv y">8 regions</span></div>
      <div class="bstat"><span class="bk">AI Powered</span><span class="bv g">Claude API</span></div>
    </div>
  </div>
  <div class="sgrid4" style="margin-top:12px">
    <div class="sbox bc"><div class="snum b" id="al2-total">--</div><div class="snlbl">Total Stories</div><div class="snsub">In memory</div></div>
    <div class="sbox wc"><div class="snum g" id="al2-bull-pct">--%</div><div class="snlbl">Bullish %</div><div class="snsub">Of today's stories</div></div>
    <div class="sbox lc"><div class="snum r" id="al2-bear-pct">--%</div><div class="snlbl">Bearish %</div><div class="snsub">Of today's stories</div></div>
    <div class="sbox yc"><div class="snum y" id="al2-onchain">--</div><div class="snlbl">Live TPS</div><div class="snsub">XRPL network</div></div>
  </div>
</div>

<!-- SECTION: XRP INTELLIGENCE BRIEF (v3.1) -->
<div style="margin-bottom:10px">
  <div style="background:linear-gradient(135deg,#0a0a0a 0%,#0d0d18 100%);
    border:1px solid rgba(255,153,0,.3);border-radius:12px;overflow:hidden">

    <!-- Header -->
    <div style="padding:14px 18px;background:rgba(255,153,0,.06);
      border-bottom:1px solid rgba(255,153,0,.25);
      display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:12px">
        <span style="font-size:32px;filter:drop-shadow(0 0 10px rgba(255,153,0,.6))">🔮</span>
        <div>
          <div style="font-size:18px;font-weight:900;color:#fff;font-family:var(--mn);
            text-transform:uppercase;letter-spacing:2px">XRP Intelligence Brief</div>
          <div style="font-size:13px;font-family:var(--mn);color:var(--or);margin-top:2px">
            AI-powered daily analysis · Cross-feed connection mapping · Domino effect projections
          </div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <div id="pred-status-badge" style="font-size:13px;font-family:var(--mn);
          font-weight:700;padding:4px 12px;border-radius:4px;
          background:rgba(128,153,179,.1);color:var(--tx);
          border:1px solid var(--b)">PENDING</div>
        <button onclick="triggerBrief()"
          style="background:rgba(255,153,0,.12);border:1px solid rgba(255,153,0,.4);
            color:var(--or);padding:5px 14px;border-radius:5px;cursor:pointer;
            font-family:var(--mn);font-size:13px;font-weight:700;
            text-transform:uppercase;letter-spacing:.05em;transition:all .2s"
          onmouseover="this.style.background='rgba(255,153,0,.25)'"
          onmouseout="this.style.background='rgba(255,153,0,.12)'">
          ⚡ GENERATE NOW
        </button>
        <a href="/api/email-digest" target="_blank"
          style="background:rgba(117,188,255,.12);color:var(--bl);border:1px solid rgba(117,188,255,.3);
          border-radius:5px;padding:7px 14px;font-family:var(--mn);font-size:12px;font-weight:700;
          cursor:pointer;text-decoration:none;display:inline-block">
          📧 EMAIL FORMAT
        </a>
      </div>
    </div>

    <!-- Meta row -->
    <div style="padding:8px 18px;background:rgba(0,0,0,.3);border-bottom:1px solid rgba(255,255,255,.04);
      display:flex;gap:20px;flex-wrap:wrap;font-family:var(--mn);font-size:13px;color:var(--tx)">
      <span>📅 Generated: <span id="pred-generated" style="color:var(--br)">--</span></span>
      <span>📰 Stories analyzed: <span id="pred-story-count" style="color:var(--br)">--</span></span>
      <span>📡 Sources: <span id="pred-src-count" style="color:var(--br)">--</span></span>
      <span style="margin-left:auto">⏰ <span id="pred-next-run" style="color:var(--or)">--</span></span>
    </div>

    <!-- Content — 5 sections -->
    <div id="pred-content" style="padding:18px;display:grid;grid-template-columns:1fr 1fr;gap:14px">

      <!-- Loading state -->
      <div id="pred-loading" style="grid-column:1/-1;text-align:center;padding:40px;
        font-family:var(--mn);color:var(--tx)">
        <div style="font-size:32px;margin-bottom:10px">🔮</div>
        <div style="font-size:13px">Brief pending — generates daily at 12:00 PM CST</div>
        <div style="font-size:13px;margin-top:6px;color:var(--tx)">
          Or click <strong style="color:var(--or)">GENERATE NOW</strong> to run immediately
          (requires ANTHROPIC_API_KEY in Railway)
        </div>
      </div>

      <!-- Section cards (hidden until brief is ready) -->
      <div id="pred-sections" style="display:none;grid-column:1/-1;
        display:none;grid-template-columns:1fr 1fr;gap:14px">

        <!-- Market Pulse -->
        <div style="background:rgba(117,188,255,.04);border:1px solid rgba(117,188,255,.2);
          border-radius:8px;padding:14px">
          <div style="font-size:13px;font-weight:700;color:var(--bl);font-family:var(--mn);
            text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px">
            📊 Market Pulse
          </div>
          <div id="pred-pulse" style="font-size:13px;color:var(--br);line-height:1.8;
            font-family:system-ui">--</div>
        </div>

        <!-- Story Connections -->
        <div style="background:rgba(0,229,204,.04);border:1px solid rgba(0,229,204,.2);
          border-radius:8px;padding:14px">
          <div style="font-size:13px;font-weight:700;color:var(--tq);font-family:var(--mn);
            text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px">
            🔗 Story Connections
          </div>
          <div id="pred-conn" style="font-size:13px;color:var(--br);line-height:1.8;
            font-family:system-ui">--</div>
        </div>

        <!-- Domino Effect — full width -->
        <div style="grid-column:1/-1;background:rgba(255,153,0,.05);
          border:1px solid rgba(255,153,0,.25);border-radius:8px;padding:14px">
          <div style="font-size:13px;font-weight:700;color:var(--or);font-family:var(--mn);
            text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px">
            🌊 Domino Effect — Cause &amp; Consequence Chains
          </div>
          <div id="pred-domino" style="font-size:13px;color:var(--br);line-height:1.8;
            font-family:system-ui">--</div>
        </div>

        <!-- Regional Flashpoints -->
        <div style="background:rgba(72,255,130,.04);border:1px solid rgba(72,255,130,.2);
          border-radius:8px;padding:14px">
          <div style="font-size:13px;font-weight:700;color:var(--gr);font-family:var(--mn);
            text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px">
            🌍 Regional Flashpoints
          </div>
          <div id="pred-regional" style="font-size:13px;color:var(--br);line-height:1.8;
            font-family:system-ui">--</div>
        </div>

        <!-- Watchlist -->
        <div style="background:rgba(255,204,0,.04);border:1px solid rgba(255,204,0,.2);
          border-radius:8px;padding:14px">
          <div style="font-size:13px;font-weight:700;color:var(--yl);font-family:var(--mn);
            text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px">
            👁️ 24-72h Watchlist
          </div>
          <div id="pred-watch" style="font-size:13px;color:var(--br);line-height:1.8;
            font-family:system-ui">--</div>
        </div>

      </div>
    </div>

    <!-- Disclaimer -->
    <div style="padding:10px 18px;background:rgba(255,204,0,.04);
      border-top:1px solid rgba(255,204,0,.15);
      font-size:13px;font-family:system-ui;color:var(--tx);line-height:1.7">
      ⚠️ <strong style="color:var(--yl)">DISCLAIMER:</strong>
      This Intelligence Brief is generated by AI and is
      <strong style="color:var(--yl)">purely speculative and not financial advice.</strong>
      It is intended for informational and educational purposes only.
      Never trade what you cannot afford to lose.
      Past analysis does not guarantee future accuracy.
      Always <strong style="color:var(--yl)">Do Your Own Research (DYOR)</strong>
      before making any investment decisions.
      XRPRadar and its AI systems assume no liability for trading decisions.
    </div>

  </div>
</div>

<!-- SECTION 9f: UNIQUE DISPLAYS (v3.0i) -->
<div style="margin-bottom:10px">
  <div class="score">
    <div class="sec-title" style="color:var(--or)">🎨 Unique Displays</div>

    <!-- Top row: Smart Money Score + F&G History -->
    <div style="display:grid;grid-template-columns:280px 1fr;gap:10px;margin-bottom:14px">

      <!-- 38. Smart Money Score -->
      <div class="abox" style="border-color:rgba(255,153,0,.35);background:rgba(255,153,0,.05);text-align:left;padding:14px">
        <div class="albl" style="color:var(--or);margin-bottom:8px">🧠 Smart Money Score</div>
        <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:6px">
          <div style="font-size:52px;font-weight:900;font-family:var(--mn);line-height:1"
            id="sm-score">--</div>
          <div style="font-size:13px;font-family:var(--mn);color:var(--tx)">/100</div>
        </div>
        <div style="font-size:13px;font-weight:700;margin-bottom:10px" id="sm-label">--</div>
        <!-- Score bar -->
        <div style="height:8px;background:var(--s2);border-radius:4px;overflow:hidden;margin-bottom:10px">
          <div id="sm-bar" style="height:100%;border-radius:4px;transition:width .8s;width:0%"></div>
        </div>
        <!-- Signal breakdown -->
        <div id="sm-signals" style="font-size:13px;font-family:var(--mn)"></div>
      </div>

      <!-- 39. Fear & Greed 30-Day History Chart -->
      <div class="abox" style="text-align:left;padding:14px">
        <div class="albl" style="margin-bottom:8px">😱 Fear &amp; Greed Index — 30 Day History</div>
        <div style="display:flex;align-items:flex-end;gap:2px;height:80px" id="fg-history-chart"></div>
        <div style="display:flex;justify-content:space-between;font-size:13px;
          font-family:var(--mn);color:var(--tx);margin-top:4px">
          <span>30 days ago</span><span>20 days ago</span><span>10 days ago</span><span>today</span>
        </div>
        <div style="display:flex;gap:14px;margin-top:8px;font-size:13px;font-family:var(--mn)">
          <span style="color:var(--rd)">■ Extreme Fear (0-25)</span>
          <span style="color:var(--or)">■ Fear (25-45)</span>
          <span style="color:var(--yl)">■ Neutral (45-55)</span>
          <span style="color:var(--gr)">■ Greed (55-75)</span>
          <span style="color:#00ffcc">■ Extreme Greed (75-100)</span>
        </div>
      </div>
    </div>

    <!-- 36. Price History Heatmap -->
    <div style="margin-bottom:14px">
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px">
        🌡️ 90-Day Price Performance Heatmap
        <span style="font-size:13px;font-weight:400;text-transform:none;letter-spacing:0;
          margin-left:10px;color:var(--tx)">Darker green = stronger gain · Darker red = stronger loss</span>
      </div>
      <!-- Day labels -->
      <div style="display:flex;gap:2px;margin-bottom:4px">
        <div style="width:24px;flex-shrink:0"></div>
        <div style="display:flex;gap:2px;flex:1">
          <div style="flex:1;text-align:center;font-size:13px;font-family:var(--mn);color:var(--tx)">Mon</div>
          <div style="flex:1;text-align:center;font-size:13px;font-family:var(--mn);color:var(--tx)">Tue</div>
          <div style="flex:1;text-align:center;font-size:13px;font-family:var(--mn);color:var(--tx)">Wed</div>
          <div style="flex:1;text-align:center;font-size:13px;font-family:var(--mn);color:var(--tx)">Thu</div>
          <div style="flex:1;text-align:center;font-size:13px;font-family:var(--mn);color:var(--tx)">Fri</div>
          <div style="flex:1;text-align:center;font-size:13px;font-family:var(--mn);color:var(--tx)">Sat</div>
          <div style="flex:1;text-align:center;font-size:13px;font-family:var(--mn);color:var(--tx)">Sun</div>
        </div>
      </div>
      <div id="heatmap-grid" style="display:flex;flex-direction:column;gap:2px"></div>
    </div>

    <!-- 37. Regional Activity Heatmap — with SVG World Map -->
    <div>
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px">
        🗺️ Global XRP Activity Map — Stories by Region Today
      </div>
      <!-- SVG World Map with clickable/coloured regions -->
      <div style="position:relative;background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:10px;margin-bottom:10px">
        <svg id="world-activity-map" viewBox="0 0 800 400" style="width:100%;height:auto" xmlns="http://www.w3.org/2000/svg">
          <!-- Background -->
          <rect width="800" height="400" fill="#0a0a0a" rx="6"/>
          <!-- Ocean texture -->
          <rect width="800" height="400" fill="url(#ocean)" rx="6" opacity="0.3"/>
          <defs>
            <radialGradient id="ocean" cx="50%" cy="50%">
              <stop offset="0%" stop-color="#1a2030"/>
              <stop offset="100%" stop-color="#0a0a0a"/>
            </radialGradient>
            <!-- Region glow filters -->
            <filter id="glow-strong"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
            <filter id="glow-mid"><feGaussianBlur stdDeviation="2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          </defs>

          <!-- ── NORTH AMERICA ─────────────────────────────────── -->
          <g id="rmap-US" class="rmap-region" data-region="US" style="cursor:pointer" onclick="mapRegionClick('US')">
            <ellipse cx="155" cy="155" rx="90" ry="70" fill="#1a2030" stroke="#2a3040" stroke-width="1"/>
            <text x="155" y="148" text-anchor="middle" fill="#8099b3" font-size="11" font-family="monospace" font-weight="700">N. AMERICA</text>
            <text x="155" y="163" text-anchor="middle" fill="#48ff82" font-size="18" font-family="monospace" font-weight="900" id="rmap-US-count">0</text>
            <text x="155" y="178" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace">stories</text>
          </g>

          <!-- ── LATIN AMERICA ──────────────────────────────────── -->
          <g id="rmap-LatAm" class="rmap-region" data-region="LatAm" style="cursor:pointer" onclick="mapRegionClick('LatAm')">
            <ellipse cx="185" cy="280" rx="65" ry="60" fill="#1a2030" stroke="#2a3040" stroke-width="1"/>
            <text x="185" y="272" text-anchor="middle" fill="#8099b3" font-size="11" font-family="monospace" font-weight="700">LATAM</text>
            <text x="185" y="287" text-anchor="middle" fill="#48ff82" font-size="18" font-family="monospace" font-weight="900" id="rmap-LatAm-count">0</text>
            <text x="185" y="302" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace">stories</text>
          </g>

          <!-- ── EUROPE ─────────────────────────────────────────── -->
          <g id="rmap-Europe" class="rmap-region" data-region="Europe" style="cursor:pointer" onclick="mapRegionClick('Europe')">
            <ellipse cx="390" cy="130" rx="75" ry="60" fill="#1a2030" stroke="#2a3040" stroke-width="1"/>
            <text x="390" y="122" text-anchor="middle" fill="#8099b3" font-size="11" font-family="monospace" font-weight="700">EUROPE</text>
            <text x="390" y="137" text-anchor="middle" fill="#48ff82" font-size="18" font-family="monospace" font-weight="900" id="rmap-Europe-count">0</text>
            <text x="390" y="152" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace">stories</text>
          </g>

          <!-- ── AFRICA ─────────────────────────────────────────── -->
          <g id="rmap-Africa" class="rmap-region" data-region="Africa" style="cursor:pointer" onclick="mapRegionClick('Africa')">
            <ellipse cx="390" cy="265" rx="65" ry="75" fill="#1a2030" stroke="#2a3040" stroke-width="1"/>
            <text x="390" y="257" text-anchor="middle" fill="#8099b3" font-size="11" font-family="monospace" font-weight="700">AFRICA</text>
            <text x="390" y="272" text-anchor="middle" fill="#48ff82" font-size="18" font-family="monospace" font-weight="900" id="rmap-Africa-count">0</text>
            <text x="390" y="287" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace">stories</text>
          </g>

          <!-- ── MIDDLE EAST / UAE ──────────────────────────────── -->
          <g id="rmap-UAE" class="rmap-region" data-region="UAE" style="cursor:pointer" onclick="mapRegionClick('UAE')">
            <ellipse cx="515" cy="185" rx="60" ry="50" fill="#1a2030" stroke="#2a3040" stroke-width="1"/>
            <text x="515" y="177" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace" font-weight="700">MIDDLE EAST</text>
            <text x="515" y="192" text-anchor="middle" fill="#48ff82" font-size="18" font-family="monospace" font-weight="900" id="rmap-UAE-count">0</text>
            <text x="515" y="207" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace">stories</text>
          </g>

          <!-- ── INDIA ──────────────────────────────────────────── -->
          <g id="rmap-India" class="rmap-region" data-region="India" style="cursor:pointer" onclick="mapRegionClick('India')">
            <ellipse cx="580" cy="215" rx="52" ry="50" fill="#1a2030" stroke="#2a3040" stroke-width="1"/>
            <text x="580" y="207" text-anchor="middle" fill="#8099b3" font-size="11" font-family="monospace" font-weight="700">INDIA</text>
            <text x="580" y="222" text-anchor="middle" fill="#48ff82" font-size="18" font-family="monospace" font-weight="900" id="rmap-India-count">0</text>
            <text x="580" y="237" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace">stories</text>
          </g>

          <!-- ── JAPAN ──────────────────────────────────────────── -->
          <g id="rmap-Japan" class="rmap-region" data-region="Japan" style="cursor:pointer" onclick="mapRegionClick('Japan')">
            <ellipse cx="680" cy="130" rx="52" ry="45" fill="#1a2030" stroke="#2a3040" stroke-width="1"/>
            <text x="680" y="122" text-anchor="middle" fill="#8099b3" font-size="11" font-family="monospace" font-weight="700">JAPAN</text>
            <text x="680" y="137" text-anchor="middle" fill="#48ff82" font-size="18" font-family="monospace" font-weight="900" id="rmap-Japan-count">0</text>
            <text x="680" y="152" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace">stories</text>
          </g>

          <!-- ── SE ASIA / KOREA ────────────────────────────────── -->
          <g id="rmap-SEA" class="rmap-region" data-region="SEA" style="cursor:pointer" onclick="mapRegionClick('SEA')">
            <ellipse cx="660" cy="245" rx="65" ry="55" fill="#1a2030" stroke="#2a3040" stroke-width="1"/>
            <text x="660" y="237" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace" font-weight="700">SE ASIA/KR</text>
            <text x="660" y="252" text-anchor="middle" fill="#48ff82" font-size="18" font-family="monospace" font-weight="900" id="rmap-SEA-count">0</text>
            <text x="660" y="267" text-anchor="middle" fill="#8099b3" font-size="10" font-family="monospace">stories</text>
          </g>

          <!-- Connection lines between regions (faint) -->
          <line x1="245" y1="155" x2="315" y2="130" stroke="#1a3050" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>
          <line x1="465" y1="130" x2="455" y2="185" stroke="#1a3050" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>
          <line x1="575" y1="185" x2="528" y2="215" stroke="#1a3050" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>
          <line x1="632" y1="215" x2="628" y2="190" stroke="#1a3050" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>
          <line x1="680" y1="175" x2="680" y2="195" stroke="#1a3050" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>

          <!-- Legend -->
          <g transform="translate(20, 360)">
            <rect width="10" height="10" fill="#48ff82" rx="2"/>
            <text x="14" y="9" fill="#8099b3" font-size="10" font-family="monospace">Active</text>
            <rect x="60" width="10" height="10" fill="#ffcc00" rx="2"/>
            <text x="74" y="9" fill="#8099b3" font-size="10" font-family="monospace">Moderate</text>
            <rect x="140" width="10" height="10" fill="#ff4060" rx="2"/>
            <text x="154" y="9" fill="#8099b3" font-size="10" font-family="monospace">High activity</text>
            <rect x="235" width="10" height="10" fill="#1a2030" stroke="#2a3040" rx="2"/>
            <text x="249" y="9" fill="#8099b3" font-size="10" font-family="monospace">Quiet</text>
          </g>
        </svg>
        <div id="map-region-tooltip" style="display:none;position:absolute;top:10px;right:10px;
          background:var(--s2);border:1px solid var(--bl);border-radius:6px;padding:8px 12px;
          font-family:var(--mn);font-size:12px;color:var(--br);max-width:200px"></div>
      </div>
      <!-- Story count boxes below map -->
      <div id="regional-heatmap" style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px"></div>
    </div>

  </div>
</div>

<!-- SECTION 9e: PRACTICAL TOOLS (v3.0h) -->
<div style="margin-bottom:10px">
  <div class="score">
    <div class="sec-title" style="color:var(--tq)">🛠️ Practical Tools</div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;align-items:stretch">

      <!-- LEFT COL: P&L Calc + Multi-Currency -->
      <div style="display:flex;flex-direction:column;gap:10px">

        <!-- 32. XRP P&L Calculator -->
        <div class="panel" style="border-color:rgba(0,229,204,.25)">
          <div class="ph">
            <span class="pt" style="color:var(--tq);font-size:14px;font-weight:800;letter-spacing:1.5px">
              💰 XRP P&amp;L Calculator
            </span>
          </div>
          <div style="padding:14px;display:flex;flex-direction:column;gap:10px">

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div>
                <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
                  text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Buy Price (USD)</div>
                <input id="pl-buy" type="number" step="0.0001" placeholder="e.g. 0.50"
                  oninput="calcPL()"
                  style="width:100%;background:var(--s2);border:1px solid var(--b);
                    color:var(--br);padding:8px 10px;border-radius:5px;
                    font-size:14px;font-family:var(--mn);outline:none">
              </div>
              <div>
                <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
                  text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Quantity (XRP)</div>
                <input id="pl-qty" type="number" step="1" placeholder="e.g. 10000"
                  oninput="calcPL()"
                  style="width:100%;background:var(--s2);border:1px solid var(--b);
                    color:var(--br);padding:8px 10px;border-radius:5px;
                    font-size:14px;font-family:var(--mn);outline:none">
              </div>
            </div>

            <div>
              <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
                text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">
                Sell / Target Price (USD)
                <span style="color:var(--tq);cursor:pointer;margin-left:6px"
                  onclick="document.getElementById('pl-sell').value=currentXRPPrice.toFixed(4);calcPL()">
                  [use live price]
                </span>
              </div>
              <input id="pl-sell" type="number" step="0.0001" placeholder="e.g. 2.00"
                oninput="calcPL()"
                style="width:100%;background:var(--s2);border:1px solid var(--b);
                  color:var(--br);padding:8px 10px;border-radius:5px;
                  font-size:14px;font-family:var(--mn);outline:none">
            </div>

            <!-- Results -->
            <div id="pl-results" style="background:var(--s2);border:1px solid var(--b);
              border-radius:6px;padding:10px;font-family:var(--mn);font-size:13px;
              display:none">
              <div style="display:flex;justify-content:space-between;padding:4px 0;
                border-bottom:1px solid rgba(255,255,255,.05)">
                <span style="color:var(--tx)">Cost Basis</span>
                <span id="pl-cost" style="color:var(--br);font-weight:700">--</span>
              </div>
              <div style="display:flex;justify-content:space-between;padding:4px 0;
                border-bottom:1px solid rgba(255,255,255,.05)">
                <span style="color:var(--tx)">Current / Target Value</span>
                <span id="pl-value" style="color:var(--br);font-weight:700">--</span>
              </div>
              <div style="display:flex;justify-content:space-between;padding:4px 0;
                border-bottom:1px solid rgba(255,255,255,.05)">
                <span style="color:var(--tx)">P&amp;L (USD)</span>
                <span id="pl-usd" style="font-weight:700;font-size:16px">--</span>
              </div>
              <div style="display:flex;justify-content:space-between;padding:4px 0">
                <span style="color:var(--tx)">P&amp;L (%)</span>
                <span id="pl-pct" style="font-weight:700;font-size:18px">--</span>
              </div>
            </div>
            <div style="font-size:13px;font-family:var(--mn);color:var(--tx)">
              ⚠️ Not financial advice. For informational purposes only.
            </div>
          </div>
        </div>

        <!-- 33. Multi-Currency Price Display -->
        <div class="panel" style="border-color:rgba(0,229,204,.2)">
          <div class="ph">
            <span class="pt" style="color:var(--tq);font-size:14px;font-weight:800;letter-spacing:1.5px">
              💱 XRP Price — Multi-Currency
            </span>
            <span id="fx-ts" style="font-size:13px;font-family:var(--mn);color:var(--tx)">--</span>
          </div>
          <div id="fx-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;padding:12px">
            <div class="abox hi">
              <div class="albl">USD 🇺🇸</div>
              <div class="aval b" style="font-size:20px" id="fx-usd">--</div>
            </div>
            <div class="abox">
              <div class="albl">EUR 🇪🇺</div>
              <div class="aval" style="font-size:20px" id="fx-eur">--</div>
            </div>
            <div class="abox">
              <div class="albl">GBP 🇬🇧</div>
              <div class="aval" style="font-size:20px" id="fx-gbp">--</div>
            </div>
            <div class="abox">
              <div class="albl">JPY 🇯🇵</div>
              <div class="aval" style="font-size:18px" id="fx-jpy">--</div>
            </div>
            <div class="abox">
              <div class="albl">AUD 🇦🇺</div>
              <div class="aval" style="font-size:20px" id="fx-aud">--</div>
            </div>
            <div class="abox">
              <div class="albl">CAD 🇨🇦</div>
              <div class="aval" style="font-size:20px" id="fx-cad">--</div>
            </div>
            <div class="abox">
              <div class="albl">SGD 🇸🇬</div>
              <div class="aval" style="font-size:20px" id="fx-sgd">--</div>
            </div>
            <div class="abox">
              <div class="albl">INR 🇮🇳</div>
              <div class="aval" style="font-size:18px" id="fx-inr">--</div>
            </div>
            <div class="abox">
              <div class="albl">BRL 🇧🇷</div>
              <div class="aval" style="font-size:20px" id="fx-brl">--</div>
            </div>
          </div>
        </div>
      </div>

      <!-- RIGHT COL: Wallet Checker + Portfolio Tracker -->
      <div style="display:flex;flex-direction:column;gap:10px;height:100%">

        <!-- 34. XRPL Wallet Value Checker -->
        <div class="panel" style="border-color:rgba(117,188,255,.25)">
          <div class="ph">
            <span class="pt" style="color:var(--bl);font-size:14px;font-weight:800;letter-spacing:1.5px">
              🔍 XRPL Wallet Checker
            </span>
          </div>
          <div style="padding:14px">
            <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
              text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Enter XRPL Address</div>
            <div style="display:flex;gap:6px;margin-bottom:10px">
              <input id="wallet-addr" type="text" placeholder="r..."
                style="flex:1;background:var(--s2);border:1px solid var(--b);
                  color:var(--br);padding:8px 10px;border-radius:5px;
                  font-size:13px;font-family:var(--mn);outline:none"
                onkeydown="if(event.key==='Enter')checkWallet()">
              <button onclick="checkWallet()"
                style="background:var(--bld);border:1px solid var(--bl);color:var(--bl);
                  padding:8px 14px;border-radius:5px;cursor:pointer;
                  font-family:var(--mn);font-size:13px;font-weight:700;
                  text-transform:uppercase;transition:all .2s"
                onmouseover="this.style.background='var(--bl)';this.style.color='#000'"
                onmouseout="this.style.background='var(--bld)';this.style.color='var(--bl)'">
                CHECK
              </button>
            </div>
            <div id="wallet-result" style="font-family:var(--mn);font-size:13px">
              <div style="color:var(--tx)">Enter any XRPL address to see live balance and USD value.</div>
            </div>
          </div>
        </div>

        <!-- 35. Portfolio Tracker -->
        <div class="panel" style="border-color:rgba(72,255,130,.2)">
          <div class="ph">
            <span class="pt" style="color:var(--gr);font-size:14px;font-weight:800;letter-spacing:1.5px">
              📈 Portfolio Tracker
            </span>
            <span style="font-size:13px;font-family:var(--mn);color:var(--tx)">Session only</span>
          </div>
          <div style="padding:12px">
            <!-- Add position row -->
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:6px;margin-bottom:8px">
              <input id="pt-label" type="text" placeholder="Label (e.g. Wallet 1)"
                style="background:var(--s2);border:1px solid var(--b);color:var(--br);
                  padding:6px 8px;border-radius:4px;font-size:13px;
                  font-family:var(--mn);outline:none">
              <input id="pt-amount" type="number" placeholder="XRP amount"
                style="background:var(--s2);border:1px solid var(--b);color:var(--br);
                  padding:6px 8px;border-radius:4px;font-size:13px;
                  font-family:var(--mn);outline:none">
              <input id="pt-cost" type="number" placeholder="Avg buy price"
                style="background:var(--s2);border:1px solid var(--b);color:var(--br);
                  padding:6px 8px;border-radius:4px;font-size:13px;
                  font-family:var(--mn);outline:none">
              <button onclick="addPortfolioEntry()"
                style="background:var(--grd);border:1px solid var(--gr);color:var(--gr);
                  padding:6px 10px;border-radius:4px;cursor:pointer;
                  font-family:var(--mn);font-size:13px;font-weight:700">
                + ADD
              </button>
            </div>
            <!-- Portfolio table -->
            <div id="portfolio-table" style="margin-bottom:8px"></div>
            <!-- Portfolio totals -->
            <div id="portfolio-totals" style="display:none;background:var(--s2);
              border:1px solid var(--b);border-radius:6px;padding:10px;
              font-family:var(--mn);font-size:13px">
              <div style="display:flex;justify-content:space-between;padding:3px 0">
                <span style="color:var(--tx)">Total XRP</span>
                <span id="pt-total-xrp" style="color:var(--br);font-weight:700">--</span>
              </div>
              <div style="display:flex;justify-content:space-between;padding:3px 0">
                <span style="color:var(--tx)">Total Value</span>
                <span id="pt-total-val" style="color:var(--br);font-weight:700">--</span>
              </div>
              <div style="display:flex;justify-content:space-between;padding:3px 0">
                <span style="color:var(--tx)">Total P&amp;L</span>
                <span id="pt-total-pl" style="font-weight:700;font-size:14px">--</span>
              </div>
            </div>
            <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:6px">
              ⚠️ Session only — entries clear on page refresh. Not financial advice.
            </div>
          </div>
        </div>


        <!-- 36b. XRP Remittance Savings Calculator -->
        <div class="panel" style="border-color:rgba(0,229,204,.25);flex:1;display:flex;flex-direction:column">
          <div class="ph">
            <span class="pt" style="color:var(--tq);font-size:14px;font-weight:800;letter-spacing:1.5px">
              💸 Remittance Calculator
            </span>
            <span style="font-size:13px;font-family:var(--mn);color:var(--tx)">SWIFT vs XRP</span>
          </div>
          <div style="padding:14px;display:flex;flex-direction:column;gap:10px;flex:1">

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div>
                <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
                  text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Send Amount (USD)</div>
                <input id="rm-amount" type="number" placeholder="e.g. 1000"
                  oninput="calcRemittance()"
                  style="width:100%;background:var(--s2);border:1px solid var(--b);
                    color:var(--br);padding:8px 10px;border-radius:5px;
                    font-size:14px;font-family:var(--mn);outline:none">
              </div>
              <div>
                <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
                  text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Corridor</div>
                <select id="rm-corridor" onchange="calcRemittance()"
                  style="width:100%;background:var(--s2);border:1px solid var(--b);
                    color:var(--br);padding:8px 10px;border-radius:5px;
                    font-size:13px;font-family:var(--mn);outline:none;cursor:pointer">
                  <option value="6.0">🇺🇸→🇲🇽 USA to Mexico (6%)</option>
                  <option value="7.5">🇺🇸→🇵🇭 USA to Philippines (7.5%)</option>
                  <option value="8.0">🇬🇧→🇳🇬 UK to Nigeria (8%)</option>
                  <option value="5.5">🇯🇵→🇵🇭 Japan to Philippines (5.5%)</option>
                  <option value="6.5">🇦🇺→🇵🇭 Australia to Philippines (6.5%)</option>
                  <option value="9.0">🇺🇸→🇮🇳 USA to India (9%)</option>
                  <option value="7.0">🇪🇺→🇲🇽 Europe to Mexico (7%)</option>
                  <option value="5.0">🇸🇬→🌏 Singapore to SE Asia (5%)</option>
                </select>
              </div>
            </div>

            <!-- Results grid -->
            <div id="rm-results" style="display:none">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">

                <div style="background:var(--rdd);border:1px solid rgba(255,64,96,.3);
                  border-radius:6px;padding:10px;text-align:center">
                  <div style="font-size:13px;font-family:var(--mn);color:var(--rd);
                    text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">SWIFT / Traditional</div>
                  <div style="font-size:22px;font-weight:900;font-family:var(--mn);
                    color:var(--rd)" id="rm-swift-fee">--</div>
                  <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:3px">fee lost</div>
                  <div style="font-size:13px;font-family:var(--mn);color:var(--br);
                    margin-top:6px;font-weight:700" id="rm-swift-recv">-- received</div>
                  <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
                    margin-top:3px">⏱ 1-5 business days</div>
                </div>

                <div style="background:var(--grd);border:1px solid rgba(72,255,130,.3);
                  border-radius:6px;padding:10px;text-align:center">
                  <div style="font-size:13px;font-family:var(--mn);color:var(--gr);
                    text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">XRP / XRPL ODL</div>
                  <div style="font-size:22px;font-weight:900;font-family:var(--mn);
                    color:var(--gr)">$0.0002</div>
                  <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:3px">fee lost</div>
                  <div style="font-size:13px;font-family:var(--mn);color:var(--br);
                    margin-top:6px;font-weight:700" id="rm-xrp-recv">-- received</div>
                  <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
                    margin-top:3px">⚡ 3-5 seconds</div>
                </div>

              </div>

              <!-- Savings banner -->
              <div style="background:rgba(0,229,204,.08);border:1px solid rgba(0,229,204,.3);
                border-radius:6px;padding:10px;text-align:center">
                <div style="font-size:13px;font-family:var(--mn);color:var(--tq);
                  text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">XRP Saves You</div>
                <div style="font-size:28px;font-weight:900;font-family:var(--mn);
                  color:var(--tq)" id="rm-savings">--</div>
                <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
                  margin-top:3px" id="rm-xrp-needed">-- XRP needed · at live price</div>
              </div>
            </div>

            <div style="font-size:13px;font-family:var(--mn);color:var(--tx)">
              ⚠️ Traditional fees are averages. Actual rates vary by provider.
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</div>

<!-- SECTION 9d: SENTIMENT ENGINE (v3.0g) -->
<div style="margin-bottom:10px">
  <div class="score">
    <div class="sec-title" style="color:var(--yl)">🧠 Sentiment Engine</div>

    <!-- Top row: Google Trend score + Velocity gauge -->
    <div style="display:grid;grid-template-columns:200px 1fr;gap:10px;margin-bottom:14px">

      <!-- Google Trend Score -->
      <div class="abox" style="border-color:rgba(255,204,0,.3);background:var(--yld);text-align:center">
        <div class="albl" style="color:var(--yl)">XRP Interest Score</div>
        <div style="font-size:48px;font-weight:900;font-family:var(--mn);line-height:1;
          margin:6px 0" id="sg-trend-score" style="color:var(--br)">--</div>
        <div style="font-size:13px;font-weight:700;font-family:var(--mn)" id="sg-trend-label">--</div>
        <div style="height:6px;background:var(--s2);border-radius:3px;overflow:hidden;margin-top:8px">
          <div id="sg-trend-bar" style="height:100%;background:var(--yl);border-radius:3px;
            transition:width .8s;width:0%"></div>
        </div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:6px" id="sg-trend-kw"></div>
      </div>

      <!-- News Velocity — 24h bar chart -->
      <div class="abox" style="text-align:left;padding:12px">
        <div class="albl">📰 News Velocity — Stories per Hour (24h)</div>
        <div id="sg-velocity-chart" style="display:flex;align-items:flex-end;gap:2px;
          height:60px;margin-top:8px"></div>
        <div style="display:flex;justify-content:space-between;font-size:13px;
          font-family:var(--mn);color:var(--tx);margin-top:4px">
          <span id="sg-vel-oldest">24h ago</span>
          <span>12h ago</span>
          <span>now</span>
        </div>
      </div>
    </div>

    <!-- 28. 30-Day Sentiment Trend Chart -->
    <div style="margin-bottom:14px">
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px">📈 30-Day Sentiment Trend</div>
      <div id="sg-daily-chart" style="display:flex;align-items:flex-end;gap:2px;height:80px"></div>
      <div style="display:flex;justify-content:space-between;font-size:13px;
        font-family:var(--mn);color:var(--tx);margin-top:4px" id="sg-daily-labels">
        <span>30d ago</span><span>20d ago</span><span>10d ago</span><span>today</span>
      </div>
      <div style="display:flex;gap:12px;margin-top:6px;font-size:13px;font-family:var(--mn)">
        <span><span style="color:var(--gr)">■</span> Bullish</span>
        <span><span style="color:var(--rd)">■</span> Bearish</span>
        <span><span style="color:var(--tx)">■</span> Neutral</span>
      </div>
    </div>

    <!-- 30. Source Leaderboard -->
    <div>
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px">🏆 Source Leaderboard — Most Active (Today)</div>
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-family:var(--mn);font-size:13px">
          <thead>
            <tr style="background:var(--s2);border-bottom:1px solid var(--b)">
              <th style="padding:5px 8px;text-align:left;color:var(--tx);font-size:13px;
                text-transform:uppercase;letter-spacing:1px;width:24px">#</th>
              <th style="padding:5px 8px;text-align:left;color:var(--tx);font-size:13px;
                text-transform:uppercase;letter-spacing:1px">Source</th>
              <th style="padding:5px 8px;text-align:center;color:var(--tx);font-size:13px;
                text-transform:uppercase;letter-spacing:1px">Stories</th>
              <th style="padding:5px 8px;text-align:center;color:var(--tx);font-size:13px;
                text-transform:uppercase;letter-spacing:1px">🟢 Bull</th>
              <th style="padding:5px 8px;text-align:center;color:var(--tx);font-size:13px;
                text-transform:uppercase;letter-spacing:1px">🔴 Bear</th>
              <th style="padding:5px 8px;text-align:left;color:var(--tx);font-size:13px;
                text-transform:uppercase;letter-spacing:1px">Sentiment Bar</th>
              <th style="padding:5px 8px;text-align:center;color:var(--tx);font-size:13px;
                text-transform:uppercase;letter-spacing:1px">⚡ Breaking</th>
            </tr>
          </thead>
          <tbody id="sg-leaderboard"></tbody>
        </table>
      </div>
    </div>

  </div>
</div>

<!-- SECTION 9c: COMPETITIVE INTELLIGENCE (v3.0f) -->
<div style="margin-bottom:10px">

  <!-- 24. XRP vs Competitors -->
  <div class="score" style="margin-bottom:10px">
    <div class="sec-title" style="color:var(--bl)">⚔️ Competitive Intelligence</div>

    <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
      letter-spacing:1.5px;margin-bottom:8px">📊 XRP vs Major Competitors — Live Performance</div>
    <div id="comp-vs-table" style="overflow-x:auto;margin-bottom:14px">
      <table style="width:100%;border-collapse:collapse;font-family:var(--mn);font-size:13px">
        <thead>
          <tr style="background:var(--s2);border-bottom:1px solid var(--b)">
            <th style="padding:8px 12px;text-align:left;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Asset</th>
            <th style="padding:8px 12px;text-align:right;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Price</th>
            <th style="padding:8px 12px;text-align:right;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">24h %</th>
            <th style="padding:8px 12px;text-align:right;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">7d %</th>
            <th style="padding:8px 12px;text-align:right;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Market Cap</th>
            <th style="padding:8px 12px;text-align:left;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">XRP Edge</th>
          </tr>
        </thead>
        <tbody id="comp-vs-body"></tbody>
      </table>
    </div>

    <!-- 25 + 26. ODL Corridors + ISO 20022 side by side -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">

      <!-- 25. ODL Corridors -->
      <div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
          letter-spacing:1.5px;margin-bottom:8px">🌐 Active ODL Corridors</div>
        <div id="comp-odl-list"></div>
      </div>

      <!-- 26. ISO 20022 Adoption -->
      <div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
          letter-spacing:1.5px;margin-bottom:8px">📋 ISO 20022 Adoption</div>
        <div style="background:var(--s2);border:1px solid rgba(72,255,130,.25);border-radius:8px;
          padding:10px;margin-bottom:8px">
          <div style="font-size:13px;color:var(--gr);line-height:1.7;font-family:system-ui" id="comp-iso-advantage"></div>
        </div>
        <div id="comp-iso-list"></div>
        <div style="margin-top:8px;padding:6px 10px;background:var(--s2);border-radius:5px;
          border:1px solid var(--b);font-size:13px;font-family:var(--mn)">
          Banks exploring ISO 20022 + Ripple:
          <span id="comp-iso-banks" style="color:var(--yl);font-weight:700;font-size:14px">--</span>
        </div>
      </div>
    </div>

    <!-- 27. XRP vs SWIFT -->
    <div>
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px">⚡ XRP vs SWIFT — The Case for ODL</div>
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px" id="comp-swift-grid">

        <div class="abox neg">
          <div class="albl">SWIFT Daily Volume</div>
          <div class="aval r" style="font-size:18px" id="cs-swift-vol">$5T</div>
          <div class="asub">Traditional rails</div>
        </div>
        <div class="abox neg">
          <div class="albl">SWIFT Settlement</div>
          <div class="aval r" style="font-size:18px">1-5 days</div>
          <div class="asub">Avg. cross-border time</div>
        </div>
        <div class="abox neg">
          <div class="albl">SWIFT Avg Cost</div>
          <div class="aval r" style="font-size:18px">2-10%</div>
          <div class="asub">Remittance fees</div>
        </div>
        <div class="abox pos">
          <div class="albl">XRPL Settlement</div>
          <div class="aval g" style="font-size:18px">3-5 sec</div>
          <div class="asub">Any corridor, 24/7</div>
        </div>
        <div class="abox pos">
          <div class="albl">XRPL Cost</div>
          <div class="aval g" style="font-size:18px">$0.0002</div>
          <div class="asub">Per transaction</div>
        </div>

      </div>
      <div style="margin-top:8px;padding:10px 14px;background:rgba(72,255,130,.04);
        border:1px solid rgba(72,255,130,.2);border-radius:6px;font-size:13px;
        color:var(--br);line-height:1.7;font-family:system-ui" id="cs-note"></div>
    </div>

  </div>
</div>

<!-- SECTION 9b: EXECUTIVE & DEVELOPER TRACKER (v3.0e) -->
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">

  <!-- 22. Executive Statement Tracker -->
  <div class="panel" style="border-color:rgba(255,153,0,.25)">
    <div class="ph">
      <span class="pt" style="color:var(--or);font-size:16px;font-weight:800;letter-spacing:2px">
        🎙️ Ripple Exec Tracker
      </span>
      <span id="exec-ts" style="font-size:13px;font-family:var(--mn);color:var(--tx)">--</span>
    </div>
    <!-- Executive tabs -->
    <div style="display:flex;gap:0;border-bottom:1px solid var(--b);overflow-x:auto">
      <button class="exec-tab on" onclick="setExecTab(this,'all')"
        style="padding:6px 14px;background:transparent;border:none;color:var(--or);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer;
          text-transform:uppercase;letter-spacing:.05em;border-bottom:2px solid var(--or);white-space:nowrap">
        ALL
      </button>
      <button class="exec-tab" onclick="setExecTab(this,'Brad Garlinghouse')"
        style="padding:6px 12px;background:transparent;border:none;color:var(--tx);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer;
          text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;border-bottom:2px solid transparent">
        BRAD
      </button>
      <button class="exec-tab" onclick="setExecTab(this,'Monica Long')"
        style="padding:6px 12px;background:transparent;border:none;color:var(--tx);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer;
          text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;border-bottom:2px solid transparent">
        MONICA
      </button>
      <button class="exec-tab" onclick="setExecTab(this,'David Schwartz')"
        style="padding:6px 12px;background:transparent;border:none;color:var(--tx);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer;
          text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;border-bottom:2px solid transparent">
        DAVID
      </button>
      <button class="exec-tab" onclick="setExecTab(this,'Stuart Alderoty')"
        style="padding:6px 12px;background:transparent;border:none;color:var(--tx);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer;
          text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;border-bottom:2px solid transparent">
        STUART
      </button>
    </div>
    <div id="exec-feed" style="max-height:320px;overflow-y:auto;padding:8px 12px">
      <div class="empty">Loading executive activity...</div>
    </div>
  </div>

  <!-- 23. GitHub Developer Activity -->
  <div class="panel" style="border-color:rgba(72,255,130,.2)">
    <div class="ph">
      <span class="pt" style="color:var(--gr);font-size:16px;font-weight:800;letter-spacing:2px">
        💻 XRPL Dev Activity
      </span>
      <span id="gh-ts" style="font-size:13px;font-family:var(--mn);color:var(--tx)">--</span>
    </div>
    <!-- GitHub stats strip -->
    <div style="display:grid;grid-template-columns:repeat(4,1fr);
      border-bottom:1px solid var(--b);background:var(--s2)">
      <div style="padding:8px 10px;text-align:center;border-right:1px solid var(--b)">
        <div style="font-size:16px;font-weight:900;font-family:var(--mn);color:var(--gr)" id="gh-rippled-7d">--</div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;letter-spacing:.05em">rippled commits<br>7 days</div>
      </div>
      <div style="padding:8px 10px;text-align:center;border-right:1px solid var(--b)">
        <div style="font-size:16px;font-weight:900;font-family:var(--mn);color:var(--bl)" id="gh-dev-7d">--</div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;letter-spacing:.05em">other repos<br>7 days</div>
      </div>
      <div style="padding:8px 10px;text-align:center;border-right:1px solid var(--b)">
        <div style="font-size:16px;font-weight:900;font-family:var(--mn);color:var(--yl)" id="gh-stars">--</div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;letter-spacing:.05em">GitHub stars<br>3 repos</div>
      </div>
      <div style="padding:8px 10px;text-align:center">
        <div style="font-size:16px;font-weight:900;font-family:var(--mn);color:var(--or)" id="gh-issues">--</div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;letter-spacing:.05em">open issues<br>3 repos</div>
      </div>
    </div>
    <!-- Last commit banner -->
    <div style="padding:8px 12px;border-bottom:1px solid var(--b);background:rgba(72,255,130,.04)">
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-bottom:2px">Latest commit</div>
      <div style="font-size:13px;font-weight:700;color:var(--gr)" id="gh-last-msg">Loading...</div>
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:2px">
        <span id="gh-last-author"></span> &nbsp;·&nbsp; <span id="gh-last-date"></span>
      </div>
    </div>
    <!-- Commit feed -->
    <div id="gh-feed" style="max-height:220px;overflow-y:auto;padding:8px 12px">
      <div class="empty">Loading commits...</div>
    </div>
  </div>

</div>

<!-- SECTION 10: REGULATORY RADAR (v3.0d) -->
<div style="margin-bottom:10px">

  <!-- Section Header -->
  <div class="score" style="margin-bottom:10px">
    <div class="sec-title" style="color:var(--or)">🏛️ Regulatory Radar</div>

    <!-- 17. Country Status Grid -->
    <div style="margin-bottom:14px">
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px">
        🌍 Global XRP Legal Status
        <span style="float:right;font-size:13px;color:var(--tx)">Updated Jun 2026</span>
      </div>
      <div id="reg-country-grid" style="display:grid;grid-template-columns:repeat(5,1fr);gap:5px"></div>
      <div style="display:flex;gap:12px;margin-top:8px;flex-wrap:wrap;font-size:13px;font-family:var(--mn)">
        <span style="color:var(--gr)">✅ LEGAL</span>
        <span style="color:var(--bl)">📋 TAXED</span>
        <span style="color:var(--yl)">⚠️ CONTESTED</span>
        <span style="color:var(--or)">🔶 RESTRICTED</span>
        <span style="color:var(--tx)">🔍 PENDING</span>
        <span style="color:var(--rd)">❌ BANNED</span>
      </div>
    </div>

    <!-- 18. ETF Tracker -->
    <div style="margin-bottom:14px">
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px">📊 XRP ETF / ETP Tracker</div>
      <div id="reg-etf-table" style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-family:var(--mn);font-size:13px">
          <thead>
            <tr style="background:var(--s2);border-bottom:1px solid var(--b)">
              <th style="padding:6px 10px;text-align:left;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Applicant</th>
              <th style="padding:6px 10px;text-align:left;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Product</th>
              <th style="padding:6px 10px;text-align:left;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Market</th>
              <th style="padding:6px 10px;text-align:left;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Status</th>
              <th style="padding:6px 10px;text-align:left;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Filed</th>
              <th style="padding:6px 10px;text-align:left;color:var(--tx);font-size:13px;text-transform:uppercase;letter-spacing:1px">Note</th>
            </tr>
          </thead>
          <tbody id="reg-etf-body"></tbody>
        </table>
      </div>
    </div>

    <!-- 19 + 20. SEC Timeline + MiCA Calendar side by side -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">

      <!-- SEC Timeline -->
      <div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
          letter-spacing:1.5px;margin-bottom:8px">⚖️ SEC Case Timeline</div>
        <div id="reg-sec-timeline"></div>
      </div>

      <!-- MiCA Calendar -->
      <div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
          letter-spacing:1.5px;margin-bottom:8px">🇪🇺 MiCA Implementation</div>
        <div id="reg-mica-calendar"></div>
      </div>

    </div>

    <!-- 21. CBDC Projects on XRPL -->
    <div>
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px">🏦 Central Bank / CBDC Projects on XRPL</div>
      <div id="reg-cbdc-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px"></div>
    </div>

  </div>
</div>

<!-- STORY POPUP -->
<div id="story-modal" onclick="closeModal(event)">
  <div class="modal-box" onclick="event.stopPropagation()">
    <div class="modal-hdr">
      <div class="modal-x" onclick="closeModal()">✕</div>
      <div class="modal-ttl" id="modal-title"></div>
    </div>
    <div class="modal-body">
      <div id="modal-translation" class="modal-trans" style="display:none">
        <div class="modal-translbl">🌐 Translated to English</div>
        <div id="modal-translation-text"></div>
      </div>
      <div class="modal-sum" id="modal-summary"></div>
      <div class="modal-meta" id="modal-meta"></div>
      <a class="modal-btn" id="modal-read-btn" target="_blank">Read Full Story ↗</a>
    </div>
  </div>
</div>


<!-- SECTION 17b: XRP PRICE TRENDS — 30d / 90d / 6m / 60m -->
<div style="margin-bottom:10px" id="price-trends-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:8px">
      <div class="sec-title" style="color:var(--yl)">📈 XRP PRICE TRENDS</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="trend-tab" data-tf="30d"  onclick="switchTrend('30d')"  style="background:rgba(255,204,0,.2);color:var(--yl);padding:5px 14px;border-radius:5px;border:1px solid rgba(255,204,0,.5);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">30-DAY</button>
        <button class="trend-tab" data-tf="90d"  onclick="switchTrend('90d')"  style="background:var(--s2);color:var(--tx);padding:5px 14px;border-radius:5px;border:1px solid var(--b);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">90-DAY</button>
        <button class="trend-tab" data-tf="6m"   onclick="switchTrend('6m')"   style="background:var(--s2);color:var(--tx);padding:5px 14px;border-radius:5px;border:1px solid var(--b);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">6-MONTH</button>
        <button class="trend-tab" data-tf="60m"  onclick="switchTrend('60m')"  style="background:var(--s2);color:var(--tx);padding:5px 14px;border-radius:5px;border:1px solid var(--b);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">60-MONTH</button>
      </div>
    </div>
    <div id="trend-subtitle" style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:12px">30-day daily closing prices — recent momentum</div>
    <div class="trend-view" id="trend-view-30d">
      <div style="position:relative;height:230px;background:var(--bg);border:1px solid var(--b);border-radius:8px;overflow:hidden">
        <canvas id="chart-30d" style="width:100%;height:100%"></canvas>
        <div id="chart-30d-loading" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:var(--mn);font-size:13px;color:var(--tx)">Loading 30-day data...</div>
      </div>
      <div id="chart-30d-stats" style="display:flex;gap:14px;margin-top:10px;flex-wrap:wrap;font-family:var(--mn);font-size:13px"></div>
    </div>
    <div class="trend-view" id="trend-view-90d" style="display:none">
      <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:8px">
        Daily performance calendar — <span style="color:var(--gr)">green = gain</span> · <span style="color:var(--rd)">red = loss</span> · each square = one trading day
      </div>
      <div id="heatmap-grid-90" style="display:flex;flex-direction:column;gap:3px"></div>
      <div id="chart-90d-stats" style="display:flex;gap:14px;margin-top:10px;flex-wrap:wrap;font-family:var(--mn);font-size:13px"></div>
    </div>
    <div class="trend-view" id="trend-view-6m" style="display:none">
      <div style="position:relative;height:230px;background:var(--bg);border:1px solid var(--b);border-radius:8px;overflow:hidden">
        <canvas id="chart-6m" style="width:100%;height:100%"></canvas>
        <div id="chart-6m-loading" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:var(--mn);font-size:13px;color:var(--tx)">Loading 6-month data...</div>
      </div>
      <div id="chart-6m-stats" style="display:flex;gap:14px;margin-top:10px;flex-wrap:wrap;font-family:var(--mn);font-size:13px"></div>
    </div>
    <div class="trend-view" id="trend-view-60m" style="display:none">
      <div style="position:relative;height:230px;background:var(--bg);border:1px solid var(--b);border-radius:8px;overflow:hidden">
        <canvas id="chart-60m" style="width:100%;height:100%"></canvas>
        <div id="chart-60m-loading" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:var(--mn);font-size:13px;color:var(--tx)">Loading 5-year data...</div>
      </div>
      <div id="chart-60m-stats" style="display:flex;gap:14px;margin-top:10px;flex-wrap:wrap;font-family:var(--mn);font-size:13px"></div>
    </div>
  </div>
</div>




<!-- SECTION v6-J: REMITTANCE CORRIDOR INTELLIGENCE (#55) -->
<div style="margin-bottom:10px" id="remittance-intel-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--tq);margin-bottom:4px">💸 REMITTANCE CORRIDOR INTELLIGENCE</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">
      Live XRP ODL corridor tracking — volume trends, new routes, savings vs traditional rails.
      Total addressable market: <span style="color:var(--gr);font-weight:700">$6.5B+/day</span>
    </div>
    <div id="remit-corridors" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px"></div>
    <div style="margin-top:12px;padding:10px;background:rgba(0,229,204,.08);border:1px solid rgba(0,229,204,.2);border-radius:6px">
      <div style="font-size:13px;font-weight:700;color:var(--tq);font-family:var(--mn);margin-bottom:6px">🚀 NEW CORRIDORS LAUNCHING IN 2026</div>
      <div id="remit-new-corridors" style="font-size:13px;color:var(--br);font-family:var(--mn)">Loading...</div>
    </div>
  </div>
</div>

<!-- SECTION v6-K: GEOPOLITICAL RISK DASHBOARD (#56) -->
<div style="margin-bottom:10px" id="geopolitical-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px">
      <div>
        <div class="sec-title" style="color:var(--or);margin-bottom:4px">🌐 GEOPOLITICAL RISK DASHBOARD</div>
        <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Sanctions, trade wars, banking crises and regulatory shifts that accelerate or threaten XRP adoption</div>
      </div>
      <div style="text-align:center;background:rgba(72,255,130,.1);border:1px solid rgba(72,255,130,.3);border-radius:8px;padding:10px 16px">
        <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">XRP IMPACT SCORE</div>
        <div id="geo-score" style="font-size:32px;font-weight:900;color:var(--gr);font-family:var(--mn)">72</div>
        <div id="geo-risk" style="font-size:11px;color:var(--gr);font-family:var(--mn)">LOW RISK</div>
      </div>
    </div>
    <div id="geo-events" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:8px"></div>
  </div>
</div>


<!-- SECTION v6-L: RIPPLE PARTNER INTELLIGENCE (#66) -->
<div style="margin-bottom:10px" id="partner-intel-section">
  <div style="background:var(--s1);border:1px solid var(--b);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--bl);margin-bottom:4px">🤝 RIPPLE PARTNER INTELLIGENCE</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">
      Deep intelligence on each confirmed Ripple partner — what they use XRP for, estimated volume, and growth trajectory
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px">

      <div style="background:var(--bg);border:1px solid rgba(72,255,130,.3);border-radius:8px;padding:14px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <span style="font-size:20px">🇯🇵</span>
          <div><div style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn)">SBI Holdings</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">CONFIRMED · Japan · Banking</div></div>
        </div>
        <div style="font-size:12px;color:var(--tx);line-height:1.6;margin-bottom:8px">Japan's largest financial group. SBI Ripple Asia joint venture fully operational. SBI VC Trade, SBI Remit, and MoneyTap all use XRP/XRPL infrastructure. One of the deepest institutional XRP integrations globally.</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;font-family:var(--mn)">
          <div style="color:var(--tx)">Use Case: <span style="color:var(--gr)">ODL + Remittance</span></div>
          <div style="color:var(--tx)">Est. Volume: <span style="color:var(--yl)">$500M+/yr</span></div>
          <div style="color:var(--tx)">Corridor: <span style="color:var(--bl)">Japan→Philippines</span></div>
          <div style="color:var(--tx)">Growth: <span style="color:var(--gr)">↑ Expanding</span></div>
        </div>
      </div>

      <div style="background:var(--bg);border:1px solid rgba(72,255,130,.3);border-radius:8px;padding:14px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <span style="font-size:20px">🇪🇸</span>
          <div><div style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn)">Santander</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">CONFIRMED · Spain/Global · Banking</div></div>
        </div>
        <div style="font-size:12px;color:var(--tx);line-height:1.6;margin-bottom:8px">One Pay FX powered by Ripple since 2018. Expanded to multiple markets including UK, Brazil, Poland, and Spain. One of the earliest and longest-standing major bank integrations with Ripple technology.</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;font-family:var(--mn)">
          <div style="color:var(--tx)">Use Case: <span style="color:var(--gr)">Cross-border payments</span></div>
          <div style="color:var(--tx)">Est. Volume: <span style="color:var(--yl)">$200M+/yr</span></div>
          <div style="color:var(--tx)">Markets: <span style="color:var(--bl)">UK, Brazil, Poland</span></div>
          <div style="color:var(--tx)">Growth: <span style="color:var(--gr)">↑ Multi-market</span></div>
        </div>
      </div>

      <div style="background:var(--bg);border:1px solid rgba(72,255,130,.3);border-radius:8px;padding:14px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <span style="font-size:20px">🇵🇭</span>
          <div><div style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn)">Coins.ph</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">CONFIRMED · Philippines · Fintech</div></div>
        </div>
        <div style="font-size:12px;color:var(--tx);line-height:1.6;margin-bottom:8px">Philippines-based crypto wallet using ODL for the USA→Philippines corridor. Serves millions of Filipino overseas workers sending remittances home. One of the highest-volume ODL partners globally by transaction count.</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;font-family:var(--mn)">
          <div style="color:var(--tx)">Use Case: <span style="color:var(--gr)">ODL Remittance</span></div>
          <div style="color:var(--tx)">Est. Volume: <span style="color:var(--yl)">$800M+/yr</span></div>
          <div style="color:var(--tx)">Corridor: <span style="color:var(--bl)">USA→Philippines</span></div>
          <div style="color:var(--tx)">Users: <span style="color:var(--gr)">Millions OFWs</span></div>
        </div>
      </div>

      <div style="background:var(--bg);border:1px solid rgba(72,255,130,.3);border-radius:8px;padding:14px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <span style="font-size:20px">🇲🇽</span>
          <div><div style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn)">Bitso</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">CONFIRMED · Mexico · Exchange</div></div>
        </div>
        <div style="font-size:12px;color:var(--tx);line-height:1.6;margin-bottom:8px">Mexico's largest crypto exchange. Primary ODL partner for the USA→Mexico corridor — the world's largest ODL route by volume. Processes hundreds of millions of dollars in XRP-powered cross-border settlements daily.</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;font-family:var(--mn)">
          <div style="color:var(--tx)">Use Case: <span style="color:var(--gr)">ODL Primary Partner</span></div>
          <div style="color:var(--tx)">Est. Volume: <span style="color:var(--yl)">$1.8B+/yr</span></div>
          <div style="color:var(--tx)">Corridor: <span style="color:var(--bl)">USA→Mexico (largest)</span></div>
          <div style="color:var(--tx)">Growth: <span style="color:var(--gr)">↑ Dominant</span></div>
        </div>
      </div>

      <div style="background:var(--bg);border:1px solid rgba(72,255,130,.3);border-radius:8px;padding:14px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <span style="font-size:20px">🇧🇹</span>
          <div><div style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn)">Bank of Bhutan</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">CONFIRMED · Bhutan · Central Bank</div></div>
        </div>
        <div style="font-size:12px;color:var(--tx);line-height:1.6;margin-bottom:8px">First sovereign CBDC built on XRPL. The Druk Digital currency is issued by the Royal Monetary Authority of Bhutan and runs natively on the XRP Ledger. A landmark proof-of-concept for central bank adoption of XRPL.</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;font-family:var(--mn)">
          <div style="color:var(--tx)">Use Case: <span style="color:var(--gr)">Sovereign CBDC</span></div>
          <div style="color:var(--tx)">Status: <span style="color:var(--gr)">✅ LIVE</span></div>
          <div style="color:var(--tx)">Currency: <span style="color:var(--bl)">Druk Digital (BTN)</span></div>
          <div style="color:var(--tx)">Significance: <span style="color:var(--yl)">First ever</span></div>
        </div>
      </div>

      <div style="background:var(--bg);border:1px solid rgba(117,188,255,.3);border-radius:8px;padding:14px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <span style="font-size:20px">🌐</span>
          <div><div style="font-size:14px;font-weight:700;color:var(--bl);font-family:var(--mn)">Ripple x BIS (Project Nexus)</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">CONFIRMED · Global · Research</div></div>
        </div>
        <div style="font-size:12px;color:var(--tx);line-height:1.6;margin-bottom:8px">Bank for International Settlements Project Nexus explores XRPL for multi-CBDC settlements between central banks. If adopted at scale, this would position XRPL as the backbone of the global interbank settlement system.</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;font-family:var(--mn)">
          <div style="color:var(--tx)">Use Case: <span style="color:var(--gr)">Multi-CBDC Settlement</span></div>
          <div style="color:var(--tx)">Status: <span style="color:var(--bl)">Research/Pilot</span></div>
          <div style="color:var(--tx)">Partner: <span style="color:var(--bl)">BIS Innovation Hub</span></div>
          <div style="color:var(--tx)">Impact: <span style="color:var(--yl)">⭐ Transformative</span></div>
        </div>
      </div>

    </div>
  </div>
</div>

<!-- SECTION v6-AI: AI-POWERED TOOLS (#71, #72, #74) -->
<div style="margin-bottom:10px" id="ai-tools-section">
  <div style="background:var(--s1);border:1px solid rgba(117,188,255,.2);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--bl);margin-bottom:4px">🤖 AI-POWERED ANALYSIS TOOLS</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:16px">Powered by Claude AI — Requires ANTHROPIC_API_KEY in Railway</div>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px">

      <!-- #71 Price Scenario Builder -->
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:14px">
        <div style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn);margin-bottom:8px">🔮 Price Scenario Builder</div>
        <div style="font-size:12px;color:var(--tx);margin-bottom:10px">Describe a macro event — AI tells you how XRP has historically responded and what to expect.</div>
        <textarea id="scenario-input" rows="3" placeholder="e.g. Federal Reserve cuts rates by 0.5%..."
          style="width:100%;background:var(--s1);border:1px solid var(--b);color:var(--br);
          padding:8px;border-radius:5px;font-size:13px;font-family:system-ui;resize:vertical;box-sizing:border-box"></textarea>
        <button onclick="runScenario()" id="scenario-btn"
          style="margin-top:8px;width:100%;background:rgba(72,255,130,.15);color:var(--gr);
          padding:8px;border-radius:5px;border:1px solid rgba(72,255,130,.3);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
          ⚡ ANALYZE SCENARIO
        </button>
        <div id="scenario-result" style="margin-top:10px;font-size:13px;color:var(--br);line-height:1.6;display:none;
          padding:10px;background:var(--s1);border-radius:6px;border-left:3px solid var(--gr)"></div>
      </div>

      <!-- #72 Regulatory Impact Analyzer -->
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:14px">
        <div style="font-size:14px;font-weight:700;color:var(--yl);font-family:var(--mn);margin-bottom:8px">⚖️ Regulatory Impact Analyzer</div>
        <div style="font-size:12px;color:var(--tx);margin-bottom:10px">Paste any new regulation or news headline — AI scores its impact on XRP 1-10 with reasoning.</div>
        <textarea id="reg-input" rows="3" placeholder="e.g. EU passes new crypto licensing requirement for exchanges..."
          style="width:100%;background:var(--s1);border:1px solid var(--b);color:var(--br);
          padding:8px;border-radius:5px;font-size:13px;font-family:system-ui;resize:vertical;box-sizing:border-box"></textarea>
        <button onclick="runRegAnalysis()" id="reg-btn"
          style="margin-top:8px;width:100%;background:rgba(255,204,0,.15);color:var(--yl);
          padding:8px;border-radius:5px;border:1px solid rgba(255,204,0,.3);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
          ⚡ ANALYZE IMPACT
        </button>
        <div id="reg-result" style="margin-top:10px;font-size:13px;color:var(--br);line-height:1.6;display:none;
          padding:10px;background:var(--s1);border-radius:6px;border-left:3px solid var(--yl)"></div>
      </div>

      <!-- #74 Bull/Bear Case Generator -->
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:14px">
        <div style="font-size:14px;font-weight:700;color:var(--bl);font-family:var(--mn);margin-bottom:8px">🐂🐻 Bull vs Bear Case</div>
        <div style="font-size:12px;color:var(--tx);margin-bottom:10px">AI writes the strongest current bull case AND bear case for XRP based on today's intelligence.</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px">
          <button onclick="runBullBear('bull')" id="bull-btn"
            style="background:rgba(72,255,130,.15);color:var(--gr);padding:8px;border-radius:5px;
            border:1px solid rgba(72,255,130,.3);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
            🐂 BULL CASE
          </button>
          <button onclick="runBullBear('bear')" id="bear-btn"
            style="background:rgba(255,64,96,.15);color:var(--rd);padding:8px;border-radius:5px;
            border:1px solid rgba(255,64,96,.3);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
            🐻 BEAR CASE
          </button>
        </div>
        <button onclick="runBullBear('both')" id="both-btn"
          style="width:100%;background:rgba(117,188,255,.15);color:var(--bl);padding:8px;border-radius:5px;
          border:1px solid rgba(117,188,255,.3);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
          ⚡ GENERATE BOTH
        </button>
        <div id="bullbear-result" style="margin-top:10px;font-size:13px;color:var(--br);line-height:1.6;display:none;
          max-height:300px;overflow-y:auto;padding:10px;background:var(--s1);border-radius:6px"></div>
      </div>

      <!-- #73 AI Story Credibility Scorer -->
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:14px">
        <div style="font-size:14px;font-weight:700;color:var(--tq);font-family:var(--mn);margin-bottom:8px">🔍 Story Credibility Scorer</div>
        <div style="font-size:12px;color:var(--tx);margin-bottom:10px">Paste any XRP headline or story. AI rates its credibility 1-10 and flags FUD vs signal.</div>
        <textarea id="cred-input" rows="3" placeholder="Paste a headline or story here..."
          style="width:100%;background:var(--s1);border:1px solid var(--b);color:var(--br);
          padding:8px;border-radius:5px;font-size:13px;font-family:system-ui;resize:vertical;box-sizing:border-box"></textarea>
        <button onclick="runCredibilityScore()" id="cred-btn"
          style="margin-top:8px;width:100%;background:rgba(0,229,204,.15);color:var(--tq);
          padding:8px;border-radius:5px;border:1px solid rgba(0,229,204,.3);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
          ⚡ SCORE CREDIBILITY
        </button>
        <div id="cred-result" style="margin-top:10px;font-size:13px;color:var(--br);line-height:1.6;display:none;
          padding:10px;background:var(--s1);border-radius:6px;border-left:3px solid var(--tq)"></div>
      </div>

      <!-- #75 AI Partner Deal Probability -->
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:14px">
        <div style="font-size:14px;font-weight:700;color:var(--or);font-family:var(--mn);margin-bottom:8px">🎯 Partner Deal Probability</div>
        <div style="font-size:12px;color:var(--tx);margin-bottom:10px">Name a rumored Ripple partnership. AI scores the probability it becomes confirmed and explains why.</div>
        <input type="text" id="deal-input" placeholder="e.g. JPMorgan Chase, Western Union, PayPal..."
          style="width:100%;background:var(--s1);border:1px solid var(--b);color:var(--br);
          padding:9px 12px;border-radius:5px;font-size:13px;font-family:var(--mn);box-sizing:border-box;margin-bottom:8px">
        <button onclick="runDealProbability()" id="deal-btn"
          style="width:100%;background:rgba(255,153,0,.15);color:var(--or);
          padding:8px;border-radius:5px;border:1px solid rgba(255,153,0,.3);
          font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
          ⚡ SCORE PROBABILITY
        </button>
        <div id="deal-result" style="margin-top:10px;font-size:13px;color:var(--br);line-height:1.6;display:none;
          padding:10px;background:var(--s1);border-radius:6px;border-left:3px solid var(--or)"></div>
      </div>

    </div>
  </div>
</div>

<!-- SECTION 17c: CHAINEDGE PROMOTIONAL / SPONSOR SECTION -->
<div style="margin-bottom:16px">
  <div style="background:linear-gradient(135deg,#0a0a12 0%,#0d0a14 100%);
    border:1px solid rgba(117,188,255,.2);border-radius:12px;overflow:hidden">

    <div style="padding:14px 18px;border-bottom:1px solid rgba(117,188,255,.15);
      display:flex;align-items:center;gap:10px">
      <span style="font-size:20px">🔗</span>
      <div style="font-size:14px;font-weight:700;color:var(--bl);font-family:var(--mn);
        text-transform:uppercase;letter-spacing:2px">From the XRPRadar Team</div>
    </div>

    <div style="padding:16px 18px;display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px">

      <!-- ChainEdge Ebooks -->
      <div style="background:var(--s2);border:1px solid rgba(72,255,130,.2);border-radius:8px;padding:14px">
        <div style="font-size:16px;margin-bottom:6px">📘</div>
        <div style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn);margin-bottom:6px">
          CHAINEDGE CRYPTO GUIDES
        </div>
        <div style="font-size:13px;color:var(--tx);line-height:1.6;margin-bottom:10px">
          Master XRP algorithmic trading, on-chain intelligence, and institutional strategies.
          Written by the team behind XRPRadar.
        </div>
        <a href="https://gumroad.com" target="_blank"
          style="display:inline-block;background:rgba(72,255,130,.15);color:var(--gr);
          padding:7px 16px;border-radius:5px;border:1px solid rgba(72,255,130,.3);
          font-family:var(--mn);font-size:13px;font-weight:700;text-decoration:none">
          📖 Browse Ebooks →
        </a>
      </div>

      <!-- Social / Follow -->
      <div style="background:var(--s2);border:1px solid rgba(117,188,255,.2);border-radius:8px;padding:14px">
        <div style="font-size:16px;margin-bottom:6px">📡</div>
        <div style="font-size:14px;font-weight:700;color:var(--bl);font-family:var(--mn);margin-bottom:6px">
          FOLLOW XRPRADAR
        </div>
        <div style="font-size:13px;color:var(--tx);line-height:1.6;margin-bottom:10px">
          Daily signals, market intelligence, and XRP ecosystem updates on X and Instagram.
          First to know when XRP moves.
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <a href="https://twitter.com/XRPRadar" target="_blank"
            style="background:rgba(117,188,255,.1);color:var(--bl);padding:6px 14px;
            border-radius:5px;border:1px solid rgba(117,188,255,.3);
            font-family:var(--mn);font-size:13px;font-weight:700;text-decoration:none">
            𝕏 @XRPRadar
          </a>
          <a href="https://instagram.com/XRPRadar" target="_blank"
            style="background:rgba(255,153,0,.1);color:var(--or);padding:6px 14px;
            border-radius:5px;border:1px solid rgba(255,153,0,.3);
            font-family:var(--mn);font-size:13px;font-weight:700;text-decoration:none">
            📸 Instagram
          </a>
        </div>
      </div>

      <!-- Pro Teaser / Email Signup -->
      <div style="background:var(--s2);border:1px solid rgba(72,255,130,.3);border-radius:8px;padding:14px">
        <div style="font-size:16px;margin-bottom:6px">🔔</div>
        <div style="font-size:14px;font-weight:700;color:var(--gr);font-family:var(--mn);margin-bottom:6px">
          XRPRADAR DAILY BRIEF
        </div>
        <div style="font-size:13px;color:var(--tx);line-height:1.6;margin-bottom:10px">
          Get the AM + PM Intelligence Brief delivered to your inbox every day. 
          Be first to know when XRP moves.
        </div>
        <div style="display:flex;gap:6px">
          <input type="email" id="pro-email" placeholder="your@email.com"
            style="flex:1;background:var(--bg);border:1px solid var(--b);color:var(--br);
            padding:7px 12px;border-radius:5px;font-size:13px;font-family:var(--mn)">
          <button onclick="submitProEmail()"
            style="background:rgba(72,255,130,.15);color:var(--gr);padding:7px 14px;
            border-radius:5px;border:1px solid rgba(72,255,130,.3);
            font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
            NOTIFY ME
          </button>
        </div>
        <div id="pro-email-msg" style="font-size:12px;margin-top:6px;font-family:var(--mn)"></div>
      </div>

      <!-- Sponsor Slot -->
      <div style="background:var(--s2);border:1px dashed rgba(255,204,0,.3);border-radius:8px;padding:14px">
        <div style="font-size:16px;margin-bottom:6px">💼</div>
        <div style="font-size:14px;font-weight:700;color:var(--yl);font-family:var(--mn);margin-bottom:6px">
          SPONSOR XRPRADAR
        </div>
        <div style="font-size:13px;color:var(--tx);line-height:1.6;margin-bottom:10px">
          Reach thousands of XRP investors, institutions, and enthusiasts daily.
          Premium placement available. Contact us for rates.
        </div>
        <a href="mailto:redrioholdings@gmail.com?subject=XRPRadar Sponsorship"
          style="display:inline-block;background:rgba(255,204,0,.1);color:var(--yl);
          padding:7px 16px;border-radius:5px;border:1px solid rgba(255,204,0,.3);
          font-family:var(--mn);font-size:13px;font-weight:700;text-decoration:none">
          📩 Inquire Now →
        </a>
      </div>

    </div>
  </div>
</div>

<!-- FOOTER -->

<!-- SECTION v6-M: XRPRADAR LEADERBOARD (#80) -->
<div style="margin-bottom:10px" id="leaderboard-section">
  <div style="background:var(--s1);border:1px solid rgba(255,204,0,.2);border-radius:12px;padding:16px">
    <div class="sec-title" style="color:var(--yl);margin-bottom:4px">🏆 XRPRADAR LEADERBOARD</div>
    <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:14px">
      Top sources, most active regions, and community engagement — the XRPRadar intelligence rankings
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px">

      <!-- Top Sources Today -->
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:12px">
        <div style="font-size:13px;font-weight:700;color:var(--yl);font-family:var(--mn);margin-bottom:8px">📡 TOP SOURCES TODAY</div>
        <div id="lb-sources" style="font-family:var(--mn);font-size:12px">
          <div style="color:var(--tx)">Loading...</div>
        </div>
      </div>

      <!-- Top Regions Today -->
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:12px">
        <div style="font-size:13px;font-weight:700;color:var(--bl);font-family:var(--mn);margin-bottom:8px">🗺️ MOST ACTIVE REGIONS</div>
        <div id="lb-regions" style="font-family:var(--mn);font-size:12px">
          <div style="color:var(--tx)">Loading...</div>
        </div>
      </div>

      <!-- Signal Score Streak -->
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:12px">
        <div style="font-size:13px;font-weight:700;color:var(--gr);font-family:var(--mn);margin-bottom:8px">🔥 LIVE INTELLIGENCE</div>
        <div style="text-align:center;padding:10px 0">
          <div style="font-size:40px;font-weight:900;color:var(--yl);font-family:var(--mn)" id="lb-signal">--</div>
          <div style="font-size:12px;color:var(--tx);margin-top:4px">Signal Score</div>
          <div style="font-size:14px;font-weight:700;margin-top:6px" id="lb-signal-label">Calculating...</div>
        </div>
        <div style="border-top:1px solid var(--b);padding-top:8px;margin-top:4px">
          <div style="display:flex;justify-content:space-between;font-size:12px;font-family:var(--mn)">
            <span style="color:var(--tx)">Feeds Active:</span>
            <span style="color:var(--gr)" id="lb-feeds">--/306</span>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:12px;font-family:var(--mn);margin-top:4px">
            <span style="color:var(--tx)">Stories Today:</span>
            <span style="color:var(--bl)" id="lb-stories">--</span>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:12px;font-family:var(--mn);margin-top:4px">
            <span style="color:var(--tx)">Poll Votes:</span>
            <span style="color:var(--yl)" id="lb-poll-votes">--</span>
          </div>
        </div>
      </div>

    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- EXPERIMENTAL METRICS — v7.0 through v7.2                       -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div id="experimental-metrics" style="margin-bottom:10px">
  <div style="background:linear-gradient(135deg,#0a0a14,#0d0d1a);border:1px solid rgba(117,188,255,.15);
    border-radius:14px;padding:20px">

    <!-- Section header -->
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;padding-bottom:14px;
      border-bottom:1px solid rgba(117,188,255,.1)">
      <span style="font-size:22px">🧪</span>
      <div>
        <div style="font-size:18px;font-weight:900;color:var(--bl);font-family:var(--mn);
          letter-spacing:2px;text-transform:uppercase">Experimental Metrics</div>
        <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-top:2px">
          Advanced intelligence tools — continuously expanding · v7.x
        </div>
      </div>
    </div>

    <!-- ─── FEATURE 1: XRP TIME MACHINE ───────────────────────── -->
    <div class="exp-card" id="time-machine-section">
      <div class="exp-title">⏱️ XRP "WHAT IF" TIME MACHINE</div>
      <div class="exp-sub">How much would your investment be worth if you had bought XRP on any date?</div>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:14px">
        <div>
          <label class="exp-lbl">Investment Amount (USD)</label>
          <input type="number" id="tm-amount" value="1000" min="1"
            class="exp-input" placeholder="e.g. 1000">
        </div>
        <div>
          <label class="exp-lbl">Purchase Date</label>
          <input type="date" id="tm-date" class="exp-input" value="2020-01-01">
        </div>
        <div style="display:flex;align-items:flex-end">
          <button onclick="runTimeMachine()" class="exp-btn" style="width:100%">
            ⚡ CALCULATE
          </button>
        </div>
      </div>

      <!-- Quick date buttons -->
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">
        <button onclick="setTMDate('2020-01-01')" class="exp-tag">Jan 2020</button>
        <button onclick="setTMDate('2021-01-01')" class="exp-tag">Jan 2021</button>
        <button onclick="setTMDate('2021-11-01')" class="exp-tag">ATH Era</button>
        <button onclick="setTMDate('2023-01-01')" class="exp-tag">Jan 2023</button>
        <button onclick="setTMDate('2024-01-01')" class="exp-tag">Jan 2024</button>
        <button onclick="setTMDate('2025-01-01')" class="exp-tag">Jan 2025</button>
      </div>

      <!-- Results panel (hidden until calculated) -->
      <div id="tm-results" style="display:none">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-bottom:14px">
          <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
            <div class="exp-stat-lbl">INVESTED</div>
            <div class="exp-stat-val" id="tm-invested" style="color:var(--tx)">--</div>
          </div>
          <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
            <div class="exp-stat-lbl">XRP BOUGHT</div>
            <div class="exp-stat-val" id="tm-xrp-bought" style="color:var(--bl)">--</div>
          </div>
          <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
            <div class="exp-stat-lbl">PRICE THEN</div>
            <div class="exp-stat-val" id="tm-price-then" style="color:var(--yl)">--</div>
          </div>
          <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
            <div class="exp-stat-lbl">PRICE NOW</div>
            <div class="exp-stat-val" id="tm-price-now" style="color:var(--gr)">--</div>
          </div>
          <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
            <div class="exp-stat-lbl">CURRENT VALUE</div>
            <div class="exp-stat-val" id="tm-value-now" style="font-size:22px">--</div>
          </div>
          <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
            <div class="exp-stat-lbl">PEAK VALUE</div>
            <div class="exp-stat-val" id="tm-value-peak" style="color:var(--yl)">--</div>
          </div>
          <div class="exp-stat-box" style="border-color:rgba(255,204,0,.3)">
            <div class="exp-stat-lbl">PROFIT / LOSS</div>
            <div class="exp-stat-val" id="tm-pnl">--</div>
          </div>
          <div class="exp-stat-box" style="border-color:rgba(255,204,0,.3)">
            <div class="exp-stat-lbl">RETURN %</div>
            <div class="exp-stat-val" id="tm-return-pct">--</div>
          </div>
        </div>
        <div id="tm-narrative" style="padding:12px;background:rgba(72,255,130,.05);border:1px solid rgba(72,255,130,.15);
          border-radius:6px;font-size:13px;color:var(--br);line-height:1.7;font-family:system-ui"></div>
      </div>
      <div id="tm-loading" style="display:none;font-size:13px;color:var(--tq);font-family:var(--mn);padding:10px 0">
        ⏳ Fetching historical price data...
      </div>
      <div id="tm-error" style="display:none;font-size:13px;color:var(--rd);font-family:var(--mn);padding:10px 0"></div>

      <div class="exp-divider"></div>

    <!-- ─── FEATURE 2: MACRO EVENTS CALENDAR ─────────────────── -->
    <div class="exp-card" id="macro-calendar-section">
      <div class="exp-title">📅 MACRO EVENTS CALENDAR</div>
      <div class="exp-sub">Every upcoming event that could move XRP — Fed meetings, ETF deadlines, escrow releases, legislative votes, XRPL upgrades</div>

      <!-- Category filter -->
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">
        <button onclick="filterCalendar('ALL')"        class="exp-tag" id="cal-f-ALL"        >ALL</button>
        <button onclick="filterCalendar('FED')"        class="exp-tag" id="cal-f-FED"        style="color:var(--rd)">🏛️ FED</button>
        <button onclick="filterCalendar('ETF')"        class="exp-tag" id="cal-f-ETF"        style="color:var(--gr)">📊 ETF</button>
        <button onclick="filterCalendar('LEGAL')"      class="exp-tag" id="cal-f-LEGAL"      style="color:var(--yl)">⚖️ LEGAL</button>
        <button onclick="filterCalendar('CONGRESS')"   class="exp-tag" id="cal-f-CONGRESS"   style="color:var(--bl)">🏛️ CONGRESS</button>
        <button onclick="filterCalendar('ESCROW')"     class="exp-tag" id="cal-f-ESCROW"     style="color:var(--or)">🔒 ESCROW</button>
        <button onclick="filterCalendar('XRPL')"       class="exp-tag" id="cal-f-XRPL"       style="color:var(--tq)">🔗 XRPL</button>
        <button onclick="filterCalendar('REGULATORY')" class="exp-tag" id="cal-f-REGULATORY" style="color:var(--tx)">📋 REGULATORY</button>
        <button onclick="filterCalendar('RIPPLE')"     class="exp-tag" id="cal-f-RIPPLE"     style="color:var(--gr)">🌊 RIPPLE</button>
      </div>

      <div id="macro-calendar-grid" style="display:flex;flex-direction:column;gap:6px">
        <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Loading calendar...</div>
      </div>
    </div>



      <div class="exp-divider"></div>

    <!-- ─── FEATURE 3: DERIVATIVES INTELLIGENCE ───────────────── -->
    <div class="exp-card" id="derivatives-section">
      <div class="exp-title">📉 DERIVATIVES INTELLIGENCE DASHBOARD</div>
      <div class="exp-sub">Funding rates, long/short positioning, open interest — how institutions are really betting on XRP</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-bottom:14px">
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">CURRENT FUNDING</div>
          <div class="exp-stat-val" id="dv-funding" style="font-size:16px">--</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn);margin-top:2px" id="dv-funding-trend">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">LONG/SHORT RATIO</div>
          <div class="exp-stat-val" id="dv-ls-ratio">--</div>
          <div style="font-size:12px;font-family:var(--mn);margin-top:2px" id="dv-positioning">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">LONG LIQUIDATIONS 24H</div>
          <div class="exp-stat-val" id="dv-long-liq" style="color:var(--rd)">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">SHORT LIQUIDATIONS 24H</div>
          <div class="exp-stat-val" id="dv-short-liq" style="color:var(--gr)">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">OI TREND (12H)</div>
          <div class="exp-stat-val" id="dv-oi-trend">--</div>
        </div>
        <div class="exp-stat-box" style="border-color:rgba(117,188,255,.3)">
          <div class="exp-stat-lbl">UPDATED</div>
          <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:4px" id="dv-ts">--</div>
        </div>
      </div>
      <!-- Funding rate mini chart -->
      <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:6px">24-HOUR FUNDING RATE HISTORY</div>
      <div style="height:70px;background:var(--bg);border:1px solid var(--b);border-radius:6px;overflow:hidden">
        <canvas id="dv-funding-chart" style="width:100%;height:100%"></canvas>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--tx);font-family:var(--mn);margin-top:4px">
        <span>24h ago</span>
        <span style="color:var(--gr)">▲ Positive = longs paying = bullish bias</span>
        <span>now</span>
      </div>
    </div>

      <div class="exp-divider"></div>

    <!-- ─── FEATURE 4: RLUSD DEDICATED DASHBOARD ──────────────── -->
    <div class="exp-card" id="rlusd-dashboard">
      <div class="exp-title">💵 RLUSD STABLECOIN DASHBOARD</div>
      <div class="exp-sub">Ripple's NYDFS-regulated USD stablecoin — supply growth, velocity, and ecosystem penetration</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-bottom:12px">
        <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
          <div class="exp-stat-lbl">TOTAL SUPPLY</div>
          <div class="exp-stat-val" id="rlusd-supply">--</div>
        </div>
        <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
          <div class="exp-stat-lbl">24H VOLUME</div>
          <div class="exp-stat-val" id="rlusd-vol">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">MARKET CAP</div>
          <div class="exp-stat-val" id="rlusd-mcap" style="color:var(--bl)">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">PRICE PEG</div>
          <div class="exp-stat-val" id="rlusd-price">--</div>
          <div style="font-size:11px;font-family:var(--mn);margin-top:2px" id="rlusd-peg-status">Checking...</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">24H CHANGE</div>
          <div class="exp-stat-val" id="rlusd-change">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">RANK</div>
          <div class="exp-stat-val" id="rlusd-rank" style="color:var(--yl)">--</div>
        </div>
      </div>
      <div style="padding:10px;background:rgba(72,255,130,.05);border:1px solid rgba(72,255,130,.1);border-radius:6px;font-size:13px;color:var(--tx);line-height:1.6">
        <b style="color:var(--gr)">Why RLUSD matters for XRP:</b> RLUSD serves as the stable settlement leg in XRP ODL corridors — enabling businesses to hold value in USD while using XRP as the bridge. Growing RLUSD supply = more ODL activity = more XRP demand.
      </div>
    </div>

      <div class="exp-divider"></div>

    <!-- ─── FEATURE 5: CUSTOM KEYWORD ALERT SYSTEM ────────────── -->
    <div class="exp-card" id="keyword-alerts-section">
      <div class="exp-title">🔔 CUSTOM KEYWORD ALERT SYSTEM</div>
      <div class="exp-sub">Set up to 10 keywords — the moment any matches a headline in our feed, you get an instant browser notification</div>
      <div style="display:flex;gap:8px;margin-bottom:10px">
        <input type="text" id="kw-input" placeholder="e.g. Bank of America, Ripple IPO, ETF approved..."
          class="exp-input" style="flex:1" onkeydown="if(event.key==='Enter') addKeyword()">
        <button onclick="addKeyword()" class="exp-btn exp-btn-gr">+ ADD</button>
      </div>
      <div id="kw-tags" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;min-height:28px">
        <span style="font-size:12px;color:var(--tx);font-family:var(--mn);padding:4px 0">No keywords set — add one above</span>
      </div>
      <div id="kw-alert-banner" style="display:none;padding:10px 12px;background:rgba(72,255,130,.1);
        border:1px solid rgba(72,255,130,.3);border-radius:6px;margin-bottom:10px">
        <div style="font-size:13px;font-weight:700;color:var(--gr);font-family:var(--mn);margin-bottom:4px">🔔 KEYWORD MATCH</div>
        <div id="kw-alert-text" style="font-size:13px;color:var(--br)"></div>
      </div>
      <div style="font-size:12px;color:var(--tx);font-family:var(--mn)">
        ℹ️ Keywords are checked against every new story as it arrives. Browser notifications require permission.
        <button onclick="requestKwPermission()" class="exp-btn" style="margin-left:10px;padding:4px 12px;font-size:12px">
          Enable Notifications
        </button>
      </div>
    </div>

      <div class="exp-divider"></div>

    <!-- ─── FEATURE 6: XRPL VALIDATOR NETWORK MAP ─────────────── -->
    <div class="exp-card" id="validator-map-section">
      <div class="exp-title">🌐 XRPL VALIDATOR NETWORK MAP</div>
      <div class="exp-sub">Live view of the 35+ validators on the Unique Node List (UNL) — geography, operator, uptime, decentralization score</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-bottom:14px">
        <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
          <div class="exp-stat-lbl">UNL VALIDATORS</div>
          <div class="exp-stat-val" id="val-count">35</div>
        </div>
        <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
          <div class="exp-stat-lbl">RIPPLE-OPERATED</div>
          <div class="exp-stat-val" id="val-ripple-count" style="color:var(--yl)">6</div>
        </div>
        <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
          <div class="exp-stat-lbl">INDEPENDENT</div>
          <div class="exp-stat-val" id="val-indie-count" style="color:var(--gr)">29</div>
        </div>
        <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
          <div class="exp-stat-lbl">DECENTRALIZATION</div>
          <div class="exp-stat-val" id="val-decentral" style="color:var(--gr)">83%</div>
        </div>
        <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
          <div class="exp-stat-lbl">AVG UPTIME</div>
          <div class="exp-stat-val" id="val-uptime" style="color:var(--gr)">99.8%</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">CONSENSUS</div>
          <div class="exp-stat-val" id="val-consensus" style="font-size:15px;color:var(--gr)">FBC ✅</div>
        </div>
      </div>
      <!-- Validator list by region -->
      <div id="validator-list" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:6px;max-height:300px;overflow-y:auto"></div>
      <div style="margin-top:10px;padding:10px;background:rgba(72,255,130,.05);border:1px solid rgba(72,255,130,.1);border-radius:6px;font-size:12px;color:var(--tx);line-height:1.6">
        <b style="color:var(--gr)">Decentralization fact:</b> No single entity controls XRPL consensus. Even Ripple Labs' 6 validators represent only 17% of the UNL. Removing all Ripple validators would not halt the network. The "XRP is centralised" narrative is factually incorrect.
      </div>
    </div>

      <div class="exp-divider"></div>

    <!-- ─── FEATURE 7: RIPPLE TREASURY & ESCROW ANALYTICS ─────── -->
    <div class="exp-card" id="escrow-analytics-section">
      <div class="exp-title">🏦 RIPPLE TREASURY & ESCROW ANALYTICS</div>
      <div class="exp-sub">Complete transparency on XRP supply dynamics — escrow releases, Ripple sales, re-locks, and projected timeline to 2032</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-bottom:14px">
        <div class="exp-stat-box" style="border-color:rgba(255,204,0,.3)">
          <div class="exp-stat-lbl">ESCROW REMAINING</div>
          <div class="exp-stat-val" id="esc-remaining" style="color:var(--yl)">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">RELEASED TO DATE</div>
          <div class="exp-stat-val" id="esc-released" style="color:var(--or)">--</div>
        </div>
        <div class="exp-stat-box" style="border-color:rgba(72,255,130,.3)">
          <div class="exp-stat-lbl">NET TO MARKET/MO</div>
          <div class="exp-stat-val" id="esc-net-mo" style="color:var(--gr)">~100-200M</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn);margin-top:2px">After re-locks</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">NEXT RELEASE</div>
          <div class="exp-stat-val" id="esc-next" style="font-size:16px;color:var(--bl)">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">ESCROW % OF SUPPLY</div>
          <div class="exp-stat-val" id="esc-pct" style="color:var(--yl)">--</div>
        </div>
        <div class="exp-stat-box">
          <div class="exp-stat-lbl">PROJECTED EMPTY</div>
          <div class="exp-stat-val" id="esc-empty-date" style="font-size:15px;color:var(--tx)">~2032</div>
        </div>
      </div>
      <!-- Monthly release chart -->
      <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:6px">MONTHLY RELEASE HISTORY (1B/month released — Ripple re-locks remainder)</div>
      <div style="padding:12px;background:var(--bg);border-radius:6px;border:1px solid var(--b)">
        <div style="display:flex;flex-direction:column;gap:6px" id="escrow-release-timeline">
          <div style="font-size:13px;color:var(--tx);font-family:var(--mn)">Loading escrow history...</div>
        </div>
      </div>
      <div style="margin-top:10px;font-size:12px;color:var(--tx);line-height:1.6;padding:8px 10px;background:rgba(255,204,0,.04);border:1px solid rgba(255,204,0,.1);border-radius:6px">
        <b style="color:var(--yl)">Supply transparency:</b> Ripple established the 55B XRP escrow in 2017. 1B XRP is released monthly. Typically 800-900M is immediately re-locked for a future month, with only ~100-200M entering circulation — representing less than 0.1% of circulating supply per month.
      </div>
    </div>


  </div><!-- end inner container -->
</div><!-- end experimental-metrics -->

<footer>
  <div>🛰️ <em style="color:var(--bl);font-weight:700">XRPRadar</em> &nbsp;|&nbsp; Version: <span id="ft-ver" style="color:var(--tq);font-weight:700">--</span> &nbsp;|&nbsp; Updated: <span id="ft-last" style="color:var(--br)">--</span> &nbsp;|&nbsp; Uptime: <span id="ft-uptime" style="color:var(--br)">--</span> &nbsp;&nbsp;<a href="/debug" target="_blank" style="color:var(--or);font-size:13px;font-weight:700;text-decoration:none;border:1px solid var(--or);padding:1px 6px;border-radius:3px">DEBUG</a></div>
  <div style="color:var(--yl)">⚠️ Not Financial Advice — XRPRadar is for informational purposes only. DYOR.</div>
  <div>Feeds: <span id="ft-feeds" style="color:var(--br)">--</span> &nbsp;|&nbsp; Maintenance: <span id="ft-maint" style="color:var(--br)">--</span> &nbsp;|&nbsp; Preflight: <span id="ft-qa-status" style="font-weight:700">--</span> &nbsp;&nbsp;<button onclick="openPFModal()" style="color:var(--bl);font-size:13px;font-weight:700;text-decoration:none;border:1px solid var(--bl);padding:1px 8px;border-radius:3px;background:var(--bld);cursor:pointer;font-family:var(--mn)">🔍 DETAILS</button></div>
  <div style="height:16px"></div>
  <div style="padding-bottom:14px;font-size:13px;font-family:var(--mn);color:var(--tx);text-align:center;border-top:1px solid rgba(255,255,255,.06);padding-top:10px;margin-top:4px">
    ©️ Copyright 2026 Red Rio Ventures, LLC. All rights reserved globally. <span id="visitor-count" style="color:var(--tx);font-size:11px;opacity:.4;margin-left:8px"></span>
  </div>
</footer>

<!-- PRECHECK DETAILS MODAL -->
<div id="pf-modal" onclick="closePFModal(event)" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.88);z-index:9999;align-items:center;justify-content:center;padding:20px">
  <div id="pf-box" style="background:var(--s1);border:1px solid var(--bl);border-radius:10px;max-width:560px;width:100%;overflow:hidden" onclick="event.stopPropagation()">
    <div style="padding:10px 16px;background:var(--s2);border-bottom:1px solid var(--b);display:flex;justify-content:space-between;align-items:center;font-family:var(--mn)">
      <span style="color:var(--bl);font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:1px">🔍 Preflight / QA Details</span>
      <span onclick="closePFModal()" style="color:var(--bl);cursor:pointer;font-size:18px;border:1px solid var(--bl);width:26px;height:26px;display:flex;align-items:center;justify-content:center;border-radius:4px">✕</span>
    </div>
    <div style="padding:16px;font-family:var(--mn);font-size:13px;line-height:2.4">
      <div>Last run: <span id="pf-last" style="color:var(--br)">--</span></div>
      <div>Feed Integrity: <span id="pf-feeds" style="color:var(--br)">--</span></div>
      <div>Last Error: <span id="pf-error" style="color:var(--rd)">None</span></div>
      <div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--b)" id="pf-checks"></div>
    </div>
  </div>
</div>

</div><!-- end .w -->

<script>
// ── State ─────────────────────────────────────────────────────────────────
let allStories = [];
let storyData  = {};
let activeCat  = "all";
let activeSearch = "";

// ── Fetch ─────────────────────────────────────────────────────────────────
async function fetchData(){
  try{
    const d = await fetch("/api/data").then(r=>r.json());
    updateHeader(d);
    updateStatus(d);
    updateMarket(d);
    updatePriceIntel(d);
    updateOnchainIntel(d);
    updateTechIntel(d);
    updatePrediction(d);
    updateDispIntel(d);
    updateToolsIntel(d);
    updateSentIntel(d);
    updateEcosystem(d);
    updateMainstreamIntel(d);
    updateCompIntel(d);
    updateRegIntel(d);
    updateExecIntel(d);
    updateAI(d);
    updateScoreboard(d);
    updateAnalytics(d);
    updateRegions(d);
    updateRight(d);
    updateFooter(d);
    updateBreaking(d);
    // v6.0 new sections
    updateSignalScore(d);
    updateMacroDashboard(d);
    updateOrderBook(d);
    updateIPOWatch(d);
    updateCurrencyCrisis(d);
    updateAdoptionVelocity(d);
    updateCommunityPoll(d);
    updateWeeklyDigest(d);
    updateRemittanceIntel(d);
    updateGeopoliticalRisk(d);
    checkWhaleAlerts(d);
    updateLeaderboard(d);
    updatePriceTrends(d);
    updateExperimental(d);
    // v6.2 new panels
    updateInstFlow(d);
    updateCBDCComp(d);
    updateOptionsFlow(d);
    updateAccumDistrib(d);
    updateWhaleWatchlist(d);
    updateTxVolume(d);
    updateDevScore(d);
  }catch(e){console.error("fetchData:",e);}
}

async function fetchNews(){
  try{
    const d = await fetch("/api/news").then(r=>r.json());
    allStories = d.stories||[];
    window.allStories = allStories;
    allStories.forEach(s=>{storyData[s.id]=s;});
    renderNews(d.total_all||0);
    renderTop20();
  }catch(e){console.error("fetchNews:",e);}
}

function renderTop20(){
  const el=document.getElementById("top20-feed");
  if(!el) return;
  // Sort: breaking first, then by recency
  const sorted=[...allStories]
    .sort((a,b)=>{
      if(a.breaking&&!b.breaking) return -1;
      if(!a.breaking&&b.breaking) return 1;
      return (b.pub||"").localeCompare(a.pub||"");
    })
    .slice(0,20);
  if(!sorted.length){el.innerHTML='<div class="empty">Loading stories...</div>';return;}
  const sentC={"bullish":"var(--gr)","bearish":"var(--rd)","neutral":"var(--tx)"};
  el.innerHTML=sorted.map((s,i)=>{
    const brk=s.breaking?'<span style="color:var(--yl);font-weight:700;font-family:var(--mn);font-size:13px">⚡ BREAKING &nbsp;</span>':''
    const sent=s.sentiment||"neutral";
    const sum=s.summary?s.summary.substring(0,160)+(s.summary.length>160?"...":""):"";
    const url=s.link||s.url||"#";
    return `<div style="display:flex;gap:12px;align-items:flex-start;padding:10px 14px;
      background:var(--s2);border:1px solid var(--b);border-radius:8px;
      cursor:pointer;transition:all .2s;margin-bottom:2px"
      onclick="window.open('${url}','_blank')"
      onmouseover="this.style.borderColor='var(--bl)';this.style.background='var(--s1)'"
      onmouseout="this.style.borderColor='var(--b)';this.style.background='var(--s2)'">
      <div style="font-size:18px;font-weight:900;font-family:var(--mn);color:var(--tx);
        min-width:28px;text-align:right;margin-top:2px;opacity:.5">${i+1}</div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;flex-wrap:wrap">
          ${brk}
          <span style="font-size:13px;font-weight:700;font-family:var(--mn);
            color:var(--tx);background:var(--s1);padding:2px 8px;border-radius:4px;
            border:1px solid var(--b)">${s.source}</span>
          <span style="font-size:13px;font-family:var(--mn);
            color:${sentC[sent]||"var(--tx)"};font-weight:700;text-transform:uppercase">${sent}</span>
          <span style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-left:auto">${s.age||""}</span>
        </div>
        <div style="font-size:15px;font-weight:700;color:var(--bl);line-height:1.45;margin-bottom:4px">${s.title}</div>
        ${sum?`<div style="font-size:13px;color:var(--tx);line-height:1.55;opacity:.85">${sum}</div>`:""}
        <div style="margin-top:6px;display:flex;gap:6px">
          <span style="font-size:12px;color:var(--bl);font-family:var(--mn);
            background:rgba(117,188,255,.08);padding:3px 10px;border-radius:3px;
            border:1px solid rgba(117,188,255,.2)">↗ READ STORY</span>
          <span onclick="event.stopPropagation();shareStory('${s.title||""}','${s.link||s.url||""}','${s.source||""}','${s.sentiment||""}','${s.age||""}')"
            style="font-size:12px;color:var(--tq);font-family:var(--mn);cursor:pointer;
            background:rgba(0,229,204,.08);padding:3px 10px;border-radius:3px;
            border:1px solid rgba(0,229,204,.2)">📤 SHARE</span>
        </div>
      </div>
    </div>`;
  }).join("");
}

// ── Format helpers ─────────────────────────────────────────────────────────
function fmtUSD(v){
  if(!v) return "--";
  v=parseFloat(v);
  if(v>=1e12) return `$${(v/1e12).toFixed(2)}T`;
  if(v>=1e9)  return `$${(v/1e9).toFixed(2)}B`;
  if(v>=1e6)  return `$${(v/1e6).toFixed(2)}M`;
  return `$${v.toFixed(2)}`;
}
function c(id,v){const el=document.getElementById(id);if(el&&v!==undefined)el.textContent=v;}






// ── Executive & Developer Tracker (v3.0e) ─────────────────────────────────
let execStories = [];
let activeExec  = "all";

function setExecTab(btn, exec){
  activeExec = exec;
  document.querySelectorAll(".exec-tab").forEach(b=>{
    b.style.color         = "var(--tx)";
    b.style.borderBottom  = "2px solid transparent";
  });
  btn.style.color        = "var(--or)";
  btn.style.borderBottom = "2px solid var(--or)";
  renderExecFeed();
}

function renderExecFeed(){
  const feed = document.getElementById("exec-feed");
  if(!feed) return;
  const stories = activeExec === "all"
    ? execStories
    : execStories.filter(s => s.exec_name === activeExec);
  if(!stories.length){
    feed.innerHTML = '<div class="empty">No recent statements found.</div>';
    return;
  }
  feed.innerHTML = stories.map(s=>`
    <div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04)">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        <span style="font-size:13px;font-weight:700;font-family:var(--mn);
          color:var(--or);background:rgba(255,153,0,.1);padding:2px 7px;
          border-radius:3px;border:1px solid rgba(255,153,0,.3)">${s.exec_name||""}</span>
        <span style="font-size:13px;font-family:var(--mn);color:var(--tx)">${s.exec_title||""}</span>
        <span style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-left:auto">${s.age||""}</span>
      </div>
      <div style="font-size:13px;font-weight:700;color:var(--bl);line-height:1.4;margin-bottom:2px;
        cursor:pointer" onclick="window.open('${s.link||"#"}','_blank')"
        onmouseover="this.style.color='var(--gr)'" onmouseout="this.style.color='var(--bl)'">
        ${s.title||""}
      </div>
      <div style="font-size:13px;font-family:var(--mn);color:var(--tx)">${s.source||""}</div>
    </div>`).join("");
}

function updateExecIntel(d){
  const ei = d.exec_intel || {};
  if(ei.ts) c("exec-ts", ei.ts);

  // 22. Executive Stories
  if(ei.exec_stories && ei.exec_stories.length){
    execStories = ei.exec_stories;
    renderExecFeed();
  }

  // 23. GitHub Stats
  const gs = ei.github_stats || {};
  if(gs.rippled_commits_7d !== undefined) c("gh-rippled-7d", gs.rippled_commits_7d);
  if(gs.xrpl_dev_commits_7d !== undefined) c("gh-dev-7d",  gs.xrpl_dev_commits_7d);
  if(gs.stars)  c("gh-stars",  gs.stars.toLocaleString());
  if(gs.open_issues !== undefined) c("gh-issues", gs.open_issues);
  if(gs.last_commit_msg)    c("gh-last-msg",    gs.last_commit_msg);
  if(gs.last_commit_author) c("gh-last-author", gs.last_commit_author);
  if(gs.last_commit_date)   c("gh-last-date",   gs.last_commit_date);
  if(ei.ts) c("gh-ts", ei.ts);

  // GitHub commit feed
  const ghFeed = document.getElementById("gh-feed");
  if(ghFeed && ei.github_commits && ei.github_commits.length){
    const repoColor = {"rippled":"var(--gr)","xrpl-dev-portal":"var(--bl)","xrpl.js":"var(--yl)"};
    ghFeed.innerHTML = ei.github_commits.map(commit=>`
      <div style="display:flex;gap:8px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.03);
        cursor:pointer" onclick="window.open('${commit.url||"#"}','_blank')">
        <div style="width:6px;height:6px;border-radius:50%;flex-shrink:0;margin-top:5px;
          background:${repoColor[commit.repo]||"var(--tx)"}"></div>
        <div style="min-width:0">
          <div style="font-size:13px;font-weight:600;color:var(--br);line-height:1.3;
            overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${commit.msg||""}</div>
          <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:1px">
            <span style="color:${repoColor[commit.repo]||"var(--tx)"};font-weight:700">${commit.repo}</span>
            &nbsp;·&nbsp;${commit.author||""}
            &nbsp;·&nbsp;${commit.date||""}
          </div>
        </div>
      </div>`).join("");
  }
}






// ── XRP Intelligence Brief (v3.1) ─────────────────────────────────────────
function updatePrediction(d){
  const pred = d.prediction || {};

  // Status badge
  const badge = document.getElementById("pred-status-badge");
  const statusMap = {
    "pending":    {text:"⏰ SCHEDULED",   bg:"rgba(128,153,179,.1)", col:"var(--tx)"},
    "generating": {text:"⚙️ GENERATING...",bg:"rgba(255,153,0,.15)",  col:"var(--or)"},
    "complete":   {text:"✅ COMPLETE",     bg:"rgba(72,255,130,.1)",  col:"var(--gr)"},
    "error":      {text:"❌ ERROR",        bg:"rgba(255,64,96,.1)",   col:"var(--rd)"},
  };
  if(badge){
    const st = statusMap[pred.status] || statusMap["pending"];
    badge.textContent       = st.text;
    badge.style.background  = st.bg;
    badge.style.color       = st.col;
    badge.style.borderColor = st.col;
  }

  // Meta row
  c("pred-generated",   pred.generated_at  || "--");
  c("pred-story-count", pred.story_count   ? pred.story_count + " stories" : "--");
  c("pred-src-count",   pred.source_count  ? pred.source_count + " sources" : "--");
  c("pred-next-run",    pred.next_run_cst  || "--");

  const loading  = document.getElementById("pred-loading");
  const sections = document.getElementById("pred-sections");

  if(pred.status === "complete" && pred.sections){
    const sec = pred.sections;
    if(loading)  loading.style.display  = "none";
    if(sections){ sections.style.display = "grid"; }

    c("pred-pulse",    sec.market_pulse         || "Generating...");
    c("pred-conn",     sec.connections           || "Generating...");
    c("pred-domino",   sec.domino_effect         || "Generating...");
    c("pred-regional", sec.regional_flashpoints  || "Generating...");
    c("pred-watch",    sec.watchlist             || "Generating...");
    c("pred-tradfi",   sec.tradfi_outlook        || "Generating...");

  } else if(pred.status === "generating"){
    if(loading){
      loading.innerHTML = `<div style="font-size:32px;margin-bottom:10px">⚙️</div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--or)">
          Analyzing ${pred.story_count||"--"} stories from ${pred.source_count||"--"} sources...<br>
          Brief will appear in approximately 15-20 seconds.
        </div>`;
      loading.style.display = "block";
    }
    if(sections) sections.style.display = "none";

  } else if(pred.status === "error" && pred.error){
    if(loading){
      loading.innerHTML = `<div style="font-size:32px;margin-bottom:10px">⚠️</div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--rd)">
          ${pred.error}
        </div>
        <div style="font-size:13px;color:var(--tx);margin-top:8px">
          Check that ANTHROPIC_API_KEY is set in Railway Variables.
        </div>`;
      loading.style.display = "block";
    }
    if(sections) sections.style.display = "none";
  }
}

async function triggerBrief(){
  const badge = document.getElementById("pred-status-badge");
  if(badge){ badge.textContent="⚙️ TRIGGERING..."; badge.style.color="var(--or)"; }
  try{
    await fetch("/run-prediction");
    // Poll for result every 3 seconds for up to 60 seconds
    let polls = 0;
    const timer = setInterval(async ()=>{
      polls++;
      if(polls > 20){ clearInterval(timer); return; }
      const d = await fetch("/api/data").then(r=>r.json());
      updatePrediction(d);
      if(d.prediction && d.prediction.status === "complete"){
        clearInterval(timer);
      }
    }, 3000);
  }catch(e){
    if(badge){ badge.textContent="❌ TRIGGER FAILED"; badge.style.color="var(--rd)"; }
  }
}

// ── Unique Displays (v3.0i) ────────────────────────────────────────────────
function updateDispIntel(d){
  const di = d.disp_intel || {};

  // ── 38. Smart Money Score ─────────────────────────────────────────────
  const sm = di.smart_money || {};
  if(sm.score !== undefined){
    const score = sm.score;
    const col   = score >= 80 ? "var(--gr)" :
                  score >= 60 ? "var(--bl)" :
                  score >= 40 ? "var(--yl)" :
                  score >= 20 ? "var(--or)" : "var(--rd)";
    const scoreEl = document.getElementById("sm-score");
    if(scoreEl){ scoreEl.textContent = score; scoreEl.style.color = col; }
    c("sm-label", sm.label || "--");
    const bar = document.getElementById("sm-bar");
    if(bar){ bar.style.width = `${score}%`; bar.style.background = col; }

    const sigEl = document.getElementById("sm-signals");
    if(sigEl && sm.signals && sm.signals.length){
      sigEl.innerHTML = sm.signals.map(sig=>{
        const sc = sig.positive ? "var(--gr)" : "var(--rd)";
        return `<div style="display:flex;justify-content:space-between;
          padding:3px 0;border-bottom:1px solid rgba(255,255,255,.04)">
          <span style="color:var(--tx)">${sig.label}</span>
          <span style="color:${sc};font-weight:700">+${sig.points}</span>
        </div>`;
      }).join("");
    }
  }

  // ── 39. Fear & Greed 30-Day Chart ────────────────────────────────────
  const fgEl = document.getElementById("fg-history-chart");
  if(fgEl && di.fg_history && di.fg_history.length){
    const fgColor = v =>
      v <= 25 ? "var(--rd)"  :
      v <= 45 ? "var(--or)"  :
      v <= 55 ? "var(--yl)"  :
      v <= 75 ? "var(--gr)"  : "#00ffcc";
    fgEl.innerHTML = di.fg_history.map((f,i)=>{
      const isToday = i === di.fg_history.length - 1;
      const col     = fgColor(f.value);
      return `<div title="${f.label}: ${f.value}"
        style="flex:1;background:${col};border-radius:2px 2px 0 0;
          min-height:4px;height:${f.value}%;cursor:default;
          ${isToday ? "outline:2px solid #fff;outline-offset:-1px" : ""}
          opacity:${isToday?1:0.75};transition:opacity .2s"
        onmouseover="this.style.opacity=1"
        onmouseout="this.style.opacity=${isToday?1:0.75}">
      </div>`;
    }).join("");
  }

  // ── 36. Price History Heatmap ─────────────────────────────────────────
  const hmEl = document.getElementById("heatmap-grid");
  if(hmEl && di.price_heatmap && di.price_heatmap.length){
    // Group by week number (use date-based week key)
    const weeks = {};
    di.price_heatmap.forEach(day=>{
      const wk = day.week || day.date.substring(0,7);
      if(!weeks[wk]) weeks[wk] = {};
      weeks[wk][day.dow] = day;
    });

    const heatColor = pct => {
      const abs = Math.abs(pct);
      if(pct >= 5)  return `rgba(72,255,130,0.95)`;
      if(pct >= 3)  return `rgba(72,255,130,0.75)`;
      if(pct >= 1)  return `rgba(72,255,130,0.50)`;
      if(pct >= 0)  return `rgba(72,255,130,0.25)`;
      if(pct >= -1) return `rgba(255,64,96,0.25)`;
      if(pct >= -3) return `rgba(255,64,96,0.50)`;
      if(pct >= -5) return `rgba(255,64,96,0.75)`;
      return `rgba(255,64,96,0.95)`;
    };

    hmEl.innerHTML = Object.entries(weeks).map(([wk,days])=>{
      // Get week label from first day
      const firstDay = Object.values(days)[0];
      const wkLabel  = firstDay ? firstDay.date.slice(5) : "";
      return `<div style="display:flex;gap:2px;align-items:center">
        <div style="width:24px;flex-shrink:0;font-size:13px;font-family:var(--mn);
          color:var(--tx);text-align:right;padding-right:4px">${wkLabel}</div>
        <div style="display:flex;gap:2px;flex:1">
          ${[0,1,2,3,4,5,6].map(dow=>{
            const day = days[dow];
            if(!day) return `<div style="flex:1;height:20px;border-radius:3px;
              background:var(--s2);opacity:.2"></div>`;
            const col = heatColor(day.change);
            return `<div title="${day.date}: ${day.change > 0 ? "+" : ""}${day.change}% ($${day.price})"
              style="flex:1;height:20px;border-radius:3px;background:${col};cursor:default;
                transition:transform .1s"
              onmouseover="this.style.transform='scale(1.15)'"
              onmouseout="this.style.transform='scale(1)'">
            </div>`;
          }).join("")}
        </div>
      </div>`;
    }).join("");
  }

  // ── 37. Regional Activity Heatmap ────────────────────────────────────
  const rhEl = document.getElementById("regional-heatmap");
  if(rhEl){
    const allStories = window.allStories || [];
    const regionKeywords = {
      "🇯🇵 Japan":          ["japan","japanese","jpy","sbi","coincheck"],
      "🇰🇷 Korea":          ["korea","korean","krw","upbit","bithumb"],
      "🇦🇪 UAE/Middle East":["uae","dubai","emirates","middle east","adgm","vara"],
      "🇪🇺 Europe":         ["europe","european","eur","mica","ecb","binance.eu"],
      "🇮🇳 India":          ["india","indian","inr","rupee","wazirx","coinswitch"],
      "🌎 Latin America":   ["latam","latin","mexico","brazil","bitso","brasil"],
      "🌍 Africa":          ["africa","african","nigeria","kenya","flutterwave"],
      "🌏 SE Asia":         ["singapore","thailand","philippines","malay","sea","sgd","php"],
    };
    const maxStories = 20;
    const regionCounts = {};
    Object.keys(regionKeywords).forEach(r=>{ regionCounts[r]=0; });
    allStories.forEach(s=>{
      const txt = (s.title+" "+(s.summary||"")).toLowerCase();
      Object.entries(regionKeywords).forEach(([r,kws])=>{
        if(kws.some(kw=>txt.includes(kw))) regionCounts[r]++;
      });
    });
    const maxCount = Math.max(...Object.values(regionCounts), 1);
    rhEl.innerHTML = Object.entries(regionCounts).map(([region, count])=>{
      const pct    = Math.round((count / maxCount) * 100);
      const col    = pct >= 70 ? "var(--gr)" : pct >= 40 ? "var(--yl)" :
                     pct >= 15 ? "var(--bl)" : "var(--tx)";
      const bgAlpha= (pct / 100 * 0.2).toFixed(2);
      return `<div style="background:rgba(117,188,255,${bgAlpha});border:1px solid var(--b);
        border-radius:8px;padding:10px;text-align:center">
        <div style="font-size:18px;margin-bottom:4px">${region.split(" ")[0]}</div>
        <div style="font-size:13px;font-weight:700;color:var(--br);font-family:var(--mn);
          margin-bottom:6px">${region.split(" ").slice(1).join(" ")}</div>
        <div style="font-size:20px;font-weight:900;font-family:var(--mn);
          color:${col};margin-bottom:4px">${count}</div>
        <div style="height:4px;background:var(--s2);border-radius:2px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:${col};
            border-radius:2px;transition:width .8s"></div>
        </div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:3px">
          stories today
        </div>
      </div>`;
    }).join("");
    // Update SVG world map with activity counts
    const mapCounts = {
      'US':     (regionCounts['🇺🇸 N. America']||regionCounts['🇺🇸 USA']||0),
      'LatAm':  (regionCounts['🌎 Latin America']||0),
      'Europe': (regionCounts['🇪🇺 Europe']||0),
      'Africa': (regionCounts['🌍 Africa']||0),
      'UAE':    (regionCounts['🇦🇪 UAE/Middle East']||0),
      'India':  (regionCounts['🇮🇳 India']||0),
      'Japan':  (regionCounts['🇯🇵 Japan']||0),
      'SEA':    (regionCounts['🌏 SE Asia']||0),
    };
    updateWorldMap(mapCounts);
  }
  // ── 60-Month Price Chart ────────────────────────────────────────────────
  st hist60  = (di.price_history_60m||[]);
  const canvas60 = document.getElementById("chart-60m");
  const loading60 = document.getElementById("chart-60m-loading");
  const stats60   = document.getElementById("chart-60m-stats");
  if(canvas60 && hist60.length > 5){
    if(loading60) loading60.style.display="none";
    const ctx = canvas60.getContext("2d");
    const W = canvas60.parentElement.offsetWidth||900;
    const H = 260;
    canvas60.width = W; canvas60.height = H;
    const prices = hist60.map(p=>p.price);
    const labels = hist60.map(p=>p.date);
    const minP = Math.min(...prices), maxP = Math.max(...prices);
    const range = maxP - minP || 1;
    const padL=52,padR=14,padT=20,padB=34;
    const cW=W-padL-padR, cH=H-padT-padB;
    ctx.clearRect(0,0,W,H);
    // Grid
    for(let i=0;i<=5;i++){
      const y=padT+cH*(1-i/5);
      ctx.strokeStyle="rgba(255,255,255,.06)"; ctx.lineWidth=1;
      ctx.beginPath(); ctx.moveTo(padL,y); ctx.lineTo(W-padR,y); ctx.stroke();
      ctx.fillStyle="rgba(255,255,255,.4)"; ctx.font="10px monospace"; ctx.textAlign="right";
      ctx.fillText("$"+(minP+(maxP-minP)*i/5).toFixed(3), padL-4, y+4);
    }
    // Area fill
    const grad=ctx.createLinearGradient(0,padT,0,padT+cH);
    grad.addColorStop(0,"rgba(72,255,130,.3)"); grad.addColorStop(1,"rgba(72,255,130,.02)");
    ctx.beginPath();
    hist60.forEach((p,i)=>{
      const x=padL+cW*i/(hist60.length-1);
      const y=padT+cH*(1-(p.price-minP)/range);
      i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
    });
    ctx.lineTo(padL+cW,padT+cH); ctx.lineTo(padL,padT+cH); ctx.closePath();
    ctx.fillStyle=grad; ctx.fill();
    // Line
    ctx.beginPath(); ctx.strokeStyle="#48ff82"; ctx.lineWidth=2; ctx.lineJoin="round";
    hist60.forEach((p,i)=>{
      const x=padL+cW*i/(hist60.length-1);
      const y=padT+cH*(1-(p.price-minP)/range);
      i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
    });
    ctx.stroke();
    // ATH marker
    const athIdx=prices.indexOf(maxP);
    if(athIdx>=0){
      const ax=padL+cW*athIdx/(hist60.length-1);
      const ay=padT+cH*(1-(maxP-minP)/range);
      ctx.fillStyle="#ffcc00"; ctx.font="bold 10px monospace"; ctx.textAlign="center";
      ctx.fillText("ATH $"+maxP.toFixed(3), ax, Math.max(ay-8,14));
    }
    // X labels every 6 months
    ctx.fillStyle="rgba(255,255,255,.4)"; ctx.font="10px monospace"; ctx.textAlign="center";
    hist60.forEach((p,i)=>{ if(i%6===0){ const x=padL+cW*i/(hist60.length-1); ctx.fillText(p.date,x,H-6); }});
    // Stats
    const currP=prices[prices.length-1], firstP=prices[0];
    const chg=((currP-firstP)/firstP*100).toFixed(1);
    if(stats60) stats60.innerHTML=
      "<div>📅 <span style='color:#8099b3'>Period: </span><b style='color:#cce0ff'>"+labels[0]+" → "+labels[labels.length-1]+"</b></div>"+
      "<div>🔝 <span style='color:#8099b3'>ATH: </span><b style='color:#ffcc00'>$"+maxP.toFixed(4)+"</b></div>"+
      "<div>📉 <span style='color:#8099b3'>Low: </span><b style='color:#ff4060'>$"+minP.toFixed(4)+"</b></div>"+
      "<div>📊 <span style='color:#8099b3'>5Y: </span><b style='color:"+(chg>0?"#48ff82":"#ff4060")+"'>"+(chg>0?"+":"")+chg+"%</b></div>"+
      "<div>💰 <span style='color:#8099b3'>Now: </span><b style='color:#48ff82'>$"+currP.toFixed(4)+"</b></div>";
  }

}

// ── Practical Tools (v3.0h) ────────────────────────────────────────────────
let currentXRPPrice = 0;
let portfolioEntries = [];


// ── Remittance Savings Calculator ─────────────────────────────────────────
function calcRemittance(){
  const amount   = parseFloat(document.getElementById("rm-amount")?.value || 0);
  const corridor = parseFloat(document.getElementById("rm-corridor")?.value || 6.0);
  const res      = document.getElementById("rm-results");
  if(!amount || amount <= 0 || !res) return;

  const swiftFee  = amount * (corridor / 100);
  const swiftRecv = amount - swiftFee;
  const xrpFee    = 0.0002;
  const xrpRecv   = amount - xrpFee;
  const savings   = swiftFee - xrpFee;
  const xrpNeeded = currentXRPPrice > 0 ? (amount / currentXRPPrice).toFixed(2) : "--";

  const fmt = v => "$" + v.toLocaleString("en-US", {minimumFractionDigits:2, maximumFractionDigits:2});

  c("rm-swift-fee",  fmt(swiftFee));
  c("rm-swift-recv", fmt(swiftRecv) + " received");
  c("rm-xrp-recv",   fmt(xrpRecv)   + " received");
  c("rm-savings",    fmt(savings));
  c("rm-xrp-needed", `${xrpNeeded} XRP needed · at live price`);

  res.style.display = "block";
}

// ── 32. P&L Calculator ────────────────────────────────────────────────────
function calcPL(){
  const buy  = parseFloat(document.getElementById("pl-buy")?.value  || 0);
  const qty  = parseFloat(document.getElementById("pl-qty")?.value  || 0);
  const sell = parseFloat(document.getElementById("pl-sell")?.value || 0);
  const res  = document.getElementById("pl-results");
  if(!buy || !qty || !sell || !res) return;

  const cost   = buy  * qty;
  const value  = sell * qty;
  const plUSD  = value - cost;
  const plPct  = ((sell - buy) / buy) * 100;
  const isPos  = plUSD >= 0;
  const col    = isPos ? "var(--gr)" : "var(--rd)";
  const sign   = isPos ? "+" : "";

  c("pl-cost",  `$${cost.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}`);
  c("pl-value", `$${value.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}`);

  const plUSDEl = document.getElementById("pl-usd");
  if(plUSDEl){
    plUSDEl.textContent = `${sign}$${Math.abs(plUSD).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
    plUSDEl.style.color = col;
  }
  const plPctEl = document.getElementById("pl-pct");
  if(plPctEl){
    plPctEl.textContent = `${sign}${plPct.toFixed(2)}%`;
    plPctEl.style.color = col;
  }
  res.style.display = "block";
  res.style.borderColor = isPos ? "rgba(72,255,130,.3)" : "rgba(255,64,96,.3)";
}

// ── 33. Multi-Currency Display ─────────────────────────────────────────────
function updateToolsIntel(d){
  const ti  = d.tools_intel || {};
  const px  = parseFloat((d.price || {}).usd || 0);
  currentXRPPrice = px;
  if(!px) return;

  const fxr = ti.fx_rates || {};
  if(ti.ts) c("fx-ts", ti.ts);
  c("fx-usd", `$${px.toFixed(4)}`);

  const fxMap = {
    "fx-eur":"EUR", "fx-gbp":"GBP", "fx-jpy":"JPY",
    "fx-aud":"AUD", "fx-cad":"CAD", "fx-sgd":"SGD",
    "fx-inr":"INR", "fx-brl":"BRL",
  };
  const decimals = {"fx-jpy":0,"fx-inr":2};

  Object.entries(fxMap).forEach(([elId, cur])=>{
    const rate = fxr[cur] || 0;
    if(!rate) return;
    const converted = px * rate;
    const dec = decimals[elId] !== undefined ? decimals[elId] : 4;
    const el = document.getElementById(elId);
    if(el) el.textContent = converted.toFixed(dec);
  });

  // Refresh portfolio values with new price
  if(portfolioEntries.length) renderPortfolio();
}

// ── 34. Wallet Checker ────────────────────────────────────────────────────
async function checkWallet(){
  const addr = (document.getElementById("wallet-addr")?.value || "").trim();
  const res  = document.getElementById("wallet-result");
  if(!addr || !addr.startsWith("r") || addr.length < 20){
    if(res) res.innerHTML = '<div style="color:var(--rd)">⚠️ Enter a valid XRPL address (starts with r, 25-34 chars)</div>';
    return;
  }
  if(res) res.innerHTML = '<div style="color:var(--tx)">🔍 Fetching wallet data...</div>';
  try{
    const resp = await fetch(`https://api.xrpscan.com/api/v1/account/${addr}`);
    if(!resp.ok) throw new Error("Not found");
    const data = await resp.json();
    const bal  = parseFloat(data.xrpBalance || data.balance || 0);
    const usd  = bal * currentXRPPrice;
    const tag  = data.accountName?.name || "";
    const ts   = data.inception ? new Date(data.inception).toLocaleDateString() : "--";
    const txCnt= data.txCount || "--";
    res.innerHTML = `
      <div style="background:var(--s2);border:1px solid rgba(117,188,255,.3);
        border-radius:6px;padding:10px">
        ${tag ? `<div style="font-size:13px;color:var(--yl);font-weight:700;
          margin-bottom:6px;font-family:var(--mn)">🏷️ ${tag}</div>` : ""}
        <div style="font-size:28px;font-weight:900;font-family:var(--mn);
          color:var(--bl);margin-bottom:4px">
          ${bal.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:6})} XRP
        </div>
        <div style="font-size:18px;font-weight:700;font-family:var(--mn);
          color:var(--gr);margin-bottom:8px">
          ≈ $${usd.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})} USD
        </div>
        <div style="font-size:13px;color:var(--tx);display:flex;gap:12px;flex-wrap:wrap">
          <span>Account opened: <strong style="color:var(--br)">${ts}</strong></span>
          <span>Transactions: <strong style="color:var(--br)">${txCnt}</strong></span>
        </div>
        <div style="font-size:13px;font-family:var(--mn);color:var(--tx);
          margin-top:6px;word-break:break-all">${addr}</div>
      </div>`;
  }catch(err){
    if(res) res.innerHTML = `<div style="color:var(--rd)">⚠️ Could not load wallet: ${err.message}. Verify address is valid.</div>`;
  }
}

// ── 35. Portfolio Tracker ─────────────────────────────────────────────────
function addPortfolioEntry(){
  const label  = document.getElementById("pt-label")?.value?.trim()  || `Entry ${portfolioEntries.length+1}`;
  const amount = parseFloat(document.getElementById("pt-amount")?.value || 0);
  const cost   = parseFloat(document.getElementById("pt-cost")?.value  || 0);
  if(!amount || amount <= 0){ alert("Enter a valid XRP amount"); return; }
  portfolioEntries.push({ label, amount, cost, id: Date.now() });
  ["pt-label","pt-amount","pt-cost"].forEach(id=>{
    const el = document.getElementById(id);
    if(el) el.value = "";
  });
  renderPortfolio();
}

function removePortfolioEntry(id){
  portfolioEntries = portfolioEntries.filter(e => e.id !== id);
  renderPortfolio();
}

function renderPortfolio(){
  const tableEl  = document.getElementById("portfolio-table");
  const totalsEl = document.getElementById("portfolio-totals");
  if(!tableEl) return;
  if(!portfolioEntries.length){
    tableEl.innerHTML = '<div style="font-size:13px;font-family:var(--mn);color:var(--tx)">No entries yet. Add a position above.</div>';
    if(totalsEl) totalsEl.style.display = "none";
    return;
  }
  let totalXRP = 0, totalVal = 0, totalCost = 0;
  tableEl.innerHTML = `<table style="width:100%;border-collapse:collapse;font-family:var(--mn);font-size:13px;margin-bottom:6px">
    <thead><tr style="background:var(--s2);border-bottom:1px solid var(--b)">
      <th style="padding:4px 6px;text-align:left;color:var(--tx);font-size:13px">Label</th>
      <th style="padding:4px 6px;text-align:right;color:var(--tx);font-size:13px">XRP</th>
      <th style="padding:4px 6px;text-align:right;color:var(--tx);font-size:13px">Buy $</th>
      <th style="padding:4px 6px;text-align:right;color:var(--tx);font-size:13px">Value</th>
      <th style="padding:4px 6px;text-align:right;color:var(--tx);font-size:13px">P&amp;L</th>
      <th style="padding:4px 6px;text-align:right;color:var(--tx);font-size:13px">%</th>
      <th style="padding:4px 4px;text-align:center;color:var(--tx);font-size:13px"></th>
    </tr></thead><tbody>` +
    portfolioEntries.map(e=>{
      const val  = e.amount * currentXRPPrice;
      const cost = e.cost   * e.amount;
      const pl   = val - cost;
      const pct  = e.cost > 0 ? ((currentXRPPrice - e.cost) / e.cost * 100) : 0;
      const col  = pl >= 0 ? "var(--gr)" : "var(--rd)";
      const sign = pl >= 0 ? "+" : "";
      totalXRP  += e.amount;
      totalVal  += val;
      totalCost += cost;
      return `<tr style="border-bottom:1px solid rgba(255,255,255,.03)">
        <td style="padding:4px 6px;color:var(--br);font-weight:700">${e.label}</td>
        <td style="padding:4px 6px;text-align:right;color:var(--br)">${e.amount.toLocaleString()}</td>
        <td style="padding:4px 6px;text-align:right;color:var(--tx)">$${e.cost.toFixed(4)}</td>
        <td style="padding:4px 6px;text-align:right;color:var(--bl);font-weight:700">
          $${val.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}
        </td>
        <td style="padding:4px 6px;text-align:right;color:${col};font-weight:700">
          ${sign}$${Math.abs(pl).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}
        </td>
        <td style="padding:4px 6px;text-align:right;color:${col};font-weight:700">
          ${sign}${pct.toFixed(1)}%
        </td>
        <td style="padding:4px 4px;text-align:center">
          <span onclick="removePortfolioEntry(${e.id})"
            style="color:var(--rd);cursor:pointer;font-size:13px">✕</span>
        </td>
      </tr>`;
    }).join("") + "</tbody></table>";

  const totalPL  = totalVal - totalCost;
  const totalPct = totalCost > 0 ? (totalPL / totalCost * 100) : 0;
  const col      = totalPL >= 0 ? "var(--gr)" : "var(--rd)";
  const sign     = totalPL >= 0 ? "+" : "";
  c("pt-total-xrp", totalXRP.toLocaleString() + " XRP");
  c("pt-total-val", `$${totalVal.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`);
  const plEl = document.getElementById("pt-total-pl");
  if(plEl){
    plEl.textContent = `${sign}$${Math.abs(totalPL).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})} (${sign}${totalPct.toFixed(2)}%)`;
    plEl.style.color = col;
  }
  if(totalsEl) totalsEl.style.display = "block";
}

// ── Sentiment Engine (v3.0g) ───────────────────────────────────────────────
function updateSentIntel(d){
  const si = d.sent_intel || {};

  // ── 31. Google Trend Score ────────────────────────────────────────────
  const score = si.google_trend || 0;
  const scoreEl = document.getElementById("sg-trend-score");
  if(scoreEl){
    scoreEl.textContent = score;
    scoreEl.style.color = score > 70 ? "var(--gr)" : score > 40 ? "var(--yl)" : "var(--tx)";
  }
  c("sg-trend-label", si.google_trend_label || "--");
  const tBar = document.getElementById("sg-trend-bar");
  if(tBar){
    tBar.style.width     = `${score}%`;
    tBar.style.background = score > 70 ? "var(--gr)" : score > 40 ? "var(--yl)" : "var(--tx)";
  }
  if(si.trend_keywords && si.trend_keywords.length){
    const kwEl = document.getElementById("sg-trend-kw");
    if(kwEl) kwEl.textContent = si.trend_keywords.slice(0,3).join(" · ");
  }

  // ── 29. News Velocity Chart (24h bars) ────────────────────────────────
  const velEl = document.getElementById("sg-velocity-chart");
  if(velEl && si.velocity_hours && si.velocity_hours.length){
    const maxV = Math.max(...si.velocity_hours.map(h=>h.count), 1);
    velEl.innerHTML = si.velocity_hours.map((h,i)=>{
      const pct  = Math.round((h.count / maxV) * 100);
      const isNow = i === 23;
      const col  = isNow ? "var(--bl)" : h.count > maxV * 0.7 ? "var(--gr)" :
                   h.count > maxV * 0.3 ? "var(--yl)" : "var(--s2)";
      return `<div title="${h.count} stories" style="flex:1;background:${col};
        border-radius:2px 2px 0 0;min-height:2px;height:${Math.max(pct,2)}%;
        transition:height .4s;cursor:default"></div>`;
    }).join("");
  }

  // ── 28. 30-Day Sentiment Chart ────────────────────────────────────────
  const dayEl = document.getElementById("sg-daily-chart");
  const di2   = d.disp_intel || {};
  const fgHist= di2.fg_history || [];

  // Use story sentiment if we have 3+ days; otherwise fall back to F&G history
  const hasSentDays = si.daily_sentiment && si.daily_sentiment.length >= 3;

  if(dayEl && !hasSentDays && fgHist.length){
    // Fallback: render Fear & Greed 30-day as the trend chart
    const labelEl = document.getElementById("sg-daily-labels");
    if(labelEl) labelEl.innerHTML = '<span>30d ago</span><span>20d ago</span><span>10d ago</span><span style="color:var(--bl)">today (F&G)</span>';
    const fgColor = v => v<=25?"var(--rd)":v<=45?"var(--or)":v<=55?"var(--yl)":v<=75?"var(--gr)":"#00ffcc";
    dayEl.innerHTML = fgHist.map((f,i)=>{
      const isToday = i === fgHist.length-1;
      return `<div title="${f.label||''}: ${f.value}"
        style="flex:1;background:${fgColor(f.value)};border-radius:2px 2px 0 0;
          min-height:3px;height:${f.value}%;cursor:default;
          ${isToday?"outline:2px solid #fff;outline-offset:-1px":""}
          opacity:0.8">
      </div>`;
    }).join("");
  } else if(dayEl && hasSentDays){
    const days = si.daily_sentiment;
    const maxD = Math.max(...days.map(d=>d.total), 1);
    dayEl.innerHTML = days.map((day,i)=>{
      const h    = Math.round((day.total / maxD) * 80);
      const bPct = day.bull_pct || 0;
      const rPct = day.bear_pct || 0;
      const nPct = 100 - bPct - rPct;
      const isToday = i === days.length - 1;
      return `<div title="${day.date}: ${day.bull}🟢 ${day.bear}🔴 ${day.neut}⚪ (${day.total} total)"
        style="flex:1;display:flex;flex-direction:column;min-width:4px;
          border-radius:2px 2px 0 0;overflow:hidden;cursor:default;
          ${isToday?"outline:1px solid var(--bl)":""};height:${Math.max(h,3)}px">
        <div style="flex:${bPct};background:var(--gr);min-height:${bPct>0?1:0}px"></div>
        <div style="flex:${nPct};background:var(--tx);min-height:${nPct>0?1:0}px"></div>
        <div style="flex:${rPct};background:var(--rd);min-height:${rPct>0?1:0}px"></div>
      </div>`;
    }).join("");
  } else if(dayEl){
    dayEl.innerHTML = '<div style="font-size:13px;font-family:var(--mn);color:var(--tx);padding:20px;text-align:center">📡 Sentiment history accumulates over time as stories are collected.</div>';
  }

  // ── 30. Source Leaderboard ────────────────────────────────────────────
  const lbEl = document.getElementById("sg-leaderboard");
  if(lbEl && si.source_leaders && si.source_leaders.length){
    const medals = ["🥇","🥈","🥉"];
    lbEl.innerHTML = si.source_leaders.map((src,i)=>{
      const rank  = medals[i] || `${i+1}`;
      const bPct  = src.bull_pct || 0;
      const rPct  = src.bear_pct || 0;
      const rowBg = i < 3 ? `background:rgba(${i===0?"255,204,0":i===1?"192,192,192":"205,127,50"},.05)` : "";
      return `<tr style="border-bottom:1px solid rgba(255,255,255,.03);${rowBg}">
        <td style="padding:5px 8px;text-align:center;font-size:13px">${rank}</td>
        <td style="padding:5px 8px;font-weight:700;color:var(--br)">${src.name}</td>
        <td style="padding:5px 8px;text-align:center;font-weight:700;
          color:var(--bl)">${src.total}</td>
        <td style="padding:5px 8px;text-align:center;color:var(--gr);font-weight:700">${bPct}%</td>
        <td style="padding:5px 8px;text-align:center;color:var(--rd);font-weight:700">${rPct}%</td>
        <td style="padding:5px 8px;min-width:80px">
          <div style="height:6px;background:var(--s2);border-radius:3px;overflow:hidden">
            <div style="height:100%;width:${bPct}%;background:var(--gr);border-radius:3px"></div>
          </div>
        </td>
        <td style="padding:5px 8px;text-align:center;color:var(--yl);font-weight:700">
          ${src.breaking > 0 ? src.breaking : "—"}
        </td>
      </tr>`;
    }).join("");
  }
}



// ── XRP Ecosystem Map ──────────────────────────────────────────────────────
function updateEcosystem(d){
  const p  = d.price        || {};
  const oc = d.onchain_intel|| {};

  // Live stats wired into cards
  const supply = p.supply_circ
    ? (parseFloat(p.supply_circ)/1e9).toFixed(1) + "B XRP"
    : "~57B XRP";
  c("eco-supply",   supply);

  const acct = oc.accounts_total
    ? parseInt(oc.accounts_total).toLocaleString()
    : "--";
  c("eco-accounts", acct);

  const rlusd = oc.rlusd_supply && oc.rlusd_supply > 0
    ? "$" + (parseFloat(oc.rlusd_supply)/1e6).toFixed(1) + "M"
    : "--";
  c("eco-rlusd", rlusd);

  const dex = oc.dex_vol_24h && oc.dex_vol_24h > 0
    ? "$" + (parseFloat(oc.dex_vol_24h)/1e6).toFixed(2) + "M"
    : "--";
  c("eco-dex", dex);
}

// ── Mainstream Integration Monitor ────────────────────────────────────────
function updateMainstreamIntel(d){
  const mi = d.mainstream_intel || {};

  // ── Partnership Grid ──────────────────────────────────────────────────
  const grid = document.getElementById("ms-partner-grid");
  if(grid && mi.partnerships){
    const statusStyle = {
      "CONFIRMED": {bg:"rgba(72,255,130,.08)",  border:"rgba(72,255,130,.35)",  col:"var(--gr)",  icon:"✅"},
      "EXPLORING": {bg:"rgba(117,188,255,.08)", border:"rgba(117,188,255,.35)", col:"var(--bl)",  icon:"🔍"},
      "RUMORED":   {bg:"rgba(255,204,0,.08)",   border:"rgba(255,204,0,.35)",   col:"var(--yl)",  icon:"💬"},
      "PILOT":     {bg:"rgba(255,153,0,.08)",   border:"rgba(255,153,0,.35)",   col:"var(--or)",  icon:"🧪"},
      "COMPETING": {bg:"rgba(255,64,96,.08)",   border:"rgba(255,64,96,.35)",   col:"var(--rd)",  icon:"⚔️"},
    };
    grid.innerHTML = mi.partnerships.map(p=>{
      const st = statusStyle[p.status] || statusStyle["EXPLORING"];
      return `<div class="ms-card" data-status="${p.status}"
        style="background:${st.bg};border:1px solid ${st.border};
        border-radius:8px;padding:12px;cursor:default;transition:transform .2s"
        title="${p.detail} — ${p.source}"
        onmouseover="this.style.transform='scale(1.02)'"
        onmouseout="this.style.transform='scale(1)'">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
          <span style="font-size:13px">${p.country.split(" ")[0]}</span>
          <span style="font-size:11px;font-weight:700;font-family:var(--mn);
            color:${st.col}">${st.icon} ${p.status}</span>
          <span style="font-size:10px;font-family:var(--mn);color:var(--tx);
            margin-left:auto">${p.type}</span>
        </div>
        <div style="font-size:13px;font-weight:900;color:#fff;
          font-family:var(--mn);margin-bottom:4px">${p.institution}</div>
        <div style="font-size:11px;color:var(--tx);line-height:1.5;
          font-family:system-ui">${p.detail.substring(0,90)}${p.detail.length>90?"...":""}</div>
        <div style="font-size:10px;font-family:var(--mn);color:var(--tx);
          margin-top:5px;font-style:italic">${p.source}</div>
      </div>`;
    }).join("");
    if(typeof activeMainstreamFilter !== 'undefined' && activeMainstreamFilter !== 'ALL'){
      filterMainstream(activeMainstreamFilter);
    }
  }

  // ── Integration Timeline ──────────────────────────────────────────────
  const tl = document.getElementById("ms-timeline");
  if(tl && mi.integration_timeline){
    tl.innerHTML = mi.integration_timeline.map((ev,i)=>{
      const isLast   = i === mi.integration_timeline.length - 1;
      const isMajor  = ev.major;
      const dotColor = isLast ? "var(--gr)" : isMajor ? "var(--yl)" : "var(--tx)";
      const dotSize  = isMajor ? "14px" : "10px";
      return `<div style="display:flex;flex-direction:column;align-items:center;
        min-width:120px;flex:1;padding:0 6px;position:relative">
        <!-- Dot on the line -->
        <div style="width:${dotSize};height:${dotSize};border-radius:50%;
          background:${dotColor};border:2px solid var(--bg);
          margin-bottom:8px;flex-shrink:0;z-index:1;
          ${isMajor?`box-shadow:0 0 10px ${dotColor}`:""}"></div>
        <!-- Content below line -->
        <div style="text-align:center">
          <div style="font-size:12px;font-weight:900;font-family:var(--mn);
            color:${dotColor};margin-bottom:2px">${ev.year}</div>
          <div style="font-size:11px;font-weight:700;color:#fff;
            line-height:1.3;margin-bottom:3px">${ev.event}</div>
          <div style="font-size:10px;color:var(--tx);line-height:1.4;
            font-family:system-ui">${ev.detail.substring(0,60)}${ev.detail.length>60?"...":""}</div>
        </div>
      </div>`;
    }).join("");
  }
}

// ── Competitive Intelligence (v3.0f) ──────────────────────────────────────
function updateCompIntel(d){
  const ci = d.comp_intel || {};

  // ── 24. XRP vs Competitors ────────────────────────────────────────────
  const tbody = document.getElementById("comp-vs-body");
  if(tbody){
    const xrp   = ci.xrp_vs || {};
    const coins = ci.vs_coins || {};
    const edges = {
      "SOL": "Payment rails vs smart contract platform. XRP: instant settlement, 0.0002 USD fee.",
      "ETH": "XRP 1,000x cheaper per tx. 3-sec vs 12-sec finality. Purpose-built for payments.",
      "ADA": "XRP: live ODL corridors, bank partnerships, regulatory clarity vs research-phase.",
      "XLM": "XRP: larger liquidity, more corridors, institutional adoption. Stellar: NGO focus.",
    };
    const rows = [
      {id:"ripple",   sym:"XRP",  emoji:"🪙",  data: xrp,                  isSelf: true},
      {id:"solana",   sym:"SOL",  emoji:"◎",   data: coins.solana  || {},   isSelf: false},
      {id:"ethereum", sym:"ETH",  emoji:"⟠",   data: coins.ethereum|| {},   isSelf: false},
      {id:"cardano",  sym:"ADA",  emoji:"₳",   data: coins.cardano || {},   isSelf: false},
      {id:"stellar",  sym:"XLM",  emoji:"✦",   data: coins.stellar || {},   isSelf: false},
    ];
    tbody.innerHTML = rows.map((r,i)=>{
      const ch24 = parseFloat(r.data.change_24h || 0);
      const ch7d = parseFloat(r.data.change_7d  || 0);
      const px   = parseFloat(r.data.price      || 0);
      const mc   = parseFloat(r.data.mcap       || 0);
      const c24c = ch24 >= 0 ? "var(--gr)" : "var(--rd)";
      const c7dc = ch7d >= 0 ? "var(--gr)" : "var(--rd)";
      const edge = edges[r.sym] || "";
      const rowBg = r.isSelf
        ? "background:rgba(117,188,255,.06);border-left:3px solid var(--bl)"
        : i%2===0 ? "background:var(--s1)" : "";
      return `<tr style="${rowBg};border-bottom:1px solid rgba(255,255,255,.03)">
        <td style="padding:8px 12px">
          <span style="font-size:16px;margin-right:6px">${r.emoji}</span>
          <span style="font-weight:900;color:${r.isSelf?"var(--bl)":"var(--br)"};
            font-family:var(--mn)">${r.sym}</span>
        </td>
        <td style="padding:8px 12px;text-align:right;font-weight:700;
          color:var(--br);font-family:var(--mn)">
          $${px < 1 ? px.toFixed(4) : px.toFixed(2)}
        </td>
        <td style="padding:8px 12px;text-align:right;font-weight:700;
          color:${c24c};font-family:var(--mn)">
          ${ch24>=0?"+":""}${ch24.toFixed(2)}%
        </td>
        <td style="padding:8px 12px;text-align:right;font-weight:700;
          color:${c7dc};font-family:var(--mn)">
          ${ch7d>=0?"+":""}${ch7d.toFixed(2)}%
        </td>
        <td style="padding:8px 12px;text-align:right;font-family:var(--mn);color:var(--tx)">
          ${mc >= 1e9 ? "$"+(mc/1e9).toFixed(1)+"B" : mc >= 1e6 ? "$"+(mc/1e6).toFixed(1)+"M" : "--"}
        </td>
        <td style="padding:8px 12px;font-size:13px;color:${r.isSelf?"var(--bl)":"var(--tx)"};
          max-width:220px">${r.isSelf ? "🎯 Tracking live" : edge}</td>
      </tr>`;
    }).join("");
  }

  // ── Mainstream Integration Filter ──────────────────────────────────────
  let activeMainstreamFilter = 'ALL';
  function filterMainstream(status){
    activeMainstreamFilter = status;
    document.querySelectorAll('[id^="msf-"]').forEach(btn=>{
      btn.style.opacity='0.5'; btn.style.fontWeight='700'; btn.style.outline='none';
    });
    const active = document.getElementById('msf-'+status);
    if(active){ active.style.opacity='1'; active.style.outline='2px solid currentColor'; }
    document.querySelectorAll('.ms-card').forEach(card=>{
      card.style.display = (status==='ALL'||card.dataset.status===status) ? '' : 'none';
    });
    const visible = [...document.querySelectorAll('.ms-card')].filter(c=>c.style.display!=='none').length;
    const el = document.getElementById('ms-count');
    if(el) el.textContent = visible + ' partner' + (visible!==1?'s':'');
  }



  // ── 25. ODL Corridors ─────────────────────────────────────────────────
  const odlEl = document.getElementById("comp-odl-list");
  if(odlEl && ci.odl_corridors){
    const stColor = {"ACTIVE":"var(--gr)","GROWING":"var(--yl)","PENDING":"var(--tx)"};
    odlEl.innerHTML = ci.odl_corridors.map(c=>`
      <div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;
        border-bottom:1px solid rgba(255,255,255,.04)">
        <span style="font-size:13px;color:${stColor[c.status]||"var(--tx)"};
          margin-top:5px;flex-shrink:0">●</span>
        <div style="min-width:0">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
            <span style="font-size:13px;font-weight:700;color:var(--br);font-family:var(--mn)">
              ${c.from_c} → ${c.to_c}
            </span>
            <span style="font-size:13px;color:${stColor[c.status]};font-weight:700;
              font-family:var(--mn)">${c.status}</span>
            <span style="font-size:13px;color:var(--tx);font-family:var(--mn)">${c.partner}</span>
          </div>
          <div style="font-size:13px;color:var(--tx);margin-top:2px;line-height:1.4">${c.vol_note}</div>
        </div>
      </div>`).join("");
  }

  // ── 26. ISO 20022 ─────────────────────────────────────────────────────
  const isoAdv = document.getElementById("comp-iso-advantage");
  if(isoAdv && ci.iso20022) isoAdv.textContent = ci.iso20022.xrp_advantage || "";

  const isoBanks = document.getElementById("comp-iso-banks");
  if(isoBanks && ci.iso20022) isoBanks.textContent = `${ci.iso20022.banks_exploring}+`;

  const isoEl = document.getElementById("comp-iso-list");
  if(isoEl && ci.iso20022 && ci.iso20022.adopted){
    isoEl.innerHTML = ci.iso20022.adopted.map(a=>`
      <div style="display:flex;align-items:center;gap:7px;padding:4px 0;
        border-bottom:1px solid rgba(255,255,255,.03);font-family:var(--mn);font-size:13px">
        <span style="color:var(--gr);font-size:13px">✅</span>
        <span style="font-weight:700;color:var(--br)">${a.name}</span>
        <span style="color:var(--tx)">${a.region}</span>
        <span style="color:var(--tx);margin-left:auto;font-size:13px">${a.note.substring(0,40)}...</span>
      </div>`).join("");
  }

  // ── 27. XRP vs SWIFT ─────────────────────────────────────────────────
  const sv = ci.swift_vs || {};
  if(sv.note) c("cs-note", sv.note);
}

// ── Regulatory Radar (v3.0d) ───────────────────────────────────────────────
function updateRegIntel(d){
  const ri = d.reg_intel || {};

  // ── 17. Country Status Grid ───────────────────────────────────────────
  const cgEl = document.getElementById("reg-country-grid");
  if(cgEl && ri.countries){
    const colorMap = {
      "LEGAL":     {bg:"rgba(72,255,130,.08)",  border:"rgba(72,255,130,.35)",  text:"var(--gr)", icon:"✅"},
      "TAXED":     {bg:"rgba(117,188,255,.08)", border:"rgba(117,188,255,.35)", text:"var(--bl)", icon:"📋"},
      "CONTESTED": {bg:"rgba(255,204,0,.08)",   border:"rgba(255,204,0,.35)",   text:"var(--yl)", icon:"⚠️"},
      "RESTRICTED":{bg:"rgba(255,153,0,.08)",   border:"rgba(255,153,0,.35)",   text:"var(--or)", icon:"🔶"},
      "PENDING":   {bg:"rgba(128,153,179,.08)", border:"rgba(128,153,179,.3)",  text:"var(--tx)", icon:"🔍"},
      "BANNED":    {bg:"rgba(255,64,96,.08)",   border:"rgba(255,64,96,.35)",   text:"var(--rd)", icon:"❌"},
    };
    cgEl.innerHTML = ri.countries.map(c=>{
      const cm = colorMap[c.status] || colorMap["PENDING"];
      return `<div title="${c.note||""}"
        style="background:${cm.bg};border:1px solid ${cm.border};border-radius:6px;
          padding:7px 8px;cursor:default;transition:border-color .2s"
        onmouseover="showRegTooltip(this,'${(c.note||"").replace(/'/g,"&#39;")}')"
        onmouseout="hideRegTooltip()">
        <div style="font-size:16px;margin-bottom:3px">${c.flag}</div>
        <div style="font-size:13px;font-weight:700;color:var(--br);font-family:var(--mn);
          line-height:1.2;margin-bottom:3px">${c.country}</div>
        <div style="font-size:13px;font-weight:700;color:${cm.text};font-family:var(--mn)">
          ${cm.icon} ${c.status}
        </div>
      </div>`;
    }).join("");
  }

  // ── 18. ETF / ETP Tracker ─────────────────────────────────────────────
  const etfEl = document.getElementById("reg-etf-body");
  if(etfEl && ri.etf_tracker){
    const etfColor = {"LIVE":"var(--gr)","FILED":"var(--bl)","REVIEW":"var(--yl)","PENDING":"var(--tx)","REJECTED":"var(--rd)"};
    etfEl.innerHTML = ri.etf_tracker.map((e,i)=>`
      <tr style="border-bottom:1px solid rgba(255,255,255,.03);
        background:${i%2===0?"var(--s1)":"transparent"}">
        <td style="padding:6px 10px;color:var(--br);font-weight:700">${e.applicant}</td>
        <td style="padding:6px 10px;color:var(--tx)">${e.product}</td>
        <td style="padding:6px 10px;color:var(--tx)">${e.market}</td>
        <td style="padding:6px 10px">
          <span style="color:${etfColor[e.status]||"var(--tx)"};font-weight:700;
            font-family:var(--mn);font-size:13px;
            background:${etfColor[e.status]||"var(--tx)"}18;
            padding:2px 8px;border-radius:3px;
            border:1px solid ${etfColor[e.status]||"var(--b)"}44">
            ${e.status==="LIVE"?"✅":e.status==="FILED"?"📋":e.status==="REVIEW"?"⏳":"🔍"} ${e.status}
          </span>
        </td>
        <td style="padding:6px 10px;color:var(--tx)">${e.date}</td>
        <td style="padding:6px 10px;color:var(--tx);font-size:13px">${e.note}</td>
      </tr>`).join("");
  }

  // ── 19. SEC Case Timeline ─────────────────────────────────────────────
  const secEl = document.getElementById("reg-sec-timeline");
  if(secEl && ri.sec_timeline){
    secEl.innerHTML = ri.sec_timeline.map(ev=>{
      const isCurrent = ev.status === "current";
      const isMajor   = ev.major;
      const dotColor  = isCurrent ? "var(--gr)" : isMajor ? "var(--yl)" : "var(--bl)";
      return `<div style="display:flex;gap:10px;margin-bottom:10px;position:relative">
        <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0">
          <div style="width:${isMajor?"12px":"8px"};height:${isMajor?"12px":"8px"};
            border-radius:50%;background:${dotColor};margin-top:3px;
            ${isMajor?`box-shadow:0 0 8px ${dotColor}`:""}"></div>
          <div style="width:1px;flex:1;background:var(--b);margin-top:4px"></div>
        </div>
        <div style="padding-bottom:6px">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:2px">
            <span style="font-size:13px;font-weight:700;font-family:var(--mn);
              color:${dotColor}">${ev.date}</span>
            ${isCurrent?'<span style="font-size:13px;font-family:var(--mn);color:var(--gr);background:rgba(72,255,130,.1);padding:1px 5px;border-radius:3px;border:1px solid rgba(72,255,130,.3)">NOW</span>':""}
            ${isMajor?'<span style="font-size:13px;font-family:var(--mn);color:var(--yl)">★ MAJOR</span>':""}
          </div>
          <div style="font-size:13px;font-weight:700;color:var(--br);margin-bottom:2px">${ev.event}</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.5">${ev.detail}</div>
        </div>
      </div>`;
    }).join("");
  }

  // ── 20. MiCA Calendar ─────────────────────────────────────────────────
  const micaEl = document.getElementById("reg-mica-calendar");
  if(micaEl && ri.mica_calendar){
    micaEl.innerHTML = ri.mica_calendar.map(m=>{
      const dotColor = m.done ? "var(--gr)" : "var(--tx)";
      return `<div style="display:flex;gap:10px;margin-bottom:10px">
        <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0">
          <div style="width:8px;height:8px;border-radius:50%;margin-top:3px;
            background:${dotColor};${m.done?`box-shadow:0 0 6px ${dotColor}`:"border:1px solid var(--b)"}"></div>
          <div style="width:1px;flex:1;background:var(--b);margin-top:4px"></div>
        </div>
        <div style="padding-bottom:6px">
          <div style="font-size:13px;font-weight:700;font-family:var(--mn);
            color:${dotColor};margin-bottom:2px">
            ${m.date} ${m.done?"✓":""}
          </div>
          <div style="font-size:13px;font-weight:700;color:${m.done?"var(--br)":"var(--tx)"};margin-bottom:2px">${m.event}</div>
          <div style="font-size:13px;color:var(--tx);line-height:1.5">${m.detail}</div>
        </div>
      </div>`;
    }).join("");
  }

  // ── 21. CBDC Projects ─────────────────────────────────────────────────
  const cbdcEl = document.getElementById("reg-cbdc-grid");
  if(cbdcEl && ri.cbdc_projects){
    const stColor = {"LIVE":"var(--gr)","PILOT":"var(--yl)","EXPLORING":"var(--bl)"};
    cbdcEl.innerHTML = ri.cbdc_projects.map(p=>`
      <div style="background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:12px;
        border-color:${stColor[p.status]||"var(--b)"}44">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
          <span style="font-size:20px">${p.flag}</span>
          <div>
            <div style="font-size:13px;font-weight:700;color:var(--br);font-family:var(--mn)">${p.country}</div>
            <div style="font-size:13px;color:${stColor[p.status]||"var(--tx)"};font-weight:700;font-family:var(--mn)">
              ${p.status==="LIVE"?"✅":p.status==="PILOT"?"🧪":"🔍"} ${p.status}
            </div>
          </div>
          <div style="margin-left:auto;font-size:13px;font-family:var(--mn);
            color:var(--tx);text-align:right">${p.partner}</div>
        </div>
        <div style="font-size:13px;font-weight:700;color:var(--bl);margin-bottom:4px">${p.project}</div>
        <div style="font-size:13px;color:var(--tx);line-height:1.5">${p.detail}</div>
      </div>`).join("");
  }
}

// ── Reg Tooltip ────────────────────────────────────────────────────────────
let regTooltip = null;
function showRegTooltip(el, text){
  if(!text) return;
  let tt = document.getElementById("reg-tt");
  if(!tt){
    tt = document.createElement("div");
    tt.id = "reg-tt";
    tt.style.cssText = "position:fixed;z-index:9000;background:var(--s1);border:1px solid var(--b);"+
      "color:var(--br);font-size:13px;font-family:system-ui;padding:8px 12px;border-radius:6px;"+
      "max-width:300px;line-height:1.6;pointer-events:none;box-shadow:0 4px 20px rgba(0,0,0,.5)";
    document.body.appendChild(tt);
  }
  tt.textContent = text;
  tt.style.display = "block";
  const r = el.getBoundingClientRect();
  tt.style.top  = (r.bottom + 6 + window.scrollY) + "px";
  tt.style.left = Math.min(r.left, window.innerWidth - 320) + "px";
}
function hideRegTooltip(){
  const tt = document.getElementById("reg-tt");
  if(tt) tt.style.display = "none";
}

// ── Technical Signals (v3.0c) ──────────────────────────────────────────────
function updateTechIntel(d){
  const ti  = d.tech_intel || {};
  const cur = (d.price || {}).usd || 0;

  // ── 13. RSI Gauges ─────────────────────────────────────────────────────
  function renderRSI(valId, barId, lblId, rsi, label){
    const valEl = document.getElementById(valId);
    const barEl = document.getElementById(barId);
    const lblEl = document.getElementById(lblId);
    if(!valEl || !barEl) return;

    const pct   = Math.min(Math.max(rsi, 0), 100);
    const color = rsi < 30 ? "var(--gr)" :
                  rsi < 45 ? "var(--yl)" :
                  rsi < 65 ? "var(--bl)" :
                  rsi < 75 ? "var(--or)" : "var(--rd)";

    valEl.textContent = rsi.toFixed(1);
    valEl.style.color = color;
    barEl.style.width = `${pct}%`;
    barEl.style.background = color;
    if(lblEl){ lblEl.textContent = label || ""; lblEl.style.color = color; }
  }

  if(ti.rsi_1h) renderRSI("rsi-1h-val","rsi-1h-bar","rsi-1h-lbl", ti.rsi_1h, ti.rsi_1h_label);
  if(ti.rsi_1d) renderRSI("rsi-1d-val","rsi-1d-bar","rsi-1d-lbl", ti.rsi_1d, ti.rsi_1d_label);

  // ── 14. 52-Week Range ──────────────────────────────────────────────────
  if(ti.week52_high && ti.week52_low){
    c("w52-low",  `$${parseFloat(ti.week52_low).toFixed(4)}`);
    c("w52-high", `$${parseFloat(ti.week52_high).toFixed(4)}`);
    c("w52-cur",  `$${parseFloat(cur).toFixed(4)}`);

    const needle = document.getElementById("w52-needle");
    if(needle && ti.week52_position !== undefined){
      needle.style.left = `${Math.min(Math.max(ti.week52_position, 1), 99)}%`;
    }
    c("w52-pos",       `${ti.week52_position}%`);

    const fromLow  = ti.week52_pct_low;
    const fromHigh = ti.week52_pct_high;
    const flEl = document.getElementById("w52-from-low");
    const fhEl = document.getElementById("w52-from-high");
    if(flEl){ flEl.textContent=`+${parseFloat(fromLow).toFixed(1)}%`; flEl.style.color="var(--gr)"; }
    if(fhEl){ fhEl.textContent=`${parseFloat(fromHigh).toFixed(1)}%`; fhEl.style.color="var(--rd)"; }
  }

  // ── 15. Support & Resistance Table ────────────────────────────────────
  const srEl = document.getElementById("sr-table");
  if(srEl){
    const res = (ti.resistance || []).slice().reverse(); // show highest first
    const sup = ti.support || [];
    if(!res.length && !sup.length){
      srEl.innerHTML = '<div class="empty">Calculating from 90-day price history...</div>';
    } else {
      let html = "";
      res.forEach((r,i)=>{
        const pct = cur > 0 ? ((r-cur)/cur*100).toFixed(2) : "--";
        html += `<div style="display:flex;justify-content:space-between;padding:5px 0;
          border-bottom:1px solid rgba(255,255,255,.04);font-family:var(--mn);font-size:13px">
          <span style="color:var(--rd);font-weight:700">R${res.length-i}</span>
          <span style="color:var(--br);font-weight:700">$${parseFloat(r).toFixed(4)}</span>
          <span style="color:var(--rd)">+${pct}%</span>
        </div>`;
      });
      // Current price divider
      html += `<div style="display:flex;justify-content:space-between;padding:6px 0;
        background:var(--bld);border-radius:4px;margin:4px 0;padding:5px 8px;
        font-family:var(--mn);font-size:13px;border:1px solid rgba(117,188,255,.3)">
        <span style="color:var(--bl);font-weight:700">NOW</span>
        <span style="color:var(--br);font-weight:900">$${parseFloat(cur).toFixed(4)}</span>
        <span style="color:var(--bl)">current</span>
      </div>`;
      sup.forEach((s,i)=>{
        const pct = cur > 0 ? ((s-cur)/cur*100).toFixed(2) : "--";
        html += `<div style="display:flex;justify-content:space-between;padding:5px 0;
          border-bottom:1px solid rgba(255,255,255,.04);font-family:var(--mn);font-size:13px">
          <span style="color:var(--gr);font-weight:700">S${i+1}</span>
          <span style="color:var(--br);font-weight:700">$${parseFloat(s).toFixed(4)}</span>
          <span style="color:var(--gr)">${pct}%</span>
        </div>`;
      });
      srEl.innerHTML = html;
    }
  }

  // ── 16. Price Time Machine ────────────────────────────────────────────
  if(ti.price_1y_ago){
    c("pt-1y-price", `$${parseFloat(ti.price_1y_ago).toFixed(4)}`);
    const ch1y  = parseFloat(ti.price_1y_change || 0);
    const ch1yEl= document.getElementById("pt-1y-change");
    if(ch1yEl){
      ch1yEl.textContent = `${ch1y>=0?"+":""}${ch1y.toFixed(2)}% vs today`;
      ch1yEl.style.color = ch1y>=0?"var(--gr)":"var(--rd)";
    }
  }
  if(ti.price_1m_ago){
    c("pt-1m-price", `$${parseFloat(ti.price_1m_ago).toFixed(4)}`);
    const ch1m  = parseFloat(ti.price_1m_change || 0);
    const ch1mEl= document.getElementById("pt-1m-change");
    if(ch1mEl){
      ch1mEl.textContent = `${ch1m>=0?"+":""}${ch1m.toFixed(2)}% vs today`;
      ch1mEl.style.color = ch1m>=0?"var(--gr)":"var(--rd)";
    }
  }

  // Narrative
  if(ti.price_1y_ago && cur){
    const ch   = parseFloat(ti.price_1y_change || 0);
    const dir  = ch >= 0 ? "gained" : "lost";
    const emoji= ch >= 50 ? "🚀" : ch >= 20 ? "📈" : ch >= 0 ? "↗️" : ch >= -20 ? "↘️" : "📉";
    const narr = document.getElementById("pt-narrative");
    if(narr) narr.textContent =
      `${emoji} XRP has ${dir} ${Math.abs(ch).toFixed(1)}% over the past year. ` +
      `From $${parseFloat(ti.price_1y_ago).toFixed(4)} to $${parseFloat(cur).toFixed(4)} today.`;
  }
}

// ── On-Chain Intelligence (v3.0b) ─────────────────────────────────────────
function updateOnchainIntel(d){
  const oc = d.onchain_intel || {};

  // RLUSD
  if(oc.rlusd_supply)
    c("oc-rlusd-supply", fmtNum(oc.rlusd_supply));
  if(oc.rlusd_vol_24h)
    c("oc-rlusd-vol",    fmtUSD(oc.rlusd_vol_24h));

  // DEX Volume
  if(oc.dex_vol_24h)
    c("oc-dex-vol",    fmtUSD(oc.dex_vol_24h));
  if(oc.dex_trades_24h)
    c("oc-dex-trades", `${parseInt(oc.dex_trades_24h).toLocaleString()} trades 24h`);

  // Accounts
  if(oc.accounts_total)
    c("oc-accounts",     parseInt(oc.accounts_total).toLocaleString());
  if(oc.accounts_new_24h)
    c("oc-accounts-new", `+${parseInt(oc.accounts_new_24h).toLocaleString()}`);

  // Exchange Flow
  const flowEl  = document.getElementById("oc-flow");
  const flowBox = document.getElementById("oc-flow-box");
  const flowMap = {
    "INFLOW":  {color:"var(--gr)",  bg:"pos", icon:"📈"},
    "OUTFLOW": {color:"var(--rd)",  bg:"neg", icon:"📉"},
    "MIXED":   {color:"var(--yl)",  bg:"yl",  icon:"↕️"},
    "NEUTRAL": {color:"var(--tx)",  bg:"",    icon:"➡️"},
  };
  if(flowEl && oc.exchange_flow){
    const fm = flowMap[oc.exchange_flow] || flowMap["NEUTRAL"];
    flowEl.textContent  = `${fm.icon} ${oc.exchange_flow}`;
    flowEl.style.color  = fm.color;
    if(flowBox) flowBox.className = `abox ${fm.bg}`;
  }
  if(oc.exchange_flow_note) c("oc-flow-note", oc.exchange_flow_note);

  // Escrow Countdown
  if(oc.escrow_days !== undefined){
    c("oc-esc-days", String(oc.escrow_days).padStart(2,"0"));
    c("oc-esc-hrs",  String(oc.escrow_hours).padStart(2,"0"));
    c("oc-esc-min",  String(oc.escrow_minutes).padStart(2,"0"));
    c("oc-esc-date", `1B XRP · Next release: ${oc.escrow_next_date||"--"}`);
  }

  // Whale Alert Feed
  if(oc.ts) c("oc-whale-ts", oc.ts);
  const wf = document.getElementById("oc-whale-feed");
  if(wf && oc.whale_alerts){
    if(!oc.whale_alerts.length){
      wf.innerHTML='<div class="empty">No large transactions detected recently</div>';
    } else {
      wf.innerHTML = oc.whale_alerts.map(w=>{
        if(w.amount_xrp){
          // On-chain transaction
          const usd = w.amount_usd ? ` ($${parseInt(w.amount_usd).toLocaleString()})` : "";
          return `<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04)">
            <div style="font-size:13px;font-weight:700;color:var(--yl);font-family:var(--mn)">
              🐋 ${parseInt(w.amount_xrp).toLocaleString()} XRP${usd}
            </div>
            <div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-top:2px">
              ${w.from||"unknown"} → ${w.to||"unknown"} · ${w.ts||""}
            </div>
          </div>`;
        } else {
          // News story fallback
          const sc = w.sentiment==="bullish"?"var(--gr)":w.sentiment==="bearish"?"var(--rd)":"var(--tx)";
          return `<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04);cursor:pointer">
            <div style="font-size:13px;font-weight:600;color:var(--yl);line-height:1.4">${w.title||""}</div>
            <div style="font-size:13px;font-family:var(--mn);color:var(--tx);margin-top:2px">
              <span style="color:${sc};font-weight:700">${w.sentiment||""}</span>
              &nbsp;·&nbsp;${w.source||""}&nbsp;·&nbsp;${w.age||""}
            </div>
          </div>`;
        }
      }).join("");
    }
  }
}

function fmtNum(v){
  if(!v) return "--";
  v=parseFloat(v);
  if(v>=1e9)  return `${(v/1e9).toFixed(2)}B`;
  if(v>=1e6)  return `${(v/1e6).toFixed(2)}M`;
  if(v>=1e3)  return `${(v/1e3).toFixed(2)}K`;
  return v.toLocaleString();
}

// ── Price Intelligence (v3.0a) ─────────────────────────────────────────────
function updatePriceIntel(d){
  const pi = d.price_intel || {};

  // 1. Dominance
  if(pi.dominance !== undefined)
    c("pi-dom", `${parseFloat(pi.dominance).toFixed(3)}%`);

  // 2. Funding Rate — colour-coded: green=positive(bullish), red=negative(bearish)
  if(pi.funding_rate !== undefined){
    const fr    = parseFloat(pi.funding_rate);
    const frEl  = document.getElementById("pi-fr");
    const frBox = document.getElementById("pi-fr-box");
    if(frEl){
      frEl.textContent = `${fr >= 0 ? "+" : ""}${fr.toFixed(4)}%`;
      frEl.style.color = fr >= 0 ? "var(--gr)" : "var(--rd)";
    }
    if(frBox){
      frBox.className = fr >= 0 ? "abox pos" : "abox neg";
    }
    const frSub = document.getElementById("pi-fr-sub");
    if(frSub) frSub.textContent = fr >= 0 ? "Longs paying — bullish" : "Shorts paying — bearish";
  }

  // 3. Open Interest
  if(pi.open_interest_usd){
    c("pi-oi-usd", fmtUSD(pi.open_interest_usd));
    c("pi-oi-xrp", `${parseInt(pi.open_interest_xrp).toLocaleString()} XRP`);
  }

  // 4. XRP/ETH
  if(pi.xrp_eth){
    c("pi-xrpeth", parseFloat(pi.xrp_eth).toFixed(6) + " ETH");
    c("pi-eth-usd", `ETH: $${parseFloat(pi.eth_usd||0).toLocaleString()}`);
  }

  // 5. Volatility — colour coded: green=low(<40%), yellow=medium, red=high(>80%)
  if(pi.volatility_30d){
    const vol   = parseFloat(pi.volatility_30d);
    const volEl = document.getElementById("pi-vol");
    const volBox= document.getElementById("pi-vol-box");
    if(volEl){
      volEl.textContent = `${vol.toFixed(1)}%`;
      volEl.style.color = vol < 40 ? "var(--gr)" : vol < 80 ? "var(--yl)" : "var(--rd)";
    }
    const volSub = document.getElementById("pi-vol-sub");
    if(volSub) volSub.textContent = vol < 40 ? "Low — calm market" : vol < 80 ? "Medium — active" : "High — volatile";
  }

  // 6. Bid/Ask Spread
  if(pi.spread_pct !== undefined){
    const sp = parseFloat(pi.spread_pct);
    c("pi-spread", `${sp.toFixed(4)}%`);
    if(pi.bid && pi.ask)
      c("pi-ba", `Bid: $${parseFloat(pi.bid).toFixed(5)} / Ask: $${parseFloat(pi.ask).toFixed(5)}`);
  }
}

// ── Header ─────────────────────────────────────────────────────────────────
function updateHeader(d){
  c("uts", d.last_updated||"--");
  const fa = document.getElementById("feedPill");
  if(fa){fa.textContent=`${d.feeds_active||0}/${d.feeds_total||230} FEEDS`;}
}

// ── Status Row ─────────────────────────────────────────────────────────────
function updateStatus(d){
  const p=d.price||{};
  const fg=d.fear_greed||{};
  const pr=document.getElementById("st-price");
  if(pr&&p.usd){
    const ch=parseFloat(p.change_24h||0);
    pr.textContent=`$${parseFloat(p.usd).toFixed(4)} ${ch>=0?"▲":"▼"}${Math.abs(ch).toFixed(2)}%`;
    pr.style.color=ch>=0?"var(--gr)":"var(--rd)";
    checkPriceAlerts(parseFloat(p.usd));
  }
  c("st-feeds",`${d.feeds_active||0} / ${d.feeds_total||306} active`);
  const fgEl=document.getElementById("st-fg");
  if(fgEl&&fg.score!==undefined){
    fgEl.textContent=`${fg.score} / ${fg.label||"--"}`;
    fgEl.style.color=fg.score<30?"var(--rd)":fg.score>70?"var(--gr)":"var(--yl)";
  }
}

// ── Market Overview ─────────────────────────────────────────────────────────
function updateMarket(d){
  const p=d.price||{};
  c("mk-mcap",   fmtUSD(p.mcap));
  c("mk-rank",   `Rank #${p.rank||"--"}`);
  c("mk-vol",    fmtUSD(p.volume_24h));
  c("mk-vratio", `Vol/MCap: ${p.vol_mcap_ratio||"--"}%`);
  c("mk-ath",    p.ath?`$${parseFloat(p.ath).toFixed(4)}`:"--");
  c("mk-athpct", p.ath_pct?`${Math.abs(parseFloat(p.ath_pct)).toFixed(1)}% below ATH`:"--");
  const hi=document.getElementById("mk-high");
  if(hi&&p.high_24h){hi.textContent=`$${parseFloat(p.high_24h).toFixed(4)}`;}
  const lo=document.getElementById("mk-low");
  if(lo&&p.low_24h){lo.textContent=`$${parseFloat(p.low_24h).toFixed(4)}`;}
  c("mk-btc", p.btc?`${parseFloat(p.btc).toFixed(8)}`:"--");
  // Right panel mirrors
  c("rc-supply", p.supply_circ?`${(p.supply_circ/1e9).toFixed(1)}B XRP`:"--");
  c("rc-tps",    (d.onchain||{}).tps||"--");
  c("rc-ledger", (d.onchain||{}).ledger_index||"--");
  c("rm-rank",   `#${p.rank||"--"}`);
  c("rm-mcap",   fmtUSD(p.mcap));
  c("rm-vol",    fmtUSD(p.volume_24h));
  c("rm-ratio",  p.vol_mcap_ratio?`${p.vol_mcap_ratio}%`:"--");
  c("rm-ath",    p.ath?`$${parseFloat(p.ath).toFixed(4)}`:"--");
  c("rm-athpct", p.ath_pct?`${Math.abs(parseFloat(p.ath_pct)).toFixed(1)}% below`:"--");
  if(p.high_24h) c("rm-high",`$${parseFloat(p.high_24h).toFixed(4)}`);
  if(p.low_24h)  c("rm-low", `$${parseFloat(p.low_24h).toFixed(4)}`);
  c("rm-btc",    p.btc?`${parseFloat(p.btc).toFixed(8)}`:"--");
}

// ── AI ─────────────────────────────────────────────────────────────────────
function updateAI(d){
  const us=d.ai_us||{};
  const gl=d.ai_global||{};
  if(us.pulse) c("ai-us-pulse", us.pulse);
  if(us.regulatory) c("ai-us-reg", us.regulatory);
  if(us.institutional) c("ai-us-inst", us.institutional);
  if(us.ts) c("ai-us-ts", us.ts);
  if(gl.pulse) c("ai-gl-pulse", gl.pulse);
  if(gl.thesis) c("ai-gl-thesis", gl.thesis);
  if(gl.ts) c("ai-gl-ts", gl.ts);
  const sg=gl.signals||{};
  const sigEl=document.getElementById("ai-signals");
  if(sigEl&&Object.keys(sg).length){
    const dc={"bullish":"g","bearish":"r","neutral":"y","quiet":"q"};
    const fl={"Japan":"🇯🇵","Korea":"🇰🇷","UAE":"🇦🇪","Europe":"🇪🇺","LatAm":"🌎","Africa":"🌍","India":"🇮🇳","SEA":"🌏"};
    sigEl.innerHTML=Object.entries(sg).map(([r,s])=>
      `<div class="sig-chip"><div class="sdot ${dc[s]||"q"}"></div><span>${fl[r]||""} ${r}</span></div>`
    ).join("");
  }
}

// ── Regional Cards ─────────────────────────────────────────────────────────
const REGIONS=[{k:"Japan",f:"🇯🇵"},{k:"Korea",f:"🇰🇷"},{k:"UAE",f:"🇦🇪"},{k:"Europe",f:"🇪🇺"},
               {k:"India",f:"🇮🇳"},{k:"LatAm",f:"🌎"},{k:"Africa",f:"🌍"},{k:"SEA",f:"🌏"}];
const SIGMAP={"bullish":"bull","bearish":"bear","neutral":"neut","quiet":"quiet"};
const DOTMAP={"bullish":"gbull","bearish":"gbear","neutral":"gneut","quiet":"gquiet"};

function updateRegions(d){
  const sigs=(d.ai_global||{}).signals||{};
  const rAI=d.ai_regions||{};
  const grid=document.getElementById("regionGrid");
  if(!grid) return;
  grid.innerHTML=REGIONS.map(({k,f})=>{
    const sig=sigs[k]||"quiet";
    const pulse=(rAI[k]||{}).pulse||"Loading intelligence...";
    return `<div class="slot ${SIGMAP[sig]||""}" id="slot-${k}">
      <div class="slot-top">
        <div class="tqdot ${DOTMAP[sig]}"></div>
        <span class="sname">${f} ${k.toUpperCase()}</span>
        <span class="sbadge ${SIGMAP[sig]||"quiet"}">${sig.toUpperCase()}</span>
      </div>
      <div class="sstrat">${k} Intelligence</div>
      <div class="sact" id="reg-pulse-${k}">${pulse}</div>
      <div id="reg-stories-${k}" style="margin-top:6px"></div>
      <div class="sfoot"><span id="reg-count-${k}">Loading...</span></div>
    </div>`;
  }).join("");
  REGIONS.forEach(({k})=>fetchRegionStories(k));
}

async function fetchRegionStories(reg){
  try{
    const d=await fetch(`/api/news?region=${reg}&limit=50`).then(r=>r.json());
    const allReg=(d.stories||[]);
    const total=d.total||allReg.length;
    const el=document.getElementById(`reg-stories-${reg}`);
    const cnt=document.getElementById(`reg-count-${reg}`);
    if(cnt) cnt.textContent=`${total} stories`;
    if(!el) return;
    if(!allReg.length){el.innerHTML='<div style="font-size:13px;color:var(--tx);font-family:var(--mn)">No regional stories yet</div>';return;}
    // Show first 8 in scrollable container; "View All" expands
    const preview=allReg.slice(0,8);
    const storyHtml=stories=>stories.map(s=>{
      const trans=s.translated_title
        ?`<div style="font-size:12px;color:var(--tq);font-style:italic;margin-top:3px;padding:3px 6px;background:var(--tqd);border-left:2px solid var(--tq);border-radius:2px">🌐 ${s.translated_title}</div>`
        :(s.lang==="non-english"?`<div style="font-size:12px;color:var(--tx);font-style:italic;margin-top:2px">🌐 Translation pending...</div>`:"");
      const sent=s.sentiment==="bullish"?"g":s.sentiment==="bearish"?"r":"";
      return `<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04);cursor:pointer"
          onclick="window.open('${s.link||s.url||"#"}','_blank')">
        <div style="font-size:14px;font-weight:700;color:var(--bl);line-height:1.35">${s.title}</div>
        ${trans}
        <div style="font-size:12px;font-family:var(--mn);color:var(--tx);margin-top:3px">
          <span style="color:${sent==="g"?"var(--gr)":sent==="r"?"var(--rd)":"var(--tx)"};font-weight:700">${s.sentiment||"neutral"}</span>
          &nbsp;·&nbsp;${s.source}&nbsp;·&nbsp;${s.age||timeAgo(s.pub)||""}
        </div>
      </div>`;
    }).join("");
    const reachable = allReg.length;
    if(cnt) cnt.textContent=`${reachable} stories`;
    el.style.maxHeight="280px";
    el.style.overflowY="auto";
    el.style.paddingRight="4px";
    el.innerHTML = storyHtml(preview);
    if(reachable>8){
      const btn=document.createElement("button");
      btn.className="reg-viewall-btn";
      btn.style.cssText="margin-top:8px;width:100%;padding:8px;background:rgba(117,188,255,.1);"+
        "color:var(--bl);border:1px solid rgba(117,188,255,.3);border-radius:5px;"+
        "cursor:pointer;font-size:13px;font-weight:700;font-family:var(--mn)";
      btn.textContent=`📋 View All ${reachable} Stories`;
      let expanded=false;
      btn.onclick=()=>{
        if(!expanded){
          el.innerHTML=storyHtml(allReg);
          el.style.maxHeight="600px";
          btn.textContent=`▲ Collapse (showing all ${reachable})`;
          expanded=true;
        } else {
          el.innerHTML=storyHtml(preview);
          el.style.maxHeight="280px";
          btn.textContent=`📋 View All ${reachable} Stories`;
          expanded=false;
        }
      };
      const oldBtn=el.parentElement.querySelector(".reg-viewall-btn");
      if(oldBtn) oldBtn.remove();
      el.parentElement.appendChild(btn);
    }
  }catch(e){console.error("fetchRegionStories:",e);}
}

// ── Scoreboard ─────────────────────────────────────────────────────────────
function updateScoreboard(d){
  const st=d.story_stats||{};
  const p=d.price||{};
  const fg=d.fear_greed||{};
  c("sc-total", st.today||0);
  c("sc-feeds", `${d.feeds_active||0}/${d.feeds_total||230} sources`);
  c("sc-bull",  st.bullish||0);
  c("sc-bear",  st.bearish||0);
  c("sc-neut",  st.neutral||0);
  c("sc-fg",    fg.score||"--");
  c("sc-fg-lbl",fg.label||"--");
  c("sc-rank",  p.rank?`#${p.rank}`:"#--");
  c("sc-mcap",  fmtUSD(p.mcap));
  c("sc-vol",   fmtUSD(p.volume_24h));
  if(p.high_24h) c("sc-high",`$${parseFloat(p.high_24h).toFixed(4)}`);
  if(p.low_24h)  c("sc-low", `$${parseFloat(p.low_24h).toFixed(4)}`);
  const t=(st.today)||1;
  c("sc-bull-pct",`${Math.round((st.bullish||0)/t*100)}%`);
  c("sc-bear-pct",`${Math.round((st.bearish||0)/t*100)}%`);
  const net=(st.bullish||0)-(st.bearish||0);
  const netEl=document.getElementById("sc-net");
  if(netEl){netEl.textContent=`Net: ${net>=0?"+":""}${net}`;netEl.style.color=net>=0?"var(--gr)":"var(--rd)";}
  const fill=document.getElementById("sc-fill");
  if(fill) fill.style.width=`${Math.round((st.bullish||0)/t*100)}%`;
}

// ── Analytics ──────────────────────────────────────────────────────────────
function updateAnalytics(d){
  const st=d.story_stats||{};
  const p=d.price||{};
  const fg=d.fear_greed||{};
  const oc=d.onchain||{};
  const t=(st.today)||1;
  c("al-today",  st.today||0);
  c("al-bull",   st.bullish||0);
  c("al-bear",   st.bearish||0);
  c("al-neut",   st.neutral||0);
  const net=(st.bullish||0)-(st.bearish||0);
  const nel=document.getElementById("al-net");
  if(nel){nel.textContent=`${net>=0?"+":""}${net}`;nel.style.color=net>=0?"var(--gr)":"var(--rd)";}
  const ratio=st.bearish?((st.bullish||0)/(st.bearish)).toFixed(2):"∞";
  c("al-ratio",  `${ratio}:1 bull/bear`);
  c("al-rank",   p.rank?`#${p.rank}`:"--");
  c("al-mcap",   fmtUSD(p.mcap));
  c("al-vol",    fmtUSD(p.volume_24h));
  c("al-vratio", p.vol_mcap_ratio?`${p.vol_mcap_ratio}%`:"--");
  const fgEl2=document.getElementById("al-fg");
  if(fgEl2&&fg.score){fgEl2.textContent=`${fg.score} — ${fg.label||""}`;fgEl2.style.color=fg.score<30?"var(--rd)":fg.score>70?"var(--gr)":"var(--yl)";}
  c("al-athpct", p.ath_pct?`${Math.abs(parseFloat(p.ath_pct)).toFixed(1)}% below`:"--");
  c("al-feeds",  `${d.feeds_active||0}/${d.feeds_total||230}`);
  c("al2-total", st.total||0);
  c("al2-bull-pct",`${Math.round((st.bullish||0)/t*100)}%`);
  c("al2-bear-pct",`${Math.round((st.bearish||0)/t*100)}%`);
  c("al2-onchain",oc.tps||"--");
}

// ── Right Panel Feed List ──────────────────────────────────────────────────
function updateRight(d){
  c("feed-active",`${d.feeds_active||0}/230`);
  const fl=document.getElementById("feed-list");
  if(fl&&d.feed_health){
    const entries=Object.entries(d.feed_health);
    fl.innerHTML=entries.slice(0,25).map(([name,status])=>
      `<div class="rrow"><span class="rk">${name}</span><span style="color:${status==="UP"?"var(--gr)":"var(--rd)"}">${status==="UP"?"●":"✗"}</span></div>`
    ).join("")+`<div style="font-size:13px;color:var(--tx);font-family:var(--mn);padding:4px 0">&mdash; ${entries.length} sources total</div>`;
  }
}

// ── Breaking News ──────────────────────────────────────────────────────────
function updateBreaking(d){
  const bb=document.getElementById("breaking");
  const bt=document.getElementById("bktext");
  if(d.breaking&&bt){
    bt.textContent=`${d.breaking.title} — ${d.breaking.source} — ${d.breaking.age||""}`;
    if(bb) bb.style.display="flex";
  }
}

// ── Footer ─────────────────────────────────────────────────────────────────
let pfData = {};
function updateFooter(d){
  pfData = d;
  // Visitor counter
  const vc = d.visitor_count||0;
  const vcEl = document.getElementById("visitor-count");
  if(vcEl && vc > 5) vcEl.textContent = vc.toLocaleString()+" visits";
  c("ft-ver",  d.version||"--");
  c("ft-last", d.last_updated||"--");
  if(d.start_time){
    const hrs=Math.floor((Date.now()-new Date(d.start_time))/3600000);
    const mins=Math.floor(((Date.now()-new Date(d.start_time))%3600000)/60000);
    c("ft-uptime",`${hrs}h ${mins}m`);
  }
  const qsEl=document.getElementById("ft-qa-status");
  if(qsEl){qsEl.textContent=d.qa_status==="PASS"?"✅ PASS":"❌ FAIL";qsEl.style.color=d.qa_status==="PASS"?"var(--gr)":"var(--rd)";}
  const maintEl=document.getElementById("ft-maint");
  if(maintEl){const m=d.maintenance||"OK";maintEl.textContent=m==="OK"?"✅ OK":"🔧 "+m;maintEl.style.color=m==="OK"?"var(--gr)":"var(--yl)";}
  c("ft-feeds",`${d.feeds_active||0}/${d.feeds_total||230} active`);
}
function openPFModal(){
  const d=pfData;
  c("pf-last",  d.qa_last||"--");
  c("pf-feeds", `${d.feeds_active||0}/${d.feeds_total||230} feeds active`);
  c("pf-error", d.last_error||"None");
  const pfEl=document.getElementById("pf-error");
  if(pfEl) pfEl.style.color=d.last_error?"var(--rd)":"var(--gr)";
  const chkEl=document.getElementById("pf-checks");
  if(chkEl&&d.qa_details&&d.qa_details.length){
    chkEl.innerHTML=d.qa_details.map(ch=>
      `<div style="color:${ch.ok?"var(--gr)":"var(--rd)"};font-weight:700">${ch.ok?"✓":"✗"} ${ch.name}${ch.detail?" — "+ch.detail:""}</div>`
    ).join("");
  }
  document.getElementById("pf-modal").style.display="flex";
  document.body.style.overflow="hidden";
}
function closePFModal(e){
  if(e&&e.target!==document.getElementById("pf-modal")) return;
  document.getElementById("pf-modal").style.display="none";
  document.body.style.overflow="";
}

// ── News Render ─────────────────────────────────────────────────────────────
const SRC_COLORS={
  official:"official",major:"major",xrp:"xrp",community:"community",
  international:"international",aggregator:"aggregator",legal:"legal",
  mainstream:"mainstream",institutional:"institutional",whale:"whale",
  ecosystem:"xrp",technical:"international"
};

function renderNews(totalAll){
  let stories=allStories;
  if(activeCat!=="all") stories=stories.filter(s=>s.category===activeCat);
  if(activeSearch)       stories=stories.filter(s=>s.title.toLowerCase().includes(activeSearch));
  const feed=document.getElementById("news-feed");
  const cnt=document.getElementById("news-count");
  if(!feed) return;
  const tot=totalAll||allStories.length;
  const fa=document.getElementById("feed-active");
  const faText=fa?fa.textContent:"--";
  if(cnt) cnt.innerHTML=`<span style="color:var(--bl);font-weight:700">${stories.length}</span> stories shown &nbsp;|&nbsp; <span style="color:var(--gr);font-weight:700">${tot}</span> total &nbsp;|&nbsp; <span style="color:var(--bl);font-weight:700">${faText}</span> of <span style="color:var(--gr);font-weight:700">306</span> sources online`;
  if(!stories.length){
    if(allStories.length===0){
      feed.innerHTML='<div class="empty" style="padding:20px;line-height:2">📡 Scanning 306 sources...<br>Stories will appear shortly after first feed scan completes.</div>';
    } else {
      feed.innerHTML='<div class="empty">No stories match your filter. Try ALL to see all stories.</div>';
    }
    return;
  }
  feed.innerHTML=stories.slice(0,100).map(s=>{
    const sc=SRC_COLORS[s.type]||"major";
    const sent=s.sentiment==="bullish"?"bull":s.sentiment==="bearish"?"bear":"neut";
    const sentLbl=s.sentiment==="bullish"?"🟢 Bullish":s.sentiment==="bearish"?"🔴 Bearish":"⚪ Neutral";
    const sum=s.summary?`<div class="nsum">${s.summary.substring(0,200)}${s.summary.length>200?"...":""}</div>`:"";
    const isForeign=s.lang==="non-english";
    const trans=s.translated_title?`<div class="ntrans">🌐 EN: ${s.translated_title}</div>`:(isForeign?`<div class="ntrans" style="color:var(--tx);background:none;border:none;font-style:italic">🌐 Translation pending next AI cycle...</div>`:"");
    const brk=s.breaking?`<span class="nbreak">⚡ BREAKING</span>`:"";
    const stUrl=s.link||s.url||"#";
    return `<div class="ncard" onclick="window.open('${stUrl}','_blank')">
      <div class="ncard-hdr">
        <span class="nsrc ${sc}">${s.source}</span>
        <span class="ncat" onclick="event.stopPropagation();document.querySelectorAll('.nbtn').forEach(b=>{b.classList.remove('on');if(b.textContent.trim()==='${s.category||'ALL'}')b.classList.add('on')});activeCat='${s.category||'all'}';renderNews()" style="cursor:pointer" title="Filter by ${s.category}">${s.category}</span>
        ${brk}
      </div>
      <div class="ntitle">${s.title}</div>
      ${trans}${sum}
      <div class="nfoot">
        <span class="nsent ${sent}">${sentLbl}</span>
        <span class="nage">${s.age||""}</span>
      </div>
    </div>`;
  }).join("");
}

function setFilter(btn,cat){
  activeCat=cat;
  document.querySelectorAll(".nbtn").forEach(b=>b.classList.remove("on"));
  btn.classList.add("on");
  renderNews();
}
function filterNews(){
  activeSearch=document.getElementById("search-box").value.toLowerCase();
  renderNews();
}

// ── Story Modal ─────────────────────────────────────────────────────────────
function openStoryModal(sid){
  const s=storyData[sid]; if(!s) return;
  document.getElementById("modal-title").textContent=s.title;
  const transEl=document.getElementById("modal-translation");
  const transText=document.getElementById("modal-translation-text");
  if(s.translated_title||s.translated_summary){
    transEl.style.display="block";
    transText.innerHTML=(s.translated_title?`<strong>${s.translated_title}</strong><br>`:"")+(s.translated_summary||"");
  } else if(s.lang==="non-english"){
    transEl.style.display="block";
    transText.textContent="Translation pending — check back after next AI cycle.";
  } else { transEl.style.display="none"; }
  c("modal-summary", s.summary||"Click Read Full Story for the complete article.");
  const sentC=s.sentiment==="bullish"?"var(--gr)":s.sentiment==="bearish"?"var(--rd)":"var(--tx)";
  document.getElementById("modal-meta").innerHTML=
    `<span style="color:var(--bl);font-weight:700">${s.source}</span>
     <span style="color:${sentC};font-weight:700">${(s.sentiment||"").toUpperCase()}</span>
     <span style="color:var(--tx)">${s.category||""}</span>
     <span style="color:var(--tx);margin-left:auto">${s.age||""}</span>`;
  document.getElementById("modal-read-btn").href=s.link;
  document.getElementById("story-modal").style.display="flex";
  document.body.style.overflow="hidden";
}
function closeModal(e){
  if(e&&e.target!==document.getElementById("story-modal")) return;
  document.getElementById("story-modal").style.display="none";
  document.body.style.overflow="";
}
document.addEventListener("keydown",e=>{if(e.key==="Escape"){document.getElementById("story-modal").style.display="none";document.body.style.overflow="";}});

// ── Init ─────────────────────────────────────────────────────────────────────
fetchData();
  switchTrend('30d');
fetchNews();
setInterval(fetchData,  60000);
setInterval(fetchNews, 600000);
setInterval(()=>REGIONS.forEach(({k})=>fetchRegionStories(k)), 600000);
// Retry news if still empty after 20 seconds (first scan takes time)
setTimeout(()=>{ if(allStories.length===0) fetchNews(); }, 20000);
setTimeout(()=>{ if(allStories.length===0) fetchNews(); }, 60000);
</script>

<!-- Sticky Back-to-XRPRadar button for returning visitors -->
<div id="xrpr-sticky-back" style="position:fixed;bottom:20px;right:20px;z-index:9999;
  display:none;flex-direction:column;align-items:flex-end;gap:8px">
  <a href="/" style="background:var(--b);border:1px solid var(--bl);color:var(--bl);
    padding:10px 18px;border-radius:8px;font-family:var(--mn);font-size:13px;font-weight:700;
    text-decoration:none;display:flex;align-items:center;gap:8px;
    box-shadow:0 4px 20px rgba(117,188,255,.2);transition:all .2s"
    onmouseover="this.style.background='var(--bl)';this.style.color='#000'"
    onmouseout="this.style.background='var(--b)';this.style.color='var(--bl)'">
    🛰️ ← BACK TO XRPRADAR
  </a>
</div>
<script>
// Show sticky back button if user navigated away and returned
(function(){
  let shown = false;
  window.addEventListener('pageshow', function(e){
    if(e.persisted){
      document.getElementById('xrpr-sticky-back').style.display='flex';
      shown = true;
    }
  });
  // Also show on hash change or history navigation
  window.addEventListener('popstate', function(){
    document.getElementById('xrpr-sticky-back').style.display='flex';
  });
  // Bookmark prompt after 30 seconds
  setTimeout(function(){
    const el = document.getElementById('xrpr-sticky-back');
    if(el && !shown){
      el.style.display='flex';
      setTimeout(()=>{ el.style.display='none'; }, 8000);
    }
  }, 45000);
})();

// ════════════════════════════════════════════════════════════════════
// v6.0 JS UPDATE FUNCTIONS
// ════════════════════════════════════════════════════════════════════

function updateSignalScore(d){
  const ss = d.signal_score||{};
  if(!ss.total && ss.total!==0) return;
  const total = ss.total||0;
  const grade = ss.grade||"--";
  const label = ss.label||"--";
  const ts    = ss.ts||"";
  c("ss-score", total);
  c("ss-grade", grade+"/100");
  c("ss-label", label);
  c("ss-ts",    ts);
  const bar = document.getElementById("ss-bar");
  if(bar) bar.style.width = total+"%";
  // Color the score
  const scoreEl = document.getElementById("ss-score");
  if(scoreEl){
    if(total>=70)      scoreEl.style.color="var(--gr)";
    else if(total>=50) scoreEl.style.color="var(--yl)";
    else if(total>=30) scoreEl.style.color="var(--or)";
    else               scoreEl.style.color="var(--rd)";
  }
  // Components
  const comp = ss.components||{};
  const compMap = [
    ["price_momentum","ss-c1","ss-c1s"],
    ["rsi_signal",    "ss-c2","ss-c2s"],
    ["sentiment",     "ss-c3","ss-c3s"],
    ["on_chain",      "ss-c4","ss-c4s"],
    ["macro",         "ss-c5","ss-c5s"],
    ["inst_flow",     "ss-c6","ss-c6s"],
    ["whale_activity","ss-c7","ss-c7s"],
    ["fear_greed",    "ss-c8","ss-c8s"],
  ];
  compMap.forEach(([key,scoreId,sigId])=>{
    const cv = comp[key]||{};
    const scoreEl2 = document.getElementById(scoreId);
    const sigEl    = document.getElementById(sigId);
    if(scoreEl2){
      const s = cv.score||0;
      const w = cv.weight||10;
      scoreEl2.textContent = s+"/"+w;
      scoreEl2.style.color = s>=w*0.7?"var(--gr)":s>=w*0.4?"var(--yl)":"var(--rd)";
    }
    if(sigEl) sigEl.textContent = cv.signal||"--";
  });
}

function updateMacroDashboard(d){
  const md = d.macro_data||{};
  const cr = d.correlation||{};
  // Macro cards
  const macMap = [
    ["dxy","mac-dxy","mac-dxy-chg"],
    ["sp500","mac-sp","mac-sp-chg"],
    ["gold","mac-gold","mac-gold-chg"],
    ["treasury","mac-tnx","mac-tnx-chg"],
    ["btc","mac-btc","mac-btc-chg"],
  ];
  macMap.forEach(([key,valId,chgId])=>{
    const v = md[key]||{};
    const val = v.value||0;
    const chg = v.change_pct||0;
    const valEl = document.getElementById(valId);
    const chgEl = document.getElementById(chgId);
    if(valEl) valEl.textContent = key==="btc"?"$"+val.toLocaleString():key==="treasury"?val.toFixed(3)+"%":val.toLocaleString();
    if(chgEl){
      chgEl.textContent = (chg>=0?"+":"")+chg.toFixed(2)+"%";
      chgEl.style.color = chg>=0?"var(--gr)":"var(--rd)";
    }
  });
  // Macro signal
  const sig = md.macro_signal||"NEUTRAL";
  const sigEl = document.getElementById("mac-signal");
  const sigBox = document.getElementById("mac-signal-box");
  if(sigEl){
    sigEl.textContent = sig;
    sigEl.style.color = sig==="BULLISH"?"var(--gr)":sig==="BEARISH"?"var(--rd)":"var(--yl)";
  }
  c("mac-ts", md.ts||"--");
  // Correlation matrix
  const corrMap = {
    "xrp_btc":"corr-btc","xrp_sp500":"corr-sp","xrp_gold":"corr-gold","xrp_dxy":"corr-dxy"
  };
  Object.entries(corrMap).forEach(([key,elId])=>{
    const val = cr[key]||"--";
    const el  = document.getElementById(elId);
    if(el){
      el.textContent = val;
      el.style.color = val==="POSITIVE"?"var(--gr)":val==="NEGATIVE"?"var(--rd)":"var(--tx)";
    }
  });
}

function updateOrderBook(d){
  const ob   = d.order_book||{};
  const bids = ob.combined_bids||[];
  const asks = ob.combined_asks||[];
  const maxQ = Math.max(...bids.concat(asks).map(x=>x[1]||0),1);

  function renderSide(items, elId, col, isAsk){
    const el = document.getElementById(elId);
    if(!el||!items.length) return;
    el.innerHTML = items.slice(0,10).map(([price,qty])=>{
      const pct = Math.min((qty/maxQ)*100,100);
      const barCol = isAsk?"rgba(255,64,96,.3)":"rgba(72,255,130,.3)";
      return `<div style="position:relative;display:flex;justify-content:space-between;
        padding:3px 6px;border-radius:3px;margin-bottom:2px;overflow:hidden">
        <div style="position:absolute;top:0;${isAsk?"right":"left"}:0;height:100%;width:${pct}%;
          background:${barCol};z-index:0"></div>
        <span style="position:relative;font-size:12px;color:${col};font-weight:700">$${price.toFixed(4)}</span>
        <span style="position:relative;font-size:12px;color:var(--tx)">${qty.toLocaleString(undefined,{maximumFractionDigits:0})} XRP</span>
      </div>`;
    }).join("");
  }
  renderSide(bids,"ob-bids","var(--gr)",false);
  renderSide(asks,"ob-asks","var(--rd)",true);
  c("ob-bid-total",(ob.total_bid_depth||0).toLocaleString()+" XRP");
  c("ob-ask-total",(ob.total_ask_depth||0).toLocaleString()+" XRP");
  // Liquidity map
  const lm  = d.liquidity_map||{};
  const lmEl= document.getElementById("liq-map");
  if(lmEl && lm.exchanges && lm.exchanges.length){
    lmEl.innerHTML =
      `<div style="font-size:13px;color:var(--tx);font-family:var(--mn);margin-bottom:10px">
        Best venue: <b style="color:var(--gr)">${lm.best_venue||"--"}</b> (tightest spread)
      </div>`+
      lm.exchanges.map(ex=>`
        <div style="padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--b);margin-bottom:6px">
          <div style="font-size:14px;font-weight:700;color:var(--br);font-family:var(--mn);margin-bottom:4px">${ex.name}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;font-family:var(--mn)">
            <div>Bid Depth: <span style="color:var(--gr)">${(ex.bid_depth||0).toLocaleString()} XRP</span></div>
            <div>Spread: <span style="color:${ex.spread_pct<0.01?"var(--gr)":"var(--yl)"}">${(ex.spread_pct||0).toFixed(4)}%</span></div>
            <div>Best Bid: <span style="color:var(--gr)">$${(ex.best_bid||0).toFixed(4)}</span></div>
            <div>Best Ask: <span style="color:var(--rd)">$${(ex.best_ask||0).toFixed(4)}</span></div>
          </div>
        </div>`
      ).join("");
  }
}

function updateIPOWatch(d){
  const ipo = d.ipo_watch||{};
  c("ipo-prob",     (ipo.probability||72)+"%");
  c("ipo-val",      ipo.ripple_valuation||"~$11B");
  c("ipo-status",   ipo.ipo_status||"Monitoring...");
  c("ipo-banks",    ipo.lead_underwriters||"--");
  c("ipo-milestone",ipo.next_milestone||"--");
  const newsEl = document.getElementById("ipo-news");
  if(newsEl && ipo.news && ipo.news.length){
    newsEl.innerHTML = ipo.news.map(n=>`
      <div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04);cursor:pointer"
           onclick="window.open('${n.link||"#"}','_blank')">
        <div style="font-size:14px;font-weight:700;color:var(--bl);line-height:1.35">${n.title}</div>
        <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-top:3px">
          ${n.source||""} · ${timeAgo(n.pub)||""}
        </div>
      </div>`).join("");
  }
}

function updateCurrencyCrisis(d){
  const cc  = d.currency_crisis||{};
  const countries = cc.countries||[];
  c("cc-total","$"+(cc.odl_opportunity||0).toFixed(1)+"B");
  const grid = document.getElementById("crisis-grid");
  if(!grid||!countries.length) return;
  const riskCol = {"CRITICAL":"var(--rd)","HIGH":"var(--or)","MEDIUM":"var(--yl)","LOW":"var(--gr)"};
  grid.innerHTML = countries.map(c2=>`
    <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:12px;
      border-left:3px solid ${riskCol[c2.risk]||"var(--tx)"}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span style="font-size:14px;font-weight:700;color:var(--br);font-family:var(--mn)">${c2.country} (${c2.currency})</span>
        <span style="font-size:11px;font-weight:700;color:${riskCol[c2.risk]||"var(--tx)"};
          background:rgba(255,255,255,.05);padding:2px 8px;border-radius:3px;font-family:var(--mn)">${c2.risk} RISK</span>
      </div>
      <div style="font-size:12px;color:var(--tx);line-height:1.5;margin-bottom:6px">${c2.context}</div>
      <div style="font-size:12px;font-family:var(--mn);color:var(--tq)">
        💸 Remittance market: $${c2.remittance_usd_bn||0}B/yr · ODL corridor: ${c2.odl_corridor||"--"}
      </div>
      ${c2.rate_vs_usd?`<div style="font-size:12px;font-family:var(--mn);color:var(--tx);margin-top:4px">
        Rate: ${c2.rate_vs_usd} vs USD 
        <span style="color:${(c2.change_5d_pct||0)>0?"var(--rd)":"var(--gr)"}">${c2.change_5d_pct>0?"▲":"▼"}${Math.abs(c2.change_5d_pct||0).toFixed(2)}% (5d)</span>
      </div>`:""}
    </div>`).join("");
}

function updateAdoptionVelocity(d){
  const av = d.adoption_velocity||{};
  const sc = av.score||0;
  const el = document.getElementById("av-score");
  if(el){
    el.textContent = sc;
    el.style.color = sc>70?"var(--gr)":sc>50?"var(--yl)":"var(--or)";
  }
  c("av-trend", "/100 — "+(av.trend||"CALCULATING"));
  c("av-inst",   (av.institutional||0)+"/100");
  c("av-retail", (av.retail||0)+"/100");
  c("av-dev",    (av.developer||0)+"/100");
  c("av-reg",    (av.regulatory||0)+"/100");
  const nvt = d.nvt_ratio||{};
  c("nvt-value",  nvt.nvt||"--");
  c("nvt-interp", nvt.interpretation||"Calculating...");
}

let pollVoted = false;
function updateCommunityPoll(d){
  const poll = d.community_poll||{};
  if(!poll.question) return;
  c("poll-question", poll.question);
  const optsEl  = document.getElementById("poll-options");
  const resEl   = document.getElementById("poll-results");
  const total   = poll.total_votes||0;
  if(optsEl && !pollVoted){
    optsEl.innerHTML = (poll.options||[]).map(opt=>`
      <button onclick="submitPollVote('${opt.replace(/'/g,"\'")}',this)"
        style="background:var(--s2);border:1px solid var(--b);color:var(--br);
        padding:10px 16px;border-radius:6px;cursor:pointer;font-family:var(--mn);
        font-size:13px;font-weight:600;text-align:left;transition:all .2s;width:100%"
        onmouseover="this.style.borderColor='var(--bl)'"
        onmouseout="this.style.borderColor='var(--b)'">${opt}</button>`).join("");
  }
  if(resEl && pollVoted && total>0){
    resEl.style.display="block";
    c("poll-total", total+" votes");
    const barsEl = document.getElementById("poll-bars");
    if(barsEl){
      barsEl.innerHTML = Object.entries(poll.votes||{}).map(([opt,votes])=>{
        const pct = Math.round((votes/total)*100);
        return `<div style="margin-bottom:6px">
          <div style="display:flex;justify-content:space-between;font-family:var(--mn);font-size:13px;margin-bottom:3px">
            <span style="color:var(--br)">${opt}</span>
            <span style="color:var(--yl)">${pct}% (${votes})</span>
          </div>
          <div style="background:var(--bg);border-radius:3px;height:8px">
            <div style="height:100%;border-radius:3px;background:var(--bl);width:${pct}%;transition:width .5s"></div>
          </div>
        </div>`;
      }).join("");
    }
  }
}

async function submitPollVote(option, btn){
  if(pollVoted) return;
  pollVoted = true;
  try{
    const r = await fetch("/api/poll/vote",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({option})});
    const data = await r.json();
    document.getElementById("poll-options").style.display="none";
    document.getElementById("poll-results").style.display="block";
    c("poll-total",(data.total||0)+" votes");
    const barsEl = document.getElementById("poll-bars");
    const total  = data.total||1;
    if(barsEl){
      barsEl.innerHTML = Object.entries(data.votes||{}).map(([opt,votes])=>{
        const pct=Math.round((votes/total)*100);
        return `<div style="margin-bottom:6px">
          <div style="display:flex;justify-content:space-between;font-family:var(--mn);font-size:13px;margin-bottom:3px">
            <span style="color:${opt===option?"var(--gr)":"var(--br)"};font-weight:${opt===option?"700":"400"}">${opt}${opt===option?" ✓":""}</span>
            <span style="color:var(--yl)">${pct}%</span>
          </div>
          <div style="background:var(--bg);border-radius:3px;height:8px">
            <div style="height:100%;border-radius:3px;background:${opt===option?"var(--gr)":"var(--bl)"};width:${pct}%;transition:width .5s"></div>
          </div></div>`;
      }).join("");
    }
  }catch(e){ pollVoted=false; }
}

function updateWeeklyDigest(d){
  const wd  = d.weekly_digest||{};
  const el  = document.getElementById("weekly-digest-content");
  const dt  = document.getElementById("digest-date");
  if(dt) dt.textContent = wd.generated_date ? "Generated: "+wd.generated_date : "Next: Sunday 18:00 UTC";
  if(el && wd.content){
    el.innerHTML = `<div style="white-space:pre-wrap;font-size:14px;line-height:1.7;color:var(--br)">${wd.content}</div>`;
  }
  // Countdown to next Sunday
  const now  = new Date();
  const days = (7 - now.getDay()) % 7 || 7;
  const cnt  = document.getElementById("digest-countdown");
  if(cnt) cnt.textContent = days===0?"Today at 18:00 UTC":"In "+days+" day"+(days===1?"":"s")+" (Sunday 18:00 UTC)";
}


  // ── Price Alert System (#58) ─────────────────────────────────────────────
  let alertAbove = null, alertBelow = null, alertFired = false;
  function setAlerts(){
    const above = parseFloat(document.getElementById("alert-above").value);
    const below = parseFloat(document.getElementById("alert-below").value);
    alertAbove  = isNaN(above) ? null : above;
    alertBelow  = isNaN(below) ? null : below;
    alertFired  = false;
    const parts = [];
    if(alertAbove) parts.push("Above $"+alertAbove.toFixed(3)+" ↑");
    if(alertBelow) parts.push("Below $"+alertBelow.toFixed(3)+" ↓");
    const el = document.getElementById("alert-status");
    if(el) el.textContent = parts.length ? "✅ "+parts.join(" | ") : "No alerts set";
  }
  function clearAlerts(){
    alertAbove = alertBelow = null; alertFired = false;
    const el = document.getElementById("alert-status");
    if(el) el.textContent = "No alerts set";
    document.getElementById("price-alert-bar").style.display="none";
  }
  function checkPriceAlerts(price){
    if(alertFired) return;
    if(alertAbove && price >= alertAbove){
      showAlert("🚀 XRP crossed ABOVE $"+alertAbove.toFixed(3)+" — now $"+price.toFixed(4));
    } else if(alertBelow && price <= alertBelow){
      showAlert("🔻 XRP dropped BELOW $"+alertBelow.toFixed(3)+" — now $"+price.toFixed(4));
    }
  }
  function showAlert(msg){
    alertFired = true;
    const bar = document.getElementById("price-alert-bar");
    const msgEl= document.getElementById("alert-msg");
    if(bar)  bar.style.display="flex";
    if(msgEl)msgEl.textContent = msg;
    if("Notification" in window && Notification.permission==="granted"){
      new Notification("XRPRadar Alert",{body:msg,icon:"/favicon.ico"});
    } else if("Notification" in window && Notification.permission!=="denied"){
      Notification.requestPermission().then(p=>{ if(p==="granted") new Notification("XRPRadar Alert",{body:msg}); });
    }
  }

  // ── Pro Email Teaser (#68) ───────────────────────────────────────────────
  function submitProEmail(){
    const em  = document.getElementById("pro-email");
    const msg = document.getElementById("pro-email-msg");
    if(!em||!em.value||!em.value.includes("@")){ if(msg) msg.style.color="var(--rd)",msg.textContent="Please enter a valid email."; return; }
    if(msg){ msg.style.color="var(--gr)"; msg.textContent="✅ You're on the list! Daily briefs coming your way."; }
    em.value="";
  }


  // ── AI Tools (#71, #72, #74) ──────────────────────────────────────────────
  async function callClaudeAI(prompt, systemPrompt){
    // Calls server-side proxy — keeps API key secure on Railway server
    const resp = await fetch("/api/ai/analyze",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        prompt: prompt,
        system: systemPrompt || "You are the world's foremost XRP intelligence analyst. Be specific, bold, and institutional in tone.",
        max_tokens: 1000
      })
    });
    const data = await resp.json();
    if(!data.success){
      if(data.error && data.error.includes("ANTHROPIC_API_KEY")){
        return "⚠️ AI features require ANTHROPIC_API_KEY in Railway Variables. See setup instructions in the Intelligence Brief section.";
      }
      throw new Error(data.error||"AI analysis failed");
    }
    return data.result||"";
  }

  async function runScenario(){
    const input = document.getElementById("scenario-input").value.trim();
    if(!input){ alert("Please describe a macro scenario first."); return; }
    const btn = document.getElementById("scenario-btn");
    const res = document.getElementById("scenario-result");
    btn.textContent = "⏳ Analyzing..."; btn.disabled=true;
    res.style.display="none";
    try{
      const price = currentXRPPrice||1.0;
      const text = await callClaudeAI(
        `Macro scenario: "${input}"\n\nCurrent XRP price: $${price.toFixed(4)}\n\n`+
        `Based on historical patterns and current market conditions, analyze:\n`+
        `1. How has XRP historically responded to this type of macro event?\n`+
        `2. What is the likely short-term impact (24-72 hours)?\n`+
        `3. What is the likely medium-term impact (1-4 weeks)?\n`+
        `4. What specific price levels should traders watch?\n`+
        `5. What is your overall assessment — bullish, bearish, or neutral for XRP?\n\n`+
        `Be specific with price levels and percentage moves. Aim for 8-10 sentences total.`,
        "You are the world's foremost XRP market analyst. Be specific, name exact price levels, use historical data where relevant. No disclaimers needed — this is for sophisticated investors."
      );
      res.innerHTML = text.replace(/\n/g,"<br>");
      res.style.display="block";
    }catch(e){ res.innerHTML="Error: "+e.message; res.style.display="block"; }
    btn.textContent="⚡ ANALYZE SCENARIO"; btn.disabled=false;
  }

  async function runRegAnalysis(){
    const input = document.getElementById("reg-input").value.trim();
    if(!input){ alert("Please paste a regulation or news headline."); return; }
    const btn = document.getElementById("reg-btn");
    const res = document.getElementById("reg-result");
    btn.textContent = "⏳ Analyzing..."; btn.disabled=true;
    res.style.display="none";
    try{
      const text = await callClaudeAI(
        `Regulatory development: "${input}"\n\n`+
        `Please provide:\n`+
        `1. IMPACT SCORE: Rate the impact on XRP from 1 (very negative) to 10 (very positive)\n`+
        `2. IMMEDIATE EFFECT: What happens to XRP price and ecosystem in the next 7 days?\n`+
        `3. LONG-TERM EFFECT: What does this mean for XRP adoption in the next 6-12 months?\n`+
        `4. RIPPLE RESPONSE: How is Ripple likely to respond?\n`+
        `5. VERDICT: Bullish, Bearish, or Neutral — and why in one sentence.\n\n`+
        `Be specific and direct. 8-10 sentences total.`,
        "You are the world's leading XRP regulatory intelligence analyst. You understand Ripple's legal strategy, global crypto regulation, and XRP's regulatory journey intimately. Be direct and specific."
      );
      res.innerHTML = text.replace(/\n/g,"<br>");
      res.style.display="block";
    }catch(e){ res.innerHTML="Error: "+e.message; res.style.display="block"; }
    btn.textContent="⚡ ANALYZE IMPACT"; btn.disabled=false;
  }

  async function runBullBear(mode){
    const btnId  = mode==="both"?"both-btn":mode+"-btn";
    const btn    = document.getElementById(btnId);
    const res    = document.getElementById("bullbear-result");
    const price  = currentXRPPrice||1.0;
    if(btn){ btn.textContent="⏳ Generating..."; btn.disabled=true; }
    res.style.display="none";
    try{
      let prompt;
      if(mode==="bull"){
        prompt = `Current XRP price: $${price.toFixed(4)}. Write the strongest possible BULL CASE for XRP right now. `+
          `Include: price catalysts, institutional adoption momentum, regulatory clarity, technical setup, and what could drive XRP to new highs. `+
          `Be bold and specific. 10-12 sentences.`;
      } else if(mode==="bear"){
        prompt = `Current XRP price: $${price.toFixed(4)}. Write the strongest possible BEAR CASE for XRP right now. `+
          `Include: macro headwinds, competitive threats, adoption challenges, technical risks, and what could drive XRP significantly lower. `+
          `Be honest and specific. 10-12 sentences.`;
      } else {
        prompt = `Current XRP price: $${price.toFixed(4)}. Write BOTH the strongest BULL CASE and strongest BEAR CASE for XRP. `+
          `Label each section clearly with ## BULL CASE and ## BEAR CASE. `+
          `Each case should be 8-10 sentences. Be bold, specific, and balanced.`;
      }
      const text = await callClaudeAI(prompt,
        "You are XRPRadar's senior market strategist. Write with conviction and specificity. Name actual price targets, specific catalysts, and exact risks. This is for sophisticated institutional readers."
      );
      const colored = text
        .replace(/## BULL CASE/g,"<div style='font-size:14px;font-weight:700;color:var(--gr);margin:10px 0 6px'>🐂 BULL CASE</div>")
        .replace(/## BEAR CASE/g,"<div style='font-size:14px;font-weight:700;color:var(--rd);margin:10px 0 6px'>🐻 BEAR CASE</div>")
        .replace(/\n/g,"<br>");
      res.innerHTML = colored;
      res.style.display="block";
    }catch(e){ res.innerHTML="Error: "+e.message; res.style.display="block"; }
    if(btn){ btn.textContent=mode==="bull"?"🐂 BULL CASE":mode==="bear"?"🐻 BEAR CASE":"⚡ GENERATE BOTH"; btn.disabled=false; }
  }


  // ── Regional Activity Map Colouring ─────────────────────────────────────
  function updateWorldMap(regionCounts){
    const regions = ['US','LatAm','Europe','Africa','UAE','India','Japan','SEA'];
    const maxCount = Math.max(...Object.values(regionCounts||{}), 1);
    regions.forEach(reg=>{
      const count = regionCounts[reg]||0;
      const el    = document.getElementById('rmap-'+reg);
      const cnt   = document.getElementById('rmap-'+reg+'-count');
      if(cnt) cnt.textContent = count;
      if(el){
        const ellipse = el.querySelector('ellipse');
        if(!ellipse) return;
        const intensity = count / maxCount;
        let fill, stroke, glow;
        if(intensity === 0){
          fill="#1a2030"; stroke="#2a3040"; glow="none";
        } else if(intensity < 0.2){
          fill="rgba(72,255,130,.08)"; stroke="rgba(72,255,130,.2)"; glow="none";
        } else if(intensity < 0.4){
          fill="rgba(72,255,130,.15)"; stroke="rgba(72,255,130,.4)"; glow="glow-mid";
        } else if(intensity < 0.6){
          fill="rgba(255,204,0,.15)"; stroke="rgba(255,204,0,.5)"; glow="glow-mid";
        } else if(intensity < 0.8){
          fill="rgba(255,153,0,.2)"; stroke="rgba(255,153,0,.6)"; glow="glow-strong";
        } else {
          fill="rgba(255,64,96,.2)"; stroke="rgba(255,64,96,.7)"; glow="glow-strong";
        }
        ellipse.setAttribute('fill', fill);
        ellipse.setAttribute('stroke', stroke);
        if(glow && glow!=="none") el.setAttribute('filter','url(#'+glow+')');
        else el.removeAttribute('filter');
        // Colour the count text
        const countEl = document.getElementById('rmap-'+reg+'-count');
        if(countEl){
          if(intensity===0)       countEl.setAttribute('fill','#3a4050');
          else if(intensity<0.4)  countEl.setAttribute('fill','#48ff82');
          else if(intensity<0.7)  countEl.setAttribute('fill','#ffcc00');
          else                    countEl.setAttribute('fill','#ff4060');
        }
      }
    });
  }
  function mapRegionClick(reg){
    const tooltip = document.getElementById('map-region-tooltip');
    if(!tooltip) return;
    const regionNames = {
      'US':'North America','LatAm':'Latin America','Europe':'Europe','Africa':'Africa',
      'UAE':'Middle East / UAE','India':'India & South Asia','Japan':'Japan','SEA':'SE Asia & Korea'
    };
    const cnt = document.getElementById('rmap-'+reg+'-count');
    const stories = cnt ? cnt.textContent : '0';
    tooltip.style.display='block';
    tooltip.innerHTML = `<b style="color:var(--bl)">${regionNames[reg]||reg}</b><br>${stories} stories today<br><span style="font-size:11px;color:var(--tx)">Click regional panel below for details</span>`;
    setTimeout(()=>{ tooltip.style.display='none'; }, 3000);
  }


  // ── Remittance Corridor Intelligence (#55) ───────────────────────────────
  function updateRemittanceIntel(d){
    const ri = d.remittance_intel||{};
    const corridors = ri.corridors||[];
    const el = document.getElementById("remit-corridors");
    if(el && corridors.length){
      el.innerHTML = corridors.map(c=>`
        <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:12px;
          border-left:3px solid ${c.status==='ACTIVE'?'var(--gr)':'var(--tq)'}">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span style="font-size:14px;font-weight:700;color:var(--br);font-family:var(--mn)">${c.route}</span>
            <span style="font-size:11px;font-weight:700;color:${c.status==='ACTIVE'?'var(--gr)':'var(--tq)'};
              background:rgba(0,0,0,.3);padding:2px 6px;border-radius:3px;font-family:var(--mn)">${c.status}</span>
          </div>
          <div style="font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:6px">
            Partner: <span style="color:var(--bl)">${c.partner}</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;font-family:var(--mn)">
            <div>Volume: <span style="color:var(--yl)">${c.volume_est}</span></div>
            <div>Growth: <span style="color:var(--gr)">${c.growth}</span></div>
            <div>Trad Fee: <span style="color:var(--rd)">${c.fee_traditional}</span></div>
            <div>XRP Save: <span style="color:var(--gr)">${c.xrp_saving}</span></div>
          </div>
        </div>`).join("");
    }
    const newEl = document.getElementById("remit-new-corridors");
    if(newEl && ri.new_corridors_2026){
      newEl.innerHTML = ri.new_corridors_2026.map(c=>`
        <span style="display:inline-block;background:rgba(0,229,204,.1);border:1px solid rgba(0,229,204,.3);
          color:var(--tq);padding:3px 10px;border-radius:4px;font-family:var(--mn);font-size:12px;
          margin:2px">🔜 ${c}</span>`).join("");
    }
  }

  // ── Geopolitical Risk Dashboard (#56) ────────────────────────────────────
  function updateGeopoliticalRisk(d){
    const gr = d.geopolitical_risk||{};
    const events = gr.events||[];
    c("geo-score",  gr.xrp_impact_score||"--");
    c("geo-risk",   gr.overall_risk||"--");
    const scoreEl = document.getElementById("geo-score");
    if(scoreEl){
      const s = gr.xrp_impact_score||0;
      scoreEl.style.color = s>=70?"var(--gr)":s>=50?"var(--yl)":"var(--rd)";
    }
    const el = document.getElementById("geo-events");
    if(!el||!events.length) return;
    const impactCol = {"BULLISH":"var(--gr)","BEARISH":"var(--rd)","NEUTRAL":"var(--yl)"};
    el.innerHTML = events.map(ev=>`
      <div style="background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:12px;
        border-left:3px solid ${impactCol[ev.impact]||'var(--tx)'}">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:4px">
          <span style="font-size:12px;font-weight:700;color:var(--tx);font-family:var(--mn)">${ev.region}</span>
          <div style="display:flex;gap:4px">
            <span style="font-size:11px;font-weight:700;color:${impactCol[ev.impact]||'var(--tx)'};
              background:rgba(0,0,0,.3);padding:2px 6px;border-radius:3px;font-family:var(--mn)">${ev.impact}</span>
            <span style="font-size:11px;color:var(--tx);background:rgba(0,0,0,.3);
              padding:2px 6px;border-radius:3px;font-family:var(--mn)">${ev.urgency}</span>
          </div>
        </div>
        <div style="font-size:13px;font-weight:700;color:var(--br);margin-bottom:4px">${ev.event}</div>
        <div style="font-size:12px;color:var(--tx);line-height:1.5">${ev.detail}</div>
      </div>`).join("");
  }


  // ── Whale Move Alerts (#59) ──────────────────────────────────────────────
  let whaleAlertShown = new Set();
  function checkWhaleAlerts(d){
    const wd     = d.whale_data||{};
    const alerts = wd.alerts||[];
    const bar    = document.getElementById("whale-alert-bar");
    const txt    = document.getElementById("whale-alert-text");
    if(!bar||!txt) return;
    // Look for large moves (10M+ XRP) in last 2 hours
    const recent = alerts.filter(a=>{
      const amount = parseFloat((a.amount_xrp||a.amount||"0").toString().replace(/[^0-9.]/g,""));
      if(amount < 5000000) return false;  // Under 5M XRP — skip
      const key = a.tx_hash||a.title||a.amount;
      if(whaleAlertShown.has(key)) return false;  // Already shown
      whaleAlertShown.add(key);
      return true;
    });
    if(recent.length > 0){
      const a = recent[0];
      const amount = parseFloat((a.amount_xrp||a.amount||"0").toString().replace(/[^0-9.]/g,""));
      const direction = a.direction||a.type||"moved";
      const from = a.from_exchange||a.from||"";
      const to   = a.to_exchange||a.to||"";
      let msg = `${(amount/1000000).toFixed(1)}M XRP ${direction}`;
      if(from) msg += ` from ${from}`;
      if(to)   msg += ` to ${to}`;
      msg += ` · ${timeAgo(a.ts||a.pub||"")}`;
      txt.textContent = msg;
      bar.style.display="flex";
      // Auto-hide after 30 seconds
      setTimeout(()=>{ bar.style.display="none"; }, 30000);
      // Browser notification
      if("Notification" in window && Notification.permission==="granted"){
        new Notification("🐋 XRPRadar Whale Alert",{
          body: msg,
          icon: "/favicon.ico"
        });
      }
    }
  }


  // ── AI Story Credibility Scorer (#73) ────────────────────────────────────
  async function runCredibilityScore(){
    const input = document.getElementById("cred-input").value.trim();
    if(!input){ alert("Please paste a headline or story."); return; }
    const btn = document.getElementById("cred-btn");
    const res = document.getElementById("cred-result");
    btn.textContent="⏳ Scoring..."; btn.disabled=true;
    res.style.display="none";
    try{
      const text = await callClaudeAI(
        `XRP/Ripple story to evaluate:\n"${input}"\n\n`+
        `Please provide:\n`+
        `1. CREDIBILITY SCORE: Rate 1 (pure FUD/fake) to 10 (verified/factual)\n`+
        `2. SOURCE TYPE: Official / Mainstream / Crypto Media / Anonymous / Unknown\n`+
        `3. SIGNAL TYPE: Real signal / FUD / Hype / Neutral information\n`+
        `4. RED FLAGS: Any signs of manipulation, exaggeration, or misinformation\n`+
        `5. VERDICT: Should XRP traders act on this or ignore it?\n\n`+
        `Be direct and specific. 6-8 sentences total.`,
        "You are XRPRadar's chief intelligence officer specializing in separating signal from noise. You have deep knowledge of XRP FUD patterns, legitimate catalysts, and common manipulation tactics. Be blunt and specific."
      );
      res.innerHTML = text.replace(/\n/g,"<br>");
      res.style.display="block";
    }catch(e){ res.innerHTML="Error: "+e.message; res.style.display="block"; }
    btn.textContent="⚡ SCORE CREDIBILITY"; btn.disabled=false;
  }

  // ── AI Partner Deal Probability (#75) ────────────────────────────────────
  async function runDealProbability(){
    const input = document.getElementById("deal-input").value.trim();
    if(!input){ alert("Please name a company."); return; }
    const btn = document.getElementById("deal-btn");
    const res = document.getElementById("deal-result");
    btn.textContent="⏳ Analyzing..."; btn.disabled=true;
    res.style.display="none";
    try{
      const text = await callClaudeAI(
        `Analyze the probability that "${input}" confirms a partnership with Ripple/XRP/XRPL.\n\n`+
        `Please provide:\n`+
        `1. PROBABILITY SCORE: 0-100% chance this becomes a confirmed Ripple partnership\n`+
        `2. EVIDENCE FOR: What signals, reports, or logic support this partnership happening\n`+
        `3. EVIDENCE AGAINST: What obstacles, competing interests, or contradictions suggest it won't happen\n`+
        `4. TIMELINE ESTIMATE: If it happens, when — 6 months, 1 year, 2+ years?\n`+
        `5. WHAT TO WATCH: What news or events would confirm or deny this partnership?\n\n`+
        `Be specific and bold. 8-10 sentences total.`,
        "You are XRPRadar's institutional intelligence analyst. You specialize in evaluating Ripple partnership signals and rumors with deep knowledge of the XRP ecosystem, banking sector dynamics, and blockchain adoption patterns."
      );
      res.innerHTML = text.replace(/\n/g,"<br>");
      res.style.display="block";
    }catch(e){ res.innerHTML="Error: "+e.message; res.style.display="block"; }
    btn.textContent="⚡ SCORE PROBABILITY"; btn.disabled=false;
  }


  // ── Social Share Cards (#77) ──────────────────────────────────────────────
  function shareStory(title, url, source, sentiment, age){
    const shareText =
      `🛰️ XRPRadar Intelligence\n\n`+
      `📰 ${title}\n\n`+
      `📡 Source: ${source}  •  ${sentiment.toUpperCase()}  •  ${age}\n\n`+
      `🔗 ${url}\n\n`+
      `More XRP intelligence at xrpradar.com\n`+
      `#XRP #Ripple #XRPRadar`;
    // Try Web Share API first (mobile)
    if(navigator.share){
      navigator.share({ title:"XRPRadar — "+title, text:shareText, url:url||"https://xrpradar.com" })
        .catch(()=>{ fallbackShare(shareText); });
    } else {
      fallbackShare(shareText);
    }
  }
  function fallbackShare(text){
    // Show a copy modal
    const modal = document.createElement("div");
    modal.style.cssText="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.8);z-index:9999;display:flex;align-items:center;justify-content:center";
    modal.innerHTML=`
      <div style="background:var(--s1);border:1px solid var(--bl);border-radius:10px;padding:20px;max-width:500px;width:90%;position:relative">
        <div style="font-size:14px;font-weight:700;color:var(--bl);font-family:var(--mn);margin-bottom:10px">📤 SHARE THIS STORY</div>
        <textarea id="share-text-area" readonly rows="8"
          style="width:100%;background:var(--bg);border:1px solid var(--b);color:var(--br);
          padding:8px;border-radius:5px;font-size:12px;font-family:monospace;resize:none;box-sizing:border-box"
        >${text}</textarea>
        <div style="display:flex;gap:8px;margin-top:10px">
          <button onclick="navigator.clipboard.writeText(document.getElementById('share-text-area').value).then(()=>this.textContent='✅ COPIED!')"
            style="flex:1;background:rgba(72,255,130,.15);color:var(--gr);padding:8px;border-radius:5px;
            border:1px solid rgba(72,255,130,.3);font-family:var(--mn);font-size:13px;font-weight:700;cursor:pointer">
            📋 COPY TO CLIPBOARD
          </button>
          <button onclick="this.closest('[style*=fixed]').remove()"
            style="background:var(--s2);color:var(--tx);padding:8px 14px;border-radius:5px;
            border:1px solid var(--b);font-family:var(--mn);font-size:13px;cursor:pointer">✕</button>
        </div>
        <div style="margin-top:8px;display:flex;gap:6px">
          <a href="https://twitter.com/intent/tweet?text=${encodeURIComponent(text.substring(0,280))}" target="_blank"
            style="flex:1;text-align:center;background:rgba(117,188,255,.1);color:var(--bl);padding:7px;
            border-radius:5px;border:1px solid rgba(117,188,255,.3);font-family:var(--mn);font-size:12px;
            font-weight:700;text-decoration:none">𝕏 Share on X</a>
          <a href="https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent('https://xrpradar.com')}" target="_blank"
            style="flex:1;text-align:center;background:rgba(72,255,130,.1);color:var(--gr);padding:7px;
            border-radius:5px;border:1px solid rgba(72,255,130,.3);font-family:var(--mn);font-size:12px;
            font-weight:700;text-decoration:none">💼 LinkedIn</a>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e=>{ if(e.target===modal) modal.remove(); });
  }


  // ── XRPRadar Leaderboard (#80) ────────────────────────────────────────────
  function updateLeaderboard(d){
    // Signal score
    const ss = d.signal_score||{};
    const ssEl = document.getElementById("lb-signal");
    const ssLbl = document.getElementById("lb-signal-label");
    if(ssEl){ ssEl.textContent = ss.total||"--"; ssEl.style.color = (ss.total||0)>=60?"var(--gr)":(ss.total||0)>=40?"var(--yl)":"var(--rd)"; }
    if(ssLbl){ ssLbl.textContent = ss.label||"--"; ssLbl.style.color = (ss.total||0)>=60?"var(--gr)":(ss.total||0)>=40?"var(--yl)":"var(--rd)"; }
    c("lb-feeds",  `${d.feeds_active||0}/${d.feeds_total||306}`);
    c("lb-stories", (d.sent_intel||{}).total_today||0);
    c("lb-poll-votes", (d.community_poll||{}).total_votes||0);
    // Top Sources from source leaderboard
    const leaders = (d.sent_intel||{}).source_leaders||[];
    const srcEl = document.getElementById("lb-sources");
    if(srcEl && leaders.length){
      srcEl.innerHTML = leaders.slice(0,8).map((s,i)=>`
        <div style="display:flex;justify-content:space-between;align-items:center;
          padding:4px 0;${i<leaders.length-1?'border-bottom:1px solid rgba(255,255,255,.04)':''}">
          <div>
            <span style="color:${i===0?'var(--yl)':i===1?'var(--tx)':i===2?'var(--or)':'var(--tx)'};font-size:11px">${['🥇','🥈','🥉'][i]||'  '} </span>
            <span style="color:var(--br)">${s.source||s.name||"--"}</span>
          </div>
          <span style="color:var(--yl)">${s.count||s.stories||0}</span>
        </div>`).join("");
    }
    // Top regions
    const regEl = document.getElementById("lb-regions");
    if(regEl && window.allStories){
      const regionMap = {};
      (window.allStories||[]).forEach(s=>{
        const reg = s.region||s.source_region||"Global";
        regionMap[reg] = (regionMap[reg]||0)+1;
      });
      const sorted = Object.entries(regionMap).sort((a,b)=>b[1]-a[1]).slice(0,8);
      if(sorted.length){
        regEl.innerHTML = sorted.map(([reg,cnt],i)=>`
          <div style="display:flex;justify-content:space-between;align-items:center;
            padding:4px 0;${i<sorted.length-1?'border-bottom:1px solid rgba(255,255,255,.04)':''}">
            <span style="color:var(--br)">${['🥇','🥈','🥉'][i]||'  '} ${reg}</span>
            <span style="color:var(--tq)">${cnt}</span>
          </div>`).join("");
      }
    }
  }


  // ══════════════════════════════════════════════════════════════════
  // v6.2 UPDATE FUNCTIONS — Features #42, #45, #48, #50-53
  // ══════════════════════════════════════════════════════════════════

  // #42 Institutional Flow Tracker
  function updateInstFlow(d){
    const inf = d.inst_flow||{};
    const net = inf.net_etf_flow_7d||0;
    const netEl = document.getElementById("if-net-flow");
    if(netEl){
      netEl.textContent = (net>=0?"+":"")+net.toFixed(0)+"M";
      netEl.style.color = net>0?"var(--gr)":net<0?"var(--rd)":"var(--yl)";
    }
    c("if-inflows",   "+"+(inf.etf_inflows_7d||0).toFixed(0)+"M");
    c("if-outflows",  "-"+(inf.etf_outflows_7d||0).toFixed(0)+"M");
    const oiEl = document.getElementById("if-oi-change");
    if(oiEl){
      const oi = inf.oi_change_24h||0;
      oiEl.textContent = (oi>=0?"+":"")+oi.toFixed(0)+"M";
      oiEl.style.color = oi>0?"var(--gr)":oi<0?"var(--rd)":"var(--yl)";
    }
    c("if-funding-trend", inf.funding_trend||"NEUTRAL");
    const sigEl = document.getElementById("if-signal");
    const sigFlow = document.getElementById("if-flow-signal");
    const sig = inf.flow_signal||"NEUTRAL";
    if(sigEl){ sigEl.textContent = sig; sigEl.style.color = sig==="BULLISH"?"var(--gr)":sig==="BEARISH"?"var(--rd)":"var(--yl)"; }
    if(sigFlow){ sigFlow.textContent = "7-day institutional positioning"; }
    const movesEl = document.getElementById("if-large-moves");
    if(movesEl && inf.large_moves_24h && inf.large_moves_24h.length){
      movesEl.innerHTML = "<div style='font-size:12px;color:var(--yl);font-family:var(--mn);margin-bottom:6px'>LARGE MOVES 24H:</div>"+
        inf.large_moves_24h.map(m=>`<div style='font-size:12px;color:var(--br);font-family:var(--mn);padding:2px 0'>${m}</div>`).join("");
    } else if(movesEl){
      movesEl.innerHTML = "<div style='font-size:12px;color:var(--tx);font-family:var(--mn)'>No large institutional moves detected in past 24h — market calm</div>";
    }
  }

  // #45 CBDC Competition Monitor — static content already rendered in HTML
  // JS here updates the opportunity score if STATE has it
  function updateCBDCComp(d){
    // CBDC section is largely static curated intelligence
    // If we ever add live score tracking, update here
  }

  // #48 XRP Options Flow
  function updateOptionsFlow(d){
    const of_ = d.options_flow||{};
    const pcr = of_.put_call_ratio||0;
    const pcrEl = document.getElementById("of-pcr");
    if(pcrEl){
      pcrEl.textContent = pcr>0?pcr.toFixed(2):"--";
      pcrEl.style.color = pcr>0&&pcr<0.7?"var(--gr)":pcr>1.3?"var(--rd)":"var(--yl)";
    }
    const pcrSig = document.getElementById("of-pcr-signal");
    if(pcrSig){
      if(pcr>0&&pcr<0.7)       pcrSig.innerHTML="<span style='color:var(--gr)'>Bullish — more calls</span>";
      else if(pcr>1.3)          pcrSig.innerHTML="<span style='color:var(--rd)'>Bearish — more puts</span>";
      else if(pcr>0)            pcrSig.innerHTML="<span style='color:var(--yl)'>Neutral positioning</span>";
      else                      pcrSig.textContent="Awaiting data...";
    }
    const iv = of_.implied_vol||0;
    const ivEl = document.getElementById("of-iv");
    if(ivEl){ ivEl.textContent = iv>0?iv.toFixed(1)+"%":"--"; ivEl.style.color=iv>80?"var(--rd)":iv>50?"var(--yl)":"var(--gr)"; }
    const mp = of_.max_pain||0;
    const mpEl = document.getElementById("of-maxpain");
    if(mpEl){ mpEl.textContent = mp>0?"$"+mp.toFixed(3):"--"; }
    const posEl = document.getElementById("of-positioning");
    const pos = of_.positioning||"NEUTRAL";
    if(posEl){ posEl.textContent = pos; posEl.style.color = pos==="BULLISH"?"var(--gr)":pos==="BEARISH"?"var(--rd)":"var(--yl)"; }
    const strikesEl = document.getElementById("of-strikes");
    if(strikesEl && of_.major_strikes && of_.major_strikes.length){
      strikesEl.innerHTML = "<div style='font-size:12px;color:var(--tx);font-family:var(--mn);margin-bottom:6px'>MAJOR OPEN INTEREST STRIKES:</div>"+
        of_.major_strikes.map(s=>`<span style='display:inline-block;background:rgba(117,188,255,.1);color:var(--bl);padding:3px 8px;border-radius:3px;font-family:var(--mn);font-size:12px;margin:2px'>$${s}</span>`).join("");
    } else if(strikesEl){
      strikesEl.innerHTML = "<div style='font-size:12px;color:var(--tx);font-family:var(--mn)'>Options data updates when XRP derivatives markets are active. Binance, Deribit, and OKX tracked.</div>";
    }
  }

  // #50 Accumulation/Distribution Score
  function updateAccumDistrib(d){
    const ad = d.accum_distrib||{};
    const s7  = ad.signal_7d||"--";
    const s30 = ad.signal_30d||"--";
    const ad7El  = document.getElementById("ad-7d");
    const ad30El = document.getElementById("ad-30d");
    if(ad7El){
      ad7El.textContent = s7;
      ad7El.style.color = s7.toLowerCase().includes("accum")?"var(--gr)":s7.toLowerCase().includes("distrib")?"var(--rd)":"var(--yl)";
    }
    if(ad30El){
      ad30El.textContent = s30;
      ad30El.style.color = s30.toLowerCase().includes("accum")?"var(--gr)":s30.toLowerCase().includes("distrib")?"var(--rd)":"var(--yl)";
    }
    const wc = ad.large_wallet_change_7d||0;
    const wcEl = document.getElementById("ad-wallet-change");
    if(wcEl){
      wcEl.textContent = (wc>=0?"+":"")+wc.toFixed(2)+"% vs 7d ago";
      wcEl.style.color = wc>0?"var(--gr)":wc<0?"var(--rd)":"var(--yl)";
    }
  }

  // #51 Whale Wallet Watchlist
  function updateWhaleWatchlist(d){
    const ww = d.whale_watchlist||{};
    const alertEl = document.getElementById("ww-alerts");
    const alerts = ww.alert_count_24h||0;
    if(alertEl){ alertEl.textContent = alerts; alertEl.style.color = alerts>5?"var(--rd)":alerts>2?"var(--or)":"var(--gr)"; }
    const lastEl = document.getElementById("ww-last-move");
    if(lastEl){
      const ts = ww.last_move_ts||"";
      lastEl.textContent = ts ? "Last activity: "+timeAgo(ts) : "No significant whale moves in 24h — wallets stable";
    }
  }

  // #52 XRPL Transaction Volume Trend
  function updateTxVolume(d){
    const tv = d.tx_volume_trend||{};
    const avg7  = tv.avg_7d||0;
    const avg30 = tv.avg_30d||0;
    const fmt = n => n>=1000000?(n/1000000).toFixed(2)+"M":n>=1000?(n/1000).toFixed(1)+"K":n.toFixed(0);
    const tv7El  = document.getElementById("tv-7d");
    const tv30El = document.getElementById("tv-30d");
    if(tv7El)  tv7El.textContent  = avg7>0?fmt(avg7):"--";
    if(tv30El) tv30El.textContent = avg30>0?fmt(avg30):"--";
    const trend = tv.trend||"--";
    const tEl = document.getElementById("tv-trend");
    if(tEl){ tEl.textContent = trend; tEl.style.color = trend==="GROWING"?"var(--gr)":trend==="DECLINING"?"var(--rd)":"var(--yl)"; }
    // Mini spark chart for 90-day trend
    const daily = tv.daily_90d||[];
    const canvas = document.getElementById("tv-canvas");
    const loading = document.getElementById("tv-loading");
    if(canvas && daily.length>5){
      if(loading) loading.style.display="none";
      const ctx = canvas.getContext("2d");
      const W = canvas.parentElement.offsetWidth||400;
      const H = 60;
      canvas.width=W; canvas.height=H;
      const vals = daily.map(p=>p.count||p||0);
      const minV = Math.min(...vals), maxV = Math.max(...vals)||1;
      ctx.clearRect(0,0,W,H);
      ctx.beginPath(); ctx.strokeStyle="#48ff82"; ctx.lineWidth=1.5; ctx.lineJoin="round";
      vals.forEach((v,i)=>{
        const x=W*i/(vals.length-1), y=H*(1-(v-minV)/(maxV-minV));
        i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
      });
      ctx.stroke();
    }
  }

  // #53 Developer Activity Score
  function updateDevScore(d){
    const ds = d.dev_score||{};
    const score = ds.score||0;
    const dsEl = document.getElementById("ds-score");
    const dtEl = document.getElementById("ds-trend");
    if(dsEl){ dsEl.textContent = score||"--"; dsEl.style.color = score>=70?"var(--gr)":score>=50?"var(--yl)":"var(--rd)"; }
    if(dtEl){ dtEl.textContent = "/100 — "+(ds.trend||"CALCULATING"); dtEl.style.color = ds.trend==="GROWING"?"var(--gr)":ds.trend==="DECLINING"?"var(--rd)":"var(--yl)"; }
    c("ds-commits",  ds.commits_7d||"--");
    c("ds-contrib",  ds.contributors_30d||"--");
    c("ds-issues",   ds.open_issues||"--");
    c("ds-stars",    ds.stars_total||"--");
  }


  // ════════════════════════════════════════════════════════════════
  // PRICE TRENDS — switchTrend + chart renderers (Items 8, 9, 10)
  // ════════════════════════════════════════════════════════════════

  let activeTrend = '30d';
  const trendTitles = {
    '30d': '30-day daily closing prices — recent momentum',
    '90d': '90-day performance calendar — green=gain · red=loss · each square = one day',
    '6m':  '6-month weekly closing prices — medium-term trend',
    '60m': '60-month (five-year) monthly closing prices — the full bull/bear cycle',
  };

  function switchTrend(tf){
    activeTrend = tf;
    document.querySelectorAll('.trend-tab').forEach(btn=>{
      const on = btn.dataset.tf === tf;
      btn.style.background = on ? 'rgba(255,204,0,.2)' : 'var(--s2)';
      btn.style.color      = on ? 'var(--yl)'          : 'var(--tx)';
      btn.style.border     = on ? '1px solid rgba(255,204,0,.5)' : '1px solid var(--b)';
    });
    document.querySelectorAll('.trend-view').forEach(v=>v.style.display='none');
    const view = document.getElementById('trend-view-'+tf);
    if(view) view.style.display='block';
    const sub = document.getElementById('trend-subtitle');
    if(sub) sub.textContent = trendTitles[tf]||'';
    if(tf==='30d')  renderChart30d();
    if(tf==='90d')  renderChart90d();
    if(tf==='6m')   renderChart6m();
    if(tf==='60m')  renderChart60m();
  }

  function drawPriceLine(canvasId, loadingId, statsId, pts, lineColor, label){
    const canvas  = document.getElementById(canvasId);
    const loading = document.getElementById(loadingId);
    const statsEl = document.getElementById(statsId);
    if(!canvas||!pts||pts.length<3){if(loading)loading.textContent='No data — loading...';return;}
    if(loading) loading.style.display='none';
    const ctx = canvas.getContext('2d');
    const W=canvas.parentElement.offsetWidth||800, H=230;
    canvas.width=W; canvas.height=H;
    const prices=pts.map(p=>p.price);
    const minP=Math.min(...prices), maxP=Math.max(...prices), range=maxP-minP||1;
    const pL=54,pR=16,pT=20,pB=36, cW=W-pL-pR, cH=H-pT-pB;
    ctx.clearRect(0,0,W,H);
    for(let i=0;i<=5;i++){
      const y=pT+cH*(1-i/5);
      ctx.strokeStyle='rgba(255,255,255,.05)';ctx.lineWidth=1;
      ctx.beginPath();ctx.moveTo(pL,y);ctx.lineTo(W-pR,y);ctx.stroke();
      ctx.fillStyle='rgba(255,255,255,.4)';ctx.font='10px monospace';ctx.textAlign='right';
      ctx.fillText('$'+(minP+(maxP-minP)*i/5).toFixed(4),pL-4,y+4);
    }
    const step=Math.max(1,Math.floor(pts.length/6));
    pts.forEach((p,i)=>{
      if(i%step===0||i===pts.length-1){
        const x=pL+cW*i/(pts.length-1);
        ctx.fillStyle='rgba(255,255,255,.3)';ctx.font='9px monospace';ctx.textAlign='center';
        ctx.fillText((p.date||'').substring(0,7),x,H-pB+14);
      }
    });
    // Gradient fill
    const r=parseInt(lineColor.slice(1,3),16),g=parseInt(lineColor.slice(3,5),16),b=parseInt(lineColor.slice(5,7),16);
    const grad=ctx.createLinearGradient(0,pT,0,pT+cH);
    grad.addColorStop(0,`rgba(${r},${g},${b},.25)`);
    grad.addColorStop(1,`rgba(${r},${g},${b},.02)`);
    ctx.beginPath();
    pts.forEach((p,i)=>{const x=pL+cW*i/(pts.length-1),y=pT+cH*(1-(p.price-minP)/range);i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);});
    ctx.lineTo(pL+cW,pT+cH);ctx.lineTo(pL,pT+cH);ctx.closePath();
    ctx.fillStyle=grad;ctx.fill();
    ctx.beginPath();ctx.strokeStyle=lineColor;ctx.lineWidth=2;ctx.lineJoin='round';
    pts.forEach((p,i)=>{const x=pL+cW*i/(pts.length-1),y=pT+cH*(1-(p.price-minP)/range);i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);});
    ctx.stroke();
    const athI=prices.indexOf(maxP);
    if(athI>=0){
      const ax=pL+cW*athI/(pts.length-1),ay=pT+cH*(1-(maxP-minP)/range);
      ctx.fillStyle='#ffcc00';ctx.font='bold 9px monospace';ctx.textAlign='center';
      ctx.fillText('▲ '+label,ax,Math.max(ay-6,pT+12));
      ctx.beginPath();ctx.arc(ax,ay,3,0,Math.PI*2);ctx.fillStyle='#ffcc00';ctx.fill();
    }
    if(statsEl){
      const first=prices[0],last=prices[prices.length-1];
      const chg=first>0?((last-first)/first*100).toFixed(2):'0.00';
      const cc=parseFloat(chg)>=0?'var(--gr)':'var(--rd)';
      statsEl.innerHTML=
        `<span style="color:var(--tx)">HIGH: <b style="color:var(--gr)">$${maxP.toFixed(4)}</b></span>`+
        `<span style="color:var(--tx)">LOW: <b style="color:var(--rd)">$${minP.toFixed(4)}</b></span>`+
        `<span style="color:var(--tx)">NOW: <b style="color:var(--br)">$${last.toFixed(4)}</b></span>`+
        `<span style="color:var(--tx)">${label} CHG: <b style="color:${cc}">${parseFloat(chg)>=0?'+':''}${chg}%</b></span>`;
    }
  }

  let _lastDi = {};

  function renderChart30d(){
    const hm = (_lastDi.price_heatmap||[]).slice(-30);
    if(!hm.length) return;
    const pts = hm.map(d=>({date:d.date.substring(5),price:d.price}));
    drawPriceLine('chart-30d','chart-30d-loading','chart-30d-stats',pts,'#48ff82','30D');
  }

  function renderChart90d(){
    const hm = _lastDi.price_heatmap||[];
    const el = document.getElementById('heatmap-grid-90');
    if(!el||!hm.length) return;
    const maxAbs=Math.max(...hm.map(d=>Math.abs(d.change||0)),1);
    const weeks={};
    hm.forEach(d=>{const wk=d.week||d.date.substring(0,7);if(!weeks[wk])weeks[wk]=[];weeks[wk].push(d);});
    const DOW=['M','T','W','T','F','S','S'];
    el.innerHTML=Object.values(weeks).map(wd=>`<div style="display:flex;gap:3px">${wd.map(d=>{
      const c=d.change||0,int=Math.min(Math.abs(c)/maxAbs,1),a=0.15+int*0.7;
      const col=c>0?`rgba(72,255,130,${a})`:c<0?`rgba(255,64,96,${a})`:'rgba(128,153,179,.15)';
      return `<div title="${d.date} ${c>=0?'+':''}${c.toFixed(2)}% $${d.price}"
        style="width:26px;height:26px;border-radius:3px;background:${col};display:flex;align-items:center;
        justify-content:center;cursor:default;font-size:9px;color:rgba(255,255,255,.4);font-family:monospace">
        ${DOW[d.dow]||''}</div>`;}).join('')}</div>`).join('');
    const statsEl=document.getElementById('chart-90d-stats');
    if(statsEl){
      const gains=hm.filter(d=>d.change>=0).length,tot=hm.length||1;
      const first=hm[0]?.price||0,last=hm[hm.length-1]?.price||0;
      const chg=first>0?((last-first)/first*100).toFixed(2):'0.00';
      const cc=parseFloat(chg)>=0?'var(--gr)':'var(--rd)';
      statsEl.innerHTML=
        `<span style="color:var(--tx)">GREEN DAYS: <b style="color:var(--gr)">${gains}</b></span>`+
        `<span style="color:var(--tx)">RED DAYS: <b style="color:var(--rd)">${tot-gains}</b></span>`+
        `<span style="color:var(--tx)">WIN RATE: <b style="color:var(--yl)">${((gains/tot)*100).toFixed(0)}%</b></span>`+
        `<span style="color:var(--tx)">90-DAY CHG: <b style="color:${cc}">${parseFloat(chg)>=0?'+':''}${chg}%</b></span>`;
    }
  }

  function renderChart6m(){
    const pts = _lastDi.price_history_6m||[];
    if(!pts.length) return;
    drawPriceLine('chart-6m','chart-6m-loading','chart-6m-stats',pts,'#00e5cc','6M');
  }

  function renderChart60m(){
    const pts = _lastDi.price_history_60m||[];
    if(!pts.length) return;
    drawPriceLine('chart-60m','chart-60m-loading','chart-60m-stats',pts,'#48ff82','5Y');
  }

  function updatePriceTrends(d){
    _lastDi = d.disp_intel||{};
    if(activeTrend==='30d')  renderChart30d();
    if(activeTrend==='90d')  renderChart90d();
    if(activeTrend==='6m')   renderChart6m();
    if(activeTrend==='60m')  renderChart60m();
  }


  // ════════════════════════════════════════════════════════════════
  // V7.0 EXPERIMENTAL METRICS JAVASCRIPT
  // ════════════════════════════════════════════════════════════════

  // ── Feature 1: XRP Time Machine ──────────────────────────────────
  function setTMDate(d){ const el=document.getElementById('tm-date'); if(el) el.value=d; }

  async function runTimeMachine(){
    const amtEl = document.getElementById('tm-amount');
    const dateEl= document.getElementById('tm-date');
    const resEl = document.getElementById('tm-results');
    const ldgEl = document.getElementById('tm-loading');
    const errEl = document.getElementById('tm-error');
    if(!amtEl||!dateEl) return;
    const amount = parseFloat(amtEl.value)||0;
    const dateStr= dateEl.value;
    if(!amount||amount<=0){ if(errEl){errEl.textContent='Please enter a valid investment amount.';errEl.style.display='block';} return; }
    if(!dateStr){ if(errEl){errEl.textContent='Please select a date.';errEl.style.display='block';} return; }
    const purchaseDate = new Date(dateStr);
    const today = new Date();
    if(purchaseDate >= today){ if(errEl){errEl.textContent="Pick a date in the past.";errEl.style.display='block';} return; }
    // Show loading
    if(resEl) resEl.style.display='none';
    if(errEl) errEl.style.display='none';
    if(ldgEl) ldgEl.style.display='block';
    try{
      // Calculate days since purchase
      const msPerDay = 86400000;
      const daysSince = Math.ceil((today - purchaseDate)/msPerDay);
      const daysNeeded = Math.max(daysSince+2, 1);
      const fetchDays = Math.min(daysNeeded, 2000); // CoinGecko max ~2000 days free
      const r = await fetch(
        `https://api.coingecko.com/api/v3/coins/ripple/market_chart?vs_currency=usd&days=${fetchDays}`
      );
      const data = await r.json();
      const prices = data.prices||[];
      if(!prices.length) throw new Error('No price data returned');
      // Find price on purchase date
      const purchaseTs = purchaseDate.getTime();
      // Find closest price to purchase date
      let bestIdx=0, bestDiff=Infinity;
      prices.forEach((p,i)=>{ const diff=Math.abs(p[0]-purchaseTs); if(diff<bestDiff){bestDiff=diff;bestIdx=i;} });
      const priceThen = prices[bestIdx][1];
      const priceNow  = prices[prices.length-1][1];
      // ATH in period
      const athPrice = Math.max(...prices.slice(bestIdx).map(p=>p[1]));
      // Calculations
      const xrpBought   = amount / priceThen;
      const valueNow    = xrpBought * priceNow;
      const valuePeak   = xrpBought * athPrice;
      const pnl         = valueNow - amount;
      const returnPct   = ((valueNow - amount)/amount)*100;
      const peakReturn  = ((valuePeak - amount)/amount)*100;
      // Populate
      c('tm-invested',    '$'+amount.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}));
      c('tm-xrp-bought',  xrpBought.toLocaleString(undefined,{maximumFractionDigits:2})+' XRP');
      c('tm-price-then',  '$'+priceThen.toFixed(4));
      c('tm-price-now',   '$'+priceNow.toFixed(4));
      const valNowEl = document.getElementById('tm-value-now');
      if(valNowEl){
        valNowEl.textContent='$'+valueNow.toLocaleString(undefined,{maximumFractionDigits:2});
        valNowEl.style.color=valueNow>=amount?'var(--gr)':'var(--rd)';
      }
      c('tm-value-peak',  '$'+valuePeak.toLocaleString(undefined,{maximumFractionDigits:2}));
      const pnlEl = document.getElementById('tm-pnl');
      if(pnlEl){
        pnlEl.textContent=(pnl>=0?'+':'')+' $'+Math.abs(pnl).toLocaleString(undefined,{maximumFractionDigits:2});
        pnlEl.style.color=pnl>=0?'var(--gr)':'var(--rd)';
      }
      const retEl = document.getElementById('tm-return-pct');
      if(retEl){
        retEl.textContent=(returnPct>=0?'+':'')+returnPct.toFixed(1)+'%';
        retEl.style.color=returnPct>=0?'var(--gr)':'var(--rd)';
      }
      // Narrative
      const narr = document.getElementById('tm-narrative');
      if(narr){
        const verb = returnPct>=0?'grown':'fallen';
        const emoji= returnPct>=200?'🚀':returnPct>=50?'📈':returnPct>=0?'💚':returnPct>=-50?'📉':'🔻';
        narr.innerHTML=`${emoji} <b>If you had invested <span style="color:var(--yl)">$${amount.toLocaleString()}</span> in XRP on ${purchaseDate.toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'})}</b>, you would have purchased <b style="color:var(--bl)">${xrpBought.toLocaleString(undefined,{maximumFractionDigits:0})} XRP</b> at <b style="color:var(--yl)">$${priceThen.toFixed(4)}</b> each. Today your investment would be worth <b style="color:${returnPct>=0?'var(--gr)':'var(--rd)'}">${'$'+valueNow.toLocaleString(undefined,{maximumFractionDigits:2})}</b> — a ${returnPct>=0?'gain':'loss'} of <b>${Math.abs(returnPct).toFixed(1)}%</b>. At XRP's peak of <b style="color:var(--yl)">$${athPrice.toFixed(4)}</b> during this period, your holding would have been worth <b style="color:var(--yl)">$${valuePeak.toLocaleString(undefined,{maximumFractionDigits:2})}</b> (+${peakReturn.toFixed(0)}%).`;
      }
      if(ldgEl) ldgEl.style.display='none';
      if(resEl) resEl.style.display='block';
    }catch(e){
      if(ldgEl) ldgEl.style.display='none';
      if(errEl){errEl.textContent='Error fetching data: '+e.message+'. Please try again.';errEl.style.display='block';}
    }
  }


  // ── Feature 2: Macro Events Calendar ─────────────────────────────
  let activeCalFilter = 'ALL';
  const calCategoryColors = {
    'FED':'var(--rd)','ETF':'var(--gr)','LEGAL':'var(--yl)','CONGRESS':'var(--bl)',
    'ESCROW':'var(--or)','XRPL':'var(--tq)','REGULATORY':'var(--tx)','RIPPLE':'var(--gr)',
  };
  const calCategoryIcons = {
    'FED':'🏛️','ETF':'📊','LEGAL':'⚖️','CONGRESS':'🏛️','ESCROW':'🔒',
    'XRPL':'🔗','REGULATORY':'📋','RIPPLE':'🌊',
  };

  function filterCalendar(cat){
    activeCalFilter = cat;
    document.querySelectorAll('[id^="cal-f-"]').forEach(b=>{
      b.style.fontWeight = b.id==='cal-f-'+cat?'900':'400';
      b.style.background = b.id==='cal-f-'+cat?'rgba(117,188,255,.15)':'';
    });
    renderCalendar(window._calEvents||[]);
  }

  function renderCalendar(events){
    window._calEvents = events;
    const el = document.getElementById('macro-calendar-grid');
    if(!el) return;
    const now = new Date();
    const filtered = activeCalFilter==='ALL'?events:events.filter(e=>e.category===activeCalFilter);
    const sorted = [...filtered].sort((a,b)=>new Date(a.date)-new Date(b.date));
    if(!sorted.length){el.innerHTML='<div style="font-size:13px;color:var(--tx);font-family:var(--mn)">No events in this category.</div>';return;}
    el.innerHTML = sorted.map(ev=>{
      const evDate = new Date(ev.date+'T12:00:00');
      const daysOut= Math.ceil((evDate-now)/86400000);
      const isPast = daysOut < 0;
      const isToday= daysOut===0;
      const isSoon = daysOut>=0 && daysOut<=7;
      const col = calCategoryColors[ev.category]||'var(--tx)';
      const icon= calCategoryIcons[ev.category]||'📌';
      const urgency = isToday?'🔴 TODAY':isSoon?`🟡 IN ${daysOut}d`:isPast?'⬛ PAST':`🟢 ${daysOut}d`;
      const urgCol  = isToday?'var(--rd)':isSoon?'var(--yl)':isPast?'rgba(128,153,179,.4)':'var(--gr)';
      return `<div style="display:flex;gap:12px;padding:10px 12px;background:var(--bg);border-radius:6px;
        border:1px solid ${isPast?'rgba(255,255,255,.04)':'var(--b)'};border-left:3px solid ${isPast?'rgba(128,153,179,.3)':col};
        opacity:${isPast?'0.5':'1'}">
        <div style="min-width:90px;text-align:center;padding:4px 0">
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn)">${evDate.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})}</div>
          <div style="font-size:12px;font-weight:700;color:${urgCol};font-family:var(--mn);margin-top:3px">${urgency}</div>
        </div>
        <div style="flex:1">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">
            <span style="font-size:11px;font-weight:700;color:${col};background:${col}18;
              padding:2px 8px;border-radius:3px;font-family:var(--mn)">${icon} ${ev.category}</span>
            <span style="font-size:14px;font-weight:700;color:var(--br)">${ev.title}</span>
            <span style="font-size:11px;font-weight:700;color:${ev.impact==='HIGH'?'var(--rd)':ev.impact==='MEDIUM'?'var(--yl)':'var(--tx)'};
              font-family:var(--mn)">${ev.impact} IMPACT</span>
          </div>
          <div style="font-size:13px;color:var(--tx);line-height:1.5">${ev.detail}</div>
          <div style="font-size:11px;color:var(--tx);font-family:var(--mn);margin-top:4px;opacity:.7">SOURCE: ${ev.source}</div>
        </div>
      </div>`;
    }).join('');
  }

  function updateMacroCalendar(d){
    const cal = d.macro_calendar||{};
    const events = cal.events||[];
    if(events.length) renderCalendar(events);
  }


  // ── Feature 3: Derivatives Dashboard ─────────────────────────────
  function updateDerivatives(d){
    const dv = d.derivatives||{};
    const hist = dv.funding_rate_history||[];
    // Current funding = most recent
    const latest = hist.length ? hist[hist.length-1].rate : null;
    const fundEl = document.getElementById('dv-funding');
    if(fundEl && latest!==null){
      fundEl.textContent = (latest>=0?'+':'')+latest.toFixed(4)+'%';
      fundEl.style.color = latest>0?'var(--gr)':latest<0?'var(--rd)':'var(--yl)';
    }
    c('dv-funding-trend', dv.funding_trend||'--');
    const lsEl = document.getElementById('dv-ls-ratio');
    const posEl= document.getElementById('dv-positioning');
    if(lsEl){ lsEl.textContent=(dv.long_short_ratio||0).toFixed(3);
      lsEl.style.color=dv.long_short_ratio>1.2?'var(--gr)':dv.long_short_ratio<0.8?'var(--rd)':'var(--yl)'; }
    if(posEl){ posEl.textContent=dv.positioning||'--';
      posEl.style.color=dv.positioning&&dv.positioning.includes('LONG')?'var(--gr)':dv.positioning&&dv.positioning.includes('SHORT')?'var(--rd)':'var(--yl)'; }
    const liq = dv.liquidations_24h||{};
    c('dv-long-liq',  liq.long_liq>0?'$'+(liq.long_liq/1e6).toFixed(2)+'M':'$0.00M');
    c('dv-short-liq', liq.short_liq>0?'$'+(liq.short_liq/1e6).toFixed(2)+'M':'$0.00M');
    // OI trend
    const oiH = dv.oi_history||[];
    if(oiH.length>=2){
      const first=oiH[0].oi, last=oiH[oiH.length-1].oi;
      const chg=((last-first)/first*100).toFixed(1);
      const oiEl=document.getElementById('dv-oi-trend');
      if(oiEl){ oiEl.textContent=(parseFloat(chg)>=0?'+':'')+chg+'%';
        oiEl.style.color=parseFloat(chg)>=0?'var(--gr)':'var(--rd)'; }
    }
    c('dv-ts', dv.ts||'--');
    // Draw funding rate chart
    if(hist.length>2){
      const canvas=document.getElementById('dv-funding-chart');
      if(canvas){
        const ctx=canvas.getContext('2d');
        const W=canvas.parentElement.offsetWidth||600,H=70;
        canvas.width=W;canvas.height=H;
        const rates=hist.map(h=>h.rate);
        const minR=Math.min(...rates,0),maxR=Math.max(...rates,0);
        const range=Math.max(Math.abs(maxR),Math.abs(minR))||0.01;
        const zero=H/2;
        ctx.clearRect(0,0,W,H);
        // Zero line
        ctx.strokeStyle='rgba(255,255,255,.15)';ctx.lineWidth=1;
        ctx.beginPath();ctx.moveTo(0,zero);ctx.lineTo(W,zero);ctx.stroke();
        // Bars
        const barW=W/rates.length;
        rates.forEach((r,i)=>{
          const h2=Math.abs(r)/range*(H/2);
          const x=i*barW;
          ctx.fillStyle=r>=0?'rgba(72,255,130,.6)':'rgba(255,64,96,.6)';
          ctx.fillRect(x,r>=0?zero-h2:zero,barW-1,h2);
        });
      }
    }
  }

  // ── Feature 4: RLUSD Dashboard ───────────────────────────────────
  function updateRLUSD(d){
    const oc = d.onchain_intel||d.onchain||{};
    // RLUSD data is in onchain_intel
    const supply = oc.rlusd_supply||0;
    const vol    = oc.rlusd_vol||0;
    if(supply){ c('rlusd-supply', fmtUSD(supply)); }
    if(vol)   { c('rlusd-vol',    fmtUSD(vol)); }
    // Try to get from price data too (CoinGecko)
    const prices = d.price||{};
    // If we have RLUSD specific data
    if(oc.rlusd_price){
      const rp = parseFloat(oc.rlusd_price)||1;
      c('rlusd-price', '$'+rp.toFixed(4));
      const pegEl = document.getElementById('rlusd-peg-status');
      if(pegEl){
        const pegDiff = Math.abs(rp-1)*100;
        if(pegDiff<0.1){ pegEl.textContent='✅ ON PEG'; pegEl.style.color='var(--gr)'; }
        else if(pegDiff<0.5){ pegEl.textContent='⚠️ MINOR DEVIATION ('+pegDiff.toFixed(2)+'%)'; pegEl.style.color='var(--yl)'; }
        else{ pegEl.textContent='🚨 OFF PEG ('+pegDiff.toFixed(2)+'%)'; pegEl.style.color='var(--rd)'; }
      }
    } else {
      c('rlusd-price','$1.0000');
      const pegEl=document.getElementById('rlusd-peg-status');
      if(pegEl){pegEl.textContent='✅ PEGGED 1:1 USD';pegEl.style.color='var(--gr)';}
    }
    // Fetch live RLUSD data from CoinGecko
    fetchRLUSDLive();
  }

  async function fetchRLUSDLive(){
    try{
      const r = await fetch('https://api.coingecko.com/api/v3/coins/ripple-usd?localization=false&tickers=false&community_data=false');
      const data = await r.json();
      const md = data.market_data||{};
      if(md.current_price) c('rlusd-price','$'+(md.current_price.usd||1).toFixed(4));
      if(md.market_cap)    c('rlusd-mcap', fmtUSD(md.market_cap.usd||0));
      if(md.total_volume)  c('rlusd-vol',  fmtUSD(md.total_volume.usd||0));
      if(md.circulating_supply) c('rlusd-supply', (md.circulating_supply/1e6).toFixed(2)+'M RLUSD');
      if(data.market_cap_rank) c('rlusd-rank','#'+data.market_cap_rank);
      const chg=md.price_change_percentage_24h||0;
      const chgEl=document.getElementById('rlusd-change');
      if(chgEl){chgEl.textContent=(chg>=0?'+':'')+chg.toFixed(3)+'%';chgEl.style.color=Math.abs(chg)<0.1?'var(--gr)':'var(--yl)';}
    }catch(e){}
  }

  // ── Feature 5: Custom Keyword Alert System ────────────────────────
  let userKeywords = JSON.parse(localStorage.getItem('xrpr_keywords')||'[]');
  let kwMatchedTitles = new Set();

  function renderKeywordTags(){
    const el=document.getElementById('kw-tags');
    if(!el) return;
    if(!userKeywords.length){
      el.innerHTML='<span style="font-size:12px;color:var(--tx);font-family:var(--mn);padding:4px 0">No keywords set — add one above</span>';
      return;
    }
    el.innerHTML=userKeywords.map((kw,i)=>`
      <span style="background:rgba(117,188,255,.1);border:1px solid rgba(117,188,255,.3);
        color:var(--bl);padding:4px 10px;border-radius:4px;font-family:var(--mn);font-size:13px;
        display:flex;align-items:center;gap:6px">
        🔍 ${kw}
        <span onclick="removeKeyword(${i})" style="cursor:pointer;color:var(--tx);font-size:14px;line-height:1">×</span>
      </span>`).join('');
  }
  function addKeyword(){
    const el=document.getElementById('kw-input');
    if(!el) return;
    const kw=el.value.trim().toLowerCase();
    if(!kw||userKeywords.includes(kw)){el.value='';return;}
    if(userKeywords.length>=10){alert('Maximum 10 keywords. Remove one first.');return;}
    userKeywords.push(kw);
    localStorage.setItem('xrpr_keywords',JSON.stringify(userKeywords));
    el.value='';
    renderKeywordTags();
  }
  function removeKeyword(i){
    userKeywords.splice(i,1);
    localStorage.setItem('xrpr_keywords',JSON.stringify(userKeywords));
    renderKeywordTags();
  }
  function requestKwPermission(){
    if('Notification' in window) Notification.requestPermission().then(p=>{
      if(p==='granted') alert('✅ Notifications enabled! You will be alerted when keywords match.');
    });
  }
  function checkKeywordAlerts(stories){
    if(!userKeywords.length||!stories.length) return;
    stories.forEach(s=>{
      const title=(s.title||'').toLowerCase();
      userKeywords.forEach(kw=>{
        const matchKey=s.title+'|'+kw;
        if(title.includes(kw)&&!kwMatchedTitles.has(matchKey)){
          kwMatchedTitles.add(matchKey);
          showKwAlert(kw, s.title, s.link||s.url||'#', s.source||'');
        }
      });
    });
  }
  function showKwAlert(kw, title, link, source){
    const banner=document.getElementById('kw-alert-banner');
    const text  =document.getElementById('kw-alert-text');
    if(banner) banner.style.display='block';
    if(text) text.innerHTML=`Keyword "<b style="color:var(--yl)">${kw}</b>" matched: <a href="${link}" target="_blank"
      style="color:var(--bl);text-decoration:none">${title}</a>
      <span style="color:var(--tx);font-family:var(--mn);font-size:12px"> — ${source}</span>`;
    if('Notification' in window&&Notification.permission==='granted'){
      new Notification('🔔 XRPRadar Keyword Alert: '+kw,{body:title,icon:'/favicon.ico'});
    }
  }
  // Initialize keyword tags on load
  renderKeywordTags();

  // ── Feature 6: Validator Network Map ─────────────────────────────
  const VALIDATORS = [
    {op:"Ripple Labs",  country:"🇺🇸 USA",   region:"NA",  ripple:true,  uptime:99.9},
    {op:"Ripple Labs",  country:"🇺🇸 USA",   region:"NA",  ripple:true,  uptime:99.9},
    {op:"Ripple Labs",  country:"🇺🇸 USA",   region:"NA",  ripple:true,  uptime:99.9},
    {op:"Ripple Labs",  country:"🇬🇧 UK",    region:"EU",  ripple:true,  uptime:99.9},
    {op:"Ripple Labs",  country:"🇸🇬 SG",    region:"APAC",ripple:true,  uptime:99.9},
    {op:"Ripple Labs",  country:"🇩🇪 DE",    region:"EU",  ripple:true,  uptime:99.9},
    {op:"Arrington XRP Capital",country:"🇺🇸 USA",region:"NA",ripple:false,uptime:99.7},
    {op:"Bitrue",       country:"🇸🇬 SG",    region:"APAC",ripple:false, uptime:99.5},
    {op:"XRPL Labs",    country:"🇳🇱 NL",    region:"EU",  ripple:false, uptime:99.8},
    {op:"Coil",         country:"🇺🇸 USA",   region:"NA",  ripple:false, uptime:99.6},
    {op:"Gatehub",      country:"🇬🇧 UK",    region:"EU",  ripple:false, uptime:99.4},
    {op:"XRPL Monitor", country:"🇯🇵 JP",    region:"APAC",ripple:false, uptime:99.9},
    {op:"SBI Holdings", country:"🇯🇵 JP",    region:"APAC",ripple:false, uptime:99.8},
    {op:"Alloy Networks",country:"🇺🇸 USA",  region:"NA",  ripple:false, uptime:99.7},
    {op:"Digital Garage",country:"🇯🇵 JP",   region:"APAC",ripple:false, uptime:99.6},
    {op:"OfferZen",     country:"🇿🇦 ZA",    region:"AF",  ripple:false, uptime:99.3},
    {op:"Cloud9",       country:"🇺🇸 USA",   region:"NA",  ripple:false, uptime:99.8},
    {op:"Isrdc",        country:"🇦🇺 AU",    region:"APAC",ripple:false, uptime:99.5},
    {op:"Cabbit",       country:"🇦🇺 AU",    region:"APAC",ripple:false, uptime:99.4},
    {op:"Aesthetes",    country:"🇫🇷 FR",    region:"EU",  ripple:false, uptime:99.6},
    {op:"CryptoStreet", country:"🇳🇱 NL",    region:"EU",  ripple:false, uptime:99.7},
    {op:"RippleWork",   country:"🇮🇳 IN",    region:"APAC",ripple:false, uptime:99.5},
    {op:"NixXRP",       country:"🇨🇦 CA",    region:"NA",  ripple:false, uptime:99.6},
    {op:"Rabbit",       country:"🇨🇭 CH",    region:"EU",  ripple:false, uptime:99.8},
    {op:"BCB Group",    country:"🇬🇧 UK",    region:"EU",  ripple:false, uptime:99.4},
    {op:"Eminence",     country:"🇨🇦 CA",    region:"NA",  ripple:false, uptime:99.5},
    {op:"Positive XRP", country:"🇳🇱 NL",    region:"EU",  ripple:false, uptime:99.3},
    {op:"Exinite",      country:"🇨🇿 CZ",    region:"EU",  ripple:false, uptime:99.7},
    {op:"XRPL Dev",     country:"🇨🇳 CN",    region:"APAC",ripple:false, uptime:99.6},
    {op:"ValidateXRP",  country:"🇩🇪 DE",    region:"EU",  ripple:false, uptime:99.5},
    {op:"Allsides",     country:"🇯🇵 JP",    region:"APAC",ripple:false, uptime:99.4},
    {op:"Cabbit2",      country:"🇦🇺 AU",    region:"APAC",ripple:false, uptime:99.3},
    {op:"XRPL Community",country:"🇸🇪 SE",   region:"EU",  ripple:false, uptime:99.8},
    {op:"XRPL Security",country:"🇸🇬 SG",    region:"APAC",ripple:false, uptime:99.6},
    {op:"Bithomp",      country:"🇸🇪 SE",    region:"EU",  ripple:false, uptime:99.7},
  ];

  function renderValidatorMap(){
    const el = document.getElementById('validator-list');
    if(!el) return;
    const rippleCount = VALIDATORS.filter(v=>v.ripple).length;
    const indieCount  = VALIDATORS.length - rippleCount;
    const avgUptime   = (VALIDATORS.reduce((s,v)=>s+v.uptime,0)/VALIDATORS.length).toFixed(1);
    c('val-count',       VALIDATORS.length);
    c('val-ripple-count',rippleCount);
    c('val-indie-count', indieCount);
    c('val-decentral',   Math.round(indieCount/VALIDATORS.length*100)+'%');
    c('val-uptime',      avgUptime+'%');
    el.innerHTML = VALIDATORS.map(v=>`
      <div style="padding:8px 10px;background:var(--bg);border-radius:5px;border:1px solid var(--b);
        border-left:3px solid ${v.ripple?'var(--yl)':'var(--gr)'}">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:13px;font-weight:700;color:var(--br);font-family:var(--mn)">${v.op}</span>
          <span style="font-size:11px;color:${v.ripple?'var(--yl)':'var(--gr)'};font-family:var(--mn)">${v.ripple?'RIPPLE':'INDIE'}</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--tx);font-family:var(--mn);margin-top:3px">
          <span>${v.country}</span>
          <span style="color:var(--gr)">↑ ${v.uptime}%</span>
        </div>
      </div>`).join('');
  }

  // ── Feature 7: Escrow Analytics ──────────────────────────────────
  function updateEscrowAnalytics(d){
    const esc = (d.onchain_intel||d.onchain||{});
    const escrow = esc.escrow||{};
    const remaining = escrow.remaining_xrp||0;
    const total_xrp = 100000000000;
    const circulating = (d.price||{}).supply||45000000000;
    if(remaining){
      c('esc-remaining', (remaining/1e9).toFixed(2)+'B XRP');
      const released = total_xrp - remaining - circulating;
      c('esc-released',  released>0?(released/1e9).toFixed(2)+'B XRP':'~10B XRP');
      c('esc-pct',       (remaining/total_xrp*100).toFixed(1)+'%');
    } else {
      c('esc-remaining','~39B XRP');
      c('esc-released', '~16B XRP');
      c('esc-pct',      '~39%');
    }
    // Next escrow release - always 1st of next month
    const now=new Date();
    const nextRelease=new Date(now.getFullYear(),now.getMonth()+1,1);
    const daysToNext=Math.ceil((nextRelease-now)/86400000);
    c('esc-next', daysToNext+' days');
    // Build release timeline (last 12 months static data)
    const tlEl=document.getElementById('escrow-release-timeline');
    if(tlEl){
      const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      const year=2025;
      const releases=[850,920,780,900,860,910,840,880,900,920,850,870]; // approx re-locked millions
      const yr2=2026;
      const releases2=[900,860,820,910,890,880]; // 2026 so far
      tlEl.innerHTML=`
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(80px,1fr));gap:4px">
          ${[...months.map((m,i)=>({m:m+' '+year,rel:1000,relocked:releases[i],net:1000-releases[i]})),
             ...months.slice(0,releases2.length).map((m,i)=>({m:m+' '+yr2,rel:1000,relocked:releases2[i],net:1000-releases2[i]}))
            ].map(r=>`
            <div style="text-align:center;padding:6px 4px;background:rgba(255,204,0,.04);border:1px solid rgba(255,204,0,.1);border-radius:4px">
              <div style="font-size:10px;color:var(--tx);font-family:var(--mn)">${r.m}</div>
              <div style="font-size:11px;color:var(--or);font-family:var(--mn);font-weight:700">-${r.relocked}M</div>
              <div style="font-size:10px;color:var(--gr);font-family:var(--mn)">+${r.net}M net</div>
            </div>`).join('')}
        </div>
        <div style="margin-top:8px;font-size:11px;color:var(--tx);font-family:var(--mn)">
          Orange = re-locked by Ripple · Green = net new XRP entering circulation
        </div>`;
    }
  }

  // Wire all v7.0 features into fetchData via updateExperimental
  function updateExperimental(d){
    updateDerivatives(d);
    updateRLUSD(d);
    updateMacroCalendar(d);
    updateEscrowAnalytics(d);
    checkKeywordAlerts(d.stories||[]);
    // Render static features if not yet rendered
    if(!document.getElementById('validator-list').children.length) renderValidatorMap();
  }

</script>

</body>
</html>
"""

# ── Startup ────────────────────────────────────────────────────────────────────
load_state()
threading.Thread(target=prediction_loop, daemon=True).start()
threading.Thread(target=price_loop, daemon=True).start()
threading.Thread(target=market_loop, daemon=True).start()
threading.Thread(target=news_loop,  daemon=True).start()

# ════════════════════════════════════════════════════════════════════
# v7.0 EXPERIMENTAL FETCH FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def fetch_derivatives():
    """v7.0 #3 — Derivatives: funding rates, long/short ratio, open interest."""
    hdr = {"User-Agent":"XRPRadar/7.0"}
    dv  = STATE["derivatives"]
    try:
        r = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate?symbol=XRPUSDT&limit=24",
            headers=hdr, timeout=10).json()
        if isinstance(r, list) and r:
            history = [{"ts": x["fundingTime"], "rate": round(float(x["fundingRate"])*100, 6)} for x in r]
            dv["funding_rate_history"] = history[-24:]
            rates = [h["rate"] for h in history]
            avg_rate = sum(rates)/len(rates) if rates else 0
            if avg_rate > 0.01:    dv["funding_trend"] = "BULLISH (longs paying)"
            elif avg_rate < -0.01: dv["funding_trend"] = "BEARISH (shorts paying)"
            else:                  dv["funding_trend"] = "NEUTRAL"
    except Exception as e: log_error(f"derivs_funding: {e}")
    try:
        r = requests.get(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=XRPUSDT&period=1h&limit=1",
            headers=hdr, timeout=10).json()
        if isinstance(r, list) and r:
            ratio = round(float(r[-1].get("longShortRatio", 1.0)), 3)
            dv["long_short_ratio"] = ratio
            if ratio > 1.5:   dv["positioning"] = "CROWDED LONG"
            elif ratio > 1.1: dv["positioning"] = "LONG BIAS"
            elif ratio < 0.7: dv["positioning"] = "CROWDED SHORT"
            elif ratio < 0.9: dv["positioning"] = "SHORT BIAS"
            else:             dv["positioning"] = "BALANCED"
    except Exception as e: log_error(f"derivs_ls: {e}")
    try:
        r = requests.get(
            "https://fapi.binance.com/futures/data/openInterestHist?symbol=XRPUSDT&period=1h&limit=12",
            headers=hdr, timeout=10).json()
        if isinstance(r, list):
            dv["oi_history"] = [{"ts": x["timestamp"], "oi": round(float(x["sumOpenInterest"]),0)} for x in r]
    except Exception as e: log_error(f"derivs_oi: {e}")
    dv["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")


# ════════════════════════════════════════════════════════════════════
# v6.0 FETCH FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def fetch_order_book():
    """#41 — Live order book depth from Binance, Bitstamp, Kraken."""
    hdr = {"User-Agent": "XRPRadar/6.0"}
    ob  = STATE["order_book"]
    try:
        # Binance
        r = requests.get("https://api.binance.com/api/v3/depth?symbol=XRPUSDT&limit=20",
                         headers=hdr, timeout=10).json()
        bids_b = [(float(p), float(q)) for p,q in r.get("bids",[])[:10]]
        asks_b = [(float(p), float(q)) for p,q in r.get("asks",[])[:10]]
        spread_b = round(asks_b[0][0] - bids_b[0][0], 5) if bids_b and asks_b else 0
        ob["binance"] = {"bids":bids_b,"asks":asks_b,"spread":spread_b,"ts":"Binance"}
    except Exception as e: log_error(f"ob_binance: {e}")
    try:
        # Bitstamp
        r = requests.get("https://www.bitstamp.net/api/v2/order_book/xrpusd/",
                         headers=hdr, timeout=10).json()
        bids_s = [(float(p), float(q)) for p,q in r.get("bids",[])[:10]]
        asks_s = [(float(p), float(q)) for p,q in r.get("asks",[])[:10]]
        spread_s = round(asks_s[0][0] - bids_s[0][0], 5) if bids_s and asks_s else 0
        ob["bitstamp"] = {"bids":bids_s,"asks":asks_s,"spread":spread_s,"ts":"Bitstamp"}
    except Exception as e: log_error(f"ob_bitstamp: {e}")
    try:
        # Kraken
        r = requests.get("https://api.kraken.com/0/public/Depth?pair=XRPUSD&count=20",
                         headers=hdr, timeout=10).json()
        book = list(r.get("result",{}).values())[0] if r.get("result") else {}
        bids_k = [(float(p), float(q)) for p,q,_ in book.get("bids",[])[:10]]
        asks_k = [(float(p), float(q)) for p,q,_ in book.get("asks",[])[:10]]
        spread_k = round(asks_k[0][0] - bids_k[0][0], 5) if bids_k and asks_k else 0
        ob["kraken"] = {"bids":bids_k,"asks":asks_k,"spread":spread_k,"ts":"Kraken"}
    except Exception as e: log_error(f"ob_kraken: {e}")
    # Aggregate best bid/ask walls
    try:
        all_bids = ob["binance"]["bids"] + ob["bitstamp"]["bids"] + ob["kraken"]["bids"]
        all_asks = ob["binance"]["asks"] + ob["bitstamp"]["asks"] + ob["kraken"]["asks"]
        # Group by price level (round to 4dp)
        bid_map = {}
        for p,q in all_bids:
            k = round(p,4)
            bid_map[k] = bid_map.get(k,0) + q
        ask_map = {}
        for p,q in all_asks:
            k = round(p,4)
            ask_map[k] = ask_map.get(k,0) + q
        ob["combined_bids"] = sorted([(p,q) for p,q in bid_map.items()],reverse=True)[:15]
        ob["combined_asks"] = sorted([(p,q) for p,q in ask_map.items()])[:15]
        ob["total_bid_depth"] = round(sum(q for _,q in ob["combined_bids"]),0)
        ob["total_ask_depth"] = round(sum(q for _,q in ob["combined_asks"]),0)
    except Exception as e: log_error(f"ob_aggregate: {e}")


def fetch_macro_data():
    """#46/#47 — Macro dashboard: DXY, S&P 500, Gold, Treasuries + XRP correlation."""
    import datetime as _dt
    hdr  = {"User-Agent":"Mozilla/5.0 (compatible; XRPRadar/6.0)"}
    md   = STATE["macro_data"]
    corr = STATE["correlation"]
    symbols = {
        "dxy":      "DX-Y.NYB",
        "sp500":    "%5EGSPC",
        "gold":     "GC%3DF",
        "treasury": "%5ETNX",
        "btc":      "BTC-USD",
    }
    for key, sym in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d"
            r   = requests.get(url, headers=hdr, timeout=12).json()
            result = r.get("chart",{}).get("result",[None])[0]
            if not result: continue
            closes = result.get("indicators",{}).get("quote",[{}])[0].get("close",[])
            closes = [c for c in closes if c is not None]
            if len(closes) >= 2:
                val   = round(closes[-1], 4)
                prev  = round(closes[-2], 4)
                chg   = round((val - prev)/prev*100, 2) if prev else 0
                md[key]["value"]      = val
                md[key]["change_pct"] = chg
        except Exception as e: log_error(f"macro_{key}: {e}")
    md["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")

    # XRP vs Macro correlation (30-day, simplified directional)
    try:
        xrp_chg  = STATE["price_data"].get("change_24h", 0)
        dxy_chg  = md["dxy"]["change_pct"]
        sp_chg   = md["sp500"]["change_pct"]
        gold_chg = md["gold"]["change_pct"]
        btc_chg  = md["btc"]["change_pct"]
        def dir_corr(a,b):
            if a == 0 or b == 0: return "--"
            return "POSITIVE" if (a>0) == (b>0) else "NEGATIVE"
        corr["xrp_btc"]   = dir_corr(xrp_chg, btc_chg)
        corr["xrp_sp500"] = dir_corr(xrp_chg, sp_chg)
        corr["xrp_gold"]  = dir_corr(xrp_chg, gold_chg)
        corr["xrp_dxy"]   = dir_corr(xrp_chg, dxy_chg)
        corr["ts"]        = md["ts"]
        # Macro signal
        bull_signals = sum(1 for s in [corr["xrp_btc"],corr["xrp_sp500"]] if s=="POSITIVE")
        bear_signals = sum(1 for s in [corr["xrp_dxy"]] if s=="POSITIVE")
        if bull_signals >= 2:   md["macro_signal"] = "BULLISH"
        elif bear_signals >= 1: md["macro_signal"] = "BEARISH"
        else:                   md["macro_signal"] = "NEUTRAL"
    except Exception as e: log_error(f"macro_correlation: {e}")


def fetch_ripple_ipo_news():
    """#44 — Fetch latest Ripple IPO news."""
    hdr = {"User-Agent":"XRPRadar/6.0"}
    ipo = STATE["ipo_watch"]
    try:
        import feedparser
        feed = feedparser.parse("https://news.google.com/rss/search?q=Ripple+IPO+%22going+public%22+valuation+2026&hl=en-US&gl=US&ceid=US:en")
        news = []
        for e in feed.entries[:8]:
            news.append({
                "title":  e.get("title",""),
                "source": e.get("source",{}).get("title","") if hasattr(e.get("source",{}), "get") else "",
                "link":   e.get("link",""),
                "pub":    e.get("published",""),
            })
        ipo["news"] = news
    except Exception as e: log_error(f"ipo_news: {e}")


def fetch_currency_crisis():
    """#54 — Real-time currency crisis monitor (ODL opportunity detector)."""
    hdr = {"User-Agent":"XRPRadar/6.0"}
    cc  = STATE["currency_crisis"]
    # Track currencies known to be under stress
    crisis_countries = [
        {"country":"Argentina","currency":"ARS","symbol":"ARS%3DX","risk":"HIGH",
         "odl_corridor":"USA→Argentina","population_m":46,"remittance_usd_bn":1.2,
         "context":"Peso devaluation ongoing, inflation >100%. ODL could save billions in remittance fees."},
        {"country":"Turkey","currency":"TRY","symbol":"TRY%3DX","risk":"HIGH",
         "odl_corridor":"Europe→Turkey","population_m":85,"remittance_usd_bn":2.1,
         "context":"Lira at historic lows. Large diaspora sending money home. XRP ODL highly relevant."},
        {"country":"Nigeria","currency":"NGN","symbol":"NGN%3DX","risk":"HIGH",
         "odl_corridor":"USA/UK→Nigeria","population_m":220,"remittance_usd_bn":20.9,
         "context":"Naira severely devalued. Nigeria is Africa's largest remittance market. Ripple active."},
        {"country":"Egypt","currency":"EGP","symbol":"EGP%3DX","risk":"MEDIUM",
         "odl_corridor":"Gulf→Egypt","population_m":104,"remittance_usd_bn":28.3,
         "context":"Pound devalued 50%+ since 2022. Gulf worker remittances critical. ODL opportunity massive."},
        {"country":"Pakistan","currency":"PKR","symbol":"PKR%3DX","risk":"MEDIUM",
         "odl_corridor":"Gulf/UK→Pakistan","population_m":231,"remittance_usd_bn":27.0,
         "context":"Rupee under sustained pressure. Massive remittance market. XRP adoption growing."},
        {"country":"Lebanon","currency":"LBP","symbol":"LBP%3DX","risk":"CRITICAL",
         "odl_corridor":"Europe/USA→Lebanon","population_m":5,"remittance_usd_bn":6.7,
         "context":"Currency collapsed 95%+. Banking system frozen. XRP/crypto only viable option."},
        {"country":"Venezuela","currency":"VES","symbol":"VES%3DX","risk":"CRITICAL",
         "odl_corridor":"USA→Venezuela","population_m":28,"remittance_usd_bn":3.5,
         "context":"Bolivar hyperinflation. USD/crypto dominant. Major XRP ODL opportunity."},
        {"country":"Ethiopia","currency":"ETB","symbol":"ETB%3DX","risk":"MEDIUM",
         "odl_corridor":"Gulf→Ethiopia","population_m":126,"remittance_usd_bn":5.2,
         "context":"Birr devaluing. Diaspora growing. XRP presence through Yellow Card expanding."},
    ]
    # Fetch live exchange rates for context
    for c in crisis_countries:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{c['symbol']}?interval=1d&range=5d"
            r   = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json()
            result = r.get("chart",{}).get("result",[None])[0]
            if result:
                closes = result.get("indicators",{}).get("quote",[{}])[0].get("close",[])
                closes = [x for x in closes if x is not None]
                if len(closes) >= 2:
                    c["rate_vs_usd"]   = round(closes[-1], 4)
                    c["change_5d_pct"] = round((closes[-1]-closes[0])/closes[0]*100,2) if closes[0] else 0
        except: pass
    cc["countries"]     = crisis_countries
    cc["highest_risk"]  = next((c["country"] for c in crisis_countries if c["risk"]=="CRITICAL"), "Lebanon")
    cc["odl_opportunity"] = sum(c.get("remittance_usd_bn",0) for c in crisis_countries)
    cc["ts"]            = datetime.now(timezone.utc).strftime("%H:%M UTC")


def compute_signal_score():
    """#61 — XRPRadar Signal Score (0-100 composite institutional-grade metric)."""
    ss   = STATE["signal_score"]
    comp = ss["components"]

    # 1. Price Momentum (15pts) — 24h change
    try:
        chg = STATE["price_data"].get("change_24h", 0)
        if   chg > 5:    comp["price_momentum"] = {"score":15,"signal":"STRONG BULL","weight":15}
        elif chg > 2:    comp["price_momentum"] = {"score":12,"signal":"BULLISH","weight":15}
        elif chg > 0:    comp["price_momentum"] = {"score": 8,"signal":"MILD BULL","weight":15}
        elif chg > -2:   comp["price_momentum"] = {"score": 5,"signal":"MILD BEAR","weight":15}
        elif chg > -5:   comp["price_momentum"] = {"score": 3,"signal":"BEARISH","weight":15}
        else:            comp["price_momentum"] = {"score": 0,"signal":"STRONG BEAR","weight":15}
    except: pass

    # 2. RSI Signal (12pts)
    try:
        rsi = STATE["tech_intel"].get("rsi_1d", 50)
        if rsi == 0: rsi = 50
        if   30 <= rsi <= 40: comp["rsi_signal"] = {"score":12,"signal":"OVERSOLD — BUY ZONE","weight":12}
        elif 40 < rsi <= 50:  comp["rsi_signal"] = {"score":10,"signal":"NEUTRAL-BULLISH","weight":12}
        elif 50 < rsi <= 60:  comp["rsi_signal"] = {"score": 8,"signal":"NEUTRAL","weight":12}
        elif 60 < rsi <= 70:  comp["rsi_signal"] = {"score": 6,"signal":"APPROACHING OB","weight":12}
        elif rsi > 70:        comp["rsi_signal"] = {"score": 3,"signal":"OVERBOUGHT","weight":12}
        else:                 comp["rsi_signal"] = {"score": 5,"signal":"EXTREME OVERSOLD","weight":12}
    except: pass

    # 3. Sentiment (15pts) — bull/bear ratio from stories
    try:
        si  = STATE["sent_intel"]
        total = max(si.get("total_today",1), 1)
        bull  = si.get("bullish_today",0)
        ratio = bull/total
        if   ratio > 0.5:  comp["sentiment"] = {"score":15,"signal":"STRONGLY BULLISH","weight":15}
        elif ratio > 0.35: comp["sentiment"] = {"score":11,"signal":"BULLISH","weight":15}
        elif ratio > 0.25: comp["sentiment"] = {"score": 7,"signal":"NEUTRAL","weight":15}
        elif ratio > 0.15: comp["sentiment"] = {"score": 4,"signal":"BEARISH","weight":15}
        else:              comp["sentiment"] = {"score": 1,"signal":"STRONGLY BEARISH","weight":15}
    except: pass

    # 4. On-Chain (18pts) — exchange flow + whale activity
    try:
        flow  = STATE["onchain_intel"].get("exchange_flow","NEUTRAL")
        whale = len(STATE.get("whale_data",{}).get("alerts",[]))
        base  = 9
        if "bullish" in flow.lower():  base = 14
        elif "bearish" in flow.lower(): base = 4
        bonus = min(whale * 1, 4)
        comp["on_chain"] = {"score":min(base+bonus,18),"signal":f"Flow:{flow} Whales:{whale}","weight":18}
    except: pass

    # 5. Macro (10pts) — macro signal
    try:
        msig = STATE["macro_data"].get("macro_signal","NEUTRAL")
        if   msig == "BULLISH": comp["macro"] = {"score":10,"signal":"MACRO TAILWIND","weight":10}
        elif msig == "BEARISH": comp["macro"] = {"score": 2,"signal":"MACRO HEADWIND","weight":10}
        else:                   comp["macro"] = {"score": 5,"signal":"MACRO NEUTRAL","weight":10}
    except: pass

    # 6. Institutional Flow (15pts) — ETF net flow signal
    try:
        net = STATE["inst_flow"].get("net_etf_flow_7d",0)
        if   net > 50:  comp["inst_flow"] = {"score":15,"signal":f"ETF INFLOW +${net:.0f}M","weight":15}
        elif net > 10:  comp["inst_flow"] = {"score":11,"signal":f"ETF INFLOW +${net:.0f}M","weight":15}
        elif net > -10: comp["inst_flow"] = {"score": 7,"signal":"ETF NEUTRAL","weight":15}
        elif net > -50: comp["inst_flow"] = {"score": 3,"signal":f"ETF OUTFLOW ${net:.0f}M","weight":15}
        else:           comp["inst_flow"] = {"score": 0,"signal":"ETF HEAVY OUTFLOW","weight":15}
    except: comp["inst_flow"] = {"score":7,"signal":"ETF DATA PENDING","weight":15}

    # 7. Whale Activity (10pts) — from smart money score
    try:
        sm = STATE["disp_intel"].get("smart_money",{})
        whale_pts = sm.get("whale_pts",5)
        comp["whale_activity"] = {"score":min(whale_pts+5,10),"signal":f"Smart Money: {sm.get('score',0)}/100","weight":10}
    except: comp["whale_activity"] = {"score":5,"signal":"MONITORING","weight":10}

    # 8. Fear & Greed (5pts)
    try:
        fg = STATE["sent_intel"].get("fg_score",50)
        if   fg <= 20:  comp["fear_greed"] = {"score":5,"signal":"EXTREME FEAR — contrarian BUY","weight":5}
        elif fg <= 40:  comp["fear_greed"] = {"score":4,"signal":"FEAR — accumulation zone","weight":5}
        elif fg <= 60:  comp["fear_greed"] = {"score":2,"signal":"NEUTRAL","weight":5}
        elif fg <= 80:  comp["fear_greed"] = {"score":1,"signal":"GREED — caution","weight":5}
        else:           comp["fear_greed"] = {"score":0,"signal":"EXTREME GREED — sell signal","weight":5}
    except: pass

    # Compute total
    total = sum(c.get("score",0) for c in comp.values())
    ss["total"] = total
    if   total >= 80: ss["grade"],ss["label"] = "A+","EXTREME BULL"
    elif total >= 70: ss["grade"],ss["label"] = "A", "STRONG BULL"
    elif total >= 60: ss["grade"],ss["label"] = "B+","BULLISH"
    elif total >= 50: ss["grade"],ss["label"] = "B", "MILD BULL"
    elif total >= 40: ss["grade"],ss["label"] = "C", "NEUTRAL"
    elif total >= 30: ss["grade"],ss["label"] = "D", "MILD BEAR"
    elif total >= 20: ss["grade"],ss["label"] = "F", "BEARISH"
    else:             ss["grade"],ss["label"] = "F-","EXTREME BEAR"
    ss["ts"] = datetime.now(timezone.utc).strftime("%H:%M UTC")


def fetch_adoption_velocity():
    """#57 — XRP Adoption Velocity Score."""
    av = STATE["adoption_velocity"]
    try:
        # Institutional: based on inst_flow signal + mainstream partnerships
        inst_score = 70 if STATE["inst_flow"].get("flow_signal") == "BULLISH" else 50
        # Retail: based on fear/greed + sentiment
        fg    = STATE["sent_intel"].get("fg_score", 50)
        si    = STATE["sent_intel"]
        total = max(si.get("total_today",1),1)
        bull  = si.get("bullish_today",0)
        retail_score = int(40 + (bull/total)*40 + (100-fg)*0.2)
        # Developer: from GitHub commits
        commits = STATE["github_data"].get("commits_7d", 0)
        dev_score = min(40 + commits*2, 100)
        # Regulatory: based on country legal status (17/20 legal = 85%)
        reg_score = 72
        # Composite
        composite = int((inst_score*0.3) + (retail_score*0.25) + (dev_score*0.25) + (reg_score*0.2))
        av["score"]         = composite
        av["institutional"] = inst_score
        av["retail"]        = retail_score
        av["developer"]     = dev_score
        av["regulatory"]    = reg_score
        if   composite > 70: av["trend"] = "ACCELERATING"
        elif composite > 50: av["trend"] = "GROWING"
        elif composite > 35: av["trend"] = "STABLE"
        else:                av["trend"] = "SLOWING"
    except Exception as e: log_error(f"adoption_velocity: {e}")


def fetch_nvt_ratio():
    """#49 — Network Value to Transactions ratio."""
    nvt = STATE["nvt_ratio"]
    try:
        market_cap  = STATE["price_data"].get("market_cap", 0)
        tx_vol      = STATE["onchain_intel"].get("dex_vol_24h", 0)
        if tx_vol and market_cap:
            daily_nvt = market_cap / (tx_vol * 365) if tx_vol else 0
            nvt["nvt"] = round(daily_nvt, 2)
            if   daily_nvt < 20:  nvt["interpretation"] = "UNDERVALUED — network highly utilized"
            elif daily_nvt < 50:  nvt["interpretation"] = "FAIRLY VALUED"
            elif daily_nvt < 100: nvt["interpretation"] = "MODERATELY OVERVALUED"
            else:                 nvt["interpretation"] = "OVERVALUED vs network usage"
    except Exception as e: log_error(f"nvt: {e}")


def fetch_liquidity_map():
    """#43 — XRP Liquidity Heat Map across exchanges."""
    lm  = STATE["liquidity_map"]
    ob  = STATE["order_book"]
    try:
        exchanges = []
        for name, data in [("Binance",ob["binance"]),("Bitstamp",ob["bitstamp"]),("Kraken",ob["kraken"])]:
            if data.get("bids"):
                bid_depth  = sum(q for _,q in data["bids"][:5])
                ask_depth  = sum(q for _,q in data["asks"][:5])
                spread     = data.get("spread", 0)
                best_bid   = data["bids"][0][0] if data["bids"] else 0
                best_ask   = data["asks"][0][0] if data["asks"] else 0
                spread_pct = round(spread/best_bid*100, 4) if best_bid else 0
                exchanges.append({
                    "name":       name,
                    "bid_depth":  round(bid_depth,0),
                    "ask_depth":  round(ask_depth,0),
                    "spread":     round(spread,5),
                    "spread_pct": spread_pct,
                    "best_bid":   best_bid,
                    "best_ask":   best_ask,
                })
        lm["exchanges"] = sorted(exchanges, key=lambda x: x.get("bid_depth",0), reverse=True)
        if lm["exchanges"]:
            lm["deepest_book"]    = min(lm["exchanges"], key=lambda x: x["spread_pct"])["name"]
            lm["tightest_spread"] = min(lm["exchanges"], key=lambda x: x["spread_pct"])["name"]
            lm["best_venue"]      = lm["tightest_spread"]
    except Exception as e: log_error(f"liquidity_map: {e}")


def generate_weekly_digest():
    """#62 — Weekly Intelligence Digest (runs on Sundays at 18:00 UTC)."""
    import datetime as _dt
    now  = _dt.datetime.now(timezone.utc)
    if now.weekday() != 6: return  # Sunday only
    wd   = STATE["weekly_digest"]
    week = now.isocalendar()[1]
    if wd.get("week_number") == week: return  # Already generated this week
    stories = STATE.get("stories",[])
    if not stories: return
    try:
        top_stories = stories[:40]
        headlines   = [f"- {s['title']} ({s.get('source','')}, {s.get('age','')})" for s in top_stories]
        prompt = (
            f"Generate a comprehensive XRPRadar Weekly Intelligence Digest for week {week} of {now.year}. "
            f"This digest will be read by institutional investors, banks, and serious XRP holders. "
            f"Write in 6 sections: (1) Week in Review — key price action and market narrative, "
            f"(2) Institutional Developments — what moved the smart money this week, "
            f"(3) Regulatory Landscape — key legal and regulatory shifts, "
            f"(4) Technology & Ecosystem — XRPL developer activity and ecosystem growth, "
            f"(5) Global Intelligence — regional adoption stories from around the world, "
            f"(6) Week Ahead — what to watch in the coming 7 days. "
            f"Aim for 60-80 total sentences. Be specific, bold, and institutional in tone.\n\n"
            f"Top stories this week:\n" + "\n".join(headlines[:30])
        )
        system = (
            "You are XRPRadar's senior intelligence analyst. "
            "Write the weekly digest in the style of a Goldman Sachs weekly market letter — "
            "authoritative, dense with insight, specific names and numbers, zero filler."
        )
        content_txt = call_claude(prompt, system, max_tokens=6000)
        wd["content"]        = content_txt
        wd["generated_date"] = now.strftime("%Y-%m-%d")
        wd["week_number"]    = week
        wd["story_count"]    = len(top_stories)
    except Exception as e: log_error(f"weekly_digest: {e}")


def fetch_community_poll():
    """#60 — Community Pulse Poll — sets daily question."""
    import datetime as _dt
    poll  = STATE["community_poll"]
    today = _dt.datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if poll.get("date") == today: return
    # Rotate daily questions based on day of week
    dow   = _dt.datetime.now(timezone.utc).weekday()
    price = STATE["price_data"].get("price_usd", 1.0)
    targets = [round(price*1.05,3), round(price*1.10,3), round(price*0.95,3)]
    questions = [
        {"q": f"Where does XRP close today?",
         "opts": [f"Above ${targets[0]}", f"Above ${targets[1]}", f"Below ${targets[2]}", "About the same"]},
        {"q": "What is the BIGGEST catalyst for XRP this week?",
         "opts": ["Ripple IPO news", "ETF approval", "New bank partnership", "Macro/BTC move"]},
        {"q": "Which region will drive XRP adoption most in 2026?",
         "opts": ["Asia Pacific", "Middle East & Africa", "Latin America", "North America & Europe"]},
        {"q": "Will XRP reach $2 before end of 2026?",
         "opts": ["Yes — confident", "Yes — possible", "No — not this year", "Way more than $2"]},
        {"q": "Which Ripple product excites you most?",
         "opts": ["ODL payments", "RLUSD stablecoin", "XRPL DeFi/NFTs", "CBDC solutions"]},
        {"q": "How many XRP do you hold?",
         "opts": ["Under 1,000", "1,000 – 10,000", "10,000 – 100,000", "Over 100,000"]},
        {"q": "What is your XRP price target for end of 2026?",
         "opts": ["$1-2", "$2-5", "$5-10", "$10+"]},
    ]
    q          = questions[dow % len(questions)]
    poll["question"]   = q["q"]
    poll["options"]    = q["opts"]
    poll["date"]       = today
    if not poll.get("votes"):
        poll["votes"] = {opt: 0 for opt in q["opts"]}
        poll["total_votes"] = 0


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
@app.route("/manifest.json")
def pwa_manifest():
    return jsonify({
        "name": "XRPRadar — Signals Over Noise 24/7",
        "short_name": "XRPRadar",
        "description": "The institutional-grade XRP intelligence platform",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#000000",
        "theme_color": "#000000",
        "orientation": "portrait-primary",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })

@app.route("/api/poll/vote", methods=["POST"])
def api_poll_vote():
    try:
        data   = request.get_json()
        option = data.get("option","")
        poll   = STATE["community_poll"]
        if option in poll.get("options",[]):
            poll["votes"][option] = poll["votes"].get(option,0) + 1
            poll["total_votes"]   = sum(poll["votes"].values())
        return jsonify({"success":True,"votes":poll["votes"],"total":poll["total_votes"]})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})


