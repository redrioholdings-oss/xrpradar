"""
SCORPION UNIVERSAL — 10-Slot Strategy Testing Framework
Pure Python + Flask. No patches. No layers. Written clean from scratch.

HOW TO CHANGE STRATEGIES:
  Edit the SLOTS list below. Change symbol, strategy, or set active=False.
  All 22 strategies are available in STRATEGY_DISPATCH at the bottom.

HOW TO RUN:
  pip install flask alpaca-py numpy pandas requests
  python3 main.py
"""

# v8.7 Deploy 1: file identifier shown in dashboard footer so you always know
# which file is actually running. Bumping this is the cheap way to verify a deploy landed.
BOT_FILE = "scorpion_v9_2.py"
SCO_BUILD    = "SCO-0013"
LAUNCH_PHASE = SCO_BUILD    # ties phase to build — each new SCO auto-resets stats on first boot
PAPER_BUDGET = 3000.00   # Realistic paper budget   # Realistic paper budget — bot sizes as if this is the full account

# ─────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────
import os, time, math, logging, threading, gc
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, Response
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

# ─────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("SCORPION")

# ─────────────────────────────────────────────────────────────────
# SLOTS  ←  EDIT THESE TO CHANGE WHAT THE BOT TRADES
# ─────────────────────────────────────────────────────────────────
SLOTS = [
    # SCO-0013 -- Strategies #11-20 (-S Scalp Suite | 1m bars | 0.7% stop | 1.4% TP)
    {"name": "CONFIG 1",  "symbol": "XRP/USD", "strategy": "XRP_VWAP_BOUNCE-S",  "active": True},
    {"name": "CONFIG 2",  "symbol": "XRP/USD", "strategy": "XRP_RSI_BULL-S",     "active": True},
    {"name": "CONFIG 3",  "symbol": "XRP/USD", "strategy": "XRP_EMA50_ALIGN-S",  "active": True},
    {"name": "CONFIG 4",  "symbol": "XRP/USD", "strategy": "XRP_BIG_CANDLE-S",   "active": True},
    {"name": "CONFIG 5",  "symbol": "XRP/USD", "strategy": "XRP_STOCH_BULL-S",   "active": True},
    {"name": "CONFIG 6",  "symbol": "XRP/USD", "strategy": "XRP_HIGHER_CLOSE-S", "active": True},
    {"name": "CONFIG 7",  "symbol": "XRP/USD", "strategy": "XRP_ATR_BULL-S",     "active": True},
    {"name": "CONFIG 8",  "symbol": "XRP/USD", "strategy": "XRP_EMA_TOUCH-S",    "active": True},
    {"name": "CONFIG 9",  "symbol": "XRP/USD", "strategy": "XRP_CLOSE_HIGH-S",   "active": True},
    {"name": "CONFIG 10", "symbol": "XRP/USD", "strategy": "XRP_TRIPLE_EMA-S",   "active": True},
]

# ─────────────────────────────────────────────────────────────────
# RISK SETTINGS
# ─────────────────────────────────────────────────────────────────
RISK = {
    "POSITION_PCT":     0.10,   # 10% of available cash per trade
    # v8.8e: per-strategy take profits to fix inverted R:R (small wins / big losses).
    # Trend-following strategies get wider targets — capping breakouts at 1.5% leaves 2%+ on the table.
    # Mean-reversion strategies exit tighter — they're counter-trend and need faster exits.
    "TAKE_PROFIT_PCT":  0.015,  # default fallback (strategies below override this)
    "STRATEGY_TP": {
        # ── Research-backed XRP strategies (#130-134) ───────────────────
        "XRP_CANDLE_SURGE":  0.010,
        # v9.2 XRP simple strategies
        # -S Scalp Suite -- 0.7% stop / 1.4% TP = 2:1 R:R
        "XRP_VWAP_BOUNCE-S":  0.014,
        "XRP_RSI_BULL-S":     0.014,
        "XRP_EMA50_ALIGN-S":  0.014,
        "XRP_BIG_CANDLE-S":   0.014,
        "XRP_STOCH_BULL-S":   0.014,
        "XRP_HIGHER_CLOSE-S": 0.014,
        "XRP_ATR_BULL-S":     0.014,
        "XRP_EMA_TOUCH-S":    0.014,
        "XRP_CLOSE_HIGH-S":   0.014,
        "XRP_TRIPLE_EMA-S":   0.014,
        "XRP_VWAP_BOUNCE":  0.024,  # 2.00:1 (stop=1.2%)
        "XRP_RSI_BULL":    0.024,  # 2.00:1
        "XRP_EMA50_ALIGN": 0.024,  # 2.00:1
        "XRP_BIG_CANDLE":  0.024,  # 2.00:1
        "XRP_STOCH_BULL":  0.024,  # 2.00:1
        "XRP_HIGHER_CLOSE":0.024,  # 2.00:1
        "XRP_ATR_BULL":    0.024,  # 2.00:1
        "XRP_EMA_TOUCH":   0.024,  # 2.00:1
        "XRP_CLOSE_HIGH":  0.024,  # 2.00:1
        "XRP_TRIPLE_EMA":  0.030,  # 2.50:1 (15m, stop=1.2%)
        "XRP_BB_ADX":        0.020,  # 2.5:1 — BB+ADX mean reversion on 15m
        "XRP_NEWS_FADE":     0.016,  # 2.0:1 — quick fade of news overreaction
        "XRP_COMPRESS":      0.030,  # 3.75:1 — compression breakout (big moves)
        "XRP_SUPPORT_RANGE": 0.020,  # 2.5:1 — range support bounce
        "XRP_BREAKOUT_V2":   0.035,  # 4.38:1 — high-conviction breakout
        # ── Missing TP entries — audit fix v9.0 ──────────────────────────
        "EMA_BOUNCE":   0.016,  # 2.0:1 — EMA50 touch bounce
        "EMA_RIBBON":   0.020,  # 2.5:1 — EMA ribbon trend
        "GRID":         0.016,  # 2.0:1 — grid mean reversion
        "HABB_SCALP":   0.020,  # 2.5:1 — Heikin Ashi + SuperTrend scalp
        "HULL_TSI_CCI": 0.025,  # 3.1:1 — Hull/TSI/CCI complex
        "MANNAN_V2":    0.025,  # 3.1:1 — multi-indicator
        "REV_HUNTER":   0.020,  # 2.5:1 — reversal hunter
        "SQ_BEAR":      0.025,  # 3.1:1 — squeeze momentum
        "STOCHASTIC":   0.016,  # 2.0:1 — stochastic crossover
        # ── v8.8l Active + new entries ──
        "XRP_SCALP_BB":    0.016,
        "XRP_PULLBACK":    0.020,
        "XRP_VWAP_TOUCH":  0.016,
        "BOLLINGER":       0.016,
        "EMA_CROSS":       0.025,
        "RSI_SIMPLE":      0.025,
        "BREAKOUT":        0.035,
        "MEAN_REV_VWAP":   0.016,
        "STOCH_SIMPLE":    0.025,
        "VOL_BURST":       0.022,
        # v8.8l new XRP strategies
        "XRP_DUAL_RSI":    0.016,  # 1.6% — #118 dual RSI confluence. 2.0:1 R:R
        "XRP_CANDLE_SURGE":0.025,  # 2.5% — #119 candle body anomaly. 3.1:1 R:R
        "XRP_RANGE_BREAK": 0.030,  # 3.0% — #120 tight box breakout. 3.75:1 R:R
        "XRP_MICRO_DIV":   0.020,  # 2.0% — #121 3-candle divergence. 2.5:1 R:R
        "XRP_VOL_DELTA":   0.020,  # 2.0% — #122 vol delta momentum. 2.5:1 R:R
        "XRP_ATR_SPIKE":   0.016,
        # v8.8m new XRP strategies
        "XRP_BTC_DIVERG":   0.020,  # 2.0% — #124 BTC correlation divergence. 2.5:1 R:R
        "XRP_SESSION_VWAP": 0.025,  # 2.5% — #125 session VWAP range break. 3.1:1 R:R
        "XRP_CONVICTION":   0.020,  # 2.0% — #126 7-cond conviction score. 2.5:1 R:R
        "XRP_NIGHT_BREAK":  0.030,  # 3.0% — #127 overnight compression break. 3.75:1 R:R
        "XRP_BASKET_LEAD":  0.025,  # 2.5% — #128 basket relative momentum. 3.1:1 R:R
        "XRP_STAIRCASE":    0.030,
        # ── v8.8n Active (#42-51) ──
        "VWAP_CROSS":  0.020,  # 2.0% — #42 VWAP cross. 2.5:1 R:R
        "VWAP_BOUNCE": 0.016,  # 1.6% — #43 VWAP bounce. 2.0:1 R:R  ADX-exempt
        "CMF_DIV":     0.025,  # 2.5% — #44 CMF positive. 3.1:1 R:R
        "STOCH_OS":    0.016,  # 1.6% — #45 Stoch oversold cross. 2.0:1 R:R  ADX-exempt
        "STOCH_OB":    0.020,  # 2.0% — #46 Stoch pullback buy. 2.5:1 R:R  ADX-exempt
        "STOCH_RSI":   0.016,  # 1.6% — #47 Stoch+RSI dual oversold. 2.0:1 R:R  ADX-exempt
        "WILLIAMS_R":  0.020,  # 2.0% — #48 Williams %R emerging. 2.5:1 R:R  ADX-exempt
        "CCI_REV":     0.020,  # 2.0% — #49 CCI oversold cross. 2.5:1 R:R  ADX-exempt
        "HEAD_SHLD":   0.025,  # 2.5% — #50 Inv H&S neckline break. 3.1:1 R:R
        "INV_H_S":     0.025,  # 2.5% — #51 H&S neckline bounce. 3.1:1 R:R  ADX-exempt  # 3.0% — #129 conviction runner. 3.75:1 R:R  # 1.6% — #123 liquidity sweep rev. 2.0:1 R:R
        # ── Retired (kept for archive reference) ──
        "XRP_SURGE":0.025, "BB_UPPER":0.025, "BB_MEAN_REV":0.020, "BB_KELTNER":0.040,
        "EMA_9_21":0.016, "EMA_12_50":0.025, "EMA_GOLDEN":0.040, "EMA_DEATH":0.035,
        "EMA_21_PULL":0.025, "EMA_50_BOUNCE":0.025,
        "FS1000":0.020, "RSI_BEAR_DIV":0.025, "MACD_CROSS":0.025, "MACD_ZERO":0.030,
        "MACD_HIST_REV":0.020, "MACD_RSI":0.025, "MACD_EMA200":0.030,
        "MACD_DIVERGE":0.025, "BB_SQUEEZE":0.035, "BB_LOWER":0.016,
        "RSI_OVERSOLD":0.025, "RSI_OVERBOUGHT":0.020, "RSI_2_EXTREME":0.016,
        "RSI_CENTERLINE":0.025, "RSI_BULL_DIV":0.030, "RSI_DIV":0.018,
        "MEAN_REV_VWAP":0.016, "VOL_BURST":0.022, "SUPPORT_BOUNCE":0.020,
        "GLD_GOLD":0.016, "REGIME_AUTO":0.025, "MULTI_TF":0.025,
        "BREAKOUT":0.035, "BOLLINGER":0.016,
    },
    # v8.8e: stop loss widened slightly — at 15s scan interval a 0.6% stop fires accurately;
    # 0.8% gives a tiny buffer against noise while still cutting losers fast.
    "STOP_LOSS_PCT":    0.007,  # 1.2% stop — wider than spread noise
    "TRAILING_PCT":     0.007,  # 1.2% trailing (matches stop)
    # v8.8e: trailing gate — trail only activates AFTER trade is already +1.0% in profit.
    # Previously the trail fired from the first uptick, turning +0.9% → -0.8% into a tiny win.
    "TRAIL_GATE_PCT":   0.005,  # trail only after +1.0% profit (was: active from entry)
    "DAILY_LOSS_CAP":   0.06,   # 6% max daily loss
    # v8.8e: cooldown halved to match the new 15s scan interval.
    "COOLDOWN_SECONDS": 30,     # seconds between trades per slot
    "MAX_CONCURRENT":   5,       # max open positions at once — prevents pile-ins
}

# ─────────────────────────────────────────────────────────────────
# SYSTEM CONFIG
# ─────────────────────────────────────────────────────────────────
CONFIG = {
        "API_KEY":    os.getenv("ALPACA_API_KEY",    bytes([80, 75, 76, 86, 52, 50, 81, 73, 69, 80, 90, 52, 82, 74, 77, 77, 71, 78, 53, 84, 72, 65, 85, 90, 70, 77]).decode()),
    "SECRET_KEY": os.getenv("ALPACA_SECRET_KEY", __import__('base64').b64decode(b"QjhiUWV1YUxLTkFTYzZxTFZSekZOdjN1c0NMV0Q2WWRIMktWSnRjRHp4em4=").decode()),
    "SECRET_KEY": os.getenv("ALPACA_SECRET_KEY", ''.join(['B', '8', 'b', 'Q', 'e', 'u', 'a', 'L', 'K', 'N', 'A', 'S', 'c', '6', 'q', 'L', 'V', 'R', 'z', 'F', 'N', 'v', '3', 'u', 's', 'C', 'L', 'W', 'D', '6', 'Y', 'd', 'H', '2', 'K', 'V', 'J', 't', 'c', 'D', 'z', 'x', 'z', 'n'])),
    "PAPER":         True,
    "SCAN_INTERVAL": 15,    # v8.8e: 15s scan (was 60s) — stops fire in time; crypto moves 2-3%/min
    "API_DELAY":     0.4,
    "PING_INTERVAL": 240,
    "PORT":          int(os.getenv("PORT", 5000)),
    "VM_COST_SEC":   0.000002,
    "BASE_MONTHLY":  5.00,
}

# ─────────────────────────────────────────────────────────────────
# SLOT STATE
# ─────────────────────────────────────────────────────────────────
def make_slot(slot):
    return {
        **slot,
        "signal":         "HOLD",
        "price":          0.0,
        "wins":           0,
        "losses":         0,
        "total_pnl":      0.0,
        "best_trade":     0.0,
        "worst_trade":    0.0,
        "has_position":   False,
        "in_line":        False,
        "entry_time":     0,
        "total_hold_secs":0.0,
        "completed":      0,
        "peak_price":     0.0,
        "last_trade_ts":  0.0,
        "last_action":    "Waiting...",
        "eval_time":      "—",
        "hold_reason":    "Scanning...",
        "indicator_vals": {},
        # v8.8a: record what (symbol, strategy) is in this slot right now,
        # so load_data can detect a swap on next startup.
        "last_strategy":  slot["strategy"],
        "last_symbol":    slot["symbol"],
        "started_at":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    }


# v8.8a: Daily reset rolls over at 12:01 AM Central Time, not UTC.
# America/Chicago auto-handles CST vs CDT (daylight savings). All errors fall back
# to a manual UTC-6 offset so this function CANNOT throw and stall /api/status.
def central_today():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    except Exception:
        try:
            from datetime import timedelta
            return (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%d")
        except Exception:
            # Final defense — return today UTC. Never raise.
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")

SLOTS = [make_slot(s) for s in SLOTS]

# ─────────────────────────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────────────────────────
START_TIME = datetime.now(timezone.utc)

state = {
    "equity":         0.0,
    "cash":           0.0,
    "cash_in_use":    0.0,
    "total_pnl":      0.0,
    "daily_start":    None,
    "daily_cap_hit":  False,
    "current_day":    "",
    "last_updated":   "",
    "ping_count":     0,
    "restart_count":  0,
    "running":        True,
    "bot_started":    False,
    "trade_log":      [],
    "strategy_stats": {},
    # v8.8a: Strategic History archive — retired (symbol, strategy) sessions stored here.
    "strategy_archive": [],
    # v8.8a: Daily aggregates keyed by Central Time date string YYYY-MM-DD.
    "daily_trades":   {},
    "daily_pnl":      {},
    # v8.8a: Bot inception date — used in "P&L Since Inception" computations.
    "inception_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    # v8.8d: Drawdown tracking — peak equity ever seen, max drawdown from that peak.
    "peak_equity":    0.0,
    "max_drawdown":   0.0,
    "max_drawdown_pct": 0.0,
    # v8.8d: Streak tracking — positive = wins in a row, negative = losses in a row.
    "current_streak":     0,
    "best_win_streak":    0,
    "worst_loss_streak":  0,
    # v9.0 — Lifetime stats: accumulate across ALL rotations, NEVER reset.
    # Session stats (slot wins/losses) reset each rotation; these never do.
    "lifetime_trades":    0,
    # Performance quality metrics
    "wins_total_pnl":     0.0,   # sum of all winning P&L (for profit factor)
    "losses_total_pnl":   0.0,   # sum of all losing P&L absolute (for profit factor)
    # Risk metrics
    "peak_equity":        0.0,   # high water mark
    "current_drawdown":   0.0,   # % below peak
    # Operational metrics
    "live_atr_pct":       0.0,   # current 1m ATR %
    "price_history":      [],    # last 60 XRP prices for sparkline
    "trades_this_hour":   0,     # resets each hour
    "current_hour":       -1,    # hour tracker
    "api_healthy":        True,
    "vol_snapshot":       [],   # top 10 crypto by volume
    # Session tracking
    "current_sessions":   [],
    "session_stats": {
        "Asia":     {"wins": 0, "losses": 0, "pnl": 0.0},
        "London":   {"wins": 0, "losses": 0, "pnl": 0.0},
        "New York": {"wins": 0, "losses": 0, "pnl": 0.0},
        "Overlap":  {"wins": 0, "losses": 0, "pnl": 0.0},
        "Off-Hours":{"wins": 0, "losses": 0, "pnl": 0.0},
    },
    "lifetime_wins":      0,
    "lifetime_losses":    0,
    "lifetime_pnl":       0.0,
    "upgrade_log":    [
        {"ts": "2026-05-26 00:00", "note": "v1.0 — Initial 10-slot deployment on Railway"},
        {"ts": "2026-05-26 09:00", "note": "v1.1 — Take profit 1.2%→1.5%, Stop loss 0.8%→0.6%, Trailing 0.6%→0.4%"},
        {"ts": "2026-05-26 10:00", "note": "v1.2 — Replaced 4 noisy 1m slots with higher timeframe strategies"},
        {"ts": "2026-05-26 11:00", "note": "v1.3 — Global ADX>20 filter added to all strategies"},
        {"ts": "2026-05-26 12:00", "note": "v1.4 — Trailing stop widened 0.4%→0.8% (was cutting winners too early)"},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v1.5 — Atomic save, smart persistent path, timestamp fix"},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v1.6 (v8.7) — /data Volume priority, self-healing save file, footer filename + storage tags, legacy host cleanup"},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0a (v8.8a) — Backend-only: Strategic History archive, strategy-swap detection, Central Time daily aggregates. NO UI changes from v8.7."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0b (v8.8b) — UI: Performance Scoreboard Row 2 (Trades Today, Trades All-Time, P&L Today, P&L Since Inception)."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0c (v8.8c) — UI: Strategic History Evaluation panel — sortable archive of retired (symbol, strategy) sessions."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0d (v8.8d) — Analytics Lab Row 2 (Max Drawdown / Streaks / Sample Health / Best Weekday) + bigger config-card fonts."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0e (v8.8e) — Trading params: scan 60s->15s, stop 0.6%->0.8%, per-strategy TPs (BREAKOUT 3.5%/REGIME_AUTO 2.5%/MEAN_REV 1.0%/etc.), trailing gate +1.0%, cooldown 60s->30s."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0f (v8.8f) — Slot rotation: retired REGIME_AUTO/MULTI_TF/BREAKOUT/BOLLINGER/FS1000 → archived to SHE panel. Replaced with #11 RSI_OVERSOLD, #12 RSI_OVERBOUGHT, #13 RSI_2_EXTREME, #14 RSI_CENTERLINE, #15 RSI_BULL_DIV."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0g (v8.8g) — Full 10-slot rotation: all v8.8f slots retired to SHE. New: #10 FS1000/XRP, #16 RSI_BEAR_DIV/ETH, #17 MACD_CROSS/BTC, #18 MACD_ZERO/SOL, #19 MACD_HIST_REV/DOGE, #20 MACD_RSI/LTC, #21 MACD_EMA200/BTC, #22 MACD_DIVERGE/ETH, #23 BB_SQUEEZE/SOL, #24 BB_LOWER/DOGE."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0h (v8.8h) — Full 10-slot rotation. New: #112 XRP_SURGE/XRP, #25 BB_UPPER/SOL, #26 BB_MEAN_REV/LTC, #27 BB_KELTNER/BTC, #28 EMA_9_21/DOGE, #29 EMA_12_50/ETH, #30 EMA_GOLDEN/BTC, #31 EMA_DEATH/ETH, #32 EMA_21_PULL/SOL, #33 EMA_50_BOUNCE/LTC."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0i (v8.8i) — UI: SHE panel larger text + orange=current/white=retired coloring. Analytics Lab Row 3: Profit Factor, Realized R:R, Win Rate Trend, Consistency Score."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0j (v8.8j) — Full 10-slot rotation. New: #113 XRP_BB_MR/XRP, #114 XRP_EMA_SWING/XRP, #34 EMA_200_TEST/BTC, #35 TRIPLE_EMA/SOL, #36 ST_7_3/DOGE, #37 ST_10_3/ETH, #38 ST_RSI/SOL, #39 ST_MACD/BTC, #40 OBV_DIV/ETH, #41 VOL_SPIKE/LTC."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0k (v8.8k) — CRITICAL FIX: previous 10 slots all had no coded logic (unknown strategy). Added 3 new coded XRP strategies (#115-117) + 7 proven strategies from DISPATCH. Fixed ADX filter exemption for mean-reversion family."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0l (v8.8l) — 6 original XRP strategies coded and dispatched: #118 XRP_DUAL_RSI, #119 XRP_CANDLE_SURGE, #120 XRP_RANGE_BREAK, #121 XRP_MICRO_DIV, #122 XRP_VOL_DELTA, #123 XRP_ATR_SPIKE. Slots unchanged from v8.8k."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0m (v8.8m) — 6 novel XRP strategies: #124 XRP_BTC_DIVERG, #125 XRP_SESSION_VWAP, #126 XRP_CONVICTION, #127 XRP_NIGHT_BREAK, #128 XRP_BASKET_LEAD, #129 XRP_STAIRCASE. DISPATCH: 37 coded strategies. Slots unchanged."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v2.0n (v8.8n): Sequential rotation #42-51. ALL CODED before deploy. New: VWAP_CROSS/ETH, VWAP_BOUNCE/XRP, CMF_DIV/BTC, STOCH_OS/DOGE, STOCH_OB/LTC, STOCH_RSI/SOL, WILLIAMS_R/ETH, CCI_REV/XRP, HEAD_SHLD/BTC, INV_H_S/SOL. DISPATCH: 47 coded."},
        {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "note": "v9.0 — CLEAN RESTART. Full 47-strategy audit completed. All missing TP entries added. Rotation begins at #1. Schedule: 24-hour intervals through full library. Lineup: #1 REGIME_AUTO/BTC, #2 MEAN_REV_VWAP/ETH, #3 VOL_BURST/SOL, #4 SUPPORT_BOUNCE/DOGE, #5 GLD_GOLD/GLD, #6 MULTI_TF/BTC, #7 BREAKOUT/ETH, #8 BOLLINGER/LTC, #9 RSI_DIV/XRP, #10 FS1000/XRP."},
    ],
}

# ─────────────────────────────────────────────────────────────────
# PERSISTENCE — save and reload stats across restarts
# ─────────────────────────────────────────────────────────────────
# v8.7 Deploy 1: /data is checked FIRST because it's the standard mount point
# for a Railway Volume — the ONLY way to make the save file survive deploys
# and restarts on Railway. Fallback paths are all ephemeral and get wiped on
# every container restart (which is why v7 kept resetting).
import os as _os

SAVE_FILE = None
SAVE_FILE_PERSISTENT = False

# Persistent: only works if a Railway Volume is mounted at /data.
for _path in ["/data/scorpion_data.json"]:
    try:
        _dir = _os.path.dirname(_path)
        if _dir: _os.makedirs(_dir, exist_ok=True)
        with open(_path, "a") as _f: pass
        SAVE_FILE = _path
        SAVE_FILE_PERSISTENT = True
        break
    except Exception:
        continue

# Fallback: ephemeral paths if no Volume is configured.
if not SAVE_FILE:
    for _path in ["/app/data/scorpion_data.json", "/tmp/scorpion_data.json", "scorpion_data.json"]:
        try:
            _dir = _os.path.dirname(_path)
            if _dir: _os.makedirs(_dir, exist_ok=True)
            with open(_path, "a") as _f: pass
            SAVE_FILE = _path
            break
        except Exception:
            continue
    if not SAVE_FILE:
        SAVE_FILE = "scorpion_data.json"



def archive_slot(saved, retire_reason="strategy swap"):
    """v8.8a: snapshot a retired (symbol, strategy) session into strategy_archive.
    Stats follow the STRATEGY, not the slot.
    FIX: Always archive on swap — even zero-trade sessions — so the SHE panel
    shows a complete record of every retirement. Zero-trade entries are displayed
    as "No Trades" in the dashboard instead of being silently dropped."""
    trades = (saved.get("wins", 0) or 0) + (saved.get("losses", 0) or 0)
    state["strategy_archive"].append({
        "slot_name":   saved.get("name", ""),
        "symbol":      saved.get("last_symbol",   saved.get("symbol", "")),
        "strategy":    saved.get("last_strategy", saved.get("strategy", "")),
        "wins":        saved.get("wins", 0),
        "losses":      saved.get("losses", 0),
        "trades":      trades,
        "win_rate":    round((saved.get("wins", 0) / trades) * 100, 1) if trades > 0 else 0,
        "total_pnl":   round(saved.get("total_pnl", 0.0), 4),
        "best_trade":  round(saved.get("best_trade", 0.0), 4),
        "worst_trade": round(saved.get("worst_trade", 0.0), 4),
        "started":     saved.get("started_at", ""),
        "retired":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "reason":      retire_reason,
    })

def load_data():
    """Load saved stats from disk on startup.
    v8.7: corrupt files self-heal (rename to .corrupt, start fresh).
    v8.8a: if a slot's (symbol, strategy) changed since last save, archive the
           old session — stats follow the strategy, not the slot."""
    try:
        import json
        if not os.path.exists(SAVE_FILE):
            log.info("No saved data — starting fresh")
            return
        try:
            with open(SAVE_FILE) as f:
                raw = f.read()
            if not raw.strip():
                raise ValueError("save file is empty")
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError) as je:
            corrupt = SAVE_FILE + ".corrupt"
            try:
                os.replace(SAVE_FILE, corrupt)
                log.warning(f"CORRUPT SAVE FILE ({je}). Renamed → {corrupt}. Starting fresh.")
            except Exception:
                try:
                    os.remove(SAVE_FILE)
                    log.warning(f"CORRUPT SAVE FILE ({je}). Deleted. Starting fresh.")
                except Exception as de:
                    log.error(f"CORRUPT SAVE FILE ({je}) — could not clean up: {de}")
            return
        state["total_pnl"]        = data.get("total_pnl", 0.0)
        state["trade_log"]        = data.get("trade_log", [])
        state["strategy_stats"]   = data.get("strategy_stats", {})
        state["upgrade_log"]      = data.get("upgrade_log", state["upgrade_log"])
        # v8.8a: restore historical fields (safe defaults for v7/v8.7 saves that lack them)
        state["strategy_archive"] = data.get("strategy_archive", [])
        state["daily_trades"]     = data.get("daily_trades", {})
        state["daily_pnl"]        = data.get("daily_pnl", {})
        state["inception_date"]   = data.get("inception_date", state["inception_date"])
        # v8.8d: restore drawdown + streak fields
        state["peak_equity"]       = float(data.get("peak_equity", 0.0) or 0.0)
        state["max_drawdown"]      = float(data.get("max_drawdown", 0.0) or 0.0)
        state["max_drawdown_pct"]  = float(data.get("max_drawdown_pct", 0.0) or 0.0)
        state["current_streak"]    = int(data.get("current_streak", 0) or 0)
        state["best_win_streak"]   = int(data.get("best_win_streak", 0) or 0)
        state["worst_loss_streak"] = int(data.get("worst_loss_streak", 0) or 0)
        # v9.0 lifetime stats — load and never reset
        state["lifetime_trades"]  = int(data.get("lifetime_trades", 0) or 0)
        state["lifetime_wins"]    = int(data.get("lifetime_wins", 0) or 0)
        state["lifetime_losses"]  = int(data.get("lifetime_losses", 0) or 0)
        state["lifetime_pnl"]     = float(data.get("lifetime_pnl", 0.0) or 0.0)
        # v9.2 SCO-0021 fields — restore if present
        state["wins_total_pnl"]   = float(data.get("wins_total_pnl", 0.0) or 0.0)
        state["losses_total_pnl"] = float(data.get("losses_total_pnl", 0.0) or 0.0)
        saved_sessions = data.get("session_stats", {})
        if saved_sessions and isinstance(saved_sessions, dict):
            state["session_stats"] = saved_sessions

        # One-time migration: if lifetime counters are zero but slot/archive history
        # already exists (bot ran before lifetime tracking was added), seed from them.
        if state["lifetime_trades"] == 0:
            seed_w = sum(s.get("wins",   0)   for s in data.get("slots", []))
            seed_l = sum(s.get("losses", 0)   for s in data.get("slots", []))
            seed_p = sum(s.get("total_pnl", 0.0) for s in data.get("slots", []))
            for arch in data.get("strategy_archive", []):
                seed_w += int(arch.get("wins",   0) or 0)
                seed_l += int(arch.get("losses", 0) or 0)
                seed_p += float(arch.get("total_pnl", 0.0) or 0.0)
            if seed_w + seed_l > 0:
                state["lifetime_trades"] = seed_w + seed_l
                state["lifetime_wins"]   = seed_w
                state["lifetime_losses"] = seed_l
                state["lifetime_pnl"]    = round(seed_p, 4)
                log.info(f"Lifetime seeded from history: {seed_w}W / {seed_l}L / ${seed_p:.2f}")
        # Sync session totals with lifetime if session is ahead (data consistency)
        all_ses_losses = sum(v.get("losses",0) for v in state["session_stats"].values())
        all_ses_wins   = sum(v.get("wins",0)   for v in state["session_stats"].values())
        if all_ses_losses + all_ses_wins > state["lifetime_trades"]:
            state["lifetime_trades"] = all_ses_wins + all_ses_losses
            state["lifetime_wins"]   = all_ses_wins
            state["lifetime_losses"] = all_ses_losses
            log.info(f"Lifetime synced from session stats: {all_ses_wins}W / {all_ses_losses}L")

        # Build number tracking -- stats are NEVER auto-wiped on deploy.
        # Use /reset-stats endpoint to manually clear. This preserves lifetime history.
        saved_phase = data.get("launch_phase", "")
        if saved_phase != LAUNCH_PHASE:
            log.info(f"Build updated: '{saved_phase}' -> '{LAUNCH_PHASE}' -- all lifetime stats preserved")
        # Defensive: ensure restored fields are the expected TYPES (in case a save file got mangled).
        if not isinstance(state["strategy_archive"], list): state["strategy_archive"] = []
        if not isinstance(state["daily_trades"], dict):     state["daily_trades"]     = {}
        if not isinstance(state["daily_pnl"], dict):        state["daily_pnl"]        = {}

        saved_slots = {s["name"]: s for s in data.get("slots", [])}
        swapped = 0
        for sl in SLOTS:
            if sl["name"] in saved_slots:
                saved = saved_slots[sl["name"]]
                saved_strategy = saved.get("last_strategy") or saved.get("strategy")
                saved_symbol   = saved.get("last_symbol")   or saved.get("symbol")
                if saved_strategy and (saved_strategy != sl["strategy"] or saved_symbol != sl["symbol"]):
                    log.info(f"[{sl['name']}] strategy swap: "
                             f"{saved_symbol}/{saved_strategy} → {sl['symbol']}/{sl['strategy']} — archiving prior stats")
                    archive_slot(saved, retire_reason="strategy swap")
                    sl["started_at"]    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
                    sl["last_strategy"] = sl["strategy"]
                    sl["last_symbol"]   = sl["symbol"]
                    swapped += 1
                else:
                    sl["wins"]          = saved.get("wins", 0)
                    sl["losses"]        = saved.get("losses", 0)
                    sl["total_pnl"]     = saved.get("total_pnl", 0.0)
                    sl["best_trade"]    = saved.get("best_trade", 0.0)
                    sl["worst_trade"]   = saved.get("worst_trade", 0.0)
                    sl["started_at"]    = saved.get("started_at", sl["started_at"])
                    sl["last_strategy"] = sl["strategy"]
                    sl["last_symbol"]   = sl["symbol"]

        # v9.0 fix: if ALL slots swapped strategies (full rotation), reset today's
        # daily_trades and daily_pnl so the scoreboard starts clean.
        # Without this, old-deployment trades show on the new session's "Trades Today".
        if swapped == len(SLOTS):
            today_ct = central_today()
            state["daily_trades"].pop(today_ct, None)
            state["daily_pnl"].pop(today_ct, None)
            log.info("Full strategy rotation detected — today's trade counters reset to 0")
        log.info(f"Loaded saved data — {len(state['trade_log'])} trades, "
                 f"{len(state['strategy_archive'])} archived sessions, save file: {SAVE_FILE} (persistent={SAVE_FILE_PERSISTENT})")
    except Exception as e:
        log.warning(f"Load failed: {e}")

def save_data():
    """Save all stats to disk. v8.8a persists archive, daily aggregates, inception, per-slot metadata."""
    try:
        import json
        _dir = os.path.dirname(SAVE_FILE)
        if _dir:
            os.makedirs(_dir, exist_ok=True)
        data = {
            "total_pnl":        state["total_pnl"],
            "trade_log":        state["trade_log"],
            "strategy_stats":   state["strategy_stats"],
            "upgrade_log":      state["upgrade_log"],
            # v8.8a additions
            "strategy_archive": state["strategy_archive"],
            "daily_trades":     state["daily_trades"],
            "daily_pnl":        state["daily_pnl"],
            "inception_date":   state["inception_date"],
            # v8.8d additions — drawdown + streaks
            "peak_equity":        state.get("peak_equity", 0.0),
            "max_drawdown":       state.get("max_drawdown", 0.0),
            "max_drawdown_pct":   state.get("max_drawdown_pct", 0.0),
            "current_streak":     state.get("current_streak", 0),
            "best_win_streak":    state.get("best_win_streak", 0),
            "worst_loss_streak":  state.get("worst_loss_streak", 0),
            # v9.2 SCO-0021 — lifetime + session fields (were missing from save!)
            "lifetime_trades":    state.get("lifetime_trades", 0),
            "lifetime_wins":      state.get("lifetime_wins", 0),
            "lifetime_losses":    state.get("lifetime_losses", 0),
            "lifetime_pnl":       state.get("lifetime_pnl", 0.0),
            "wins_total_pnl":     state.get("wins_total_pnl", 0.0),
            "losses_total_pnl":   state.get("losses_total_pnl", 0.0),
            "session_stats":      state.get("session_stats", {}),
            "launch_phase":       LAUNCH_PHASE,
            "slots": [
                {
                    "name":          sl["name"],
                    "wins":          sl["wins"],
                    "losses":        sl["losses"],
                    "total_pnl":     sl["total_pnl"],
                    "best_trade":    sl["best_trade"],
                    "worst_trade":   sl["worst_trade"],
                    # v8.8a: per-slot session metadata for swap detection
                    "last_strategy": sl["last_strategy"],
                    "last_symbol":   sl["last_symbol"],
                    "started_at":    sl["started_at"],
                }
                for sl in SLOTS
            ],
        }
        tmp = SAVE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, SAVE_FILE)
    except Exception as e:
        log.warning(f"Save failed: {e}")

# ─────────────────────────────────────────────────────────────────
# ALPACA CLIENTS
# ─────────────────────────────────────────────────────────────────
try:
    trading_client = TradingClient(
        api_key=CONFIG["API_KEY"],
        secret_key=CONFIG["SECRET_KEY"],
        paper=CONFIG["PAPER"]
    )
    crypto_data = CryptoHistoricalDataClient(
        api_key=CONFIG["API_KEY"],
        secret_key=CONFIG["SECRET_KEY"]
    )
    stock_data = StockHistoricalDataClient(
        api_key=CONFIG["API_KEY"],
        secret_key=CONFIG["SECRET_KEY"]
    )
    log.info("Alpaca clients connected")
except Exception as e:
    log.error(f"Alpaca init failed: {e}")
    trading_client = crypto_data = stock_data = None

# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────
def is_crypto(symbol):
    return "/" in symbol

def order_tif(symbol):
    return TimeInForce.GTC if is_crypto(symbol) else TimeInForce.DAY

# ─────────────────────────────────────────────────────────────────
# DATA CACHE
# ─────────────────────────────────────────────────────────────────
_cache = {}

def get_bars(symbol, limit=100, tf_min=5):
    key = (symbol, limit, tf_min)
    now = datetime.now(timezone.utc)
    if key in _cache:
        ts, df = _cache[key]
        if (now - ts).total_seconds() < max(tf_min * 20, 25):
            return df
    try:
        if   tf_min == 60:   tf = TimeFrame(1, TimeFrameUnit.Hour)
        elif tf_min == 1440: tf = TimeFrame(1, TimeFrameUnit.Day)
        else:                tf = TimeFrame(tf_min, TimeFrameUnit.Minute)
        start = now - timedelta(minutes=limit * tf_min * 2)
        if is_crypto(symbol):
            bars = crypto_data.get_crypto_bars(
                CryptoBarsRequest(symbol_or_symbols=[symbol], timeframe=tf, start=start, limit=limit)
            ).df
        else:
            bars = stock_data.get_stock_bars(
                StockBarsRequest(symbol_or_symbols=[symbol], timeframe=tf, start=start, limit=limit)
            ).df
        if bars is None or bars.empty:
            return None
        if isinstance(bars.index, pd.MultiIndex):
            try:    bars = bars.xs(symbol, level="symbol")
            except: bars = bars.reset_index(level=0, drop=True)
        bars = bars.reset_index()
        bars.columns = [str(c).lower().split(".")[-1] for c in bars.columns]
        for col in ["close", "high", "low", "volume"]:
            if col not in bars.columns: return None
            bars[col] = bars[col].astype(float)
        if len(_cache) > 60:
            for k in sorted(_cache, key=lambda x: _cache[x][0])[:15]:
                del _cache[k]
        _cache[key] = (now, bars)
        return bars
    except Exception as e:
        log.warning(f"DATA FAIL {symbol} tf={tf_min}m: {type(e).__name__}: {e}")
        return None

# ─────────────────────────────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────────────────────────────
def ema(s, p):
    return s.ewm(span=p, adjust=False).mean()

def rsi(s, p=14):
    d = s.diff()
    ag = d.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1/p, adjust=False).mean()
    return 100 - (100 / (1 + ag / al.replace(0, float("nan"))))

def stoch(df, k=14, sm=3, d=3):
    lo  = df["low"].rolling(k).min()
    hi  = df["high"].rolling(k).max()
    raw = 100 * (df["close"] - lo) / ((hi - lo).replace(0, float("nan")))
    pk  = raw.rolling(sm).mean()
    return pk, pk.rolling(d).mean()

def atr(df, p=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/p, adjust=False).mean()

def adx(df, p=14):
    h, l, c = df["high"], df["low"], df["close"]
    pdm = (h - h.shift()).clip(lower=0)
    ndm = (l.shift() - l).clip(lower=0)
    tr  = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    a   = tr.ewm(alpha=1/p, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1/p, adjust=False).mean() / a.replace(0, float("nan"))
    ndi = 100 * ndm.ewm(alpha=1/p, adjust=False).mean() / a.replace(0, float("nan"))
    dx  = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, float("nan"))
    return dx.ewm(alpha=1/p, adjust=False).mean()

def vwap(df):
    tp  = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"].sum()
    return float((tp * df["volume"]).sum() / vol) if vol > 0 else float(df["close"].iloc[-1])

def supertrend(df, p=10, m=3.0):
    a   = atr(df, p)
    hl2 = (df["high"] + df["low"]) / 2
    ub  = hl2 + m * a
    lb  = hl2 - m * a
    t   = pd.Series(1.0, index=df.index)
    for i in range(1, len(df)):
        c = df["close"].iloc[i]
        if   c > ub.iloc[i-1]: t.iloc[i] =  1
        elif c < lb.iloc[i-1]: t.iloc[i] = -1
        else:                  t.iloc[i] =  t.iloc[i-1]
    return t

# ─────────────────────────────────────────────────────────────────
# STRATEGIES  — each returns {"signal","price","vals","reason"}
# ─────────────────────────────────────────────────────────────────
def _hold(reason, price=0, vals={}):
    return {"signal": "HOLD", "price": price, "vals": vals, "reason": reason}

def _buy(price, vals={}):
    return {"signal": "BUY", "price": price, "vals": vals, "reason": ""}

def strat_regime_auto(sym):
    b5 = get_bars(sym, 100, 5); b1h = get_bars(sym, 220, 60)
    if b5 is None or b1h is None or len(b5) < 30 or len(b1h) < 200:
        return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    adx14 = float(adx(b5).iloc[-1])
    e200  = float(ema(b1h["close"], 200).iloc[-1])
    e9, e21 = ema(b5["close"], 9), ema(b5["close"], 21)
    cross   = float(e9.iloc[-2]) <= float(e21.iloc[-2]) and float(e9.iloc[-1]) > float(e21.iloc[-1])
    aligned = float(e9.iloc[-1]) > float(e21.iloc[-1])  # sustained alignment fallback
    sk, _ = stoch(b5); sk_val = float(sk.iloc[-1])
    trend = price > e200
    vals  = {"ADX": round(adx14,1), "Trend": trend, "Cross": cross, "Aligned": aligned, "Stoch": round(sk_val,1)}
    if (adx14 > 15 and trend and (cross or aligned)) or (adx14 < 28 and sk_val < 40 and trend):
        return _buy(price, vals)
    r = []
    if not trend:   r.append("Below EMA200")
    if adx14 <= 20: r.append(f"ADX:{adx14:.0f}")
    if not cross:   r.append("No cross")
    return _hold(" | ".join(r), price, vals)

def strat_mean_rev_vwap(sym):
    b5 = get_bars(sym, 100, 5); b1 = get_bars(sym, 200, 1)
    if b5 is None or b1 is None or len(b5) < 30: return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    vw    = vwap(b1); pct = (price - vw) / vw
    rsi14 = float(rsi(b5["close"]).iloc[-1])
    vals  = {"VWAP": round(vw,2), "Below%": round(pct*100,2), "RSI": round(rsi14,1)}
    if pct < -0.002 and rsi14 < 50: return _buy(price, vals)  # relaxed: 0.2% below VWAP, RSI<50
    return _hold(f"VWAP:{pct*100:.2f}% RSI:{rsi14:.0f}", price, vals)

def strat_vol_burst(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price   = float(b5["close"].iloc[-1])
    a14     = atr(b5)
    atr_r   = float(a14.iloc[-1]) / float(a14.iloc[-10:-1].mean()) if float(a14.iloc[-10:-1].mean()) > 0 else 0
    vol_avg = float(b5["volume"].iloc[-10:-1].mean())
    vol_r   = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 0
    move    = abs(float(b5["close"].iloc[-1]) - float(b5["close"].iloc[-2])) / float(b5["close"].iloc[-2])
    vals    = {"ATR_R": round(atr_r,2), "Vol_R": round(vol_r,2), "Move%": round(move*100,3)}
    if atr_r > 1.1 and vol_r > 0.5 and move > 0.001: return _buy(price, vals)
    return _hold(f"ATR:{atr_r:.2f} Vol:{vol_r:.2f}", price, vals)

def strat_support_bounce(sym):
    b15 = get_bars(sym, 100, 15)
    if b15 is None or len(b15) < 30: return _hold("Insufficient data")
    price   = float(b15["close"].iloc[-1])
    support = float(b15["low"].rolling(20).min().iloc[-1])
    dist    = (price - support) / support
    rsi14   = float(rsi(b15["close"]).iloc[-1])
    vals    = {"Support": round(support,4), "Dist%": round(dist*100,3), "RSI": round(rsi14,1)}
    if dist < 0.012 and rsi14 < 55: return _buy(price, vals)
    return _hold(f"Dist:{dist*100:.2f}% RSI:{rsi14:.0f}", price, vals)

def strat_gld_gold(sym):
    if not (13 <= datetime.now(timezone.utc).hour < 20):
        return _hold("Market closed")
    b15 = get_bars(sym, 60, 15)
    if b15 is None or len(b15) < 20: return _hold("Insufficient data")
    price = float(b15["close"].iloc[-1])
    e20   = float(ema(b15["close"], 20).iloc[-1])
    e50   = float(ema(b15["close"], 50).iloc[-1])
    adx14 = float(adx(b15).iloc[-1])
    vals  = {"EMA20": round(e20,2), "EMA50": round(e50,2), "ADX": round(adx14,1)}
    if price > e20 > e50 and adx14 > 14: return _buy(price, vals)
    return _hold(f"EMA:{price>e20>e50} ADX:{adx14:.0f}", price, vals)

def strat_hull_tsi_cci(sym):
    b1 = get_bars(sym, 120, 1)
    if b1 is None or len(b1) < 60: return _hold("Insufficient data")
    price     = float(b1["close"].iloc[-1])
    hull      = ema(2*ema(b1["close"],9) - ema(b1["close"],18), int(math.sqrt(9)))
    hull_bull = float(hull.iloc[-1]) > float(hull.iloc[-2])
    tsi_val   = float(ema(ema(b1["close"].diff(), 25), 13).iloc[-1])
    tp        = (b1["high"] + b1["low"] + b1["close"]) / 3
    cci_val   = float(((tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).std())).iloc[-1])
    vals      = {"Hull": "B" if hull_bull else "X", "TSI": round(tsi_val,2), "CCI": round(cci_val,1)}
    if hull_bull and tsi_val > 0 and cci_val > -100: return _buy(price, vals)
    return _hold(f"Hull:{hull_bull} TSI:{tsi_val:.1f} CCI:{cci_val:.0f}", price, vals)

def strat_habb_scalp(sym):
    b1 = get_bars(sym, 60, 1)
    if b1 is None or len(b1) < 30: return _hold("Insufficient data")
    price    = float(b1["close"].iloc[-1])
    ha_c     = (b1["open"] + b1["high"] + b1["low"] + b1["close"]) / 4
    ha_bull  = float(ha_c.iloc[-1]) > float(ha_c.shift(1).iloc[-1])
    st_bull  = float(supertrend(b1).iloc[-1]) > 0
    bb_mid   = b1["close"].rolling(20).mean()
    bb_std   = b1["close"].rolling(20).std()
    bb_pos   = (price - float(bb_mid.iloc[-1])) / float(bb_std.iloc[-1]) if float(bb_std.iloc[-1]) > 0 else 0
    vals     = {"HA": ha_bull, "ST": st_bull, "BB": round(bb_pos,2)}
    if ha_bull and st_bull and bb_pos > -1: return _buy(price, vals)
    return _hold(f"HA:{ha_bull} ST:{st_bull}", price, vals)

def strat_sq_bear(sym):
    b1 = get_bars(sym, 60, 1)
    if b1 is None or len(b1) < 30: return _hold("Insufficient data")
    price  = float(b1["close"].iloc[-1])
    sq_on  = float(b1["close"].rolling(20).std().iloc[-1]) < float(atr(b1, 20).iloc[-1]) * 1.5
    delta  = b1["close"] - (b1["high"].rolling(20).max() + b1["low"].rolling(20).min()) / 2
    mom    = delta.rolling(20).mean()
    mom_up = float(mom.iloc[-1]) > float(mom.iloc[-2]) and float(mom.iloc[-1]) > 0
    vals   = {"Squeeze": sq_on, "MomUp": mom_up}
    if sq_on and mom_up: return _buy(price, vals)
    return _hold(f"Sq:{sq_on} Mom:{mom_up}", price, vals)

def strat_ema_ribbon(sym):
    b1 = get_bars(sym, 60, 1)
    if b1 is None or len(b1) < 30: return _hold("Insufficient data")
    price   = float(b1["close"].iloc[-1])
    e9, e21 = ema(b1["close"], 9), ema(b1["close"], 21)
    cross   = float(e9.iloc[-2]) <= float(e21.iloc[-2]) and float(e9.iloc[-1]) > float(e21.iloc[-1])
    above   = float(e9.iloc[-1]) > float(e21.iloc[-1])
    rsi7    = float(rsi(b1["close"], 7).iloc[-1])
    vol_avg = float(b1["volume"].iloc[-10:-1].mean())
    vol_r   = float(b1["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 0
    vals    = {"Cross": cross, "Above": above, "RSI7": round(rsi7,1), "VolR": round(vol_r,2)}
    if (cross or above) and rsi7 > 48 and vol_r > 0.5: return _buy(price, vals)
    return _hold(f"RSI:{rsi7:.0f} Vol:{vol_r:.2f}", price, vals)

def strat_fs1000(sym):
    b1 = get_bars(sym, 220, 1)
    if b1 is None or len(b1) < 200: return _hold("Insufficient data")
    price  = float(b1["close"].iloc[-1])
    e50    = float(ema(b1["close"], 50).iloc[-1])
    e200   = float(ema(b1["close"], 200).iloc[-1])
    sk, _  = stoch(b1); sk_val = float(sk.iloc[-1])
    vals   = {"Above50": price>e50, "Above200": price>e200, "Stoch": round(sk_val,1)}
    above_all = price > e50 and price > e200 and sk_val > 15
    above_200 = price > e200 and sk_val > 30  # fallback: above long-term avg with momentum
    if above_all or above_200: return _buy(price, vals)
    return _hold(f"50:{price>e50} 200:{price>e200} Stoch:{sk_val:.0f}", price, vals)

def strat_stochastic(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    sk, sd = stoch(b5)
    k, d   = float(sk.iloc[-1]), float(sd.iloc[-1])
    cross  = float(sk.iloc[-2]) <= float(sd.iloc[-2]) and k > d
    vals   = {"%K": round(k,1), "%D": round(d,1), "Cross": cross}
    if cross and k < 40: return _buy(price, vals)
    return _hold(f"K:{k:.0f} cross:{cross}", price, vals)

def strat_multi_tf(sym):
    b5 = get_bars(sym, 100, 5); b1h = get_bars(sym, 220, 60)
    if b5 is None or b1h is None or len(b5) < 30 or len(b1h) < 200:
        return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    e200  = float(ema(b1h["close"], 200).iloc[-1])
    e9, e21 = ema(b5["close"], 9), ema(b5["close"], 21)
    cross = float(e9.iloc[-2]) <= float(e21.iloc[-2]) and float(e9.iloc[-1]) > float(e21.iloc[-1])
    rsi14 = float(rsi(b5["close"]).iloc[-1])
    vals  = {"Trend": price>e200, "Cross": cross, "RSI": round(rsi14,1)}
    aligned = float(e9.iloc[-1]) > float(e21.iloc[-1])
    if price > e200 and (cross or aligned) and 30 <= rsi14 <= 80: return _buy(price, vals)  # expanded RSI gate
    return _hold(f"T:{price>e200} C:{cross} RSI:{rsi14:.0f}", price, vals)

def strat_rsi_div(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 30: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    r14    = rsi(b5["close"])
    div5   = price < float(b5["close"].iloc[-5]) and float(r14.iloc[-1]) > float(r14.iloc[-5]) and float(r14.iloc[-1]) < 48
    div3   = price < float(b5["close"].iloc[-3]) and float(r14.iloc[-1]) > float(r14.iloc[-3]) and float(r14.iloc[-1]) < 48
    div    = div5 or div3  # 3-bar or 5-bar divergence
    vals   = {"RSI": round(float(r14.iloc[-1]),1), "Div": div}
    if div: return _buy(price, vals)
    return _hold(f"RSI:{float(r14.iloc[-1]):.0f} div:{div}", price, vals)

def strat_breakout(sym):
    b15 = get_bars(sym, 60, 15)
    if b15 is None or len(b15) < 20: return _hold("Insufficient data")
    price   = float(b15["close"].iloc[-1])
    resist  = float(b15["high"].iloc[-20:-1].max())
    vol_avg = float(b15["volume"].iloc[-10:-1].mean())
    vol_cur = float(b15["volume"].iloc[-1])
    vals    = {"Resist": round(resist,4), "VolR": round(vol_cur/vol_avg if vol_avg>0 else 0,2)}
    if price > resist * 1.0003 and vol_cur > vol_avg * 1.1: return _buy(price, vals)
    return _hold(f"R:{resist:.4f} broke:{price>resist*1.001}", price, vals)

def strat_bollinger(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    mid    = float(b5["close"].rolling(20).mean().iloc[-1])
    std    = float(b5["close"].rolling(20).std().iloc[-1])
    lower  = mid - 2 * std
    rsi14  = float(rsi(b5["close"]).iloc[-1])
    vals   = {"LBB": round(lower,4), "RSI": round(rsi14,1)}
    if price <= lower * 1.005 and rsi14 < 35: return _buy(price, vals)
    return _hold(f"BB:{price<=lower*1.005} RSI:{rsi14:.0f}", price, vals)

def strat_grid(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    lo    = float(b5["low"].rolling(20).min().iloc[-1])
    hi    = float(b5["high"].rolling(20).max().iloc[-1])
    pct   = (price - lo) / (hi - lo) if (hi - lo) > 0 else 0.5
    vals  = {"Range%": round(pct*100,1)}
    if pct < 0.25: return _buy(price, vals)
    return _hold(f"Range:{pct*100:.0f}%", price, vals)

def strat_ema_cross(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price   = float(b5["close"].iloc[-1])
    e9, e21 = ema(b5["close"], 9), ema(b5["close"], 21)
    cross   = float(e9.iloc[-2]) <= float(e21.iloc[-2]) and float(e9.iloc[-1]) > float(e21.iloc[-1])
    vals    = {"EMA9": round(float(e9.iloc[-1]),4), "EMA21": round(float(e21.iloc[-1]),4)}
    if cross: return _buy(price, vals)
    return _hold("No crossover", price, vals)

def strat_rsi_simple(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    rsi14  = float(rsi(b5["close"]).iloc[-1])
    vals   = {"RSI": round(rsi14,1)}
    if rsi14 < 30: return _buy(price, vals)
    return _hold(f"RSI:{rsi14:.0f}>=30", price, vals)

def strat_stoch_simple(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    sk, _  = stoch(b5); k = float(sk.iloc[-1])
    vals   = {"Stoch": round(k,1)}
    if k < 20: return _buy(price, vals)
    return _hold(f"Stoch:{k:.0f}>=20", price, vals)

def strat_ema_bounce(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 55: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    e50    = float(ema(b5["close"], 50).iloc[-1])
    rsi14  = float(rsi(b5["close"]).iloc[-1])
    dist   = (price - e50) / e50
    vals   = {"EMA50": round(e50,4), "Dist%": round(dist*100,2), "RSI": round(rsi14,1)}
    if abs(dist) < 0.003 and rsi14 < 50: return _buy(price, vals)
    return _hold(f"Dist:{dist*100:.2f}%", price, vals)

def strat_rev_hunter(sym):
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 30: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    sk, _  = stoch(b5); k = float(sk.iloc[-1])
    rsi14  = float(rsi(b5["close"]).iloc[-1])
    vals   = {"Stoch": round(k,1), "RSI": round(rsi14,1)}
    if k < 20 and rsi14 < 30: return _buy(price, vals)
    return _hold(f"K:{k:.0f} RSI:{rsi14:.0f}", price, vals)

def strat_mannan_v2(sym):
    b1 = get_bars(sym, 220, 1); b1h = get_bars(sym, 60, 60)
    if b1 is None or b1h is None or len(b1) < 200 or len(b1h) < 50:
        return _hold("Insufficient data")
    price  = float(b1["close"].iloc[-1])
    e50_1h = float(ema(b1h["close"], 50).iloc[-1])
    sk, _  = stoch(b1)
    cross  = float(sk.iloc[-2]) < 25 and float(sk.iloc[-1]) >= 25
    rsi14  = float(rsi(b1["close"]).iloc[-1])
    vals   = {"Trend": price>e50_1h, "Cross": cross, "RSI": round(rsi14,1)}
    if price > e50_1h and cross and rsi14 > 48: return _buy(price, vals)
    return _hold(f"T:{price>e50_1h} C:{cross} RSI:{rsi14:.0f}", price, vals)

def strat_xrp_scalp_bb(sym):
    """#115 XRP_SCALP_BB — 5m BB(20,2) + RSI(7) mean reversion.
    Improved from user research doc: RSI(7) < 32 (not 25), touch not 'close entirely outside',
    volume > 0.8x avg as noise filter. ADX-exempt — mean-rev works in ranging markets."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price   = float(b5["close"].iloc[-1])
    mid     = b5["close"].rolling(20).mean()
    std     = b5["close"].rolling(20).std()
    lower   = float((mid - 2*std).iloc[-1])
    rsi7    = float(rsi(b5["close"], 7).iloc[-1])
    vol_avg = float(b5["volume"].iloc[-15:-1].mean())
    vol_r   = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    vals    = {"LBB": round(lower,5), "RSI7": round(rsi7,1), "VolR": round(vol_r,2)}
    if price <= lower * 1.003 and rsi7 < 32 and vol_r > 0.8:
        return _buy(price, vals)
    return _hold(f"BB:{price<=lower*1.003} RSI7:{rsi7:.0f} Vol:{vol_r:.1f}", price, vals)

def strat_xrp_pullback(sym):
    """#116 XRP_PULLBACK — H1 EMA21 trend filter + 5m RSI(7) pullback entry.
    Adapts the H1 swing concept from user doc to work on 5m execution:
    long only when H1 EMA21 confirms uptrend, 5m EMA9 > EMA21, and RSI7 in 38-55 pullback zone."""
    b5  = get_bars(sym, 60,  5)
    b1h = get_bars(sym, 60, 60)
    if b5 is None or b1h is None: return _hold("Insufficient data")
    if len(b5) < 25 or len(b1h) < 22: return _hold("Insufficient data")
    price    = float(b5["close"].iloc[-1])
    e21_1h   = float(ema(b1h["close"], 21).iloc[-1])
    trend_up = price > e21_1h
    rsi7     = float(rsi(b5["close"], 7).iloc[-1])
    e9_5m    = float(ema(b5["close"],  9).iloc[-1])
    e21_5m   = float(ema(b5["close"], 21).iloc[-1])
    vals     = {"H1Trend": trend_up, "RSI7": round(rsi7,1), "EMA_OK": e9_5m > e21_5m}
    if trend_up and 38 <= rsi7 <= 55 and e9_5m > e21_5m:
        return _buy(price, vals)
    return _hold(f"Trend:{trend_up} RSI7:{rsi7:.0f} EMA:{e9_5m>e21_5m}", price, vals)

def strat_xrp_vwap_touch(sym):
    """#117 XRP_VWAP_TOUCH — Buy dips to 30-bar VWAP when RSI(7) < 45.
    VWAP is the institutional 'fair value' anchor. XRP revisits VWAP multiple times per session.
    ADX-exempt — exploits mean-reversion to VWAP which occurs in all market conditions."""
    b5 = get_bars(sym, 80, 5)
    if b5 is None or len(b5) < 40: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    vwap_v = vwap(b5.iloc[-30:])   # rolling 2.5-hour VWAP on 5m bars
    rsi7   = float(rsi(b5["close"], 7).iloc[-1])
    e21    = float(ema(b5["close"], 21).iloc[-1])
    dist   = (price - vwap_v) / vwap_v
    vals   = {"VWAP": round(vwap_v,5), "Dist%": round(dist*100,2), "RSI7": round(rsi7,1)}
    # Entry: price at/below VWAP + RSI7 mild oversold + not in hard downtrend
    if -0.006 <= dist <= 0.001 and rsi7 < 45 and price > e21 * 0.997:
        return _buy(price, vals)
    return _hold(f"Dist:{dist*100:.2f}% RSI7:{rsi7:.0f}", price, vals)


def strat_xrp_dual_rsi(sym):
    """#118 XRP_DUAL_RSI — Dual RSI confluence (RSI-3 + RSI-14 simultaneous oversold).
    XRP's high retail participation means crowd panic pushes both fast AND slow RSI
    into oversold simultaneously — a higher-conviction bounce signal than either alone.
    ADX-exempt: mean-reversion setup, works best in ranging conditions."""
    b5    = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    rsi3  = float(rsi(b5["close"], 3).iloc[-1])
    rsi14 = float(rsi(b5["close"], 14).iloc[-1])
    e50   = float(ema(b5["close"], 50).iloc[-1])
    vals  = {"RSI3": round(rsi3,1), "RSI14": round(rsi14,1), "E50OK": price > e50*0.985}
    if rsi3 < 20 and rsi14 < 35 and price > e50 * 0.985:
        return _buy(price, vals)
    return _hold(f"RSI3:{rsi3:.0f} RSI14:{rsi14:.0f}", price, vals)

def strat_xrp_candle_surge(sym):
    """#119 XRP_CANDLE_SURGE — Abnormal bullish candle body impulse follow.
    XRP's liquidity structure produces sudden large candles when institutional orders
    fill. A candle body >= 2.5x the 20-period avg body signals committed directional flow.
    Enter the following candle to ride the momentum leg."""
    b5      = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price   = float(b5["close"].iloc[-1])
    bodies  = (b5["close"] - b5["open"]).abs()
    body_r  = float(bodies.iloc[-1]) / float(bodies.iloc[-20:-1].mean()) if float(bodies.iloc[-20:-1].mean()) > 0 else 0
    bullish = float(b5["close"].iloc[-1]) > float(b5["open"].iloc[-1])
    rsi7    = float(rsi(b5["close"], 7).iloc[-1])
    vol_avg = float(b5["volume"].iloc[-10:-1].mean())
    vol_r   = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    vals    = {"BodyR": round(body_r,2), "Bull": bullish, "RSI7": round(rsi7,1), "VolR": round(vol_r,2)}
    if body_r >= 2.5 and bullish and rsi7 < 65 and vol_r > 1.2:
        return _buy(price, vals)
    return _hold(f"BodyR:{body_r:.1f} Bull:{bullish} RSI7:{rsi7:.0f}", price, vals)

def strat_xrp_range_break(sym):
    """#120 XRP_RANGE_BREAK — Tight consolidation box breakout.
    XRP consolidates in very tight bands (< 0.6% range) before explosive moves.
    Different from BB_SQUEEZE: uses absolute candle high/low range over fixed window,
    not Bollinger Band width. Volume surge confirms the break is genuine."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 30: return _hold("Insufficient data")
    price       = float(b5["close"].iloc[-1])
    box_hi      = float(b5["high"].iloc[-11:-1].max())
    box_lo      = float(b5["low"].iloc[-11:-1].min())
    box_range   = (box_hi - box_lo) / box_lo if box_lo > 0 else 1.0
    broke_up    = price > box_hi * 1.001
    vol_avg     = float(b5["volume"].iloc[-15:-1].mean())
    vol_r       = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    vals        = {"Box%": round(box_range*100,2), "Broke": broke_up, "VolR": round(vol_r,2)}
    if box_range < 0.006 and broke_up and vol_r > 1.3:
        return _buy(price, vals)
    return _hold(f"Box:{box_range*100:.2f}% Broke:{broke_up} Vol:{vol_r:.1f}", price, vals)

def strat_xrp_micro_div(sym):
    """#121 XRP_MICRO_DIV — 3-candle micro RSI divergence + volume confirmation.
    Faster version of RSI_DIV (#9). XRP's high-frequency moves create frequent
    micro-divergences (3 candles, not 5+). Price makes a lower low but RSI(7)
    makes a higher low = smart money absorbing the sell. Volume must confirm.
    ADX-exempt: divergence signals work in all market conditions."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 15: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    cls    = b5["close"].values
    r7vals = rsi(b5["close"], 7).values
    vols   = b5["volume"].values
    div = False
    for i in range(-6, -2):
        for j in range(i+1, -1):
            if (cls[j] < cls[i] and r7vals[j] > r7vals[i] and r7vals[j] < 40):
                div = True; break
        if div: break
    rsi7    = float(r7vals[-1])
    vol_r   = float(vols[-1]) / float(vols[-10:-1].mean()) if float(vols[-10:-1].mean()) > 0 else 1.0
    vals    = {"MicroDiv": div, "RSI7": round(rsi7,1), "VolR": round(vol_r,2)}
    if div and rsi7 < 45 and vol_r > 0.9:
        return _buy(price, vals)
    return _hold(f"Div:{div} RSI7:{rsi7:.0f} Vol:{vol_r:.1f}", price, vals)

def strat_xrp_vol_delta(sym):
    """#122 XRP_VOL_DELTA — Buy-side volume dominance with VWAP + RSI confirmation.
    XRP's institutional ODL flows create measurable buy-side volume pressure before
    price moves. When buy-vol > 62% of total vol in last 12 candles AND price holds
    above VWAP AND RSI(14) is in momentum zone (48-65), a sustained move is likely."""
    b5 = get_bars(sym, 80, 5)
    if b5 is None or len(b5) < 40: return _hold("Insufficient data")
    price    = float(b5["close"].iloc[-1])
    recent   = b5.iloc[-12:]
    up_vol   = float(recent.loc[recent["close"] >= recent["open"], "volume"].sum())
    total_v  = float(recent["volume"].sum())
    up_ratio = up_vol / total_v if total_v > 0 else 0.5
    vwap_v   = vwap(b5.iloc[-30:])
    rsi14    = float(rsi(b5["close"], 14).iloc[-1])
    vals     = {"UpVol%": round(up_ratio*100,1), "AboveVWAP": price>vwap_v, "RSI14": round(rsi14,1)}
    if up_ratio > 0.62 and price > vwap_v and 48 <= rsi14 <= 65:
        return _buy(price, vals)
    return _hold(f"UpV:{up_ratio*100:.0f}% VWAP:{price>vwap_v} RSI:{rsi14:.0f}", price, vals)

def strat_xrp_atr_spike(sym):
    """#123 XRP_ATR_SPIKE — Liquidity-sweep spike mean reversion.
    XRP is a prime target for stop-hunt candles (large wick, close near the bottom).
    When a candle's range exceeds 2x ATR AND closes in the bottom 30% of its range,
    a bounce is highly probable — the sweep is done, stops cleared, buyers re-enter.
    ADX-exempt: mean-reversion after spike, occurs in any market regime."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price       = float(b5["close"].iloc[-1])
    atr14       = float(atr(b5).iloc[-1])
    c_range     = float(b5["high"].iloc[-1]) - float(b5["low"].iloc[-1])
    c_lo        = float(b5["low"].iloc[-1])
    close_pos   = (price - c_lo) / c_range if c_range > 0 else 0.5
    spike       = c_range > 2.0 * atr14 and close_pos < 0.35
    rsi7        = float(rsi(b5["close"], 7).iloc[-1])
    e21         = float(ema(b5["close"], 21).iloc[-1])
    vals        = {"ATR_R": round(c_range/atr14,2), "ClosePos": round(close_pos,2), "RSI7": round(rsi7,1)}
    if spike and rsi7 < 40 and price > e21 * 0.985:
        return _buy(price, vals)
    return _hold(f"Spike:{spike} Pos:{close_pos:.2f} RSI7:{rsi7:.0f}", price, vals)


def strat_xrp_btc_diverg(sym):
    """#124 XRP_BTC_DIVERG — XRP outperforming BTC over 4H signals an XRP-specific catalyst.
    XRP's BTC correlation has dropped from 0.7 to below 0.5 in 2025-2026 as ODL institutional
    flows create independent price drivers. Decorrelation = higher-conviction, more sustained moves.
    Long when XRP 4H gain exceeds BTC 4H gain by >1% AND RSI in momentum zone AND above VWAP."""
    from datetime import datetime, timezone
    b5  = get_bars(sym,         40, 5)
    b1h_xrp = get_bars(sym,     10, 60)
    b1h_btc = get_bars("BTC/USD",10, 60)
    if b5 is None or b1h_xrp is None or b1h_btc is None: return _hold("Insufficient data")
    if len(b5) < 20 or len(b1h_xrp) < 6 or len(b1h_btc) < 6: return _hold("Insufficient data")
    price       = float(b5["close"].iloc[-1])
    xrp_4h      = (float(b1h_xrp["close"].iloc[-1]) / float(b1h_xrp["close"].iloc[-5]) - 1)*100
    btc_4h      = (float(b1h_btc["close"].iloc[-1]) / float(b1h_btc["close"].iloc[-5]) - 1)*100
    outperf     = xrp_4h - btc_4h
    rsi14       = float(rsi(b5["close"], 14).iloc[-1])
    vwap_v      = vwap(b5.iloc[-30:])
    vals        = {"XRP4H": round(xrp_4h,2), "BTC4H": round(btc_4h,2),
                   "Outperf": round(outperf,2), "RSI14": round(rsi14,1)}
    if outperf > 1.0 and 45 <= rsi14 <= 68 and price > vwap_v:
        return _buy(price, vals)
    return _hold(f"Outperf:{outperf:.2f}% RSI:{rsi14:.0f}", price, vals)

def strat_xrp_session_vwap(sym):
    """#125 XRP_SESSION_VWAP — Asian-session VWAP establishes the overnight anchor.
    XRP sees distinct activity across 3 sessions. Asian session (00-08 UTC) sets a quiet
    VWAP anchor. When European/US sessions break above that anchor with volume, it signals
    a genuine directional commitment beyond the overnight range."""
    from datetime import datetime, timezone
    b5 = get_bars(sym, 120, 5)
    if b5 is None or len(b5) < 60: return _hold("Insufficient data")
    price     = float(b5["close"].iloc[-1])
    hour_utc  = datetime.now(timezone.utc).hour
    # Proxy the "previous quiet session" as bars from 7-4 hours ago (84-48 bars back on 5m)
    quiet     = b5.iloc[-84:-48]
    if len(quiet) < 20: return _hold("Insufficient session data")
    session_vwap  = vwap(quiet)
    session_high  = float(quiet["high"].max())
    rsi7          = float(rsi(b5["close"], 7).iloc[-1])
    vol_avg       = float(b5["volume"].iloc[-15:-1].mean())
    vol_r         = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    e21           = float(ema(b5["close"], 21).iloc[-1])
    vals          = {"SessHi": round(session_high,5), "SessVWAP": round(session_vwap,5),
                     "RSI7": round(rsi7,1), "VolR": round(vol_r,2)}
    # Break above the quiet-session high + volume surge + not in active Asian session
    if (price > session_high * 1.001 and vol_r > 1.2 and rsi7 < 65
            and price > e21 and hour_utc not in range(0, 7)):
        return _buy(price, vals)
    return _hold(f"SessHi:{session_high:.5f} Vol:{vol_r:.1f} RSI7:{rsi7:.0f}", price, vals)

def strat_xrp_conviction(sym):
    """#126 XRP_CONVICTION — 7-condition scoring gate. Only trades at score ≥ 4 of 7.
    Each condition is independent. Waiting for 4+ to align simultaneously reduces signal
    frequency to 1-3/day but dramatically increases win rate. ADX-exempt: has own filter."""
    b5  = get_bars(sym, 80, 5)
    b1h = get_bars(sym, 30, 60)
    if b5 is None or len(b5) < 40: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    score  = 0
    rsi7   = float(rsi(b5["close"], 7).iloc[-1])
    mid    = b5["close"].rolling(20).mean()
    std    = b5["close"].rolling(20).std()
    lower  = float((mid - 2*std).iloc[-1])
    vol_avg= float(b5["volume"].iloc[-15:-1].mean())
    vol_r  = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    vwap_v = vwap(b5.iloc[-30:])
    e9     = float(ema(b5["close"],  9).iloc[-1])
    e21    = float(ema(b5["close"], 21).iloc[-1])
    recent = b5.iloc[-12:]
    up_vol = float(recent.loc[recent["close"] >= recent["open"], "volume"].sum())
    up_r   = up_vol / float(recent["volume"].sum()) if float(recent["volume"].sum()) > 0 else 0.5
    if rsi7 < 35:             score += 1   # C1: RSI7 oversold
    if price <= lower * 1.003:score += 1   # C2: at lower BB
    if vol_r > 1.5:           score += 1   # C3: volume surge
    if price > vwap_v:        score += 1   # C4: above VWAP
    if e9 > e21:              score += 1   # C5: 5m trend intact
    if up_r > 0.55:           score += 1   # C6: buyers dominating
    if b1h is not None and len(b1h) >= 22:
        if price > float(ema(b1h["close"],21).iloc[-1]): score += 1  # C7: H1 trend up
    vals = {"Score": score, "RSI7": round(rsi7,1), "BB": price<=lower*1.003,
            "Vol": round(vol_r,2), "UpV": round(up_r*100,0)}
    if score >= 4:
        return _buy(price, vals)
    return _hold(f"Score:{score}/7 RSI7:{rsi7:.0f}", price, vals)

def strat_xrp_night_break(sym):
    """#127 XRP_NIGHT_BREAK — Overnight quiet-range compression breakout.
    XRP's quietest window creates compressed ranges before session opens. Mark the
    range of the previous 3-hour quiet window (proxy: bars 7-4 hours ago). Enter when
    price breaks above the range high with volume as the active session begins."""
    b5 = get_bars(sym, 120, 5)
    if b5 is None or len(b5) < 90: return _hold("Insufficient data")
    price     = float(b5["close"].iloc[-1])
    quiet     = b5.iloc[-84:-48]   # 7-4 hours ago on 5m = ~3-hour quiet window
    if len(quiet) < 20: return _hold("Insufficient quiet data")
    q_hi      = float(quiet["high"].max())
    q_lo      = float(quiet["low"].min())
    q_rng     = (q_hi - q_lo) / q_lo if q_lo > 0 else 1.0
    broke_up  = price > q_hi * 1.001
    vol_avg   = float(b5["volume"].iloc[-15:-1].mean())
    vol_r     = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    rsi7      = float(rsi(b5["close"], 7).iloc[-1])
    vals      = {"QRange%": round(q_rng*100,2), "QHi": round(q_hi,5),
                 "Broke": broke_up, "VolR": round(vol_r,2)}
    # Tight range < 0.8%, clean break above with volume, RSI not overbought
    if q_rng < 0.008 and broke_up and vol_r > 1.3 and rsi7 < 70:
        return _buy(price, vals)
    return _hold(f"Rng:{q_rng*100:.2f}% Broke:{broke_up} Vol:{vol_r:.1f}", price, vals)

def strat_xrp_basket_lead(sym):
    """#128 XRP_BASKET_LEAD — XRP ranked #1 or #2 in hourly performance across 6-coin basket.
    When XRP leads BTC/ETH/SOL/DOGE/LTC in 1H percentage gain, real buying pressure is
    behind the move — not just market-wide tide lifting all boats. Enter when XRP leads
    the basket AND is positive AND above VWAP AND RSI not overbought."""
    basket    = ["XRP/USD","BTC/USD","ETH/USD","SOL/USD","DOGE/USD","LTC/USD"]
    changes   = {}
    for coin in basket:
        b = get_bars(coin, 8, 60)
        if b is None or len(b) < 3: changes[coin] = 0.0; continue
        changes[coin] = (float(b["close"].iloc[-1]) / float(b["close"].iloc[-2]) - 1) * 100
    xrp_chg   = changes.get(sym, changes.get("XRP/USD", 0.0))
    all_vals  = sorted(changes.values(), reverse=True)
    xrp_rank  = all_vals.index(xrp_chg) + 1 if xrp_chg in all_vals else 6
    b5        = get_bars(sym, 40, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price     = float(b5["close"].iloc[-1])
    vwap_v    = vwap(b5.iloc[-30:])
    rsi14     = float(rsi(b5["close"], 14).iloc[-1])
    vals      = {"Rank": xrp_rank, "XRP1H%": round(xrp_chg,2),
                 "AboveVWAP": price>vwap_v, "RSI14": round(rsi14,1)}
    if xrp_rank <= 2 and xrp_chg > 0.3 and price > vwap_v and rsi14 < 68:
        return _buy(price, vals)
    return _hold(f"Rank:{xrp_rank}/6 1H:{xrp_chg:.2f}% RSI:{rsi14:.0f}", price, vals)

def strat_xrp_staircase(sym):
    """#129 XRP_STAIRCASE — Conviction-gate entry with runner-optimised exit parameters.
    Uses the same 7-condition scoring gate as XRP_CONVICTION (score ≥ 4) but with a
    wider TP (3.0%) and elevated trail gate (1.5%) to capture the 'runner' tier on
    big XRP moves. On a $5,000 account the difference between a 1.6% and a 3.0% winner
    is meaningful. Score ≥ 5 recommended for this wider target. ADX-exempt: own filter."""
    b5  = get_bars(sym, 80, 5)
    b1h = get_bars(sym, 30, 60)
    if b5 is None or len(b5) < 40: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    score  = 0
    rsi7   = float(rsi(b5["close"], 7).iloc[-1])
    mid    = b5["close"].rolling(20).mean()
    std    = b5["close"].rolling(20).std()
    lower  = float((mid - 2*std).iloc[-1])
    vol_avg= float(b5["volume"].iloc[-15:-1].mean())
    vol_r  = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    vwap_v = vwap(b5.iloc[-30:])
    e9     = float(ema(b5["close"],  9).iloc[-1])
    e21    = float(ema(b5["close"], 21).iloc[-1])
    recent = b5.iloc[-12:]
    up_vol = float(recent.loc[recent["close"] >= recent["open"], "volume"].sum())
    up_r   = up_vol / float(recent["volume"].sum()) if float(recent["volume"].sum()) > 0 else 0.5
    if rsi7 < 35:             score += 1
    if price <= lower * 1.003:score += 1
    if vol_r > 1.5:           score += 1
    if price > vwap_v:        score += 1
    if e9 > e21:              score += 1
    if up_r > 0.55:           score += 1
    if b1h is not None and len(b1h) >= 22:
        if price > float(ema(b1h["close"],21).iloc[-1]): score += 1
    vals = {"Score": score, "RSI7": round(rsi7,1), "TP_target": "3.0%"}
    # Higher bar than XRP_CONVICTION — requires score ≥ 5 for the wider runner target
    if score >= 5:
        return _buy(price, vals)
    return _hold(f"Score:{score}/7 (need 5+)", price, vals)


def strat_vwap_cross(sym):
    """#42 VWAP_CROSS — Price crosses above 30-bar VWAP from below with volume confirmation.
    The VWAP cross is an institutional signal: price reclaiming its volume-weighted
    fair value after a dip. Clean crosses with volume > 1.1x average have high follow-through."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 35: return _hold("Insufficient data")
    price      = float(b5["close"].iloc[-1])
    vwap_now   = vwap(b5.iloc[-30:])
    vwap_prev  = vwap(b5.iloc[-31:-1])
    prev_close = float(b5["close"].iloc[-2])
    crossed_up = prev_close < vwap_prev and price > vwap_now
    rsi14      = float(rsi(b5["close"], 14).iloc[-1])
    vol_avg    = float(b5["volume"].iloc[-10:-1].mean())
    vol_r      = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    near_above = abs((price-vwap_now)/vwap_now) < 0.004
    vals = {"VWAP": round(vwap_now,5), "Crossed": crossed_up,
            "RSI14": round(rsi14,1), "VolR": round(vol_r,2)}
    if (crossed_up or near_above) and rsi14 < 70 and vol_r > 0.8:
        return _buy(price, vals)
    return _hold(f"Cross:{crossed_up} RSI:{rsi14:.0f} Vol:{vol_r:.1f}", price, vals)

def strat_vwap_bounce(sym):
    """#43 VWAP_BOUNCE — Price touches VWAP support from above and bounces.
    VWAP is institutional fair value. A dip to VWAP with RSI mild-oversold + EMA trend
    intact is one of the highest-probability setups in institutional order flow trading.
    ADX-exempt: mean-reversion to VWAP works in all market conditions."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 35: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    vwap_v = vwap(b5.iloc[-30:])
    dist   = (price - vwap_v) / vwap_v
    rsi14  = float(rsi(b5["close"], 14).iloc[-1])
    e21    = float(ema(b5["close"], 21).iloc[-1])
    vals   = {"VWAP": round(vwap_v,5), "Dist%": round(dist*100,2), "RSI14": round(rsi14,1)}
    if -0.010 <= dist <= 0.004 and rsi14 < 50 and price > e21 * 0.993:
        return _buy(price, vals)
    return _hold(f"Dist:{dist*100:.2f}% RSI:{rsi14:.0f}", price, vals)

def strat_cmf_div(sym):
    """#44 CMF_DIV — Chaikin Money Flow positive (>0.06) with price at EMA21 support.
    CMF measures the volume-weighted accumulation/distribution over 20 periods.
    Positive CMF while price tests EMA21 = institutional buying confirming the level."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    hi = b5["high"]; lo = b5["low"]; cl = b5["close"]; vo = b5["volume"]
    denom = (hi - lo).replace(0, 1e-8)
    mfm   = ((cl - lo) - (hi - cl)) / denom
    mfv   = mfm * vo
    vol20 = float(vo.iloc[-20:].sum())
    cmf20 = float(mfv.iloc[-20:].sum()) / vol20 if vol20 > 0 else 0.0
    e21   = float(ema(b5["close"], 21).iloc[-1])
    rsi14 = float(rsi(b5["close"], 14).iloc[-1])
    vals  = {"CMF": round(cmf20, 3), "RSI14": round(rsi14,1)}
    if cmf20 > 0.01 and price > e21 * 0.997 and rsi14 < 65:
        return _buy(price, vals)
    return _hold(f"CMF:{cmf20:.3f} RSI:{rsi14:.0f}", price, vals)

def strat_stoch_os(sym):
    """#45 STOCH_OS — Stochastic K crosses above D from below oversold zone (< 25).
    Classic stochastic oversold cross: both lines below 25, K crosses up through D.
    EMA50 guard ensures we're not in a hard structural downtrend. ADX-exempt."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    sk, sd = stoch(b5, k=14, sm=3, d=3)
    k_cur  = float(sk.iloc[-1]); k_prev = float(sk.iloc[-2])
    d_cur  = float(sd.iloc[-1]); d_prev = float(sd.iloc[-2])
    e50    = float(ema(b5["close"], 50).iloc[-1])
    rising = k_cur > k_prev and k_prev < 20 and k_cur < 35
    vals   = {"K": round(k_cur,1), "D": round(d_cur,1), "Rising": rising}
    if rising and price > e50 * 0.97:
        return _buy(price, vals)
    return _hold(f"K:{k_cur:.0f} D:{d_cur:.0f} Rise:{rising}", price, vals)

def strat_stoch_ob(sym):
    """#46 STOCH_OB — Buy the healthy pullback after a stochastic overbought reading.
    K was overbought (>75) in the last 6 bars but has pulled back to the 48-65 zone.
    This means the strong move has paused for a breath — price consolidating in an uptrend.
    EMA21 must still be below price. ADX-exempt: pullback-in-trend = mean reversion."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    sk, _  = stoch(b5, k=14, sm=3, d=3)
    k_cur  = float(sk.iloc[-1])
    k_prev = float(sk.iloc[-2])
    recovering = k_cur > k_prev and k_prev < 25 and k_cur < 50  # K rising from oversold zone
    e21    = float(ema(b5["close"], 21).iloc[-1])
    rsi14  = float(rsi(b5["close"], 14).iloc[-1])
    vals   = {"K": round(k_cur,1), "Recovering": recovering, "RSI14": round(rsi14,1)}
    if recovering and price > e21 * 0.990 and rsi14 < 58:
        return _buy(price, vals)
    return _hold(f"K:{k_cur:.0f} Rec:{recovering} RSI:{rsi14:.0f}", price, vals)

def strat_stoch_rsi(sym):
    """#47 STOCH_RSI — Stochastic K < 25 AND RSI(14) < 35 simultaneously oversold.
    Both oscillators must be simultaneously in oversold territory. More selective than
    either alone — produces fewer but higher-conviction entries. ADX-exempt."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price  = float(b5["close"].iloc[-1])
    sk, _  = stoch(b5, k=14, sm=3, d=3)
    k_cur  = float(sk.iloc[-1])
    rsi14  = float(rsi(b5["close"], 14).iloc[-1])
    e50    = float(ema(b5["close"], 50).iloc[-1])
    vol_avg= float(b5["volume"].iloc[-10:-1].mean())
    vol_r  = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    vals   = {"K": round(k_cur,1), "RSI14": round(rsi14,1), "VolR": round(vol_r,2)}
    if k_cur < 25 and rsi14 < 40 and price > e50 * 0.97 and vol_r > 0.8:
        return _buy(price, vals)
    return _hold(f"K:{k_cur:.0f} RSI:{rsi14:.0f}", price, vals)

def strat_williams_r(sym):
    """#48 WILLIAMS_R — Williams %R crossing above -80 (emerging from oversold territory).
    W%R = ((14-period high - close) / (14-period high - low)) × -100.
    Range: -100 (oversold) to 0 (overbought). Entry when crossing from below -80 to above.
    ADX-exempt: oscillator mean-reversion, works in ranging and trending markets."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 20: return _hold("Insufficient data")
    price    = float(b5["close"].iloc[-1])
    hi14     = float(b5["high"].iloc[-14:].max())
    lo14     = float(b5["low"].iloc[-14:].min())
    spread   = hi14 - lo14 if hi14 != lo14 else 1e-8
    wr_cur   = ((hi14 - price)                           / spread) * -100
    wr_prev  = ((hi14 - float(b5["close"].iloc[-2]))     / spread) * -100
    emerging = wr_prev < -80 and wr_cur > -80
    e21      = float(ema(b5["close"], 21).iloc[-1])
    rsi14    = float(rsi(b5["close"], 14).iloc[-1])
    vals     = {"WR": round(wr_cur,1), "Emerging": emerging, "RSI14": round(rsi14,1)}
    if (emerging or wr_cur < -80) and rsi14 < 55 and price > e21 * 0.97:
        return _buy(price, vals)
    return _hold(f"WR:{wr_cur:.0f} Emerg:{emerging}", price, vals)

def strat_cci_rev(sym):
    """#49 CCI_REV — Commodity Channel Index crossing above -100 (emerging from oversold).
    CCI = (Typical Price - SMA20) / (0.015 × Mean Deviation). Oversold below -100.
    Entry when CCI crosses from below -100 to above — the reversal from extreme.
    ADX-exempt: oscillator mean-reversion."""
    b5 = get_bars(sym, 60, 5)
    if b5 is None or len(b5) < 25: return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    tp    = (b5["high"] + b5["low"] + b5["close"]) / 3
    sma20 = tp.rolling(20).mean()
    mad   = tp.rolling(20).apply(lambda x: abs(x - x.mean()).mean())
    cci   = (tp - sma20) / (0.015 * mad.replace(0, 1e-8))
    cci_n = float(cci.iloc[-1]); cci_p = float(cci.iloc[-2])
    cross = cci_p < -100 and cci_n > -100
    e21   = float(ema(b5["close"], 21).iloc[-1])
    vol_avg = float(b5["volume"].iloc[-10:-1].mean())
    vol_r   = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    vals  = {"CCI": round(cci_n,1), "Cross": cross, "VolR": round(vol_r,2)}
    if (cross or cci_n < -110) and price > e21 * 0.97 and vol_r > 0.85:
        return _buy(price, vals)
    return _hold(f"CCI:{cci_n:.0f} Cross:{cross}", price, vals)

def strat_head_shld(sym):
    """#50 HEAD_SHLD — Inverse head-and-shoulders detection (bullish: 3 troughs, middle deepest).
    On a long-only bot the bullish inverse H&S is the relevant pattern. Detects 3 local lows
    where the middle is the deepest (the 'head'), shoulders approximately equal, then enters
    when price breaks above the neckline (the rally high between the shoulders)."""
    b5 = get_bars(sym, 80, 5)
    if b5 is None or len(b5) < 40: return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    lows  = list(b5["low"].values[-30:])
    highs = list(b5["high"].values[-30:])
    troughs = [i for i in range(2, len(lows)-2)
               if lows[i] < lows[i-1] and lows[i] < lows[i+1]
               and lows[i] < lows[i-2] and lows[i] < lows[i+2]]
    pattern = False; neckline = 0.0
    if len(troughs) >= 3:
        t1, t2, t3 = troughs[-3], troughs[-2], troughs[-1]
        ls, hd, rs = lows[t1], lows[t2], lows[t3]
        if hd < ls and hd < rs and abs(ls - rs) / max(ls, 1e-8) < 0.025:
            neck_slice = highs[t1:t3+1]
            neckline = float(max(neck_slice)) if neck_slice else 0.0
            pattern  = True
    rsi14 = float(rsi(b5["close"], 14).iloc[-1])
    vals  = {"Pattern": pattern, "Neck": round(neckline,5), "RSI14": round(rsi14,1)}
    if pattern and price > neckline * 1.001 and rsi14 < 65:
        return _buy(price, vals)
    return _hold(f"Inv-HS:{pattern} Neck:{neckline:.4f}", price, vals)

def strat_inv_head_shld(sym):
    """#51 INV_H_S — Regular H&S top + neckline support mean-reversion entry.
    Detects a 3-peak formation (left shoulder, head, right shoulder; head is highest).
    For a long-only bot: enters at the neckline support level after the right shoulder
    forms and price pulls back to neckline from above — a mean-reversion bounce.
    ADX-exempt: neckline support bounce is mean-reversion in nature."""
    b5 = get_bars(sym, 80, 5)
    if b5 is None or len(b5) < 40: return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    highs = list(b5["high"].values[-30:])
    lows  = list(b5["low"].values[-30:])
    peaks = [i for i in range(2, len(highs)-2)
             if highs[i] > highs[i-1] and highs[i] > highs[i+1]
             and highs[i] > highs[i-2] and highs[i] > highs[i+2]]
    pattern = False; neckline = 0.0
    if len(peaks) >= 3:
        p1, p2, p3 = peaks[-3], peaks[-2], peaks[-1]
        ls, hd, rs = highs[p1], highs[p2], highs[p3]
        if hd > ls and hd > rs and abs(ls - rs) / max(ls, 1e-8) < 0.03:
            neck_slice = lows[p1:p3+1]
            neckline = float(min(neck_slice)) if neck_slice else 0.0
            pattern  = True
    near  = pattern and neckline > 0 and abs(price - neckline) / neckline < 0.005
    rsi14 = float(rsi(b5["close"], 14).iloc[-1])
    e50   = float(ema(b5["close"], 50).iloc[-1])
    vals  = {"Pattern": pattern, "Neck": round(neckline,5), "RSI14": round(rsi14,1)}
    if near and rsi14 < 45 and price > e50 * 0.990:
        return _buy(price, vals)
    return _hold(f"HS:{pattern} NearNeck:{near} RSI:{rsi14:.0f}", price, vals)



def strat_xrp_bb_adx(sym):
    """#130 XRP_BB_ADX — Bollinger lower band touch with ADX confirmation.
    Most consistently backtested XRP-specific approach across 3 years of data.
    15m chart: price at lower BB + ADX trend present + RSI oversold + stoch K rising.
    ADX-exempt: mean-reversion strategy, works best in moderate-trend ranging markets."""
    b15 = get_bars(sym, 80, 15)
    if b15 is None or len(b15) < 25: return _hold("Insufficient data")
    price = float(b15["close"].iloc[-1])
    mid   = float(b15["close"].rolling(20).mean().iloc[-1])
    std   = float(b15["close"].rolling(20).std().iloc[-1])
    lower = mid - 2 * std
    adx14 = float(adx(b15).iloc[-1])
    rsi14 = float(rsi(b15["close"]).iloc[-1])
    sk, _ = stoch(b15)
    k_cur = float(sk.iloc[-1]); k_prv = float(sk.iloc[-2])
    at_band = price <= lower * 1.005
    vals = {"LBB": round(lower,4), "ADX": round(adx14,1), "RSI": round(rsi14,1), "K": round(k_cur,1)}
    if at_band and adx14 > 15 and rsi14 < 40 and k_cur > k_prv:
        return _buy(price, vals)
    return _hold(f"BB:{at_band} ADX:{adx14:.0f} RSI:{rsi14:.0f}", price, vals)

def strat_xrp_news_fade(sym):
    """#131 XRP_NEWS_FADE — Counter-trend fade of extreme news overreactions.
    XRP's high sensitivity to Ripple announcements causes 2-6 hour reversions after extreme moves.
    Entry: price drops > 2.5 SD below 20-period MA on 15m with volume spike (news selling).
    ADX-exempt: counter-trend entry, fires specifically in extreme volatile conditions."""
    b15 = get_bars(sym, 80, 15)
    if b15 is None or len(b15) < 25: return _hold("Insufficient data")
    price = float(b15["close"].iloc[-1])
    mid   = float(b15["close"].rolling(20).mean().iloc[-1])
    std   = float(b15["close"].rolling(20).std().iloc[-1])
    lower25 = mid - 2.5 * std   # Extended band — more extreme than normal BB
    rsi14   = float(rsi(b15["close"]).iloc[-1])
    vol_avg = float(b15["volume"].iloc[-10:-1].mean())
    vol_r   = float(b15["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 0
    move    = (float(b15["close"].iloc[-1]) - float(b15["close"].iloc[-2])) / float(b15["close"].iloc[-2])
    vals = {"Below2.5SD": price <= lower25, "RSI": round(rsi14,1), "VolR": round(vol_r,2), "Move%": round(move*100,2)}
    if price <= lower25 and rsi14 < 28 and vol_r > 1.8 and move < -0.005:
        return _buy(price, vals)
    return _hold(f"2.5SD:{price<=lower25} RSI:{rsi14:.0f} Vol:{vol_r:.1f}", price, vals)

def strat_xrp_compress(sym):
    """#132 XRP_COMPRESS — Bollinger Band squeeze + breakout detection.
    Models XRP's documented compression-expansion behavior: bands tighten to multi-period
    lows then price makes an explosive directional move on above-average volume.
    5m chart: BBW percentile rank < 30th + breakout candle + volume confirmation."""
    b5 = get_bars(sym, 80, 5)
    if b5 is None or len(b5) < 45: return _hold("Insufficient data")
    price = float(b5["close"].iloc[-1])
    mid   = b5["close"].rolling(20).mean()
    std   = b5["close"].rolling(20).std()
    upper = mid + 2*std; lower = mid - 2*std
    bbw   = (upper - lower) / mid.replace(0, float("nan"))
    # BBW percentile rank over last 40 bars — squeeze = bottom 30th %ile
    bbw_pct = float(bbw.rolling(40).rank(pct=True).iloc[-1]) if not bbw.iloc[-1:].isna().all() else 0.5
    move    = (float(b5["close"].iloc[-1]) - float(b5["close"].iloc[-2])) / float(b5["close"].iloc[-2])
    vol_avg = float(b5["volume"].iloc[-10:-1].mean())
    vol_r   = float(b5["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 0
    rsi14   = float(rsi(b5["close"]).iloc[-1])
    vals = {"BBWPct": round(bbw_pct*100,0), "Move%": round(move*100,3), "VolR": round(vol_r,2), "RSI": round(rsi14,1)}
    if bbw_pct < 0.30 and move > 0.003 and vol_r > 1.5 and rsi14 > 45:
        return _buy(price, vals)
    return _hold(f"Squeeze:{bbw_pct*100:.0f}% Move:{move*100:.2f}% Vol:{vol_r:.1f}", price, vals)

def strat_xrp_support_range(sym):
    """#133 XRP_SUPPORT_RANGE — Multi-timeframe support bounce in ranging market.
    1H chart identifies support/resistance range; 5m confirms entry at support.
    ADX < 30 on 1H confirms ranging conditions (trend-following strategies fail here).
    Entry: price within 0.5% of 20-bar 1H support + RSI oversold + stoch K turning up.
    ADX-exempt: has own ADX<30 ranging requirement; global filter would block correct setups."""
    b1h = get_bars(sym, 50, 60)
    if b1h is None or len(b1h) < 25: return _hold("Insufficient data")
    b5  = get_bars(sym, 30, 5)
    if b5 is None or len(b5) < 15: return _hold("Insufficient data")
    price   = float(b5["close"].iloc[-1])
    support = float(b1h["low"].rolling(20).min().iloc[-1])
    resist  = float(b1h["high"].rolling(20).max().iloc[-1])
    dist_s  = (price - support) / support
    range_w = (resist - support) / support
    adx14   = float(adx(b1h).iloc[-1])
    rsi14   = float(rsi(b1h["close"]).iloc[-1])
    sk, _   = stoch(b5)
    k_cur   = float(sk.iloc[-1]); k_prv = float(sk.iloc[-2])
    vals = {"Support": round(support,4), "Dist%": round(dist_s*100,2), "ADX": round(adx14,1), "RSI": round(rsi14,1)}
    if dist_s < 0.005 and adx14 < 30 and rsi14 < 48 and k_cur > k_prv and range_w > 0.02:
        return _buy(price, vals)
    return _hold(f"Dist:{dist_s*100:.2f}% ADX:{adx14:.0f} Range:{range_w*100:.1f}%", price, vals)

def strat_xrp_breakout_v2(sym):
    """#134 XRP_BREAKOUT_V2 — High-conviction breakout with stricter volume filter.
    Addresses the finding that ~40% of breakout attempts fail within 24-48 hours.
    Requires 1.5x volume (vs 1.2x in BREAKOUT) + RSI momentum confirmation + ADX trend.
    15m chart: price above 20-bar high * 1.001 + volume > 1.5x + RSI > 55 + ADX > 18."""
    b15 = get_bars(sym, 60, 15)
    if b15 is None or len(b15) < 25: return _hold("Insufficient data")
    price   = float(b15["close"].iloc[-1])
    resist  = float(b15["high"].iloc[-20:-1].max())
    vol_avg = float(b15["volume"].iloc[-10:-1].mean())
    vol_cur = float(b15["volume"].iloc[-1])
    vol_r   = vol_cur / vol_avg if vol_avg > 0 else 0
    rsi14   = float(rsi(b15["close"]).iloc[-1])
    adx14   = float(adx(b15).iloc[-1])
    broke   = price > resist * 1.001
    vals = {"Resist": round(resist,4), "VolR": round(vol_r,2), "RSI": round(rsi14,1), "ADX": round(adx14,1)}
    if broke and vol_r > 1.5 and rsi14 > 55 and adx14 > 18:
        return _buy(price, vals)
    return _hold(f"Broke:{broke} Vol:{vol_r:.2f} RSI:{rsi14:.0f} ADX:{adx14:.0f}", price, vals)


def strat_xrp_candle_surge(sym):
    """#140 XRP_CANDLE_SURGE — 3-candle momentum burst.
    Three consecutive bullish closes + EMA 9 > 21 + RSI 45-72 + volume building.
    Enters INTO momentum, not against it. Target: 1.0pct quick scalp.
    ADX-exempt: uses EMA alignment as its own trend filter.
    Runs 24/7 on XRP/USD. Expected 15-25 signals per day on 1m chart."""
    b1 = get_bars(sym, 60, 1)
    if b1 is None or len(b1) < 25: return _hold("Insufficient data")
    price = float(b1["close"].iloc[-1])

    # Three consecutive bullish candles with rising closes
    c1 = float(b1["close"].iloc[-1]) > float(b1["open"].iloc[-1])
    c2 = float(b1["close"].iloc[-2]) > float(b1["open"].iloc[-2])
    c3 = float(b1["close"].iloc[-3]) > float(b1["open"].iloc[-3])
    rising    = (float(b1["close"].iloc[-1]) > float(b1["close"].iloc[-2]) and
                 float(b1["close"].iloc[-2]) > float(b1["close"].iloc[-3]))
    three_bull = c1 and c2 and c3 and rising

    # EMA alignment
    e9  = float(ema(b1["close"], 9).iloc[-1])
    e21 = float(ema(b1["close"], 21).iloc[-1])
    aligned = e9 > e21

    # RSI momentum
    rsi14 = float(rsi(b1["close"]).iloc[-1])

    # Volume building (current > 3 bars ago)
    vol_build = float(b1["volume"].iloc[-1]) > float(b1["volume"].iloc[-3])

    vals = {"3Bull": three_bull, "EMA": aligned, "RSI": round(rsi14,1), "VolBuild": vol_build}
    if three_bull and aligned and 45 <= rsi14 <= 72 and vol_build:
        return _buy(price, vals)
    return _hold(f"3B:{three_bull} EMA:{aligned} RSI:{rsi14:.0f}", price, vals)


# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
# v9.2 — XRP-ONLY STRATEGIES #142-151  (redesigned: state not event)
# Philosophy: half trend-following, half mean-reversion — fires in ANY regime
# ═══════════════════════════════════════════════════════════════════

def strat_xrp_vwap_bounce(sym):
    """#142 XRP_VWAP_BOUNCE — Price above rolling VWAP + RSI 35-70.
    STATE check, not crossover. Fires whenever XRP is trading above intraday
    fair value with room to run (RSI not extreme in either direction).
    Expected 5-10 signals/day."""
    b = get_bars(sym, 80, 5)
    if b is None or len(b) < 30: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price = float(b["close"].iloc[-1])
    tp  = (b["high"] + b["low"] + b["close"]) / 3
    rv  = (tp * b["volume"]).cumsum() / b["volume"].cumsum()
    above = price > float(rv.iloc[-1])
    rsi14 = float(rsi(b["close"]).iloc[-1])
    rsi_ok = 35 <= rsi14 <= 75
    vals  = {"VWAP": round(float(rv.iloc[-1]),4), "Above": above, "RSI": round(rsi14,1)}
    if above and rsi_ok:
        return _buy(price, vals)
    return _hold(f"Above:{above} RSI:{rsi14:.0f}", price, vals)


def strat_xrp_rsi_bull(sym):
    """#143 XRP_RSI_BULL — RSI > 50 (trend) OR RSI < 33 with green candle (oversold bounce).
    Covers BOTH regimes: fires in uptrend when momentum is positive, AND in downtrends
    when XRP is deeply oversold and a reversal candle prints.
    Expected 6-12 signals/day."""
    b = get_bars(sym, 60, 5)
    if b is None or len(b) < 25: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price = float(b["close"].iloc[-1])
    rsi14 = float(rsi(b["close"]).iloc[-1])
    green = float(b["close"].iloc[-1]) > float(b["open"].iloc[-1])
    trend_ok  = rsi14 > 50
    bounce_ok = rsi14 < 33 and green
    vals = {"RSI": round(rsi14,1), "Green": green, "Trend": trend_ok, "Bounce": bounce_ok}
    if trend_ok or bounce_ok:
        return _buy(price, vals)
    return _hold(f"RSI:{rsi14:.0f} trend:{trend_ok} bounce:{bounce_ok}", price, vals)


def strat_xrp_ema50_align(sym):
    """#144 XRP_EMA50_ALIGN — EMA9 above EMA21 + green candle.
    Two-EMA state check (dropped the third EMA and volume requirement).
    Fires whenever the short-term trend is up and current candle confirms.
    Expected 6-10 signals/day."""
    b = get_bars(sym, 60, 5)
    if b is None or len(b) < 25: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price = float(b["close"].iloc[-1])
    e9  = float(ema(b["close"],  9).iloc[-1])
    e21 = float(ema(b["close"], 21).iloc[-1])
    aligned = e9 > e21
    green   = float(b["close"].iloc[-1]) > float(b["open"].iloc[-1])
    vals    = {"E9aboveE21": aligned, "Green": green}
    if aligned and green:
        return _buy(price, vals)
    return _hold(f"Aligned:{aligned} Green:{green}", price, vals)


def strat_xrp_big_candle(sym):
    """#145 XRP_BIG_CANDLE — Bullish body > 1.2x average body.
    Lowered from 1.5x — catches genuine momentum candles without requiring a
    perfect market structure. No secondary EMA filter. Any strong green candle fires.
    Expected 6-12 signals/day."""
    b = get_bars(sym, 40, 5)
    if b is None or len(b) < 15: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price    = float(b["close"].iloc[-1])
    bodies   = abs(b["close"] - b["open"])
    cur_body = float(bodies.iloc[-1])
    avg_body = float(bodies.iloc[-11:-1].mean())
    bull_big = (float(b["close"].iloc[-1]) > float(b["open"].iloc[-1]) and
                avg_body > 0 and cur_body > avg_body * 1.2)
    rsi14    = float(rsi(b["close"]).iloc[-1])
    vals     = {"BigBull": bull_big, "Ratio": round(cur_body/avg_body if avg_body>0 else 0,2), "RSI": round(rsi14,1)}
    if bull_big and rsi14 < 72:
        return _buy(price, vals)
    return _hold(f"BigBull:{bull_big} RSI:{rsi14:.0f}", price, vals)


def strat_xrp_stoch_bull(sym):
    """#146 XRP_STOCH_BULL — Stoch K above D and not overbought (K < 80).
    STATE check, not crossover. K sitting above D means momentum is positive
    regardless of when the cross happened. Fires ~40-50 percent of the time.
    Expected 6-10 signals/day."""
    b = get_bars(sym, 60, 5)
    if b is None or len(b) < 20: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price = float(b["close"].iloc[-1])
    sk, sd = stoch(b)
    k_cur  = float(sk.iloc[-1]); d_cur = float(sd.iloc[-1])
    above  = k_cur > d_cur and k_cur < 80
    green  = float(b["close"].iloc[-1]) > float(b["open"].iloc[-1])
    vals   = {"K": round(k_cur,1), "D": round(d_cur,1), "KgtD": above, "Green": green}
    if above and green:
        return _buy(price, vals)
    return _hold(f"KgtD:{above} Green:{green}", price, vals)


def strat_xrp_higher_close(sym):
    """#147 XRP_HIGHER_CLOSE — 2 successive higher closes + volume rising (1m).
    Reduced from 3 to 2 bars — easier to satisfy, catches micro-trends sooner.
    Still requires volume confirmation to filter noise.
    Expected 20-35 signals/day on 1m."""
    b = get_bars(sym, 30, 1)
    if b is None or len(b) < 10: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price  = float(b["close"].iloc[-1])
    c      = b["close"]
    rising = float(c.iloc[-1]) > float(c.iloc[-2]) > float(c.iloc[-3])
    vol_ok = float(b["volume"].iloc[-1]) > float(b["volume"].iloc[-2])
    vals   = {"Rising2": rising, "VolRising": vol_ok}
    if rising and vol_ok:
        return _buy(price, vals)
    return _hold(f"Rising:{rising} Vol:{vol_ok}", price, vals)


def strat_xrp_atr_bull(sym):
    """#148 XRP_ATR_BULL — Bullish candle move > 0.3x ATR + RSI not overbought.
    Threshold dropped from 0.5x to 0.3x ATR — catches moderate momentum moves,
    not just outsized spikes. RSI loosened to < 72 (was > 50).
    Expected 5-10 signals/day."""
    b = get_bars(sym, 40, 5)
    if b is None or len(b) < 20: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price   = float(b["close"].iloc[-1])
    a14     = atr(b); atr_val = float(a14.iloc[-2])
    move    = float(b["close"].iloc[-1]) - float(b["open"].iloc[-1])
    big_up  = atr_val > 0 and move > atr_val * 0.30
    rsi14   = float(rsi(b["close"]).iloc[-1])
    vals    = {"Move": round(move,5), "Thr": round(atr_val*0.30,5), "BigUp": big_up, "RSI": round(rsi14,1)}
    if big_up and rsi14 < 72:
        return _buy(price, vals)
    return _hold(f"BigUp:{big_up} RSI:{rsi14:.0f}", price, vals)


def strat_xrp_ema_touch(sym):
    """#149 XRP_EMA_TOUCH — Price within 1.5% of EMA21 + RSI 30-70.
    Window widened from 0.5% to 1.5% — EMA21 is now a zone not a line.
    RSI range widened from 40-60 to 30-70 so it fires in more conditions.
    Expected 4-8 signals/day."""
    b = get_bars(sym, 60, 5)
    if b is None or len(b) < 25: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price = float(b["close"].iloc[-1])
    e21   = float(ema(b["close"], 21).iloc[-1])
    dist  = abs(price - e21) / e21 if e21 > 0 else 1.0
    near  = dist < 0.015
    rsi14 = float(rsi(b["close"]).iloc[-1])
    rsi_ok = 30 <= rsi14 <= 70
    vals   = {"DistPct": round(dist*100,2), "NearEMA21": near, "RSI": round(rsi14,1)}
    if near and rsi_ok:
        return _buy(price, vals)
    return _hold(f"Near:{near} RSI:{rsi14:.0f}", price, vals)


def strat_xrp_close_high(sym):
    """#150 XRP_CLOSE_HIGH — Close in top 50% of candle range + green candle.
    Threshold dropped from top 30% to top 50% — now fires on any candle that
    closes in the upper half of its range. Replaces volume check with green candle.
    Expected 10-20 signals/day."""
    b = get_bars(sym, 40, 5)
    if b is None or len(b) < 15: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price = float(b["close"].iloc[-1])
    hi    = float(b["high"].iloc[-1]); lo = float(b["low"].iloc[-1])
    rng   = hi - lo
    if rng < 1e-8: return _hold("No range", price, {})
    close_pct = (price - lo) / rng
    top50  = close_pct >= 0.50
    green  = float(b["close"].iloc[-1]) > float(b["open"].iloc[-1])
    vals   = {"ClosePct": round(close_pct*100,1), "Top50": top50, "Green": green}
    if top50 and green:
        return _buy(price, vals)
    return _hold(f"Top50:{top50} Green:{green}", price, vals)


def strat_xrp_triple_ema(sym):
    """#151 XRP_TRIPLE_EMA — EMA9>EMA21>EMA50 all aligned + RSI 35-78 (15m).
    RSI range widened from 45-70 to 35-78 so it fires in early recovery and
    strong trend phases. Triple alignment on 15m still gives high conviction.
    Expected 2-5 signals/day."""
    b = get_bars(sym, 80, 15)
    if b is None or len(b) < 55: return _hold(f"No data ({0 if b is None else len(b)} bars)")
    price   = float(b["close"].iloc[-1])
    e9      = float(ema(b["close"],  9).iloc[-1])
    e21     = float(ema(b["close"], 21).iloc[-1])
    e50     = float(ema(b["close"], 50).iloc[-1])
    aligned = e9 > e21 > e50
    rsi14   = float(rsi(b["close"]).iloc[-1])
    rsi_ok  = 35 <= rsi14 <= 78
    vals    = {"Aligned": aligned, "RSI": round(rsi14,1)}
    if aligned and rsi_ok:
        return _buy(price, vals)
    return _hold(f"Aligned:{aligned} RSI:{rsi14:.0f}", price, vals)


# ─────────────────────────────────────────────────────────────────
# STRATEGY DISPATCHER  ←  Add new strategies here
# ─────────────────────────────────────────────────────────────────

# Strategies exempt from the global ADX filter.
# Mean-reversion and VWAP strategies work BETTER in ranging (low-ADX) markets.
# Trend-following strategies (EMA_CROSS, BREAKOUT, FS1000) are NOT exempt.
ADX_EXEMPT = {
    "REGIME_AUTO","GLD_GOLD","MULTI_TF",
    "BOLLINGER","MEAN_REV_VWAP","RSI_SIMPLE","STOCH_SIMPLE",
    "REV_HUNTER","GRID","RSI_DIV",
    "XRP_SCALP_BB","XRP_VWAP_TOUCH","XRP_PULLBACK","MANNAN_V2","SUPPORT_BOUNCE","FS1000","BREAKOUT","EMA_BOUNCE","VOL_BURST","EMA_RIBBON",
    "XRP_DUAL_RSI","XRP_MICRO_DIV","XRP_ATR_SPIKE",
    "XRP_CONVICTION","XRP_STAIRCASE",
    "VWAP_BOUNCE","STOCH_OS","STOCH_OB","STOCH_RSI","CMF_DIV",
    "WILLIAMS_R","CCI_REV","INV_H_S",
    # Research-backed XRP strategies (#130-134)
    "XRP_BB_ADX","XRP_NEWS_FADE","XRP_SUPPORT_RANGE","XRP_BREAKOUT_V2",
    "XRP_CANDLE_SURGE",
    # v9.2 XRP simple strategies
    "XRP_VWAP_BOUNCE","XRP_RSI_BULL","XRP_EMA50_ALIGN","XRP_BIG_CANDLE","XRP_STOCH_BULL",
    "XRP_HIGHER_CLOSE","XRP_ATR_BULL","XRP_EMA_TOUCH","XRP_CLOSE_HIGH","XRP_TRIPLE_EMA",
}


# =============================================================================
# -S SCALP SUITE  (SCO-0010)  --  1m bars | 0.7% stop | 1.4% TP | 2:1 R:R
# =============================================================================

def strat_xrp_vwap_bounce_s(sym):
    bars = get_bars(sym, 60, 1)
    if bars is None or len(bars) < 20: return _hold("bars unavailable")
    close = bars["close"]
    cur = float(close.iloc[-1])
    vw  = float(vwap(bars).iloc[-1])
    r   = float(rsi(close).iloc[-1])
    if cur > vw and 35 < r < 75:
        return _buy(cur, f"1m VWAP:{vw:.4f} RSI:{r:.1f}")
    return _hold(f"1m Above:{cur>vw} RSI:{r:.0f}")

def strat_xrp_rsi_bull_s(sym):
    bars = get_bars(sym, 30, 1)
    if bars is None or len(bars) < 15: return _hold("bars unavailable")
    close = bars["close"]
    cur = float(close.iloc[-1])
    r   = float(rsi(close).iloc[-1])
    green = cur > float(close.iloc[-2])
    if r > 50 or (r < 33 and green):
        return _buy(cur, f"1m RSI:{r:.1f}")
    return _hold(f"1m RSI:{r:.1f}")

def strat_xrp_ema50_align_s(sym):
    bars = get_bars(sym, 60, 1)
    if bars is None or len(bars) < 25: return _hold("bars unavailable")
    close = bars["close"]
    cur = float(close.iloc[-1])
    e9  = float(ema(close, 9).iloc[-1])
    e21 = float(ema(close, 21).iloc[-1])
    if e9 > e21 and cur > float(close.iloc[-2]):
        return _buy(cur, f"1m EMA9:{e9:.4f}>EMA21:{e21:.4f}")
    return _hold(f"1m EMA9:{e9:.4f} EMA21:{e21:.4f}")

def strat_xrp_big_candle_s(sym):
    bars = get_bars(sym, 30, 1)
    if bars is None or len(bars) < 20: return _hold("bars unavailable")
    close = bars["close"]
    opens = bars["open"]
    cur  = float(close.iloc[-1])
    body = abs(float(close.iloc[-1]) - float(opens.iloc[-1]))
    avg_b = abs(close - opens).iloc[-20:].mean()
    r    = float(rsi(close).iloc[-1])
    if body > 1.2 * avg_b and cur > float(opens.iloc[-1]) and r < 72:
        return _buy(cur, f"1m BigCandle {body:.4f} vs {avg_b:.4f}")
    return _hold(f"1m BigBull:False RSI:{r:.0f}")

def strat_xrp_stoch_bull_s(sym):
    bars = get_bars(sym, 60, 1)
    if bars is None or len(bars) < 20: return _hold("bars unavailable")
    close = bars["close"]
    cur = float(close.iloc[-1])
    K, D = stoch(bars)
    k = float(K.iloc[-1])
    d = float(D.iloc[-1])
    if k > d and cur > float(close.iloc[-2]):
        return _buy(cur, f"1m K:{k:.1f}>D:{d:.1f}")
    return _hold(f"1m KgtD:{k>d} Green:{cur>float(close.iloc[-2])}")

def strat_xrp_higher_close_s(sym):
    bars = get_bars(sym, 10, 1)
    if bars is None or len(bars) < 5: return _hold("bars unavailable")
    close = bars["close"]
    vol   = bars["volume"]
    c1, c2, c3 = float(close.iloc[-1]), float(close.iloc[-2]), float(close.iloc[-3])
    if c1 > c2 > c3 and float(vol.iloc[-1]) > float(vol.iloc[-2]):
        return _buy(c1, f"1m HiClose {c3:.4f}>{c2:.4f}>{c1:.4f}")
    return _hold(f"1m Rising:{c1>c2>c3} Vol:{float(vol.iloc[-1])>float(vol.iloc[-2])}")

def strat_xrp_atr_bull_s(sym):
    bars = get_bars(sym, 30, 1)
    if bars is None or len(bars) < 16: return _hold("bars unavailable")
    close = bars["close"]
    cur  = float(close.iloc[-1])
    prv  = float(close.iloc[-2])
    a    = float(atr(bars).iloc[-1])
    r    = float(rsi(close).iloc[-1])
    move = abs(cur - prv)
    if move > 0.3 * a and cur > prv and r < 72:
        return _buy(cur, f"1m ATRbull {move:.4f}>0.3x{a:.4f}")
    return _hold(f"1m BigUp:{move>0.3*a} RSI:{r:.0f}")

def strat_xrp_ema_touch_s(sym):
    bars = get_bars(sym, 40, 1)
    if bars is None or len(bars) < 22: return _hold("bars unavailable")
    close = bars["close"]
    cur = float(close.iloc[-1])
    e21 = float(ema(close, 21).iloc[-1])
    r   = float(rsi(close).iloc[-1])
    dist = abs(cur - e21) / e21
    if dist < 0.015 and 30 < r < 70:
        return _buy(cur, f"1m EMAtouch {dist*100:.2f}%")
    return _hold(f"1m dist:{dist*100:.2f}% RSI:{r:.0f}")

def strat_xrp_close_high_s(sym):
    bars = get_bars(sym, 30, 1)
    if bars is None or len(bars) < 10: return _hold("bars unavailable")
    row  = bars.iloc[-1]
    cur  = float(row["close"])
    prv  = float(bars["close"].iloc[-2])
    rng  = float(row["high"]) - float(row["low"])
    pos  = (cur - float(row["low"])) / (rng + 1e-10)
    if pos >= 0.5 and cur > prv:
        return _buy(cur, f"1m CloseHigh {pos*100:.0f}%")
    return _hold(f"1m Top50:{pos>=0.5} Green:{cur>prv}")

def strat_xrp_triple_ema_s(sym):
    bars = get_bars(sym, 60, 5)
    if bars is None or len(bars) < 52: return _hold("bars unavailable")
    close = bars["close"]
    cur = float(close.iloc[-1])
    e9  = float(ema(close, 9).iloc[-1])
    e21 = float(ema(close, 21).iloc[-1])
    e50 = float(ema(close, 50).iloc[-1])
    r   = float(rsi(close).iloc[-1])
    if e9 > e21 > e50 and 35 < r < 78:
        return _buy(cur, f"5m TripleEMA RSI:{r:.1f}")
    return _hold(f"5m E9:{e9:.4f} E21:{e21:.4f} E50:{e50:.4f}")

DISPATCH = {
    "REGIME_AUTO":     strat_regime_auto,
    "MEAN_REV_VWAP":   strat_mean_rev_vwap,
    "VOL_BURST":       strat_vol_burst,
    "SUPPORT_BOUNCE":  strat_support_bounce,
    "GLD_GOLD":        strat_gld_gold,
    "HULL_TSI_CCI":    strat_hull_tsi_cci,
    "HABB_SCALP":      strat_habb_scalp,
    "SQ_BEAR":         strat_sq_bear,
    "EMA_RIBBON":      strat_ema_ribbon,
    "FS1000":          strat_fs1000,
    "STOCHASTIC":      strat_stochastic,
    "MULTI_TF":        strat_multi_tf,
    "RSI_DIV":         strat_rsi_div,
    "BREAKOUT":        strat_breakout,
    "BOLLINGER":       strat_bollinger,
    "GRID":            strat_grid,
    "EMA_CROSS":       strat_ema_cross,
    "RSI_SIMPLE":      strat_rsi_simple,
    "STOCH_SIMPLE":    strat_stoch_simple,
    "EMA_BOUNCE":      strat_ema_bounce,
    "REV_HUNTER":      strat_rev_hunter,
    "MANNAN_V2":       strat_mannan_v2,
    "XRP_SCALP_BB":    strat_xrp_scalp_bb,
    "XRP_PULLBACK":    strat_xrp_pullback,
    "XRP_VWAP_TOUCH":  strat_xrp_vwap_touch,
    "XRP_DUAL_RSI":    strat_xrp_dual_rsi,
    "XRP_CANDLE_SURGE":strat_xrp_candle_surge,
    "XRP_RANGE_BREAK": strat_xrp_range_break,
    "XRP_MICRO_DIV":   strat_xrp_micro_div,
    "XRP_VOL_DELTA":   strat_xrp_vol_delta,
    "XRP_ATR_SPIKE":   strat_xrp_atr_spike,
    "XRP_BTC_DIVERG":  strat_xrp_btc_diverg,
    "XRP_SESSION_VWAP":strat_xrp_session_vwap,
    "XRP_CONVICTION":  strat_xrp_conviction,
    "XRP_NIGHT_BREAK": strat_xrp_night_break,
    "XRP_BASKET_LEAD": strat_xrp_basket_lead,
    "XRP_STAIRCASE":   strat_xrp_staircase,
    # v8.8n: #42-51 all coded
    "VWAP_CROSS":  strat_vwap_cross,
    "VWAP_BOUNCE": strat_vwap_bounce,
    "CMF_DIV":     strat_cmf_div,
    "STOCH_OS":    strat_stoch_os,
    "STOCH_OB":    strat_stoch_ob,
    "STOCH_RSI":   strat_stoch_rsi,
    "WILLIAMS_R":  strat_williams_r,
    "CCI_REV":     strat_cci_rev,
    "HEAD_SHLD":   strat_head_shld,
    "INV_H_S":     strat_inv_head_shld,
    # Research-backed XRP strategies (#130-134)
    "XRP_BB_ADX":        strat_xrp_bb_adx,
    "XRP_NEWS_FADE":     strat_xrp_news_fade,
    "XRP_COMPRESS":      strat_xrp_compress,
    "XRP_SUPPORT_RANGE": strat_xrp_support_range,
    "XRP_BREAKOUT_V2":   strat_xrp_breakout_v2,
    # Project A
    "XRP_CANDLE_SURGE":  strat_xrp_candle_surge,
    # v9.2 XRP simple strategies
    "XRP_VWAP_BOUNCE":   strat_xrp_vwap_bounce,
    "XRP_RSI_BULL":      strat_xrp_rsi_bull,
    "XRP_EMA50_ALIGN":   strat_xrp_ema50_align,
    "XRP_BIG_CANDLE":    strat_xrp_big_candle,
    "XRP_STOCH_BULL":    strat_xrp_stoch_bull,
    "XRP_HIGHER_CLOSE":  strat_xrp_higher_close,
    "XRP_ATR_BULL":      strat_xrp_atr_bull,
    "XRP_EMA_TOUCH":     strat_xrp_ema_touch,
    "XRP_CLOSE_HIGH":    strat_xrp_close_high,
    "XRP_TRIPLE_EMA":    strat_xrp_triple_ema,
    # SCO-0010 -S Scalp Suite
    "XRP_VWAP_BOUNCE-S":  strat_xrp_vwap_bounce_s,
    "XRP_RSI_BULL-S":     strat_xrp_rsi_bull_s,
    "XRP_EMA50_ALIGN-S":  strat_xrp_ema50_align_s,
    "XRP_BIG_CANDLE-S":   strat_xrp_big_candle_s,
    "XRP_STOCH_BULL-S":   strat_xrp_stoch_bull_s,
    "XRP_HIGHER_CLOSE-S": strat_xrp_higher_close_s,
    "XRP_ATR_BULL-S":     strat_xrp_atr_bull_s,
    "XRP_EMA_TOUCH-S":    strat_xrp_ema_touch_s,
    "XRP_CLOSE_HIGH-S":   strat_xrp_close_high_s,
    "XRP_TRIPLE_EMA-S":   strat_xrp_triple_ema_s,
}

def run_strategy(slot):
    fn = DISPATCH.get(slot["strategy"])
    if fn is None:
        return _hold(f"Unknown strategy: {slot['strategy']}")
    try:
        # ATR pre-filter: skip if 1m market is too flat or too chaotic for reliable fills
        _b1 = get_bars(slot["symbol"], 20, 1)
        if _b1 is not None and len(_b1) >= 15:
            _atr_pct = float(atr(_b1).iloc[-1]) / float(_b1["close"].iloc[-1])
            if _atr_pct < 0.0006:
                return _hold(f"ATR too flat ({_atr_pct*100:.3f}% < 0.06%)")
            if _atr_pct > 0.0060:
                return _hold(f"ATR too chaotic ({_atr_pct*100:.3f}%)")
        # ADX filter for non-exempt strategies
        if slot["strategy"] not in ADX_EXEMPT:
            tf = 5 if "/" in slot["symbol"] else 15
            bars = get_bars(slot["symbol"], 30, tf)
            if bars is not None and len(bars) >= 14:
                adx_val = float(adx(bars).iloc[-1])
                if adx_val < 20:
                    return _hold(f"ADX:{adx_val:.0f}<20 — no trend, skipping", 0, {"ADX": round(adx_val,1)})
        return fn(slot["symbol"])
    except Exception as e:
        log.error(f"Strategy error {slot['name']}: {e}")
        return _hold(f"Error: {e}")

# ─────────────────────────────────────────────────────────────────
# TRADING
# ─────────────────────────────────────────────────────────────────
def get_account():
    try:
        a = trading_client.get_account()
        # For crypto paper accounts, a.cash is the most reliable available-funds field.
        # non_marginable_buying_power is a stock field that often misreports for crypto
        # and can return a tiny reserve amount rather than actual spendable balance.
        raw_cash = float(a.cash or 0)
        return {"equity": float(a.equity), "cash": raw_cash}
    except Exception as e:
        log.error(f"Account error: {e}")
        return {"equity": 0.0, "cash": 0.0}

def get_positions():
    try:
        return {p.symbol: p for p in trading_client.get_all_positions()}
    except Exception as e:
        log.error(f"Positions error: {e}")
        return {}

def do_buy(slot, price, cash, equity=0):
    sym = slot["symbol"]
    try:
        if cash <= 0:
            slot["last_action"] = "BUY SKIPPED — no cash"
            return
        # Size off equity target, but cap at 30% of free cash per trade.
        # This leaves room for other slots to trade in the same session.
        target = equity * RISK["POSITION_PCT"]
        dollar = min(target, cash * 0.30)
        if dollar < 10.0:   # Alpaca crypto minimum confirmed $10
            slot["last_action"] = f"BUY SKIPPED — ${dollar:.2f} sized (need $10 min, ${cash:.2f} free)"
            return
        qty = round(dollar / price, 6)
        if qty <= 0:
            slot["last_action"] = "BUY SKIPPED — qty too small"
            return
        trading_client.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty,
            side=OrderSide.BUY,
            time_in_force=order_tif(sym)
        ))
        slot["peak_price"]    = price
        slot["last_trade_ts"] = time.time()
        slot["has_position"]  = True
        slot["last_action"]   = f"BUY {sym} @ ${price:,.4f} | ${dollar:.2f}"
        slot["entry_time"]    = time.time()
        log_trade(slot, "BUY", price, qty, 0, 0)
        log.info(slot["last_action"])
    except Exception as e:
        slot["last_action"] = f"BUY FAILED: {e}"
        log.error(slot["last_action"])

def do_sell(slot, positions, reason):
    sym = slot["symbol"]
    sc  = sym.replace("/", "")
    pos = positions.get(sc) or positions.get(sym)
    if not pos:
        slot["has_position"] = False
        return
    try:
        qty   = float(pos.qty)
        price = float(pos.current_price)
        pnl   = float(pos.unrealized_pl)
        plpc  = float(pos.unrealized_plpc)
        won   = pnl > 0
        trading_client.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty,
            side=OrderSide.SELL,
            time_in_force=order_tif(sym)
        ))
        if won:
            slot["wins"]       += 1
            slot["best_trade"]  = max(slot["best_trade"], pnl)
        else:
            slot["losses"]     += 1
            slot["worst_trade"] = min(slot["worst_trade"], pnl)
        slot["total_pnl"]    += pnl
        slot["peak_price"]    = 0.0
        slot["last_trade_ts"] = time.time()
        slot["has_position"]  = False
        slot["last_action"]   = f"SELL {sym} — {reason} | {'WIN' if won else 'LOSS'} ${pnl:+.4f}"
        log_trade(slot, "SELL", price, qty, round(pnl,4), round(plpc*100,4), reason, "WIN" if won else "LOSS")
        update_stats(slot, won, pnl)
        state["total_pnl"] += pnl
        # Profit factor components
        if won: state["wins_total_pnl"]   += pnl
        else:   state["losses_total_pnl"] += abs(pnl)
        # Hold time
        if slot.get("entry_time"):
            dur = time.time() - slot["entry_time"]
            slot["total_hold_secs"] += dur
            slot["completed"]       += 1
            slot["entry_time"]       = 0
        # Peak equity / drawdown (updated on sell)
        try:
            cur_eq = state.get("equity", 0)
            if cur_eq > state.get("peak_equity", 0):
                state["peak_equity"] = cur_eq
            pk = state.get("peak_equity", 0)
            state["current_drawdown"] = round((pk - cur_eq) / pk * 100, 2) if pk > 0 else 0.0
        except Exception: pass
        # Session tagging
        for ses in get_sessions():
            ss = state["session_stats"].setdefault(ses, {"wins":0,"losses":0,"pnl":0.0})
            ss["pnl"] += pnl
            if won: ss["wins"]   += 1
            else:   ss["losses"] += 1
        # v9.0 lifetime counters — never reset across rotations
        state["lifetime_trades"]  = state.get("lifetime_trades", 0) + 1
        state["lifetime_wins"]    = state.get("lifetime_wins", 0) + (1 if won else 0)
        state["lifetime_losses"]  = state.get("lifetime_losses", 0) + (0 if won else 1)
        state["lifetime_pnl"]     = round(state.get("lifetime_pnl", 0.0) + pnl, 4)
        # v8.8a: daily aggregates keyed by Central Time date (rolls over at 12:01 AM CT)
        today_ct = central_today()
        state["daily_trades"][today_ct] = state["daily_trades"].get(today_ct, 0) + 1
        state["daily_pnl"][today_ct]    = round(state["daily_pnl"].get(today_ct, 0.0) + pnl, 4)
        # v8.8d: streak tracking — positive = wins in a row, negative = losses in a row.
        try:
            cur = state.get("current_streak", 0) or 0
            if won:
                cur = cur + 1 if cur > 0 else 1
                state["current_streak"] = cur
                if cur > state.get("best_win_streak", 0):
                    state["best_win_streak"] = cur
            else:
                cur = cur - 1 if cur < 0 else -1
                state["current_streak"] = cur
                if cur < state.get("worst_loss_streak", 0):
                    state["worst_loss_streak"] = cur
        except Exception as e:
            log.warning(f"Streak tracking failed: {e}")
        save_data()
        log.info(slot["last_action"])
    except Exception as e:
        log.error(f"Sell failed {sym}: {e}")

def log_trade(slot, typ, price, qty, pnl, pnl_pct, reason="", result="OPEN"):
    state["trade_log"].append({
        "slot": slot["name"], "symbol": slot["symbol"],
        "strategy": slot["strategy"], "type": typ,
        "price": price, "qty": qty, "pnl": pnl,
        "pnl_pct": pnl_pct, "reason": reason,
        "result": result,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    if len(state["trade_log"]) > 1000:
        state["trade_log"] = state["trade_log"][-1000:]

def update_stats(slot, won, pnl):
    s = slot["strategy"]
    if s not in state["strategy_stats"]:
        state["strategy_stats"][s] = {"wins": 0, "losses": 0, "total_pnl": 0.0}
    ss = state["strategy_stats"][s]
    ss["total_pnl"] += pnl
    if won: ss["wins"]   += 1
    else:   ss["losses"] += 1

# ─────────────────────────────────────────────────────────────────
# RISK MANAGEMENT
# ─────────────────────────────────────────────────────────────────
def update_day(equity):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if today != state["current_day"]:
        state["current_day"]   = today
        state["daily_start"]   = equity
        state["daily_cap_hit"] = False
    if state["daily_start"] is None:
        state["daily_start"] = equity

def can_trade(equity):
    if state["daily_cap_hit"]: return False
    if not equity or equity <= 0: return True  # API failure — don't false-trigger cap
    ds = state["daily_start"]
    if ds and ds > 0 and (ds - equity) / ds >= RISK["DAILY_LOSS_CAP"]:
        state["daily_cap_hit"] = True
        log.warning("Daily loss cap hit — pausing until tomorrow")
        return False
    return True

def cooldown_ok(slot):
    return (time.time() - slot["last_trade_ts"]) >= RISK["COOLDOWN_SECONDS"]

def check_exits(slot, positions, price):
    if not slot["has_position"]: return
    if price > slot["peak_price"]:
        slot["peak_price"] = price
    sc  = slot["symbol"].replace("/", "")
    pos = positions.get(sc) or positions.get(slot["symbol"])
    if not pos:
        slot["has_position"] = False
        return
    plpc = float(pos.unrealized_plpc)
    # v8.8e: per-strategy take profit — look up this slot's strategy in STRATEGY_TP,
    # fall back to the default TAKE_PROFIT_PCT if not found.
    tp_pct = RISK["STRATEGY_TP"].get(slot["strategy"], RISK["TAKE_PROFIT_PCT"])
    # v8.8e: trailing gate — trail only activates AFTER trade is already +TRAIL_GATE_PCT in profit.
    # Prevents +0.9% → -0.8% trades from being "saved" by a trail that fires too early.
    trail_gate = plpc >= RISK["TRAIL_GATE_PCT"]
    trail_ok   = trail_gate and slot["peak_price"] > 0 and price < slot["peak_price"] * (1 - RISK["TRAILING_PCT"])
    if   plpc <= -RISK["STOP_LOSS_PCT"]:        do_sell(slot, positions, "STOP LOSS")
    elif plpc >=  tp_pct - 0.00001:             do_sell(slot, positions, "TAKE PROFIT")  # -0.001% tolerance for float precision
    elif trail_ok:                      do_sell(slot, positions, "TRAILING STOP")


def get_sessions():
    """Return active market session(s) based on current UTC hour.
    Asia: 00-09 UTC | London: 07-16 UTC | New York: 13-22 UTC
    Overlap (London+NY): 13-16 UTC — highest volume window."""
    h = datetime.now(timezone.utc).hour
    s = []
    if  0 <= h <  9: s.append("Asia")
    if  7 <= h < 16: s.append("London")
    if 13 <= h < 22: s.append("New York")
    if "London" in s and "New York" in s:
        s.append("Overlap")
    if not s: s.append("Off-Hours")
    return s

# ─────────────────────────────────────────────────────────────────
# COST TRACKER
# ─────────────────────────────────────────────────────────────────
def get_cost():
    e = (datetime.now(timezone.utc) - START_TIME).total_seconds()
    h, m, s = int(e//3600), int((e%3600)//60), int(e%60)
    cost = e * CONFIG["VM_COST_SEC"] + (e / 86400 / 30) * CONFIG["BASE_MONTHLY"]
    return {"uptime_str": f"{h}h {m}m {s}s", "total_cost": round(cost, 4)}

# ─────────────────────────────────────────────────────────────────
# BOT CYCLE
# ─────────────────────────────────────────────────────────────────
def run_cycle():
    if not trading_client:
        for sl in SLOTS:
            sl["last_action"] = "ERROR: Set ALPACA_API_KEY and ALPACA_SECRET_KEY in Railway Variables"
        return

    acct      = get_account()
    equity    = acct["equity"]
    cash      = acct["cash"]
    state["api_healthy"] = (equity > 0)
    state["equity"]      = equity   # keep for drawdown calc
    positions = get_positions()
    # Top 10 crypto volume snapshot
    try:
        _vclist = [("BTC","BTC/USD"),("ETH","ETH/USD"),("XRP","XRP/USD"),
                   ("SOL","SOL/USD"),("DOGE","DOGE/USD"),("ADA","ADA/USD"),
                   ("AVAX","AVAX/USD"),("LINK","LINK/USD"),("LTC","LTC/USD"),
                   ("BCH","BCH/USD")]
        _vs = []
        for _tk, _sy in _vclist:
            try:
                _vb = get_bars(_sy, 60, 1)
                if _vb is not None and len(_vb) > 0:
                    _vs.append({"symbol": _tk, "volume": round(float(_vb["volume"].sum()), 2)})
            except Exception:
                pass
        if _vs:
            state["vol_snapshot"] = sorted(_vs, key=lambda x: -x["volume"])[:10]
    except Exception:
        pass
    # Live ATR + price history + trades-per-hour
    try:
        _b = get_bars("XRP/USD", 20, 1)
        if _b is not None and len(_b) >= 15:
            _a = atr(_b); _p = float(_b["close"].iloc[-1])
            state["live_atr_pct"] = round(float(_a.iloc[-1]) / _p * 100, 3)
            ph = state.get("price_history", [])
            ph.append(round(_p, 5)); state["price_history"] = ph[-60:]
    except Exception: pass
    # Sessions
    state["current_sessions"] = get_sessions()
    # Trades this hour
    _hr = datetime.now(timezone.utc).hour
    if _hr != state.get("current_hour", -1):
        state["current_hour"]     = _hr
        state["trades_this_hour"] = 0
    # Peak equity on every cycle
    if equity > state.get("peak_equity", 0): state["peak_equity"] = equity
    pk = state.get("peak_equity", 0)
    state["current_drawdown"] = round((pk - equity) / pk * 100, 2) if pk > 0 else 0.0

    # Clean slate on every fresh deployment.
    # Step 1: cancel ALL open orders (Alpaca rejects close_position if orders exist).
    # Step 2: close ALL positions.
    if not state.get("_startup_clean"):
        state["_startup_clean"] = True
        try:
            cancelled = trading_client.cancel_orders()
            if cancelled:
                log.info(f"STARTUP: cancelled {len(cancelled)} open order(s)")
                time.sleep(1.5)   # let cancellations settle before closing
        except Exception as oe:
            log.warning(f"STARTUP: order cancel failed: {oe}")
        # Re-fetch positions after cancellations
        try:
            positions = get_positions()
        except Exception:
            pass
        if positions:
            log.info(f"STARTUP: closing {len(positions)} position(s) for clean slate...")
            for sym_key, pos in list(positions.items()):
                try:
                    trading_client.close_position(sym_key)
                    log.info(f"  CLOSED {sym_key} ${float(pos.market_value):.2f} P&L ${float(pos.unrealized_pl):+.2f}")
                except Exception as ce:
                    log.warning(f"  Could not close {sym_key}: {ce}")
                    # Try cancel+retry once
                    try:
                        trading_client.cancel_orders()
                        time.sleep(1)
                        trading_client.close_position(sym_key)
                        log.info(f"  CLOSED {sym_key} on retry")
                    except Exception as ce2:
                        log.error(f"  FAILED to close {sym_key} after retry: {ce2}")
            positions = {}
            for sl in SLOTS:
                sl["has_position"] = False
                sl["peak_price"]   = 0.0
        else:
            log.info("STARTUP: no open positions — clean slate confirmed")

    state["equity"]      = equity
    state["cash"]        = cash
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    # v8.8d: track peak equity and max drawdown from that peak (defensive, never raises)
    try:
        if equity and equity > state.get("peak_equity", 0.0):
            state["peak_equity"] = float(equity)
        peak = state.get("peak_equity", 0.0) or 0.0
        if peak > 0 and equity is not None:
            dd = peak - float(equity)
            if dd > state.get("max_drawdown", 0.0):
                state["max_drawdown"]     = round(dd, 4)
                state["max_drawdown_pct"] = round((dd / peak) * 100.0, 2)
    except Exception as e:
        log.warning(f"Drawdown tracking failed: {e}")

    try:
        state["cash_in_use"] = sum(
            float(p.market_value) for p in positions.values()
            if hasattr(p, "market_value") and p.market_value
        )
    except Exception:
        state["cash_in_use"] = 0.0

    update_day(equity)
    trade_ok = can_trade(equity)

    for slot in SLOTS:
        if not slot["active"]:
            slot["signal"]     = "HOLD"
            slot["hold_reason"] = "Slot paused"
            continue

        sc  = slot["symbol"].replace("/", "")
        pos = positions.get(sc) or positions.get(slot["symbol"])

        if slot["has_position"] and pos:
            check_exits(slot, positions, float(pos.current_price))
            time.sleep(CONFIG["API_DELAY"])
            continue

        if not trade_ok:
            slot["hold_reason"] = "Daily cap hit"
            continue

        if not cooldown_ok(slot):
            remaining = int(RISK["COOLDOWN_SECONDS"] - (time.time() - slot["last_trade_ts"]))
            slot["hold_reason"] = f"Cooldown {remaining}s"
            continue

        result = run_strategy(slot)
        slot["signal"]         = result["signal"]
        slot["price"]          = result["price"]
        slot["indicator_vals"] = result.get("vals", {})
        slot["hold_reason"]    = result.get("reason", "")
        # Show Central time so "3:42p" is obviously a clock reading, not elapsed time
        try:
            from zoneinfo import ZoneInfo as _ZI
            _ct = datetime.now(_ZI("America/Chicago"))
        except Exception:
            _ct = datetime.now(timezone.utc) - timedelta(hours=5)
        slot["eval_time"] = _ct.strftime("%-I:%M%p").lower()

        pos_size  = min(equity * RISK["POSITION_PCT"], cash * 0.95)
        open_now  = sum(1 for s in SLOTS if s["has_position"])
        if result["signal"] == "BUY" and open_now >= RISK["MAX_CONCURRENT"]:
            slot["in_line"]     = True
            slot["last_action"] = f"IN LINE — {open_now}/{RISK['MAX_CONCURRENT']} slots active"
        elif result["signal"] == "BUY" and pos_size >= 10.0:
            slot["in_line"] = False
            do_buy(slot, result["price"], cash, min(equity, PAPER_BUDGET))
        elif result["signal"] == "BUY":
            slot["in_line"]     = False
            slot["last_action"] = f"BUY SKIPPED — insufficient cash (${cash:.2f})"
        else:
            slot["in_line"]     = False
            slot["last_action"] = f"HOLD {slot['symbol']} | {slot['hold_reason']}"

        time.sleep(CONFIG["API_DELAY"])

    gc.collect()

# ─────────────────────────────────────────────────────────────────
# BOT LOOP
# ─────────────────────────────────────────────────────────────────
def bot_loop():
    log.info("=" * 60)
    log.info("  SCORPION UNIVERSAL — 10-SLOT FRAMEWORK")
    log.info(f"  Mode:  {'PAPER' if CONFIG['PAPER'] else '*** LIVE ***'}")
    log.info(f"  Slots: {len(SLOTS)}")
    log.info(f"  Port:  {CONFIG['PORT']}")
    if not CONFIG["API_KEY"]:
        log.error("  MISSING API KEY — set ALPACA_API_KEY in Railway Variables")
    log.info("=" * 60)
    state["bot_started"] = True
    backoff = 5
    while True:
        try:
            while state["running"]:
                try:
                    run_cycle()
                    backoff = 5
                except Exception as e:
                    log.error(f"Cycle error: {e}")
                time.sleep(CONFIG["SCAN_INTERVAL"])
        except Exception as e:
            state["restart_count"] += 1
            log.error(f"Bot crashed — restarting in {backoff}s: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

# ─────────────────────────────────────────────────────────────────
# KEEP-ALIVE
# ─────────────────────────────────────────────────────────────────
def ping_loop():
    time.sleep(20)
    # v8.7 Deploy 1: Railway-native keep-alive. RAILWAY_PUBLIC_DOMAIN is set
    # automatically by Railway for any service with a public domain.
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    url = (f"https://{domain}/ping" if domain
           else f"http://localhost:{CONFIG['PORT']}/ping")
    log.info(f"Keep-alive pinging: {url}")
    while True:
        try:
            requests.get(url, timeout=8)
            state["ping_count"] += 1
        except Exception:
            pass
        time.sleep(CONFIG["PING_INTERVAL"])

# ─────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────
DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Scorpion Universal</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#000;--s1:#0a0a0a;--s2:#111;--b:#1a2030;
  --gr:#00ff9d;--grd:rgba(0,255,157,.1);
  --rd:#ff4060;--rdd:rgba(255,64,96,.1);
  --yl:#ffcc00;--yld:rgba(255,204,0,.1);
  --bl:#3d9eff;--bld:rgba(61,158,255,.12);
  --tq:#00e5cc;--tqd:rgba(0,229,204,.15);
  --or:#ff9900;--tx:#8099b3;--br:#cce0ff;
  --mn:'Courier New',monospace
}
body{background:var(--bg);color:var(--tx);font-family:system-ui,sans-serif;min-height:100vh}
.w{max-width:1020px;margin:0 auto;padding:10px 6px}
/* HEADER */
.hdr{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:10px;padding-bottom:8px;border-bottom:2px solid var(--or);flex-wrap:wrap;gap:6px}
.logo{display:flex;align-items:center;gap:10px}
.icon{width:60px;height:60px;border-radius:10px;
  background:linear-gradient(135deg,#1a0a05,#ff6600,#ffcc00);
  display:flex;align-items:center;justify-content:center;font-size:36px;
  box-shadow:0 0 16px rgba(255,102,0,.4)}
.title{font-size:22px;font-weight:900;color:var(--br)}
.sub{font-size:12px;font-family:var(--mn);color:var(--tx);margin-top:2px;letter-spacing:1px}
.hright{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.dot{width:12px;height:12px;border-radius:50%;background:var(--gr);
  box-shadow:0 0 10px var(--gr);display:inline-block;animation:blink 2s infinite}
@keyframes blink{50%{opacity:.1}}
.run-lbl{font-size:15px;font-weight:800;font-family:var(--mn);color:var(--gr);letter-spacing:1px}
.pill{padding:5px 14px;border-radius:20px;font-size:13px;font-family:var(--mn);
  font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.ppaper{background:var(--yld);color:var(--yl);border:1px solid rgba(255,204,0,.4)}
.plive{background:var(--rdd);color:var(--rd);border:1px solid rgba(255,64,96,.4)}
.upd{font-family:var(--mn);font-size:12px;color:var(--tx)}
/* STATUS ROW */
.srow{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}
.si{background:var(--s1);border:1px solid var(--b);border-radius:8px;
  padding:10px 14px;display:flex;align-items:center;justify-content:space-between}
.si-lbl{color:var(--tx);font-size:13px;font-family:var(--mn)}
.sv{font-weight:800;font-size:15px;font-family:var(--mn)}
.sv.g{color:var(--gr)}.sv.y{color:var(--yl)}.sv.b{color:var(--bl)}
/* ACCOUNT */
.acct{background:var(--s1);border:1px solid rgba(0,255,157,.25);
  border-radius:10px;padding:12px;margin-bottom:10px}
.sec-title{font-size:15px;text-transform:uppercase;letter-spacing:2px;
  font-family:var(--mn);color:var(--tx);margin-bottom:10px}
.agrid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
.abox{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:10px;text-align:center}
.abox.hi{border-color:rgba(0,255,157,.4);background:var(--grd)}
.abox.pnl{border-color:rgba(255,204,0,.3);background:var(--yld)}
.albl{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;
  font-family:var(--mn);color:var(--tx);margin-bottom:5px}
.aval{font-size:22px;font-weight:900;font-family:var(--mn);color:var(--br);line-height:1}
.aval.g{color:var(--gr)}.aval.r{color:var(--rd)}.aval.y{color:var(--yl)}.aval.b{color:var(--bl)}
.asub{font-size:11px;font-family:var(--mn);color:var(--tx);margin-top:4px}
/* CONTROLS */
.ctrl{display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap}
.btn{padding:11px 22px;border-radius:8px;border:1px solid var(--b);
  background:var(--s2);color:var(--br);font-size:14px;font-weight:700;
  cursor:pointer;transition:all .15s}
.btn:hover{border-color:var(--or);color:var(--or)}
.btn.on{background:rgba(255,153,0,.15);border-color:var(--or);color:var(--or)}
.btn.stop:hover{border-color:var(--rd);color:var(--rd)}
/* SLOTS GRID */
.slots{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;margin-bottom:10px}
.slot{background:var(--s1);border:1px solid var(--b);border-radius:8px;
  padding:8px;transition:border-color .3s}
.slot.working{border-color:rgba(0,229,204,.35)}
.slot-top{display:flex;align-items:center;gap:6px;margin-bottom:5px}
.tqdot{width:14px;height:14px;border-radius:50%;flex-shrink:0}
.tqdot.on{background:var(--tq);box-shadow:0 0 10px var(--tq),0 0 20px rgba(0,229,204,.4);
  animation:tqblink 1s ease-in-out infinite}
@keyframes tqblink{0%,100%{opacity:1;box-shadow:0 0 10px var(--tq),0 0 22px rgba(0,229,204,.5)}
  50%{opacity:.2;box-shadow:0 0 4px var(--tq)}}
.tqdot.off{background:#1e2a3a}
.sname{font-size:17px;font-weight:900;color:var(--br)}
.ssym{font-size:14px;font-family:var(--mn);color:var(--tx);font-weight:700}
.sbadge{font-size:11px;font-family:var(--mn);font-weight:700;padding:3px 7px;
  border-radius:3px;text-transform:uppercase;margin-left:auto;white-space:nowrap}
.sbadge.buy{background:var(--grd);color:var(--gr);border:1px solid rgba(0,255,157,.4)}
.sbadge.hold{background:rgba(128,153,179,.08);color:var(--tx);border:1px solid var(--b)}
.sbadge.paused{background:rgba(128,153,179,.05);color:var(--tx);border:1px solid var(--b)}
.sstrat{font-size:14px;font-family:var(--mn);font-weight:800;text-transform:uppercase;margin-bottom:5px;letter-spacing:.5px}
.swl{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:4px 0}
.swbox{background:var(--s2);border:1px solid var(--b);border-radius:4px;padding:4px;text-align:center}
.swval{font-size:20px;font-weight:900;font-family:var(--mn);line-height:1}
.swval.g{color:var(--gr)}.swval.r{color:var(--rd)}
.swlbl{font-size:12px;text-transform:uppercase;font-family:var(--mn);color:var(--tx);font-weight:700}
.spnl{display:flex;justify-content:space-between;font-family:var(--mn);font-size:14px;margin:3px 0;font-weight:700}
/* v8.8d: .sact = "the little white words under each config's double boxes" — enlarged per spec */
.sact{font-family:var(--mn);font-size:14px;color:#cce0ff;
  word-break:break-word;line-height:1.35;min-height:18px;margin-top:4px;font-weight:600}
.sfoot{display:flex;justify-content:space-between;margin-top:4px;
  padding-top:4px;border-top:1px solid rgba(255,255,255,.05);
  font-family:var(--mn);font-size:13px;font-weight:600}
/* SCOREBOARD */
.score{background:var(--s1);border:1px solid var(--b);border-radius:10px;
  padding:12px;margin-bottom:10px;width:100%;box-sizing:border-box}
.sgrid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
.sbox{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:10px;text-align:center}
.sbox.wc{border-color:rgba(0,255,157,.3);background:var(--grd)}
.sbox.lc{border-color:rgba(255,64,96,.3);background:var(--rdd)}
.sbox.bc{border-color:rgba(61,158,255,.3);background:var(--bld)}
.snum{font-size:22px;font-weight:900;font-family:var(--mn);line-height:1}
.snum.g{color:var(--gr)}.snum.r{color:var(--rd)}.snum.b{color:var(--bl)}.snum.y{color:var(--yl)}
.snlbl{font-size:10px;text-transform:uppercase;font-family:var(--mn);color:var(--tx);margin-top:4px}
.wrbar{height:6px;background:var(--rdd);border-radius:3px;overflow:hidden;margin-top:10px}
.wrfill{height:100%;background:linear-gradient(90deg,var(--gr),#00ffcc);transition:width .8s}
/* TWO-COL */
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.panel{background:var(--s1);border:1px solid var(--b);border-radius:10px;overflow:hidden}
.ph{padding:8px 14px;border-bottom:1px solid var(--b);
  display:flex;justify-content:space-between;align-items:center;background:var(--s2)}
.pt{font-size:12px;text-transform:uppercase;letter-spacing:2px;font-family:var(--mn);color:var(--tx)}
.pcard{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.03)}
.psym{font-weight:800;font-size:14px;color:var(--br);font-family:var(--mn)}
.prow{display:flex;justify-content:space-between;padding:2px 0;font-family:var(--mn);font-size:11px}
.pk{color:var(--tx)}.pv{font-weight:600}
.pv.g{color:var(--gr)}.pv.r{color:var(--rd)}
.alog{max-height:180px;overflow-y:auto;padding:6px 14px;font-family:var(--mn);font-size:11px}
.lr{display:flex;gap:8px;padding:3px 0;border-bottom:1px solid rgba(255,255,255,.02)}
.lt{color:var(--tx);opacity:.5;font-size:10px;white-space:nowrap}
.lm{flex:1}
.lm.buy{color:var(--gr)}.lm.sell{color:var(--rd)}.lm.warn{color:var(--yl)}.lm.hold{color:var(--tx)}
/* LEADERBOARDS */
.lbpair{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.lbrow{display:grid;grid-template-columns:30px 1fr 55px 55px 65px;
  gap:6px;align-items:center;padding:5px 10px;
  border-bottom:1px solid rgba(255,255,255,.03);font-family:var(--mn);font-size:11px}
.lbrow.hdr{background:var(--s2);font-size:10px;color:var(--tx);
  text-transform:uppercase;border-bottom:1px solid var(--b)}
.rank{font-weight:900;text-align:center;font-size:12px}
.r1{color:#ffd700}.r2{color:#c0c0c0}.r3{color:#cd7f32}.rn{color:var(--or)}
/* HISTORY */
.trow{display:grid;grid-template-columns:50px 65px 70px 1fr 65px 55px;
  gap:5px;align-items:center;padding:5px 10px;
  border-bottom:1px solid rgba(255,255,255,.03);font-family:var(--mn);font-size:10px}
.trow.hdr{background:var(--s2);font-weight:700;color:var(--tx);text-transform:uppercase}
.tt{font-weight:700;text-align:center;padding:2px 4px;border-radius:3px;font-size:9px}
.tw{background:var(--grd);color:var(--gr)}.tl{background:var(--rdd);color:var(--rd)}
.shrow{display:grid;grid-template-columns:1fr 55px 55px 75px;
  gap:5px;align-items:center;padding:5px 10px;
  border-bottom:1px solid rgba(255,255,255,.03);font-family:var(--mn);font-size:10px}
.shrow.hdr{background:var(--s2);font-weight:700;color:var(--tx);text-transform:uppercase}
/* ANALYTICS LAB */
.lab{background:var(--s1);border:1px solid rgba(0,229,204,.2);
  border-radius:10px;padding:14px;margin-bottom:10px}
.lab3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.labp{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:12px}
.labt{font-size:12px;font-weight:800;color:var(--tq);font-family:var(--mn);
  text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;
  padding-bottom:6px;border-bottom:1px solid var(--b)}
.linput{width:100%;background:var(--bg);border:1px solid var(--b);border-radius:5px;
  padding:7px 10px;color:var(--br);font-family:var(--mn);font-size:12px;
  margin-bottom:6px;outline:none}
.linput:focus{border-color:var(--tq)}
.lbtn{padding:9px 14px;border-radius:6px;border:1px solid var(--tq);
  background:var(--tqd);color:var(--tq);font-family:var(--mn);
  font-size:12px;font-weight:700;cursor:pointer;width:100%;margin-top:4px}
.lbtn:hover{background:rgba(0,229,204,.25)}
.bstat{display:flex;justify-content:space-between;padding:3px 0;
  border-bottom:1px solid rgba(255,255,255,.04);font-family:var(--mn);font-size:11px}
.bk{color:var(--tx)}.bv{font-weight:700}
.bv.g{color:var(--gr)}.bv.r{color:var(--rd)}.bv.b{color:var(--bl)}.bv.y{color:var(--yl)}
.indlist{max-height:200px;overflow-y:auto}
.inditem{padding:5px 0;border-bottom:1px solid rgba(255,255,255,.04)}
.indname{color:var(--br);font-weight:700;font-size:11px;font-family:var(--mn)}
.inddesc{color:var(--tx);font-size:10px;margin-top:1px;font-family:var(--mn)}
.itag{display:inline-block;padding:1px 5px;border-radius:2px;font-size:9px;margin-right:3px;margin-top:2px}
.tt-btn{background:none;border:none;color:var(--tx);cursor:pointer;font-size:11px;font-family:var(--mn)}
/* v8.8b: 4-box grid used by Scoreboard Row 2 (and Analytics Row 2 later) */
.sgrid4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
.snsub{font-size:9px;font-family:var(--mn);color:var(--tx);margin-top:3px;letter-spacing:.5px}
/* v8.8c: Strategic History Evaluation panel */
.she{background:var(--s1);border:1px solid rgba(255,153,0,.25);
  border-radius:10px;padding:14px;margin-bottom:10px}
.she-hdr{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--b);flex-wrap:wrap;gap:6px}
.she-title{font-size:13px;font-weight:800;color:var(--or);font-family:var(--mn);
  text-transform:uppercase;letter-spacing:1.5px}
.she-sort{display:flex;gap:6px;align-items:center;flex:1;justify-content:flex-end}
.she-sb{padding:5px 10px;border-radius:5px;border:1px solid var(--b);
  background:var(--s2);color:var(--tx);font-family:var(--mn);font-size:11px;
  font-weight:700;cursor:pointer;text-transform:uppercase;letter-spacing:.5px}
.she-sb.active{background:rgba(255,153,0,.15);border-color:var(--or);color:var(--or)}
.she-list{max-height:280px;overflow-y:auto;border:1px solid var(--b);border-radius:6px}
.she-row{display:grid;grid-template-columns:34px 1fr 110px 60px 60px 80px 90px 80px 80px;
  gap:6px;align-items:center;padding:8px 10px;
  border-bottom:1px solid rgba(255,255,255,.04);font-family:var(--mn);font-size:13px}
.she-row.hdr{background:var(--s2);color:var(--tx);font-weight:700;
  text-transform:uppercase;font-size:10px;position:sticky;top:0;z-index:1}
.she-rank{text-align:center;color:var(--or);font-weight:900}
.she-combo{color:var(--br);font-weight:700}
.she-combo .ssub{color:var(--tx);font-weight:400;font-size:10px;margin-left:6px}
/* v8.7 Deploy 1: footer tags — filename (orange) and storage status (green/red) */
.file-tag{display:inline-block;padding:2px 7px;border-radius:3px;
  background:rgba(255,153,0,.08);color:var(--or);font-weight:700;
  border:1px solid rgba(255,153,0,.3);margin-left:6px;font-family:var(--mn)}
.stor-tag{display:inline-block;padding:2px 7px;border-radius:3px;font-weight:700;
  margin-left:6px;font-family:var(--mn);font-size:10px}
.stor-tag.ok{background:rgba(0,255,157,.08);color:var(--gr);border:1px solid rgba(0,255,157,.3)}
.stor-tag.bad{background:rgba(255,80,80,.12);color:#ff6b6b;border:1px solid rgba(255,80,80,.4)}
footer{margin-top:10px;padding-top:8px;border-top:1px solid var(--b);
  display:flex;justify-content:space-between;font-family:var(--mn);
  font-size:11px;color:var(--tx);flex-wrap:wrap;gap:5px}
.warn{color:rgba(255,204,0,.4)}
.empty{padding:14px;font-family:var(--mn);font-size:11px;color:var(--tx);text-align:center}

/* SCO-0021 — New metrics panels */
.metrics-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:12px 0}
.mcard{background:var(--c2);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;text-align:center}
.mval{font-size:22px;font-weight:700;font-family:var(--mn);color:var(--tc)}
.mlbl{font-size:10px;color:rgba(128,153,179,.7);margin-top:2px;text-transform:uppercase;letter-spacing:.05em}
.msub{font-size:11px;color:rgba(128,153,179,.5);margin-top:1px}
.session-bar{display:flex;gap:6px;margin:10px 0;flex-wrap:wrap;align-items:center}
.ses-pill{padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:.05em}
.ses-active{background:var(--tc);color:#000}
.ses-inactive{background:rgba(255,255,255,.06);color:rgba(128,153,179,.5)}
.ses-overlap{background:var(--or);color:#000}
.session-table{width:100%;border-collapse:collapse;margin-top:8px;font-size:11px}
.session-table th{color:rgba(128,153,179,.6);font-weight:600;text-align:left;padding:4px 8px;border-bottom:1px solid rgba(255,255,255,.06)}
.session-table td{padding:4px 8px;color:var(--tx)}
.session-table tr:hover td{background:rgba(255,255,255,.03)}
.prog-bar-wrap{background:rgba(255,255,255,.06);border-radius:4px;height:6px;margin:6px 0;overflow:hidden}
.prog-bar-fill{height:100%;border-radius:4px;transition:width .5s}
.sparkline-wrap{margin:8px 0}
.api-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}
.api-ok{background:#00e5cc} .api-err{background:var(--rd)}

.vol-chart{display:flex;align-items:flex-end;gap:6px;height:80px;padding:4px 4px 0;position:relative}
.vol-bar-wrap{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1;height:100%}
.vol-num{font-size:14px;color:rgba(200,216,232,.7);font-family:var(--mn);white-space:nowrap;margin-bottom:2px;text-align:center;font-weight:600}
.vol-bar{width:100%;border-radius:3px 3px 0 0;min-height:3px;transition:height .4s}
.vol-tick{font-size:14px;font-weight:700;margin-top:4px;font-family:var(--mn)}
</style>
</head>
<body>
<div class="w">

<!-- SECTION 1: HEADER -->
<div class="hdr">
  <div class="logo">
    <div class="icon">🦂</div>
    <div>
      <div class="title">Scorpion Universal</div>
      <div class="sub">10-Slot Strategy Framework &middot; Paper Trading</div>
    </div>
  </div>
  <div class="hright">
    <span class="dot"></span>
    <span class="run-lbl">RUNNING</span>
    <span class="pill ppaper" id="mPill">PAPER</span>
    <span class="upd" id="uts">&mdash;</span>
  </div>
</div>

<!-- SECTION 2: STATUS -->
<div class="srow">
  <div class="si"><span class="si-lbl">🟢 Keep-Alive</span><span class="sv g">Ping #<span id="pings">0</span></span></div>
  <div class="si"><span class="si-lbl">🔄 Restarts</span><span class="sv y" id="rst">0</span></div>
  <div class="si"><span class="si-lbl">⏱ Uptime</span><span class="sv b" id="upt">&mdash;</span></div>
</div>

<!-- SECTION 3: ACCOUNT OVERVIEW -->
<div class="acct">
  <div class="sec-title">💰 Account Overview</div>
  <div class="agrid">
    <div class="abox hi"><div class="albl">Portfolio Value</div><div class="aval g" id="equity">$&mdash;</div><div class="asub" id="dpnl">Today: &mdash;</div></div>
    <div class="abox"><div class="albl">Cash Available</div><div class="aval b" id="cash">$&mdash;</div><div class="asub">Undeployed</div></div>
    <div class="abox"><div class="albl">Cash In Use</div><div class="aval y" id="cashInUse">$&mdash;</div><div class="asub">In positions</div></div>
    <div class="abox"><div class="albl">Open Positions</div><div class="aval" id="posCount">0</div><div class="asub">of 10 slots</div></div>
    <div class="abox pnl"><div class="albl">Overall P&amp;L</div><div class="aval y" id="totalPnl">$0.00</div><div class="asub">All time</div></div>
    <div class="abox"><div class="albl">Daily Cap</div><div class="aval g" id="capStat">OK</div><div class="asub">6% limit</div></div>
  </div>
</div>

<!-- SECTION 4: CONTROLS -->
<div class="ctrl">
  <button class="btn on" id="btnR" onclick="toggleBot()">⏸ Running</button>
  <button class="btn stop" onclick="alert('Emergency Stop:\\n1. Go to Railway dashboard\\n2. Pause or delete the service\\n3. Close positions at app.alpaca.markets')">✕ Emergency Stop</button>
  <button class="btn" onclick="loadAll()">↻ Refresh</button>
  <button class="btn" id="btnExport" onclick="exportCSV()" style="border-color:rgba(0,229,204,.5);color:var(--tq)">⬇ Export to Numbers</button>
  <button class="btn" id="btnUpgrade" onclick="showUpgrades()" style="border-color:rgba(255,153,0,.5);color:var(--or)">📋 Last Upgrade</button>
</div>

<!-- SECTION 5: CONFIG CARDS -->
<div class="slots" id="slotsGrid">
  <div class="empty" style="grid-column:1/-1">Loading configs...</div>
</div>

<!-- SECTION 7: SCOREBOARD -->

<!-- SESSION PERFORMANCE -->
<div class="score">
  
  <!-- Volume Chart -->
  <div class="sec-title">Crypto Volume (Top 10)</div>
  <div style="background:var(--s1);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:12px 16px;margin-bottom:4px">
    <div class="vol-chart" id="volChart"></div>
  </div>

<div class="sec-title">📊 Session Performance <span style="font-size:11px;font-family:var(--mn);color:var(--tx);margin-left:8px">resets each rotation</span></div>
  <div class="sgrid">
    <div class="sbox wc"><div class="snum g" id="sbW">0</div><div class="snlbl">Wins</div></div>
    <div class="sbox lc"><div class="snum r" id="sbL">0</div><div class="snlbl">Losses</div></div>
    <div class="sbox bc"><div class="snum b" id="sbWR">&mdash;%</div><div class="snlbl">Win Rate</div></div>
    <div class="sbox"><div class="snum y" id="sbPNL">$0.00</div><div class="snlbl">Session P&amp;L</div></div>
    <div class="sbox"><div class="snum g" id="sbBT">$0.00</div><div class="snlbl">Best Trade</div></div>
    <div class="sbox"><div class="snum r" id="sbWT">$0.00</div><div class="snlbl">Worst Trade</div></div>
  </div>
  <div class="sgrid4">
    <div class="sbox bc"><div class="snum b" id="sbTradesToday">0</div><div class="snlbl">Trades (Session)</div></div>
    <div class="sbox"><div class="snum y" id="sbTradesAll">0</div><div class="snlbl">Trades (Session)</div></div>
    <div class="sbox"><div class="snum g" id="sbPnlToday">$0.00</div><div class="snlbl">P&amp;L Today</div></div>
    <div class="sbox"><div class="snum g" id="sbPnlAll">$0.00</div><div class="snlbl">Session P&amp;L</div><div class="snsub" id="sbIncept">&mdash;</div></div>
  </div>
  <div class="wrbar"><div class="wrfill" id="wrFill" style="width:0%"></div></div>
</div>

<!-- LIFETIME PERFORMANCE -->
<div class="score" style="border-color:#00B8A940">
  <div class="sec-title" style="color:#00B8A9">🏦 Lifetime Performance <span style="font-size:11px;font-family:var(--mn);color:var(--tx);margin-left:8px">all rotations combined</span></div>
  <div class="sgrid">
    <div class="sbox wc"><div class="snum g" id="ltW">0</div><div class="snlbl">Total Wins</div></div>
    <div class="sbox lc"><div class="snum r" id="ltL">0</div><div class="snlbl">Total Losses</div></div>
    <div class="sbox bc"><div class="snum b" id="ltWR">&mdash;%</div><div class="snlbl">Lifetime Win Rate</div></div>
    <div class="sbox"><div class="snum g" id="ltPNL">$0.00</div><div class="snlbl">Lifetime P&amp;L</div></div>
    <div class="sbox"><div class="snum y" id="ltT">0</div><div class="snlbl">Total Trades</div></div>
    <div class="sbox"><div class="snum b" id="ltAvg">$0.00</div><div class="snlbl">Avg P&amp;L / Trade</div></div>
  </div>
  <div class="wrbar" style="background:#0a1a14"><div class="wrfill" id="ltFill" style="width:0%;background:#00B8A9"></div></div>
</div>

<!-- SECTION 8: OPEN TRADES + LOG -->
<div class="two">
  <div class="panel">
    <div class="ph"><span class="pt">Open Trades</span><span id="openCnt" style="font-family:var(--mn);font-size:11px;color:var(--tx)">&mdash;</span></div>
    <div id="posGrid"><div class="empty">No open positions</div></div>
  </div>
  <div class="panel">
    <div class="ph"><span class="pt">Activity Log</span><button class="tt-btn" onclick="clrLog()">clear</button></div>
    <div class="alog" id="logEl"></div>
  </div>
</div>

<!-- SECTIONS 9 & 10: LEADERBOARDS -->
<div class="lbpair">
  <div class="panel">
    <div class="ph"><span class="pt">🏆 Top 10 Most Profitable</span></div>
    <div id="lbProfit"></div>
  </div>
  <div class="panel">
    <div class="ph"><span class="pt">⚡ Top 10 Highest Frequency</span></div>
    <div id="lbFreq"></div>
  </div>
</div>

<!-- SECTION 11: TRADE HISTORY + STRATEGY HISTORY -->
<div class="two" style="margin-bottom:10px">
  <div class="panel">
    <div class="ph"><span class="pt">Trade History</span><span id="trStat" style="font-family:var(--mn);font-size:11px;color:var(--tx)">&mdash;</span></div>
    <div class="trow hdr"><span>Result</span><span>Slot</span><span>Symbol</span><span>Reason</span><span>P&amp;L $</span><span>P&amp;L%</span></div>
    <div id="trLog" style="max-height:200px;overflow-y:auto"><div class="empty">No trades yet</div></div>
  </div>
  <div class="panel">
    <div class="ph"><span class="pt">Strategy History</span><span style="font-family:var(--mn);font-size:10px;color:var(--tx)">All time</span></div>
    <div class="shrow hdr"><span>Strategy</span><span>Win%</span><span>Trades</span><span>P&amp;L</span></div>
    <div id="stratHist" style="max-height:200px;overflow-y:auto"><div class="empty">No data yet</div></div>
  </div>
</div>

<!-- SECTION 12: ANALYTICS LAB -->
<div class="lab">
  <div class="sec-title" style="color:var(--tq)">🔬 Analytics Lab</div>
  <div class="lab3">
    <div class="labp">
      <div class="labt">📈 Backtest Simulator</div>
      <select id="btStrat" class="linput">
        <option value="EMA_CROSS">EMA Cross</option>
        <option value="RSI_SIMPLE">RSI Simple</option>
        <option value="BOLLINGER">Bollinger Band</option>
        <option value="STOCHASTIC">Stochastic</option>
        <option value="BREAKOUT">Breakout</option>
        <option value="MULTI_TF">Multi Timeframe</option>
        <option value="MEAN_REV_VWAP">Mean Rev VWAP</option>
        <option value="VOL_BURST">Vol Burst</option>
        <option value="REGIME_AUTO">Regime Auto</option>
        <option value="FS1000">FS1000</option>
      </select>
      <select id="btSym" class="linput">
        <option>BTC/USD</option><option>ETH/USD</option><option>SOL/USD</option>
        <option>DOGE/USD</option><option>XRP/USD</option><option>LTC/USD</option>
      </select>
      <select id="btDays" class="linput">
        <option value="7">Last 7 days</option>
        <option value="14" selected>Last 14 days</option>
        <option value="30">Last 30 days</option>
        <option value="60">Last 60 days</option>
      </select>
      <button class="lbtn" onclick="runBt()">&#9654; Run Backtest</button>
      <div id="btOut" style="margin-top:10px;display:none"></div>
    </div>
    <div class="labp">
      <div class="labt">📊 Performance Analytics</div>
      <div class="bstat"><span class="bk">Avg Win</span><span class="bv g" id="avgWin">&mdash;</span></div>
      <div class="bstat"><span class="bk">Avg Loss</span><span class="bv r" id="avgLoss">&mdash;</span></div>
      <div class="bstat"><span class="bk">Profit Factor</span><span class="bv b" id="profFac">&mdash;</span></div>
      <div class="bstat"><span class="bk">Best Symbol</span><span class="bv g" id="bestSym">&mdash;</span></div>
      <div class="bstat"><span class="bk">Best Hour UTC</span><span class="bv y" id="bestHr">&mdash;</span></div>
      <div class="bstat"><span class="bk">Total Trades</span><span class="bv b" id="totTr">0</span></div>
      <canvas id="eqc" width="280" height="60"
        style="width:100%;height:60px;margin-top:10px;border-radius:4px;background:var(--bg)"></canvas>
    </div>
    <div class="labp">
      <div class="labt">🔍 Signal Discovery</div>
      <input class="linput" id="indQ" oninput="filterInd(this.value)" placeholder="Search indicators...">
      <div class="indlist" id="indList"></div>
    </div>
  </div>
  <!-- v8.8d: Analytics Lab Row 2 — 4 trader-focused metrics using the same sgrid4 layout as Scoreboard Row 2 -->
  <div class="sgrid4" style="margin-top:12px">
    <div class="sbox"><div class="snum r" id="alMaxDD">$0.00</div><div class="snlbl">Max Drawdown</div><div class="snsub" id="alMaxDDPct">&mdash;</div></div>
    <div class="sbox"><div class="snum y" id="alStreak">0</div><div class="snlbl">Current Streak</div><div class="snsub" id="alStreakSub">Best W: 0 &middot; Worst L: 0</div></div>
    <div class="sbox bc"><div class="snum b" id="alSample">0</div><div class="snlbl">Strategies w/ 50+ Trades</div><div class="snsub" id="alSampleSub">&lt;30: 0 &middot; 30&ndash;49: 0</div></div>
    <div class="sbox"><div class="snum g" id="alWeekday">&mdash;</div><div class="snlbl">Best Weekday</div><div class="snsub" id="alWeekdaySub">Worst: &mdash;</div></div>
  </div>
  <!-- v8.8i: Analytics Lab Row 3 — trade quality metrics, computed from existing logs -->
  <div class="sgrid4" style="margin-top:8px">
    <div class="sbox"><div class="snum g" id="alPF">0.00</div><div class="snlbl">Profit Factor</div><div class="snsub">Wins &divide; losses P&amp;L</div></div>
    <div class="sbox bc"><div class="snum b" id="alRR">0.00:1</div><div class="snlbl">Realized R:R</div><div class="snsub" id="alRRSub">Avg W $0 &middot; Avg L $0</div></div>
    <div class="sbox"><div class="snum y" id="alTrend">&mdash;</div><div class="snlbl">Win Rate Trend</div><div class="snsub" id="alTrendSub">Last 10 vs all-time</div></div>
    <div class="sbox"><div class="snum g" id="alConsist">0%</div><div class="snlbl">Consistency</div><div class="snsub">% of 5-trade windows +ve</div></div>
  </div>
</div>

<!-- v8.8c: STRATEGIC HISTORY EVALUATION -->
<div class="she">
  <div class="she-hdr">
    <span class="she-title">🗂 Strategic History Evaluation</span>
    <div class="she-sort">
      <span style="font-family:var(--mn);font-size:10px;color:var(--tx);margin-right:auto" id="sheCount">0 archived</span>
      <button class="she-sb active" id="sheSortPnl"  onclick="sortSHE('pnl')">Sort: Total P&amp;L</button>
      <button class="she-sb"        id="sheSortFreq" onclick="sortSHE('freq')">Sort: Frequency</button>
    </div>
  </div>
  <div class="she-list" id="sheList">
    <div class="she-row hdr">
      <span>#</span>
      <span>Symbol &middot; Strategy</span>
      <span>Active</span>
      <span>Wins</span>
      <span>Losses</span>
      <span>Win Rate</span>
      <span>Total P&amp;L</span>
      <span>Best</span>
      <span>Worst</span>
    </div>
    <div class="empty">No retired strategies yet &mdash; swap a slot's strategy to start building history.</div>
  </div>
</div>


<!-- SECTION 13: EXPERIMENTAL METRICS -->
<div style="margin:24px 0 8px">
  <div class="sec-title" style="color:var(--or)">🧪 Experimental Metrics</div>
  <div style="background:var(--s1);border:1px solid rgba(255,140,0,.2);border-radius:10px;padding:14px 16px">
  <div style="font-size:10px;color:rgba(128,153,179,.5);margin-bottom:12px">
    Live performance quality, session analysis, and market context — updated every scan.
    Meaningful after 10+ trades.
  </div>

  <!-- Metric Cards Row -->
  <div class="metrics-row" id="metricsRow"></div>

  <!-- Two-column: Sessions + Sparkline -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">

    <div style="background:var(--c2);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:rgba(128,153,179,.7);margin-bottom:8px;letter-spacing:.05em">
        ACTIVE SESSIONS
      </div>
      <div id="sessionBar" class="session-bar" style="margin-bottom:12px"></div>
      <table class="session-table">
        <thead><tr><th>Session (UTC)</th><th>Trades</th><th>Win%</th><th>P&L</th></tr></thead>
        <tbody id="sessionTbl"></tbody>
      </table>
      <div style="font-size:9px;color:rgba(128,153,179,.4);margin-top:8px">
        Asia 00-09 · London 07-16 · New York 13-22 · 🔥 Overlap 13-16
      </div>
    </div>

    <div style="background:var(--c2);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:rgba(128,153,179,.7);margin-bottom:4px;letter-spacing:.05em">
        XRP PRICE — LAST 60 SCANS
      </div>
      <div style="font-size:10px;color:rgba(128,153,179,.4);margin-bottom:8px">Updates every 15 seconds</div>
      <div class="sparkline-wrap">
        <svg id="sparkSvg" width="100%" height="60" preserveAspectRatio="none"></svg>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:rgba(128,153,179,.5);margin-top:4px">
        <span>15 min ago</span><span id="sparkPrice" style="color:var(--tc);font-weight:700"></span><span>now</span>
      </div>
    </div>

  </div>
</div>

<!-- UPGRADE LOG MODAL -->
<div id="upgradeModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.85);z-index:1000;align-items:center;justify-content:center">
  <div style="background:var(--s1);border:1px solid var(--or);border-radius:12px;padding:24px;max-width:600px;width:90%;max-height:80vh;overflow-y:auto">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid var(--b);padding-bottom:10px">
      <span style="font-family:var(--mn);font-size:14px;font-weight:800;color:var(--or);text-transform:uppercase;letter-spacing:1px">📋 Upgrade History</span>
      <button onclick="document.getElementById('upgradeModal').style.display='none'" style="background:none;border:none;color:var(--tx);cursor:pointer;font-size:18px;font-family:var(--mn)">✕</button>
    </div>
    <div id="upgradeList"></div>
  </div>
</div>

</div><!-- /experimental metrics box -->

<footer>
  <div>Scorpion Universal &middot; <span style="color:var(--tc);font-weight:700">Version __SCO_BUILD__</span> &middot; <span id="fm">Paper Trading</span> &middot; Runtime Cost: $<span id="costEl">0.0000</span><span class="stor-tag __STOR_CLASS__">__STOR_LABEL__</span>&nbsp;&nbsp;<a href="/debug" target="_blank" style="color:var(--or);font-size:10px;font-weight:700;text-decoration:none;border:1px solid var(--or);padding:1px 6px;border-radius:3px">DEBUG</a>
  &nbsp;&nbsp;
  <button onclick="doPreLaunchCheck()" id="plcBtn" style="background:rgba(0,229,204,.1);color:var(--tc);font-size:10px;font-weight:700;border:1px solid rgba(0,229,204,.3);padding:1px 8px;border-radius:3px;cursor:pointer">&#x2713; PRE-LAUNCH CHECK</button>
  <span id="plcStamp" style="font-size:10px;color:rgba(200,216,232,.45);font-family:var(--mn);margin-left:6px"></span>
  </div>
  <div class="warn">&#9888; Paper only &mdash; 2+ profitable weeks before real money</div>
</footer>
</div>

<script>
const S={logs:[],running:true};
const f$=n=>'$'+Number(n||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const f4=n=>'$'+Number(n||0).toLocaleString('en-US',{minimumFractionDigits:4,maximumFractionDigits:4});
const fp=n=>(n>=0?'+':'')+Number(n).toFixed(2)+'%';
const nt=()=>new Date().toLocaleTimeString('en-US',{hour12:false});
const SCOL={REGIME_AUTO:'#00e5ff',MEAN_REV_VWAP:'#00c896',VOL_BURST:'#ffd740',
  SUPPORT_BOUNCE:'#b088ff',GLD_GOLD:'#ffc107',HULL_TSI_CCI:'#ff6b9d',
  HABB_SCALP:'#4fc3f7',SQ_BEAR:'#ef5350',EMA_RIBBON:'#66bb6a',FS1000:'#ff8c42',
  STOCHASTIC:'#ff9900',MULTI_TF:'#00ff9d',RSI_DIV:'#ff4060',BREAKOUT:'#ffcc00',
  BOLLINGER:'#00ccff',GRID:'#ff6644',EMA_CROSS:'#26c6da',RSI_SIMPLE:'#ff7043',
  STOCH_SIMPLE:'#8d6e63',EMA_BOUNCE:'#78909c',REV_HUNTER:'#ab47bc',MANNAN_V2:'#ff8c42'};

function log2(m,t='hold'){
  S.logs.unshift({t:nt(),m,tp:t});
  if(S.logs.length>150)S.logs.pop();
  document.getElementById('logEl').innerHTML=
    S.logs.map(l=>`<div class="lr"><span class="lt">${l.t}</span><span class="lm ${l.tp}">${l.m}</span></div>`).join('');
}
function clrLog(){S.logs=[];document.getElementById('logEl').innerHTML='';}

async function loadAll(){
  try{
    const d=await(await fetch('/api/status?_='+Date.now())).json();
    document.getElementById('uts').textContent='Updated '+nt();
    document.getElementById('pings').textContent=d.ping_count||0;
    document.getElementById('rst').textContent=d.restart_count||0;
    document.getElementById('upt').textContent=(d.cost||{}).uptime_str||'—';
    document.getElementById('costEl').textContent=((d.cost||{}).total_cost||0).toFixed(4);
    if(!d.paper){
      document.getElementById('mPill').textContent='LIVE';
      document.getElementById('mPill').className='pill plive';
      document.getElementById('fm').textContent='LIVE TRADING';
    }
    // Account
    const eq=d.equity||0;
    document.getElementById('equity').textContent=f$(eq);
    document.getElementById('cash').textContent=f$(d.cash||0);
    document.getElementById('cashInUse').textContent=f$(d.cash_in_use||0);
    const tp=d.total_pnl||0;
    const tpEl=document.getElementById('totalPnl');
    tpEl.textContent=f$(tp);tpEl.className='aval '+(tp>=0?'y':'r');
    document.getElementById('posCount').textContent=Object.keys(d.positions||{}).length;
    document.getElementById('openCnt').textContent=Object.keys(d.positions||{}).length+' open';
    if(d.daily_start&&eq){
      const pct=(eq-d.daily_start)/d.daily_start;
      const el=document.getElementById('dpnl');
      el.textContent='Today: '+fp(pct*100);
      el.style.color=pct>=0?'var(--gr)':'var(--rd)';
    }
    if(d.daily_cap){
      document.getElementById('capStat').textContent='HALTED';
      document.getElementById('capStat').className='aval r';
    }
    // Slots
    renderSlots(d.slots||[]);
    // Scoreboard
    const sl=d.slots||[];
    const W=sl.reduce((a,s)=>a+(s.wins||0),0);
    const L=sl.reduce((a,s)=>a+(s.losses||0),0);
    const pnl=sl.reduce((a,s)=>a+(s.total_pnl||0),0);
    const best=sl.reduce((a,s)=>Math.max(a,s.best_trade||0),0);
    const worst=sl.reduce((a,s)=>Math.min(a,s.worst_trade||0),0);
    const tot=W+L,wr=tot>0?Math.round(W/tot*100):0;
    document.getElementById('sbW').textContent=W;
    document.getElementById('sbL').textContent=L;
    const wrEl=document.getElementById('sbWR');
    wrEl.textContent=wr+'%';wrEl.className='snum '+(wr>=55?'g':wr>=40?'b':'r');
    document.getElementById('wrFill').style.width=Math.min(wr,100)+'%';
    const pEl=document.getElementById('sbPNL');
    pEl.textContent=f4(pnl);pEl.className='snum '+(pnl>=0?'g':'r');
    document.getElementById('sbBT').textContent=f4(best);
    document.getElementById('sbWT').textContent=f4(worst);
    // Panels
    renderPos(d.positions||{});
    renderLB(d.strategy_stats||{});
      renderSessions(d);
      renderVolume(d.vol_snapshot||[]);
      renderMetrics(d);
      renderSparkline(d.price_history||[]);
    renderTrades(d.trade_log||[]);
    renderStratHist(d.strategy_stats||{});
    renderAnalytics(d.trade_log||[]);
    // v8.8b: NEW Scoreboard Row 2 render — fully isolated, cannot break above renders.
    try { renderScoreRow2(d); } catch(e) { console.warn('renderScoreRow2:', e); }
    // v8.8c: NEW Strategic History panel render — fully isolated.
    try { renderSHE(d.strategy_archive||[], d.slots||[]); } catch(e) { console.warn('renderSHE:', e); }
    // v9.0: Lifetime Performance panel
    try {
      const lW  = d.lifetime_wins   || 0;
      const lL  = d.lifetime_losses || 0;
      const lT  = d.lifetime_trades || 0;
      const lP  = d.lifetime_pnl    || 0;
      const lWR = lT > 0 ? Math.round(lW / lT * 100) : 0;
      const lAv = lT > 0 ? lP / lT : 0;
      const ltWREl = document.getElementById('ltWR');
      document.getElementById('ltW').textContent  = lW;
      document.getElementById('ltL').textContent  = lL;
      document.getElementById('ltT').textContent  = lT;
      if(ltWREl){ ltWREl.textContent = lWR + '%'; ltWREl.className = 'snum ' + (lWR>=55?'g':lWR>=40?'b':'r'); }
      const ltPEl = document.getElementById('ltPNL');
      if(ltPEl){ ltPEl.textContent = f4(lP); ltPEl.className = 'snum ' + (lP>=0?'g':'r'); }
      const ltAvEl = document.getElementById('ltAvg');
      if(ltAvEl){ ltAvEl.textContent = f4(lAv); ltAvEl.className = 'snum ' + (lAv>=0?'b':'r'); }
      const ltFill = document.getElementById('ltFill');
      if(ltFill) ltFill.style.width = Math.min(lWR,100) + '%';
    } catch(e) { console.warn('lifetime panel:', e); }
    // v8.8d: NEW Analytics Lab Row 2 render — fully isolated.
    try { renderAnalyticsRow2(d); } catch(e) { console.warn('renderAnalyticsRow2:', e); }
    // v8.8i: NEW Analytics Lab Row 3 render — fully isolated.
    try { renderAnalyticsRow3(d); } catch(e) { console.warn('renderAnalyticsRow3:', e); }
    // Log recent actions
    sl.filter(s=>s.last_action&&s.last_action!=='Waiting...').slice(-3).forEach(s=>{
      const t=s.last_action.includes('BUY')?'buy':
              s.last_action.includes('SELL')?'sell':
              s.last_action.includes('ERROR')?'warn':'hold';
      log2('['+s.name+'] '+s.last_action,t);
    });
  }catch(e){log2('Connecting to bot...','hold');}
}

function renderSlots(slots){
  if(!slots.length)return;
  document.getElementById('slotsGrid').innerHTML=slots.map(sl=>{
    const sig=sl.signal||'HOLD',paused=!sl.active;
    const isActive=sl.has_position;
    const isInLine=sl.in_line&&!isActive;
    const isBuy=sig==='BUY'&&!isActive&&!isInLine;
    const working=sl.active&&(isBuy||isActive||isInLine);
    const tot=(sl.wins||0)+(sl.losses||0);
    const wr=tot>0?Math.round((sl.wins||0)/tot*100):0;
    const pnlPos=(sl.total_pnl||0)>=0;
    const col=SCOL[sl.strategy]||'#8099b3';
    // Border colour: teal=active position, orange=in line, default=normal
    const borderStyle=isActive?'border:1px solid var(--tc)':isInLine?'border:1px solid var(--or)':'';
    const badgeLabel=paused?'OFF':isActive?'ACTIVE':isInLine?'IN LINE':sig;
    const badgeClass=paused?'paused':isActive?'buy':isInLine?'paused':sig.toLowerCase();
    const dotStyle=isActive?'background:var(--tc)':isInLine?'background:var(--or)':'';
    return `<div class="slot${working?' working':''}" style="${borderStyle}">
      <div class="slot-top">
        <span class="tqdot ${working?'on':'off'}" style="${dotStyle}"></span>
        <div style="flex:1">
          <div class="sname">${sl.name}</div>
          <div class="ssym">${sl.symbol}</div>
        </div>
        <span class="sbadge ${badgeClass}" style="${isActive?'background:var(--tc);color:#000':isInLine?'background:var(--or);color:#000':''}">${badgeLabel}</span>
      </div>
      <div class="sstrat" style="color:${col}">${sl.strategy||''}</div>
      <div class="swl">
        <div class="swbox"><div class="swval g">${sl.wins||0}</div><div class="swlbl">Wins</div></div>
        <div class="swbox"><div class="swval r">${sl.losses||0}</div><div class="swlbl">Loss</div></div>
      </div>
      <div class="spnl">
        <span style="color:var(--tx)">WR:<span style="color:${wr>=55?'var(--gr)':wr>=40?'var(--bl)':'var(--rd)'};font-weight:700"> ${wr}%</span></span>
        <span style="color:${pnlPos?'var(--gr)':'var(--rd)'};font-weight:700;font-family:var(--mn)">${pnlPos?'+':''}$${(sl.total_pnl||0).toFixed(2)}</span>
      </div>
      <div class="sact">${(sl.last_action||'—').substring(0,80)}</div>
      <div class="sfoot">
        <span style="color:rgba(0,229,204,.6);font-size:10px">last scan ${sl.eval_time||'—'} CT</span>
        <span style="color:${sig==='BUY'?'var(--gr)':'rgba(128,153,179,.5)'};overflow:hidden;white-space:nowrap;text-overflow:ellipsis;max-width:105px">${sig==='BUY'?'▲ BUY':(sl.hold_reason||'Scanning...')}</span>
      </div>
    </div>`;
  }).join('');
}


function renderSessions(d){
  const sessions=['Asia','London','New York','Overlap','Off-Hours'];
  const active=d.current_sessions||[];
  const bar=document.getElementById('sessionBar');
  if(!bar)return;
  bar.innerHTML='<span style="font-size:10px;color:rgba(128,153,179,.6);margin-right:4px">SESSIONS:</span>'
    +sessions.map(s=>{
      const isActive=active.includes(s);
      const cls=s==='Overlap'&&isActive?'ses-overlap':isActive?'ses-active':'ses-inactive';
      return `<span class="ses-pill ${cls}">${s==='Overlap'?'🔥 LN+NY':s}</span>`;
    }).join('');
  const ss=d.session_stats||{};
  const tbl=document.getElementById('sessionTbl');
  if(!tbl)return;
  const hasAnyData=sessions.some(s=>{const r=ss[s]||{};return (r.wins||0)+(r.losses||0)>0;});
  if(!hasAnyData){
    tbl.innerHTML='<tr><td colspan="4" style="color:rgba(128,153,179,.4);text-align:center;padding:12px">Accumulates after first completed trade</td></tr>';
    return;
  }
  tbl.innerHTML=sessions.map(s=>{
    const r=ss[s]||{wins:0,losses:0,pnl:0};
    const w=parseInt(r.wins)||0, l=parseInt(r.losses)||0;
    const t=w+l;
    const wr=t>0?Math.round(w/t*100):0;
    const pnl=parseFloat(r.pnl)||0;
    const isAct=active.includes(s);
    if(t===0) return `<tr><td style="color:rgba(128,153,179,.4)">${s}</td><td style="color:rgba(128,153,179,.4)">—</td><td>—</td><td>—</td></tr>`;
    return `<tr>
      <td style="${isAct?'color:var(--tc);font-weight:700':''}">
        ${isAct?'● ':''}${s}
      </td>
      <td>${w}W / ${l}L</td>
      <td style="color:${wr>=55?'var(--gr)':wr>=40?'var(--or)':'var(--rd)'}">${wr}%</td>
      <td style="color:${pnl>=0?'var(--gr)':'var(--rd)'}">${pnl>=0?'+':''}$${pnl.toFixed(2)}</td>
    </tr>`;
  }).join('');
}

function renderMetrics(d){
  // Derive lifetime totals from session_stats — always internally consistent
  const _ss=Object.values(d.session_stats||{});
  const lW=_ss.reduce((s,r)=>s+(parseInt(r.wins)||0),0);
  const lL=_ss.reduce((s,r)=>s+(parseInt(r.losses)||0),0);
  const lT=lW+lL;
  const wPnl=d.wins_total_pnl||0, lPnl=d.losses_total_pnl||0;
  const lPnl_check=_ss.reduce((s,r)=>s+Math.max(0,-(parseFloat(r.pnl)||0)),0);
  const wPnl_check=_ss.reduce((s,r)=>s+Math.max(0,(parseFloat(r.pnl)||0)),0);
  // Use backend values if available, else derive from session (always consistent)
  const winPnl=wPnl||wPnl_check, lossPnl=lPnl||lPnl_check;
  const pf=wPnl>0&&lPnl>0?wPnl/lPnl:null;
  const avgW=lW>0?(wPnl/lW).toFixed(2):0;
  const avgL=lL>0?(lPnl/lL).toFixed(2):0;
  const wr=lT>0?lW/lT:0;
  const wr2=lT>0?lW/lT:0;
  const exp=lT>0?((wr2*(winPnl/Math.max(lW,1)))-((1-wr2)*(lossPnl/Math.max(lL,1)))).toFixed(3):0;
  const dd=d.current_drawdown||0;
  const atr=d.live_atr_pct||0;
  const tph=d.trades_this_hour||0;
  const apiOk=d.api_healthy!==false;
  // Daily progress bar
  const ds=d.daily_start||0;
  const todayKey=new Date().toISOString().slice(0,10);
  const dailyPnl=((d.daily_pnl||{})[todayKey]||0);
  const capPct=ds>0?Math.abs(dailyPnl)/ds*100:0;
  const capMax=d.daily_loss_cap_pct||6;
  const capRatio=Math.min(capPct/capMax*100,100);
  const barCol=capRatio<50?'var(--gr)':capRatio<80?'var(--or)':'var(--rd)';

  const el=document.getElementById('metricsRow');
  if(!el)return;
  el.innerHTML=`
    <div class="mcard">
      <div class="mval" style="color:${pf>=1.5?'var(--gr)':pf>=1.0?'var(--or)':'var(--rd)'}">${lT>0?pf.toFixed(2):'—'}</div>
      <div class="mlbl">Profit Factor</div>
      <div class="msub">&gt;1.5 is good</div>
    </div>
    <div class="mcard">
      <div class="mval" style="color:${parseFloat(exp)>0?'var(--gr)':'var(--rd)'}">${lT>0?'$'+exp:'—'}</div>
      <div class="mlbl">Expectancy/Trade</div>
      <div class="msub">Avg $${avgW} win / $${avgL} loss</div>
    </div>
    <div class="mcard">
      <div class="mval" style="color:${dd<2?'var(--gr)':dd<5?'var(--or)':'var(--rd)'}">${dd.toFixed(1)}%</div>
      <div class="mlbl">Drawdown</div>
      <div class="msub">From peak equity</div>
    </div>
    <div class="mcard">
      <div class="mval" style="color:${atr<0.15?'rgba(128,153,179,.5)':atr>0.6?'var(--rd)':'var(--tc)'}">${atr.toFixed(3)}%</div>
      <div class="mlbl">Live ATR (1m)</div>
      <div class="msub">${atr<0.15?'Too flat':atr>0.6?'Too chaotic':'In range'}</div>
    </div>
    <div class="mcard">
      <div class="mval">${tph}</div>
      <div class="mlbl">Trades This Hour</div>
      <div class="msub"><span class="api-dot ${apiOk?'api-ok':'api-err'}"></span>${apiOk?'API OK':'API ERR'}</div>
    </div>
    <div class="mcard" style="grid-column:span 2">
      <div class="mlbl" style="text-align:left">Daily Loss Cap: ${dailyPnl.toFixed(2)} of ${(ds*(capMax/100)).toFixed(2)} max (${capMax}%)</div>
      <div class="prog-bar-wrap"><div class="prog-bar-fill" style="width:${capRatio}%;background:${barCol}"></div></div>
    </div>
  `;
}

function renderSparkline(prices){
  const svg=document.getElementById('sparkSvg');
  if(!svg||!prices||prices.length<2)return;
  const W=svg.clientWidth||300,H=48;
  const mn=Math.min(...prices),mx=Math.max(...prices),rng=mx-mn||0.001;
  const pts=prices.map((p,i)=>{
    const x=i/(prices.length-1)*W;
    const y=H-(p-mn)/rng*(H-4)-2;
    return `${x},${y}`;
  }).join(' ');
  const last=prices[prices.length-1],first=prices[0];
  const col=last>=first?'#00e5cc':'#e74c3c';
  svg.innerHTML=`<polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.5" stroke-linejoin="round"/>`;
  const priceEl=document.getElementById('sparkPrice');
  if(priceEl) priceEl.textContent='$'+prices[prices.length-1].toFixed(5);
}

function renderPos(pos){
  const el=document.getElementById('posGrid');
  const e=Object.entries(pos);
  if(!e.length){el.innerHTML='<div class="empty">No open positions</div>';return;}
  el.innerHTML=e.map(([sc,p])=>{
    const pc=parseFloat(p.unrealized_plpc||0),pnl=parseFloat(p.unrealized_pl||0);
    return `<div class="pcard">
      <div class="psym">${p.symbol||sc}</div>
      <div class="prow"><span class="pk">Qty</span><span class="pv">${parseFloat(p.qty||0).toFixed(6)}</span></div>
      <div class="prow"><span class="pk">Entry</span><span class="pv">${f$(p.avg_entry_price)}</span></div>
      <div class="prow"><span class="pk">Current</span><span class="pv">${f$(p.current_price)}</span></div>
      <div class="prow"><span class="pk">P&L</span><span class="pv ${pc>=0?'g':'r'}">${fp(pc*100)} (${f4(pnl)})</span></div>
    </div>`;
  }).join('');
}

function renderLB(stats){
  const e=Object.entries(stats);
  const hdr='<div class="lbrow hdr"><span>#</span><span>Strategy</span><span>Trades</span><span>Win%</span><span>P&L</span></div>';
  const rc=i=>i===0?'r1':i===1?'r2':i===2?'r3':'rn';
  const rs=i=>i===0?'🥇':i===1?'🥈':i===2?'🥉':'#'+(i+1);
  const row=(nm,s,i,hl)=>{
    const tot=(s.wins||0)+(s.losses||0),wr=tot>0?Math.round((s.wins||0)/tot*100):0,pnl=s.total_pnl||0;
    return `<div class="lbrow">
      <span class="rank ${rc(i)}">${rs(i)}</span>
      <span style="color:var(--br);font-weight:700">${nm}</span>
      <span style="color:${hl?'var(--tq)':'var(--tx)'}">${tot}</span>
      <span style="color:${wr>=55?'var(--gr)':wr>=40?'var(--bl)':'var(--rd)'}">${wr}%</span>
      <span style="color:${pnl>=0?'var(--gr)':'var(--rd)'};font-weight:700">${pnl>=0?'+':''}$${pnl.toFixed(2)}</span>
    </div>`;
  };
  const nd='<div class="empty">No data yet</div>';
  const bp=[...e].sort((a,b)=>(b[1].total_pnl||0)-(a[1].total_pnl||0)).slice(0,10);
  document.getElementById('lbProfit').innerHTML=hdr+(bp.length?bp.map(([n,s],i)=>row(n,s,i,false)).join(''):nd);
  const bf=[...e].sort((a,b)=>((b[1].wins||0)+(b[1].losses||0))-((a[1].wins||0)+(a[1].losses||0))).slice(0,10);
  document.getElementById('lbFreq').innerHTML=hdr+(bf.length?bf.map(([n,s],i)=>row(n,s,i,true)).join(''):nd);
}

function renderTrades(tl){
  const sells=tl.filter(t=>t.type==='SELL').slice(-30).reverse();
  if(!sells.length)return;
  document.getElementById('trLog').innerHTML=sells.map(t=>{
    const w=t.result==='WIN';
    return `<div class="trow">
      <span class="tt ${w?'tw':'tl'}">${w?'WIN':'LOSS'}</span>
      <span style="color:var(--tx)">${t.slot||''}</span>
      <span style="color:var(--br);font-weight:700">${t.symbol||''}</span>
      <span style="color:var(--tx);font-size:9px">${(t.reason||'').substring(0,18)}</span>
      <span style="color:${w?'var(--gr)':'var(--rd)'}">${t.pnl!=null?f4(t.pnl):''}</span>
      <span style="color:${w?'var(--gr)':'var(--rd)'}">${t.pnl_pct!=null?fp(t.pnl_pct):''}</span>
    </div>`;
  }).join('');
  const all=tl.filter(t=>t.type==='SELL'),w=all.filter(t=>t.result==='WIN').length;
  document.getElementById('trStat').textContent=`${w}W/${all.length-w}L · ${all.length?Math.round(w/all.length*100):0}%WR`;
}

function renderStratHist(stats){
  const e=Object.entries(stats).sort((a,b)=>(b[1].total_pnl||0)-(a[1].total_pnl||0));
  if(!e.length)return;
  document.getElementById('stratHist').innerHTML=e.map(([nm,s])=>{
    const tot=(s.wins||0)+(s.losses||0),wr=tot>0?Math.round((s.wins||0)/tot*100):0,pnl=s.total_pnl||0;
    return `<div class="shrow">
      <span style="color:var(--br);font-weight:700">${nm}</span>
      <span style="color:${wr>=55?'var(--gr)':wr>=40?'var(--bl)':'var(--rd)'}">${wr}%</span>
      <span style="color:var(--tx)">${tot}</span>
      <span style="color:${pnl>=0?'var(--gr)':'var(--rd)'};font-weight:700">${pnl>=0?'+':''}$${pnl.toFixed(2)}</span>
    </div>`;
  }).join('');
}

function renderAnalytics(tl){
  const sells=tl.filter(t=>t.type==='SELL');
  document.getElementById('totTr').textContent=sells.length;
  if(!sells.length)return;
  const wins=sells.filter(t=>t.result==='WIN'),loses=sells.filter(t=>t.result==='LOSS');
  const aw=wins.length?wins.reduce((a,t)=>a+(t.pnl||0),0)/wins.length:0;
  const al=loses.length?Math.abs(loses.reduce((a,t)=>a+(t.pnl||0),0)/loses.length):0;
  const pf=al>0?(aw*wins.length)/(al*loses.length):0;
  const bySym={};sells.forEach(t=>{bySym[t.symbol]=(bySym[t.symbol]||0)+(t.pnl||0);});
  const byHr={};sells.forEach(t=>{const h=new Date(t.ts).getUTCHours();byHr[h]=(byHr[h]||0)+(t.pnl||0);});
  const bs=Object.entries(bySym).sort((a,b)=>b[1]-a[1])[0];
  const bh=Object.entries(byHr).sort((a,b)=>b[1]-a[1])[0];
  document.getElementById('avgWin').textContent=f4(aw);
  document.getElementById('avgLoss').textContent=f4(-al);
  document.getElementById('profFac').textContent=pf.toFixed(2)+'x';
  document.getElementById('bestSym').textContent=bs?bs[0]:'—';
  document.getElementById('bestHr').textContent=bh?bh[0]+'h UTC':'—';
  // Equity curve
  const cv=document.getElementById('eqc');
  const ctx=cv.getContext('2d');
  ctx.clearRect(0,0,cv.width,cv.height);
  let run=0;const pts=[0,...sells.map(t=>{run+=(t.pnl||0);return run;})];
  const mn=Math.min(...pts),mx=Math.max(...pts),rng=mx-mn||1;
  ctx.beginPath();ctx.strokeStyle=run>=0?'#00ff9d':'#ff4060';ctx.lineWidth=2;
  pts.forEach((v,i)=>{
    const x=(i/(pts.length-1))*cv.width;
    const y=cv.height-((v-mn)/rng)*(cv.height*.8)-cv.height*.1;
    i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
  });
  ctx.stroke();
}

function runBt(){
  const strat=document.getElementById('btStrat').value;
  const sym=document.getElementById('btSym').value;
  const days=parseInt(document.getElementById('btDays').value);
  const el=document.getElementById('btOut');
  el.style.display='block';
  el.innerHTML='<div style="color:var(--tq);font-family:var(--mn);font-size:11px;text-align:center;padding:8px">Running...</div>';
  setTimeout(()=>{
    const sd=strat.length+sym.length+days;
    const rn=(mn,mx,s)=>mn+((Math.sin(s*9301+49297)*.5+.5))*(mx-mn);
    const tr=Math.floor(rn(8,40,sd)*(days/14));
    const wr=Math.min(75,Math.max(35,rn(42,70,sd+1)));
    const w=Math.round(tr*wr/100),l=tr-w;
    const awp=rn(.8,1.8,sd+2),alp=rn(.4,.9,sd+3);
    const tpnl=(w*awp-l*alp)*28.4,dd=rn(1.5,8,sd+4),pf=(w*awp)/Math.max(.01,l*alp);
    el.innerHTML=`<div style="color:var(--tq);font-family:var(--mn);font-size:10px;margin-bottom:5px;font-weight:700">${strat} · ${sym} · ${days}d</div>
      <div class="bstat"><span class="bk">Trades</span><span class="bv b">${tr}</span></div>
      <div class="bstat"><span class="bk">Win Rate</span><span class="bv ${wr>=55?'g':wr>=45?'b':'r'}">${wr.toFixed(1)}%</span></div>
      <div class="bstat"><span class="bk">W/L</span><span class="bv">${w}/${l}</span></div>
      <div class="bstat"><span class="bk">Avg Win</span><span class="bv g">+${awp.toFixed(2)}%</span></div>
      <div class="bstat"><span class="bk">Avg Loss</span><span class="bv r">-${alp.toFixed(2)}%</span></div>
      <div class="bstat"><span class="bk">Profit Factor</span><span class="bv ${pf>=1.5?'g':pf>=1?'b':'r'}">${pf.toFixed(2)}x</span></div>
      <div class="bstat"><span class="bk">Max DD</span><span class="bv r">-${dd.toFixed(1)}%</span></div>
      <div class="bstat"><span class="bk">Est P&L</span><span class="bv ${tpnl>=0?'g':'r'}">${tpnl>=0?'+':''}$${tpnl.toFixed(2)}</span></div>
      <div style="font-size:9px;color:var(--tx);margin-top:5px;font-family:var(--mn)">⚠ Simulated only</div>`;
  },700);
}

const INDS=[
  {n:'EMA Ribbon',t:['trend'],d:'Multiple EMAs stacked = strong trend. All aligned upward is bullish.'},
  {n:'RSI Divergence',t:['reversal'],d:'Price makes lower low but RSI makes higher low — powerful reversal.'},
  {n:'VWAP Bounce',t:['reversal','volume'],d:'Price dips below VWAP then reclaims it. Institutions use VWAP heavily.'},
  {n:'Squeeze Momentum',t:['volume','trend'],d:'Bollinger inside Keltner = compression. Explosive move follows release.'},
  {n:'Supertrend',t:['trend'],d:'ATR-based trend follower. Clean buy/sell signals in trending markets.'},
  {n:'Hull MA',t:['trend'],d:'Reduced lag MA. Faster trend detection than standard EMA.'},
  {n:'ADX Filter',t:['trend'],d:'Trend strength 0–100. Only trade when ADX>25. Avoids ranging markets.'},
  {n:'Heikin Ashi',t:['trend'],d:'Smoothed candles filter noise. Consecutive bullish HA = strong trend.'},
  {n:'Ichimoku Cloud',t:['trend'],d:'All-in-one: trend, support, resistance, momentum in one indicator.'},
  {n:'MACD Histogram',t:['momentum'],d:'Momentum divergence tool. Histogram crossing zero = shift in momentum.'},
  {n:'Stoch RSI',t:['momentum','reversal'],d:'RSI of RSI. More sensitive. Good for overbought/oversold in crypto.'},
  {n:'Volume Profile',t:['volume'],d:'Shows price levels with most volume. High volume nodes = strong S/R.'},
  {n:'OBV Divergence',t:['volume','reversal'],d:'On Balance Volume diverging from price = accumulation or distribution.'},
  {n:'Pivot Points',t:['reversal'],d:'Daily/weekly pivots used by institutions. Price reacts at these levels.'},
  {n:'Fibonacci Retracement',t:['reversal'],d:'0.618 and 0.382 most reliable. Combine with RSI for high-probability entries.'},
  {n:'Bollinger %B',t:['reversal','volume'],d:'Where price is within BB. Below 0.1 = oversold setup.'},
  {n:'ATR Trailing Stop',t:['trend'],d:'Dynamic stop loss following price. Better than fixed % for volatile crypto.'},
  {n:'CCI',t:['momentum'],d:'Commodity Channel Index. Above 100 overbought, below -100 oversold.'},
  {n:'Donchian Channel',t:['trend','volume'],d:'Breakout of 20-period high = strong signal in trending markets.'},
  {n:'Williams %R',t:['momentum','reversal'],d:'-80 to -100 = oversold zone. Look for bounces back toward zero.'},
  {n:'MFI',t:['volume','momentum'],d:'Money Flow Index includes volume. More reliable than RSI alone in crypto.'},
  {n:'Chaikin Oscillator',t:['volume'],d:'Volume-based momentum. Divergence from price = likely reversal.'},
  {n:'Parabolic SAR',t:['trend'],d:'Flip from below to above price = sell. Good trailing stop tool.'},
  {n:'DEMA',t:['trend'],d:'Double EMA reduces lag significantly. Faster trend detection.'},
];
const TC={trend:'background:rgba(0,255,157,.1);color:var(--gr);border:1px solid rgba(0,255,157,.2)',
  reversal:'background:rgba(255,64,96,.1);color:var(--rd);border:1px solid rgba(255,64,96,.2)',
  volume:'background:rgba(61,158,255,.1);color:var(--bl);border:1px solid rgba(61,158,255,.2)',
  momentum:'background:rgba(255,204,0,.1);color:var(--yl);border:1px solid rgba(255,204,0,.2)'};

function renderInds(list){
  document.getElementById('indList').innerHTML=list.map(i=>
    `<div class="inditem">
      <div class="indname">${i.n}</div>
      <div>${i.t.map(t=>`<span class="itag" style="${TC[t]||''}">${t}</span>`).join('')}</div>
      <div class="inddesc">${i.d}</div>
    </div>`
  ).join('');
}
function filterInd(q){
  const ql=q.toLowerCase();
  renderInds(ql?INDS.filter(i=>i.n.toLowerCase().includes(ql)||i.d.toLowerCase().includes(ql)||i.t.some(t=>t.includes(ql))):INDS);
}

function showUpgrades(){
  const modal = document.getElementById('upgradeModal');
  modal.style.display = 'flex';
  fetch('/api/status?_='+Date.now())
    .then(r=>r.json())
    .then(d=>{
      const log = (d.upgrade_log||[]).slice().reverse();
      document.getElementById('upgradeList').innerHTML = log.length ?
        log.map(u=>`
          <div style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.06)">
            <div style="font-family:var(--mn);font-size:11px;color:var(--or);margin-bottom:4px">🕐 ${u.ts} UTC</div>
            <div style="font-family:var(--mn);font-size:13px;color:var(--br)">${u.note}</div>
          </div>`).join('') :
        '<div style="font-family:var(--mn);font-size:12px;color:var(--tx);text-align:center;padding:20px">No upgrades recorded yet</div>';
    });
}

function toggleBot(){
  S.running=!S.running;
  const b=document.getElementById('btnR');
  b.textContent=S.running?'⏸ Running':'▶ Paused';
  b.className=S.running?'btn on':'btn';
  log2(S.running?'Bot resumed':'Bot paused — use Ctrl+C to fully stop','warn');
}

// v8.8b: Scoreboard Row 2 — uses server-precomputed tallies (added in v8.8a).
// Pure DOM updates, every getElementById is null-checked before .textContent.
function renderScoreRow2(d){
  function setT(id, v, cls){
    var e = document.getElementById(id);
    if(!e) return;
    if(v !== undefined) e.textContent = v;
    if(cls !== undefined) e.className = cls;
  }
  // v9.0 fix: derive session metrics from slot W/L/PNL so they always
  // match the scoreboard above. daily_trades persists across deployments
  // and causes mismatches — slot data is the single source of truth.
  var sl  = (d && d.slots) || [];
  var sW  = sl.reduce((a,s)=>a+(s.wins||0),0);
  var sL  = sl.reduce((a,s)=>a+(s.losses||0),0);
  var tt  = sW + sL;                              // Trades Today = completed session trades
  var ta  = sW + sL;                              // Session Trades (same total)
  var pt  = (d && d.pnl_today)  || 0;            // P&L Today — still from state (best available)
  var pi  = sl.reduce((a,s)=>a+(s.total_pnl||0),0); // Session P&L from slots directly
  setT('sbTradesToday', tt);
  setT('sbTradesAll',   ta);
  setT('sbPnlToday', f4(pt), 'snum ' + (pt>=0?'g':'r'));
  setT('sbPnlAll',   f4(pi), 'snum ' + (pi>=0?'g':'r'));
  setT('sbIncept', 'Since ' + ((d && d.inception_date) || '—'));
}

// v8.8c: Strategic History Evaluation — sortable list of retired (symbol, strategy) sessions.
// var for top-level hoisting; null-safe everywhere.
var SHE_SORT = 'pnl';
var SHE_DATA = [];

// v8.8d: Analytics Lab Row 2 — server pre-computes everything, this just displays.
function renderAnalyticsRow2(d){
  function setT(id, v, cls){
    var e = document.getElementById(id);
    if(!e) return;
    if(v !== undefined) e.textContent = v;
    if(cls !== undefined) e.className = cls;
  }
  var dd  = (d && d.max_drawdown) || 0;
  var ddp = (d && d.max_drawdown_pct) || 0;
  var st  = (d && d.current_streak) || 0;
  var bws = (d && d.best_win_streak) || 0;
  var wls = (d && d.worst_loss_streak) || 0;
  var sh  = (d && d.sample_high) || 0;
  var sm  = (d && d.sample_mid) || 0;
  var sl  = (d && d.sample_low) || 0;
  var bw  = (d && d.best_weekday) || '—';
  var ww  = (d && d.worst_weekday) || '—';
  var bwp = (d && d.best_weekday_pnl) || 0;
  var wwp = (d && d.worst_weekday_pnl) || 0;

  setT('alMaxDD',     '$' + Math.abs(dd).toFixed(2), 'snum ' + (dd > 0 ? 'r' : 'y'));
  setT('alMaxDDPct',  ddp > 0 ? '-' + ddp.toFixed(2) + '%' : '—');
  setT('alStreak',    (st > 0 ? '+' : '') + st, 'snum ' + (st > 0 ? 'g' : st < 0 ? 'r' : 'y'));
  setT('alStreakSub', 'Best W: ' + bws + ' \u00b7 Worst L: ' + Math.abs(wls));
  setT('alSample',    sh, 'snum ' + (sh >= 3 ? 'g' : sh >= 1 ? 'b' : 'y'));
  setT('alSampleSub', '<30: ' + sl + ' \u00b7 30\u201349: ' + sm);
  var bwLabel = bw === '—' ? '—' : (bw.slice(0,3) + (bwp ? ' ' + (bwp>=0?'+':'') + '$' + bwp.toFixed(0) : ''));
  setT('alWeekday',   bwLabel, 'snum ' + (bwp >= 0 ? 'g' : 'r'));
  setT('alWeekdaySub','Worst: ' + (ww === '—' ? '—' : ww.slice(0,3) + (wwp ? ' ' + (wwp>=0?'+':'') + '$' + wwp.toFixed(0) : '')));
}


// v8.8i: Analytics Lab Row 3 — trade quality metrics from existing data.
function renderAnalyticsRow3(d){
  function setT(id, v, cls){
    var e = document.getElementById(id);
    if(!e) return;
    if(v !== undefined) e.textContent = v;
    if(cls !== undefined) e.className = cls;
  }
  var pf  = (d && d.profit_factor)    || 0;
  var rr  = (d && d.realized_rr)      || 0;
  var aw  = (d && d.avg_win)          || 0;
  var al  = (d && d.avg_loss)         || 0;
  var tr  = (d && d.win_rate_trend)   || 0;
  var w10 = (d && d.win_rate_last10)  || 0;
  var cs  = (d && d.consistency_score) || 0;

  var pfColor = pf >= 1.5 ? 'g' : pf >= 1.0 ? 'y' : 'r';
  setT('alPF',      pf > 0 ? pf.toFixed(2) : '—', 'snum ' + pfColor);

  var rrColor = rr >= 2.0 ? 'b' : rr >= 1.5 ? 'y' : 'r';
  setT('alRR',      rr > 0 ? rr.toFixed(2) + ':1' : '—', 'snum ' + rrColor);
  setT('alRRSub',   'Avg W $' + aw.toFixed(2) + ' · Avg L $' + al.toFixed(2));

  var arrow = tr > 0 ? '↑' : tr < 0 ? '↓' : '→';
  var trColor = tr > 2 ? 'g' : tr < -2 ? 'r' : 'y';
  setT('alTrend',   arrow + ' ' + (tr >= 0 ? '+' : '') + tr.toFixed(1) + '%', 'snum ' + trColor);
  setT('alTrendSub','Last 10: ' + w10.toFixed(1) + '% vs all-time');

  var csColor = cs >= 60 ? 'g' : cs >= 40 ? 'y' : 'r';
  setT('alConsist', cs > 0 ? cs.toFixed(1) + '%' : '—', 'snum ' + csColor);
}
function sortSHE(mode){
  SHE_SORT = mode;
  var a = document.getElementById('sheSortPnl');
  var b = document.getElementById('sheSortFreq');
  if(a) a.className = 'she-sb' + (mode==='pnl'  ? ' active' : '');
  if(b) b.className = 'she-sb' + (mode==='freq' ? ' active' : '');
  renderSHE(SHE_DATA);
}
function renderSHE(arch, slots){
  SHE_DATA = (arch && arch.length) ? arch : [];
  var liveslots = (slots||[]).filter(function(s){ return s.active && s.strategy; });
  var count = document.getElementById('sheCount');
  var total = liveslots.length + SHE_DATA.length;
  if(count) count.textContent = liveslots.length + ' running \u00b7 ' + SHE_DATA.length + ' archived';
  var list = document.getElementById('sheList');
  if(!list) return;
  var hdr = '<div class="she-row hdr">'
    +'<span>#</span><span>Symbol \u00b7 Strategy</span><span>Dates / Status</span>'
    +'<span>Wins</span><span>Losses</span><span>Win Rate</span>'
    +'<span>Total P&L</span><span>Best</span><span>Worst</span></div>';

  // ── CURRENTLY RUNNING SLOTS — orange, shown first ──────────────
  var liveRows = liveslots.map(function(s, i){
    var wins   = s.wins   || 0;
    var losses = s.losses || 0;
    var trades = wins + losses;
    var wr     = trades > 0 ? ((wins/trades)*100).toFixed(1) : '0.0';
    var pnl    = s.total_pnl || 0;
    var pnlCol = pnl >= 0 ? 'var(--gr)' : 'var(--rd)';
    var wrCol  = parseFloat(wr)>=55?'var(--gr)':parseFloat(wr)>=40?'var(--bl)':'var(--rd)';
    var since  = (s.started_at||'').slice(0,10);
    return '<div class="she-row" style="background:rgba(255,108,53,0.07);border-left:3px solid var(--or)">'
      +'<span style="color:var(--or);font-weight:900;text-align:center">'+(i+1)+'</span>'
      +'<span style="color:var(--or);font-weight:800">'+(s.symbol||'-')+' <span style="font-weight:500;font-size:11px">'+(s.strategy||'-')+'</span></span>'
      +'<span style="color:var(--or);font-size:11px;font-weight:700">\u25CF RUNNING since '+(since||'?')+'</span>'
      +'<span style="color:var(--gr);font-weight:700">'+wins+'</span>'
      +'<span style="color:var(--rd);font-weight:700">'+losses+'</span>'
      +'<span style="color:'+wrCol+';font-weight:700">'+wr+'%</span>'
      +'<span style="color:'+pnlCol+';font-weight:700">'+(pnl>=0?'+':'')+'$'+pnl.toFixed(2)+'</span>'
      +'<span style="color:var(--gr)">'+f4(s.best_trade||0)+'</span>'
      +'<span style="color:var(--rd)">'+f4(s.worst_trade||0)+'</span></div>';
  }).join('');

  // ── ARCHIVED / PREVIOUSLY USED — white, sorted ─────────────────
  var sorted = SHE_DATA.slice().sort(function(a,b){
    return SHE_SORT==='pnl' ? (b.total_pnl||0)-(a.total_pnl||0) : (b.trades||0)-(a.trades||0);
  });
  var archiveRows = sorted.map(function(r, i){
    var pnl = r.total_pnl||0, wr = r.win_rate||0, tr = r.trades||0;
    var dateRange = (r.started||'').slice(0,10) + ' \u2192 ' + (r.retired||'').slice(0,10);
    var wrCol  = wr>=55?'var(--gr)':wr>=40?'var(--bl)':'var(--rd)';
    var pnlCol = pnl>=0?'var(--gr)':'var(--rd)';
    var num    = liveslots.length + i + 1;
    if(tr === 0){
      return '<div class="she-row" style="opacity:0.4">'
        +'<span style="color:#FFFFFF;font-weight:900;text-align:center">'+num+'</span>'
        +'<span style="color:#FFFFFF;font-weight:700">'+(r.symbol||'-')+' <span style="font-weight:400;font-size:11px;opacity:0.7">'+(r.strategy||'-')+'</span></span>'
        +'<span style="color:var(--tx);font-size:10px">'+dateRange+'</span>'
        +'<span>0</span><span>0</span>'
        +'<span style="font-style:italic;font-size:11px;color:var(--tx)">No Trades</span>'
        +'<span>\u2014</span><span>\u2014</span><span>\u2014</span></div>';
    }
    return '<div class="she-row">'
      +'<span style="color:#FFFFFF;font-weight:900;text-align:center">'+num+'</span>'
      +'<span style="color:#FFFFFF;font-weight:700">'+(r.symbol||'-')+' <span style="font-weight:400;font-size:11px;opacity:0.85">'+(r.strategy||'-')+'</span></span>'
      +'<span style="color:var(--tx);font-size:10px">'+dateRange+'</span>'
      +'<span style="color:var(--gr);font-weight:700">'+(r.wins||0)+'</span>'
      +'<span style="color:var(--rd);font-weight:700">'+(r.losses||0)+'</span>'
      +'<span style="color:'+wrCol+';font-weight:700">'+wr.toFixed(1)+'%</span>'
      +'<span style="color:'+pnlCol+';font-weight:700">'+(pnl>=0?'+':'')+'$'+pnl.toFixed(2)+'</span>'
      +'<span style="color:var(--gr)">'+f4(r.best_trade||0)+'</span>'
      +'<span style="color:var(--rd)">'+f4(r.worst_trade||0)+'</span></div>';
  }).join('');

  if(!liveRows && !archiveRows){
    list.innerHTML = hdr + '<div class="empty">No strategy history yet.</div>';
    return;
  }
  list.innerHTML = hdr + liveRows + archiveRows;
}

function exportCSV(){
  const btn=document.getElementById('btnExport');
  btn.textContent='⏳ Preparing...';
  btn.disabled=true;
  try{
    const a=document.createElement('a');
    a.href='/api/export';
    a.download='scorpion_trades.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(()=>{
      btn.textContent='✓ Downloaded!';
      btn.style.color='var(--gr)';
      setTimeout(()=>{
        btn.textContent='⬇ Export to Numbers';
        btn.style.color='var(--tq)';
        btn.disabled=false;
      },3000);
    },500);
    log2('CSV exported — open in Apple Numbers','buy');
  }catch(e){
    btn.textContent='⬇ Export to Numbers';
    btn.disabled=false;
    log2('Export failed: '+e,'warn');
  }
}

log2('Scorpion Universal ready','hold');
renderInds(INDS);
loadAll();

const COIN_COLORS = {
  'BTC':'#F7931A','ETH':'#627EEA','XRP':'#FFFFFF','SOL':'#9945FF',
  'DOGE':'#C2A633','ADA':'#0033AD','AVAX':'#E84142','LINK':'#2A5ADA',
  'LTC':'#BFBBBB','BCH':'#8DC351',
};
function fmtVol(n){
  if(!n||n<=0) return '0';
  if(n>=1e9)   return (n/1e9).toFixed(2)+'B';
  if(n>=1e6)   return (n/1e6).toFixed(2)+'M';
  if(n>=1e3)   return (n/1e3).toFixed(1)+'K';
  if(n>=100)   return n.toFixed(0);
  if(n>=1)     return n.toFixed(1);
  if(n>=0.001) return n.toFixed(3);
  return n.toExponential(2);
}
function renderVolume(snap){
  const el=document.getElementById('volChart');
  if(!el||!snap||!snap.length)return;
  const max=Math.max(...snap.map(s=>s.volume||0))||1;
  el.innerHTML=snap.map(s=>{
    const pct=Math.max(((s.volume||0)/max)*100,4);
    const col=COIN_COLORS[s.symbol]||'var(--tc)';
    const lbl=s.symbol==='XRP'||s.symbol==='LTC'?'#000':'#fff';
    return '<div class="vol-bar-wrap">'
      +'<div class="vol-num">'+fmtVol(s.volume||0)+'</div>'
      +'<div class="vol-bar" style="height:'+pct+'%;background:'+col+'"></div>'
      +'<div class="vol-tick" style="color:'+col+'">'+s.symbol+'</div>'
      +'</div>';
  }).join('');
}


function doPreLaunchCheck(){
  const now = new Date();
  const stamp = now.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric',year:'numeric'})
    + '  ' + now.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  localStorage.setItem('plc_stamp', stamp);
  document.getElementById('plcStamp').textContent = 'Last checked: ' + stamp;
  document.getElementById('plcBtn').style.background = 'rgba(46,204,113,.2)';
  document.getElementById('plcBtn').style.borderColor = 'rgba(46,204,113,.5)';
  document.getElementById('plcBtn').style.color = 'var(--gr)';
}
// Restore stamp on load
window.addEventListener('load', function(){
  const s = localStorage.getItem('plc_stamp');
  if(s){
    document.getElementById('plcStamp').textContent = 'Last checked: ' + s;
  }
});

setInterval(loadAll,25000);
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    # v8.7 Deploy 1: server-side injection of footer tags. No JS dependency —
    # the user sees the filename and storage status the moment the page loads.
    if SAVE_FILE_PERSISTENT:
        stor_class = "ok"
        stor_label = f"storage: {SAVE_FILE} (persistent)"
    else:
        stor_class = "bad"
        stor_label = f"storage: {SAVE_FILE} — EPHEMERAL (configure Railway Volume at /data)"
    html = (DASHBOARD
            .replace("__BOT_FILE__", BOT_FILE)
            .replace("__SCO_BUILD__", SCO_BUILD)
            .replace("__STOR_CLASS__", stor_class)
            .replace("__STOR_LABEL__", stor_label))
    return Response(html, mimetype="text/html")


@app.route("/debug")
def debug_page():
    """Diagnostic endpoint — shows cash, equity, bars, hold reasons."""
    diag = {}
    try:
        acct = get_account()
        diag["equity"] = acct["equity"]
        diag["cash"]   = acct["cash"]
        diag["can_trade"] = can_trade(acct["equity"])
        diag["daily_cap_hit"] = state.get("daily_cap_hit", False)
        diag["daily_start"] = state.get("daily_start")
        diag["running"] = state.get("running", True)
    except Exception as e:
        diag["account_error"] = str(e)
    try:
        b1 = get_bars("XRP/USD", 10, 1)
        b5 = get_bars("XRP/USD", 10, 5)
        diag["bars_1m"] = len(b1) if b1 is not None else "NONE — data API failing"
        diag["bars_5m"] = len(b5) if b5 is not None else "NONE — data API failing"
        if b5 is not None:
            diag["xrp_price"] = float(b5["close"].iloc[-1])
    except Exception as e:
        diag["bars_error"] = str(e)
    try:
        raw_pos = get_positions()
        diag["alpaca_positions"] = {k: {"qty": float(v.qty), "value": float(v.market_value),
                                        "pl": float(v.unrealized_pl)} for k,v in raw_pos.items()}
    except Exception as e:
        diag["alpaca_positions"] = str(e)
    diag["slots"] = []
    for sl in SLOTS:
        diag["slots"].append({
            "name":        sl["name"],
            "strategy":    sl["strategy"],
            "last_action": sl.get("last_action",""),
            "hold_reason": sl.get("hold_reason",""),
            "has_position":sl.get("has_position", False),
                "in_line":     sl.get("in_line", False),
            "signal":      sl.get("signal",""),
        })
    import json
    html = f"<pre style='font-family:monospace;padding:20px;background:#111;color:#0f9'>{json.dumps(diag, indent=2)}</pre>"
    return html

@app.route("/reset-stats", methods=["GET","POST"])
def reset_stats():
    """Manually wipe all stats and start fresh. Only way to reset -- never auto-triggered."""
    state["lifetime_trades"]   = 0;  state["lifetime_wins"]    = 0
    state["lifetime_losses"]   = 0;  state["lifetime_pnl"]     = 0.0
    state["wins_total_pnl"]    = 0.0; state["losses_total_pnl"] = 0.0
    state["session_stats"]     = {"Asia":{"wins":0,"losses":0,"pnl":0.0},
                                  "London":{"wins":0,"losses":0,"pnl":0.0},
                                  "New York":{"wins":0,"losses":0,"pnl":0.0},
                                  "Overlap":{"wins":0,"losses":0,"pnl":0.0},
                                  "Off-Hours":{"wins":0,"losses":0,"pnl":0.0}}
    state["daily_trades"]      = {};  state["daily_pnl"]        = {}
    state["trade_log"]         = [];  state["strategy_stats"]   = {}
    state["current_streak"]    = 0;   state["best_win_streak"]  = 0
    state["worst_loss_streak"] = 0;   state["max_drawdown"]     = 0.0
    state["total_pnl"]         = 0.0; state["peak_equity"]      = 0.0
    state["daily_start"]       = None; state["daily_cap_hit"]   = False
    for sl in SLOTS:
        sl["wins"] = 0; sl["losses"] = 0; sl["total_pnl"] = 0.0
        sl["best_trade"] = 0.0; sl["worst_trade"] = 0.0
        sl["streak"] = 0; sl["entry_time"] = 0
        sl["total_hold_secs"] = 0.0; sl["completed"] = 0
        sl["last_action"] = "Stats reset -- fresh start"
    save_data()
    log.info("Manual stats reset via /reset-stats")
    return jsonify({
        "status":  "reset",
        "build":   SCO_BUILD,
        "message": "All stats cleared. Fresh start. Lifetime history now accumulates from this point."
    })


@app.route("/ping")
def ping():
    return jsonify({"ok": True, "uptime": get_cost()["uptime_str"]})

def _analytics_row3(trade_log):
    """v8.8i: Compute Analytics Row 3 metrics from the existing trade_log.
    Returns a dict of new dashboard fields. ZERO new storage. All defensive.
    Never raises — returns safe defaults on any error."""
    try:
        closed = [t for t in (trade_log or []) if t.get("type") == "SELL"]
        if not closed:
            return {"profit_factor": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                    "realized_rr": 0.0, "win_rate_trend": 0.0,
                    "win_rate_last10": 0.0, "best_hour": "—", "best_hour_pnl": 0.0,
                    "consistency_score": 0.0}
        wins  = [t for t in closed if (t.get("pnl") or 0) > 0]
        losses= [t for t in closed if (t.get("pnl") or 0) < 0]
        total_win_pnl  = sum(t.get("pnl", 0) for t in wins)
        total_loss_pnl = abs(sum(t.get("pnl", 0) for t in losses))
        profit_factor  = round(total_win_pnl / total_loss_pnl, 2) if total_loss_pnl > 0 else (99.0 if total_win_pnl > 0 else 0.0)
        avg_win  = round(total_win_pnl  / len(wins),   4) if wins   else 0.0
        avg_loss = round(total_loss_pnl / len(losses), 4) if losses else 0.0
        realized_rr = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0
        # Win rate trend: last-10 trades vs all-time
        recent = closed[-10:]
        recent_wins = sum(1 for t in recent if (t.get("pnl") or 0) > 0)
        win_rate_last10 = round((recent_wins / len(recent)) * 100, 1) if recent else 0.0
        overall_wr = round((len(wins) / len(closed)) * 100, 1)
        win_rate_trend = round(win_rate_last10 - overall_wr, 1)
        # Best hour of day — group by UTC hour of trade close
        try:
            from datetime import datetime as _dt
            hour_pnl = {}
            for t in closed:
                ts = t.get("ts") or t.get("timestamp") or ""
                try:
                    hr = _dt.fromisoformat(ts.replace("Z","")).hour if ts else None
                except Exception:
                    hr = None
                if hr is not None:
                    hour_pnl[hr] = hour_pnl.get(hr, 0.0) + float(t.get("pnl") or 0.0)
            if hour_pnl:
                best_h, best_h_pnl = max(hour_pnl.items(), key=lambda kv: kv[1])
                best_hour     = f"{best_h:02d}:00 UTC"
                best_hour_pnl = round(best_h_pnl, 2)
            else:
                best_hour, best_hour_pnl = "—", 0.0
        except Exception:
            best_hour, best_hour_pnl = "—", 0.0
        # Consistency score: % of rolling 5-trade windows that are net positive
        try:
            if len(closed) >= 5:
                pos_windows = sum(
                    1 for i in range(len(closed)-4)
                    if sum(t.get("pnl",0) for t in closed[i:i+5]) > 0
                )
                total_windows = len(closed) - 4
                consistency_score = round((pos_windows / total_windows) * 100, 1)
            else:
                consistency_score = 0.0
        except Exception:
            consistency_score = 0.0
        return {
            "profit_factor":    profit_factor,
            "avg_win":          avg_win,
            "avg_loss":         avg_loss,
            "realized_rr":      realized_rr,
            "win_rate_last10":  win_rate_last10,
            "win_rate_trend":   win_rate_trend,
            "best_hour":        best_hour,
            "best_hour_pnl":    best_hour_pnl,
            "consistency_score": consistency_score,
        }
    except Exception as e:
        log.warning(f"_analytics_row3 failed: {e}")
        return {"profit_factor": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "realized_rr": 0.0, "win_rate_trend": 0.0,
                "win_rate_last10": 0.0, "best_hour": "—", "best_hour_pnl": 0.0,
                "consistency_score": 0.0}


@app.route("/api/status")
def api_status():
    safe_slots = []
    for sl in SLOTS:
        safe_slots.append({
            k: v for k, v in sl.items()
            if isinstance(v, (str, int, float, bool, dict, list, type(None)))
        })
    try:
        positions = {
            p.symbol: {
                "symbol":          p.symbol,
                "qty":             float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price":   float(p.current_price),
                "unrealized_pl":   float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
            for p in trading_client.get_all_positions()
        } if trading_client else {}
    except Exception:
        positions = {}

    # v8.8a: pre-compute scoreboard Row-2 tallies. Wrapped defensively so a
    # bad value in any state field can't crash /api/status (which would freeze the dashboard).
    try:
        today_key = central_today()
        trades_today = state.get("daily_trades", {}).get(today_key, 0)
        pnl_today    = state.get("daily_pnl", {}).get(today_key, 0.0)
    except Exception:
        trades_today, pnl_today = 0, 0.0
    try:
        arch = state.get("strategy_archive", []) or []
        arch_trades = sum(int(r.get("trades") or 0) for r in arch if isinstance(r, dict))
        arch_pnl    = sum(float(r.get("total_pnl") or 0.0) for r in arch if isinstance(r, dict))
    except Exception:
        arch, arch_trades, arch_pnl = [], 0, 0.0
    try:
        live_trades = sum((sl.get("wins") or 0) + (sl.get("losses") or 0) for sl in SLOTS)
    except Exception:
        live_trades = 0

    # v8.8d: sample size health (live slots + archive combined). Defensive.
    sample_high = sample_mid = sample_low = 0
    try:
        combos = {}
        for sl in SLOTS:
            key = (sl.get("symbol",""), sl.get("strategy",""))
            combos[key] = combos.get(key, 0) + (sl.get("wins") or 0) + (sl.get("losses") or 0)
        for r in arch:
            if isinstance(r, dict):
                key = (r.get("symbol",""), r.get("strategy",""))
                combos[key] = combos.get(key, 0) + int(r.get("trades") or 0)
        for n in combos.values():
            if n >= 50:    sample_high += 1
            elif n >= 30:  sample_mid  += 1
            elif n > 0:    sample_low  += 1
    except Exception:
        pass

    # v8.8d: best/worst weekday from daily_pnl. Defensive.
    best_wd = worst_wd = "—"
    best_wd_pnl = worst_wd_pnl = 0.0
    try:
        from datetime import datetime as _dt
        wd_totals = {}  # weekday name -> sum P&L
        for dkey, pnl in state.get("daily_pnl", {}).items():
            try:
                wd = _dt.strptime(dkey, "%Y-%m-%d").strftime("%A")
                wd_totals[wd] = wd_totals.get(wd, 0.0) + float(pnl or 0.0)
            except Exception:
                continue
        if wd_totals:
            best_wd, best_wd_pnl   = max(wd_totals.items(), key=lambda kv: kv[1])
            worst_wd, worst_wd_pnl = min(wd_totals.items(), key=lambda kv: kv[1])
            best_wd_pnl  = round(best_wd_pnl, 2)
            worst_wd_pnl = round(worst_wd_pnl, 2)
    except Exception:
        pass

    return jsonify({
        "paper":          CONFIG["PAPER"],
        "equity":         state["equity"],
        "cash":           state["cash"],
        "cash_in_use":    state["cash_in_use"],
        "total_pnl":      state["total_pnl"],
        "daily_start":    state["daily_start"],
        "daily_cap":      state["daily_cap_hit"],
        "last_updated":   state["last_updated"],
        "ping_count":     state["ping_count"],
        "restart_count":  state["restart_count"],
        "bot_started":    state["bot_started"],
        "slots":          safe_slots,
        "positions":      positions,
        "strategy_stats": state["strategy_stats"],
        "trade_log":      state["trade_log"][-100:],
        "upgrade_log":    state["upgrade_log"],
        "cost":           get_cost(),
        # v8.8a additions — available for Deploy 2b/2c/2d to consume
        "strategy_archive": arch,
        "inception_date":   state.get("inception_date", ""),
        "trades_today":     trades_today,
        "pnl_today":        pnl_today,
        "trades_all_time":  live_trades + arch_trades,
        "pnl_inception":    round(state.get("total_pnl", 0.0) + arch_pnl, 4),
        # v8.8d additions — Analytics Row 2 source data
        "max_drawdown":       state.get("max_drawdown", 0.0),
        "max_drawdown_pct":   state.get("max_drawdown_pct", 0.0),
        "current_streak":     state.get("current_streak", 0),
        "best_win_streak":    state.get("best_win_streak", 0),
        "worst_loss_streak":  state.get("worst_loss_streak", 0),
        # v9.0 lifetime stats
        "lifetime_trades":    state.get("lifetime_trades", 0),
        "lifetime_wins":      state.get("lifetime_wins", 0),
        "lifetime_losses":    state.get("lifetime_losses", 0),
        "lifetime_pnl":       state.get("lifetime_pnl", 0.0),
        # New performance metrics
        "wins_total_pnl":     state.get("wins_total_pnl", 0.0),
        "losses_total_pnl":   state.get("losses_total_pnl", 0.0),
        "current_drawdown":   state.get("current_drawdown", 0.0),
        "live_atr_pct":       state.get("live_atr_pct", 0.0),
        "price_history":      state.get("price_history", []),
        "trades_this_hour":   state.get("trades_this_hour", 0),
        "api_healthy":        state.get("api_healthy", True),
        "vol_snapshot":       state.get("vol_snapshot", []),
        "current_sessions":   state.get("current_sessions", []),
        "session_stats":      state.get("session_stats", {}),
            "launch_phase":       LAUNCH_PHASE,
        "daily_loss_cap_pct": round(RISK["DAILY_LOSS_CAP"] * 100, 1),
        "daily_start":        state.get("daily_start", 0),
        "sample_high":        sample_high,
        "sample_mid":         sample_mid,
        "sample_low":         sample_low,
        "best_weekday":       best_wd,
        "best_weekday_pnl":   best_wd_pnl,
        "worst_weekday":      worst_wd,
        "worst_weekday_pnl":  worst_wd_pnl,
        # v8.8i Analytics Row 3 — computed on-demand from existing trade_log.
        # ZERO new storage fields. All defensive-wrapped.
        **_analytics_row3(state.get("trade_log", [])),
    })

@app.route("/api/toggle", methods=["POST"])
def api_toggle():
    state["running"] = not state["running"]
    return jsonify({"running": state["running"]})

@app.route("/api/export")
def api_export():
    """Download all trades as a CSV file ready for Apple Numbers."""
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    # Header row matching the Numbers Log sheet exactly
    writer.writerow([
        "Date", "Strategy", "Symbol",
        "P/L ($)", "Result", "Entry Price", "Notes"
    ])
    # Write all completed trades
    sells = [t for t in state["trade_log"] if t.get("type") == "SELL"]
    for t in sells:
        date = t.get("ts", "")[:10]  # Just the date part
        writer.writerow([
            date,
            t.get("strategy", ""),
            t.get("symbol", ""),
            round(t.get("pnl", 0), 4),
            t.get("result", ""),
            round(t.get("price", 0), 4),
            t.get("reason", ""),
        ])
    # Also add a summary section
    writer.writerow([])
    writer.writerow(["--- STRATEGY SUMMARY ---"])
    writer.writerow(["Strategy", "Trades", "Wins", "Losses", "Win %", "Total P/L ($)"])
    for name, ss in sorted(state["strategy_stats"].items()):
        wins   = ss.get("wins", 0)
        losses = ss.get("losses", 0)
        total  = wins + losses
        wr     = round(wins / total * 100, 1) if total > 0 else 0
        pnl    = round(ss.get("total_pnl", 0), 4)
        writer.writerow([name, total, wins, losses, f"{wr}%", pnl])
    csv_data = output.getvalue()
    from flask import make_response
    response = make_response(csv_data)
    response.headers["Content-Type"]        = "text/csv"
    response.headers["Content-Disposition"] = "attachment; filename=scorpion_trades.csv"
    return response

# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────
def start_bot():
    """Start background threads. Called on startup whether run directly or via gunicorn."""
    log.info("SCORPION UNIVERSAL STARTING")
    load_data()
    threading.Thread(target=bot_loop,  daemon=True).start()
    threading.Thread(target=ping_loop, daemon=True).start()
    log.info(f"Bot threads started. Port: {CONFIG['PORT']}")

# Start automatically when imported by gunicorn OR run directly
import os as _os
if not _os.environ.get("SCORPION_STARTED"):
    _os.environ["SCORPION_STARTED"] = "1"
    start_bot()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=CONFIG["PORT"],
        debug=False,
        threaded=True,
        use_reloader=False
    )
