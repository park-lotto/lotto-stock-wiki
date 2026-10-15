# -*- coding: utf-8 -*-
"""묶음 병합(관제 212, 2026-10-15) — 줄에 선 트랙들을 시험 1번·push 1번으로, 깨지면 반으로 나눠 범인만 뺀다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import track  # noqa: E402
from test_track import repo, _git, _origin_head  # noqa: E402,F401
from test_finish_speed import _LightGate, _make_track_commit, _ok_video  # noqa: E402
from test_queue_after_gate import _commit_main  # noqa: E402


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


# ── 관제 212 진단(Fable) 수리 검증 ─────────────────────────────────────────
def test_영상관문은_묶음_라벨이면_병합본_트리해시를_쓴다(repo):
    import video_gate
    _make_track_commit(repo, "영1", fname="t_v1.py", body="V = 1\n")
    _make_track_commit(repo, "영2", fname="t_v2.py", body="W = 1\n")
    stage = track._open_stage(repo, "_vg")
    try:
        _git(stage, "merge", "--no-ff", "--no-commit", "track/영1", "track/영2")
        calls = []

        def sh(cmd, timeout=None):
            calls.append(cmd)
            return 1, "서버 없음(시험)"
        ok, fails, notes = video_gate._measure_and_judge(sh, stage, "묶음(2)", {}, None, say=lambda s: None)
        assert not any("해시를 못 읽었다" in f for f in fails), fails
        assert calls, "해시를 읽은 뒤 서버 단계까지 갔다"
    finally:
        track._close_stage(repo, stage)


def test_관제_오류_트랙이_섞여도_일꾼은_살고_나머지는_들어간다(repo, monkeypatch):
    monkeypatch.setattr(track, "BATCH_GATHER_SEC", 0)
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    _make_track_commit(repo, "정상1", fname="t_n1.py", body="N = 1\n")
    _make_track_commit(repo, "폭탄", fname="t_bomb.py", body="B = 1\n")
    _make_track_commit(repo, "정상2", fname="t_n2.py", body="M = 1\n")
    for n in ("정상1", "폭탄", "정상2"):
        _queue(repo, n)
    real = track._control.finish_gate

    def fg(repo_, stage, br, name, *a, **k):
        if name == "폭탄":
            raise RuntimeError("관제 내부 오류(시험)")
        return real(repo_, stage, br, name, *a, **k)
    monkeypatch.setattr(track._control, "finish_gate", fg)
    g = _CountGate()
    track._merge_worker(repo, g, _ok_video)
    assert g.runs == [["t_n1.py", "t_n2.py"]], g.runs
    import json
    res = {p.name.split("__")[1].split(".")[0]: json.loads(p.read_text(encoding="utf-8"))
           for p in track._queue_dir(repo).glob("*.result.json")}
    assert res["폭탄"]["rc"] == 1 and res["정상1"]["rc"] == 0 and res["정상2"]["rc"] == 0


def test_등록_뒤에_한_커밋은_이번_묶음에_안_들어간다(repo, monkeypatch):
    monkeypatch.setattr(track, "BATCH_GATHER_SEC", 0)
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    wt = _make_track_commit(repo, "늦은커밋", fname="t_first.py", body="F = 1\n")
    _queue(repo, "늦은커밋")
    (wt / "t_after.py").write_text("A = 1\n", encoding="utf-8")
    _git(wt, "add", "t_after.py")
    _git(wt, "commit", "-m", "등록 뒤 커밋")
    track._merge_worker(repo, _CountGate(), _ok_video)
    _git(repo, "fetch", "origin")
    files = _git(repo, "ls-tree", "--name-only", "origin/main")
    assert "t_first.py" in files and "t_after.py" not in files


def test_주인이_죽은_번호표는_조용히_사라지지_않고_결과가_남는다(repo):
    import json
    _make_track_commit(repo, "고아", fname="t_o.py", body="O = 1\n")
    t = _queue(repo, "고아")
    d = json.loads(t.read_text(encoding="utf-8"))
    d["pid"] = 999999                                  # 없는 프로세스
    t.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert track._queue_pending(repo) == []
    r = json.loads(t.with_name(t.name[:-5] + ".result.json").read_text(encoding="utf-8"))
    assert r["rc"] == 1 and "죽어" in r["msg"]


def test_일꾼은_자기_결과가_나오면_남은_줄을_넘기고_빠진다(repo, monkeypatch):
    monkeypatch.setattr(track, "BATCH_GATHER_SEC", 0)
    _make_track_commit(repo, "나", fname="t_me.py", body="M = 1\n")
    t = _queue(repo, "나")
    res = t.with_name(t.name[:-5] + ".result.json")
    res.write_text('{"rc": 0, "msg": "x"}', encoding="utf-8")
    g = _CountGate()
    track._merge_worker(repo, g, _ok_video, own_result=res)
    assert g.runs == [], "자기 결과가 이미 있으면 묶음을 돌지 않고 빠진다"


def test_깨진_시험과_관련된_트랙이_하나면_그것만_먼저_빼서_시험_횟수를_줄인다(repo, monkeypatch):
    """이분이면 3트랙 중 1개 범인에 시험 5번 — 용의 트랙을 먼저 빼면 3번(묶음 1 + 나머지 1 + 범인 1)."""
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    _commit_main(repo, "shopping_shorts/tests/test_culprit.py", "import shopping_shorts.culprit\n")
    _make_track_commit(repo, "착1", fname="t_ok1.py", body="A = 1\n")
    _make_track_commit(repo, "범인", fname="shopping_shorts/culprit.py", body="X = 1\n")
    _make_track_commit(repo, "착2", fname="t_ok2.py", body="B = 1\n")
    for n in ("착1", "범인", "착2"):
        _queue(repo, n)

    class G(_CountGate):
        def snapshot(self, cwd=None, paths=None, **kw):
            self.runs.append(sorted(p.name for p in Path(cwd).glob("t_*.py")))
            bad = (Path(cwd) / "shopping_shorts" / "culprit.py").exists()
            return self._snap(["shopping_shorts/tests/test_culprit.py::test_x"] if bad else [])
    g = G()
    track._merge_worker(repo, g, _ok_video)
    assert len(g.runs) == 3, g.runs
    _git(repo, "fetch", "origin")
    files = _git(repo, "ls-tree", "-r", "--name-only", "origin/main")
    assert "t_ok1.py" in files and "t_ok2.py" in files and "shopping_shorts/culprit.py" not in files
