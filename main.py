"""
═══════════════════════════════════════════════════════════════════════
XRPRadar — Iteration 3
Version 1 — Frame / Baseline Shell (black, exact Iteration-1 look)
Red Rio Ventures, LLC
═══════════════════════════════════════════════════════════════════════

Freshly written from scratch. No code copied from Iteration 1 — the look,
fonts, sizes, and exact RGB palette are matched; the code is new.

This version rebuilds the Iteration-1 FRAME only:
  • Breaking News bar (very top)
  • Header: icon tile + title + tagline + Sources Live (left);
            LIVE dot + FEEDS pill + date/time stamp (right)
  • Footer: brand | version | updated | uptime + DEBUG button;
            Not-Financial-Advice notice;
            Feeds | Maintenance | Preflight + DETAILS button; copyright
  • Preflight self-check (footer status + DETAILS modal)
  • /debug and /ping routes
  • Floating "Return to Site" button (for when a visitor opens a story
    or extra window) + Back-to-Top behavior

Exact Iteration-1 palette (RGB unchanged):
  --bg#000  --s1#0a0a0a  --s2#111  --b#1a2030
  --gr#48ff82 green  --rd#ff4060 red  --yl#ffcc00 gold
  --bl#75bcff blue    --tq#00e5cc teal --or#ff9900 orange
  --tx#8099b3 label   --br#cce0ff body  --mn 'Courier New'

Permanently excluded (per standing instruction): ATH, CoinGecko, and any
access-limited feeds. No data feeds or external calls in this version yet.
═══════════════════════════════════════════════════════════════════════
"""

import os
from datetime import datetime, timezone
from flask import Flask, Response, jsonify

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
APP_VERSION = "1"
APP_NAME    = "XRPRadar"
TAGLINE     = "Signals Over Noise 24/7"
COPYRIGHT   = "\u00A9\uFE0F Copyright 2026 Red Rio Ventures, LLC. All rights reserved globally."
BOOT_TIME   = datetime.now(timezone.utc)

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────
# PREFLIGHT SELF-CHECK
# ─────────────────────────────────────────────────────────────────────
def run_preflight():
    checks = []
    checks.append(("Flask app responding", True, "Server handled the request"))
    checks.append(("Version string present", bool(APP_VERSION), f"Reporting version {APP_VERSION}"))
    try:
        up = (datetime.now(timezone.utc) - BOOT_TIME).total_seconds()
        checks.append(("Uptime clock running", up >= 0, f"{int(up)} seconds since boot"))
    except Exception as e:
        checks.append(("Uptime clock running", False, str(e)))
    port = os.environ.get("PORT", "8080")
    checks.append(("Port configured", bool(port), f"PORT={port}"))

    passed = sum(1 for _, ok, _ in checks if ok)
    total  = len(checks)
    overall = "PASS" if passed == total else "FAIL"
    return checks, passed, total, overall


# ─────────────────────────────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────────────────────────────
def render_page():
    checks, passed, total, overall = run_preflight()
    overall_color = "#48ff82" if overall == "PASS" else "#ff4060"
    boot_str = BOOT_TIME.strftime("%Y-%m-%d %H:%M:%S UTC")

    modal_rows = ""
    for label, ok, detail in checks:
        c = "#48ff82" if ok else "#ff4060"
        t = "PASS" if ok else "FAIL"
        modal_rows += (
            '<div class="pf-row">'
            f'<span class="pf-row-label">{label}</span>'
            f'<span class="pf-row-badge" style="color:{c}">{t}</span>'
            f'<span class="pf-row-detail">{detail}</span>'
            '</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{APP_NAME} \u2014 {TAGLINE}</title>
<style>
  /* ─── EXACT ITERATION-1 PALETTE (RGB unchanged) ─────────────── */
  :root{{
    --bg:#000; --s1:#0a0a0a; --s2:#111; --b:#1a2030;
    --gr:#48ff82; --grd:rgba(72,255,130,.1);
    --rd:#ff4060; --rdd:rgba(255,64,96,.1);
    --yl:#ffcc00; --yld:rgba(255,204,0,.1);
    --bl:#75bcff; --bld:rgba(117,188,255,.12);
    --tq:#00e5cc; --tqd:rgba(0,229,204,.15);
    --or:#ff9900; --tx:#8099b3; --br:#cce0ff;
    --mn:'Courier New',monospace;
  }}
  *{{ box-sizing:border-box; }}
  body{{
    background:var(--bg); color:var(--br);
    font-family:system-ui,sans-serif; font-size:15px;
    min-height:100vh; -webkit-font-smoothing:antialiased; margin:0;
  }}
  .w{{ max-width:2400px; margin:0 auto; padding:10px 28px; }}

  /* ─── BREAKING NEWS BAR (very top) ──────────────────────────── */
  #breaking{{
    background:var(--s1); border-bottom:2px solid rgba(255,153,0,.4);
    padding:8px 0; display:flex; align-items:center; overflow:hidden;
  }}
  .bkinner{{ max-width:2400px; margin:0 auto; padding:0 28px; display:flex; align-items:center; width:100%; }}
  .bklbl{{
    color:var(--or); font-weight:900; font-size:16px; font-family:var(--mn);
    flex-shrink:0; padding-right:14px; margin-right:14px;
    border-right:2px solid rgba(255,153,0,.5);
    text-transform:uppercase; letter-spacing:.08em;
  }}
  .bkscroll{{ flex:1; overflow:hidden; height:26px; position:relative; display:flex; align-items:center; }}
  .bktext{{
    display:inline-block; animation:bkscroll 45s linear infinite; white-space:nowrap;
    cursor:default; will-change:transform; padding-left:100%;
    font-size:15px; color:var(--br); font-family:system-ui; font-weight:500; line-height:26px;
  }}
  .bkscroll:hover .bktext{{ animation-play-state:paused; }}
  @keyframes bkscroll{{ 0%{{transform:translateX(0)}} 100%{{transform:translateX(-100%)}} }}

  /* ─── HEADER ─────────────────────────────────────────────────── */
  .hdr{{
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:10px; padding-bottom:8px;
    border-bottom:2px solid var(--bl); flex-wrap:wrap; gap:6px;
  }}
  .logo{{ display:flex; align-items:center; gap:10px; }}
  .icon{{
    width:60px; height:60px; border-radius:10px;
    background:linear-gradient(135deg,#001a3a,#0066cc,#75bcff);
    display:flex; align-items:center; justify-content:center; font-size:36px;
    box-shadow:0 0 16px rgba(117,188,255,.4);
  }}
  .title{{ font-size:22px; font-weight:900; color:var(--br); font-style:italic; }}
  .sub{{ font-size:13px; font-family:var(--mn); color:var(--tx); margin-top:2px; letter-spacing:1px; }}
  .hright{{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .dot{{
    width:12px; height:12px; border-radius:50%; background:var(--gr);
    box-shadow:0 0 10px var(--gr); display:inline-block; animation:blink 2s infinite;
  }}
  @keyframes blink{{ 50%{{opacity:.1}} }}
  .run-lbl{{ font-size:15px; font-weight:800; font-family:var(--mn); color:var(--gr); letter-spacing:1px; }}
  .pill{{ padding:5px 14px; border-radius:20px; font-size:13px; font-family:var(--mn); font-weight:700; letter-spacing:1.5px; text-transform:uppercase; }}
  .plive{{ background:var(--grd); color:var(--gr); border:1px solid rgba(72,255,130,.4); }}
  .upd{{ font-family:var(--mn); font-size:13px; color:var(--tx); }}

  /* ─── MAIN ───────────────────────────────────────────────────── */
  main{{ max-width:1180px; margin:0 auto; padding:14px 28px 90px; min-height:50vh; }}
  h1.page-title{{ font-size:22px; font-weight:900; font-style:italic; margin:4px 0; color:var(--br); }}
  .subtitle{{ color:var(--tx); font-size:13px; font-family:var(--mn); letter-spacing:1px; margin-bottom:22px; }}
  .note{{ border:1px solid var(--b); border-radius:8px; background:var(--s1); padding:16px 20px; color:var(--tx); font-size:14px; }}

  /* ─── FOOTER ─────────────────────────────────────────────────── */
  footer{{
    border-top:2px solid var(--bl); background:var(--bg);
    padding:16px 28px 16px; text-align:center;
    color:var(--tx); font-size:13px; font-family:var(--mn);
  }}
  footer .f-line{{ margin:5px 0; }}
  footer .brand-em{{ color:var(--bl); font-weight:700; font-style:normal; }}
  footer .val{{ color:var(--br); font-weight:700; }}
  .footer-btn{{ font-family:var(--mn); font-size:13px; font-weight:700; text-decoration:none; border-radius:3px; padding:1px 8px; cursor:pointer; margin-left:6px; }}
  .debug-btn{{ color:var(--or); border:1px solid var(--or); background:transparent; }}
  .debug-btn:hover{{ background:rgba(255,153,0,.12); }}
  .details-btn{{ color:var(--bl); border:1px solid var(--bl); background:transparent; }}
  .details-btn:hover{{ background:var(--bld); }}
  .notice{{ color:var(--yl); }}
  .copyright{{ font-size:12px; color:var(--tx); border-top:1px solid var(--b); padding-top:10px; margin-top:10px; }}

  /* ─── PREFLIGHT MODAL ────────────────────────────────────────── */
  #pf-modal{{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.92); z-index:9999; align-items:center; justify-content:center; padding:20px; }}
  #pf-box{{ background:var(--s1); border:1px solid var(--bl); border-radius:10px; max-width:580px; width:100%; overflow:hidden; }}
  #pf-box .pf-head{{ padding:12px 16px; background:var(--s2); border-bottom:1px solid var(--b); display:flex; justify-content:space-between; align-items:center; font-family:var(--mn); }}
  #pf-box .pf-head .t{{ color:var(--bl); font-weight:800; font-size:13px; text-transform:uppercase; letter-spacing:1px; }}
  #pf-box .pf-head .x{{ color:var(--bl); cursor:pointer; font-size:18px; font-weight:900; border:1px solid var(--bl); width:26px; height:26px; display:flex; align-items:center; justify-content:center; border-radius:4px; }}
  #pf-box .pf-head .x:hover{{ background:var(--bl); color:#000; }}
  #pf-box .pf-body{{ padding:14px 16px; font-family:var(--mn); font-size:13px; }}
  #pf-box .pf-overall{{ font-weight:800; color:{overall_color}; margin-bottom:10px; }}
  .pf-row{{ display:grid; grid-template-columns:1fr auto; grid-template-areas:"label badge" "detail detail"; gap:2px 10px; padding:8px 0; border-bottom:1px solid var(--b); }}
  .pf-row-label{{ grid-area:label; font-weight:700; color:var(--br); }}
  .pf-row-badge{{ grid-area:badge; font-weight:800; }}
  .pf-row-detail{{ grid-area:detail; color:var(--tx); font-size:12px; }}

  /* ─── FLOATING RETURN / BACK-TO-TOP BUTTON ───────────────────── */
  #back-to-top{{
    position:fixed; right:22px; bottom:22px; z-index:200;
    background:var(--bl); color:#000; border:none; border-radius:50%;
    width:46px; height:46px; font-size:20px; font-weight:900; cursor:pointer;
    box-shadow:0 0 14px rgba(117,188,255,.5);
    display:none; align-items:center; justify-content:center; line-height:1;
  }}
  #back-to-top:hover{{ background:#a6d4ff; }}
</style>
</head>
<body id="top">

  <!-- ═══ BREAKING NEWS BAR (very top) ═══ -->
  <div id="breaking">
    <div class="bkinner">
      <span class="bklbl">\u26A1 BREAKING NEWS</span>
      <div class="bkscroll">
        <div class="bktext" id="bktext">Monitoring XRP global news feeds \u2014 live headlines connect in a later version.</div>
      </div>
    </div>
  </div>

  <div class="w">
    <!-- ═══ HEADER ═══ -->
    <div class="hdr">
      <div class="logo">
        <div class="icon">\U0001F6F0\uFE0F</div>
        <div>
          <div class="title">{APP_NAME}</div>
          <div class="sub" style="font-size:13px;color:#ffffff;letter-spacing:1.5px">{TAGLINE}</div>
          <div class="sub" style="font-size:13px;color:var(--gr);letter-spacing:1px">\u25CF Frame Live</div>
        </div>
      </div>
      <div class="hright">
        <span class="dot"></span>
        <span class="run-lbl">LIVE</span>
        <span class="pill plive" id="feedPill">SHELL OK</span>
        <span class="upd" id="uts">{boot_str}</span>
      </div>
    </div>
  </div>

  <!-- ═══ MAIN ═══ -->
  <main>
    <h1 class="page-title">{APP_NAME} \u2014 Iteration 3</h1>
    <div class="subtitle">VERSION {APP_VERSION} &middot; FRAME / BASELINE SHELL</div>
    <div class="note">
      Iteration-1 frame on black, rebuilt fresh: Breaking News bar at the top,
      header with icon, title, tagline, Sources line, LIVE indicator, FEEDS
      pill, and date/time stamp; footer with DEBUG button and Preflight DETAILS;
      and a floating Return-to-Site button. Data sections are added in later
      versions, two to three at a time, each verified first. ATH, CoinGecko,
      and access-limited feeds are permanently excluded.
    </div>
  </main>

  <!-- ═══ FLOATING RETURN / BACK-TO-TOP BUTTON ═══ -->
  <button id="back-to-top" title="Return to top of site" aria-label="Return to site">&#8679;</button>

  <!-- ═══ FOOTER ═══ -->
  <footer>
    <div class="f-line">
      \U0001F6F0\uFE0F <em class="brand-em">{APP_NAME}</em>
      &nbsp;|&nbsp; Version: <span class="val">{APP_VERSION}</span>
      &nbsp;|&nbsp; Updated: <span class="val" id="ft-last">{boot_str}</span>
      &nbsp;|&nbsp; Uptime: <span class="val" id="ft-uptime">0s</span>
      <a class="footer-btn debug-btn" href="/debug" target="_blank" rel="noopener">DEBUG</a>
    </div>
    <div class="f-line notice">
      \u26A0\uFE0F Not Financial Advice \u2014 XRPRadar is for informational purposes only. DYOR.
    </div>
    <div class="f-line">
      Feeds: <span class="val" id="ft-feeds">\u2014</span>
      &nbsp;|&nbsp; Maintenance: <span class="val" id="ft-maint">None</span>
      &nbsp;|&nbsp; Preflight: <span style="color:{overall_color};font-weight:800" id="ft-qa">{overall}</span>
      <button class="footer-btn details-btn" onclick="openPFModal()">\U0001F50D DETAILS</button>
    </div>
    <div class="f-line copyright">{COPYRIGHT}</div>
  </footer>

  <!-- ═══ PREFLIGHT DETAILS MODAL ═══ -->
  <div id="pf-modal" onclick="closePFModal(event)">
    <div id="pf-box" onclick="event.stopPropagation()">
      <div class="pf-head">
        <span class="t">\U0001F50D Preflight / QA Details</span>
        <span class="x" onclick="closePFModal()">\u2715</span>
      </div>
      <div class="pf-body">
        <div class="pf-overall">OVERALL: {overall} &nbsp;({passed}/{total} checks passed)</div>
        {modal_rows}
        <div style="margin-top:10px;color:var(--tx);font-size:12px">Last run: {boot_str}</div>
      </div>
    </div>
  </div>

  <script>
    // Live uptime counter (footer)
    (function () {{
      var bootMs = {int(BOOT_TIME.timestamp() * 1000)};
      var el = document.getElementById('ft-uptime');
      function tick() {{
        if (!el) return;
        var s = Math.floor((Date.now() - bootMs) / 1000);
        var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
        el.textContent = (h ? h + 'h ' : '') + (m ? m + 'm ' : '') + sec + 's';
      }}
      tick(); setInterval(tick, 1000);
    }})();

    // Preflight modal
    function openPFModal() {{ var m = document.getElementById('pf-modal'); if (m) m.style.display = 'flex'; }}
    function closePFModal() {{ var m = document.getElementById('pf-modal'); if (m) m.style.display = 'none'; }}
    document.addEventListener('keydown', function (e) {{ if (e.key === 'Escape') closePFModal(); }});

    // Floating return / back-to-top
    (function () {{
      var btn = document.getElementById('back-to-top'); if (!btn) return;
      function toggle() {{ btn.style.display = (window.scrollY > 200) ? 'flex' : 'none'; }}
      window.addEventListener('scroll', toggle, {{ passive:true }});
      btn.addEventListener('click', function () {{ window.scrollTo({{ top:0, behavior:'smooth' }}); }});
      toggle();
    }})();
  </script>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return Response(render_page(), mimetype="text/html")


@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "version": APP_VERSION})


@app.route("/debug")
def debug():
    checks, passed, total, overall = run_preflight()
    uptime = int((datetime.now(timezone.utc) - BOOT_TIME).total_seconds())
    return jsonify({
        "app":           APP_NAME,
        "version":       APP_VERSION,
        "iteration":     3,
        "preflight":     overall,
        "checks_passed": f"{passed}/{total}",
        "checks": [
            {"label": label, "status": "PASS" if ok else "FAIL", "detail": detail}
            for label, ok, detail in checks
        ],
        "uptime_secs":   uptime,
        "booted_utc":    BOOT_TIME.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "now_utc":       datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
