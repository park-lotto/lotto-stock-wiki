"""소재 장면 전환 목록(seg_snap) — 검출·캐시·화면 데이터 싣기(2026-09-27).

쓰임: app.api_mix_scene_lab_data 가 DATA.scenecuts[video_id] 로 싣고 scene_play.js guardReadWindow 가 컷 읽는 창을 줄인다
  (창 가드 검사는 test_scene_play_read_guard.py). 조각 좌표를 고치는 '경계 붙이기'는 30일 job 90% 좌표를 바꾸고 새 잔상을 만들어
  뺐다 — 이 모듈은 전환 목록만 준다.
합성: 0~1초 = testsrc2(움직이는 무늬), 1~2초 = mandelbrot — 전환은 30번 프레임(1.000초).
"""
import shutil
import subprocess

import pytest

from shopping_shorts import seg_snap

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg 없음")

F = 1 / 30.0
CUT = 1.0


@pytest.fixture(scope="module")
def two_scene(tmp_path_factory):
    d = tmp_path_factory.mktemp("snap")
    p = d / "two.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", "testsrc2=s=180x320:r=30:d=1",
                    "-f", "lavfi", "-i", "mandelbrot=s=180x320:r=30",
                    "-filter_complex", "[1:v]trim=duration=1,setpts=PTS-STARTPTS[b];[0:v][b]concat=n=2:v=1[v]",
                    "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                   check=True, stdin=subprocess.DEVNULL)
    return p


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SEG_SNAP_CACHE_DIR", str(tmp_path / "cache"))
    seg_snap._MEM.clear()


def test_detects_the_one_cut(two_scene):
    cuts = seg_snap.detect_cuts(two_scene)
    assert len(cuts) == 1 and abs(cuts[0] - CUT) < 1e-3, cuts


def test_motion_is_not_a_cut():
    """빠른 움직임: 프레임마다 튐이 커도 앞뒤와 비슷하면 전환이 아니다."""
    m = [0.0] + [0.6] * 40
    assert seg_snap.cuts_from_motion(m, [i * F for i in range(41)]) == []
    m[20] = 2.5
    assert seg_snap.cuts_from_motion(m, [i * F for i in range(41)]) == [round(20 * F, 4)]


def test_edge_of_floors_to_ms():
    """0.001초 **내림** — 창 끝을 이 값으로 두면 전환 프레임(pts >= 값)이 읽히지 않는다(60fps x.xxx67 도)."""
    assert seg_snap.edge_of(12.0167) == 12.016
    assert seg_snap.edge_of(1.0) == 1.0
    assert seg_snap.edge_of(9.3) == 9.3


def test_cache_file_written_and_reused(two_scene, tmp_path):
    seg_snap.scene_cuts(two_scene)
    files = list((tmp_path / "cache").glob("*.scenecuts.json"))
    assert len(files) == 1
    seg_snap._MEM.clear()
    orig = seg_snap.detect_cuts
    try:
        seg_snap.detect_cuts = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("캐시를 안 읽었다"))
        assert seg_snap.scene_cuts(two_scene) == [CUT]
    finally:
        seg_snap.detect_cuts = orig


def test_failure_gives_empty_list(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    assert seg_snap.scene_cuts(bad) == []
    assert seg_snap.scene_cuts(tmp_path / "없음.mp4") == []


def test_scenecuts_map(two_scene):
    got = seg_snap.scenecuts_map({"s0": str(two_scene), "s1": str(two_scene)})
    assert got == {"s0": [1.0], "s1": [1.0]}


def test_app_ships_scenecuts_and_no_coordinate_snap(two_scene, monkeypatch, tmp_path):
    """화면 데이터에 전환 목록을 싣는다(app._lab_scenecuts). 조각 좌표를 바꾸는 붙이기는 없다."""
    from pathlib import Path
    from shopping_shorts import app
    monkeypatch.setattr(app, "_resolve_sources", lambda job, work: {"s0": str(two_scene)})
    assert app._lab_scenecuts({"job_id": "t"}, tmp_path) == {"s0": [1.0]}
    monkeypatch.setattr(app, "_resolve_sources", lambda job, work: (_ for _ in ()).throw(RuntimeError("x")))
    assert app._lab_scenecuts({"job_id": "t"}, tmp_path) == {}            # 못 재면 빈 목록(화면은 열린다)
    src = Path(app.__file__).read_text(encoding="utf-8")
    i = src.index("def api_mix_scene_lab_data(")
    body = src[i:src.index(chr(10) + "@app.", i)]
    assert '"scenecuts": _lab_scenecuts(job, work)' in body
    assert "_snap_segs" not in src and "snap_seg_map" not in src, "조각 좌표 붙이기가 되살아났다(청소본 서명·새 잔상)"
