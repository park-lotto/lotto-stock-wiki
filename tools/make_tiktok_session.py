# -*- coding: utf-8 -*-
"""틱톡 로그인 세션(storage_state) 만들기 — 사장님이 직접 로그인한다.

왜: kw_backends.pw_tiktok은 세션이 있으면 프록시로 무료로 긁고, 없으면
Apify($0.0195/회)로 폴백한다. 세션 파일 하나로 그 비용이 0이 된다
(_CHAIN·엔드포인트·프론트 무수정 — handoff/렌즈CN통합.md 실측).

샤오홍슈 세션(rednote_session.json)을 만든 것과 같은 방법이다.
⚠️도우인은 QR 로그인이 +82 SMS 거부로 막혔다 — 틱톡도 같은 벽일 수 있다.

쓰는 법:
    python tools/make_tiktok_session.py
  → 창이 뜨면 로그인한다. 로그인이 끝나 피드가 보이면 터미널에서 엔터.
  → out/tiktok_session.json 에 저장된다. 서버로는 scp로 올린다.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "out" / "tiktok_session.json"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        # headless=False — 사장님이 직접 로그인해야 하므로 창을 띄운다.
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(locale="ko-KR")
        page = ctx.new_page()
        page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
        print("=" * 60)
        print("  브라우저 창에서 틱톡에 로그인하세요.")
        print("  로그인이 끝나 피드가 보이면 여기로 돌아와 엔터를 누르세요.")
        print("=" * 60)
        try:
            input()
        except EOFError:
            print("입력을 못 받았다 — 창을 닫지 말고 다시 실행해라.", file=sys.stderr)
            return 1
        ctx.storage_state(path=str(OUT))
        # 로그인 판정: 세션에 sessionid 쿠키가 들어왔는지로 본다(문자열 검사 아님).
        import json
        data = json.loads(OUT.read_text(encoding="utf-8"))
        names = {c.get("name") for c in data.get("cookies") or []}
        ok = "sessionid" in names
        print("저장:", OUT)
        print("쿠키 %d개 · sessionid %s" % (len(names), "있음 ✅" if ok else "없음 ❌ (로그인 안 된 듯)"))
        browser.close()
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
