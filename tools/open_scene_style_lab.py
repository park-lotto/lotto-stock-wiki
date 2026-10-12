"""로컬 LAB 결과를 관리자 페이지·랜딩에서 열고 스크린샷으로 남긴다."""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path,
                        default=ROOT / "out" / "scene-style-lab-probe" / "probe-result.json")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    result = json.loads(args.probe.read_text(encoding="utf-8"))
    out = args.probe.parent.resolve()

    from shopping_shorts import app as appmod
    from shopping_shorts.store import Store
    import uvicorn

    db = out / "browser-lab.db"
    appmod.DB_PATH = str(db)
    appmod._MIX_WORK_DIR = Path(result["work_root"])
    appmod._AUTH_ON = True
    appmod.DASH_SECRET = "local-scene-style-lab-probe"
    store = Store(str(db))
    store.ensure_paywall_schema()
    if not store.get_mix_job("scene-style-local-probe"):
        store.create_mix_job("scene-style-local-probe", [], 20, "free", customer_id=0)
    manifest = json.loads(
        (Path(result["work_root"]) / "_scene_style_lab" / result["lab_id"] / "manifest.json")
        .read_text(encoding="utf-8")
    )
    clean_sources = (manifest.get("clean") or {}).get("paths") or {}
    store.update_mix_job(
        "scene-style-local-probe",
        edit_plan=manifest["edit_plan"],
        clean_sources=clean_sources,
        headcopy=manifest.get("headcopy"),
    )
    expires = int(datetime.now(timezone.utc).timestamp()) + 3600
    cookie = appmod._sign_session(0, expires)
    server = uvicorn.Server(uvicorn.Config(appmod.app, host="127.0.0.1", port=args.port,
                                           log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.context.add_cookies([{
                "name": "dash_auth", "value": cookie,
                "url": f"http://127.0.0.1:{args.port}",
            }])
            page.goto(
                f"http://127.0.0.1:{args.port}/scene_style_lab.html?lab={result['lab_id']}",
                wait_until="networkidle",
            )
            page.wait_for_selector("#outputs:not([hidden])")
            page.screenshot(path=str(out / "admin-lab.png"), full_page=True)
            page.goto(
                f"http://127.0.0.1:{args.port}/scene-style-lab/{result['lab_id']}",
                wait_until="networkidle",
            )
            page.screenshot(path=str(out / "landing.png"), full_page=True)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    main()
