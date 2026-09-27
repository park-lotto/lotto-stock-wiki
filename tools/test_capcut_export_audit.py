# -*- coding: utf-8 -*-
"""tools/capcut_export_audit.py — 대조가 실제로 어긋남을 잡는지(가짜 편성표, 영상·DB 없이).

① 완성본 컷 = render_cuts(_render_mix 의 컷 결정부), ② 캡컷 = capcut_draft.build_draft 가 만든 초안의 영상 트랙,
③ 내보내기 = export_bundle._beat_source_clips 가 _cut_clip 에 넘긴 구간 — 셋 다 라이브 함수가 만든다.
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


@pytest.fixture
def three(monkeypatch):
    """같은 편성표로 ①②③을 만든다."""
    monkeypatch.setenv("SCREEN_CLIPS", "0")          # 화면 데이터 없음 = 서버 계산(렌더·캡컷·ZIP 모두 같은 함수)
    monkeypatch.setattr(va, "_probe_duration", lambda p: _DURS.get(str(p), 0.0))
    plan = copy.deepcopy(_PLAN)
    R = aud.render_cuts(plan, _TTS, _SRC)
    tl = va._beat_timeline(plan, _TTS)
    asset = {p: "C:/cap/p/" + Path(p).name for p in list(_SRC.values()) + list(_TTS.values())}
    draft, _ = cd.build_draft(plan=plan, timeline=tl, source_video_paths=_SRC, tts_paths=_TTS,
                              asset_paths=asset, project_name="t", video_durs={p: _DURS[p] for p in _SRC.values()})
    C = aud.capcut_cuts(draft, tl, _SRC)
    return R, draft, tl, C, None, plan


def _export(monkeypatch, tmp_path, plan, tl):
    rec = []
    monkeypatch.setattr(eb, "_cut_clip", lambda s, a, e, o: rec.append((s, a, e, Path(o).name)) or False)
    eb._beat_source_clips(plan, tl, _SRC, tmp_path / "sources", src_durs={"s0": 10.0, "s1": 8.0})
    return aud.export_cuts(rec, _SRC)


def test_same_plan_all_three_agree(three, monkeypatch, tmp_path):
    R, draft, tl, C, _rec, plan = three
    E = _export(monkeypatch, tmp_path, plan, tl)
    assert len(R) == 3 and len(C) == 3 and len(E) == 3
    bc, nc = aud.compare(R, C, "capcut")
    be, ne = aud.compare(R, E, "export")
    assert (bc, nc) == ([], 3)
    assert (be, ne) == ([], 3)


def test_capcut_start_off_by_03_is_caught(three):
    R, draft, tl, C, _rec, _plan = three
    vt = next(t for t in draft["tracks"] if t["type"] == "video")
    vt["segments"][1]["source_timerange"]["start"] += 300_000        # 두 번째 컷 소스 시작 +0.3초
    C2 = aud.capcut_cuts(draft, tl, _SRC)
    bc, _ = aud.compare(R, C2, "capcut")
    assert [(b["beat"], b["ci"], b["why"]) for b in bc] == [(1, 0, ["start"])]


def test_capcut_timeline_shift_and_missing_cut_caught(three):
    R, draft, tl, C, _rec, _plan = three
    C2 = copy.deepcopy(C)
    C2[2]["t0"] += 0.3
    bc, _ = aud.compare(R, C2, "capcut")
    assert bc and bc[0]["why"] == ["t0"]
    bc2, n2 = aud.compare(R, C[:2], "capcut")                          # 셋째 칸 컷이 캡컷에 없다
    assert n2 == 3 and bc2[0]["why"] == ["count"]


def test_clean_kind_mismatch_caught(three, monkeypatch, tmp_path):
    """완성본은 청소본(src)을 쓰는데 ZIP 은 원본 — '청소' 사유로 잡혀야 한다."""
    R, draft, tl, C, _rec, plan = three
    E = _export(monkeypatch, tmp_path, plan, tl)
    R2 = [dict(r, src="/real/clean_" + Path(r["src"]).name) for r in R]
    be, _ = aud.compare(R2, E, "export", clean_src_paths={r["src"] for r in R2})
    assert len(be) == 3 and all(b["why"] == ["clean"] for b in be)
    # 완성본 1편 청소(final)인데 ZIP 원본도 '청소'
    be2, _ = aud.compare(R, E, "export", render_clean="final")
    assert len(be2) == 3 and all(b["why"] == ["clean"] for b in be2)


def test_freeze_cut_flagged_for_capcut():
    """완성본이 느리게+정지로 채운 컷을 캡컷은 한 배속으로 늘린다 — 화면이 다르니 잡는다."""
    r = [{"beat": 0, "ci": 0, "vid": "s0", "src": "/a", "start": 0, "read": 1.0, "t0": 0, "out": 2.0,
          "speed": 1.0, "freeze": 0.85}]
    x = [{"beat": 0, "ci": 0, "vid": "s0", "src": "/a", "start": 0, "read": 1.0, "t0": 0, "out": 2.0, "speed": 0.5}]
    bc, _ = aud.compare(r, x, "capcut")
    assert bc and bc[0]["why"] == ["freeze"]


def test_render_mirror_guard():
    src = Path(va.__file__).read_text(encoding="utf-8")
    aud.check_render_mirror(src)                                        # 지금 원문엔 다 있다
    with pytest.raises(RuntimeError):
        aud.check_render_mirror(src.replace("plan = plan_beat_clips_for(beat, tts_dur, _srcd, runout=runout)", "x"))


def test_route_subs_present_in_app():
    """쓰기 자리 바꾸기의 필수 원문이 app.py 라우트에 실제로 있다(없으면 서버 실행이 멈춘다 — 여기서 먼저 안다)."""
    src = (ROOT / "shopping_shorts" / "app.py").read_text(encoding="utf-8")
    for name, subs in (("api_mix_capcut", aud._CAPCUT_SUBS), ("api_mix_export", aud._EXPORT_SUBS)):
        i = src.index("def %s(" % name)
        body = src[i:src.index("\n@app.", i)]
        for old, _new, req in subs:
            if req:
                assert old in body, (name, old)


def test_snapshot_diff(tmp_path):
    (tmp_path / "a.txt").write_text("1")
    a = aud.snapshot(tmp_path)
    assert aud.snap_diff(a, aud.snapshot(tmp_path)) == []
    (tmp_path / "b.txt").write_text("2")
    assert aud.snap_diff(a, aud.snapshot(tmp_path)) == ["+b.txt"]


def test_relative_vs_absolute_same_file_not_src_mismatch(tmp_path, monkeypatch):
    """같은 파일을 상대/절대 경로로 적었다고 '다른 파일'로 세지 않는다(서버 첫 실행 오탐 25건의 원인)."""
    f = tmp_path / "s0.mp4"
    f.write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    r = [{"beat": 0, "ci": 0, "vid": "s0", "src": "s0.mp4", "start": 1.0, "read": 1.0}]
    x = [{"beat": 0, "ci": 0, "vid": "s0", "src": str(f), "start": 1.0, "read": 1.0}]
    assert aud.compare(r, x, "export")[0] == []
    x2 = [dict(x[0], src=str(tmp_path / "other.mp4"))]
    assert aud.compare(r, x2, "export")[0][0]["why"] == ["src"]


def test_final_clip_freeze_not_flagged():
    """캡컷이 완성본 조각(final_clip)을 쓰면 정지까지 구워진 화면이라 freeze 로 세지 않는다(서버 실측 오탐 5건)."""
    r = [{"beat": 0, "ci": 0, "vid": "s0", "src": "/a/s0.mp4", "start": 3.0, "read": 1.0, "t0": 0, "out": 2.0,
          "speed": 0.87, "freeze": 0.85}]
    x = [{"beat": 0, "ci": 0, "vid": "cc0", "src": "/w/capcut_clean_cc0_ab.mp4", "start": 0.0, "read": 2.0,
          "t0": 0, "out": 2.0, "speed": 1.0}]
    assert aud.compare(r, x, "capcut", render_clean="final")[0] == []
    assert aud.compare(r, x, "capcut")[0][0]["why"] == ["clean"]          # 완성본이 청소 안 했는데 조각이면 청소 불일치
