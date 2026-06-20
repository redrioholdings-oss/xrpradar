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
BOT_FILE          = "XRPRadar_v1.3"
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
            trans_prompt = (f"Translate these news headlines to English. "
                           f"Reply ONLY with a JSON object mapping numbers to translated text:\n{titles_to_translate}")
            raw = call_claude(trans_prompt, "You are a translator. Reply only with valid JSON.", 300)
            raw = raw.strip().lstrip("```json").rstrip("```").strip()
            trans_map = json.loads(raw)
            for i, s in enumerate(foreign):
                key = str(i+1)
                if key in trans_map:
                    translations[s["id"]] = trans_map[key]
                    # Update story with translation
                    for story in STATE["stories"]:
                        if story["id"] == s["id"]:
                            story["translated_title"] = trans_map[key]
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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XRPRadar — Signals Over Noise 24/7</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#000000;
  --dark:#050505;
  --mid:#0A0A0A;
  --panel:#0D0D0D;
  --card:#111111;
  --tc:#75BCFF;
  --tcd:#5AA8FF;
  --lime:#48FF82;
  --org:#FF8C00;
  --gold:#C9A84C;
  --wht:#FFFFFF;
  --heather:#9FA8B3;
  --gray:#6B7280;
  --red:#FF4444;
  --ylw:#FFD700;
  --border:#1A2A1A;
}
body{background:var(--bg);color:var(--wht);font-family:Arial,sans-serif;font-size:14px;letter-spacing:.01em;-webkit-font-smoothing:antialiased}
a{color:var(--tc);text-decoration:none}
a:hover{text-decoration:underline;color:var(--lime)}

/* ── NAV ──────────────────────────────────────────────────────────── */
#nav{
  position:sticky;top:0;z-index:100;
  background:#000;border-bottom:2px solid var(--tc);
  display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;height:68px;
}
.nav-logo{display:flex;align-items:center;gap:14px}
.nav-sat{font-size:42px;filter:drop-shadow(0 0 10px var(--tc));line-height:1}
.nav-brand{}
.nav-name{font-size:28px;font-weight:900;color:var(--tc);letter-spacing:.06em;line-height:1}
.nav-tagline{font-size:13px;color:var(--lime);font-style:italic;margin-top:1px}
.nav-links{display:flex;gap:8px}
.nav-links a{
  background:#0A0A0A;border:1px solid #333;color:var(--heather);
  padding:6px 14px;border-radius:5px;cursor:pointer;
  font-size:12px;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;transition:all .2s;text-decoration:none;
}
.nav-links a:hover,.nav-links a.active{background:var(--tc);color:#000;border-color:var(--tc)}
.nav-live{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--heather)}
.live-dot{width:9px;height:9px;border-radius:50%;background:var(--lime);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 4px var(--lime)}50%{opacity:.4;box-shadow:none}}

/* ── BREAKING NEWS ────────────────────────────────────────────────── */
#breaking{
  background:#4B5563;
  border-top:1px solid #6B7280;border-bottom:1px solid #6B7280;
  padding:5px 20px;display:none;
  align-items:center;gap:0;overflow:hidden;
}
.breaking-label{
  color:#FFFFFF;font-weight:900;font-size:13px;
  flex-shrink:0;padding-right:14px;border-right:1px solid #9CA3AF;
  margin-right:14px;white-space:nowrap;letter-spacing:.04em;
}
.breaking-scroll{flex:1;overflow:hidden;position:relative;height:22px}
.breaking-text{
  color:#FFD0A0;font-size:13px;white-space:nowrap;
  position:absolute;top:0;left:0;
  animation:marquee 40s linear infinite;
}
@keyframes marquee{0%{transform:translateX(100%)}100%{transform:translateX(-100%)}}

/* ── SECTION TITLES ───────────────────────────────────────────────── */
.row-title{
  font-size:16px;font-weight:700;
  text-transform:uppercase;letter-spacing:.08em;
  margin-bottom:12px;color:var(--tc);
}
.section-wrap{padding:16px 20px;border-bottom:1px solid #111}

/* ── CARDS ────────────────────────────────────────────────────────── */
.card-grid{display:grid;gap:14px}
.g4{grid-template-columns:repeat(4,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g2{grid-template-columns:repeat(2,1fr)}
.card{
  background:var(--panel);border:1px solid #1E1E1E;
  border-radius:10px;padding:18px;
  position:relative;overflow:hidden;
}
.card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--tc)}
.card.lime::before{background:var(--lime)}
.card.org::before{background:var(--org)}
.card-label{
  font-size:12px;color:var(--tc);font-weight:700;
  text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;
}
.card-label.lime{color:var(--lime)}
.card-label.heather{color:var(--heather)}
.card-value{font-size:32px;font-weight:900;color:var(--wht);line-height:1.1}
.card-sub{font-size:14px;color:var(--gray);margin-top:6px}
.card-change{font-size:18px;font-weight:700;margin-top:6px}
.card-sm .card-value{font-size:28px}
.price-hero .card-value{font-size:38px}

/* ── CHART ────────────────────────────────────────────────────────── */
#chart-row{background:var(--dark);padding:16px 20px}
#tv-chart{width:100%;height:500px;border-radius:10px;overflow:hidden;border:1px solid #1E2E1E}
.tradingview-widget-container{width:100%;height:100%}

/* ── AI ROWS ──────────────────────────────────────────────────────── */
.ai-section{background:#070F0A;border-bottom:1px solid #111;padding:16px 20px}
.ai-badge{
  display:inline-block;padding:5px 14px;border-radius:5px;
  font-size:12px;font-weight:700;letter-spacing:.06em;margin-bottom:10px;
}
.ai-badge-tc{background:rgba(0,229,204,.15);color:var(--tc);border:1px solid var(--tc)}
.ai-badge-lime{background:rgba(57,255,20,.12);color:var(--lime);border:1px solid var(--lime)}
.ai-text{font-size:14px;color:#C8E8D8;line-height:1.7}
.ai-thesis{font-size:14px;color:var(--lime);line-height:1.7}
.ai-meta{font-size:12px;color:var(--gray);line-height:1.9}
.signal-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-top:6px}
.signal-chip{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--wht);background:#0A1A0A;padding:5px 8px;border-radius:5px}
.sig-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.sig-bull{background:var(--lime)}.sig-bear{background:var(--red)}
.sig-neut{background:var(--ylw)}.sig-quiet{background:#333}

/* ── REGIONAL ROWS ────────────────────────────────────────────────── */
.region-section{padding:14px 20px;border-bottom:1px solid #0A0A0A;background:var(--bg)}
.region-header{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.region-flag{font-size:22px}
.region-name{font-size:17px;font-weight:700;color:var(--tc)}
.region-pulse{font-size:13px;color:#A0C8A0;line-height:1.6;margin-bottom:8px}
.region-stories{display:flex;flex-direction:column;gap:6px}
.region-story{
  background:var(--panel);border:1px solid #161616;border-radius:6px;
  padding:8px 12px;cursor:pointer;transition:border-color .2s;
}
.region-story:hover{border-color:var(--tc)}
.region-story-title{font-size:13px;font-weight:600;color:var(--wht);line-height:1.4}
.region-story-title.foreign{color:#D0E8D0}
.region-story-translation{font-size:11px;color:var(--tc);margin-top:3px;font-style:italic}
.region-story-meta{display:flex;gap:8px;margin-top:5px;font-size:11px;align-items:center}
.region-sent{padding:2px 7px;border-radius:3px;font-weight:700}
.region-sent.bullish{background:#0A2A0A;color:var(--lime)}
.region-sent.bearish{background:#2A0A0A;color:var(--red)}
.region-sent.neutral{background:#1A1A1A;color:var(--gray)}
.region-age{color:#333;margin-left:auto}
.region-src{color:#444;font-size:10px}
.foreign-badge{
  font-size:10px;padding:1px 6px;border-radius:3px;
  background:rgba(0,229,204,.1);color:var(--tc);border:1px solid rgba(0,229,204,.3);
}

/* ── NEWS FEED ────────────────────────────────────────────────────── */
#insights-hdr{
  background:#050F05;padding:10px 20px;
  border-bottom:1px solid #111;
  display:flex;gap:20px;align-items:center;
}
.insights-label{font-size:14px;font-weight:700;color:var(--tc);text-transform:uppercase;letter-spacing:1px}
#main-content{display:grid;grid-template-columns:1fr 360px;gap:0;background:var(--bg)}
#news-panel{background:var(--bg);border-right:1px solid #111;padding:14px}
.news-controls{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center}
.search-box{
  flex:1;min-width:220px;
  background:#0A0A0A;border:2px solid var(--tc);
  color:var(--wht);padding:10px 16px;border-radius:6px;
  font-size:15px;outline:none;
}
.search-box:focus{border-color:var(--tc)}
.filter-btn{
  background:#0A0A0A;border:1px solid #222;color:var(--heather);
  padding:7px 14px;border-radius:5px;cursor:pointer;
  font-size:12px;font-weight:700;transition:all .2s;
}
.filter-btn:hover,.filter-btn.active{background:var(--tc);color:#000;border-color:var(--tc)}
#news-count{font-size:13px;color:var(--heather);padding:4px 0 10px}
.story-card{
  background:var(--panel);border:1px solid #1A1A1A;border-radius:8px;
  padding:12px;margin-bottom:10px;cursor:pointer;transition:border-color .2s;
}
.story-card:hover{border-color:var(--tc)}
.story-header{display:flex;align-items:center;gap:6px;margin-bottom:6px;flex-wrap:wrap}
.src-badge{font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px}
.src-official{background:#003366;color:#6699FF}
.src-major{background:#0A1A0A;color:var(--lime)}
.src-xrp{background:#001A18;color:var(--tc)}
.src-community{background:#1A1000;color:#FFA500}
.src-international{background:#0A001A;color:#CC99FF}
.src-aggregator{background:#0A0A00;color:#FFFF88}
.src-legal{background:#1A0000;color:#FF9999}
.src-mainstream{background:#000A1A;color:#88AAFF}
.src-institutional{background:#0A0A00;color:var(--gold)}
.src-whale{background:#001A00;color:var(--lime)}
.src-ecosystem{background:#001818;color:var(--tc)}
.src-technical{background:#0A001A;color:#BB88FF}
.story-title{font-size:15px;font-weight:700;color:var(--tc);line-height:1.5;margin-bottom:5px}
.story-title.foreign-title{color:#C8E8C8}
.story-translation{font-size:12px;color:var(--tc);font-style:italic;margin-bottom:5px}
.story-summary{font-size:13px;color:var(--wht);line-height:1.6;margin-bottom:6px}
.story-footer{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.sentiment-tag{font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px}
.sent-bullish{background:#051A05;color:var(--lime)}
.sent-bearish{background:#1A0505;color:var(--red)}
.sent-neutral{background:#111;color:var(--gray)}
.cat-tag{font-size:11px;color:#444;background:#0A0A0A;padding:2px 6px;border-radius:3px}
.story-age{font-size:12px;color:var(--heather);margin-left:auto}

/* ── RIGHT PANEL ──────────────────────────────────────────────────── */
#right-panel{background:var(--mid)}
.right-card{padding:14px;border-bottom:1px solid #111}
.right-title{font-size:13px;font-weight:700;color:var(--tc);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px}
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid #0A0A0A;font-size:13px}
.stat-label{color:var(--heather)}
.stat-val{color:var(--wht);font-weight:700}
.stat-val.tc{color:var(--tc)}
.stat-val.lime{color:var(--lime)}

/* ── SCOREBOARD ───────────────────────────────────────────────────── */
#scoreboard{background:var(--dark);padding:16px 20px;border-top:2px solid var(--tc)}
.score-title{font-size:18px;font-weight:700;color:var(--tc);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px}
.score-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.score-card{background:var(--panel);border:1px solid #1E1E1E;border-radius:8px;padding:14px;text-align:center}
.score-card.tc{border-top:3px solid var(--tc)}
.score-num{font-size:28px;font-weight:900;color:var(--wht)}
.score-num.tc{color:var(--tc)}
.score-num.lime{color:var(--lime)}
.score-num.red{color:var(--red)}
.score-lbl{font-size:12px;color:var(--heather);text-transform:uppercase;letter-spacing:1px;margin-top:3px}
.score-sub{font-size:12px;color:var(--gray);margin-top:4px}

/* ── ANALYTICS ────────────────────────────────────────────────────── */
.analytics-section{padding:16px 20px;background:var(--bg);border-top:1px solid #111}
.analytics-title{font-size:16px;font-weight:700;color:var(--lime);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px}
.analytics-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.analytics-card{background:var(--panel);border:1px solid #1A2A1A;border-radius:8px;padding:14px;text-align:center}
.analytics-card::before{content:"";display:block;height:2px;background:var(--lime);margin-bottom:10px;border-radius:1px}
.analytics-val{font-size:24px;font-weight:700;color:var(--wht)}
.analytics-lbl{font-size:11px;color:var(--heather);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.analytics-sub{font-size:11px;color:var(--gray);margin-top:3px}

/* ── FOOTER ───────────────────────────────────────────────────────── */
#footer{background:#020505;padding:16px 20px;border-top:2px solid #111}
.footer-grid{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:16px;margin-bottom:14px}
.footer-brand{font-size:22px;font-weight:900;color:var(--tc);margin-bottom:6px}
.footer-tagline{font-size:13px;color:var(--lime);font-style:italic;margin-bottom:8px}
.footer-txt{font-size:12px;color:var(--heather);line-height:1.9}
.footer-txt strong{color:var(--tc)}
.footer-disclaimer{font-size:11px;color:#444;line-height:1.8}
.footer-upgrade{margin-top:10px;border-top:1px solid #111;padding-top:10px}
.footer-upgrade-title{font-size:12px;font-weight:700;color:var(--heather);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.footer-upgrade-log{font-size:11px;color:#444;line-height:1.9}

/* ── SYSTEM HEALTH ────────────────────────────────────────────────── */
#sys-health{background:#020202;border-top:2px solid #1A2A00;display:grid;grid-template-columns:repeat(4,1fr)}
.sys-zone{padding:12px 16px;border-right:1px solid #0A1A00}
.sys-zone:last-child{border-right:none}
.sys-title{font-size:10px;font-weight:700;color:var(--heather);text-transform:uppercase;letter-spacing:1px;margin-bottom:5px}
.sys-val{font-size:14px;color:var(--wht);font-weight:700}
.sys-sub{font-size:11px;color:var(--gray);margin-top:3px;line-height:1.6}
.pass{color:var(--lime)}.fail{color:var(--red)}.warn{color:var(--ylw)}


/* ── STORY POPUP OVERLAY ──────────────────────────────────────────────────── */
#story-modal{
  display:none;position:fixed;top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,.95);z-index:9999;flex-direction:column;
}
.modal-header{
  background:#050505;padding:12px 20px;
  display:flex;align-items:center;gap:14px;
  border-bottom:2px solid var(--tc);flex-shrink:0;
}
.modal-close{
  color:var(--tc);font-size:26px;cursor:pointer;font-weight:900;
  width:36px;height:36px;display:flex;align-items:center;justify-content:center;
  border:2px solid var(--tc);border-radius:6px;flex-shrink:0;
  transition:all .2s;
}
.modal-close:hover{background:var(--tc);color:#000}
.modal-title{color:var(--wht);font-size:14px;font-weight:700;flex:1;line-height:1.4}
.modal-src{color:var(--tc);font-size:12px;flex-shrink:0}
.modal-open-btn{
  background:var(--tc);color:#000;font-size:12px;font-weight:700;
  padding:6px 14px;border-radius:5px;cursor:pointer;border:none;flex-shrink:0;
}
.modal-open-btn:hover{background:var(--lime)}
#story-iframe{flex:1;border:none;width:100%;background:#fff}
.modal-blocked{
  flex:1;display:none;align-items:center;justify-content:center;
  flex-direction:column;gap:16px;background:#050505;
}
.modal-blocked-msg{color:var(--heather);font-size:15px;text-align:center;line-height:1.8}
.modal-blocked-btn{
  background:var(--tc);color:#000;font-weight:700;
  padding:12px 28px;border-radius:8px;cursor:pointer;border:none;font-size:15px;
}
.modal-blocked-btn:hover{background:var(--lime)}

/* ── MISC ─────────────────────────────────────────────────────────── */
.loading{color:#222;font-size:13px;font-style:italic}
.heather{color:var(--heather)}
</style>
</head>
<body>

<!-- NAV BAR -->
<div id="nav">
  <div class="nav-logo">
    <span class="nav-sat">🛰️</span>
    <div class="nav-brand">
      <div class="nav-name"><em>XRPRadar</em></div>
      <div class="nav-tagline" style="color:#FFFFFF">Signals Over Noise 24/7</div>
    </div>
  </div>
  <div class="nav-links">
    <a href="#price-row">MARKETS</a>
    <a href="#news-panel">NEWS</a>
    <a href="#ai-briefing-us">INTELLIGENCE</a>
    <a href="#regional-rows">REGIONS</a>
    <a href="#analytics-row">ANALYTICS</a>
    <a href="#sys-health">SYSTEM</a>
  </div>
  <div class="nav-live">
    <div class="live-dot"></div>
    <span>LIVE</span>
    <span id="nav-updated" style="margin-left:8px;color:var(--heather)">Connecting...</span>
  </div>
</div>

<!-- BREAKING NEWS BANNER -->
<div id="breaking" style="display:flex">
  <span class="breaking-label">⚡ BREAKING NEWS</span>
  <div class="breaking-scroll">
    <div class="breaking-text" id="breaking-text"></div>
  </div>
</div>

<!-- PRICE AND VALUE -->
<div id="price-row" class="section-wrap">
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
      <div class="card-label">Fear &amp; Greed Index</div>
      <div class="card-value card-sm" id="fg-score">--</div>
      <div class="card-sub" id="fg-label">--</div>
      <div class="card-sub" style="margin-top:6px;font-size:12px;color:var(--gray)">Extreme Fear ← → Extreme Greed</div>
    </div>
  </div>
</div>

<!-- SECONDARY PRICE ROW -->
<div class="section-wrap" style="background:var(--dark)">
  <div class="card-grid g4">
    <div class="card card-sm">
      <div class="card-label">Price Change</div>
      <div class="card-sub">7 Day: <span id="s-7d" style="font-weight:700">--</span></div>
      <div class="card-sub" style="margin-top:5px">30 Day: <span id="s-30d" style="font-weight:700">--</span></div>
    </div>
    <div class="card card-sm">
      <div class="card-label">All-Time High</div>
      <div class="card-value" id="s-ath" style="font-size:24px">--</div>
      <div class="card-sub" id="s-ath-pct">--% below ATH</div>
    </div>
    <div class="card card-sm">
      <div class="card-label">24h Range</div>
      <div class="card-sub">High: <span id="p-high" style="font-weight:700;color:var(--lime)">--</span></div>
      <div class="card-sub" style="margin-top:5px">Low: <span id="p-low" style="font-weight:700;color:var(--red)">--</span></div>
    </div>
    <div class="card card-sm">
      <div class="card-label">XRP / BTC</div>
      <div class="card-value" id="s-btc" style="font-size:20px;word-break:break-all">--</div>
      <div class="card-sub" style="color:var(--gray);font-size:12px">BTC pair — altseason signal</div>
    </div>
  </div>
</div>

<!-- LIVE CHART -->
<div id="chart-row">
  <div class="row-title">📊 LIVE XRP/USD CHART</div>
  <div id="tv-chart">
    <div class="tradingview-widget-container">
      <div id="tradingview_xrp"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {"autosize":true,"symbol":"BITSTAMP:XRPUSD","interval":"60","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"en","backgroundColor":"#000000","gridColor":"#0A0A0A","hide_top_toolbar":false,"hide_legend":false,"save_image":false,"calendar":false,"support_host":"https://www.tradingview.com"}
      </script>
    </div>
  </div>
</div>

<!-- US INTELLIGENCE -->
<div id="ai-briefing-us" class="ai-section">
  <div class="row-title" style="color:var(--tc)">🇺🇸 US INTELLIGENCE</div>
  <div class="card-grid g4">
    <div>
      <div class="ai-badge ai-badge-tc">US PULSE</div>
      <div class="ai-text" id="ai-us-pulse"><span class="loading">Analyzing US sources...</span></div>
    </div>
    <div>
      <div class="ai-badge ai-badge-tc">REGULATORY</div>
      <div class="ai-text" id="ai-us-regulatory"><span class="loading">Loading...</span></div>
    </div>
    <div>
      <div class="ai-badge ai-badge-tc">INSTITUTIONAL</div>
      <div class="ai-text" id="ai-us-institutional"><span class="loading">Loading...</span></div>
    </div>
    <div>
      <div class="ai-badge ai-badge-tc">📍 US DATA</div>
      <div class="ai-meta" id="ai-us-meta">Waiting for data...</div>
    </div>
  </div>
</div>

<!-- GLOBAL PULSE -->
<div class="ai-section" style="background:#040A04">
  <div class="row-title" style="color:var(--lime)">🌐 GLOBAL PULSE</div>
  <div class="card-grid g4">
    <div>
      <div class="ai-badge ai-badge-lime">GLOBAL SUMMARY</div>
      <div class="ai-text" id="ai-gl-pulse"><span class="loading">Synthesizing global signals...</span></div>
    </div>
    <div>
      <div class="ai-badge ai-badge-lime">REGIONAL SIGNALS</div>
      <div id="ai-signals" class="signal-grid"><div class="loading">Loading...</div></div>
    </div>
    <div>
      <div class="ai-badge ai-badge-lime">CUMULATIVE THESIS</div>
      <div class="ai-thesis" id="ai-gl-thesis"><span class="loading">Building analysis...</span></div>
    </div>
    <div>
      <div class="ai-badge ai-badge-lime">📍 GLOBAL DATA</div>
      <div class="ai-meta" id="ai-gl-meta">Waiting for data...</div>
    </div>
  </div>
</div>

<!-- REGIONAL INTELLIGENCE ROWS -->
<div id="regional-rows">
  <div class="section-wrap" style="padding-bottom:6px">
    <div class="row-title">🗺️ REGIONAL INTELLIGENCE</div>
  </div>

  <!-- Japan -->
  <div class="region-section">
    <div class="region-header">
      <span class="region-flag">🇯🇵</span>
      <span class="region-name">JAPAN</span>
      <span id="region-sig-Japan" class="sentinel-chip" style="margin-left:auto;font-size:12px;color:var(--heather)"></span>
    </div>
    <div class="region-pulse" id="region-pulse-Japan">Loading Japan intelligence...</div>
    <div class="region-stories" id="region-stories-Japan"></div>
  </div>

  <!-- Korea -->
  <div class="region-section">
    <div class="region-header">
      <span class="region-flag">🇰🇷</span>
      <span class="region-name">SOUTH KOREA</span>
      <span id="region-sig-Korea" style="margin-left:auto;font-size:12px;color:var(--heather)"></span>
    </div>
    <div class="region-pulse" id="region-pulse-Korea">Loading Korea intelligence...</div>
    <div class="region-stories" id="region-stories-Korea"></div>
  </div>

  <!-- UAE -->
  <div class="region-section">
    <div class="region-header">
      <span class="region-flag">🇦🇪</span>
      <span class="region-name">UAE &amp; MIDDLE EAST</span>
      <span id="region-sig-UAE" style="margin-left:auto;font-size:12px;color:var(--heather)"></span>
    </div>
    <div class="region-pulse" id="region-pulse-UAE">Loading UAE intelligence...</div>
    <div class="region-stories" id="region-stories-UAE"></div>
  </div>

  <!-- Europe -->
  <div class="region-section">
    <div class="region-header">
      <span class="region-flag">🇪🇺</span>
      <span class="region-name">EUROPE</span>
      <span id="region-sig-Europe" style="margin-left:auto;font-size:12px;color:var(--heather)"></span>
    </div>
    <div class="region-pulse" id="region-pulse-Europe">Loading Europe intelligence...</div>
    <div class="region-stories" id="region-stories-Europe"></div>
  </div>

  <!-- India -->
  <div class="region-section">
    <div class="region-header">
      <span class="region-flag">🇮🇳</span>
      <span class="region-name">INDIA</span>
      <span id="region-sig-India" style="margin-left:auto;font-size:12px;color:var(--heather)"></span>
    </div>
    <div class="region-pulse" id="region-pulse-India">Loading India intelligence...</div>
    <div class="region-stories" id="region-stories-India"></div>
  </div>

  <!-- LatAm -->
  <div class="region-section">
    <div class="region-header">
      <span class="region-flag">🌎</span>
      <span class="region-name">LATIN AMERICA</span>
      <span id="region-sig-LatAm" style="margin-left:auto;font-size:12px;color:var(--heather)"></span>
    </div>
    <div class="region-pulse" id="region-pulse-LatAm">Loading LatAm intelligence...</div>
    <div class="region-stories" id="region-stories-LatAm"></div>
  </div>

  <!-- Africa -->
  <div class="region-section">
    <div class="region-header">
      <span class="region-flag">🌍</span>
      <span class="region-name">AFRICA</span>
      <span id="region-sig-Africa" style="margin-left:auto;font-size:12px;color:var(--heather)"></span>
    </div>
    <div class="region-pulse" id="region-pulse-Africa">Loading Africa intelligence...</div>
    <div class="region-stories" id="region-stories-Africa"></div>
  </div>

  <!-- Southeast Asia -->
  <div class="region-section">
    <div class="region-header">
      <span class="region-flag">🌏</span>
      <span class="region-name">SOUTHEAST ASIA</span>
      <span id="region-sig-SEA" style="margin-left:auto;font-size:12px;color:var(--heather)"></span>
    </div>
    <div class="region-pulse" id="region-pulse-SEA">Loading SEA intelligence...</div>
    <div class="region-stories" id="region-stories-SEA"></div>
  </div>
</div>

<!-- INSIGHTS HEADER -->
<div id="insights-hdr">
  <span class="insights-label">📡 INSIGHTS</span>
  <span style="color:#1A1A1A;font-size:14px">|</span>
  <span class="insights-label" style="color:var(--lime)">📰 GLOBAL NEWS FEED</span>
  <span style="font-size:12px;color:var(--heather);margin-left:auto">🔗 ON-CHAIN &amp; MARKET DATA ▶</span>
</div>

<!-- MAIN CONTENT -->
<div id="main-content">

  <!-- NEWS PANEL -->
  <div id="news-panel">
    <div class="news-controls" style="flex-direction:column;gap:8px">
      <input class="search-box" id="search-box" placeholder="🔍 Search XRP news..." oninput="filterNews()" style="width:100%">
      <div style="display:flex;gap:6px;flex-wrap:nowrap">
        <button class="filter-btn active" onclick="setFilter(this,'all')">ALL</button>
        <button class="filter-btn" onclick="setFilter(this,'Price')">PRICE</button>
        <button class="filter-btn" onclick="setFilter(this,'Legal')">LEGAL</button>
        <button class="filter-btn" onclick="setFilter(this,'Regulatory')">REG</button>
        <button class="filter-btn" onclick="setFilter(this,'Ecosystem')">ECOSYSTEM</button>
        <button class="filter-btn" onclick="setFilter(this,'Technical')">TECH</button>
        <button class="filter-btn" onclick="setFilter(this,'Whale')">WHALE</button>
      </div>
    </div>
    <div id="news-count" class="loading">Loading news...</div>
    <div id="news-feed"></div>
  </div>

  <!-- RIGHT PANEL -->
  <div id="right-panel">
    <!-- XRPL Network -->
    <div class="right-card">
      <div class="right-title">🔗 XRPL NETWORK</div>
      <div class="stat-row"><span class="stat-label">Network</span><span class="stat-val lime">● Live</span></div>
      <div class="stat-row"><span class="stat-label">Consensus</span><span class="stat-val">Federated Byzantine</span></div>
      <div class="stat-row"><span class="stat-label">Ledger Close</span><span class="stat-val">~3-5 seconds</span></div>
      <div class="stat-row"><span class="stat-label">Transaction Fee</span><span class="stat-val">~0.00001 XRP</span></div>
      <div class="stat-row"><span class="stat-label">Circulating</span><span class="stat-val tc" id="rc-supply">--</span></div>
      <div class="stat-row"><span class="stat-label">Escrow Locked</span><span class="stat-val">~43B XRP</span></div>
      <div class="stat-row"><span class="stat-label">Live TPS</span><span class="stat-val lime" id="oc-tps">--</span></div>
      <div class="stat-row"><span class="stat-label">Ledger Index</span><span class="stat-val" id="oc-ledger">--</span></div>
    </div>
    <!-- Market Structure -->
    <div class="right-card">
      <div class="right-title">📊 MARKET STRUCTURE</div>
      <div class="stat-row"><span class="stat-label">Global Rank</span><span class="stat-val tc" id="rm-rank">--</span></div>
      <div class="stat-row"><span class="stat-label">Market Cap</span><span class="stat-val" id="rm-mcap">--</span></div>
      <div class="stat-row"><span class="stat-label">24h Volume</span><span class="stat-val" id="rm-vol">--</span></div>
      <div class="stat-row"><span class="stat-label">Vol / MCap</span><span class="stat-val" id="rm-ratio">--</span></div>
      <div class="stat-row"><span class="stat-label">ATH</span><span class="stat-val" id="rm-ath">--</span></div>
      <div class="stat-row"><span class="stat-label">% Below ATH</span><span class="stat-val" id="rm-ath-pct">--</span></div>
      <div class="stat-row"><span class="stat-label">24h High</span><span class="stat-val lime" id="rm-high">--</span></div>
      <div class="stat-row"><span class="stat-label">24h Low</span><span class="stat-val" style="color:var(--red)" id="rm-low">--</span></div>
    </div>
    <!-- Escrow -->
    <div class="right-card">
      <div class="right-title">⏳ RIPPLE ESCROW</div>
      <div class="stat-row"><span class="stat-label">Next Release</span><span class="stat-val tc" id="esc-date">--</span></div>
      <div class="stat-row"><span class="stat-label">Amount</span><span class="stat-val">1B XRP</span></div>
      <div class="stat-row"><span class="stat-label">Schedule</span><span class="stat-val">Monthly, 1st</span></div>
      <div class="stat-row"><span class="stat-label">Est. Locked</span><span class="stat-val">~43B XRP</span></div>
    </div>
    <!-- Feed Status -->
    <div class="right-card">
      <div class="right-title">📡 FEED STATUS</div>
      <div class="stat-row">
        <span class="stat-label">Active Sources</span>
        <span class="stat-val lime" id="feed-active">--</span>
      </div>
      <div id="feed-health-list" style="margin-top:8px;max-height:220px;overflow-y:auto"></div>
    </div>
  </div>
</div>

<!-- ANALYTICS ROW -->
<div id="analytics-row" class="analytics-section">
  <div class="analytics-title">🔬 ANALYTICS LAB</div>
  <div class="analytics-grid">
    <div class="analytics-card">
      <div class="analytics-val" id="an-total">--</div>
      <div class="analytics-lbl">Stories Today</div>
      <div class="analytics-sub" id="an-sources">-- of -- sources</div>
    </div>
    <div class="analytics-card">
      <div class="analytics-val lime" id="an-bull">--</div>
      <div class="analytics-lbl">🟢 Bullish</div>
      <div class="analytics-sub" id="an-bull-pct">--%</div>
    </div>
    <div class="analytics-card">
      <div class="analytics-val" style="color:var(--red)" id="an-bear">--</div>
      <div class="analytics-lbl">🔴 Bearish</div>
      <div class="analytics-sub" id="an-bear-pct">--%</div>
    </div>
    <div class="analytics-card">
      <div class="analytics-val heather" id="an-neut">--</div>
      <div class="analytics-lbl">⚪ Neutral</div>
      <div class="analytics-sub" id="an-net">Net: --</div>
    </div>
    <div class="analytics-card">
      <div class="analytics-val" id="an-fear" style="color:var(--ylw)">--</div>
      <div class="analytics-lbl">Fear &amp; Greed</div>
      <div class="analytics-sub" id="an-fear-lbl">--</div>
    </div>
    <div class="analytics-card">
      <div class="analytics-val tc" id="an-rank">--</div>
      <div class="analytics-lbl">Global Rank</div>
      <div class="analytics-sub">CoinGecko</div>
    </div>
    <div class="analytics-card">
      <div class="analytics-val lime" id="an-vol-ratio">--</div>
      <div class="analytics-lbl">Vol / MCap %</div>
      <div class="analytics-sub">Trading activity</div>
    </div>
    <div class="analytics-card">
      <div class="analytics-val" id="an-ath-pct" style="color:var(--org)">--</div>
      <div class="analytics-lbl">% Below ATH</div>
      <div class="analytics-sub">ATH recovery</div>
    </div>
  </div>
</div>

<!-- SCOREBOARD -->
<div id="scoreboard">
  <div class="score-title">🦂 XRPRADAR SCOREBOARD</div>
  <div class="score-grid">
    <div class="score-card tc">
      <div class="score-num tc" id="sc-total">--</div>
      <div class="score-lbl">Stories Today</div>
      <div class="score-sub" id="sc-sources">-- of -- sources</div>
    </div>
    <div class="score-card" style="border-top:3px solid var(--lime)">
      <div class="score-num lime" id="sc-bull">--</div>
      <div class="score-lbl">🟢 Bullish</div>
      <div class="score-sub" id="sc-bull-pct">--%</div>
    </div>
    <div class="score-card" style="border-top:3px solid var(--red)">
      <div class="score-num red" id="sc-bear">--</div>
      <div class="score-lbl">🔴 Bearish</div>
      <div class="score-sub" id="sc-bear-pct">--%</div>
    </div>
    <div class="score-card">
      <div class="score-num heather" id="sc-neut">--</div>
      <div class="score-lbl">⚪ Neutral</div>
      <div class="score-sub" id="sc-net">Net: --</div>
    </div>
  </div>
</div>

<!-- FOOTER -->
<div id="footer" style="background:#020505;padding:12px 20px;border-top:2px solid #111;font-size:11px;color:var(--heather)">
  <!-- Row a: Brand + version + runtime -->
  <div style="display:flex;align-items:center;gap:20px;padding:4px 0;border-bottom:1px solid #111">
    <span style="color:var(--tc);font-weight:700;font-size:13px">🛰️ <em>XRPRadar</em></span>
    <span>Version: <strong id="ft-ver" style="color:#fff">--</strong></span>
    <span>Uptime: <span id="ft-uptime" style="color:#fff">--</span></span>
    <span id="ft-updated" style="margin-left:auto">--</span>
  </div>
  <!-- Row d: Not financial advice in yellow -->
  <div style="padding:4px 0;border-bottom:1px solid #111;color:var(--ylw)">
    ⚠️ Not Financial Advice — XRPRadar is for informational purposes only. DYOR.
  </div>
  <!-- Row e: Last updated + precheck -->
  <div style="display:flex;gap:20px;padding:4px 0;border-bottom:1px solid #111">
    <span>Last Updated: <span id="ft-last" style="color:#fff">--</span></span>
    <span>System Precheck: <span id="ft-qa" style="color:#fff">--</span></span>
  </div>
  <!-- Row f: Preflight details -->
  <div style="padding:4px 0;border-bottom:1px solid #111" id="footer-precheck"></div>
  <!-- Row g: Maintenance -->
  <div style="padding:4px 0">
    Maintenance: <span id="ft-maint" style="color:#fff">--</span>
    &nbsp;|&nbsp; Feeds: <span id="ft-feeds" style="color:#fff">--</span>
  </div>
</div>

<!-- SYSTEM HEALTH BAR -->
<div id="sys-health">
  <div class="sys-zone">
    <div class="sys-title">📦 Version / Last Updated</div>
    <div class="sys-val heather" id="sh-version">--</div>
    <div class="sys-sub heather" id="sh-updated">--</div>
  </div>
  <div class="sys-zone">
    <div class="sys-title">✅ Preflight / QA Check (4h)</div>
    <div class="sys-val" id="sh-qa-status">--</div>
    <div class="sys-sub" id="sh-qa-last">Last run: --</div>
    <div id="sh-qa-detail" class="sys-sub" style="margin-top:4px"></div>
  </div>
  <div class="sys-zone">
    <div class="sys-title">📡 Feed Integrity</div>
    <div class="sys-val" id="sh-feeds">-- feeds active</div>
    <div class="sys-sub" id="sh-error">No errors</div>
    <div class="sys-sub" id="sh-error-ts" style="color:#333"></div>
  </div>
  <div class="sys-zone">
    <div class="sys-title">🔧 Maintenance</div>
    <div class="sys-val pass" id="sh-maint">✅ OK</div>
    <div class="sys-sub">Start: <span id="sh-start" class="heather">--</span></div>
  </div>
</div>

<!-- STORY POPUP OVERLAY -->
<div id="story-modal">
  <div class="modal-header">
    <div class="modal-close" onclick="closeStoryModal()">✕</div>
    <div class="modal-title" id="modal-title">Loading story...</div>
    <div class="modal-src" id="modal-src"></div>
    <button class="modal-open-btn" id="modal-open-btn" onclick="openInNewTab()">Open in New Tab ↗</button>
  </div>
  <iframe id="story-iframe" onload="iframeLoaded()" onerror="iframeBlocked()"></iframe>
  <div class="modal-blocked" id="modal-blocked">
    <div class="modal-blocked-msg">This site doesn't allow embedding.<br>Click below to read the full story.</div>
    <button class="modal-blocked-btn" onclick="openInNewTab()">Read Full Story ↗</button>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let allStories   = [];
let activeCat    = "all";
let activeSearch = "";

// ── Helpers ────────────────────────────────────────────────────────────────
function c(id, val){ const el=document.getElementById(id); if(el&&val!==undefined) el.textContent=val; }
function fmtUSD(v){
  if(!v) return "--";
  v=parseFloat(v);
  if(v>=1e12) return `$${(v/1e12).toFixed(2)}T`;
  if(v>=1e9)  return `$${(v/1e9).toFixed(2)}B`;
  if(v>=1e6)  return `$${(v/1e6).toFixed(2)}M`;
  if(v>=1e3)  return `$${(v/1e3).toFixed(2)}K`;
  return `$${v.toFixed(2)}`;
}
function col(id, v, pos, neg){
  const el=document.getElementById(id);
  if(el) el.style.color = parseFloat(v||0)>=0 ? pos : neg;
}

// ── Fetch Data ─────────────────────────────────────────────────────────────
async function fetchData(){
  try{
    const r = await fetch("/api/data");
    const d = await r.json();
    updatePrice(d);
    updateAI(d);
    updateScoreboard(d);
    updateAnalytics(d);
    updateRegions(d);
    updateSystemHealth(d);
    updateFooter(d);
    if(d.last_updated) c("nav-updated", d.last_updated);
  }catch(e){ console.error("fetchData:",e); }
}

async function fetchNews(){
  try{
    const r = await fetch("/api/news");
    const d = await r.json();
    allStories = d.stories||[];
    renderNews(d.total_all||0);
  }catch(e){ console.error("fetchNews:",e); }
}

// ── Price ──────────────────────────────────────────────────────────────────
function updatePrice(d){
  const p  = d.price||{};
  const fg = d.fear_greed||{};
  const oc = d.onchain||{};

  // Main price card
  c("p-price", p.usd ? `$${parseFloat(p.usd).toFixed(4)}` : "--");
  const ch24 = parseFloat(p.change_24h||0);
  const p24  = document.getElementById("p-change24");
  if(p24){ p24.textContent=`${ch24>=0?"▲":"▼"} ${Math.abs(ch24).toFixed(2)}% (24h)`; p24.style.color=ch24>=0?"var(--lime)":"var(--red)"; }
  const ch7=parseFloat(p.change_7d||0);
  const p7=document.getElementById("p-change7");
  if(p7){ p7.textContent=`7D: ${ch7>=0?"+":""}${ch7.toFixed(2)}%`; p7.style.color=ch7>=0?"var(--lime)":"var(--red)"; }

  c("p-mcap",    fmtUSD(p.mcap));
  c("p-rank",    `Rank #${p.rank||"--"}`);
  c("p-supply",  p.supply_circ ? `${(p.supply_circ/1e9).toFixed(1)}B circulating` : "--");
  c("p-vol",     fmtUSD(p.volume_24h));
  c("p-volratio",p.vol_mcap_ratio ? `Vol/MCap: ${p.vol_mcap_ratio}%` : "Vol/MCap: --");
  c("p-btc",     p.btc ? `BTC: ${parseFloat(p.btc).toFixed(8)}` : "BTC: --");
  c("fg-score",  fg.score!==undefined ? fg.score : "--");
  c("fg-label",  fg.label||"--");
  const fgEl=document.getElementById("fg-score");
  if(fgEl&&fg.score!==undefined) fgEl.style.color=fg.score<30?"var(--red)":fg.score>70?"var(--lime)":"var(--ylw)";

  // Secondary row
  const ch30=parseFloat(p.change_30d||0);
  const s7=document.getElementById("s-7d"); if(s7){s7.textContent=`${ch7>=0?"+":""}${ch7.toFixed(2)}%`;s7.style.color=ch7>=0?"var(--lime)":"var(--red)";}
  const s30=document.getElementById("s-30d"); if(s30){s30.textContent=`${ch30>=0?"+":""}${ch30.toFixed(2)}%`;s30.style.color=ch30>=0?"var(--lime)":"var(--red)";}
  c("s-ath", p.ath ? `$${parseFloat(p.ath).toFixed(4)}` : "--");
  const athPct=parseFloat(p.ath_pct||0);
  const athEl=document.getElementById("s-ath-pct"); if(athEl){athEl.textContent=`${athPct.toFixed(1)}% below ATH`;athEl.style.color="var(--org)";}
  c("s-btc", p.btc ? `₿ ${parseFloat(p.btc).toFixed(8)}` : "--");
  c("p-high", p.high_24h ? `$${parseFloat(p.high_24h).toFixed(4)}` : "--");
  c("p-low",  p.low_24h  ? `$${parseFloat(p.low_24h).toFixed(4)}`  : "--");
  c("esc-date", (d.escrow||{}).next_date || "1st of next month");

  // Right panel mirrors
  c("rc-supply",  p.supply_circ ? `${(p.supply_circ/1e9).toFixed(1)}B XRP` : "--");
  c("rm-rank",    `#${p.rank||"--"}`);
  c("rm-mcap",    fmtUSD(p.mcap));
  c("rm-vol",     fmtUSD(p.volume_24h));
  c("rm-ratio",   p.vol_mcap_ratio ? `${p.vol_mcap_ratio}%` : "--");
  c("rm-ath",     p.ath ? `$${parseFloat(p.ath).toFixed(4)}` : "--");
  c("rm-ath-pct", athPct ? `${Math.abs(athPct).toFixed(1)}% below` : "--");
  c("rm-high",    p.high_24h ? `$${parseFloat(p.high_24h).toFixed(4)}` : "--");
  c("rm-low",     p.low_24h  ? `$${parseFloat(p.low_24h).toFixed(4)}`  : "--");

  // On-chain
  c("oc-tps",    oc.tps ? `${oc.tps} TPS` : "--");
  c("oc-ledger", oc.ledger_index||"--");

  // Breaking news
  if(d.breaking){
    const bb=document.getElementById("breaking");
    const bt=document.getElementById("breaking-text");
    if(bb&&bt){ bt.textContent=`${d.breaking.title} — ${d.breaking.source} — ${d.breaking.age||""}`; bb.style.display="flex"; }
  } else {
    const bt2=document.getElementById("breaking-text"); if(bt2) bt2.textContent="Monitoring XRP global news feeds — no breaking alerts at this time.";
  }
}

// ── AI ─────────────────────────────────────────────────────────────────────
function updateAI(d){
  const us=d.ai_us||{};
  const gl=d.ai_global||{};
  if(us.pulse) c("ai-us-pulse", us.pulse);
  if(us.regulatory) c("ai-us-regulatory", us.regulatory);
  if(us.institutional) c("ai-us-institutional", us.institutional);
  if(us.ts){
    const m=document.getElementById("ai-us-meta");
    if(m) m.innerHTML=`Last analysis: <strong style="color:var(--tc)">${us.ts}</strong><br>Sources monitored: US/Institutional/Legal<br>Feeds: Major crypto + Google News`;
  }
  if(gl.pulse) c("ai-gl-pulse", gl.pulse);
  if(gl.thesis) c("ai-gl-thesis", gl.thesis);
  const sg=gl.signals||{};
  const sigEl=document.getElementById("ai-signals");
  if(sigEl&&Object.keys(sg).length){
    const dc={"bullish":"sig-bull","bearish":"sig-bear","neutral":"sig-neut","quiet":"sig-quiet"};
    const fl={"Japan":"🇯🇵","Korea":"🇰🇷","UAE":"🇦🇪","Europe":"🇪🇺","LatAm":"🌎","Africa":"🌍","India":"🇮🇳","SEA":"🌏"};
    sigEl.innerHTML=Object.entries(sg).map(([r,s])=>
      `<div class="signal-chip"><div class="sig-dot ${dc[s]||"sig-quiet"}"></div><span>${fl[r]||""}  ${r}</span></div>`
    ).join("");
  }
  if(gl.ts){
    const m=document.getElementById("ai-gl-meta");
    if(m) m.innerHTML=`Last analysis: <strong style="color:var(--lime)">${gl.ts}</strong><br>${Object.keys(sg).length} regions monitored<br>${(d.feeds_active||0)}/${(d.feeds_total||0)} sources active`;
  }
}

// ── Regional Rows ──────────────────────────────────────────────────────────
const REGION_FLAGS={"Japan":"🇯🇵","Korea":"🇰🇷","UAE":"🇦🇪","Europe":"🇪🇺","India":"🇮🇳","LatAm":"🌎","Africa":"🌍","SEA":"🌏"};
const SIG_COLORS={"bullish":"var(--lime)","bearish":"var(--red)","neutral":"var(--ylw)","quiet":"var(--gray)"};

function updateRegions(d){
  const regions=d.ai_regions||{};
  const signals=(d.ai_global||{}).signals||{};
  ["Japan","Korea","UAE","Europe","India","LatAm","Africa","SEA"].forEach(reg=>{
    const ri=regions[reg]||{};
    const sig=signals[reg]||"quiet";
    const sigEl=document.getElementById(`region-sig-${reg}`);
    if(sigEl){sigEl.textContent=`● ${sig.toUpperCase()}`;sigEl.style.color=SIG_COLORS[sig]||"var(--gray)";}
    if(ri.pulse){const pel=document.getElementById(`region-pulse-${reg}`);if(pel)pel.textContent=ri.pulse;}
  });
}

async function fetchRegionNews(reg){
  try{
    const r=await fetch(`/api/news?region=${reg}`);
    const d=await r.json();
    const stories=(d.stories||[]).slice(0,5);
    const el=document.getElementById(`region-stories-${reg}`);
    if(!el) return;
    if(!stories.length){el.innerHTML='<div style="font-size:12px;color:#333;padding:4px 0">No regional stories found yet...</div>';return;}
    el.innerHTML=stories.map(s=>{
      const isForeign=s.lang==="non-english";
      const trans=s.translated_title ? `<div class="region-story-translation">🌐 ${s.translated_title}</div>` : "";
      const fb=isForeign ? `<span class="foreign-badge">🌐 Translated</span>` : "";
      return `<div class="region-story" onclick="openStoryModal('${s.link}','${s.title.replace(/'/g,\"\\'\")}','${s.source}')">
        <div class="region-story-title ${isForeign?"foreign":""}">${s.title}</div>
        ${trans}
        <div class="region-story-meta">
          <span class="region-sent ${s.sentiment}">${s.sentiment}</span>
          <span class="region-src">${s.source}</span>
          ${fb}
          <span class="region-age">${s.age||""}</span>
        </div>
      </div>`;
    }).join("");
  }catch(e){}
}

// ── Scoreboard & Analytics ─────────────────────────────────────────────────
function updateScoreboard(d){
  const st=d.story_stats||{};
  c("sc-total",   st.today||0);
  c("sc-sources", `${d.feeds_active||0} of ${d.feeds_total||0} sources`);
  c("sc-bull",    st.bullish||0);
  c("sc-bear",    st.bearish||0);
  c("sc-neut",    st.neutral||0);
  const t=(st.today)||1;
  c("sc-bull-pct",`${Math.round((st.bullish||0)/t*100)}%`);
  c("sc-bear-pct",`${Math.round((st.bearish||0)/t*100)}%`);
  const net=(st.bullish||0)-(st.bearish||0);
  const netEl=document.getElementById("sc-net");
  if(netEl){netEl.textContent=`Net: ${net>=0?"+":""}${net}`;netEl.style.color=net>=0?"var(--lime)":"var(--red)";}
}

function updateAnalytics(d){
  const st=d.story_stats||{};
  const p=d.price||{};
  const fg=d.fear_greed||{};
  const t=(st.today)||1;
  c("an-total",     st.today||0);
  c("an-sources",   `${d.feeds_active||0} of ${d.feeds_total||0} sources`);
  c("an-bull",      st.bullish||0);
  c("an-bear",      st.bearish||0);
  c("an-neut",      st.neutral||0);
  c("an-bull-pct",  `${Math.round((st.bullish||0)/t*100)}%`);
  c("an-bear-pct",  `${Math.round((st.bearish||0)/t*100)}%`);
  const net=(st.bullish||0)-(st.bearish||0);
  const netEl=document.getElementById("an-net");
  if(netEl){netEl.textContent=`Net: ${net>=0?"+":""}${net}`;netEl.style.color=net>=0?"var(--lime)":"var(--red)";}
  c("an-fear",     fg.score!==undefined?fg.score:"--");
  c("an-fear-lbl", fg.label||"--");
  c("an-rank",     p.rank?`#${p.rank}`:"--");
  c("an-vol-ratio",p.vol_mcap_ratio?`${p.vol_mcap_ratio}%`:"--");
  const athPct=parseFloat(p.ath_pct||0);
  c("an-ath-pct",  athPct?`${Math.abs(athPct).toFixed(1)}%`:"--");
}

// ── System Health ──────────────────────────────────────────────────────────
function updateSystemHealth(d){
  c("sh-version",  d.version||"--");
  c("sh-updated",  d.last_updated||"--");
  c("sh-feeds",    `${d.feeds_active||0}/${d.feeds_total||0} feeds active`);
  const qaEl=document.getElementById("sh-qa-status");
  if(qaEl){qaEl.textContent=d.qa_status||"PENDING";qaEl.className="sys-val "+(d.qa_status==="PASS"?"pass":d.qa_status==="FAIL"?"fail":"warn");}
  c("sh-qa-last", `Last run: ${d.qa_last||"Not yet run"}`);
  if(d.qa_details&&d.qa_details.length){
    const det=document.getElementById("sh-qa-detail");
    if(det) det.innerHTML=d.qa_details.map(chk=>`<span style="color:${chk.ok?"var(--lime)":"var(--red)"}">${chk.ok?"✓":"✗"} ${chk.name}</span>`).join(" ");
  }
  const errEl=document.getElementById("sh-error");
  if(d.last_error){
    if(errEl){errEl.textContent=`Last error: ${d.last_error}`;errEl.style.color="var(--red)";}
    c("sh-error-ts", d.last_error_ts||"");
  } else {
    if(errEl){errEl.textContent="No errors logged";errEl.style.color="var(--gray)";}
  }
  const maintEl=document.getElementById("sh-maint");
  if(maintEl){const m=d.maintenance||"OK";maintEl.textContent=m==="OK"?"✅ OK":m==="ACTIVE"?"🔧 ACTIVE":"⏳ PENDING";maintEl.className="sys-val "+(m==="OK"?"pass":"warn");}
  if(d.start_time) c("sh-start", new Date(d.start_time).toISOString().replace("T"," ").substring(0,16)+" UTC");
  const fhl=document.getElementById("feed-health-list");
  const fha=document.getElementById("feed-active");
  if(fhl&&d.feed_health){
    const entries=Object.entries(d.feed_health);
    const up=entries.filter(([,v])=>v==="UP").length;
    if(fha) fha.textContent=`${up}/${entries.length}`;
    fhl.innerHTML=entries.map(([name,status])=>
      `<div class="stat-row"><span class="stat-label" style="font-size:11px">${name}</span><span style="font-size:11px;color:${status==="UP"?"var(--lime)":"var(--red)"}">${status==="UP"?"●":"✗"}</span></div>`
    ).join("");
  }
}

function updateFooter(d){
  c("ft-ver",     d.version||"--");
  c("ft-updated", `Last updated: ${d.last_updated||"--"}`);
  if(d.start_time){
    const hrs=Math.floor((Date.now()-new Date(d.start_time))/3600000);
    c("ft-uptime", `Uptime: ${hrs}h`);
  }
  if(d.upgrade_log){
    document.getElementById("upgrade-log").innerHTML=
      d.upgrade_log.map(u=>`<div style="margin-bottom:4px"><span style="color:var(--heather)">${u.ts}</span> — ${u.note}</div>`).join("");
  // Color-coded precheck results
  if(d.qa_details && d.qa_details.length) {
    const precheckEl = document.getElementById("footer-precheck");
    if(precheckEl) precheckEl.innerHTML = d.qa_details.map(chk=>
      `<span style="color:${chk.ok?"#FFFFFF":"var(--heather)"};margin-right:12px">${chk.ok?"✓":"✗"} ${chk.name}</span>`
    ).join("");
  }
  }
}

// ── News Render ────────────────────────────────────────────────────────────
const SRC_COLORS={
  official:"src-official",major:"src-major",xrp:"src-xrp",
  community:"src-community",international:"src-international",
  aggregator:"src-aggregator",legal:"src-legal",mainstream:"src-mainstream",
  institutional:"src-institutional",whale:"src-whale",ecosystem:"src-ecosystem",technical:"src-technical"
};

function renderNews(totalAll){
  let stories=allStories;
  if(activeCat!=="all") stories=stories.filter(s=>s.category===activeCat);
  if(activeSearch)      stories=stories.filter(s=>s.title.toLowerCase().includes(activeSearch));

  const feed=document.getElementById("news-feed");
  const cnt=document.getElementById("news-count");
  if(!feed) return;

  const total=totalAll||allStories.length;
  const activeFeeds = document.getElementById("feed-active")?.textContent || "--";
  if(cnt) cnt.innerHTML = `<span style="color:var(--tc);font-weight:700">${stories.length}</span> stories shown &nbsp;|&nbsp; <span style="color:var(--lime);font-weight:700">${total}</span> total collected &nbsp;|&nbsp; <span style="color:var(--tc);font-weight:700">${activeFeeds}</span> of <span style="color:var(--lime);font-weight:700">230</span> sources online`;

  if(!stories.length){
    feed.innerHTML=`<div class="loading" style="padding:20px 0">No stories match your filter. Feeds refresh every 10 minutes.</div>`;
    return;
  }

  feed.innerHTML=stories.slice(0,100).map(s=>{
    const srcClass=SRC_COLORS[s.type]||"src-major";
    const sentClass=`sent-${s.sentiment}`;
    const sentLabel=s.sentiment==="bullish"?"🟢 Bullish":s.sentiment==="bearish"?"🔴 Bearish":"⚪ Neutral";
    const summary=s.summary?`<div class="story-summary">${s.summary.substring(0,200)}${s.summary.length>200?"...":""}</div>`:"";
    const isForeign=s.lang==="non-english";
    const titleClass=isForeign?"story-title foreign-title":"story-title";
    const trans=s.translated_title?`<div class="story-translation">🌐 ${s.translated_title}</div>`:"";
    const fb=isForeign&&!s.translated_title?`<span style="font-size:10px;color:var(--tc);margin-left:4px">🌐</span>`:"";
    return `<div class="story-card" onclick="openStoryModal('${s.link}','${s.title.replace(/'/g,\"\\'\")}','${s.source}')">
      <div class="story-header">
        <span class="src-badge ${srcClass}">${s.source}</span>
        <span class="cat-tag">${s.category}</span>
        ${s.breaking?'<span style="color:var(--org);font-size:11px;font-weight:700">⚡ BREAKING</span>':""}
        ${fb}
      </div>
      <div class="${titleClass}">${s.title}</div>
      ${trans}
      ${summary}
      <div class="story-footer">
        <span class="sentiment-tag ${sentClass}">${sentLabel}</span>
        <span class="story-age">${s.age||""}</span>
      </div>
    </div>`;
  }).join("");
}

function setFilter(btn,cat){
  activeCat=cat;
  document.querySelectorAll(".filter-btn").forEach(b=>b.classList.remove("active"));
  btn.classList.add("active");
  renderNews();
}
function filterNews(){
  activeSearch=document.getElementById("search-box").value.toLowerCase();
  renderNews();
}

// ── Story Modal ────────────────────────────────────────────────────────────
let currentStoryUrl = "";

function openStoryModal(url, title, source) {
  currentStoryUrl = url;
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-src").textContent = source;
  document.getElementById("story-iframe").src = url;
  document.getElementById("story-iframe").style.display = "block";
  document.getElementById("modal-blocked").style.display = "none";
  document.getElementById("story-modal").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function closeStoryModal() {
  document.getElementById("story-modal").style.display = "none";
  document.getElementById("story-iframe").src = "";
  document.body.style.overflow = "";
}

function openInNewTab() {
  window.open(currentStoryUrl, "_blank");
}

function iframeLoaded() {
  // Try to detect blocked frames
  try {
    const iframe = document.getElementById("story-iframe");
    if (!iframe.contentDocument && !iframe.contentWindow.location.href) {
      iframeBlocked();
    }
  } catch(e) {
    iframeBlocked();
  }
}

function iframeBlocked() {
  document.getElementById("story-iframe").style.display = "none";
  document.getElementById("modal-blocked").style.display = "flex";
}

// Close modal on background click
document.addEventListener("keydown", e => { if(e.key === "Escape") closeStoryModal(); });

// ── Init ───────────────────────────────────────────────────────────────────
async function init(){
  await fetchData();
  await fetchNews();
  // Load regional stories
  ["Japan","Korea","UAE","Europe","India","LatAm","Africa","SEA"].forEach(reg=>{
    fetchRegionNews(reg);
  });
}

init();
setInterval(fetchData,  60000);
setInterval(fetchNews,  600000);
setInterval(()=>{ ["Japan","Korea","UAE","Europe","India","LatAm","Africa","SEA"].forEach(r=>fetchRegionNews(r)); }, 600000);
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
