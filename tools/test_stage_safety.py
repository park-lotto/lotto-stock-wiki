# -*- coding: utf-8 -*-
"""병합 폴더 안전(2026-10-03 카드 093 실측): 동시 finish 의 청소가 막 만든 병합 폴더를 지우자 그 폴더의 `git merge` 가
main 폴더에서 돌아 MERGE_HEAD 가 남았고, main 폴더 동기화가 2시간 멈춰 모든 finish 가 옛 판본으로 돌았다."""
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import track  # noqa: E402
from test_track import repo, _git  # noqa: E402,F401
from test_finish_speed import _LightGate, _make_track_commit  # noqa: E402


def test_병합_폴더가_빈_폴더면_git_이_main_폴더로_올라가지_않는다(repo):
    fake = repo / track.TRACKS_DIR / (track.STAGE_PREFIX + "가짜")
    fake.mkdir(parents=True)
    rc, out = track.run(["git", "rev-parse", "--show-toplevel"], fake)
    assert rc != 0, "병합 폴더가 아닌데 git 이 상위 저장소(main 폴더)를 잡았다: %s" % out


def test_사라진_병합_폴더에서는_병합하지_않고_멈춘다(repo):
    _make_track_commit(repo, "사라짐")
    fake = repo / track.TRACKS_DIR / (track.STAGE_PREFIX + "사라짐")
    fake.mkdir(parents=True, exist_ok=True)
    with pytest.raises(track.TrackError, match="main 폴더 보호"):
        track._merge_and_gate("사라짐", repo, fake, "track/사라짐", _LightGate(), track.worktree_path("사라짐", repo))
    assert not (repo / ".git" / "MERGE_HEAD").exists(), "main 폴더에 병합이 걸렸다"


def test_청소는_주인_없는_막_생긴_폴더를_건드리지_않는다(repo, monkeypatch):
    root = repo / track.TRACKS_DIR
    young = root / (track.STAGE_PREFIX + "막생김")
    old = root / (track.STAGE_PREFIX + "오래됨")
    young.mkdir(parents=True)
    old.mkdir(parents=True)
    t = time.time() - track.STAGE_YOUNG_SEC - 60
    os.utime(old, (t, t))
    removed = track._clean_dead_stages(repo)
    assert young.exists() and (track.STAGE_PREFIX + "막생김") not in removed
    assert (track.STAGE_PREFIX + "오래됨") in removed


def test_주인_표시는_폴더를_만들기_전에(repo, monkeypatch):
    order = []
    real_mark, real_run = track._mark_stage_owner, track.run
    monkeypatch.setattr(track, "_mark_stage_owner", lambda st: (order.append("표시"), real_mark(st))[1])

    def spy(cmd, cwd, check=False):
        if cmd[:3] == ["git", "worktree", "add"]:
            order.append("만들기")
        return real_run(cmd, cwd, check)
    monkeypatch.setattr(track, "run", spy)
    st = track._open_stage(repo, "순서")
    try:
        assert order.index("표시") < order.index("만들기"), order
    finally:
        track._close_stage(repo, st)


def test_최신_판본은_origin_main_에_맞춘_도구_폴더에서(repo, monkeypatch):
    (repo / "tools").mkdir(exist_ok=True)
    (repo / "tools" / "track.py").write_text("# v1\n", encoding="utf-8")
    _git(repo, "add", "tools/track.py")
    _git(repo, "commit", "-m", "도구 v1")
    _git(repo, "push", "origin", "HEAD:main")
    monkeypatch.setattr(track, "main_worktree", lambda cwd=None: repo)
    p = track._latest_tools_track_py()
    assert p.read_text(encoding="utf-8") == "# v1\n"
    (repo / "tools" / "track.py").write_text("# v2\n", encoding="utf-8")
    _git(repo, "commit", "-am", "도구 v2")
    _git(repo, "push", "origin", "HEAD:main")
    _git(repo, "reset", "--hard", "HEAD~1")        # main 폴더는 낡았다(동기화 막힘 흉내)
    assert track._latest_tools_track_py().read_text(encoding="utf-8") == "# v2\n", "main 폴더가 낡아도 origin/main 판본이어야"
