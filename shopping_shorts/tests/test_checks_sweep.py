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
