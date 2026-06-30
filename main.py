"""
═══════════════════════════════════════════════════════════════════════
XRPRadar — Iteration 2
Version 3 — Structural Baseline Shell
Iteration-1 look on a WHITE background.
Red Rio Ventures, LLC
═══════════════════════════════════════════════════════════════════════

Freshly written. No code copied from Iteration 1 — the look is matched,
the code is new.

Color rule applied exactly as instructed:
  • Every Iteration-1 accent color and button is KEPT the same
        green #48ff82 · red #ff4060 · gold #ffcc00 · blue #75bcff
        teal  #00e5cc · orange #ff9900
  • Only fonts that were WHITE or GRAY are darkened so they read on white
        gray  #8099b3  → #5a6b7a (readable)
        light #cce0ff  → #1a2a4a (dark navy body text)
        white #ffffff  → #1a2a4a
  • Background is white (page) with light panels.

Shell elements reproduced in their Iteration-1 positions:
  • Header: gradient icon box + title + tagline + sources line (left);
            LIVE dot + status pill + date/time stamp (right)
  • Breaking News bar (placeholder text until the news section is built)
  • Footer: brand | version | updated | uptime + DEBUG button;
            Not-Financial-Advice notice; Feeds | Maintenance | Preflight
            + DETAILS button; copyright
  • Floating Back-to-Top button
═══════════════════════════════════════════════════════════════════════
"""

import os
from datetime import datetime, timezone
from flask import Flask, Response, jsonify

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
APP_VERSION = "3"
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
     Accent colors identical to Iteration 1. White/gray fonts darkened.
     Page background white; panels light. */
  :root {{
    --bg:#ffffff;            /* page background (was #000)           */
    --s1:#f7f9fb;            /* panel fill   (was #0a0a0a)           */
    --s2:#eef2f7;            /* panel fill 2 (was #111)              */
    --b:#d8e0ea;            /* border       (was #1a2030)           */

    /* accent colors — KEPT EXACTLY as Iteration 1 */
    --gr:#48ff82;  --grd:rgba(72,255,130,.12);
    --rd:#ff4060;  --rdd:rgba(255,64,96,.10);
    --yl:#ffcc00;  --yld:rgba(255,204,0,.12);
    --bl:#75bcff;  --bld:rgba(117,188,255,.14);
    --tq:#00e5cc;  --tqd:rgba(0,229,204,.15);
    --or:#ff9900;

    /* fonts that were white/gray — DARKENED to read on white */
    --tx:#5a6b7a;            /* was #8099b3 gray  (labels)          */
    --br:#1a2a4a;            /* was #cce0ff light (body text)       */

    --mn:'Courier New',monospace;
  }}

  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--br);
    font-family:system-ui,sans-serif; font-size:15px;
    min-height:100vh; -webkit-font-smoothing:antialiased;
  }}
  .w {{ max-width:2400px; margin:0 auto; padding:10px 28px; }}

  /* ─── HEADER ─────────────────────────────────────────────────── */
  .hdr {{
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:10px; padding-bottom:8px;
    border-bottom:2px solid var(--bl); flex-wrap:wrap; gap:6px;
  }}
  .logo {{ display:flex; align-items:center; gap:10px; }}
  .icon {{
    width:60px; height:60px; border-radius:10px;
    background:linear-gradient(135deg,#001a3a,#0066cc,#75bcff);
    display:flex; align-items:center; justify-content:center; font-size:36px;
    box-shadow:0 0 16px rgba(117,188,255,.4);
  }}
  .title {{ font-size:22px; font-weight:900; color:var(--br); font-style:italic; }}
  .sub {{ font-size:13px; font-family:var(--mn); color:var(--tx); margin-top:2px; letter-spacing:1px; }}
  .sub.white {{ color:var(--br); }}          /* was #ffffff white → dark */
  .sub.green {{ color:#1e7e34; }}            /* "Sources Live" — green darkened just enough to read */
  .hright {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .dot {{
    width:12px; height:12px; border-radius:50%; background:var(--gr);
    box-shadow:0 0 10px var(--gr); display:inline-block; animation:blink 2s infinite;
  }}
  @keyframes blink {{ 50% {{ opacity:.1; }} }}
  .run-lbl {{ font-size:15px; font-weight:800; font-family:var(--mn); color:#1e7e34; letter-spacing:1px; }}
  .pill {{
    padding:5px 14px; border-radius:20px; font-size:13px; font-family:var(--mn);
    font-weight:700; letter-spacing:1.5px; text-transform:uppercase;
  }}
  .plive {{ background:var(--grd); color:#1e7e34; border:1px solid rgba(72,255,130,.5); }}
  .upd {{ font-family:var(--mn); font-size:13px; color:var(--tx); }}

  /* ─── BREAKING NEWS BAR ──────────────────────────────────────── */
  #breaking {{
    background:var(--s1); border-bottom:2px solid rgba(255,153,0,.5);
    border-top:1px solid var(--b);
    padding:8px 0; display:flex; align-items:center; overflow:hidden;
  }}
  .bkinner {{ max-width:2400px; margin:0 auto; padding:0 28px; display:flex; align-items:center; width:100%; }}
  .bklbl {{
    color:var(--or); font-weight:900; font-size:16px; font-family:var(--mn);
    flex-shrink:0; padding-right:14px; margin-right:14px;
    border-right:2px solid rgba(255,153,0,.6);
    text-transform:uppercase; letter-spacing:.08em;
  }}
  .bkscroll {{ flex:1; overflow:hidden; height:26px; position:relative; display:flex; align-items:center; }}
  .bktext {{ font-size:15px; color:var(--br); font-family:system-ui; font-weight:500; }}

  /* ─── MAIN ───────────────────────────────────────────────────── */
  main {{ max-width:1180px; margin:0 auto; padding:18px 28px 80px; min-height:55vh; }}
  h1.page-title {{ font-size:22px; font-weight:900; font-style:italic; margin:4px 0; color:var(--br); }}
  .subtitle {{ color:var(--tx); font-size:13px; font-family:var(--mn); letter-spacing:1px; margin-bottom:22px; }}
  .note {{
    border:1px solid var(--b); border-radius:8px; background:var(--s1);
    padding:16px 20px; color:var(--tx); font-size:14px;
  }}

  /* ─── FOOTER ─────────────────────────────────────────────────── */
  footer {{
    border-top:2px solid var(--bl); background:var(--bg);
    padding:16px 28px 14px; text-align:center;
    color:var(--tx); font-size:13px; font-family:var(--mn);
  }}
  footer .f-line {{ margin:5px 0; }}
  footer .brand-em {{ color:var(--bl); font-weight:700; font-style:normal; }}
  footer .val {{ color:var(--br); font-weight:700; }}
  .footer-btn {{
    font-family:var(--mn); font-size:13px; font-weight:700; text-decoration:none;
    border-radius:3px; padding:1px 8px; cursor:pointer; margin-left:6px;
  }}
  .debug-btn {{ color:var(--or); border:1px solid var(--or); background:#fff; }}
  .debug-btn:hover {{ background:#fff7ec; }}
  .details-btn {{ color:var(--bl); border:1px solid var(--bl); background:#fff; }}
  .details-btn:hover {{ background:#eef4fb; }}
  .notice {{ color:#a8780a; }}        /* gold notice darkened just enough to read on white */
  .copyright {{
    font-size:12px; color:var(--tx);
    border-top:1px solid var(--b); padding-top:10px; margin-top:10px;
  }}

  /* ─── PREFLIGHT MODAL ────────────────────────────────────────── */
  #pf-modal {{
    display:none; position:fixed; inset:0; background:rgba(0,0,0,.45);
    z-index:9999; align-items:center; justify-content:center; padding:20px;
  }}
  #pf-box {{
    background:#fff; border:1px solid var(--bl); border-radius:10px;
    max-width:580px; width:100%; overflow:hidden; box-shadow:0 8px 30px rgba(0,0,0,.2);
  }}
  #pf-box .pf-head {{
    padding:10px 16px; background:var(--s2); border-bottom:1px solid var(--b);
    display:flex; justify-content:space-between; align-items:center; font-family:var(--mn);
  }}
  #pf-box .pf-head .t {{ color:var(--bl); font-weight:800; font-size:13px; text-transform:uppercase; letter-spacing:1px; }}
  #pf-box .pf-head .x {{
    color:var(--bl); cursor:pointer; font-size:16px; border:1px solid var(--bl);
    width:26px; height:26px; display:flex; align-items:center; justify-content:center; border-radius:4px;
  }}
  #pf-box .pf-body {{ padding:14px 16px; font-family:var(--mn); font-size:13px; }}
  #pf-box .pf-overall {{ font-weight:800; color:{overall_color}; margin-bottom:10px; }}
  .pf-row {{
    display:grid; grid-template-columns:1fr auto;
    grid-template-areas:"label badge" "detail detail"; gap:2px 10px;
    padding:8px 0; border-bottom:1px solid var(--b);
  }}
  .pf-row-label  {{ grid-area:label; font-weight:700; color:var(--br); }}
  .pf-row-badge  {{ grid-area:badge; font-weight:800; }}
  .pf-row-detail {{ grid-area:detail; color:var(--tx); font-size:12px; }}

  /* ─── FLOATING BACK-TO-TOP ───────────────────────────────────── */
  #back-to-top {{
    position:fixed; right:22px; bottom:22px; z-index:200;
    background:var(--bl); color:#06223d; border:none; border-radius:50%;
    width:46px; height:46px; font-size:20px; font-weight:900; cursor:pointer;
    box-shadow:0 2px 8px rgba(0,0,0,.18);
    display:none; align-items:center; justify-content:center; line-height:1;
  }}
  #back-to-top:hover {{ background:#4aa3f0; }}
</style>
</head>
<body>

  <!-- ═══ HEADER ═══ -->
  <div class="w" id="top">
    <div class="hdr">
      <div class="logo">
        <div class="icon">\U0001F6F0\uFE0F</div>
        <div>
          <div class="title">{APP_NAME}</div>
          <div class="sub white" style="letter-spacing:1.5px">{TAGLINE}</div>
          <div class="sub green">\u25CF Baseline Shell Live</div>
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

  <!-- ═══ BREAKING NEWS BAR ═══ -->
  <div id="breaking">
    <div class="bkinner">
      <span class="bklbl">\u26A1 BREAKING NEWS</span>
      <div class="bkscroll">
        <div class="bktext" id="bktext">News feed connects in a later version \u2014 this is the bar in its Iteration-1 position.</div>
      </div>
    </div>
  </div>

  <!-- ═══ MAIN ═══ -->
  <main>
    <h1 class="page-title">{APP_NAME} \u2014 Iteration 2</h1>
    <div class="subtitle">VERSION {APP_VERSION} &middot; STRUCTURAL BASELINE SHELL</div>
    <div class="note">
      Header, Breaking News bar, footer, DEBUG button, and Preflight (with its
      DETAILS modal) are placed as in Iteration 1, on a white background. All
      Iteration-1 accent colors are kept; only white/gray fonts were darkened
      to read on white. Data sections arrive in later versions, two to three
      at a time, each fully verified first.
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
        <div style="margin-top:10px;color:var(--tx);font-size:12px">Last run: {boot_str}</div>
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
    function openPFModal() {{
      var m = document.getElementById('pf-modal'); if (m) m.style.display = 'flex';
    }}
    function closePFModal() {{
      var m = document.getElementById('pf-modal'); if (m) m.style.display = 'none';
    }}
    document.addEventListener('keydown', function (e) {{ if (e.key === 'Escape') closePFModal(); }});

    // Floating back-to-top button
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
