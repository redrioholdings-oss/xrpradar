"""
═══════════════════════════════════════════════════════════════════════
XRPRadar — Iteration 2
Version 1 — Structural Baseline Shell
Red Rio Ventures, LLC
═══════════════════════════════════════════════════════════════════════

This is a fresh, from-scratch rebuild. No code is carried over from
Iteration 1. Version 1 establishes the structural shell only:

  • Header (branded, fixed)
  • Footer (branded, fixed)
  • Preflight self-check panel (PASS / FAIL)
  • /debug diagnostic endpoint + on-page Debug button
  • Floating "Back to Top / Home" return button
  • White background, dark text, optimized for a 13" laptop screen

No data feeds, no price logic, no external API calls yet. Those arrive
in later versions, section by section, each fully verified before we
move on.
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
COPYRIGHT   = "© Copyright 2026 Red Rio Ventures, LLC. All rights reserved globally."
BOOT_TIME   = datetime.now(timezone.utc)

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────
# PREFLIGHT SELF-CHECK
# Runs server-side checks and returns a list of (label, ok, detail).
# Version 1 only checks the basics that exist so far.
# ─────────────────────────────────────────────────────────────────────
def run_preflight():
    checks = []

    # 1. App is responding
    checks.append(("Flask app responding", True, "Server handled the request"))

    # 2. Version string is set
    checks.append((
        "Version string present",
        bool(APP_VERSION),
        f"Reporting version {APP_VERSION}"
    ))

    # 3. Uptime is measurable
    try:
        up = (datetime.now(timezone.utc) - BOOT_TIME).total_seconds()
        checks.append(("Uptime clock running", up >= 0, f"{int(up)} seconds since boot"))
    except Exception as e:
        checks.append(("Uptime clock running", False, str(e)))

    # 4. Port is configured
    port = os.environ.get("PORT", "8080")
    checks.append(("Port configured", bool(port), f"PORT={port}"))

    passed = sum(1 for _, ok, _ in checks if ok)
    total  = len(checks)
    overall = "PASS" if passed == total else "FAIL"
    return checks, passed, total, overall


# ─────────────────────────────────────────────────────────────────────
# PAGE  (single full HTML document, served as one string)
# ─────────────────────────────────────────────────────────────────────
def render_page():
    checks, passed, total, overall = run_preflight()

    # Build the preflight rows
    rows = ""
    for label, ok, detail in checks:
        badge_color = "#1E7E34" if ok else "#C0392B"
        badge_text  = "PASS" if ok else "FAIL"
        rows += (
            '<tr>'
            f'<td class="pf-label">{label}</td>'
            f'<td class="pf-badge" style="color:{badge_color}">{badge_text}</td>'
            f'<td class="pf-detail">{detail}</td>'
            '</tr>'
        )

    overall_color = "#1E7E34" if overall == "PASS" else "#C0392B"
    boot_str = BOOT_TIME.strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{APP_NAME} — v{APP_VERSION}</title>
<style>
  /* ─── Design tokens ─────────────────────────────────────────────
     White background, dark text. Tuned for a 13" laptop (~1280-1440px).
     System font stack = zero font download = fastest possible load. */
  :root {{
    --bg:        #ffffff;
    --ink:       #1a2a4a;   /* primary dark navy text */
    --ink-soft:  #555555;   /* secondary grey text   */
    --line:      #e2e8f0;   /* hairline borders      */
    --accent:    #1a5276;   /* link / accent blue    */
    --panel:     #f7f9fb;   /* faint panel fill      */
    --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}

  * {{ box-sizing: border-box; }}

  html, body {{
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 15px;
    line-height: 1.5;
  }}

  /* ─── Header (fixed top) ─────────────────────────────────────── */
  header {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--bg);
    border-bottom: 2px solid var(--ink);
    padding: 10px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .brand {{
    display: flex;
    align-items: baseline;
    gap: 10px;
  }}
  .brand .logo {{
    font-size: 22px;
    font-weight: 800;
    color: var(--ink);
    letter-spacing: 0.5px;
  }}
  .brand .tag {{
    font-size: 13px;
    color: var(--ink-soft);
    font-style: italic;
  }}
  .header-right {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .ver-pill {{
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 700;
    color: var(--accent);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 3px 9px;
  }}
  .debug-btn {{
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 700;
    color: #ffffff;
    background: var(--accent);
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    cursor: pointer;
    text-decoration: none;
  }}
  .debug-btn:hover {{ background: #14405e; }}

  /* ─── Main content ───────────────────────────────────────────── */
  main {{
    max-width: 1180px;     /* comfortable on a 13" screen */
    margin: 0 auto;
    padding: 24px 20px 80px;
  }}

  h1.page-title {{
    font-size: 26px;
    font-weight: 800;
    margin: 4px 0 4px;
  }}
  .subtitle {{
    color: var(--ink-soft);
    font-size: 14px;
    margin-bottom: 24px;
  }}

  /* ─── Preflight panel ────────────────────────────────────────── */
  .panel {{
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    padding: 18px 20px;
    margin-bottom: 22px;
  }}
  .panel h2 {{
    font-size: 17px;
    font-weight: 800;
    margin: 0 0 4px;
  }}
  .panel .panel-sub {{
    font-size: 13px;
    color: var(--ink-soft);
    margin-bottom: 14px;
  }}
  .overall {{
    font-family: var(--mono);
    font-size: 15px;
    font-weight: 800;
    color: {overall_color};
    margin-bottom: 12px;
  }}
  table.pf {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }}
  table.pf th {{
    text-align: left;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--ink-soft);
    border-bottom: 1px solid var(--line);
    padding: 6px 8px;
  }}
  table.pf td {{
    border-bottom: 1px solid var(--line);
    padding: 7px 8px;
    vertical-align: top;
  }}
  .pf-label {{ font-weight: 600; width: 34%; }}
  .pf-badge {{
    font-family: var(--mono);
    font-weight: 800;
    width: 12%;
  }}
  .pf-detail {{ color: var(--ink-soft); font-size: 13px; }}

  /* ─── Placeholder note for future sections ───────────────────── */
  .note {{
    border: 1px dashed var(--line);
    border-radius: 8px;
    padding: 16px 20px;
    color: var(--ink-soft);
    font-size: 14px;
    background: #ffffff;
  }}

  /* ─── Footer ─────────────────────────────────────────────────── */
  footer {{
    border-top: 1px solid var(--line);
    padding: 16px 20px;
    text-align: center;
    color: var(--ink-soft);
    font-size: 12px;
    background: var(--bg);
  }}
  footer .f-line {{ margin: 2px 0; }}

  /* ─── Floating "Back to Top" return button ───────────────────── */
  #back-to-top {{
    position: fixed;
    right: 22px;
    bottom: 22px;
    z-index: 200;
    background: var(--ink);
    color: #ffffff;
    border: none;
    border-radius: 50%;
    width: 46px;
    height: 46px;
    font-size: 20px;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    display: none;          /* hidden until user scrolls */
    align-items: center;
    justify-content: center;
    line-height: 1;
  }}
  #back-to-top:hover {{ background: var(--accent); }}
</style>
</head>
<body>

  <!-- ═══ HEADER ═══ -->
  <header>
    <div class="brand">
      <span class="logo">{APP_NAME}</span>
      <span class="tag">{TAGLINE}</span>
    </div>
    <div class="header-right">
      <span class="ver-pill">v{APP_VERSION}</span>
      <a class="debug-btn" href="/debug" target="_blank" rel="noopener">DEBUG</a>
    </div>
  </header>

  <!-- ═══ MAIN ═══ -->
  <main id="top">
    <h1 class="page-title">{APP_NAME} — Iteration 2</h1>
    <div class="subtitle">Version {APP_VERSION} &middot; Structural baseline shell</div>

    <!-- Preflight panel -->
    <div class="panel">
      <h2>Preflight Self-Check</h2>
      <div class="panel-sub">Server-side checks run on every page load.</div>
      <div class="overall">OVERALL: {overall} &nbsp;({passed}/{total} checks passed)</div>
      <table class="pf">
        <thead>
          <tr><th>Check</th><th>Status</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>

    <!-- Placeholder for future sections -->
    <div class="note">
      This is the Version 1 baseline shell. Data sections (price, feeds,
      intelligence panels, etc.) will be added in later versions, two to
      three visual sections at a time, each fully verified before moving on.
    </div>
  </main>

  <!-- ═══ FLOATING RETURN BUTTON ═══ -->
  <button id="back-to-top" title="Back to top" aria-label="Back to top">&#8679;</button>

  <!-- ═══ FOOTER ═══ -->
  <footer>
    <div class="f-line">{APP_NAME} &middot; {TAGLINE}</div>
    <div class="f-line">Version {APP_VERSION} &middot; Booted {boot_str}</div>
    <div class="f-line">{COPYRIGHT}</div>
  </footer>

  <script>
    // Floating "Back to Top" button — appears after scrolling down a bit.
    (function () {{
      var btn = document.getElementById('back-to-top');
      if (!btn) return;
      function toggle() {{
        if (window.scrollY > 200) {{
          btn.style.display = 'flex';
        }} else {{
          btn.style.display = 'none';
        }}
      }}
      window.addEventListener('scroll', toggle, {{ passive: true }});
      btn.addEventListener('click', function () {{
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
      }});
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
        "app":          APP_NAME,
        "version":      APP_VERSION,
        "iteration":    2,
        "preflight":    overall,
        "checks_passed": f"{passed}/{total}",
        "checks": [
            {"label": label, "status": "PASS" if ok else "FAIL", "detail": detail}
            for label, ok, detail in checks
        ],
        "uptime_secs":  uptime,
        "booted_utc":   BOOT_TIME.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "now_utc":      datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
