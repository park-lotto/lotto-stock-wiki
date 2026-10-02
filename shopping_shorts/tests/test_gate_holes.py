# -*- coding: utf-8 -*-
"""finish 게이트 구멍 2개(2026-10-02 사장님 "남은 구멍 두 가지 해", 카드 075).

① 게이트 pytest 가 shopping_shorts/tests 만 돌아 tools/test_*.py 회귀를 못 잡았다
   (실측 10-02: 관제수리 병합이 tools/test_video_gate.py 의 모듈 수준 기대를 깨뜨렸는데 통과).
   tools 시험을 넣으면, 그 안의 finish 시험이 게이트가 쥔 **전역 락**을 다시 기다려 영원히 멈춘다 → 시험 중엔 개별 락.
② 영상 관문(서버 비교 10~25분)이 전역 병합 락 **안**에서 돌아 그동안 다른 트랙 finish 가 전부 줄을 섰다."""
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import merge_gate  # noqa: E402
import track  # noqa: E402


# ───────── ① tools 시험도 게이트에서 ─────────
def test_게이트_pytest는_tools_시험도_모은다(tmp_path):
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 0, "1 passed"
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "test_x.py").write_text("def test_x(): pass\n", encoding="utf-8")
    merge_gate.snapshot(tmp_path, run=fake_run)
    py = [c for c in calls if "pytest" in c]
    assert py, "pytest 를 안 돌렸다"
    args = py[0]
    assert any(a.replace("\\", "/").startswith("tools") for a in args), "tools 시험 경로가 pytest 인자에 없다: %r" % args
    assert "--continue-on-collection-errors" in args, "tools 쪽 수집 오류 하나로 전체가 안 돌면 안 된다"
    assert any("E" in a for a in args if a.startswith("-r")), "수집 오류(ERROR)도 실패 목록에 들어와야 한다"


def test_시험_중에는_전역_락이_아니라_개별_락():
    assert os.environ.get("PYTEST_CURRENT_TEST"), "pytest 안에서만 의미 있다"
    assert track._finish_lock_path() != track._FINISH_LOCK, "시험이 전역 락을 잡으면 게이트 안에서 교착한다"
    assert track._video_lock_path() != track._VIDEO_LOCK


def test_게이트_자식_pytest는_개별_락_환경을_받는다(tmp_path):
    seen = {}

    def fake_sub_run(cmd, cwd=None, capture_output=None, text=None, encoding=None, errors=None, env=None):
        seen.update(env or {})
        class R:
            returncode, stdout, stderr = 0, "", ""
        return R()
    orig = merge_gate.subprocess.run
    merge_gate.subprocess.run = fake_sub_run
    try:
        merge_gate._run(["x"], tmp_path)
    finally:
        merge_gate.subprocess.run = orig
    assert seen.get("TRACK_FINISH_LOCK") and seen.get("TRACK_VIDEO_LOCK"), "게이트가 띄운 pytest 는 개별 락 경로를 받아야 한다"


# ───────── ② 영상 관문은 전역 락 밖 ─────────
def test_영상_관문_도는_동안_다른_finish가_락을_얻는다(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    monkeypatch.setenv("TRACK_VIDEO_LOCK", str(tmp_path / "v.lock"))
    got_other = threading.Event()
    in_video = threading.Event()

    def video_gate(stage, br):
        in_video.set()
        got_other.wait(10)                      # 다른 finish 가 락을 얻을 때까지 영상 관문이 '돈다'
        from video_gate import GateResult
        return GateResult(True, True, "")

    def other():
        in_video.wait(10)
        with track._finish_gate_lock():
            got_other.set()

    t = threading.Thread(target=other)
    t.start()
    with track._finish_gate_lock() as lk:
        ok = track._run_video_gate_unlocked(lk, video_gate, "stage", "br")
    t.join(15)
    assert got_other.is_set(), "영상 관문이 도는 동안 다른 finish 가 전역 락을 못 얻었다"
    assert ok.ok


def test_락을_놓은_사이에도_내_임시폴더는_청소되지_않는다(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    stage = track.tracks_dir(repo) / (track.STAGE_PREFIX + "나")
    dead = track.tracks_dir(repo) / (track.STAGE_PREFIX + "죽은것")
    stage.mkdir(parents=True)
    dead.mkdir(parents=True)
    track._stage_owner_file(stage).write_text(str(os.getppid()), encoding="utf-8")   # 다른 살아 있는 프로세스(부모)가 쓰는 stage
    monkeypatch.setattr(track, "run", lambda cmd, cwd, check=False: (0, ""))
    removed = track._clean_dead_stages(repo)
    assert stage.exists() and "죽은것" in " ".join(removed) and (track.STAGE_PREFIX + "나") not in removed
