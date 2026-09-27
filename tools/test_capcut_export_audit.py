# -*- coding: utf-8 -*-
"""tools/capcut_export_audit.py — 대조가 실제로 어긋남을 잡는지 + 캡컷·ZIP 이 완성본 컷 계획을 그대로 싣는지(가짜 편성표, DB 없이).

① 완성본 컷 = render_cuts(video_assemble.render_cut_plan — 렌더가 굽는 계획), ② 캡컷 = capcut_draft.build_draft 가 만든 초안의
영상 트랙(영상 조각 + 정지 사진 조각), ③ 내보내기 = export_bundle._beat_source_clips 가 _cut_clip 에 넘긴 구간 — 셋 다 라이브 함수.
"""
import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("capcut_export_audit", ROOT / "tools" / "capcut_export_audit.py")
aud = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aud)

from shopping_shorts import capcut_draft as cd, export_bundle as eb, video_assemble as va  # noqa: E402

_SRC = {"s0": "/real/s0.mp4", "s1": "/real/s1.mp4"}
_DURS = {"/real/s0.mp4": 10.0, "/real/s1.mp4": 8.0, "/real/b0.mp3": 2.0, "/real/b1.mp3": 1.5, "/real/b2.mp3": 2.4}
_TTS = {0: "/real/b0.mp3", 1: "/real/b1.mp3", 2: "/real/b2.mp3"}
_PLAN = {"beats": [
    {"beat_idx": 0, "role": "훅", "narration": "첫 장면", "primary": {"video_id": "s0", "start": 0.0, "end": 2.0}},
    {"beat_idx": 1, "role": "본문", "narration": "둘째 장면", "primary": {"video_id": "s1", "start": 1.0, "end": 2.5}},
    {"beat_idx": 2, "role": "본문", "narration": "셋째 장면", "primary": {"video_id": "s0", "start": 4.0, "end": 6.4}},
]}
# 셋째 칸: 재료 0.6초에 음성 2.4초 → 완성본은 느리게(1.15배)+마지막 프레임 정지
_PLAN_FREEZE = copy.deepcopy(_PLAN)
_PLAN_FREEZE["beats"][2].update(phrase_sync=False, manual_cuts=[
    {"video_id": "s0", "seg_id": "s0-0", "start": 4.0, "dur": 2.4, "sdur": 0.6}])   # 화면 컷: 0.6초를 2.4초 칸에


def _asset():
    return {p: "C:/cap/p/" + Path(p).name for p in list(_SRC.values()) + list(_TTS.values())}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SCREEN_CLIPS", "0")          # 화면 데이터 없음 = 서버 계산(렌더·캡컷·ZIP 모두 같은 계획)
    monkeypatch.setattr(va, "_probe_duration", lambda p: _DURS.get(str(p), 0.0))
    return monkeypatch


def _three(plan, freeze_images=None, drop_freeze=False):
    plan = copy.deepcopy(plan)
    R = aud.render_cuts(plan, _TTS, _SRC)
    tl = va._beat_timeline(plan, _TTS)
    vd = {p: _DURS[p] for p in _SRC.values()}
    segs = cd.capcut_segments(plan, tl, _SRC, _TTS, vd)
    if freeze_images is None and not drop_freeze:
        freeze_images = {(bi, s["ci"]): "C:/cap/p/freeze_%02d_%d.jpg" % (bi, s["ci"])
                         for bi, ss in (segs or {}).items() for s in ss if s.get("hold")}
    draft, _ = cd.build_draft(plan=plan, timeline=tl, source_video_paths=_SRC, tts_paths=_TTS, asset_paths=_asset(),
                              project_name="t", video_durs=vd, cut_segments=segs, freeze_images=freeze_images or {})
    return R, draft, tl, plan


def _export(monkeypatch, tmp_path, plan, tl):
    rec = []
    monkeypatch.setattr(eb, "_cut_clip", lambda s, a, e, o: rec.append((s, a, e, Path(o).name)) or False)
    eb._beat_source_clips(plan, tl, _SRC, tmp_path / "sources", src_durs={"s0": 10.0, "s1": 8.0})
    return aud.export_cuts(rec, _SRC)


def test_same_plan_all_three_agree(env, tmp_path):
    R, draft, tl, plan = _three(_PLAN)
    C = aud.capcut_cuts(draft, tl, _SRC)
    E = _export(env, tmp_path, plan, tl)
    assert len(R) == 3 and len(C) == 3 and len(E) == 3
    assert aud.compare(R, C, "capcut") == ([], 3)
    assert aud.compare(R, E, "export") == ([], 3)


def test_freeze_cut_goes_to_capcut_as_move_plus_photo(env, tmp_path):
    """정지 컷: 완성본 = 느리게+정지 → 캡컷 = [같은 배속 영상 조각 + 정지 사진 조각], 자리·길이 같음."""
    R, draft, tl, plan = _three(_PLAN_FREEZE)
    r2 = [r for r in R if r["beat"] == 2][0]
    assert r2["freeze"] > 0.5 and abs(r2["speed"] - 1 / 1.15) < 0.01
    vt = next(t for t in draft["tracks"] if t["type"] == "video")
    photos = [s for s in vt["segments"] if s["material_id"] in
              {m["id"] for m in draft["materials"]["videos"] if m["type"] == "photo"}]
    assert len(photos) == 1
    C = aud.capcut_cuts(draft, tl, _SRC)
    assert aud.compare(R, C, "capcut") == ([], 3)
    # 영상 조각 뒤에 빈틈·겹침 없이 정지 조각이 붙는다
    segs = sorted(vt["segments"], key=lambda s: s["target_timerange"]["start"])
    for a, b in zip(segs, segs[1:]):
        assert a["target_timerange"]["start"] + a["target_timerange"]["duration"] == b["target_timerange"]["start"]
    E = _export(env, tmp_path, plan, tl)
    assert aud.compare(R, E, "export") == ([], 3)


def test_freeze_without_photo_is_caught(env):
    """정지 그림을 못 뜨면 종전처럼 한 배속으로 늘린다 — 대조가 freeze 로 잡아야 한다(사보타주 대용)."""
    R, draft, tl, _plan = _three(_PLAN_FREEZE, drop_freeze=True)
    C = aud.capcut_cuts(draft, tl, _SRC)
    bc, _ = aud.compare(R, C, "capcut")
    assert [(b["beat"], b["why"]) for b in bc] == [(2, ["freeze"])]


def test_capcut_start_off_by_03_is_caught(env):
    R, draft, tl, _plan = _three(_PLAN)
    vt = next(t for t in draft["tracks"] if t["type"] == "video")
    vt["segments"][1]["source_timerange"]["start"] += 300_000        # 두 번째 컷 소스 시작 +0.3초
    bc, _ = aud.compare(R, aud.capcut_cuts(draft, tl, _SRC), "capcut")
    assert [(b["beat"], b["ci"], b["why"]) for b in bc] == [(1, 0, ["start"])]


def test_capcut_timeline_shift_and_missing_cut_caught(env):
    R, draft, tl, _plan = _three(_PLAN)
    C = aud.capcut_cuts(draft, tl, _SRC)
    C2 = copy.deepcopy(C)
    C2[2]["t0"] += 0.3
    bc, _ = aud.compare(R, C2, "capcut")
    assert bc and bc[0]["why"] == ["t0"]
    bc2, n2 = aud.compare(R, C[:2], "capcut")                          # 셋째 칸 컷이 캡컷에 없다
    assert n2 == 3 and bc2[0]["why"] == ["count"]


def test_clean_kind_mismatch_caught(env, tmp_path):
    """완성본은 청소본(src)을 쓰는데 ZIP 은 원본 — '청소' 사유로 잡혀야 한다."""
    R, draft, tl, plan = _three(_PLAN)
    E = _export(env, tmp_path, plan, tl)
    R2 = [dict(r, src="/real/clean_" + Path(r["src"]).name) for r in R]
    be, _ = aud.compare(R2, E, "export", clean_src_paths={r["src"] for r in R2})
    assert len(be) == 3 and all(b["why"] == ["clean"] for b in be)
    be2, _ = aud.compare(R, E, "export", render_clean="final")         # 완성본 1편 청소인데 ZIP 원본
    assert len(be2) == 3 and all(b["why"] == ["clean"] for b in be2)


def test_final_clip_freeze_not_flagged():
    """캡컷이 완성본 조각(final_clip)을 쓰면 정지까지 구워진 화면이라 freeze 로 세지 않는다."""
    r = [{"beat": 0, "ci": 0, "vid": "s0", "src": "/a/s0.mp4", "start": 3.0, "read": 1.0, "t0": 0, "out": 2.0,
          "speed": 0.87, "freeze": 0.85}]
    x = [{"beat": 0, "ci": 0, "vid": "cc0", "src": "/w/capcut_clean_cc0_ab.mp4", "start": 0.0, "read": 2.0,
          "t0": 0, "out": 2.0, "speed": 1.0, "freeze": 0.0}]
    assert aud.compare(r, x, "capcut", render_clean="final")[0] == []
    assert aud.compare(r, x, "capcut")[0][0]["why"] == ["clean"]


def test_relative_vs_absolute_same_file_not_src_mismatch(tmp_path, monkeypatch):
    f = tmp_path / "s0.mp4"
    f.write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    r = [{"beat": 0, "ci": 0, "vid": "s0", "src": "s0.mp4", "start": 1.0, "read": 1.0}]
    x = [{"beat": 0, "ci": 0, "vid": "s0", "src": str(f), "start": 1.0, "read": 1.0}]
    assert aud.compare(r, x, "export")[0] == []
    assert aud.compare(r, [dict(x[0], src=str(tmp_path / "o.mp4"))], "export")[0][0]["why"] == ["src"]


def test_route_subs_present_in_app():
    """쓰기 자리 바꾸기의 필수 원문이 app.py 라우트에 실제로 있다 + 라우트가 재료 함수(export_sources_for)를 부른다."""
    src = (ROOT / "shopping_shorts" / "app.py").read_text(encoding="utf-8")
    for name, subs in (("api_mix_capcut", aud._CAPCUT_SUBS), ("api_mix_export", aud._EXPORT_SUBS)):
        i = src.index("def %s(" % name)
        body = src[i:src.index("\n@app.", i)]
        for old, _new, req in subs:
            if req:
                assert old in body, (name, old)
        assert "mix_pipeline.export_sources_for(" in body, name
        # 종전의 라우트 자체 청소 분기가 되살아나면 안 된다(판단 한 곳)
        assert "mix_pipeline.split_final_into_beat_clips(" not in body, name
        assert "for _vid, _cp in (job.get(\"clean_sources\")" not in body, name


def test_parse_summary():
    assert aud.parse_summary("x\n== 컷 214 · 캡컷 불일치 3 · 내보내기 불일치 0\n") == {"cuts": 214, "capcut": 3, "export": 0}
    assert aud.parse_summary("== 칸 3 · 다른 장면 0") is None


def test_patch_modules_uploaded_by_gate():
    """도구가 PATCH_DIR 에서 얹는 모듈은 관문이 서버에 올리는 목록(video_gate.PATCH_RELS)에 다 있어야 한다."""
    sys.path.insert(0, str(ROOT / "tools"))
    import video_gate as vg
    missing = [n for n in aud.PATCH_MODULES if ("%s.py" % n) not in vg.PATCH_RELS]
    assert not missing, missing


def test_snapshot_diff(tmp_path):
    (tmp_path / "a.txt").write_text("1")
    a = aud.snapshot(tmp_path)
    assert aud.snap_diff(a, aud.snapshot(tmp_path)) == []
    (tmp_path / "b.txt").write_text("2")
    assert aud.snap_diff(a, aud.snapshot(tmp_path)) == ["+b.txt"]


# ── 소스 영상별 캡컷 미디어(2026-09-27 이윤정님 제보 "캡컷으로 불러와도 소스영상별로 안 불러와진다") ──

def _mk(path, dur, color):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=%s:s=160x284:r=30:d=%s" % (color, dur),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


def _base_job(tmp_path, monkeypatch):
    """정본 job 모형: 통짜 청소본 1개(6초)에 s1(5~7)·s0(1~3)·s1(1~3) 순으로 지운 조각이 들어 있다."""
    from shopping_shorts import mix_pipeline as mp
    from shopping_shorts import clean_base as cb
    work = tmp_path / "work"
    for v in ("s0", "s1"):
        (work / v).mkdir(parents=True)
        _mk(work / v / "src.mp4", 8, "red")
    clean = work / "final_clean_x.mp4"
    _mk(clean, 6, "blue")
    base = {"path": str(clean), "extras": {}, "frame_exact": True, "cuts": [
        {"video_id": "s1", "src": 5.0, "dur": 2.0, "sdur": 2.0, "fin": 0.0, "beat_idx": 0},
        {"video_id": "s0", "src": 1.0, "dur": 2.0, "sdur": 2.0, "fin": 2.0, "beat_idx": 1},
        {"video_id": "s1", "src": 1.0, "dur": 2.0, "sdur": 2.0, "fin": 4.0, "beat_idx": 2}]}
    orig = {"beats": [
        {"beat_idx": 0, "narration": "a", "role": "훅", "primary": {"video_id": "s1", "seg_id": "s1-a", "start": 5.0, "end": 7.0}},
        {"beat_idx": 1, "narration": "b", "role": "본문", "primary": {"video_id": "s0", "seg_id": "s0-a", "start": 1.0, "end": 3.0}},
        {"beat_idx": 2, "narration": "c", "role": "본문", "primary": {"video_id": "s1", "seg_id": "s1-b", "start": 1.0, "end": 3.0}}]}
    plan2 = copy.deepcopy(orig)
    plan2["clean_base"] = True
    for b, (sid, t0) in zip(plan2["beats"], (("clean-0", 0.0), ("clean-1", 2.0), ("clean-2", 4.0))):
        b.update(phrase_sync=False, clean_replay=True,
                 manual_cuts=[{"video_id": "clean", "seg_id": sid, "start": t0, "dur": 1.2, "sdur": 1.2},
                              {"video_id": "clean", "seg_id": sid, "start": t0 + 1.2, "dur": 0.8, "sdur": 0.8}],
                 scene_override=[{"video_id": "clean", "seg_id": sid, "start": t0, "end": t0 + 2.0}])
    tts = {i: str(tmp_path / ("b%d.mp3" % i)) for i in range(3)}
    for b in plan2["beats"]:
        b["tts_path"] = tts[b["beat_idx"]]
    real_probe = va._probe_duration
    monkeypatch.setattr(va, "_probe_duration", lambda p: 2.0 if str(p).endswith(".mp3") else real_probe(p))
    monkeypatch.setattr(mp, "_probe_duration", va._probe_duration)
    monkeypatch.setattr(mp, "render_inputs_for", lambda *a, **k: (copy.deepcopy(plan2), cb.source_paths(base), base))
    job = {"job_id": "jb", "subtitle_removal": 1, "edit_plan": orig, "urls": ["u0", "u1"]}
    return mp, cb, work, base, plan2, tts, job


def test_base_job_capcut_media_is_per_source(tmp_path, monkeypatch):
    monkeypatch.setenv("SCREEN_CLIPS", "0")
    mp, cb, work, base, plan2, tts, job = _base_job(tmp_path, monkeypatch)
    ex = mp.export_sources_for(None, job, "jb", work, 0, for_capcut=True, clip_dir=tmp_path / "clips")
    assert ex["route"] == "base"
    assert sorted(ex["source_video_paths"]) == ["s0", "s1"], "캡컷 재료가 소스 영상별이 아니다(통짜 clean)"
    assert all(Path(p).name.startswith("capcut_src_") for p in ex["source_video_paths"].values())
    assert [p["cs"] for p in ex["source_layout"]["s1"]["pieces"]] == [1.0, 5.0], "소스별 파일 안은 원본 시간순"
    assert abs(va._probe_duration(ex["source_video_paths"]["s1"]) - 4.0) < 0.1
    assert sorted(ex["library_originals"]) == ["s0", "s1"], "보관함에 긴 원본도 소스별로"
    # 캡컷 초안: 미디어 이름 = 소스 id, 컷마다 (원본 영상, 원본 시각)이 완성본 컷 계획과 같다
    R = aud.render_cuts(plan2, tts, cb.source_paths(base))
    tl = va._beat_timeline(ex["plan"], ex["tts_paths"])
    vd = {p: va._probe_duration(p) for p in ex["source_video_paths"].values()}
    segs = cd.capcut_segments(ex["plan"], tl, ex["source_video_paths"], ex["tts_paths"], vd)
    asset = {p: "C:/cap/p/" + Path(p).name for p in list(ex["source_video_paths"].values()) + list(tts.values())}
    draft, _ = cd.build_draft(plan=ex["plan"], timeline=tl, source_video_paths=ex["source_video_paths"],
                              tts_paths=ex["tts_paths"], asset_paths=asset, project_name="t", video_durs=vd,
                              cut_segments=segs, freeze_images={})
    C = aud.capcut_cuts(draft, tl, ex["source_video_paths"])
    aud.map_origins(R, C, ex, base)
    bad_media, names = aud.media_check(R, C, draft, "base")
    assert names == ["s0", "s1"] and bad_media == []
    assert [(r["o_vid"], r["o_start"]) for r in R] == [(x["o_vid"], x["o_start"]) for x in C]
    assert aud.compare(R, C, "capcut", base_paths=set(cb.source_paths(base).values()))[0] == []


def test_blob_media_is_caught():
    """통짜 청소본(clean) 하나만 미디어로 나가면 media 로 잡는다(제보 그대로의 모양)."""
    R = [{"beat": 0, "ci": 0, "vid": "clean", "o_vid": "s1", "src": "/w/final_clean.mp4", "start": 0, "read": 1,
          "t0": 0, "out": 1, "speed": 1, "freeze": 0}]
    draft = {"materials": {"videos": [{"id": "m", "type": "video", "material_name": "clean", "path": "x"}]},
             "tracks": [{"type": "video", "segments": [{"material_id": "m"}]}]}
    bad, names = aud.media_check(R, [], draft, "base")
    assert names == ["clean"] and {tuple(b["why"]) for b in bad} == {("media",)} and len(bad) == 2


def test_source_piece_extends_to_cover_reads_past_region(tmp_path, monkeypatch):
    """컷이 조각 끝을 넘어 읽으면(청소본은 이어져 있어 렌더는 읽는다) 소스별 파일 조각도 그만큼 담는다 — 안 그러면
    시작 당기기가 컷을 앞 조각으로 민다(서버 7bbb 7칸 실측)."""
    monkeypatch.setenv("SCREEN_CLIPS", "0")
    mp, cb, work, base, plan2, tts, job = _base_job(tmp_path, monkeypatch)
    b1 = plan2["beats"][1]
    b1["manual_cuts"] = [{"video_id": "clean", "seg_id": "clean-1", "start": 2.0, "dur": 1.2, "sdur": 1.2},
                         {"video_id": "clean", "seg_id": "clean-1", "start": 3.2, "dur": 0.8, "sdur": 1.0}]  # 4.2까지 읽음
    cplan = va.render_cut_plan(plan2, tts, cb.source_paths(base))       # 렌더가 읽는 그 계획
    lay, regs = mp._source_layout_from_base(base, tmp_path / "c", cplan)
    assert lay["s0"]["pieces"][0]["len"] >= 2.2 - 1e-6, lay["s0"]["pieces"][0]["len"]
    lay0, _ = mp._source_layout_from_base(base, tmp_path / "c0")
    assert abs(lay0["s0"]["pieces"][0]["len"] - (2.0 + 2 / 30)) < 1e-6          # 여유 2프레임만
