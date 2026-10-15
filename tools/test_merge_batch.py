# -*- coding: utf-8 -*-
"""묶음 병합(관제 212, 2026-10-15) — 줄에 선 트랙들을 시험 1번·push 1번으로, 깨지면 반으로 나눠 범인만 뺀다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import track  # noqa: E402
from test_track import repo, _git, _origin_head  # noqa: E402,F401
from test_finish_speed import _LightGate, _make_track_commit, _ok_video  # noqa: E402


class _CountGate(_LightGate):
    """전체 시험 횟수를 세고, 병합본에 bad.py 가 있으면 새 실패를 낸다."""

    def __init__(self):
        super().__init__()
        self.runs = []

    def snapshot(self, cwd=None, paths=None, **kw):
        self.runs.append(sorted(p.name for p in Path(cwd).glob("t_*.py")))
        failed = ["tools/test_x.py::test_bad"] if (Path(cwd) / "bad.py").exists() else []
        return self._snap(failed)


def _queue(repo, name):
    return track._enqueue(repo, name, track.branch_name(name), track.worktree_path(name, repo), False)


def test_줄에_선_두_트랙은_시험_1번으로_같이_들어간다(repo, monkeypatch):
    monkeypatch.setattr(track, "BATCH_GATHER_SEC", 0)
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    _make_track_commit(repo, "가", fname="t_a.py", body="A = 1\n")
    _make_track_commit(repo, "나", fname="t_b.py", body="B = 1\n")
    _queue(repo, "가")
    _queue(repo, "나")
    g = _CountGate()
    track._merge_worker(repo, g, _ok_video)
    assert len(g.runs) == 1 and g.runs[0] == ["t_a.py", "t_b.py"], g.runs
    _git(repo, "fetch", "origin")
    files = _git(repo, "ls-tree", "--name-only", "origin/main")
    assert "t_a.py" in files and "t_b.py" in files
    q = track._queue_dir(repo)
    assert not list(q.glob("*__가.json")) and not list(q.glob("*__나.json")), "번호표는 결과로 바뀐다"
    assert len(list(q.glob("*.result.json"))) == 2


def test_묶음이_깨지면_반으로_나눠_깨뜨린_트랙만_뺀다(repo, monkeypatch):
    monkeypatch.setattr(track, "BATCH_GATHER_SEC", 0)
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    _make_track_commit(repo, "착한", fname="t_good.py", body="G = 1\n")
    _make_track_commit(repo, "나쁜", fname="bad.py", body="X = 1\n")
    _queue(repo, "착한")
    _queue(repo, "나쁜")
    g = _CountGate()
    track._merge_worker(repo, g, _ok_video)
    assert len(g.runs) == 3, "묶음 1번 + 반씩 2번"
    _git(repo, "fetch", "origin")
    files = _git(repo, "ls-tree", "--name-only", "origin/main")
    assert "t_good.py" in files and "bad.py" not in files
    import json
    res = {p.name.split("__")[1].split(".")[0]: json.loads(p.read_text(encoding="utf-8"))
           for p in track._queue_dir(repo).glob("*.result.json")}
    assert res["착한"]["rc"] == 0 and res["나쁜"]["rc"] == 1


def test_finish_는_줄에_올리고_일꾼이_되어_넣는다(repo, monkeypatch):
    monkeypatch.setattr(track, "BATCH_GATHER_SEC", 0)
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    _make_track_commit(repo, "혼자", fname="t_solo.py", body="S = 1\n")
    g = _CountGate()
    assert track.finish("혼자", repo=repo, gate=g, video_gate=_ok_video) == 0
    assert len(g.runs) == 1


def test_시험_자원을_기다리는_사이_온_트랙도_같은_묶음에_탄다(repo, monkeypatch):
    """2026-10-15 실측: 일꾼이 혼자일 때 묶음을 정하고 자원을 기다리는 사이 온 3트랙을 못 태웠다."""
    import contextlib
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    monkeypatch.setattr(track, "BATCH_GATHER_SEC", 0)
    _make_track_commit(repo, "먼저", fname="t_first.py", body="F = 1\n")
    _make_track_commit(repo, "나중", fname="t_late.py", body="L = 1\n")
    _queue(repo, "먼저")

    @contextlib.contextmanager
    def slow_slot(urgent=False, priority=False):
        _queue(repo, "나중")              # 자원을 기다리는 동안 다른 트랙이 줄에 선다
        yield 2
    monkeypatch.setattr(track, "_gate_slot", slow_slot)
    g = _CountGate()
    track._merge_worker(repo, g, _ok_video)
    assert g.runs == [["t_first.py", "t_late.py"]], g.runs
