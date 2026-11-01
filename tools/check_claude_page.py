# -*- coding: utf-8 -*-
"""/claude 시작 화면 점검(관제 300) — 실제 claude.html 을 브라우저로 열어 스크립트 오류·복사·접기·첫 화면을 본다."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HTML = (Path(__file__).parent.parent / "shopping_shorts/static/claude.html").read_text(encoding="utf-8")
HOME = {"presets": [], "styles": [], "results": [], "profiles": [], "installers": [], "steps": [], "notices": [],
        "packs": {"sfx": [], "bgm": [], "voices": [], "memes": [], "fonts": [], "templates": [],
                  "caption_packs": [], "caption_motions": []},
        "license": {"has_key": True, "expires": 1800000000, "slots": 2}, "devices_max": 2,
        "devices": [{"id": "a", "name": "PC-1", "slot": 1, "last_seen": 1790000000}]}


def main(out):
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1000, "height": 760})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin="http://localhost:8799")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        def h(r):
            u = r.request.url
            if u.endswith("/claude"):
                return r.fulfill(body=HTML, content_type="text/html; charset=utf-8")
            if "/me/home" in u:
                return r.fulfill(json=HOME)
            if "start_line" in u:
                return r.fulfill(body=json.dumps({"line": "TEST-LINE"}), content_type="application/json")
            return r.fulfill(body="", content_type="text/javascript")
        pg.route("http://localhost:8799/**", h)
        pg.goto("http://localhost:8799/claude")
        pg.wait_for_timeout(400)
        pg.click("#startCopy")
        pg.wait_for_timeout(200)
        clip = pg.evaluate("navigator.clipboard.readText()")
        hidden_ok = pg.evaluate("getComputedStyle(document.getElementById('license')).display") == "none"
        dev_hidden = not pg.is_visible("#devList")
        pg.screenshot(path=out)
        pg.click("details.more summary")
        dev_open = pg.is_visible("#devList")
        b.close()
    res = {"errors": errs, "copied": clip == "TEST-LINE", "license_hidden": hidden_ok,
           "devices_folded": dev_hidden, "devices_open": dev_open}
    print(res)
    return 0 if not errs and all(v for k, v in res.items() if k != "errors") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "claude_page.png"))
