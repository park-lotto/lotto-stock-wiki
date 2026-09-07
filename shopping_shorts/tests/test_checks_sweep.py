"""L1 전수 훑기(sweep) 순수 로직 단위 테스트 — 서버·브라우저 없이 돌아간다.
signature_of·classify·discover_targets 판정 로직은 가짜 dict/스텁으로 검증한다(브리프 지시).
브라우저·서버가 필요한 sweep_produce 등은 CHECKS_BASE_URL 없으면 skip."""
import os
from types import SimpleNamespace

import pytest

from shopping_shorts.checks import sweep
from shopping_shorts.checks.verdict import GRAY, GREEN, RED, Result

NEEDS_SERVER = pytest.mark.skipif(
    not os.environ.get("CHECKS_BASE_URL"), reason="CHECKS_BASE_URL 없음 — 서버/브라우저 실측은 로컬에서 skip"
)


# ---- 브리프 필수 테스트 ----

def test_signature_prefers_id_then_onclick_then_text():
    assert sweep.signature_of({"tag": "button", "id": "go", "onclick": "x()", "text": "가기"}) == "button#go"
    assert sweep.signature_of({"tag": "button", "id": "", "onclick": "deleteWork('a',this)", "text": "삭제"}) == "button@deleteWork"
    assert sweep.signature_of({"tag": "a", "id": "", "onclick": "", "text": "제작소로 이동합니다"}) == "a:제작소로 이동합니다"


def test_classify_red_on_pageerror_or_5xx_or_blank():
    empty = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    assert sweep.classify(empty, {**empty, "pageerrors": ["TypeError"]}, 1000, 1000, False)[0] == RED
    assert sweep.classify(empty, {**empty, "failed_responses": [("/api/x", 500)]}, 1000, 1000, False)[0] == RED
    assert sweep.classify(empty, empty, 1000, 50, False)[0] == RED          # 백지
    assert sweep.classify(empty, {**empty, "client_error_posts": 1}, 1000, 1000, False)[0] == RED
    assert sweep.classify(empty, empty, 1000, 990, False) == (GREEN, "")


# ---- 오탐 방지: classify()가 "정상"을 빨강으로 만들지 않는지 (핵심 검증) ----

def test_classify_normal_shrink_not_red_riview_repro():
    """리뷰 실측 재현: 모달/패널을 닫아 본문이 1000→80으로 줄어도(페이지 이동 없음, 새 에러 0)
    빨강이 아니어야 한다 — 절대하한(40) 위라 백지가 아니다."""
    empty = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    v, _ = sweep.classify(empty, empty, 1000, 80, False)
    assert v != RED


def test_classify_real_blank_still_red_below_floor():
    """본문이 절대하한(40) 밑으로까지 떨어지면 에러 유무와 무관하게 여전히 빨강이어야 한다."""
    empty = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    v, _ = sweep.classify(empty, empty, 1000, 5, False)
    assert v == RED


def test_classify_real_blank_with_error_still_red():
    empty = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    v, _ = sweep.classify(empty, {**empty, "pageerrors": ["TypeError"]}, 1000, 5, False)
    assert v == RED


def test_classify_green_when_navigated_even_if_body_shrinks():
    """다른 페이지로 이동한 뒤엔 본문 길이가 줄어도 '백지'가 아니다 — navigated=True는 예외."""
    empty = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    assert sweep.classify(empty, empty, 1000, 10, True) == (GREEN, "")


def test_classify_green_when_body_before_small():
    """원래 짧은 페이지(팝업·모달)는 절대 기준(200자) 밑이면 백지 판정 대상이 아니다."""
    empty = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    assert sweep.classify(empty, empty, 150, 5, False) == (GREEN, "")


def test_classify_green_on_401_403_only_failures():
    """401/403은 ErrorSink._on_response 단계에서부터 failed_responses에 안 쌓인다(browser.py) — 여기서도
    이미 기록된 4xx라 해도 새로 늘지 않으면(before==after) 초록이어야 한다."""
    before = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": [("/api/y", 404)]}
    after = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": [("/api/y", 404)]}
    assert sweep.classify(before, after, 1000, 990, False) == (GREEN, "")


def test_classify_only_new_failures_count():
    """기존에 있던 실패 응답이 그대로 남아 있는 것만으로는 새 빨강이 아니다 — 새로 늘어난 것만."""
    before = {"pageerrors": [], "console_errors": ["e1"], "client_error_posts": 0, "failed_responses": []}
    after = {"pageerrors": [], "console_errors": ["e1"], "client_error_posts": 0, "failed_responses": []}
    assert sweep.classify(before, after, 1000, 990, False) == (GREEN, "")


def test_signature_stable_regardless_of_dom_order_index():
    """discover_targets가 매기는 idx는 DOM 순서에 따라 바뀔 수 있다 — signature_of는 idx를 안 쓴다."""
    a = {"tag": "button", "id": "", "onclick": "openMix()", "text": "믹스 열기", "idx": 3}
    b = {"tag": "button", "id": "", "onclick": "openMix()", "text": "믹스 열기", "idx": 41}
    assert sweep.signature_of(a) == sweep.signature_of(b)


def test_signature_of_never_uses_idx_field():
    import inspect
    src = inspect.getsource(sweep.signature_of)
    assert '"idx"' not in src and "['idx']" not in src and ".get('idx'" not in src.replace('"', "'")


# ---- 안전 그물이 막은 요청 때문에 생긴 에러는 판정에서 제외(오탐 방지 #2) ----

def test_filter_blocked_noise_removes_only_blocked_related_errors():
    """차단된 요청(예: /api/delete_work) 때문에 생긴 콘솔에러·실패응답·client_error 리포트는
    이 조작 때문에 빨강이 되면 안 된다."""
    before = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    after = {
        "pageerrors": [],
        "console_errors": ["Failed to load resource: /api/delete_work/abc"],
        "client_error_posts": 1,
        "failed_responses": [("/api/delete_work/abc", 0)],
    }
    filtered = sweep.filter_blocked_noise(after, before, ["/api/delete_work/abc"])
    v, why = sweep.classify(before, filtered, 500, 480, False)
    assert v == GREEN, why


def test_filter_blocked_noise_keeps_unrelated_real_error():
    """차단과 무관한 진짜 JS 에러는 그대로 살아 빨강이어야 한다."""
    before = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    after = {
        "pageerrors": ["TypeError: cannot read x of undefined"],
        "console_errors": [],
        "client_error_posts": 0,
        "failed_responses": [],
    }
    filtered = sweep.filter_blocked_noise(after, before, ["/api/delete_work/abc"])
    v, _ = sweep.classify(before, filtered, 500, 480, False)
    assert v == RED


def test_filter_blocked_noise_noop_when_nothing_blocked():
    before = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    after = {"pageerrors": ["boom"], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    assert sweep.filter_blocked_noise(after, before, []) == after


def test_filter_blocked_noise_removes_generic_netfail_without_path():
    """★Task14 2차 실측: route.abort()가 실제로 내는 console 메시지는 경로가 안 실린
    "Failed to load resource: net::ERR_FAILED" 하나뿐이다(예: coupang identify_batch 차단 →
    "/"가 빨강으로 오판됨). 텍스트 부분매칭이 아니라 개수 기반으로도 걸러져야 한다."""
    before = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    after = {
        "pageerrors": [],
        "console_errors": ["Failed to load resource: net::ERR_FAILED"],
        "client_error_posts": 0,
        "failed_responses": [],
    }
    filtered = sweep.filter_blocked_noise(after, before, ["/api/coupang/identify_batch"])
    assert filtered["console_errors"] == []
    v, why = sweep.classify(before, filtered, 500, 480, False)
    assert v == GREEN, why


def test_filter_blocked_noise_keeps_real_error_alongside_generic_netfail():
    """경로 없는 일반 실패 메시지는 막힌 요청 수만큼만 깎는다 — 진짜 JS 에러는 예산과 무관하게 산다."""
    before = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    after = {
        "pageerrors": [],
        "console_errors": ["Failed to load resource: net::ERR_FAILED",
                            "TypeError: cannot read property 'x' of undefined"],
        "client_error_posts": 0,
        "failed_responses": [],
    }
    filtered = sweep.filter_blocked_noise(after, before, ["/api/coupang/identify_batch"])
    assert filtered["console_errors"] == ["TypeError: cannot read property 'x' of undefined"]
    v, _ = sweep.classify(before, filtered, 500, 480, False)
    assert v == RED   # 무관한 진짜 에러는 여전히 빨강


def test_filter_blocked_noise_generic_netfail_budget_capped_by_blocked_count():
    """일반 실패 메시지가 막힌 요청 수보다 많으면 초과분은 진짜 문제일 수 있어 살려둔다."""
    before = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
    after = {
        "pageerrors": [], "client_error_posts": 0, "failed_responses": [],
        "console_errors": ["Failed to load resource: net::ERR_FAILED",
                            "Failed to load resource: net::ERR_FAILED"],
    }
    filtered = sweep.filter_blocked_noise(after, before, ["/api/coupang/identify_batch"])  # 1개만 막힘
    assert len(filtered["console_errors"]) == 1   # 2개 중 1개(막힌 수만큼)만 깎임


class _ListFakePage:
    """sweep_lists 통합 시험용: goto_ready(browser.py)가 부르는 표면만 흉내낸다.
    on_goto(url)를 넘기면 goto() 시점(=실제로 안전그물이 요청을 막는 시점)에 노이즈를 주입할 수 있다."""
    def __init__(self, card_count=1, on_goto=None):
        self.card_count = card_count
        self.on_goto = on_goto

    def goto(self, url, wait_until=None, timeout=None):
        if self.on_goto:
            self.on_goto(url)

    def wait_for_selector(self, sel, timeout=None, state=None):
        pass

    def locator(self, sel):
        return SimpleNamespace(count=lambda: self.card_count)


def test_sweep_lists_does_not_redden_on_blocked_request_noise():
    """★핵심 회귀: coupang identify_batch 같은 차단 요청이 낸 "Failed to load resource: net::ERR_FAILED"
    콘솔 에러 하나만 있을 때 sweep_lists가 "/"를 빨강으로 오판하면 안 된다(2026-09-07 서버 실측 오탐).
    실제 타이밍대로 goto() 도중(=안전그물이 요청을 막는 시점)에 blocked·콘솔에러를 주입한다."""
    from shopping_shorts.checks.browser import ErrorSink

    errors = ErrorSink()
    session = SimpleNamespace(base_url="http://x", errors=errors, blocked=[])

    def _on_goto(url):
        if url == "http://x/":   # "/" 방문 때만 차단 노이즈를 흉내낸다
            session.blocked.append("POST /api/coupang/identify_batch")
            errors.console_errors.append("Failed to load resource: net::ERR_FAILED")

    session.page = _ListFakePage(card_count=5, on_goto=_on_goto)

    out = sweep.sweep_lists(session)
    home = [r for r in out if r.page == "/"][0]
    assert home.verdict == GREEN, home.reason


def test_sweep_lists_still_reddens_on_unrelated_real_error():
    """차단과 무관한 진짜 console 에러는 여전히 빨강이어야 한다(오탐 방지가 검사를 무력화하면 안 됨)."""
    from shopping_shorts.checks.browser import ErrorSink

    errors = ErrorSink()
    session = SimpleNamespace(base_url="http://x", errors=errors, blocked=[])

    def _on_goto(url):
        if url == "http://x/":
            errors.console_errors.append("TypeError: cannot read property 'x' of undefined")

    session.page = _ListFakePage(card_count=5, on_goto=_on_goto)

    out = sweep.sweep_lists(session)
    home = [r for r in out if r.page == "/"][0]
    assert home.verdict == RED


# ---- discover_targets: 페이지 스텁으로 검증 ----

class _StubPage:
    def __init__(self, result):
        self._result = result
        self.calls = []

    def evaluate(self, script, *args):
        self.calls.append((script, args))
        return self._result


def test_discover_targets_calls_page_evaluate_and_returns_list():
    stub = _StubPage([{"idx": 0, "tag": "button", "id": "a", "onclick": "", "text": "가기", "type": "",
                        "x": 1, "y": 1, "w": 10, "h": 10}])
    out = sweep.discover_targets(stub)
    assert out == stub._result
    assert len(stub.calls) == 1


def test_hit_test_true_false():
    assert sweep.hit_test(_StubPage(True), 0) is True
    assert sweep.hit_test(_StubPage(False), 0) is False
    assert sweep.hit_test(_StubPage(None), 0) is False


# ---- ★Task14 2차 실측: 제작소 전수가 앱 공통 사이드바(로그아웃·작업삭제)까지 누르면 안 된다 ----

def test_is_app_shell_nav_flags_logout_delete_rename_bugreport_and_hrefs():
    assert sweep._is_app_shell_nav({"onclick": "window.__ssLogout()"}) is True
    assert sweep._is_app_shell_nav({"onclick": "window.__ssDelWork(event,'abc')"}) is True
    assert sweep._is_app_shell_nav({"onclick": "window.__ssRenWork(event,'abc')"}) is True
    assert sweep._is_app_shell_nav({"onclick": "ssOpenBugReport()"}) is True
    assert sweep._is_app_shell_nav({"onclick": "location.href='/challenge'"}) is True
    assert sweep._is_app_shell_nav({"onclick": ""}) is False
    # ★284건 빨강 폭증 실측(2026-09-07): 단계 칩(jump(N))도 프레스 루프에 걸리면 다른 패널로
    # 넘어가버려 그 뒤 요소들이 전부 오탐났다 — _open()이 이미 이 칩으로 패널을 여니 판정 대상에서 뺀다.
    assert sweep._is_app_shell_nav({"onclick": "jump(0)"}) is True
    assert sweep._is_app_shell_nav({"onclick": "jump(9)"}) is True
    assert sweep._is_app_shell_nav({"onclick": "jumpTo(0)"}) is False   # 다른 이름의 함수는 안 건드림


def test_sweep_url_skip_excludes_matching_targets_before_any_click(monkeypatch):
    """skip으로 걸러진 요소는 클릭 루프 진입 전에 빠져야 한다(로그아웃 사고 방지) — targets 리스트에서
    아예 사라지는지를 discover_targets 실제 반환값으로 확인한다."""
    monkeypatch.setattr(sweep, "discover_targets", lambda page: [
        {"idx": 0, "tag": "div", "id": "", "onclick": "window.__ssLogout()", "text": "로그아웃",
         "x": 0, "y": 0, "w": 10, "h": 10},
        {"idx": 1, "tag": "button", "id": "", "onclick": "removeMixUrlRow(this)", "text": "삭제",
         "x": 0, "y": 0, "w": 10, "h": 10},
    ])
    monkeypatch.setattr(sweep, "hit_test", lambda page, idx: True)
    pressed = []
    monkeypatch.setattr(sweep, "_press", lambda session, info, url: pressed.append(info["idx"]) or
                        Result("L1", info["text"], GREEN, signature=f"L1:{info['idx']}", page=url))

    class _Page:
        url = "http://x/produce"
        def evaluate(self, js, *a):
            return None

    session = SimpleNamespace(page=_Page(), base_url="http://x", errors=None, blocked=[])
    monkeypatch.setattr(sweep.browser, "goto_produce", lambda page, url, timeout_ms=12000: None)

    out = sweep.sweep_url(session, "/produce", skip=sweep._is_app_shell_nav)
    assert pressed == [1]              # 로그아웃(idx0)은 클릭 루프에 아예 안 들어감
    assert [r.signature for r in out] == ["L1:1"]


# ---- GRAY 감싸기: Session 생성/로그인 실패·playwright 부재는 판정불가로 ----

class _BoomSession:
    """session.page 접근 시 RuntimeError(로그인 실패 흉내)를 던지는 가짜."""
    base_url = "http://127.0.0.1:8850"

    @property
    def page(self):
        raise RuntimeError("로그인 실패 500")


def test_sweep_produce_wraps_runtime_error_as_gray():
    out = sweep.sweep_produce(_BoomSession())
    assert len(out) == 1
    assert out[0].verdict == GRAY


def test_sweep_produce_stops_and_reports_gray_when_time_budget_exceeded(monkeypatch):
    """★Task14 3차 실측: 칩 클릭이 실제로 성공하게 되자 패널 하나만도 90초를 넘길 수 있음이
    드러났다(EPIPE로 강제종료됨). 시간예산을 넘기면 무한대기 대신 회색+이유로 멈춰야 한다."""
    class _FakePage:
        url = "http://x/produce"
        def evaluate(self, js, *a):
            if "STEP_LABELS" in js:
                return ["p0", "p1", "p2"]  # STEP_LABELS 흉내
            return 30   # timer_probe(_apply_throttle_gate가 부름) 흉내 — 스로틀 없음

    class _Session:
        page = _FakePage()
        base_url = "http://x"

    monkeypatch.setattr(sweep, "cleanup_old_evidence", lambda: None)
    monkeypatch.setattr(sweep.browser, "goto_produce", lambda page, url, timeout_ms=12000: None)
    monkeypatch.setattr(sweep, "sweep_url", lambda session, url, reopen=None, skip=None: [
        Result("L1", "가짜", GREEN, signature="L1:fake")])

    clock = {"t": 0.0}
    def _fake_time():
        clock["t"] += 40   # 패널 하나당 40초씩 흐른다고 흉내 — 3번째 패널 전에 90초 예산 초과
        return clock["t"]
    monkeypatch.setattr(sweep.time, "time", _fake_time)

    out = sweep.sweep_produce(_Session(), panels=range(3))
    gray = [r for r in out if r.verdict == GRAY]
    green = [r for r in out if r.verdict == GREEN]
    assert len(gray) == 1
    assert "시간예산" in gray[0].reason
    assert len(green) < 3   # 패널 3개를 다 못 훑고 도중에 멈췄다는 뜻


def test_sweep_lists_wraps_runtime_error_as_gray():
    out = sweep.sweep_lists(_BoomSession())
    assert len(out) == 1
    assert out[0].verdict == GRAY


def test_sweep_sidebar_wraps_runtime_error_as_gray():
    out = sweep.sweep_sidebar(_BoomSession())
    assert len(out) == 1
    assert out[0].verdict == GRAY


def test_reporter_alive_wraps_runtime_error_as_gray():
    out = sweep.reporter_alive(_BoomSession())
    assert out.verdict == GRAY


# ---- 브라우저·서버 실측 (로컬은 skip) ----

@NEEDS_SERVER
def test_sweep_produce_live():
    from shopping_shorts.checks import browser
    base = os.environ["CHECKS_BASE_URL"]
    s = browser.open_session(base, os.environ["DASH_USER"], os.environ["DASH_PASS"])
    try:
        browser.login(s)
        out = sweep.sweep_produce(s)
        assert isinstance(out, list)
    finally:
        browser.close_session(s)


# ---- 빨간 줄 증거 사진(2026-09-07 리뷰 반영) ----

class _EvidencePage:
    """page.screenshot(path=...)만 흉내내는 최소 가짜. 실패 흉내는 raise_on_screenshot로."""
    def __init__(self, raise_on_screenshot=False):
        self.url = "http://x/produce"
        self.raise_on_screenshot = raise_on_screenshot
        self.screenshot_calls = []

    def click(self, sel, timeout=3000, no_wait_after=True):
        pass

    def fill(self, sel, val, timeout=3000):
        pass

    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, script, *a):
        return 100  # _body_len 등 — 이 테스트들은 백지 판정 경로를 쓰지 않는다

    def screenshot(self, path):
        self.screenshot_calls.append(path)
        if self.raise_on_screenshot:
            raise RuntimeError("페이지가 이미 닫힘(흉내)")
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")


class _EvidenceSink:
    """before/after snapshot()을 순서대로 내주는 가짜(1번째=before, 2번째=after)."""
    def __init__(self, seq):
        self._seq = list(seq)
        self._i = 0

    def snapshot(self):
        d = self._seq[min(self._i, len(self._seq) - 1)]
        self._i += 1
        return d


class _EvidenceSession:
    base_url = "http://x"

    def __init__(self, page, sink):
        self.page = page
        self.errors = sink
        self.blocked = []


_EMPTY_SNAP = {"pageerrors": [], "console_errors": [], "client_error_posts": 0, "failed_responses": []}
_RED_INFO = {"idx": 0, "tag": "button", "id": "", "onclick": "", "text": "빨간버튼", "type": ""}


def test_press_red_writes_evidence_file(tmp_path, monkeypatch):
    """빨강일 때 EVIDENCE_ROOT/<dir>/shot.png가 실제로 생긴다."""
    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path)
    page = _EvidencePage()
    sink = _EvidenceSink([_EMPTY_SNAP, {**_EMPTY_SNAP, "pageerrors": ["TypeError: boom"]}])
    session = _EvidenceSession(page, sink)

    result = sweep._press(session, _RED_INFO, "/produce")

    assert result.verdict == RED
    assert result.evidence_dir, "빨강인데 evidence_dir이 비어 있음"
    shot = tmp_path / result.evidence_dir / "shot.png"
    assert shot.is_file()


def test_press_green_writes_no_evidence(tmp_path, monkeypatch):
    """초록일 때는 스크린샷을 찍지 않는다 — 디스크가 안 찬다."""
    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path)
    page = _EvidencePage()
    sink = _EvidenceSink([_EMPTY_SNAP, _EMPTY_SNAP])  # 새 에러 없음
    session = _EvidenceSession(page, sink)

    result = sweep._press(session, _RED_INFO, "/produce")

    assert result.verdict == GREEN
    assert result.evidence_dir == ""
    assert page.screenshot_calls == []
    assert list(tmp_path.iterdir()) == []


def test_press_red_screenshot_failure_keeps_verdict(tmp_path, monkeypatch):
    """screenshot()이 예외를 던져도(페이지 이미 닫힘 등) 판정 자체는 그대로 RED로 기록되고
    evidence_dir만 비어 있어야 한다 — 증거 캡처 실패가 점검을 죽이면 안 된다."""
    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path)
    page = _EvidencePage(raise_on_screenshot=True)
    sink = _EvidenceSink([_EMPTY_SNAP, {**_EMPTY_SNAP, "pageerrors": ["TypeError: boom"]}])
    session = _EvidenceSession(page, sink)

    result = sweep._press(session, _RED_INFO, "/produce")

    assert result.verdict == RED  # 판정은 살아있다
    assert "TypeError" in result.reason
    assert result.evidence_dir == ""  # 캡처만 실패
    assert page.screenshot_calls  # 시도는 했다


def test_capture_red_evidence_swallows_any_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path)

    class _BoomPage:
        def screenshot(self, path):
            raise OSError("disk full(흉내)")

    class _S:
        page = _BoomPage()

    assert sweep.capture_red_evidence(_S(), "sig") == ""


def test_capture_red_evidence_no_page_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path)

    class _NoPage:
        page = None

    assert sweep.capture_red_evidence(_NoPage(), "sig") == ""


def test_cleanup_old_evidence_removes_only_old_dirs(tmp_path, monkeypatch):
    import os
    import time as _time

    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path)
    old_dir = tmp_path / "old_sig_1"
    old_dir.mkdir()
    (old_dir / "shot.png").write_bytes(b"x")
    new_dir = tmp_path / "new_sig_1"
    new_dir.mkdir()
    (new_dir / "shot.png").write_bytes(b"x")
    old_ts = _time.time() - 20 * 86400
    os.utime(old_dir, (old_ts, old_ts))

    removed = sweep.cleanup_old_evidence(max_age_days=14)

    assert removed == 1
    assert not old_dir.exists()
    assert new_dir.exists()


def test_cleanup_old_evidence_missing_root_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path / "does_not_exist")
    assert sweep.cleanup_old_evidence() == 0


def test_cleanup_old_evidence_never_escapes_root(tmp_path, monkeypatch):
    """심볼릭 링크로 루트 밖을 가리켜도 그 대상은 절대 지우면 안 된다."""
    evroot = tmp_path / "evroot"
    evroot.mkdir()
    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", evroot)
    outside = tmp_path / "outside_secret"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    link = evroot / "link_out"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("이 환경은 심볼릭 링크 생성 권한이 없음")
    import os
    import time as _time
    old_ts = _time.time() - 20 * 86400
    os.utime(outside, (old_ts, old_ts))

    sweep.cleanup_old_evidence(max_age_days=14)

    assert outside.exists()
    assert (outside / "keep.txt").exists()
