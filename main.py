"""
═══════════════════════════════════════════════════════════════════════
XRPRadar — Iteration 2
Version 2 — Structural Baseline Shell (Iteration-1 layout, white theme)
Red Rio Ventures, LLC
═══════════════════════════════════════════════════════════════════════

Fresh, from-scratch rebuild. No code carried over from Iteration 1.
Version 1 reproduces the Iteration-1 LAYOUT and PLACEMENT of the shell
elements, rebuilt cleanly on a white background:

  • Header bar  : icon + title + tagline (left),
                  LIVE dot + status pill + version (right)
  • Footer      : line 1 = brand | version | updated | uptime + DEBUG button
                  line 2 = Not-Financial-Advice notice
                  line 3 = Feeds | Maintenance | Preflight + DETAILS button
                  line 4 = copyright
  • DEBUG button: in the footer, opens /debug
  • Preflight   : status shown in footer; DETAILS button opens a modal
  • Floating Back-to-Top return button
  • White background, dark text, optimized for a 13" laptop screen

No data feeds or external API calls yet — those arrive in later versions.
═══════════════════════════════════════════════════════════════════════
"""

import os
from datetime import datetime, timezone
from flask import Flask, Response, jsonify

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
APP_VERSION = "2"
APP_NAME    = "XRPRadar"
TAGLINE     = "Signals Over Noise 24/7"
COPYRIGHT   = "\u00A9\uFE0F Copyright 2026 Red Rio Ventures, LLC. All rights reserved globally."
BOOT_TIME   = datetime.now(timezone.utc)

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────
# PREFLIGHT SELF-CHECK
# Returns (checks, passed, total, overall). Each check is (label, ok, detail).
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
  :root {{
    --bg:        #ffffff;
    --ink:       #1a2a4a;
    --ink-soft:  #555555;
    --line:      #e2e8f0;
    --accent:    #1a5276;
    --green:     #1e7e34;
    --orange:    #b9770e;
    --panel:     #f7f9fb;
    --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}

  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 15px;
    line-height: 1.5;
  }}

  /* ─── HEADER BAR ─────────────────────────────────────────────── */
  .hdr {{
    position: sticky; top: 0; z-index: 100;
    background: var(--bg);
    border-bottom: 2px solid var(--ink);
    padding: 10px 20px;
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 8px;
  }}
  .logo {{ display: flex; align-items: center; gap: 12px; }}
  .logo .icon {{ font-size: 26px; line-height: 1; }}
  .logo .title {{ font-size: 22px; font-weight: 800; color: var(--ink); letter-spacing: 0.5px; line-height: 1.1; }}
  .logo .sub {{ font-size: 13px; color: var(--ink-soft); letter-spacing: 1px; line-height: 1.3; }}
  .logo .sub.live {{ color: var(--green); font-weight: 700; }}

  .hright {{ display: flex; align-items: center; gap: 10px; font-family: var(--mono); font-size: 12px; }}
  .dot {{
    width: 9px; height: 9px; border-radius: 50%;
    background: var(--green); display: inline-block;
    animation: pulse 2s infinite;
  }}
  @keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(30,126,52,0.45); }}
    70%  {{ box-shadow: 0 0 0 7px rgba(30,126,52,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(30,126,52,0); }}
  }}
  .run-lbl {{ color: var(--green); font-weight: 800; letter-spacing: 1px; }}
  .pill {{ border: 1px solid var(--line); border-radius: 4px; padding: 3px 9px; font-weight: 700; color: var(--accent); }}
  .upd {{ color: var(--ink-soft); }}

  /* ─── MAIN ───────────────────────────────────────────────────── */
  main {{ max-width: 1180px; margin: 0 auto; padding: 24px 20px 80px; min-height: 60vh; }}
  h1.page-title {{ font-size: 26px; font-weight: 800; margin: 4px 0; }}
  .subtitle {{ color: var(--ink-soft); font-size: 14px; margin-bottom: 24px; }}
  .note {{ border: 1px dashed var(--line); border-radius: 8px; padding: 16px 20px; color: var(--ink-soft); font-size: 14px; background: #ffffff; }}

  /* ─── FOOTER ─────────────────────────────────────────────────── */
  footer {{
    border-top: 1px solid var(--line);
    background: var(--bg);
    padding: 16px 20px 14px;
    text-align: center;
    color: var(--ink-soft);
    font-size: 13px;
    font-family: var(--mono);
  }}
  footer .f-line {{ margin: 4px 0; }}
  footer .brand-em {{ color: var(--accent); font-weight: 700; font-style: normal; }}
  footer .val {{ color: var(--ink); font-weight: 700; }}
  .footer-btn {{ font-family: var(--mono); font-size: 13px; font-weight: 700; text-decoration: none; border-radius: 3px; padding: 1px 8px; cursor: pointer; margin-left: 6px; }}
  .debug-btn {{ color: var(--orange); border: 1px solid var(--orange); background: #fff; }}
  .debug-btn:hover {{ background: #fff7ec; }}
  .details-btn {{ color: var(--accent); border: 1px solid var(--accent); background: #fff; }}
  .details-btn:hover {{ background: #eef4f8; }}
  .notice {{ color: #b9770e; }}
  .copyright {{ font-size: 12px; color: var(--ink-soft); border-top: 1px solid var(--line); padding-top: 10px; margin-top: 10px; }}

  /* ─── PREFLIGHT MODAL ────────────────────────────────────────── */
  #pf-modal {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 9999; align-items: center; justify-content: center; padding: 20px; }}
  #pf-box {{ background: #ffffff; border: 1px solid var(--accent); border-radius: 10px; max-width: 580px; width: 100%; overflow: hidden; box-shadow: 0 8px 30px rgba(0,0,0,0.2); }}
  #pf-box .pf-head {{ padding: 10px 16px; background: var(--panel); border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; font-family: var(--mono); }}
  #pf-box .pf-head .t {{ color: var(--accent); font-weight: 800; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
  #pf-box .pf-head .x {{ color: var(--accent); cursor: pointer; font-size: 16px; border: 1px solid var(--accent); width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; border-radius: 4px; }}
  #pf-box .pf-body {{ padding: 14px 16px; font-family: var(--mono); font-size: 13px; }}
  #pf-box .pf-overall {{ font-weight: 800; color: {overall_color}; margin-bottom: 10px; }}
  .pf-row {{ display: grid; grid-template-columns: 1fr auto; grid-template-areas: "label badge" "detail detail"; gap: 2px 10px; padding: 8px 0; border-bottom: 1px solid var(--line); }}
  .pf-row-label  {{ grid-area: label; font-weight: 700; color: var(--ink); }}
  .pf-row-badge  {{ grid-area: badge; font-weight: 800; }}
  .pf-row-detail {{ grid-area: detail; color: var(--ink-soft); font-size: 12px; }}

  /* ─── FLOATING BACK-TO-TOP ───────────────────────────────────── */
  #back-to-top {{ position: fixed; right: 22px; bottom: 22px; z-index: 200; background: var(--ink); color: #fff; border: none; border-radius: 50%; width: 46px; height: 46px; font-size: 20px; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.18); display: none; align-items: center; justify-content: center; line-height: 1; }}
  #back-to-top:hover {{ background: var(--accent); }}
</style>
</head>
<body>

  <!-- ═══ HEADER ═══ -->
  <div class="hdr" id="top">
    <div class="logo">
      <div class="icon">\U0001F6F0\uFE0F</div>
      <div>
        <div class="title">{APP_NAME}</div>
        <div class="sub">{TAGLINE}</div>
        <div class="sub live">\u25CF Baseline Shell Live</div>
      </div>
    </div>
    <div class="hright">
      <span class="dot"></span>
      <span class="run-lbl">LIVE</span>
      <span class="pill" id="statusPill">SHELL OK</span>
      <span class="upd" id="uts">v{APP_VERSION}</span>
    </div>
  </div>

  <!-- ═══ MAIN ═══ -->
  <main>
    <h1 class="page-title">{APP_NAME} \u2014 Iteration 2</h1>
    <div class="subtitle">Version {APP_VERSION} &middot; Structural baseline shell</div>
    <div class="note">
      This is the Version {APP_VERSION} baseline shell. The header, footer,
      DEBUG button, and Preflight (with its DETAILS modal) are placed exactly
      as they were in Iteration 1, rebuilt fresh on a white background. Data
      sections will be added in later versions, two to three at a time, each
      fully verified before moving on.
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
      tick();
      setInterval(tick, 1000);
    }})();

    // Preflight modal
    function openPFModal() {{
      var m = document.getElementById('pf-modal');
      if (m) m.style.display = 'flex';
    }}
    function closePFModal() {{
      var m = document.getElementById('pf-modal');
      if (m) m.style.display = 'none';
    }}
    document.addEventListener('keydown', function (e) {{
      if (e.key === 'Escape') closePFModal();
    }});

    // Floating back-to-top button
    (function () {{
      var btn = document.getElementById('back-to-top');
      if (!btn) return;
      function toggle() {{ btn.style.display = (window.scrollY > 200) ? 'flex' : 'none'; }}
      window.addEventListener('scroll', toggle, {{ passive: true }});
      btn.addEventListener('click', function () {{ window.scrollTo({{ top: 0, behavior: 'smooth' }}); }});
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
