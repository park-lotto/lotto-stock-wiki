# -*- coding: utf-8 -*-
"""틱톡 로그인 세션(storage_state) 만들기 — 사장님이 직접 로그인한다.

왜: kw_backends.pw_tiktok은 세션이 있으면 프록시로 무료로 긁고, 없으면
Apify($0.0195/회)로 폴백한다. 세션 파일 하나로 그 비용이 0이 된다
(_CHAIN·엔드포인트·프론트 무수정 — handoff/렌즈CN통합.md 실측).

샤오홍슈 세션(rednote_session.json)을 만든 것과 같은 방법이다.
⚠️도우인은 QR 로그인이 +82 SMS 거부로 막혔다 — 틱톡도 같은 벽일 수 있다.

쓰는 법:
    python tools/make_tiktok_session.py
  → 창이 뜨면 로그인만 하면 된다. **엔터를 누를 필요 없다** — 로그인이 끝나
    `sessionid` 쿠키가 생기는 순간 자동으로 저장하고 창을 닫는다.
  → out/tiktok_session.json 에 저장된다. 서버로는 scp로 올린다.

★엔터 대기(input)를 쓰지 않는 이유: Claude Code의 `!` 실행은 stdin이 없어서
  input()이 즉시 EOF로 죽는다(2026-09-08 실측 — 창만 뜨고 바로 종료됐다).
  그래서 사람의 입력이 아니라 **쿠키 상태를 폴링**해서 완료를 판정한다.
"""
import pathlib
import time

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "out" / "tiktok_session.json"
WAIT_SEC = 600          # 로그인에 쓸 수 있는 시간(10분). SMS·캡차까지 감안한 값.
POLL_SEC = 2


def _logged_in(ctx):
    """로그인 판정 — 화면 문구가 아니라 **sessionid 쿠키**로 본다.

    문자열 검사로 판정하지 않는 이유는 CLAUDE.md 0순위-B의 실사고와 같다
    (CSS 변수명에 'challenge'가 들어 있어 오판한 적이 있다)."""
    return any(c.get("name") == "sessionid" and c.get("value")
               for c in ctx.cookies())


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        # headless=False — 사장님이 직접 로그인해야 하므로 창을 띄운다.
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(locale="ko-KR")
        page = ctx.new_page()
        page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
        print("=" * 62)
        print("  브라우저 창에서 틱톡에 로그인하세요. (엔터 누를 필요 없습니다)")
        print("  로그인이 끝나면 자동으로 저장하고 창이 닫힙니다. 최대 10분 기다립니다.")
        print("=" * 62, flush=True)

        deadline = time.time() + WAIT_SEC
        ok = False
        last_note = 0
        while time.time() < deadline:
            try:
                if _logged_in(ctx):
                    ok = True
                    break
            except Exception:
                # 사용자가 창을 닫으면 컨텍스트가 죽는다 — 조용히 끝낸다.
                print("창이 닫혔습니다 — 로그인 전이면 다시 실행하세요.", flush=True)
                return 1
            left = int(deadline - time.time())
            if left // 60 != last_note:      # 1분마다 남은 시간 한 줄
                last_note = left // 60
                print("  … 로그인 대기 중 (남은 %d분)" % (left // 60 + 1), flush=True)
            time.sleep(POLL_SEC)

        if not ok:
            print("❌ 10분 안에 로그인이 확인되지 않았습니다(sessionid 없음).", flush=True)
            browser.close()
            return 2

        # 쿠키가 다 자리잡도록 잠깐 두고 저장한다(로그인 직후 리다이렉트 중일 수 있다).
        time.sleep(3)
        ctx.storage_state(path=str(OUT))
        import json
        data = json.loads(OUT.read_text(encoding="utf-8"))
        names = {c.get("name") for c in data.get("cookies") or []}
        print("✅ 저장: %s" % OUT, flush=True)
        print("   쿠키 %d개 · sessionid 있음" % len(names), flush=True)
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
