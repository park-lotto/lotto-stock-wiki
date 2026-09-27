# -*- coding: utf-8 -*-
"""워커 주인·전체 재합성 버전·청소 조립본 회귀 가드(2026-09-27).

1) @_owned_job 이 **워커 진입점**에 붙어 있다. 09-02·09-07·09-24에 함수가 데코레이터와 def 사이에 끼어들어
   데코레이터가 plan_signature·humanize_tts_error·_render_stamp 로 밀려났고, run_mix_job·run_preview·
   run_render 는 주인 컨텍스트 없이(cid 0) 돌았다. __wrapped__ 존재만 보면 엉뚱한 데코레이터도 통과하므로
   **_owned_job 의 wrap 코드인지** + **실제로 주인이 열리는지**를 본다.
2) 전체 재합성(resynth_tts_job)도 칸 재합성과 **같은 함수**(_bump_tts_ver)로 tts_ver 를 올린다.
3) 정본 경로에서 clean_video_path = 정본 + 증분 조각(extras)으로 지금 편성을 조립한 것.
"""
import inspect
from pathlib import Path

import pytest

from shopping_shorts import clean_base as cb
from shopping_shorts import keyctx
from shopping_shorts import mix_pipeline as mp
from shopping_shorts.tests import test_clean_sig_legacy as legacy

WORKERS = ("run_mix_job", "retype_mix_job", "assemble_clean_video", "run_clean_sources",
           "run_preview", "run_render", "resynth_tts_job", "resynth_one_beat")


# ── 1. 주인 컨텍스트 ─────────────────────────────────────────────────────────

def _owned_wrap_code():
    return mp._owned_job(lambda db_path=None, job_id=None: None).__code__


@pytest.mark.parametrize("name", WORKERS)
def test_워커_진입점은_owned_job으로_감싸져_있다(name):
    fn = getattr(mp, name)
    assert fn.__code__ is _owned_wrap_code(), f"{name}에 @_owned_job이 없다"
    assert "job_id" in inspect.signature(fn.__wrapped__).parameters
    assert "db_path" in inspect.signature(fn.__wrapped__).parameters


@pytest.mark.parametrize("name", ("humanize_tts_error", "plan_signature", "_render_stamp"))
def test_워커가_아닌_함수엔_owned_job이_없다(name):
    """job_id·db_path 가 없는 함수에 붙으면 주인을 0으로 **덮어써** 바깥 워커의 주인을 지운다."""
    assert not hasattr(getattr(mp, name), "__wrapped__"), f"{name}에 데코레이터가 잘못 붙어 있다"


class _Probe:
    """get_mix_job 이 불리는 순간의 주인을 적고 job 없음으로 끝낸다."""
    def __init__(self, seen): self.seen = seen
    def get_mix_job(self, jid): self.seen.append(keyctx.owner_cid()); return None
    def get_setting(self, k, d=None): return d


@pytest.mark.parametrize("call", [
    lambda: mp.run_mix_job("j", "db", "w"),
    lambda: mp.run_preview("j", "db", "w"),
    lambda: mp.run_render("j", "db", "w"),
    lambda: mp.run_clean_sources("j", "db", "w"),
    lambda: mp.resynth_tts_job("j", "db", "w"),
    lambda: mp.resynth_one_beat("j", 0, {}, "db", "w"),
], ids=["mix", "preview", "render", "clean", "resynth_all", "resynth_one"])
def test_워커는_job_주인으로_돈다(monkeypatch, call):
    seen = []
    monkeypatch.setattr(mp, "Store", lambda p: _Probe(seen))
    monkeypatch.setattr(mp, "_job_customer_id", lambda db, jid: 57)
    monkeypatch.setattr(mp.pron_corrections, "load", lambda s: {})
    assert keyctx.owner_cid() == 0
    call()
    assert seen and set(seen) == {57}
    assert keyctx.owner_cid() == 0          # 끝나면 되돌린다


def test_TTS_칸_스레드도_주인을_안다(monkeypatch, tmp_path):
    """칸 스레드에서 도는 호흡 끊기(제미나이→vertex_route.current_cid)가 cid 0으로 새지 않는다."""
    seen = []
    monkeypatch.setattr(mp, "synthesize_line", lambda *a, **k: seen.append(keyctx.owner_cid()))
    monkeypatch.setattr(mp, "finalize_beat_audio", lambda *a, **k: None)
    monkeypatch.setattr(mp.tts_joined, "enabled", lambda: False)
    beats = [{"beat_idx": i, "narration": "가나다%d" % i} for i in range(4)]
    with keyctx.owner(57):
        mp._synthesize_beats(beats, tmp_path, voice=None)
    assert seen == [57] * 4


# ── 2. 전체 재합성도 tts_ver 를 올린다 ────────────────────────────────────────

class _Store:
    def __init__(self, job): self.job = job; self.updates = []
    def get_mix_job(self, jid): return self.job
    def update_mix_job(self, jid, **kw): self.updates.append(kw); self.job.update(kw)
    def get_setting(self, k, d=None): return d


def test_전체_재합성이_모든_칸_tts_ver를_올린다(monkeypatch, tmp_path):
    plan = {"beats": [{"beat_idx": 0, "narration": "a"}, {"beat_idx": 1, "narration": "b", "tts_ver": 3}]}
    store = _Store({"job_id": "j", "edit_plan": plan, "customer_id": 5})
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp.pron_corrections, "load", lambda s: {})
    mp.resynth_tts_job("j", "db", str(tmp_path))
    saved = store.updates[-1]
    assert saved["status"] == "ready_for_review"
    assert [b.get("tts_ver") for b in saved["edit_plan"]["beats"]] == [1, 4]


def test_전체_재합성_실패면_tts_ver_그대로(monkeypatch, tmp_path):
    plan = {"beats": [{"beat_idx": 0, "narration": "a", "tts_ver": 2}]}
    store = _Store({"job_id": "j", "edit_plan": plan, "customer_id": 5})
    monkeypatch.setattr(mp, "Store", lambda p: store)
    def _boom(*a, **k): raise RuntimeError("401")
    monkeypatch.setattr(mp, "_synthesize_beats", _boom)
    monkeypatch.setattr(mp.pron_corrections, "load", lambda s: {})
    mp.resynth_tts_job("j", "db", str(tmp_path))
    assert store.job["status"] == "failed"
    assert plan["beats"][0]["tts_ver"] == 2


def test_tts_ver_올리는_곳은_한_곳():
    """칸 재합성·전체 재합성이 같은 함수로 올린다(0순위-B) — 따로 `+1`을 적으면 한쪽이 또 빠진다."""
    src = inspect.getsource(mp)
    assert src.count('["tts_ver"] = (') == 1
    assert "_bump_tts_ver(" in inspect.getsource(mp.resynth_one_beat.__wrapped__)
    assert "_bump_tts_ver(" in inspect.getsource(mp.resynth_tts_job.__wrapped__)


# ── 3. clean_video_path = 정본 + 증분 조각으로 지금 편성 조립 ──────────────────

def test_정본_증분_뒤_clean_video_path는_extras_조각으로_조립(tmp_path, monkeypatch):
    work = tmp_path / "j"
    job = legacy._base_job(work)
    job["edit_plan"]["beats"][0]["scene_override"] = [
        {"video_id": "s0", "seg_id": "s0-1", "start": 20.0, "end": 22.0}]
    legacy._incr_fakes(monkeypatch, [])
    store = legacy._Store(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_vmake_keys", lambda *a, **k: ["k"])
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: 1)
    monkeypatch.setattr(mp, "_refund_clean", lambda *a, **k: None)
    got = []

    def _asm(plan, tts_paths, sources, out, clean_fn=None, **k):
        got.append({"plan": plan, "sources": dict(sources), "clean_fn": clean_fn,
                    "burn": k.get("burn_captions")})
        Path(out).write_bytes(b"m" * 2048)
        return out
    monkeypatch.setattr(mp, "assemble", _asm)
    from shopping_shorts.tests._clean_consent import consent
    mp.run_clean_sources("j", "db", str(tmp_path), **consent(store, job, work, "button"))

    extras = cb.load_base(work).get("extras") or {}
    assert "cb0_0" in extras                                  # 증분 조각이 정본에 붙었다
    assert job["clean_status"] == "ready"
    assert len(got) == 1 and got[0]["clean_fn"] is None and got[0]["burn"] is False   # 과금 0 재조립
    srcs = got[0]["sources"]
    base_path = cb.load_base(work)["path"]
    assert base_path in srcs.values()                         # 정본
    assert srcs == cb.source_paths(cb.load_base(work))        # 정본 + 증분 조각(렌더와 같은 재료)
    assert "cb0_0" in srcs and Path(srcs["cb0_0"]).exists()    # 증분 조각
    used = {m.get("video_id") for b in got[0]["plan"]["beats"] for m in (mp._beat_materials(b) or [])}
    assert "cb0_0" in used                                    # 바뀐 칸이 조각을 가리킨다(정본 파일 통째가 아니다)
    assert job["clean_video_path"] == str(work / "clean_preview.mp4")


def test_정본_그대로_버튼도_clean_video_path를_채운다(tmp_path, monkeypatch):
    work = tmp_path / "j"
    job = legacy._base_job(work)
    store = legacy._Store(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_vmake_keys", lambda *a, **k: ["k"])
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: pytest.fail("정본이 덮는데 과금했다"))
    got = []
    monkeypatch.setattr(mp, "assemble",
                        lambda plan, t, sources, out, clean_fn=None, **k:
                        got.append(dict(sources)) or Path(out).write_bytes(b"m" * 2048))
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job["clean_status"] == "ready"
    assert len(got) == 1 and cb.load_base(work)["path"] in got[0].values()
    assert job["clean_video_path"] == str(work / "clean_preview.mp4")
