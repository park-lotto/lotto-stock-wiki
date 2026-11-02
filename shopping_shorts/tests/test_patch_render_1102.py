"""관제 304 — 완성본 뒤 구간만 교체. 재렌더·재계획 없이 바뀐 묶음만 다시 굽는다.

주인: 해도 되나 = render_bench.patch_scope · 어느 프레임 = render_bench.patch_ranges · 어느 키프레임 묶음·끼운 파일 검사 = engine/final_splice.
진짜 render() 를 도는 프레임·소리 대조 = tools/calcopy/hybrid/patch_render_check.py(합성 편, 전체 렌더와 대조). 여기는 작은 영상(320x240)으로 끼우기 자체와 판단만 잰다.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.calcopy.engine import ad_mark, encoder, final_splice as FS
from tools.calcopy.hybrid import render_bench as RB, thumb as TH
from tools.calcopy.hybrid.common import md5

X264 = ["-c:v", "libx264", "-crf", "20", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p", "-bf", "2"]


def _sh(*cmd):
    subprocess.run([str(c) for c in cmd], check=True, stdin=subprocess.DEVNULL, capture_output=True)


@pytest.fixture
def video(tmp_path):
    """3초 90프레임 — 30프레임마다 키프레임 · 소리 있음 · 완성본 표식 있음."""
    f = tmp_path / "final.mp4"
    _sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=30:d=3", "-f", "lavfi", "-i", "sine=f=440:d=3", "-map", "0:v", "-map", "1:a",
        *X264, "-g", "30", "-c:a", "aac", "-metadata", f"comment={ad_mark.MARK}", "-movflags", "+faststart", f)
    return f


def _chunk(src, color="red"):
    def make(a, b, out):
        _sh("ffmpeg", "-y", "-v", "error", "-ss", f"{a / 30:.6f}", "-i", src, "-vf", f"drawbox=x=0:y=0:w=80:h=80:c={color}:t=fill", "-frames:v", b - a, *X264, "-g", "30", out)
    return make


def test_gop_ranges_cover_changed_frames():
    keys = [0, 60, 120, 180]
    assert FS.gop_ranges(keys, 240, [[70, 100]]) == [[60, 120]]
    assert FS.gop_ranges(keys, 240, [[60, 120]]) == [[60, 120]]               # 키프레임에 딱 맞으면 그 묶음만
    assert FS.gop_ranges(keys, 240, [[70, 100], [130, 140]]) == [[60, 180]]   # 맞닿으면 합친다
    assert FS.gop_ranges(keys, 240, [[70, 100], [190, 200]]) == [[60, 120], [180, 240]]
    assert FS.gop_ranges(keys, 240, [[0, 2]]) == [[0, 60]]


def test_splice_keeps_everything_outside_the_chunk(video, tmp_path):
    src = tmp_path / "src.mp4"
    shutil.copy2(video, src)
    h0, a0 = FS.frame_hashes(video), FS.audio_md5(video)
    keys, n = FS.keyframes(video)
    chunks = FS.gop_ranges(keys, n, [[35, 50]])
    assert chunks == [[30, 60]]
    rep = FS.splice(video, chunks, _chunk(src), tmp_path / "w", log=lambda *a: None)
    h1 = FS.frame_hashes(video)
    assert rep == {"frames": 90, "kept": 60, "redone": 30} and len(h1) == 90
    assert [i for i in range(90) if h0[i] != h1[i]] == list(range(30, 60))      # 묶음 밖은 비트 그대로, 묶음 안은 전부 바뀜
    assert FS.audio_md5(video) == a0
    assert ad_mark.MARK in ad_mark._probe(video)[2]                             # 광고 표식 유지 — 봉인 검사가 본다


@pytest.mark.parametrize("first", [0, 60])
def test_splice_at_start_and_end(video, tmp_path, first):
    src = tmp_path / "src.mp4"
    shutil.copy2(video, src)
    h0 = FS.frame_hashes(video)
    FS.splice(video, [[first, first + 30]], _chunk(src), tmp_path / "w", log=lambda *a: None)
    h1 = FS.frame_hashes(video)
    assert [i for i in range(90) if h0[i] != h1[i]] == list(range(first, first + 30))


def test_splice_refuses_wrong_length_and_leaves_final(video, tmp_path):
    src = tmp_path / "src.mp4"
    shutil.copy2(video, src)
    before = md5(video)

    def short(a, b, out):
        _chunk(src)(a, b - 3, out)
    with pytest.raises(FS.SpliceFail, match="프레임 수"):
        FS.splice(video, [[30, 60]], short, tmp_path / "w", log=lambda *a: None)
    assert md5(video) == before


def test_splice_refuses_boundary_that_is_not_keyframe(video, tmp_path):
    with pytest.raises(FS.SpliceFail, match="키프레임"):
        FS.splice(video, [[35, 60]], _chunk(video), tmp_path / "w", log=lambda *a: None)


def test_splice_refuses_other_encoder_settings(video, tmp_path):
    """영상 규격이 다른 묶음(프로파일·B프레임)은 복사로 이으면 일부 재생기가 깨진다 — 끼우지 않는다."""
    src = tmp_path / "src.mp4"
    shutil.copy2(video, src)
    before = md5(video)

    def other(a, b, out):
        _sh("ffmpeg", "-y", "-v", "error", "-ss", f"{a / 30:.6f}", "-i", src, "-frames:v", b - a, "-c:v", "libx264", "-profile:v", "baseline", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p", out)
    with pytest.raises(FS.SpliceFail):
        FS.splice(video, [[30, 60]], other, tmp_path / "w", log=lambda *a: None)
    assert md5(video) == before


def test_final_gop_is_two_seconds(tmp_path, monkeypatch):
    """완성본을 마지막으로 굽는 두 곳(광고 표시·썸네일 카드)이 같은 키프레임 간격 — 그래야 구간 교체가 몇 초 안에 끝난다."""
    monkeypatch.setattr(ad_mark, "venc", lambda crf=16: ["-c:v", "libx264", "-preset", "ultrafast", "-threads", "1"])
    monkeypatch.setattr(TH, "venc", lambda crf=16: ["-c:v", "libx264", "-preset", "ultrafast", "-threads", "1"])
    f = tmp_path / "f.mp4"
    _sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=5", "-f", "lavfi", "-i", "sine=d=5", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-g", "999", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", f)
    ad_mark.apply_inplace(f, log=lambda *a: None)
    assert FS.keyframes(f)[0] == [0, 60, 120]
    j = tmp_path / "c.jpg"
    _sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=1080x1920", "-frames:v", "1", j)
    TH.stamp_video(f, j)
    assert FS.keyframes(f)[0] == [0, 60, 120]


def test_stamp_video_works_without_sound(tmp_path, monkeypatch):
    """구간 묶음엔 소리가 없다 — 옛 stamp_video 는 '-map 0:a' 로 실패."""
    monkeypatch.setattr(TH, "venc", lambda crf=16: ["-c:v", "libx264", "-preset", "ultrafast", "-threads", "1"])
    f = tmp_path / "f.mp4"
    _sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=1", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p", f)
    j = tmp_path / "c.jpg"
    _sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=1080x1920", "-frames:v", "1", j)
    TH.stamp_video(f, j)
    assert FS.keyframes(f)[1] == 30


def test_apply_span_is_frame_exact(tmp_path, monkeypatch):
    monkeypatch.setattr(ad_mark, "venc", lambda crf=16: ["-c:v", "libx264", "-preset", "ultrafast", "-threads", "1"])
    f, out = tmp_path / "f.mp4", tmp_path / "o.mp4"
    _sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=30:d=3", "-c:v", "libx264", "-qp", "0", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv444p", f)
    ad_mark.apply_span(f, 33, 47, out)
    assert FS.keyframes(out)[1] == 14


# ── 구간만 바꿔도 되나 ─────────────────────────────────────────────────────
def _T(*cuts):
    return {"cuts": [{"line": l, "kind": "tts", "t0": a, "t1": b, "src": "a.mp4", "ss": a, "fp": fp, "frames": round((b - a) * 30)} for l, a, b, fp in cuts],
            "lines": {"L1": [0, 2]}, "opos": []}


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setattr(RB, "_code_sig", lambda kind: "code")
    monkeypatch.setattr(RB, "transitions_of", lambda T, st, placed, log=None: placed.get("transitions") or [])
    R = tmp_path / "r"
    R.mkdir()
    S, M, st = {"lines": [1]}, {"cand_dir": "x", "cuts": {}, "blur": {}}, {"name": "t"}
    T = _T(("L1", 0, 1, "a"), ("L1", 1, 2, "b"))
    (R / "final.mp4").write_bytes(b"x" * 10)
    (R / "timeline.json").write_text(json.dumps(T), encoding="utf-8")
    (R / "render_info.json").write_text(json.dumps({"audio": {"lufs": -14}}), encoding="utf-8")
    (R / RB.PATCH_STATE).write_text(json.dumps({"sig": RB.patch_sig(S, M, st, None), "md5": md5(R / "final.mp4"), "placed": {"rows": []}, "trans": [], "card": None}), encoding="utf-8")
    return R, S, M, st, T


def _scope(R, T, S, M, st, MG=None):
    return RB.patch_scope(R, T, S, M, st, None, MG, log=lambda *a: None)


def test_scope_ok_when_only_picture_changed(saved):
    R, S, M, st, T = saved
    M = {**M, "cuts": {"L1": [{"ss": 3}]}, "blur": {"a.mp4": [[1, 2, 3, 4]]}}      # 컷·흐림은 지문에 안 들어간다
    got = _scope(R, _T(("L1", 0, 1, "a"), ("L1", 1, 2, "b2")), S, M, st)
    assert got and got["audio"] == {"lufs": -14}


@pytest.mark.parametrize("how", ["script", "style", "bgm", "final", "bound", "line", "orig", "motion", "full", "no_state", "trans"])
def test_scope_refuses_everything_that_is_not_picture(saved, how, monkeypatch):
    R, S, M, st, T = saved
    T2 = json.loads(json.dumps(T))
    MG = None
    if how == "script":
        S = {"lines": [2]}
    elif how == "style":
        st = {"name": "u"}
    elif how == "bgm":
        M = {**M, "bgm": "다른 곡"}
    elif how == "final":
        (R / "final.mp4").write_bytes(b"y" * 10)
    elif how == "bound":
        T2["cuts"][0]["t1"] = 1.1
    elif how == "line":
        T2["lines"]["L1"] = [0, 3]
    elif how == "orig":
        T2["opos"] = [{"span": [1, 2], "t0": 0, "src": "b.mp4"}]
    elif how == "motion":
        MG = {"layers": [1]}
    elif how == "full":
        monkeypatch.setenv(RB.FULL_ENV, "1")
    elif how == "no_state":
        (R / RB.PATCH_STATE).unlink()
    elif how == "trans":
        monkeypatch.setattr(RB, "transitions_of", lambda *a, **k: [{"t": 1, "kind": "flash"}])
    assert _scope(R, T2, S, M, st, MG) is None


def test_ranges_are_the_scenes_the_cut_touches():
    T = {"cuts": [{"frames": 60}, {"frames": 60}, {"frames": 60}, {"frames": 60}]}
    sc = [{"start": 0, "end": 1}, {"start": 1, "end": 2}, {"start": 2, "end": 3}, {"start": 3, "end": 4}, {"start": 4, "end": 6}, {"start": 6, "end": 8}]
    assert RB.patch_ranges(T, [1], sc) == [[30, 180]]          # 컷 60~120 + 앞뒤 여유 18프레임에 닿는 칸만(첫 칸 0~30 은 여유 밖)
    assert RB.patch_ranges(T, [], sc) == []


def test_ranges_stop_at_scene_outside_margin():
    T = {"cuts": [{"frames": 300}, {"frames": 30}, {"frames": 300}]}
    sc = [{"start": 0, "end": 5}, {"start": 5, "end": 9}, {"start": 9, "end": 10}, {"start": 10, "end": 11}, {"start": 11, "end": 12}]
    assert RB.patch_ranges(T, [1], sc) == [[270, 360]]         # 컷 300~330 · 앞 칸 150~270 은 여유(18) 밖이라 안 건드린다


def test_touch_rule_is_the_same_as_scene_token(tmp_path):
    """자막 칸 지문이 보는 컷 = patch_ranges 가 다시 만드는 칸 — 두 벌이면 구간 밖 칸이 낡는다."""
    T = {"cuts": [{"frames": 60, "fp": "a"}, {"frames": 60, "fp": "b"}, {"frames": 60, "fp": "c"}]}
    T2 = {"cuts": [{"frames": 60, "fp": "a"}, {"frames": 60, "fp": "B"}, {"frames": 60, "fp": "c"}]}
    sc = [{"start": s, "end": s + 0.5, "caption": "x", "chars": [s]} for s in [x * 0.5 for x in range(12)]]
    A = RB.SceneReuse(T, {"frame": {}}, {}, {}, [], [], tmp_path, None, None, log=lambda s: None)
    B = RB.SceneReuse(T2, {"frame": {}}, {}, {}, [], [], tmp_path, None, None, log=lambda s: None)
    ctx = {"text": "", "autoText": "", "scenes": sc}
    miss = [[round(s["start"] * 30), round(s["end"] * 30)] for i, s in enumerate(sc)
            if A.token(i, ctx, round(s["start"] * 30), round(s["end"] * 30), "r", {}, []) != B.token(i, ctx, round(s["start"] * 30), round(s["end"] * 30), "r", {}, [])]
    assert RB.patch_ranges(T, [1], sc) == [[miss[0][0], miss[-1][1]]]


def test_near_gates_measure_only_changed_cuts(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(RB, "cut_boundary_gate", lambda T, M, st=None: seen.setdefault("③", [c["fp"] for c in T["cuts"]]) and [])
    monkeypatch.setattr(RB, "cut_content_gate", lambda T, M, st, doc, R, log, erase=None, autoblur=False, only=None: seen.setdefault("④", only) and [])
    monkeypatch.setattr(RB, "cut_still_gate", lambda T, M, st, ks=None, R=None: seen.setdefault("⑦", ks) and [])
    monkeypatch.setattr(RB, "blur_cut_gate", lambda T, M, st: [])
    for name in ("cut_length_gate", "rhythm_gate", "plan_reuse_gate", "photo_gate", "plan_length_gate"):      # 전체 관문이 불리면 터진다
        monkeypatch.setattr(RB, name, lambda *a, **k: 1 / 0)
    T = _T(("L", 0, 1, "a"), ("L", 1, 2, "b"), ("L", 2, 3, "c"), ("L", 3, 4, "d"))
    out = RB.timeline_gates(T, {"cand_dir": "x"}, {}, tmp_path, tmp_path, plan=False, near=[1, 2])
    assert seen == {"③": ["b", "c"], "④": [1, 2], "⑦": [1, 2]}
    assert [g for g, _ in out] == ["③ 경계", "④ 글자·얼굴", "⑦ 멈춤", "흐림 면적"]


def test_encoder_default_args_unchanged():
    """화면 규격(인코더) 고르기는 건드리지 않았다 — GOP 는 완성본을 굽는 두 곳에서만 더한다."""
    assert "-g" not in encoder.venc(16)
