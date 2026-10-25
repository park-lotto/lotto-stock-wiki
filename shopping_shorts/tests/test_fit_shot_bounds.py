"""preset_make.fit_shot 의 장면 경계 = render_bench 한 벌(10-26, 98 #111).

옛 판: fit_shot 은 check_shot_cross.shot_cuts(ffmpeg scene>0.25), 관문 ③은 render_bench.shot_starts — 자가 두 벌이라 태양의맛썬 40.50·
식기세척기 50.43 진짜 편집점을 계획이 못 피하고 관문에서 멈췄다. 또 24fps 원본은 `-ss` 뒤 첫 화면이 ss 보다 최대 1원본프레임 늦어
(식기세척기 50.433 → 50.467) 컷 끝이 다음 샷 1프레임을 끌고 왔는데 관문 ③도 ss 부터 재 못 봤다(눈 확인) → render_bench.src_start."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import check_shot_cross as CSC  # noqa: E402
from tools.calcopy.engine import preset_make as PM  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402


def _src(tmp, r=30, name="a.mp4", d=4):
    p = tmp / name
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s=320x240:r={r}:d={d}", "-pix_fmt", "yuv420p", str(p)],
                   check=True, stdin=subprocess.DEVNULL)
    return p


def _cut(p, ss=1.0, n=60, **k):
    return {"src": p.name, "path": p, "ss": ss, "n": n, "speed": 1.0, "meme": False, "src_dur": 4.0, **k}


def test_fit_shot_uses_render_bench_bounds(tmp_path, monkeypatch):
    """경계 자 = render_bench.shot_starts: 앞 0.1초 번쩍 → snap_ss 와 같은 자리(1.1)로. check_shot_cross.shot_cuts 는 더 없다."""
    p = _src(tmp_path)
    monkeypatch.setattr(RB, "shot_starts", lambda v: [1.1])
    assert not hasattr(CSC, "shot_cuts")
    c = _cut(p)
    PM.fit_shot(c, {})                                  # fit_shot.enabled 꺼져도 경계 맞춤은 한다(render_bench 나레 컷처럼)
    assert c["ss"] == pytest.approx(1.1) and c["ss_planned"] == 1.0 and c["speed"] == 1.0
    assert c["ss"] == RB.snap_ss(p, 1.0, c["n"] / RB.FPS)


def test_fit_shot_no_snap_and_clean_cut_untouched(tmp_path, monkeypatch):
    p = _src(tmp_path)
    monkeypatch.setattr(RB, "shot_starts", lambda v: [1.1])
    c = _cut(p, no_snap=True)
    PM.fit_shot(c, {"enabled": True})
    assert c["ss"] == 1.0 and c["speed"] == 1.0 and "ss_planned" not in c       # 입 맞춤 컷은 render_bench 처럼 검사만
    c = _cut(p, ss=2.0, n=30)
    PM.fit_shot(c, {"enabled": True})
    assert c["ss"] == 2.0 and c["speed"] == 1.0


def test_fit_shot_tail_stretch_when_snap_fails(tmp_path, monkeypatch):
    """±0.4초로 못 피하는 꼬리 번쩍(앞뒤 경계 촘촘) → 늘림(fit_shot.enabled, min_speed 까지) — 원본에서 읽는 끝이 경계 앞."""
    p = _src(tmp_path)
    monkeypatch.setattr(RB, "shot_starts", lambda v: [0.95, 2.9, 3.2])   # ±0.4초 어디로 옮겨도 짧은 조각이 남는다
    c = _cut(p, ss=1.0, n=60)                           # [1.0,3.0) = 꼬리 2.9~3.0 번쩍 0.1초
    assert RB.snap_ss(p, 1.0, 2.0) == 1.0
    PM.fit_shot(c, {"enabled": True, "min_speed": 0.75})
    assert c["ss"] == 1.0 and c["speed"] == pytest.approx(0.95)       # 원본 1.9초를 2초로 늘림 — 경계 2.9 앞에서 끝
    assert not RB.short_pieces([0.95, 2.9, 3.2], 1.0, 1.0 + round(c["n"] * c["speed"]) / RB.FPS)
    c = _cut(p, ss=1.0, n=60)
    PM.fit_shot(c, {})                                  # 늘림 꺼짐 → 그대로(관문 ③이 멈춘다)
    assert c["ss"] == 1.0 and c["speed"] == 1.0


def test_src_start_24fps_and_gate_sees_tail_frame(tmp_path, monkeypatch):
    """24fps 원본: 첫 화면 = ss 이상 첫 원본 프레임. 관문 ③은 그 초부터 재서 끝 1프레임 다음 샷을 잡는다(옛 판 = ss 부터 재 놓침)."""
    p24, p30 = _src(tmp_path, 24, "b.mp4"), _src(tmp_path, 30, "c.mp4")
    assert RB.src_start(p24, 1.01) == pytest.approx(25 / 24, abs=1e-3)
    assert RB.src_start(p24, 25 / 24) == pytest.approx(25 / 24, abs=1e-3)
    assert RB.src_start(p30, 1.0) == 1.0 and RB.src_start(p30, 1.4) == 1.4
    monkeypatch.setattr(RB, "shot_starts", lambda v: [1.9667])
    T = {"cuts": [{"src": p24.name, "ss": 1.01, "frames": 29, "line": "줄1"}]}
    bad = RB.cut_boundary_gate(T, {"cand_dir": str(tmp_path)})
    assert bad and "1.97" in bad[0]
    assert RB.cut_boundary_gate({"cuts": [{**T["cuts"][0], "src": p30.name, "ss": 1.0}]}, {"cand_dir": str(tmp_path)}) == []   # 30fps 격자 ss 는 끝 경계 밖
    s = RB.snap_ss(p24, 1.01, 29 / RB.FPS)
    e = RB.src_start(p24, s)
    assert s != 1.01 and not RB.short_pieces([1.9667], e, e + 29 / RB.FPS)


def test_check_shot_cross_same_judgment_and_missing_source(tmp_path, monkeypatch):
    p = _src(tmp_path)
    mk = tmp_path / "make"
    mk.mkdir()
    (mk / "timeline.json").write_text(json.dumps({"groups": [
        {"src": p.name, "ss": 1.0, "dur": 2.0, "t0": 0.0, "pieces": [0]},
        {"src": "gone.mp4", "ss": 1.0, "dur": 1.0, "t0": 2.0, "pieces": [1]},
        {"src": "meme:x", "ss": 0.0, "dur": 1.0, "t0": 3.0, "pieces": [2]}]}), encoding="utf-8")
    monkeypatch.setattr(RB, "shot_starts", lambda v: [1.1])
    monkeypatch.setattr(CSC, "shot_starts", RB.shot_starts)
    r = CSC.check(mk)
    assert len(r) == 2
    assert r[0]["flash"] and r[0]["short"] == [0.1] and r[0]["head"] and r[0]["fix_ss"] == pytest.approx(1.1)
    assert r[1].get("missing") and not r[1]["flash"]                   # 옛 판은 원본이 없어도 '경계 없음'으로 통과시켰다
