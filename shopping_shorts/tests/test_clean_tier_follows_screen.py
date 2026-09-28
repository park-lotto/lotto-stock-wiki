# -*- coding: utf-8 -*-
"""화면의 자막제거 등급이 서버 job에 반드시 실린다(2026-09-28 사장님 job 7c7434ef581e: 화면 고급 → job 기본).
경로 셋: 새 job 만들 때 · 자막제거 시작 때 · 화면 열 때 동기화. 해석은 app._tier_from_body 한 곳."""
from pathlib import Path
from shopping_shorts import app as A


def test_tier_from_body():
    assert A._tier_from_body({"clean_tier": "pro"}) == "pro"
    assert A._tier_from_body({"clean_tier": "weird"}) == "basic"
    assert A._tier_from_body({}) is None and A._tier_from_body(None) is None


def test_clean_start_saves_screen_tier(monkeypatch):
    job = {"job_id": "j", "edit_plan": {"beats": [{"beat_idx": 0}]}, "customer_id": 7, "clean_status": None,
           "clean_tier": None}
    saved, judged = {}, {}

    class _S:
        def __init__(self, *a): pass
        def get_mix_job(self, j): return job
        def update_mix_job(self, jid, **k): saved.update(k)
        def queue_has_pending(self, *a): return False
        def task_is_alive(self, *a): return False
        def queue_status(self, *a): return None
        def enqueue(self, *a, **k): return 1
    monkeypatch.setattr(A, "Store", _S)
    monkeypatch.setattr(A, "_need_own_key_or_402", lambda *a, **k: None)
    monkeypatch.setattr(A, "_clean_consent_or_409", lambda store, jj, work, body, mode=None: (judged.update(jj), {})[1])
    r = A.api_produce_mix_clean(None, {"job_id": "j", "clean_tier": "pro"})
    assert r.get("ok") and saved.get("clean_tier") == "pro" and judged.get("clean_tier") == "pro"


def test_screen_sends_tier_on_all_three_paths():
    src = (Path(A.__file__).parent / "static" / "produce.html").read_text(encoding="utf-8")
    i = src.index("const _mixBody={"); assert "clean_tier" in src[i:i + 300]              # 새 job
    i = src.index("let _cbody={job_id:myJob"); assert "clean_tier" in src[i:i + 200]      # 자막제거 시작
    assert "subtitle_removal: !!STATE.subtitleRemoval,\n                           clean_tier" in src   # 화면 열 때 동기화
