"""Smoke-test and screenshot every page of the web app (desktop + phone), failing on console errors.

python src/shoot_v2.py [--only page.html]
"""
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = ROOT / "renders" / "web"
PAGES = ["index.html", "audit.html", "beregner.html", "brand.html", "metode.html"]


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main(only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    srv = serve()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    report = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for name, vp, mobile in (("desk", {"width": 1440, "height": 900}, False), ("phone", {"width": 390, "height": 844}, True)):
            ctx = b.new_context(viewport=vp, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile, color_scheme="dark")
            for page in PAGES:
                if only and page != only:
                    continue
                pg = ctx.new_page()
                errs = []
                pg.on("console", lambda m, errs=errs: errs.append(m.text) if m.type == "error" else None)
                pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
                url = base + page + ("#K1" if page == "beregner.html" else "")
                pg.goto(url, wait_until="networkidle", timeout=120000)
                if page == "index.html":
                    pg.wait_for_function("window.G && window.G.ready", timeout=120000)
                    pg.wait_for_timeout(800)
                    pg.evaluate("G.frozen = false")
                    if name == "desk":
                        pg.locator("#viewer").screenshot(path=str(OUT / "hero.png"))
                        from PIL import Image
                        Image.open(OUT / "hero.png").convert("RGB").save(WEB / "assets" / "hero.jpg", quality=84, optimize=True)
                else:
                    pg.wait_for_timeout(700)
                over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                pg.screenshot(path=str(OUT / f"{page[:-5]}_{name}.png"), full_page=page != "index.html", timeout=120000)
                report[f"{page}|{name}"] = {"errors": errs, "h_overflow_px": over}
                pg.close()
            ctx.close()
        b.close()
    srv.shutdown()
    (ROOT / "results" / "web_smoke.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = {k: v for k, v in report.items() if v["errors"] or v["h_overflow_px"] > 0}
    print(json.dumps(bad or "all pages clean", indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--only" else None)
