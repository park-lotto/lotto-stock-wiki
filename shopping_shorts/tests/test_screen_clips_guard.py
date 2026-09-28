# -*- coding: utf-8 -*-
"""완성본 컷 = 편집 화면 컷 — 렌더가 그 약속을 조용히 깨지 못하게 지키는 검사(2026-09-27).

1) 렌더는 편성표를 고쳐 쓰지 않는다: run_render가 warm 뒤에 cut_rhythm·phrase_min_cut 표식을 달면 칸 키가 달라져
   화면 컷 캐시가 빗나가고 **최종 렌더만** 서버 예비 계산으로 떨어졌다(미리보기·캡컷·ZIP엔 그 호출이 없었다).
2) 조용한 되돌아가기 금지: 화면 데이터가 있는 job인데 예비 계산으로 떨어지면 FALLBACK 경보가 남는다.
   화면 데이터가 없는 옛 job은 예비 계산이 정상이라 경보가 없다.
3) warm 뒤 칸을 고치면 BEAT_MUTATED 경보.
"""
import json
from pathlib import Path

import pytest

from shopping_shorts import clean_base as cb
from shopping_shorts import mix_pipeline as mp
from shopping_shorts import screen_clips as sc
from shopping_shorts import video_assemble as va


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    """screen_clips 전역 상태를 테스트마다 비운다(다른 테스트·다른 job과 섞이지 않게)."""
    for name in ("FALLBACKS",):
        monkeypatch.setattr(sc, name, [])
    for name in ("_CACHE", "_DATA_SEEN", "_JOB_STATE", "_OWNER"):
        monkeypatch.setattr(sc, name, {})
    monkeypatch.setattr(sc, "_SEEN", set())
    monkeypatch.setenv("SCREEN_CLIPS", "1")


class _Store:
    """컷 리듬·구절 하한 스위치가 **켜진** 가게 — 옛 렌더 시점 표식이 살아 있으면 반드시 붙는 조건."""
    def __init__(self, job, clean_on):
        self.job = job; self.updates = []; self.clean_on = clean_on
    def get_mix_job(self, jid): return self.job
    def update_mix_job(self, jid, **kw): self.updates.append(kw); self.job.update(kw)
    def get_setting(self, k, d=None):
        if k == "clean_base_enabled":
            return "1" if self.clean_on else ""
        if k == "cut_rhythm_enabled":
            return "1"
        if k == "phrase_min_cut":
            return "1.5"
        return d


def _setup(work, clean_on):
    tts = str(work / "tts" / "b0.mp3")
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "narration": "a", "tts_path": tts,
                       "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0},
                       "alternates": []}]}
    job = {"job_id": "j", "edit_plan": plan, "urls": ["u"], "subtitle_removal": 1 if clean_on else 0,
           "customer_id": 0, "clean_status": "ready"}
    work.mkdir(parents=True, exist_ok=True)
    (work / "s0").mkdir(); (work / "s0" / "v.mp4").write_bytes(b"v" * 4096)
    if clean_on:
        (work / "final_clean_abc.mp4").write_bytes(b"c" * 4096)
        cb.save_base(work, sig="abc", path=str(work / "final_clean_abc.mp4"), plan=plan,
                     cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    return job


def _patch_render(monkeypatch, store, mutate=None):
    monkeypatch.setattr(mp, "Store", lambda db: store)
    monkeypatch.setattr(mp, "_job_customer_id", lambda db, jid: 0)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp.pron_corrections, "load", lambda s: {})
    monkeypatch.setattr(mp, "_vmake_keys", lambda s, c: ["k"])
    monkeypatch.setattr(mp, "_vmake_clean", lambda *a, **k: pytest.fail("VMake가 불렸다"))
    monkeypatch.setattr(mp, "resolve_deco_media", lambda d, w: {})
    monkeypatch.setattr(mp, "_template_layer", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_scene_mask_layers", lambda *a, **k: [])
    monkeypatch.setattr(mp, "_resolve_cutaway_paths", lambda *a, **k: {})
    monkeypatch.setattr(mp, "ensure_faststart", lambda p: None)

    def _sfx(store_, plan, cid, job=None):
        if mutate:
            mutate(plan)
        return {}
    monkeypatch.setattr(mp, "_resolve_sfx_paths", _sfx)
    got = {}

    def _assemble(plan, tts, paths, out, clean_fn=None, **kw):
        got["plan"] = plan
        Path(out).write_bytes(b"f" * 4096)
        return out
    monkeypatch.setattr(mp, "assemble", _assemble)
    return got


# ── 1) 렌더 시점 표식이 더는 붙지 않는다 ───────────────────────────────────────────────
@pytest.mark.parametrize("clean_on", [False, True], ids=["원본소스", "청소본정본"])
def test_run_render_does_not_add_markers_after_warm(tmp_path, monkeypatch, clean_on):
    work = tmp_path / "j"
    job = _setup(work, clean_on)
    store = _Store(job, clean_on)
    monkeypatch.setattr(sc, "_scene_data", lambda jid: None)      # 옛 job처럼(app import 없이)
    got = _patch_render(monkeypatch, store)
    mp.run_render("j", "db", tmp_path)
    assert store.job.get("status") == "done", store.job.get("error")
    for b in got["plan"]["beats"]:
        assert "cut_rhythm" not in b, "렌더가 warm 뒤에 cut_rhythm 표식을 달았다(화면 컷 캐시가 빗나간다)"
        assert "phrase_min_cut" not in b, "렌더가 warm 뒤에 phrase_min_cut 표식을 달았다"
    assert not [e for e in sc.FALLBACKS if e["kind"] == "BEAT_MUTATED"]
    # DB 편성표에도 렌더가 표식을 박지 않았다
    assert all("cut_rhythm" not in b for b in store.job["edit_plan"]["beats"])


# ── 2) 조용한 되돌아가기 → 경보 ───────────────────────────────────────────────────────
class _Proc:
    def __init__(self, rc, out="", err=""):
        self.returncode = rc; self.stdout = out; self.stderr = err


def _screen_job(jid, tmp_path):
    b = {"beat_idx": 0, "phrase_sync": None, "narration": "가 나 다", "tts_path": str(tmp_path / jid / "b0.mp3"),
         "primary": {"video_id": "s0", "seg_id": "a", "start": 1.0, "end": 4.0}, "alternates": []}
    return {"job_id": jid, "edit_plan": {"beats": [b]}}


def _fake_node(monkeypatch, rc=0):
    res = [{"t": 2.0, "c": [{"v": "s0", "s": 1.0, "d": 2.0, "sd": 2.0, "fit": 0}]}]
    monkeypatch.setattr(sc.subprocess, "run", lambda *a, **k: _Proc(rc, json.dumps(res), "boom" if rc else ""))


def test_fallback_recorded_when_screen_data_exists(tmp_path, monkeypatch, capsys):
    job = _screen_job("jA", tmp_path)
    monkeypatch.setattr(sc, "_scene_data", lambda jid: {"beats": [{"x": 1}]})
    _fake_node(monkeypatch)
    assert sc.warm(job) == 1
    beat = job["edit_plan"]["beats"][0]
    # 화면 컷이 그대로 쓰일 때는 경보가 없다
    assert all(c.get("screen") for c in va.plan_beat_clips_for(beat, 2.0, {"s0": 30.0}))
    assert sc.FALLBACKS == []
    # warm 뒤 칸을 고치면 키가 빗나가 예비 계산 — 조용하지 않다
    beat["cut_rhythm"] = {"max_shot": 4.0, "hold": False}
    got = va.plan_beat_clips_for(beat, 2.0, {"s0": 30.0})
    assert got and not any(c.get("screen") for c in got)           # 렌더는 계속 진행(막지 않는다)
    fb = sc.fallbacks_for("jA")
    assert [(e["kind"], e["beat"], e["why"]) for e in fb] == [("FALLBACK", 0, "no_screen_cut")]
    assert "[screen_clips] FALLBACK job=jA beat=0 why=no_screen_cut" in capsys.readouterr().err
    # 같은 렌더 안에서 같은 칸을 또 불러도 한 번만 기록
    va.plan_beat_clips_for(beat, 2.0, {"s0": 30.0})
    assert len(sc.fallbacks_for("jA")) == 1


def test_fallback_on_unreadable_source(tmp_path, monkeypatch):
    job = _screen_job("jS", tmp_path)
    monkeypatch.setattr(sc, "_scene_data", lambda jid: {"beats": [{"x": 1}]})
    _fake_node(monkeypatch)
    sc.warm(job)
    beat = job["edit_plan"]["beats"][0]
    assert sc.lookup(beat, 2.0, {"s0": 0.0}) is None
    assert [e["why"] for e in sc.fallbacks_for("jS")] == ["src_unreadable s0"]


def test_node_failure_is_alarmed(tmp_path, monkeypatch, capsys):
    job = _screen_job("jN", tmp_path)
    monkeypatch.setattr(sc, "_scene_data", lambda jid: {"beats": [{"x": 1}]})
    _fake_node(monkeypatch, rc=1)
    assert sc.warm(job) == 0
    va.plan_beat_clips_for(job["edit_plan"]["beats"][0], 2.0, {"s0": 30.0})
    whys = [(e["beat"], e["why"]) for e in sc.fallbacks_for("jN")]
    assert whys[0][0] is None and whys[0][1].startswith("node_fail rc=1")
    assert whys[1] == (0, "warm_failed(node rc=1)")
    assert "FALLBACK job=jN" in capsys.readouterr().err


def test_no_screen_data_job_is_not_alarmed(tmp_path, monkeypatch, capsys):
    job = _screen_job("jOld", tmp_path)
    monkeypatch.setattr(sc, "_scene_data", lambda jid: None)      # api_mix_scene_lab_data 404 = 옛 job
    monkeypatch.setattr(sc.subprocess, "run", lambda *a, **k: pytest.fail("데이터 없는데 node를 돌렸다"))
    assert sc.warm(job) == 0
    beat = job["edit_plan"]["beats"][0]
    beat["cut_rhythm"] = {"max_shot": 4.0, "hold": False}
    assert va.plan_beat_clips_for(beat, 2.0, {"s0": 30.0})          # 예비 계산은 정상 동작
    assert sc.fallbacks_for("jOld") == []
    err = capsys.readouterr().err
    assert "FALLBACK" not in err and "info job=jOld" in err


# ── 3) warm 뒤 칸 변형 감시 ──────────────────────────────────────────────────────────
def test_check_mutation_names_changed_keys():
    plan = {"beats": [{"beat_idx": 0, "narration": "a", "fit": 1}, {"beat_idx": 1, "narration": "b"}]}
    before = sc.snapshot(plan)
    plan["beats"][0]["fit"] = 9                       # 컷에 무관한 필드(_VOLATILE)는 변형이 아니다
    plan["beats"][1]["cut_rhythm"] = {"hold": True}
    plan["beats"][1]["narration"] = "c"
    assert sc.check_mutation("jM", before, plan) == [(1, ["cut_rhythm", "narration"])]
    assert [(e["kind"], e["beat"], e["why"]) for e in sc.fallbacks_for("jM")] == \
        [("BEAT_MUTATED", 1, "cut_rhythm,narration")]


def test_run_render_records_beat_mutated(tmp_path, monkeypatch, capsys):
    work = tmp_path / "j"
    job = _setup(work, clean_on=False)
    store = _Store(job, clean_on=False)
    monkeypatch.setattr(sc, "_scene_data", lambda jid: None)

    def _mutate(plan):          # warm 뒤·assemble 앞에서 누군가 칸을 고쳐 쓴다
        plan["beats"][0]["cut_rhythm"] = {"max_shot": 4.0, "hold": True}
    got = _patch_render(monkeypatch, store, mutate=_mutate)
    mp.run_render("j", "db", tmp_path)
    assert store.job.get("status") == "done", store.job.get("error")   # 막지 않는다
    assert got["plan"]["beats"][0]["cut_rhythm"]["hold"] is True
    mut = [e for e in sc.fallbacks_for("j") if e["kind"] == "BEAT_MUTATED"]
    assert [(e["beat"], e["why"]) for e in mut] == [(0, "cut_rhythm")]
    err = capsys.readouterr().err
    assert "[screen_clips] BEAT_MUTATED job=j beat=0 keys=cut_rhythm" in err
    assert "[screen_clips] SUMMARY job=j" in err


# ── 4) 렌더 안 훅 시작점 이동 제거(렌더는 편성표를 고쳐 쓰지 않는다) ──────────────────────
class _Stop(Exception):
    pass


def test_render_mix_does_not_move_hook_start(tmp_path, monkeypatch):
    from shopping_shorts import scene_cut
    monkeypatch.setattr(scene_cut, "peak_time_in_window", lambda *a, **k: 2.0)   # 옮긴다면 0.0 → 2.0
    def _halt(*a, **k):
        raise _Stop()
    monkeypatch.setattr(va, "_important_beat_indices", _halt)                      # 조립 본체는 돌리지 않는다
    plan = {"beats": [{"beat_idx": 0, "narration": "a",
                       "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 5.0}, "alternates": []}]}
    with pytest.raises(_Stop):
        va._render_mix(plan, {}, {"s0": str(tmp_path / "s0.mp4")}, tmp_path)
    prim = plan["beats"][0]["primary"]
    assert prim["start"] == 0.0, "렌더(_render_mix)가 훅 시작점을 옮겼다"
    assert "hook_orig_start" not in prim and "hook_peak_at" not in prim


def test_hook_inpoint_at_plan_stage_ignores_screen_cache(tmp_path, monkeypatch):
    """편성 단계(run_clean_sources) 호출은 프로세스 캐시(화면 컷이 앞서 warm됐나)에 따라 갈리면 안 된다."""
    from shopping_shorts import scene_cut
    monkeypatch.setattr(scene_cut, "peak_time_in_window", lambda *a, **k: 2.0)
    plan = {"beats": [{"beat_idx": 0, "narration": "a",
                       "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 5.0}, "alternates": []}]}
    sc._CACHE[sc.beat_key(plan["beats"][0])] = {"t": 2.0, "c": [{"v": "s0", "s": 0.0, "d": 2.0}]}
    va._apply_hook_inpoint(plan, {"s0": str(tmp_path / "s0.mp4")}, tmp_path)
    assert plan["beats"][0]["primary"]["start"] == 2.0


# ── 5) 관리자 쪽지(ops_alert) — job당 1건, 이후 경보 0이면 그 job 배너를 닫는다 ─────────────
def _capture_alerts(monkeypatch, open_alerts=()):
    from shopping_shorts import ops_alert
    calls = {"raise": [], "resolve": []}
    monkeypatch.setattr(ops_alert, "raise_alert",
                        lambda kind, title, detail="", **kw: calls["raise"].append((kind, title, detail, kw)) or True)
    monkeypatch.setattr(ops_alert, "resolve_kind", lambda kind, store=None: calls["resolve"].append(kind) or 1)
    monkeypatch.setattr(ops_alert, "list_alerts", lambda limit=20, store=None: list(open_alerts))
    monkeypatch.setattr(sc, "_ALERT_RESOLVE_IN_PYTEST", True)
    return calls


def test_alert_raised_once_per_job_with_all_reasons(tmp_path, monkeypatch):
    calls = _capture_alerts(monkeypatch)
    job = _screen_job("jAl", tmp_path)
    monkeypatch.setattr(sc, "_scene_data", lambda jid: {"beats": [{"x": 1}]})
    _fake_node(monkeypatch)
    mark = sc.begin("jAl")
    sc.warm(job)
    beat = job["edit_plan"]["beats"][0]
    before = sc.snapshot(job["edit_plan"])
    beat["cut_rhythm"] = {"hold": True}
    sc.check_mutation("jAl", before, job["edit_plan"])
    va.plan_beat_clips_for(beat, 2.0, {"s0": 30.0})
    sc.summarize("jAl", mark)
    assert len(calls["raise"]) == 1 and calls["resolve"] == []
    kind, title, detail, kw = calls["raise"][0]
    assert kind == "screen_clips_fallback:jAl"
    assert "jAl" in title and "[0]" in title
    assert "no_screen_cut" in title and "BEAT_MUTATED:cut_rhythm" in title
    assert "beat=0" in detail


def test_no_alert_for_clean_or_old_job_and_banner_closed(tmp_path, monkeypatch):
    calls = _capture_alerts(monkeypatch, open_alerts=[{"kind": "screen_clips_fallback:jOld2", "resolved": None}])
    job = _screen_job("jOld2", tmp_path)
    monkeypatch.setattr(sc, "_scene_data", lambda jid: None)      # 옛 job — 예비 계산은 정상
    mark = sc.begin("jOld2")
    sc.warm(job)
    beat = job["edit_plan"]["beats"][0]
    beat["cut_rhythm"] = {"hold": True}
    va.plan_beat_clips_for(beat, 2.0, {"s0": 30.0})
    sc.summarize("jOld2", mark)
    assert calls["raise"] == []                                    # 옛 job은 경보 대상 아님
    assert calls["resolve"] == ["screen_clips_fallback:jOld2"]     # 경보 0 → 그 job의 열린 배너만 닫는다
    # 열린 배너가 없으면 닫기도 안 부른다(settings에 job마다 서명 행이 쌓이지 않게)
    calls2 = _capture_alerts(monkeypatch, open_alerts=[{"kind": "screen_clips_fallback:other", "resolved": None}])
    sc.summarize("jOld2", sc.begin("jOld2"))
    assert calls2["raise"] == [] and calls2["resolve"] == []
