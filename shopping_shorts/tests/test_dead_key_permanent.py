# -*- coding: utf-8 -*-
"""401/403(계정 사망) 키는 TTL이 만료돼도 **다시 잡히지 않는다**.

왜 이 테스트가 있나(2026-09-02 관측판 실사고):
  죽은 키 1개를 34분간 10~12번 반복 호출하고 있었다. 401/403이 429와 똑같이
  30분 TTL 잠금만 받아서, 만료되면 로테이션이 그 키를 다시 집어 또 실패했다.
  쿼터(429)는 회복되지만 계정 삭제·비활성은 회복되지 않는다 — 갈라야 한다.
"""
import pathlib

from shopping_shorts import comment_gen


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(comment_gen, "_STATE_PATH", pathlib.Path(tmp_path) / "s.json")
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["AAAA", "BBBB", "CCCC"])


def test_401_403은_TTL_만료후에도_안돌아온다(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    dead = Exception("403 PERMISSION_DENIED: service account is deleted or disabled")
    comment_gen._mark_key_exhausted(1, 60, exc=dead)
    assert 1 not in comment_gen._live_key_indices()
    # TTL 잠금을 통째로 비워도(=만료 시뮬레이션) 사망 키는 안 살아난다
    st = comment_gen._load_state()
    st["exhausted"] = {}
    comment_gen._save_state(st)
    assert 1 not in comment_gen._live_key_indices()
    assert comment_gen._live_key_indices() == [0, 2]


def test_429는_예전처럼_TTL로만_잠긴다(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    quota = Exception("429 RESOURCE_EXHAUSTED quota exceeded")
    comment_gen._mark_key_exhausted(0, 60, exc=quota)
    assert 0 not in comment_gen._live_key_indices()
    st = comment_gen._load_state()
    st["exhausted"] = {}                       # 만료되면 돌아와야 한다
    comment_gen._save_state(st)
    assert 0 in comment_gen._live_key_indices()
    assert not comment_gen._dead_fingerprints()


def test_사망표시는_풀_순서가_바뀌어도_따라간다(tmp_path, monkeypatch):
    """회원 키가 합류하면 idx가 밀린다 — 지문으로 남겨야 엉뚱한 키를 막지 않는다."""
    _setup(tmp_path, monkeypatch)
    comment_gen._mark_key_exhausted(
        1, 60, exc=Exception("401 UNAUTHENTICATED"))
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["NEW", "AAAA", "BBBB", "CCCC"])
    live = comment_gen._live_key_indices()
    assert 2 not in live                      # BBBB(사망)가 idx 2로 밀렸어도 계속 제외
    assert live == [0, 1, 3]
