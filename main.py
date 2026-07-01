"""
═══════════════════════════════════════════════════════════════════════
XRPRadar — Iteration 2
Version 4 — Header matched to the approved screenshot, on WHITE
Red Rio Ventures, LLC
═══════════════════════════════════════════════════════════════════════

Freshly written. The look is matched to the screenshot the owner approved;
no code was copied from Iteration 1.

Layout (top to bottom), exactly as in the screenshot:
  ROW 1  Breaking News bar   : ⚡ BREAKING NEWS (gold) | scrolling headline
  ROW 2  Header              :
           Left : blue rounded icon tile w/ satellite, "XRPRadar" (bold
                  italic), "Signals Over Noise 24/7", "● 230 Sources Live"
           Right: ● LIVE, green-bordered "203/230 FEEDS" pill, timestamp
           Blue underline rule beneath the header
  Footer, DEBUG button, Preflight DETAILS modal, floating Back-to-Top.

Color rule (as instructed):
  • Keep every accent color and button — green, gold, blue, red, teal.
  • Only fonts that were WHITE or GRAY are darkened to read on white.
  • Accent colors are the exact screenshot neon values (no darkening).
  • Page background is white.
═══════════════════════════════════════════════════════════════════════
"""

import os
from datetime import datetime, timezone
from flask import Flask, Response, jsonify

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
APP_VERSION   = "4"
APP_NAME      = "XRPRadar"
TAGLINE       = "Signals Over Noise 24/7"
SOURCES_TOTAL = 230          # shown in header; wired to live data in a later version
COPYRIGHT     = "\u00A9\uFE0F Copyright 2026 Red Rio Ventures, LLC. All rights reserved globally."
BOOT_TIME     = datetime.now(timezone.utc)

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
    overall_color = "#1E7E34" if overall == "PASS" else "#C0392B"
    boot_str = BOOT_TIME.strftime("%Y-%m-%d %H:%M:%S UTC")

    modal_rows = ""
    for label, ok, detail in checks:
        c = "#1E7E34" if ok else "#C0392B"
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
  /* ─── PALETTE ──────────────────────────────────────────────────
     Accents identical to the screenshot. White/gray fonts darkened
     for a white background. */
  :root {{
    --bg:#ffffff;                 /* page background (white)             */
    --panel:#f7f9fb;              /* faint panel fill                    */
    --line:#dbe3ec;              /* hairline border                     */

    /* accents kept from the screenshot */
    --green:#48ff82;             /* exact screenshot neon green          */
    --green-soft:rgba(72,255,130,.12);
    --gold:#ffcc00;              /* exact screenshot neon gold           */
    --blue:#75bcff;              /* exact screenshot blue                */
    --blue-tile1:#001a3a;        /* icon tile gradient (unchanged)        */
    --blue-tile2:#0066cc;
    --blue-tile3:#75bcff;
    --orange:#ff9900;            /* exact screenshot orange              */

    /* fonts that were white/gray — darkened */
    --ink:#1a2a4a;               /* was white title / body text           */
    --ink-soft:#5a6b7a;          /* was gray tagline / timestamp / labels */

    --mn:'Courier New',monospace;
  }}

  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:system-ui,sans-serif; font-size:15px;
    min-height:100vh; -webkit-font-smoothing:antialiased;
  }}

  /* ─── ROW 1: BREAKING NEWS BAR (very top) ────────────────────── */
  #breaking {{
    background:var(--panel);
    border-bottom:2px solid rgba(255,204,0,.5);
    padding:9px 0; display:flex; align-items:center; overflow:hidden;
  }}
  .bkinner {{ max-width:2400px; margin:0 auto; padding:0 28px; display:flex; align-items:center; width:100%; gap:16px; }}
  .bklbl {{
    color:var(--gold); font-weight:900; font-size:16px; font-family:var(--mn);
    flex-shrink:0; padding-right:16px; border-right:2px solid rgba(255,204,0,.5);
    text-transform:uppercase; letter-spacing:.08em; white-space:nowrap;
  }}
  .bkscroll {{ flex:1; overflow:hidden; height:24px; display:flex; align-items:center; }}
  .bktext {{ font-size:15px; color:var(--ink-soft); font-family:system-ui; font-weight:500; white-space:nowrap; }}

  /* ─── ROW 2: HEADER ──────────────────────────────────────────── */
  .hdr {{
    max-width:2400px; margin:0 auto; padding:14px 28px 10px;
    display:flex; align-items:flex-start; justify-content:space-between;
    border-bottom:2px solid var(--blue); flex-wrap:wrap; gap:12px;
  }}
  .logo {{ display:flex; align-items:center; gap:14px; }}
  .icon {{
    width:60px; height:60px; border-radius:12px;
    background:linear-gradient(135deg,var(--blue-tile1),var(--blue-tile2),var(--blue-tile3));
    display:flex; align-items:center; justify-content:center; font-size:34px;
    box-shadow:0 2px 10px rgba(117,188,255,.4); flex-shrink:0;
  }}
  .title {{ font-size:26px; font-weight:800; color:var(--ink); font-style:italic; line-height:1.1; }}
  .sub {{ font-size:14px; font-family:var(--mn); color:var(--ink-soft); margin-top:3px; letter-spacing:.5px; }}
  .sub.sources {{ color:var(--green); font-weight:700; }}

  .hright {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap; padding-top:4px; }}
  .live-wrap {{ display:flex; align-items:center; gap:8px; }}
  .dot {{
    width:12px; height:12px; border-radius:50%; background:var(--green);
    box-shadow:0 0 8px rgba(72,255,130,.6); display:inline-block; animation:blink 2s infinite;
  }}
  @keyframes blink {{ 50% {{ opacity:.25; }} }}
  .live-lbl {{ font-size:16px; font-weight:800; font-family:var(--mn); color:var(--ink); letter-spacing:1px; }}
  .feeds-pill {{
    padding:6px 16px; border-radius:20px; font-size:15px; font-family:var(--mn);
    font-weight:700; letter-spacing:1px; color:var(--green);
    background:var(--green-soft); border:1px solid rgba(72,255,130,.5);
  }}
  .stamp {{ font-family:var(--mn); font-size:14px; color:var(--ink-soft); }}

  /* ─── MAIN ───────────────────────────────────────────────────── */
  main {{ max-width:1180px; margin:0 auto; padding:20px 28px 80px; min-height:52vh; }}
  h1.page-title {{ font-size:22px; font-weight:800; font-style:italic; margin:4px 0; color:var(--ink); }}
  .subtitle {{ color:var(--ink-soft); font-size:13px; font-family:var(--mn); letter-spacing:1px; margin-bottom:22px; }}
  .note {{ border:1px solid var(--line); border-radius:8px; background:var(--panel); padding:16px 20px; color:var(--ink-soft); font-size:14px; }}

  /* ─── FOOTER ─────────────────────────────────────────────────── */
  footer {{
    border-top:2px solid var(--blue); background:var(--bg);
    padding:16px 28px 14px; text-align:center;
    color:var(--ink-soft); font-size:13px; font-family:var(--mn);
  }}
  footer .f-line {{ margin:5px 0; }}
  footer .brand-em {{ color:var(--blue); font-weight:700; font-style:normal; }}
  footer .val {{ color:var(--ink); font-weight:700; }}
  .footer-btn {{ font-family:var(--mn); font-size:13px; font-weight:700; text-decoration:none; border-radius:3px; padding:1px 8px; cursor:pointer; margin-left:6px; }}
  .debug-btn {{ color:var(--orange); border:1px solid var(--orange); background:#fff; }}
  .debug-btn:hover {{ background:#fff7ec; }}
  .details-btn {{ color:var(--blue); border:1px solid var(--blue); background:#fff; }}
  .details-btn:hover {{ background:#eef4fb; }}
  .notice {{ color:var(--gold); }}
  .copyright {{ font-size:12px; color:var(--ink-soft); border-top:1px solid var(--line); padding-top:10px; margin-top:10px; }}

  /* ─── PREFLIGHT MODAL ────────────────────────────────────────── */
  #pf-modal {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.45); z-index:9999; align-items:center; justify-content:center; padding:20px; }}
  #pf-box {{ background:#fff; border:1px solid var(--blue); border-radius:10px; max-width:580px; width:100%; overflow:hidden; box-shadow:0 8px 30px rgba(0,0,0,.2); }}
  #pf-box .pf-head {{ padding:10px 16px; background:var(--panel); border-bottom:1px solid var(--line); display:flex; justify-content:space-between; align-items:center; font-family:var(--mn); }}
  #pf-box .pf-head .t {{ color:var(--blue); font-weight:800; font-size:13px; text-transform:uppercase; letter-spacing:1px; }}
  #pf-box .pf-head .x {{ color:var(--blue); cursor:pointer; font-size:16px; border:1px solid var(--blue); width:26px; height:26px; display:flex; align-items:center; justify-content:center; border-radius:4px; }}
  #pf-box .pf-body {{ padding:14px 16px; font-family:var(--mn); font-size:13px; }}
  #pf-box .pf-overall {{ font-weight:800; color:{overall_color}; margin-bottom:10px; }}
  .pf-row {{ display:grid; grid-template-columns:1fr auto; grid-template-areas:"label badge" "detail detail"; gap:2px 10px; padding:8px 0; border-bottom:1px solid var(--line); }}
  .pf-row-label  {{ grid-area:label; font-weight:700; color:var(--ink); }}
  .pf-row-badge  {{ grid-area:badge; font-weight:800; }}
  .pf-row-detail {{ grid-area:detail; color:var(--ink-soft); font-size:12px; }}

  /* ─── FLOATING BACK-TO-TOP ───────────────────────────────────── */
  #back-to-top {{ position:fixed; right:22px; bottom:22px; z-index:200; background:var(--blue); color:#fff; border:none; border-radius:50%; width:46px; height:46px; font-size:20px; font-weight:900; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.18); display:none; align-items:center; justify-content:center; line-height:1; }}
  #back-to-top:hover {{ opacity:.88; }}
</style>
</head>
<body id="top">

  <!-- ═══ ROW 1: BREAKING NEWS BAR (very top, above header) ═══ -->
  <div id="breaking">
    <div class="bkinner">
      <span class="bklbl">\u26A1 BREAKING NEWS</span>
      <div class="bkscroll">
        <div class="bktext" id="bktext">News feed connects in a later version \u2014 bar shown in its Iteration-1 position at the very top.</div>
      </div>
    </div>
  </div>

  <!-- ═══ ROW 2: HEADER ═══ -->
  <div class="hdr">
    <div class="logo">
      <div class="icon">\U0001F6F0\uFE0F</div>
      <div>
        <div class="title">{APP_NAME}</div>
        <div class="sub">{TAGLINE}</div>
        <div class="sub sources">\u25CF {SOURCES_TOTAL} Sources Live</div>
      </div>
    </div>
    <div class="hright">
      <div class="live-wrap">
        <span class="dot"></span>
        <span class="live-lbl">LIVE</span>
      </div>
      <span class="feeds-pill" id="feedPill">0/{SOURCES_TOTAL} FEEDS</span>
      <span class="stamp" id="uts">{boot_str}</span>
    </div>
  </div>

  <!-- ═══ MAIN ═══ -->
  <main>
    <h1 class="page-title">{APP_NAME} \u2014 Iteration 2</h1>
    <div class="subtitle">VERSION {APP_VERSION} &middot; HEADER MATCHED TO SCREENSHOT (WHITE)</div>
    <div class="note">
      The Breaking News bar sits at the very top, above the header, exactly as
      in the screenshot. The header shows the icon tile, title, tagline, sources
      line, LIVE indicator, FEEDS pill, and date/time stamp. Accent colors are
      kept; white and gray fonts were darkened to read on white. Data sections
      arrive in later versions, two to three at a time, each verified first.
    </div>
  </main>

  <!-- ═══ FLOATING RETURN BUTTON ═══ -->
  <button id="back-to-top" title="Back to top" aria-label="Back to top">&#8679;</button>

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
        <div style="margin-top:10px;color:var(--ink-soft);font-size:12px">Last run: {boot_str}</div>
      </div>
    </div>
  </div>

  <script>
    // Live uptime counter in the footer
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

    // Floating back-to-top
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
        "iteration":     2,
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
