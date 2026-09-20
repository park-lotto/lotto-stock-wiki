"""Playwright 세션 한 벌 — 로그인은 사람과 같은 /api/login, 그물은 confirm→false + route 허용 목록,
콘솔·pageerror·client_error·4xx/5xx 수집, 타이머 스로틀 측정, 카나리."""
from dataclasses import dataclass, field
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from shopping_shorts.checks import allow_mutations
from shopping_shorts.checks.verdict import GREEN, RED, Result


@dataclass
class ErrorSink:
    pageerrors: list = field(default_factory=list)
    console_errors: list = field(default_factory=list)
    client_error_posts: int = 0
    failed_responses: list = field(default_factory=list)

    def snapshot(self):
        return {"pageerrors": list(self.pageerrors), "console_errors": list(self.console_errors),
                "client_error_posts": self.client_error_posts, "failed_responses": list(self.failed_responses)}

    def reset(self):
        self.pageerrors.clear(); self.console_errors.clear()
        self.client_error_posts = 0; self.failed_responses.clear()


@dataclass
class Session:
    pw: object
    browser: object
    context: object
    page: object
    base_url: str
    user: str
    password: str
    errors: ErrorSink
    blocked: list = field(default_factory=list)


def _attach(session):
    page, sink = session.page, session.errors
    page.on("pageerror", lambda e: sink.pageerrors.append(str(e)[:300]))
    page.on("console", lambda m: sink.console_errors.append(m.text[:300]) if m.type == "error" else None)

    def _on_response(resp):
        if resp.status >= 400 and resp.status not in (401, 402, 403):
            sink.failed_responses.append((resp.url[:200], resp.status))
    page.on("response", _on_response)

    def _route(route):
        req = route.request
        path = urlparse(req.url).path
        if path == "/api/client_error" and req.method == "POST":
            sink.client_error_posts += 1
        if not allow_mutations.is_allowed(req.method, path):
            session.blocked.append(f"{req.method} {path}")
            return route.abort()
        return route.continue_()
    # ★2026-09-07 리뷰 지적: 이 route 그물은 브라우저(page)가 보내는 요청만 잡는다.
    # Playwright의 page.request.post(...) 같은 API 컨텍스트 호출은 이 route를 안 거쳐 그대로
    # 나간다 — 지금은 그런 호출이 코드에 없어 무해하지만, 앞으로 점검 코드에서
    # page.request.post/put/delete를 쓰면 이 deny-by-default(allow_mutations)를 우회한다.
    # 검사 코드는 클릭·입력·읽기만 하고 page.request는 쓰지 않는다(설계 D17·D18).
    page.route("**/*", _route)
    page.add_init_script("window.confirm = () => false; window.open = () => null;")
    page.on("dialog", lambda d: d.dismiss())


def open_session(base_url, user, password, headless=True):
    allow_mutations.assert_safe()
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
    page = context.new_page()
    s = Session(pw, browser, context, page, base_url.rstrip("/"), user, password, ErrorSink())
    _attach(s)
    return s


def close_session(s):
    try:
        s.context.close(); s.browser.close()
    finally:
        s.pw.stop()


def login(s):
    """사람과 같은 경로: POST /api/login(form) → dash_auth 쿠키 → /api/me 로 cid 확인."""
    s.page.goto(s.base_url + "/login", wait_until="domcontentloaded")
    r = s.page.request.post(s.base_url + "/api/login", form={"user": s.user, "pass": s.password})
    if r.status not in (200, 303):
        raise RuntimeError(f"로그인 실패 {r.status}")
    me = s.page.request.get(s.base_url + "/api/me").json()
    return int(me.get("customer_id", me.get("id", -1)))


_PRODUCE_READY_JS = (
    "() => typeof STEP_LABELS !== 'undefined' && STEP_LABELS.length > 0 "
    "&& !!document.querySelector('#steps')"
)


def goto_produce(page, url, timeout_ms=12000):
    """제작소(/produce) 전용 이동. ★실측(2026-09-07 Task14): `wait_until="networkidle"`는
    /produce에서 폴링·SSE가 계속 돌아 절대 안 온다(15초 타임아웃 vs `load`는 0.18초) — 그래서
    `load`로 이동한 뒤 화면이 실제로 그려졌다는 표식(STEP_LABELS 정의 + #steps 존재)을 기다린다.
    표식이 timeout_ms 안에 안 나타나면 TimeoutError를 그대로 던진다(호출부 _run_guarded/run_flow가
    회색으로 감싼다 — 여기서 삼키지 않는다: 삼키면 "안 열림"과 "느림"을 구분 못 한다)."""
    page.goto(url, wait_until="load", timeout=timeout_ms)
    page.wait_for_function(_PRODUCE_READY_JS, timeout=timeout_ms)


def reload_produce(page, timeout_ms=12000):
    """/produce 새로고침판 goto_produce — roundtrip 검사(flows/base.py)가 새로고침 뒤 값을
    다시 읽기 전에 화면이 실제로 준비됐는지 기다리는 데 쓴다."""
    page.reload(wait_until="load", timeout=timeout_ms)
    page.wait_for_function(_PRODUCE_READY_JS, timeout=timeout_ms)


def goto_ready(page, url, ready_selector, timeout_ms=12000):
    """/produce가 아닌 화면(목록·라이브러리 등) 전용: `load` 뒤 그 검사가 실제로 읽는 셀렉터가
    나타나길 기다린다. ★못 찾아도 예외를 던지지 않는다 — 카드 0개는 그 자체로 유효한 판정 결과일
    수 있어서, 타임아웃을 "판정 불가"로 승격시키면 진짜 빈 목록까지 회색으로 가려버린다."""
    page.goto(url, wait_until="load", timeout=timeout_ms)
    try:
        page.wait_for_selector(ready_selector, timeout=timeout_ms, state="attached")
    except Exception:  # noqa: BLE001 — playwright TimeoutError 등: 못 찾았어도 그대로 진행
        pass


def timer_probe(page):
    """자동화 탭 스로틀 측정: 100ms 인터벌이 3초에 몇 번 도나(정상≈30, 스로틀=4)."""
    return page.evaluate("""() => new Promise(res => {
        let n = 0; const t = setInterval(() => n++, 100);
        setTimeout(() => { clearInterval(t); res(n); }, 3000);
    })""")


def canary(page):
    """판정기 자체가 살아있나: 일부러 에러를 내는 페이지에서 pageerror가 잡혀야 초록."""
    caught = []
    handler = lambda e: caught.append(str(e))
    page.on("pageerror", handler)
    try:
        page.set_content("<html><body><script>setTimeout(()=>{throw new Error('CANARY')},10)</script></body></html>")
        page.wait_for_timeout(300)
    finally:
        page.remove_listener("pageerror", handler)
    ok = any("CANARY" in c for c in caught)
    return Result("L0", "점검기 카나리(에러를 잡아내나)", GREEN if ok else RED,
                  reason=f"잡힌 pageerror {len(caught)}건", signature="L0:canary")
