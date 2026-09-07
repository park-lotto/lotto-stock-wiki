"""L1 전수 훑기(sweep) 순수 로직 단위 테스트 — 서버·브라우저 없이 돌아간다.
signature_of·classify·discover_targets 판정 로직은 가짜 dict/스텁으로 검증한다(브리프 지시).
브라우저·서버가 필요한 sweep_produce 등은 CHECKS_BASE_URL 없으면 skip."""
import os

import pytest

from shopping_shorts.checks import sweep
from shopping_shorts.checks.verdict import GRAY, GREEN, RED

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
