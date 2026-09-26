# -*- coding: utf-8 -*-
"""청소본 서명 회귀 가드 — 옛 청소본을 **이름이 바뀌었다는 이유로** 다시 지워 과금하지 않는다(2026-09-27).

★무엇이 있었나(서버 실측, 읽기 전용): a8ba0ef6b(09-20)가 _plan_signature 에 `speed=` 항목을 조건 없이
  넣어 그 전 청소본 462개의 파일명 서명이 전부 어긋났다. 그림은 같은데 파일을 못 찾아 재청소 14건(353초).
  최근 14일 job 중 303개는 속도 없는 옛 식으로 계산하면 기존 파일과 정확히 맞았다.
★fixture = 실제 청소 당시 편성 스냅샷(final_clean_{sig}.plan.json)에서 서명에 드는 칸 필드만 남긴 것과
  그 파일의 실제 이름 서명. 누가 서명 식에 **조건 없는 항목**을 더하면 이 테스트가 빨개진다.
"""
import json
from pathlib import Path

import pytest

from shopping_shorts import clean_base as cb
from shopping_shorts import mix_pipeline as mp

FX = Path(__file__).parent / "fixtures"
FIXTURES = sorted(FX.glob("clean_sig_*.json"))


def _load(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    job = {"edit_plan": d["plan"], "clean_tier": d["tier"], "clean_cuts": d.get("clean_cuts")}
    return d, job


def test_fixture가_있다():
    kinds = [json.loads(p.read_text(encoding="utf-8"))["kind"] for p in FIXTURES]
    assert kinds.count("legacy") >= 2 and kinds.count("current") >= 1


@pytest.mark.parametrize("p", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_실제_청소본_파일명_서명이_후보에_있다(p):
    d, job = _load(p)
    assert d["sig"] in mp._clean_sig_candidates(job, d["tier"])


@pytest.mark.parametrize("p", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_실제_파일을_찾는다_과금_0(tmp_path, monkeypatch, p):
    """파일이 있으면 _final_clean_fn 이 과금 없이 그 파일을, 그 파일의 서명으로 정본에 넘긴다."""
    d, job = _load(p)
    f = tmp_path / ("final_clean_%s.mp4" % d["sig"])
    f.write_bytes(b"c" * 4096)
    assert mp._clean_final_found(job, tmp_path, d["tier"]) == (d["sig"], f)
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: pytest.fail("있는 청소본에 과금했다"))
    saved = {}
    monkeypatch.setattr(mp, "_save_clean_base",
                        lambda job, work, sig, path, only_if_new=False: saved.update(sig=sig, path=path, oin=only_if_new))
    out = mp._final_clean_fn(None, job, "j", tmp_path, ["k"], 0)(str(tmp_path / "mix_raw.mp4"))
    assert out == str(f)
    assert saved == {"sig": d["sig"], "path": str(f), "oin": True}
    assert mp.clean_final_path_for_plan(job, tmp_path) == f
    assert mp.clean_tiers_ready(job, tmp_path)[d["tier"]] is True
    assert mp.clean_redo_state(job, tmp_path)["ready"] is True


def test_옛식은_찾기전용_새로_만들땐_현재식(tmp_path, monkeypatch):
    d, job = _load(next(p for p in FIXTURES if "legacy" in p.stem))
    cur = mp._clean_sig(job)
    assert cur != d["sig"] and mp._clean_sig_candidates(job, d["tier"])[0] == cur
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: 1)
    monkeypatch.setattr(mp, "_save_clean_base", lambda *a, **k: None)
    got = {}
    def _vc(src, keys, out, tier=None):
        got["out"] = out; Path(out).write_bytes(b"x" * 2048); return out
    monkeypatch.setattr(mp, "_vmake_clean", _vc)
    mp._final_clean_fn(None, job, "j", tmp_path, ["k"], 0)(str(tmp_path / "mix_raw.mp4"))
    assert Path(got["out"]).name == "final_clean_%s.mp4" % cur


def test_현재식_파일이_옛식보다_먼저(tmp_path):
    d, job = _load(next(p for p in FIXTURES if "legacy" in p.stem))
    cur = mp._clean_sig_candidates(job, d["tier"])[0]
    for s in (d["sig"], cur):
        (tmp_path / ("final_clean_%s.mp4" % s)).write_bytes(b"c" * 4096)
    assert mp._clean_final_found(job, tmp_path, d["tier"])[0] == cur


def test_속도를_바꾼_편성은_옛식을_안_찾는다():
    """속도는 09-20에 처음 생긴 값 — 1.0이 아닌 칸이 있으면 옛 파일은 다른 그림이다."""
    d, job = _load(next(p for p in FIXTURES if "legacy" in p.stem))
    job["edit_plan"]["beats"][0]["sync_speed"] = 1.2
    assert d["sig"] not in mp._clean_sig_candidates(job, d["tier"])
    assert len(mp._clean_sig_candidates(job, d["tier"])) == 1


# ── 버튼 경로도 정본 기준(렌더와 같은 판정 clean_base_judge) ──

class _Store:
    def __init__(self, job): self.job = job; self.updates = []
    def get_mix_job(self, jid): return self.job
    def update_mix_job(self, jid, **kw): self.updates.append(kw); self.job.update(kw)
    def get_setting(self, k, d=None): return "1" if k == "clean_base_enabled" else d


def _base_job(work, tier=None):
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "narration": "a", "tts_path": None,
                       "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []}]}
    job = {"job_id": "j", "edit_plan": plan, "urls": ["u"], "subtitle_removal": 1, "customer_id": 0}
    if tier:
        job["clean_tier"] = tier
    work.mkdir(parents=True, exist_ok=True)
    (work / "s0").mkdir(exist_ok=True); (work / "s0" / "v.mp4").write_bytes(b"v" * 4096)
    # 정본 파일 이름은 **옛 서명**(편성이 그 뒤 자막 줄만 바뀌어 지금 서명과 다르다)
    (work / "final_clean_0123456789abcdef.mp4").write_bytes(b"c" * 4096)
    cb.save_base(work, sig="0123456789abcdef", path=str(work / "final_clean_0123456789abcdef.mp4"), plan=plan,
                 cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    plan["beats"][0]["caption_lines"] = ["a", "b"]      # 서명이 바뀌는 편집(그림 재료는 그대로)
    return job


def _button(monkeypatch, tmp_path, job):
    store = _Store(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_vmake_keys", lambda *a, **k: ["k"])
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    calls = []
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: calls.append("charge") or 1)
    monkeypatch.setattr(mp, "_refund_clean", lambda *a, **k: None)
    monkeypatch.setattr(mp, "assemble_clean_video", lambda *a, **k: calls.append("assemble") or None)
    mp.run_clean_sources("j", "db", str(tmp_path))
    return store, calls


def test_버튼_정본이_덮으면_과금_0(tmp_path, monkeypatch):
    job = _base_job(tmp_path / "j")
    assert mp._clean_final_found(job, tmp_path / "j") is None       # 서명 파일로는 못 찾는 상태
    store, calls = _button(monkeypatch, tmp_path, job)
    assert calls == [] and job["clean_status"] == "ready"
    assert mp.clean_tiers_ready(job, tmp_path / "j")["basic"] is True


def test_버튼_등급이_다르면_정본을_안_쓴다(tmp_path, monkeypatch):
    """고급을 고르고 누른 버튼이 기본 정본으로 끝나면 안 된다 — 종전대로 청소 경로를 탄다."""
    job = _base_job(tmp_path / "j", tier="pro")
    store, calls = _button(monkeypatch, tmp_path, job)
    assert calls == ["assemble"]
    assert mp.clean_tiers_ready(job, tmp_path / "j") == {"basic": True, "pro": False}


def test_버튼_장면이_바뀌면_정본만으로_안_끝낸다(tmp_path, monkeypatch):
    job = _base_job(tmp_path / "j")
    job["edit_plan"]["beats"][0]["scene_override"] = [{"video_id": "s0", "seg_id": "s0-1", "start": 20.0, "end": 22.0}]
    store, calls = _button(monkeypatch, tmp_path, job)
    assert calls == ["assemble"]
