# -*- coding: utf-8 -*-
"""유튜브·인스타그램·틱톡 로그인. 내 크롬 창에서 직접 로그인하면 쿠키만 data/sessions 에 저장한다. 비밀번호는 보지 않는다."""
import sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "data" / "browser"
OUT = ROOT / "data" / "sessions"
SITES = [("유튜브", "https://accounts.google.com/ServiceLogin?continue=https%3A%2F%2Fwww.youtube.com%2F", "youtube.com", ("__Secure-3PSID", "SID", "LOGIN_INFO")),
         ("인스타그램", "https://www.instagram.com/accounts/login/", "instagram.com", ("sessionid",)),
         ("틱톡", "https://www.tiktok.com/login", "tiktok.com", ("sessionid", "sid_tt"))]
KEEP = ("youtube.com", "google.com", "instagram.com", "tiktok.com")


def write(cookies):
    OUT.mkdir(parents=True, exist_ok=True)
    rows = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        d = c["domain"]
        if not d.lstrip(".").endswith(KEEP): continue
        rows.append("\t".join([d, "TRUE" if d.startswith(".") else "FALSE", c["path"], "TRUE" if c.get("secure") else "FALSE",
                               str(int(c["expires"]) if c.get("expires", -1) > 0 else 0), c["name"], c["value"]]))
    (OUT / "cookies.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = None
        for ch in ("chrome", "msedge"):
            try:
                ctx = p.chromium.launch_persistent_context(str(PROFILE), channel=ch, headless=False, no_viewport=True, args=["--disable-blink-features=AutomationControlled"]); break
            except Exception:
                continue
        if ctx is None: sys.exit("크롬이나 엣지를 찾지 못했습니다. 크롬을 설치해 주세요.")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for name, url, dom, ok in SITES:
            has = lambda: any(c["domain"].lstrip(".").endswith(dom) and c["name"] in ok and c["value"] for c in ctx.cookies())
            if has():
                print(name, "이미 로그인됨", flush=True); continue
            page.goto(url)
            print(f"{name}: 열린 창에서 로그인해 주세요. 끝나면 자동으로 다음으로 넘어갑니다.", flush=True)
            t0 = time.time()
            while not has() and time.time() - t0 < 600: time.sleep(2)
            print(name, "완료" if has() else "시간 초과 — 나중에 다시 실행해 주세요", flush=True)
        write(ctx.cookies())
        ctx.close()
    print("저장했습니다.")


if __name__ == "__main__":
    main()
