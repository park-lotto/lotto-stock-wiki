# -*- coding: utf-8 -*-
"""청소본 정본의 컷 지도 = **그 청소본을 만든** 완성본 컷 계획(video_assemble.render_cut_plan) (2026-09-27).

사고(ec038d16ee0f, cid 591): 자막제거 버튼 → 조립(13:12) → 업체 청소 3분 → 정본 저장(13:15). 저장할 때 컷 지도를
**그때 편성으로 다시 계산**(final_clip_pairs)했는데 그 사이 고객이 장면을 바꿔, 지도는 새 편성 컷·파일은 옛 편성 컷이었다
→ 완성본(정본 좌표 재생) 7/12칸이 다른 장면. 또 그 조립 경로엔 화면 컷 준비(screen_clips.warm)가 없어 서버 예비 계산으로 짰다.
여기서는: ① final_clip_pairs = cut_map_of(render_cut_plan) (자체 계산 없음) ② 정본은 조립본 옆 컷 지도를 쓴다(청소 중 편성이
바뀌어도 파일과 같은 지도) ③ 청소 조립 전에 화면 컷을 준비한다.
"""
import copy
import json
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp, video_assemble as va

_DURS = {"s0": 30.0, "s1": 40.0}
_TTS = {0: "/t/b0.mp3", 1: "/t/b1.mp3", 2: "/t/b2.mp3"}


def _plan():
    return {"beats": [
        # 손 컷(구절 맞춤 끔) — 조각 두 개를 손으로 나눈 칸
        {"beat_idx": 0, "narration": "a", "phrase_sync": False,
         "scene_override": [{"video_id": "s0", "seg_id": "s0-a", "start": 1.0, "end": 3.0},
                            {"video_id": "s1", "seg_id": "s1-a", "start": 5.0, "end": 7.0}],
         "manual_cuts": [{"video_id": "s0", "seg_id": "s0-a", "start": 1.0, "dur": 1.4},
                         {"video_id": "s1", "seg_id": "s1-a", "start": 5.0, "dur": 1.6}]},
        # 컷 리듬 홀드 칸
        {"beat_idx": 1, "narration": "b", "cut_rhythm": {"hold": True},
         "primary": {"video_id": "s0", "seg_id": "s0-b", "start": 10.0, "end": 11.0},
         "alternates": [{"video_id": "s1", "seg_id": "s1-b", "start": 20.0, "end": 22.0}]},
        # 구절 맞춤 칸
        {"beat_idx": 2, "narration": "c. d.", "phrase_sync": True, "cap_durs": [1.0, 1.2],
         "primary": {"video_id": "s1", "seg_id": "s1-c", "start": 30.0, "end": 32.0},
         "alternates": [{"video_id": "s0", "seg_id": "s0-c", "start": 15.0, "end": 17.0}]}]}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SCREEN_CLIPS", "0")
    durs = {"/t/b0.mp3": 3.0, "/t/b1.mp3": 2.5, "/t/b2.mp3": 2.2}
    monkeypatch.setattr(va, "_probe_duration", lambda p: durs.get(str(p), 0.0))
    return monkeypatch


def test_final_clip_pairs_is_render_cut_plan_frames(env):
    """손 컷·리듬 홀드·구절 맞춤 칸 모두 — 컷 지도 = 렌더 컷 계획(프레임 자리) 그대로."""
    plan = _plan()
    got = mp.final_clip_pairs(plan, _TTS, _DURS)
    want = va.cut_map_of(va.render_cut_plan(plan, _TTS, {v: v for v in _DURS}, src_durs=_DURS, probe=lambda p: 0.0))
    assert got == want and len(got) >= 4
    for c in got:                                     # 완성본 자리는 프레임 격자
        assert abs(c["fin"] * 30 - round(c["fin"] * 30)) < 1e-6 and abs(c["dur"] * 30 - round(c["dur"] * 30)) < 1e-6


def test_final_clip_pairs_calls_render_cut_plan(env):
    seen = []
    real = va.render_cut_plan
    env.setattr(va, "render_cut_plan", lambda *a, **k: seen.append(1) or real(*a, **k))
    mp.final_clip_pairs(_plan(), _TTS, _DURS)
    assert seen, "컷 지도가 완성본 컷 계획을 안 탄다 — 두 벌"


def test_cut_map_roundtrip_and_stale_guard(tmp_path, env):
    plan = _plan()
    cplan = va.render_cut_plan(plan, _TTS, {v: v for v in _DURS}, src_durs=_DURS, probe=lambda p: 0.0)
    v = tmp_path / "mix_raw.mp4"
    v.write_bytes(b"x")
    va.write_cut_map(v, cplan)
    assert va.read_cut_map(v) == va.cut_map_of(cplan)
    import os
    import time
    t = time.time()
    os.utime(v.with_suffix(va.CUT_MAP_SUFFIX), (t - 100, t - 100))    # 지도가 영상보다 한참 오래됐다 = 다른 조립의 지도
    os.utime(v, (t, t))
    assert va.read_cut_map(v) is None


def test_clean_base_uses_map_of_assembled_file_even_if_plan_changed(tmp_path, env):
    """★사고 재현: 조립본을 만든 뒤(지도 기록) 청소 중에 편성이 바뀌어도, 정본 지도는 **파일을 만든 계획**이어야 한다."""
    work = tmp_path / "w"
    work.mkdir()
    plan_old = _plan()
    cplan = va.render_cut_plan(plan_old, _TTS, {v: v for v in _DURS}, src_durs=_DURS, probe=lambda p: 0.0)
    mix_raw = work / "mix_raw.mp4"
    mix_raw.write_bytes(b"raw")
    va.write_cut_map(mix_raw, cplan)
    plan_new = copy.deepcopy(plan_old)                 # 고객이 청소 도중 1칸 장면을 바꿨다
    plan_new["beats"][1]["primary"] = {"video_id": "s1", "seg_id": "s1-z", "start": 33.0, "end": 36.0}
    plan_new["beats"][1].pop("alternates")
    job = {"job_id": "j", "subtitle_removal": 1, "edit_plan": plan_new, "urls": ["a", "b"], "customer_id": 0}
    env.setattr(mp, "_charge_clean", lambda *a, **k: 0)
    env.setattr(mp, "_clean_final_found", lambda *a, **k: None)

    def fake_vmake(src, keys, out, tier=None, resume_key=None):
        Path(out).write_bytes(Path(src).read_bytes())
        return out
    env.setattr(mp, "_vmake_clean", fake_vmake)
    env.setattr(mp, "final_clip_pairs", lambda *a, **k: (_ for _ in ()).throw(AssertionError("청소 뒤 지도를 다시 계산했다")))
    fn = mp._final_clean_fn(None, job, "j", work, ["k"], 0)
    fn(str(mix_raw))
    base = json.loads((work / "clean_base.json").read_text(encoding="utf-8"))
    got = [(c["video_id"], c["beat_idx"], round(c["src"], 3), round(c["fin"], 4)) for c in base["cuts"]]
    want = [(c["video_id"], c["beat_idx"], round(c["src"], 3), round(c["fin"], 4)) for c in va.cut_map_of(cplan)]
    assert got == want


def test_clean_assembly_warms_screen_cuts_first(tmp_path, env):
    """자막제거 조립(완성본 1편 청소) 전에 화면 컷을 준비한다 — 안 하면 서버 예비 계산 컷으로 유료 청소본을 만든다."""
    from shopping_shorts import screen_clips as sc
    order = []
    env.setattr(sc, "warm", lambda job: order.append("warm") or 0)
    env.setattr(mp, "assemble", lambda *a, **k: order.append("assemble"))
    env.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "/x/s0.mp4"})
    env.setattr(mp, "_resolve_cutaway_paths", lambda *a, **k: {})
    env.setattr(mp, "_resolve_sfx_paths", lambda *a, **k: {})

    class _St:
        def __init__(self, *_a):
            pass

        def get_mix_job(self, _j):
            return {"job_id": "j", "edit_plan": _plan(), "customer_id": 0}

        def update_mix_job(self, *_a, **_k):
            pass
    env.setattr(mp, "Store", _St)
    mp.assemble_clean_video("j", "db", str(tmp_path), clean_fn=lambda p: p)
    assert order[:2] == ["warm", "assemble"], order


# ── 이미 틀리게 만든 정본을 판정 입구가 스스로 바로잡는다(스냅샷 편성에서 유도) ─────────────────────────

def _mkv(path, dur, hue=0):
    import subprocess
    vf = "vflip,negate,hue=h=%d" % hue if hue else "null"      # 두 원본이 밝기 모양부터 달라야 한다(두 띠 거리가 둘 다 잰다)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x284:r=30:d=%s" % dur,
                    "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _healing_env(tmp_path, env):
    """실제 영상: 원본 s0(testsrc2)·s1(색 돌린 testsrc2) + 청소 당시 편성(스냅샷)의 컷 지도대로 이어 붙인 '청소본'.
    그 뒤 편성이 바뀌어(1칸) 틀린 지도(지금 편성으로 계산)가 정본에 저장된 상황."""
    import subprocess
    work = tmp_path / "w"
    real_probe = mp._probe_duration          # 원래 probe(env 고정물이 va._probe_duration 을 이미 바꿨다)
    for v, d, h in (("s0", 30, 0), ("s1", 40, 120)):
        (work / v).mkdir(parents=True)
        _mkv(work / v / "src.mp4", d, h)
    tts, durs = {}, {}
    for i, d in enumerate((3.0, 2.5, 2.2)):
        f = tmp_path / ("b%d.mp3" % i)
        f.write_bytes(b"x")
        durs[str(f)] = d
        tts[i] = str(f)
    env.setattr(va, "_probe_duration", lambda p: durs[str(p)] if str(p) in durs else real_probe(p))
    plan_old = _plan()
    for b in plan_old["beats"]:
        b["tts_path"] = tts[b["beat_idx"]]
    (work / "final_clean_SIG.plan.json").write_text(json.dumps(dict(plan_old, _clean_sel=None)), encoding="utf-8")
    plan_new = copy.deepcopy(plan_old)                 # 청소 도중 2칸 장면을 바꿨다
    plan_new["beats"][1]["primary"] = {"video_id": "s1", "seg_id": "s1-z", "start": 33.0, "end": 36.0}
    plan_new["beats"][1].pop("alternates")
    plan_new["beats"][2]["primary"] = {"video_id": "s0", "seg_id": "s0-y", "start": 24.0, "end": 27.0}
    plan_new["beats"][2]["alternates"] = [{"video_id": "s1", "seg_id": "s1-y", "start": 2.0, "end": 4.0}]
    job = {"job_id": "j", "subtitle_removal": 1, "edit_plan": plan_new, "urls": ["a", "b"], "customer_id": 0}
    srcs = mp._resolve_sources(job, work)
    right = va.cut_map_of(va.render_cut_plan(plan_old, tts, srcs, screen=False))
    wrong = va.cut_map_of(va.render_cut_plan(plan_new, tts, srcs, screen=False))
    parts = []
    for i, c in enumerate(right):                      # 청소본 = 스냅샷 지도대로 원본 조각을 1배속으로 이어 붙임
        q = tmp_path / ("p%02d.mp4" % i)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % c["src"], "-i", srcs[c["video_id"]],
                        "-frames:v", str(int(round(c["dur"] * 30))), "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(q)], check=True, capture_output=True, stdin=subprocess.DEVNULL)
        parts.append(q)
    lst = tmp_path / "l.txt"
    lst.write_text("".join("file '%s'" % q.as_posix() + chr(10) for q in parts), encoding="utf-8")
    clean = work / "final_clean_SIG.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(clean)],
                       capture_output=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-600:]
    base = {"sig": "SIG", "path": str(clean), "extras": {}, "frame_exact": True,
            "cuts": [dict(c, cleaned=True) for c in wrong], "beat_keys": {}}
    return work, job, base, right, wrong, tts, srcs


def test_heal_rederives_map_from_snapshot(tmp_path, env):
    work, job, base, right, wrong, tts, srcs = _healing_env(tmp_path, env)
    assert right != wrong
    healed = mp.heal_base_map(job, work, base)
    key = lambda cs: [(c["video_id"], c["beat_idx"], round(c["src"], 3), round(c["fin"], 4)) for c in cs]  # noqa: E731
    assert key(healed["cuts"]) == key(right) and healed["cut_map"] == "snapshot"
    assert json.loads((work / "clean_base.json").read_text(encoding="utf-8"))["cut_map"] == "snapshot"
    assert healed["healed"]["scene_ok_new"] > healed["healed"]["scene_ok_old"]
    # 맞는 정본은 지도를 안 바꾼다(한 번 확인했다는 표시만)
    ok = dict(base, cuts=[dict(c, cleaned=True) for c in right])
    kept = mp.heal_base_map(job, work, ok)
    assert kept["cut_map"] == "verified" and kept["cuts"] == ok["cuts"]


def test_healed_base_covers_only_unchanged_beats_with_same_scene(tmp_path, env):
    """바로잡은 뒤: 바뀐 칸(1·2)은 uncovered(증분 청소 = 바뀐 장면만 과금), 안 바뀐 칸은 **같은 원본 장면**을 청소본에서 튼다.
    틀린 지도 그대로면 1칸도 '덮였다'고 보고 엉뚱한 청소본 자리를 틀었다(다른 장면)."""
    from shopping_shorts import clean_base as cb
    work, job, base, right, wrong, tts, srcs = _healing_env(tmp_path, env)
    plan_new = job["edit_plan"]
    tts_durs = {i: va._probe_duration(tts[i]) for i in tts}
    src_durs = {v: va._probe_duration(p) for v, p in srcs.items()}
    _p, unc_wrong, _ = cb.remap_plan(plan_new, base, tts_durs=tts_durs, src_durs=src_durs)
    assert 1 not in unc_wrong and 2 not in unc_wrong    # 사고 모양: 틀린 지도는 바뀐 칸도 덮였다고 본다
    healed = mp.heal_base_map(job, work, base)
    plan2, unc, _ = cb.remap_plan(plan_new, healed, tts_durs=tts_durs, src_durs=src_durs)
    assert unc == [1, 2]
    regs = cb._regions(healed)
    want = {bp["idx"]: [(cp["video_id"], round(cp["start"], 2)) for cp in bp["clips"]]
            for bp in va.render_cut_plan(plan_new, tts, srcs, screen=False)}
    for b in plan2["beats"]:
        if b["beat_idx"] in (1, 2):
            continue
        got = [(mp.clean_origin(regs, c["video_id"], c["start"], c.get("seg_id"))[0],
                round(mp.clean_origin(regs, c["video_id"], c["start"], c.get("seg_id"))[1], 2)) for c in b["manual_cuts"]]
        assert got == want[b["beat_idx"]], (b["beat_idx"], got, want[b["beat_idx"]])


def test_save_base_without_assembled_map_uses_snapshot_not_current_plan(tmp_path, env):
    work, job, base, right, wrong, tts, srcs = _healing_env(tmp_path, env)
    env.setattr(mp, "final_clip_pairs", lambda *a, **k: (_ for _ in ()).throw(AssertionError("지금 편성으로 계산했다")))
    mp._save_clean_base(job, work, "SIG", str(work / "final_clean_SIG.mp4"))
    saved = json.loads((work / "clean_base.json").read_text(encoding="utf-8"))
    assert saved["cut_map"] == "snapshot"
    assert [(c["video_id"], round(c["src"], 3)) for c in saved["cuts"]] == [(c["video_id"], round(c["src"], 3)) for c in right]


def test_judge_entry_heals_before_judging(tmp_path, env):
    """판정 입구(clean_base_judge)가 바로잡은 정본으로 판정한다 — 렌더·버튼·안내가 전부 이 입구를 지난다."""
    from shopping_shorts import clean_base as cb
    work, job, base, right, wrong, tts, srcs = _healing_env(tmp_path, env)
    env.setattr(mp, "clean_base_on", lambda *a, **k: True)
    env.setattr(cb, "load_base", lambda w: copy.deepcopy(base))
    env.setattr(cb, "calibrate", lambda w, b, s: b)
    env.setattr(mp, "clean_tts_durs", lambda plan: {i: va._probe_duration(tts[i]) for i in tts})
    env.setattr(mp, "_src_durs_for", lambda job, work: {v: va._probe_duration(p) for v, p in srcs.items()})
    out = mp.clean_base_judge(None, job, work)
    assert out["base"].get("cut_map") == "snapshot" and out["uncovered"] == [1, 2]
