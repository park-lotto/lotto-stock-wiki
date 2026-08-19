"""키를 고르는 판단은 한 곳(_next_live_key_and_idx)에서만 — 2026-08-18.

예전엔 _current_key_and_idx가 늘 live[0]을 줘서, 키가 여러 개여도 1번 키만 때렸다.
"""
import pytest

from shopping_shorts import comment_gen as cg


@pytest.fixture(autouse=True)
def _clean_rr():
    """전역 커서·최근사용 시각을 원복한다 — 안 하면 다른 테스트의 로테이션을 흔든다."""
    cur, used = cg._rr_cursor["i"], dict(cg._key_last_used)
    yield
    cg._rr_cursor["i"] = cur
    cg._key_last_used.clear()
    cg._key_last_used.update(used)


def test_호출마다_키가_돌아간다(monkeypatch):
    keys = ["K1", "K2", "K3"]
    monkeypatch.setattr(cg, "SHORTS_GEMINI_KEYS", keys)
    monkeypatch.setattr(cg, "_live_key_indices", lambda: [0, 1, 2])
    monkeypatch.setattr(cg, "_MIN_GAP_S", 0.0)
    cg._rr_cursor["i"] = 0
    cg._key_last_used.clear()
    got = [cg._current_key_and_idx()[0] for _ in range(3)]
    assert len(set(got)) == 3, f"같은 키만 나온다: {got}"


def test_전부_소진이면_None(monkeypatch):
    monkeypatch.setattr(cg, "_live_key_indices", lambda: [])
    assert cg._current_key_and_idx() == (None, None)
