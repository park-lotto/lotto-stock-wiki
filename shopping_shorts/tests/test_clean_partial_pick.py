# -*- coding: utf-8 -*-
"""장면 골라 지우기(2026-09-26) — 고른 컷만 업체로 보내고, 완성본 시간축·다음 장면은 그대로.

잡는 것:
  ① 선택 판정(허용오차·전체=None) ② 서명에 선택이 들어간다(전체 파일과 안 섞임)
  ③ 정본: 안 고른 비트는 원본 재료 그대로·증분 청소 대상 아님 / 고른 비트가 바뀌면 증분
  ④ 안 지운 컷을 '지운 조각'으로 빌려 쓰지 않는다 ⑤ 렌더 입력에 원본 소스가 같이 간다
  ⑥ 실제 ffmpeg 되붙이기 — 프레임 수 불변, 고른 구간만 바뀐다(1프레임도 안 밀린다)
  ⑦ API 입력 정리 — 전부 고르면 전체(None), 하나도 안 맞으면 거절
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import clean_base as cb


def _plan():
    return {"beats": [
        {"beat_idx": 0, "target_seconds": 2.0, "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 2.0, "primary": {"video_id": "s1", "seg_id": "s1-0", "start": 5.0, "end": 7.0}, "alternates": []}]}


CUTS = [{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0},
        {"video_id": "s1", "beat_idx": 1, "src": 5.0, "fin": 2.0, "dur": 2.0}]


def test_cut_selected_tolerance_and_all():
    c = CUTS[1]
    assert mp.cut_selected(c, None) is True                       # 선택 없음 = 전체
    assert mp.cut_selected(c, ["1|s1|5.00"]) is True
    assert mp.cut_selected(c, ["1|s1|5.20"]) is True              # 훅 시작점 확정으로 조금 움직여도 같은 컷
    assert mp.cut_selected(c, ["1|s1|6.00"]) is False
    assert mp.cut_selected(c, ["0|s1|5.00"]) is False             # 다른 비트
    assert mp.cut_selected(c, ["garbage"]) is False
    assert mp.cut_key(c) == "1|s1|5.00"


def test_sig_includes_selection_but_all_keeps_old_name():
    job = {"edit_plan": _plan()}
    s_all = mp._clean_sig(job)
    s_pick = mp._clean_sig(dict(job, clean_cuts=["1|s1|5.00"]))
    assert s_pick != s_all and s_pick.startswith(s_all) and "s" in s_pick[len(s_all):]
    assert mp._clean_sig(dict(job, clean_cuts=None)) == s_all      # 옛 job 이름 그대로(재청소 없음)
    # clean_tiers_ready도 같은 서명으로 파일을 찾는다(0순위-B)
    assert mp._clean_sig_for(dict(job, clean_cuts=["1|s1|5.00"], clean_tier="pro"), "pro") == \
        mp._clean_sig(dict(job, clean_cuts=["1|s1|5.00"], clean_tier="pro"))


def _base(tmp_path, sel):
    plan = _plan()
    (tmp_path / "final_clean_abc.mp4").write_bytes(b"c" * 4096)
    cuts = [dict(c, cleaned=mp.cut_selected(c, sel)) for c in CUTS]
    return plan, cb.save_base(tmp_path, sig="abc", path=str(tmp_path / "final_clean_abc.mp4"),
                              plan=plan, cuts=cuts, sel=sel)


def test_unpicked_beat_stays_original_and_never_incremental(tmp_path):
    plan, base = _base(tmp_path, ["1|s1|5.00"])                   # 비트1만 골랐다
    assert base["partial"] and base["skip_beats"] == [0]
    # 안 고른 비트0의 장면을 바꿔도 → 증분 청소 대상 아님, 원본 재료 그대로
    plan["beats"][0]["scene_override"] = [{"video_id": "s1", "seg_id": "s1-9", "start": 10.0, "end": 12.0}]
    plan2, unc, ext = cb.remap_plan(plan, base, tts_durs={0: 9.0, 1: 2.0})   # 비트0 음성도 크게 늘렸다
    assert unc == [] and ext == []
    assert plan2["beats"][0]["scene_override"][0]["video_id"] == "s1"      # 원본 재료
    assert plan2["beats"][1]["scene_override"][0]["video_id"] == "clean"   # 고른 비트는 청소본


def test_picked_beat_change_is_incremental(tmp_path):
    plan, base = _base(tmp_path, ["1|s1|5.00"])
    plan["beats"][1]["scene_override"] = [{"video_id": "s0", "seg_id": "s0-9", "start": 20.0, "end": 22.0}]
    _p2, unc, _e = cb.remap_plan(plan, base)
    assert unc == [1]


def test_uncleaned_cut_is_not_borrowed_as_clean_piece(tmp_path):
    plan, base = _base(tmp_path, ["1|s1|5.00"])
    # 고른 비트1이 안 지운 컷(s0 1~3)을 가져다 쓰면 — 지운 조각이 아니므로 빌려 쓰지 않고 증분 청소
    plan["beats"][1]["scene_override"] = [{"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}]
    _p2, unc, _e = cb.remap_plan(plan, base)
    assert unc == [1]
    # 전체 지운 정본이었다면 같은 조각을 그대로 빌려 쓴다(종전 동작)
    plan_all, base_all = _base(tmp_path, None)
    plan_all["beats"][1]["scene_override"] = [{"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}]
    assert cb.remap_plan(plan_all, base_all)[1] == []


def test_render_inputs_include_original_sources_for_unpicked(tmp_path, monkeypatch):
    plan, base = _base(tmp_path, ["1|s1|5.00"])
    for i in ("s0", "s1"):
        (tmp_path / i).mkdir(); (tmp_path / i / "v.mp4").write_bytes(b"v" * 4096)
    job = {"edit_plan": plan, "urls": ["u0", "u1"], "customer_id": 0, "subtitle_removal": 1, "clean_cuts": ["1|s1|5.00"]}
    monkeypatch.setattr(mp, "clean_base_on", lambda store, cid=0: True)
    plan2, paths, b = mp.render_inputs_for(None, job, "j", tmp_path, [], 0, allow_clean=False)
    assert b is not None
    assert "clean" in paths and "s0" in paths                      # 안 고른 비트0이 쓰는 원본이 같이 간다
    assert plan2["beats"][0]["primary"]["video_id"] == "s0"


def test_full_base_render_inputs_unchanged(tmp_path, monkeypatch):
    plan, base = _base(tmp_path, None)
    job = {"edit_plan": plan, "urls": ["u0", "u1"], "customer_id": 0, "subtitle_removal": 1}
    monkeypatch.setattr(mp, "clean_base_on", lambda store, cid=0: True)
    _p2, paths, _b = mp.render_inputs_for(None, job, "j", tmp_path, [], 0, allow_clean=False)
    assert set(paths) == {"clean"}                                  # 종전 그대로 — 원본을 안 섞는다


needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")


def _mk(path, n, color_expr):
    """30fps n프레임 영상 — 프레임마다 밝기가 달라 밀림을 잡을 수 있다."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x128:r=30:d=%.3f" % (n / 30.0),
                    "-f", "lavfi", "-i", "sine=f=440:r=48000:d=%.3f" % (n / 30.0),
                    # ★실제 조립본처럼 시각을 들쭉날쭉하게(시작 0.021초·29.955fps) — 시각 기준으로 자르면
                    #   프레임이 복제돼 뒤가 밀린다(2026-09-26 LAB 실측). 이 모양이어야 그 결함을 잡는다.
                    "-vf", "geq=lum='%s':cb=128:cr=128,setpts=0.021/TB+N/(29.955*TB)" % color_expr,
                    "-fps_mode", "passthrough", "-frames:v", str(n),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)


def _lumas(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=1:1,format=gray",
                          "-fps_mode", "passthrough", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return list(raw)


@needs_ffmpeg
def test_partial_splice_keeps_every_frame_in_place(tmp_path, monkeypatch):
    raw = tmp_path / "mix_raw.mp4"
    _mk(raw, 90, "mod(N*2,200)+20")            # 프레임 번호가 곧 밝기(20,22,24,…)
    sent = []

    def _fake_vmake(src, keys, out, tier=None):
        # '지움' = 화면을 새까맣게. 받은 길이·등급을 기록한다.
        sent.append((mp._probe_fps_frames(src)[2], tier))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", "geq=lum=0:cb=128:cr=128",
                        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", "-c:a", "copy", str(out)], check=True)
        return str(out)
    monkeypatch.setattr(mp, "_vmake_clean", _fake_vmake)
    cuts = [{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 1.0},    # 0~29
            {"video_id": "s1", "beat_idx": 1, "src": 4.0, "fin": 1.0, "dur": 1.0},    # 30~59 ← 고름
            {"video_id": "s0", "beat_idx": 2, "src": 8.0, "fin": 2.0, "dur": 1.0}]    # 60~89
    out = tmp_path / "out.mp4"
    mp._clean_partial(str(raw), cuts, ["1|s1|4.00"], ["k"], str(out), "pro", tmp_path)
    assert sent == [(30, "pro")]                                   # 고른 1초(30프레임)만, 등급 그대로
    a, b = _lumas(raw), _lumas(out)
    assert len(b) == len(a) == 90                                  # 길이 불변
    assert all(v < 12 for v in b[30:60])                           # 고른 구간만 지워짐
    assert all(abs(x - y) <= 2 for x, y in zip(a[:30] + a[60:], b[:30] + b[60:]))   # 나머지는 제자리 그대로


def test_body_cuts_all_means_none_and_none_matching_rejected(tmp_path, monkeypatch):
    from shopping_shorts import app as A
    job = {"edit_plan": _plan(), "customer_id": 0}
    monkeypatch.setattr(A.mix_pipeline, "_clean_strategy", lambda j: "final")
    monkeypatch.setattr(A.mix_pipeline, "clean_pick_cuts",
                        lambda j, w: [dict(c, ci=i, key=mp.cut_key(c), sel=True) for i, c in enumerate(CUTS)])
    assert A._clean_cuts_from_body(job, "j", None) is None
    assert A._clean_cuts_from_body(job, "j", ["0|s0|1.00", "1|s1|5.00"]) is None      # 전부 = 전체
    assert A._clean_cuts_from_body(job, "j", ["1|s1|5.00", "9|x|0.00"]) == ["1|s1|5.00"]  # 없는 키는 버림
    r = A._clean_cuts_from_body(job, "j", ["9|x|0.00"])
    assert getattr(r, "status_code", None) == 422
    r = A._clean_cuts_from_body(job, "j", [])
    assert getattr(r, "status_code", None) == 422
