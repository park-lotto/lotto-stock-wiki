"""버스트 429 백오프 회귀 — 100편 몰이 수집에서 성공률 29%→100% 근접을 지키는 핵심 로직.

한 라운드(라이브 키 전부)가 통째로 분당 429면 포기하지 말고 _QUOTA_BACKOFF만큼
쉬었다 재시도해야 한다. 예전엔 첫 라운드 실패 시 즉시 None → 몰이 때 성공률 폭락.
"""
import pytest

from shopping_shorts import pattern_bank, comment_gen


class _Quota(Exception):
    pass


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(pattern_bank.time, "sleep", lambda s: slept.append(s))
    return slept


def _wire_keys(monkeypatch, n=3):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k%d" % i for i in range(n)])
    monkeypatch.setattr(comment_gen, "_live_key_indices", lambda: list(range(n)))
    seq = iter(range(10_000))
    monkeypatch.setattr(comment_gen, "_next_live_key_and_idx",
                        lambda: ("k", next(seq) % n))
    monkeypatch.setattr(comment_gen.key_vault, "is_quota_error", lambda e: isinstance(e, _Quota))
    monkeypatch.setattr(comment_gen.key_vault, "is_daily_exhausted_error", lambda e: False)
    monkeypatch.setattr(comment_gen.key_vault, "is_account_disabled_error", lambda e: False)


def test_all_quota_then_success_retries_after_backoff(monkeypatch, _no_real_sleep):
    """첫 라운드 전부 429 → 백오프 후 재시도 → 성공. None이 아니라 결과가 나와야 한다."""
    _wire_keys(monkeypatch, n=3)
    calls = {"n": 0}

    class _Client:
        class models:
            @staticmethod
            def generate_content(**kw):
                calls["n"] += 1
                if calls["n"] <= 3:          # 첫 라운드(키 3개) 전부 429
                    raise _Quota("429 per minute")
                class R:                     # 둘째 라운드 첫 키 성공
                    text = '{"ok": 1}'
                return R()

    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _Client())
    out = pattern_bank._default_call("p", {"type": "object"})
    assert out == {"ok": 1}
    assert len(_no_real_sleep) == 1          # 딱 한 번 백오프 후 성공


def test_persistent_quota_gives_up_after_all_backoffs(monkeypatch, _no_real_sleep):
    """계속 429면 _QUOTA_BACKOFF 전부 소진 후 None. 무한루프 아님."""
    _wire_keys(monkeypatch, n=2)

    class _Client:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise _Quota("429")

    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _Client())
    out = pattern_bank._default_call("p", {"type": "object"})
    assert out is None
    assert len(_no_real_sleep) == len(pattern_bank._QUOTA_BACKOFF)  # 라운드 사이마다 대기


def test_non_quota_error_gives_up_immediately(monkeypatch, _no_real_sleep):
    """쿼터 아닌 에러는 백오프 없이 즉시 None(대기 낭비 금지)."""
    _wire_keys(monkeypatch, n=3)

    class _Client:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise ValueError("boom")

    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _Client())
    out = pattern_bank._default_call("p", {"type": "object"})
    assert out is None
    assert _no_real_sleep == []              # 백오프 안 함
