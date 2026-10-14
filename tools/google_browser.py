"""구글 로그인이 저장된 전용 크롬(플레이라이트) — 구글폼·Apps Script·콘솔을 Claude가 직접 조작한다.

사장님(2026-10-14): "플레이라이트로 매일 너가 직접 하는데 왜 매번 시키냐."
크롬 확장이 끊겨도 이걸로 한다. 비밀번호는 Claude가 치지 않는다 — 처음 한 번만
사장님이 이 창에서 로그인하면 프로필(PROFILE)에 남아 다음부터 자동으로 로그인돼 있다.

  py tools/google_browser.py login              # 창을 띄움 → 사장님 로그인 → 로그인 확인되면 저장하고 닫힘
  py tools/google_browser.py check              # 로그인 살아있나(구글 계정 페이지)
  py tools/google_browser.py open <url>         # 로그인된 창으로 열고 사장님이 닫을 때까지 유지
  py tools/google_browser.py gs <파일.gs> <함수>  # 새 Apps Script에 붙여넣고 함수 실행(권한 창은 사장님이 허용)
파이썬: from tools.google_browser import google_page   # with google_page() as pg: ...
"""
import os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from contextlib import contextmanager
from playwright.sync_api import sync_playwright

PROFILE = os.path.expanduser(r"~\.claude\google_browser_profile")
_ARGS = dict(channel="chrome", headless=False, viewport=None,
             ignore_default_args=["--enable-automation"],
             args=["--disable-blink-features=AutomationControlled", "--start-maximized"])


@contextmanager
def google_page():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, **_ARGS)
        try:
            yield ctx.pages[0] if ctx.pages else ctx.new_page()
        finally:
            ctx.close()


def logged_in(pg):
    """구글 세션 쿠키(SID)가 있어야 로그인. ★주소로 판정하지 마라 — 비로그인도 myaccount 소개 페이지에 머문다."""
    if pg.url == "about:blank":
        pg.goto("https://www.google.com/", wait_until="domcontentloaded")
    return any(c["name"] == "SID" and "google.com" in c["domain"] for c in pg.context.cookies())


def cmd_login():
    with google_page() as pg:
        if logged_in(pg):
            print("이미 로그인돼 있음"); return
        pg.goto("https://accounts.google.com/")
        print("창에서 구글 로그인 해주세요(최대 10분 대기)...", flush=True)
        for _ in range(300):
            time.sleep(2)
            try:
                if logged_in(pg):
                    break
            except Exception:
                pass
        print("로그인 확인:", logged_in(pg))


def cmd_open(url):
    with google_page() as pg:
        pg.goto(url)
        print("열림 — 창을 닫으면 끝납니다", flush=True)
        try:
            pg.wait_for_event("close", timeout=0)
        except Exception:
            pass


def cmd_gs(path, func):
    code = open(path, encoding="utf-8").read()
    with google_page() as pg:
        if not logged_in(pg):
            print("로그인 안 됨 — 먼저 login"); return
        pg.goto("https://script.new"); pg.wait_for_selector(".monaco-editor", timeout=60000)
        pg.wait_for_timeout(2000)
        # ★키보드로 치면 monaco 자동 들여쓰기가 계단을 만든다 — 편집기 모델에 통째로 넣는다
        pg.locator(".monaco-editor textarea").first.focus()
        ok = pg.evaluate("t => { const m = window.monaco && monaco.editor.getModels()[0];"
                         " if (!m) return false; m.setValue(t); return true; }", code)
        if not ok:
            pg.keyboard.press("Control+A"); pg.keyboard.press("Delete"); pg.keyboard.insert_text(code)
        pg.keyboard.press("Control+S"); pg.wait_for_timeout(3000)
        print("붙여넣기·저장 완료. 함수 선택 후 실행:", func, flush=True)
        pg.get_by_role("combobox").filter(has_text="myFunction").first.click() if pg.get_by_role("combobox").filter(has_text="myFunction").count() else None
        try:
            pg.get_by_role("option", name=func).click()
        except Exception:
            pass
        pg.get_by_role("button", name="실행").first.click() if pg.get_by_role("button", name="실행").count() else pg.get_by_role("button", name="Run").first.click()
        print("실행 눌렀음 — 권한 창이 뜨면 사장님이 허용. 실행 로그 대기(최대 5분)...", flush=True)
        for _ in range(150):
            time.sleep(2)
            txt = pg.inner_text("body")
            if "실행 완료" in txt or "Execution completed" in txt or "[추가]" in txt or "[갱신]" in txt:
                break
        log = pg.inner_text("body")
        for key in ("[추가]", "[갱신]", "[변경]", "오류", "Error"):
            for line in log.splitlines():
                if key in line:
                    print("로그:", line.strip())
        pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(path)), "_gs_run.png"))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "login": cmd_login()
    elif a[0] == "check":
        with google_page() as pg: print("로그인:", logged_in(pg))
    elif a[0] == "open": cmd_open(a[1])
    elif a[0] == "gs": cmd_gs(a[1], a[2])
