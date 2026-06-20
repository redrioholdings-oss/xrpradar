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
BOT_FILE          = "XRPRadar_v2.0"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
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
    "Southeast Asia": ["singapore","thailand","vietnam","philippines","indonesia","malaysia","myanmar","sea"],
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
    {"name": "GN: XRP Treasury",       "url": "https://news.google.com/rss/search?q=XRP+%22US+Treasury%22+FinCEN+crypto",    "type": "legal",        "region": "US",    "filter": False},
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

]

REGIONS = ["Japan","Korea","UAE","Europe","India","LatAm","Africa","SEA"]

# ── State ──────────────────────────────────────────────────────────────────────
STATE = {
    "price":         {},
    "fear_greed":    {},
    "escrow":        {},
    "onchain":       {},
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
        STATE["stories_by_region"][r] = [s for s in STATE["stories"][:100] if s.get("region") == r][:20]

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
def call_claude(prompt, system_prompt, max_tokens=500):
    if not ANTHROPIC_API_KEY:
        return "Add ANTHROPIC_API_KEY to Railway Variables to enable AI briefings."
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},
            json={"model":"claude-sonnet-4-6","max_tokens":max_tokens,"system":system_prompt,"messages":[{"role":"user","content":prompt}]},
            timeout=30)
        data = r.json()
        return data.get("content",[{}])[0].get("text","No response")
    except Exception as e:
        log_error(f"Claude API: {e}")
        return "AI briefing temporarily unavailable."

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
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    if v >= 1e3:  return f"${v/1e3:.2f}K"
    return f"${v:.4f}"

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/ping")
def ping():
    return "XRPRadar v1.1 OK", 200

@app.route("/api/data")
def api_data():
    return jsonify({
        "price":            STATE["price"],
        "fear_greed":       STATE["fear_greed"],
        "escrow":           STATE["escrow"],
        "onchain":          STATE["onchain"],
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
        "stories_count": len(STATE["stories"]),
        "price_usd":     STATE["price"].get("usd", 0),
        "ai_key_set":    bool(ANTHROPIC_API_KEY),
        "qa_status":     STATE["qa_status"],
        "last_error":    STATE["last_error"],
        "uptime_secs":   int((datetime.now(timezone.utc) - datetime.fromisoformat(STATE["start_time"])).total_seconds()),
        "feed_health":   STATE["feed_health"],
    })

@app.route("/")
def index():
    return Response(DASHBOARD, mimetype="text/html")

# ── Dashboard HTML ─────────────────────────────────────────────────────────────
DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
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
body{background:var(--bg);color:var(--tx);font-family:system-ui,sans-serif;min-height:100vh}
.w{max-width:1100px;margin:0 auto;padding:10px 12px}
/* HEADER */
.hdr{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:10px;padding-bottom:8px;border-bottom:2px solid var(--bl);flex-wrap:wrap;gap:6px}
.logo{display:flex;align-items:center;gap:10px}
.icon{width:60px;height:60px;border-radius:10px;
  background:linear-gradient(135deg,#001a3a,#0066cc,#75bcff);
  display:flex;align-items:center;justify-content:center;font-size:36px;
  box-shadow:0 0 16px rgba(117,188,255,.4)}
.title{font-size:22px;font-weight:900;color:var(--br);font-style:italic}
.sub{font-size:12px;font-family:var(--mn);color:var(--tx);margin-top:2px;letter-spacing:1px}
.hright{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.dot{width:12px;height:12px;border-radius:50%;background:var(--gr);
  box-shadow:0 0 10px var(--gr);display:inline-block;animation:blink 2s infinite}
@keyframes blink{50%{opacity:.1}}
.run-lbl{font-size:15px;font-weight:800;font-family:var(--mn);color:var(--gr);letter-spacing:1px}
.pill{padding:5px 14px;border-radius:20px;font-size:13px;font-family:var(--mn);
  font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.plive{background:var(--grd);color:var(--gr);border:1px solid rgba(72,255,130,.4)}
.pbl{background:var(--bld);color:var(--bl);border:1px solid rgba(117,188,255,.4)}
.upd{font-family:var(--mn);font-size:12px;color:var(--tx)}
/* STATUS ROW */
.srow{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}
.si{background:var(--s1);border:1px solid var(--b);border-radius:8px;
  padding:10px 14px;display:flex;align-items:center;justify-content:space-between}
.si-lbl{color:var(--tx);font-size:13px;font-family:var(--mn)}
.sv{font-weight:800;font-size:15px;font-family:var(--mn)}
.sv.g{color:var(--gr)}.sv.y{color:var(--yl)}.sv.b{color:var(--bl)}.sv.r{color:var(--rd)}
/* ACCOUNT / MARKET OVERVIEW */
.acct{background:var(--s1);border:1px solid rgba(117,188,255,.25);
  border-radius:10px;padding:12px;margin-bottom:10px}
.sec-title{font-size:16px;text-transform:uppercase;letter-spacing:2px;
  font-family:var(--mn);color:#ffffff;margin-bottom:10px;font-weight:800}
.agrid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
.abox{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:10px;text-align:center}
.abox.hi{border-color:rgba(117,188,255,.4);background:var(--bld)}
.abox.pos{border-color:rgba(72,255,130,.3);background:var(--grd)}
.abox.neg{border-color:rgba(255,64,96,.3);background:var(--rdd)}
.abox.yl{border-color:rgba(255,204,0,.3);background:var(--yld)}
.albl{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;
  font-family:var(--mn);color:var(--tx);margin-bottom:5px}
.aval{font-size:22px;font-weight:900;font-family:var(--mn);color:var(--br);line-height:1}
.aval.g{color:var(--gr)}.aval.r{color:var(--rd)}.aval.y{color:var(--yl)}.aval.b{color:var(--bl)}
.asub{font-size:11px;font-family:var(--mn);color:var(--tx);margin-top:4px}
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
.sbadge{font-size:11px;font-family:var(--mn);font-weight:700;padding:3px 7px;
  border-radius:3px;text-transform:uppercase;margin-left:auto;white-space:nowrap}
.sbadge.bull{background:var(--grd);color:var(--gr);border:1px solid rgba(72,255,130,.4)}
.sbadge.bear{background:var(--rdd);color:var(--rd);border:1px solid rgba(255,64,96,.3)}
.sbadge.neut{background:rgba(128,153,179,.08);color:var(--tx);border:1px solid var(--b)}
.sbadge.quiet{background:rgba(128,153,179,.05);color:var(--tx);border:1px solid var(--b)}
.sstrat{font-size:12px;font-family:var(--mn);font-weight:800;text-transform:uppercase;margin-bottom:4px;letter-spacing:.5px;color:var(--bl)}
.swl{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:4px 0}
.swbox{background:var(--s2);border:1px solid var(--b);border-radius:4px;padding:4px;text-align:center}
.swval{font-size:16px;font-weight:900;font-family:var(--mn);line-height:1;color:var(--br)}
.swlbl{font-size:10px;text-transform:uppercase;font-family:var(--mn);color:var(--tx);font-weight:700}
.sact{font-family:system-ui;font-size:13px;color:var(--br);
  word-break:break-word;line-height:1.4;min-height:18px;margin-top:4px}
.sfoot{display:flex;justify-content:space-between;margin-top:4px;
  padding-top:4px;border-top:1px solid rgba(255,255,255,.05);
  font-family:var(--mn);font-size:11px;font-weight:600;color:var(--tx)}
/* SCOREBOARD */
.score{background:var(--s1);border:1px solid var(--b);border-radius:10px;
  padding:12px;margin-bottom:10px;width:100%;box-sizing:border-box}
.sgrid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
.sbox{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:10px;text-align:center}
.sbox.wc{border-color:rgba(72,255,130,.3);background:var(--grd)}
.sbox.lc{border-color:rgba(255,64,96,.3);background:var(--rdd)}
.sbox.bc{border-color:rgba(117,188,255,.3);background:var(--bld)}
.sbox.yc{border-color:rgba(255,204,0,.3);background:var(--yld)}
.snum{font-size:22px;font-weight:900;font-family:var(--mn);line-height:1}
.snum.g{color:var(--gr)}.snum.r{color:var(--rd)}.snum.b{color:var(--bl)}.snum.y{color:var(--yl)}
.snlbl{font-size:10px;text-transform:uppercase;font-family:var(--mn);color:var(--tx);margin-top:4px}
.snsub{font-size:9px;font-family:var(--mn);color:var(--tx);margin-top:3px}
.sgrid4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
.wrbar{height:6px;background:var(--rdd);border-radius:3px;overflow:hidden;margin-top:10px}
.wrfill{height:100%;background:linear-gradient(90deg,var(--gr),#00ffcc);transition:width .8s}
/* TWO-COLUMN */
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.panel{background:var(--s1);border:1px solid var(--b);border-radius:10px;overflow:hidden}
.ph{padding:8px 14px;border-bottom:1px solid var(--b);
  display:flex;justify-content:space-between;align-items:center;background:var(--s2)}
.pt{font-size:12px;text-transform:uppercase;letter-spacing:2px;font-family:var(--mn);color:var(--tx)}
.pcard{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.03)}
.prow{display:flex;justify-content:space-between;padding:3px 0;font-family:var(--mn);font-size:12px}
.pk{color:var(--tx)}.pv{font-weight:700;color:var(--br)}
.pv.g{color:var(--gr)}.pv.r{color:var(--rd)}.pv.b{color:var(--bl)}.pv.y{color:var(--yl)}
.alog{max-height:300px;overflow-y:auto;padding:6px 14px;font-family:var(--mn);font-size:12px}
.lr{display:flex;gap:8px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.02)}
.lt{color:var(--tx);opacity:.5;font-size:10px;white-space:nowrap}
.lm{flex:1;color:var(--br)}
.lm.bull{color:var(--gr)}.lm.bear{color:var(--rd)}.lm.break{color:var(--yl)}
/* NEWS FEED */
.nrow{display:grid;grid-template-columns:1fr 340px;gap:10px;margin-bottom:10px}
.npanel{background:var(--s1);border:1px solid var(--b);border-radius:10px;overflow:hidden}
.nfeed{max-height:520px;overflow-y:auto;padding:8px 12px}
.ncard{background:var(--s2);border:1px solid var(--b);border-radius:6px;
  padding:9px;margin-bottom:7px;cursor:pointer;transition:border-color .2s}
.ncard:hover{border-color:var(--bl)}
.ncard-hdr{display:flex;align-items:center;gap:5px;margin-bottom:5px;flex-wrap:wrap}
.nsrc{font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;font-family:var(--mn)}
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
.ncat{font-size:10px;color:var(--tx);background:var(--s1);padding:2px 5px;border-radius:3px;font-family:var(--mn)}
.nbreak{font-size:10px;color:var(--yl);font-weight:700;font-family:var(--mn)}
.ntitle{font-size:14px;font-weight:700;color:var(--bl);line-height:1.4;margin-bottom:5px}
.ntrans{font-size:12px;color:var(--tq);font-family:system-ui;margin-bottom:5px;font-style:italic;padding:4px 8px;background:var(--tqd);border-left:2px solid var(--tq);border-radius:3px}
.nsum{font-size:12px;color:var(--br);line-height:1.7;margin-bottom:6px}
.nfoot{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.nsent{font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;font-family:var(--mn)}
.nsent.bull{background:var(--grd);color:var(--gr);border:1px solid rgba(72,255,130,.3)}
.nsent.bear{background:var(--rdd);color:var(--rd);border:1px solid rgba(255,64,96,.2)}
.nsent.neut{background:rgba(128,153,179,.08);color:var(--tx);border:1px solid var(--b)}
.nage{font-size:10px;color:var(--b);margin-left:auto;font-family:var(--mn)}
.ncount{font-size:12px;color:var(--tx);padding:6px 12px 8px;font-family:var(--mn)}
/* SEARCH + FILTERS */
.nctrl{padding:8px 12px;border-bottom:1px solid var(--b);background:var(--s2);display:flex;flex-direction:column;gap:6px}
.nsearch{width:100%;background:var(--bg);border:1px solid var(--b);color:var(--br);
  padding:10px 16px;border-radius:5px;font-size:14px;font-family:var(--mn);outline:none}
.nsearch:focus{border-color:var(--bl)}
.nbtns{display:flex;gap:5px;flex-wrap:nowrap}
.nbtn{background:var(--s2);border:1px solid var(--b);color:var(--br);
  padding:7px 14px;border-radius:5px;cursor:pointer;font-size:12px;font-weight:700;
  font-family:var(--mn);letter-spacing:.05em;text-transform:uppercase;transition:all .2s;white-space:nowrap}
.nbtn:hover,.nbtn.on{background:var(--bld);border-color:var(--bl);color:var(--bl)}
/* RIGHT PANEL */
.rpanel{background:var(--s1);border:1px solid var(--b);border-radius:10px;overflow:hidden}
.rcard{padding:10px 14px;border-bottom:1px solid var(--b)}
.rtitle{font-size:12px;text-transform:uppercase;letter-spacing:2px;font-family:var(--mn);color:#ffffff;margin-bottom:10px;font-weight:700}
.rrow{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.03);font-size:13px;align-items:center}
.rk{color:#ffffff;font-family:var(--mn);font-size:13px}.rv{color:var(--br);font-weight:700;font-family:var(--mn);font-size:13px}
.rv.g{color:var(--gr)}.rv.b{color:var(--bl)}.rv.r{color:var(--rd)}.rv.y{color:var(--yl)}
/* LEADERBOARDS */
.lbpair{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.lbrow{display:grid;grid-template-columns:24px 1fr 60px 60px;
  gap:6px;align-items:center;padding:5px 10px;
  border-bottom:1px solid rgba(255,255,255,.03);font-family:var(--mn);font-size:11px}
.lbrow.hdr{background:var(--s2);font-size:10px;color:var(--tx);
  text-transform:uppercase;border-bottom:1px solid var(--b)}
.rank{font-weight:900;text-align:center;font-size:12px}
.r1{color:#ffd700}.r2{color:#c0c0c0}.r3{color:#cd7f32}.rn{color:var(--or)}
/* ANALYTICS LAB */
.lab{background:var(--s1);border:1px solid rgba(0,229,204,.2);
  border-radius:10px;padding:14px;margin-bottom:10px}
.lab3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.labp{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:12px}
.labt{font-size:13px;font-weight:800;color:var(--bl);font-family:var(--mn);
  text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;
  padding-bottom:6px;border-bottom:1px solid var(--b)}
.bstat{display:flex;justify-content:space-between;padding:4px 0;
  border-bottom:1px solid rgba(255,255,255,.04);font-family:var(--mn);font-size:12px}
.bk{color:var(--tx)}.bv{font-weight:700;color:var(--br)}
.bv.g{color:var(--gr)}.bv.r{color:var(--rd)}.bv.b{color:var(--bl)}.bv.y{color:var(--yl)}
/* SIGNAL CHIPS */
.sig-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.sig-chip{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--br);
  background:var(--s2);padding:4px 8px;border-radius:4px;border:1px solid var(--b);font-family:var(--mn)}
.sdot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.sdot.g{background:var(--gr)}.sdot.r{background:var(--rd)}
.sdot.y{background:var(--yl)}.sdot.q{background:#333}
/* BREAKING NEWS */
#breaking{background:var(--s1);border-bottom:1px solid var(--b);
  padding:5px 0;display:none;align-items:center;overflow:hidden}
.bkinner{max-width:1100px;margin:0 auto;padding:0 12px;display:flex;align-items:center;width:100%}
.bklbl{color:var(--br);font-weight:700;font-size:10px;font-family:var(--mn);
  flex-shrink:0;padding-right:12px;border-right:1px solid var(--b);margin-right:12px;letter-spacing:.08em}
.bkscroll{flex:1;overflow:hidden;height:18px;position:relative}
.bktext{color:var(--tx);font-size:11px;font-family:var(--mn);white-space:nowrap;
  position:absolute;animation:marquee 40s linear infinite}
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
.modal-trans{color:var(--tq);font-size:12px;line-height:1.6;margin-bottom:12px;
  padding:8px 12px;background:var(--tqd);border-left:2px solid var(--tq);border-radius:3px;font-family:var(--mn)}
.modal-translbl{font-size:10px;color:var(--tx);margin-bottom:3px;text-transform:uppercase;letter-spacing:.06em;font-family:var(--mn)}
.modal-sum{color:var(--br);font-size:12px;line-height:1.8;margin-bottom:12px}
.modal-meta{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;font-size:11px;font-family:var(--mn)}
.modal-btn{display:block;width:100%;background:var(--bld);color:var(--bl);
  font-weight:700;font-size:12px;padding:10px;border-radius:6px;cursor:pointer;
  border:1px solid var(--bl);text-align:center;transition:all .2s;text-decoration:none;font-family:var(--mn)}
.modal-btn:hover{background:var(--bl);color:#000}

/* PRECHECK MODAL */
#pf-modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,.88);z-index:9999;align-items:center;justify-content:center;padding:20px}
#pf-box{background:var(--s1);border:1px solid var(--bl);border-radius:10px;
  max-width:560px;width:100%;padding:0;overflow:hidden}
#pf-hdr{padding:10px 16px;background:var(--s2);border-bottom:1px solid var(--b);
  display:flex;justify-content:space-between;align-items:center;font-family:var(--mn)}
#pf-body{padding:16px;font-family:var(--mn);font-size:12px;line-height:2.2}

/* FOOTER */
footer{margin-top:10px;padding-top:8px;border-top:1px solid var(--b);
  font-family:var(--mn);font-size:11px;color:var(--tx);line-height:2.2}
.warn{color:rgba(255,204,0,.4)}
.empty{padding:14px;font-family:var(--mn);font-size:11px;color:var(--tx);text-align:center}
.file-tag{display:inline-block;padding:2px 7px;border-radius:3px;
  background:rgba(117,188,255,.08);color:var(--bl);font-weight:700;
  border:1px solid rgba(117,188,255,.3);margin-left:6px;font-family:var(--mn)}
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
      <div class="sub" style="font-size:11px;color:var(--gr);letter-spacing:1px">● 230 Sources Live</div>
    </div>
  </div>
  <div class="hright">
    <span class="dot"></span>
    <span class="run-lbl">LIVE</span>
    <span class="pill plive" id="feedPill">FEEDS OK</span>
    <span class="upd" id="uts">&mdash;</span>
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

<!-- SECTION 5: US + GLOBAL INTELLIGENCE (2-column panel) -->
<div class="two">
  <div class="panel" id="ai-briefing-us">
    <div class="ph"><span class="pt" style="color:var(--bl);font-size:16px;font-weight:800;letter-spacing:2px">🇺🇸 US Intelligence</span><span style="font-size:10px;font-family:var(--mn);color:var(--tx)" id="ai-us-ts">--</span></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">US Pulse</div><div class="pv" id="ai-us-pulse" style="font-size:12px;line-height:1.7;font-family:system-ui">Fetching US intelligence...</div></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Regulatory</div><div class="pv" id="ai-us-reg" style="font-size:12px;line-height:1.7;font-family:system-ui">Loading...</div></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Institutional</div><div class="pv" id="ai-us-inst" style="font-size:12px;line-height:1.7;font-family:system-ui">Loading...</div></div>
  </div>
  <div class="panel">
    <div class="ph"><span class="pt" style="color:var(--gr);font-size:16px;font-weight:800;letter-spacing:2px">🌐 Global Pulse</span><span style="font-size:10px;font-family:var(--mn);color:var(--tx)" id="ai-gl-ts">--</span></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Global Summary</div><div class="pv g" id="ai-gl-pulse" style="font-size:12px;line-height:1.7;font-family:system-ui">Synthesizing global signals...</div></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Regional Signals</div><div id="ai-signals" class="sig-chips"><span class="empty">Loading...</span></div></div>
    <div class="pcard"><div class="albl" style="margin-bottom:4px">Cumulative Thesis</div><div style="font-size:12px;line-height:1.7;color:var(--gr);font-family:system-ui" id="ai-gl-thesis">Building analysis...</div></div>
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
      <div id="feed-list" style="max-height:200px;overflow-y:auto;overflow-x:hidden;scrollbar-width:thin;scrollbar-color:var(--b) transparent"></div>
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

<!-- FOOTER -->
<footer>
  <div>🛰️ <em style="color:var(--bl);font-weight:700">XRPRadar</em> &nbsp;|&nbsp; Version: <span id="ft-ver" style="color:var(--tq);font-weight:700">--</span> &nbsp;|&nbsp; Updated: <span id="ft-last" style="color:var(--br)">--</span> &nbsp;|&nbsp; Uptime: <span id="ft-uptime" style="color:var(--br)">--</span> &nbsp;&nbsp;<a href="/debug" target="_blank" style="color:var(--or);font-size:10px;font-weight:700;text-decoration:none;border:1px solid var(--or);padding:1px 6px;border-radius:3px">DEBUG</a></div>
  <div style="color:var(--yl)">⚠️ Not Financial Advice — XRPRadar is for informational purposes only. DYOR.</div>
  <div>Feeds: <span id="ft-feeds" style="color:var(--br)">--</span> &nbsp;|&nbsp; Maintenance: <span id="ft-maint" style="color:var(--br)">--</span> &nbsp;|&nbsp; Preflight: <span id="ft-qa-status" style="font-weight:700">--</span> &nbsp;&nbsp;<button onclick="openPFModal()" style="color:var(--bl);font-size:10px;font-weight:700;text-decoration:none;border:1px solid var(--bl);padding:1px 8px;border-radius:3px;background:var(--bld);cursor:pointer;font-family:var(--mn)">🔍 DETAILS</button></div>
  <div style="height:16px"></div>
</footer>

<!-- PRECHECK DETAILS MODAL -->
<div id="pf-modal" onclick="closePFModal(event)" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.88);z-index:9999;align-items:center;justify-content:center;padding:20px">
  <div id="pf-box" style="background:var(--s1);border:1px solid var(--bl);border-radius:10px;max-width:560px;width:100%;overflow:hidden" onclick="event.stopPropagation()">
    <div style="padding:10px 16px;background:var(--s2);border-bottom:1px solid var(--b);display:flex;justify-content:space-between;align-items:center;font-family:var(--mn)">
      <span style="color:var(--bl);font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:1px">🔍 Preflight / QA Details</span>
      <span onclick="closePFModal()" style="color:var(--bl);cursor:pointer;font-size:18px;border:1px solid var(--bl);width:26px;height:26px;display:flex;align-items:center;justify-content:center;border-radius:4px">✕</span>
    </div>
    <div style="padding:16px;font-family:var(--mn);font-size:12px;line-height:2.4">
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
    updateAI(d);
    updateScoreboard(d);
    updateAnalytics(d);
    updateRegions(d);
    updateRight(d);
    updateFooter(d);
    updateBreaking(d);
  }catch(e){console.error("fetchData:",e);}
}

async function fetchNews(){
  try{
    const d = await fetch("/api/news").then(r=>r.json());
    allStories = d.stories||[];
    allStories.forEach(s=>{storyData[s.id]=s;});
    renderNews(d.total_all||0);
  }catch(e){console.error("fetchNews:",e);}
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
  }
  c("st-feeds",`${d.feeds_active||0} / ${d.feeds_total||230} active`);
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
  c("mk-btc", p.btc?`₿ ${parseFloat(p.btc).toFixed(8)}`:"--");
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
  c("rm-btc",    p.btc?`₿ ${parseFloat(p.btc).toFixed(8)}`:"--");
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
    const d=await fetch(`/api/news?region=${reg}`).then(r=>r.json());
    const stories=(d.stories||[]).slice(0,5);
    const el=document.getElementById(`reg-stories-${reg}`);
    const cnt=document.getElementById(`reg-count-${reg}`);
    if(cnt) cnt.textContent=`${d.total||0} stories`;
    if(!el) return;
    if(!stories.length){el.innerHTML='<div style="font-size:10px;color:var(--tx);font-family:var(--mn)">No regional stories yet</div>';return;}
    el.innerHTML=stories.map(s=>{
      const trans=s.translated_title?`<div style="font-size:11px;color:var(--tq);font-style:italic;margin-top:3px;padding:3px 6px;background:var(--tqd);border-left:2px solid var(--tq);border-radius:2px">🌐 EN: ${s.translated_title}</div>`:(s.lang==="non-english"?`<div style="font-size:10px;color:var(--tx);font-style:italic;margin-top:2px">🌐 Translation pending...</div>`:"");
      const sent=s.sentiment==="bullish"?"g":s.sentiment==="bearish"?"r":"";
      return `<div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,.03);cursor:pointer" onclick="openStoryModal('${s.id}')">
        <div style="font-size:11px;font-weight:700;color:var(--bl);line-height:1.3">${s.title}</div>
        ${trans}
        <div style="font-size:10px;font-family:var(--mn);color:var(--tx);margin-top:2px">
          <span style="color:${sent==="g"?"var(--gr)":sent==="r"?"var(--rd)":"var(--tx)"};font-weight:700">${s.sentiment}</span>
          &nbsp;·&nbsp;${s.source}&nbsp;·&nbsp;${s.age||""}
        </div>
      </div>`;
    }).join("");
  }catch(e){}
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
    fl.innerHTML=entries.map(([name,status])=>
      `<div class="rrow"><span class="rk">${name}</span><span style="color:${status==="UP"?"var(--gr)":"var(--rd)"};">${status==="UP"?"●":"✗"}</span></div>`
    ).join("");
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
  if(cnt) cnt.innerHTML=`<span style="color:var(--bl);font-weight:700">${stories.length}</span> stories shown &nbsp;|&nbsp; <span style="color:var(--gr);font-weight:700">${tot}</span> total &nbsp;|&nbsp; <span style="color:var(--bl);font-weight:700">${faText}</span> of <span style="color:var(--gr);font-weight:700">230</span> sources online`;
  if(!stories.length){
    if(allStories.length===0){
      feed.innerHTML='<div class="empty" style="padding:20px;line-height:2">📡 Scanning 230 sources...<br>Stories will appear shortly after first feed scan completes.</div>';
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
    return `<div class="ncard" onclick="openStoryModal('${s.id}')">
      <div class="ncard-hdr">
        <span class="nsrc ${sc}">${s.source}</span>
        <span class="ncat">${s.category}</span>
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
fetchNews();
setInterval(fetchData,  60000);
setInterval(fetchNews, 600000);
setInterval(()=>REGIONS.forEach(({k})=>fetchRegionStories(k)), 600000);
// Retry news if still empty after 20 seconds (first scan takes time)
setTimeout(()=>{ if(allStories.length===0) fetchNews(); }, 20000);
setTimeout(()=>{ if(allStories.length===0) fetchNews(); }, 60000);
</script>
</body>
</html>
"""

# ── Startup ────────────────────────────────────────────────────────────────────
load_state()
threading.Thread(target=price_loop, daemon=True).start()
threading.Thread(target=news_loop,  daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
