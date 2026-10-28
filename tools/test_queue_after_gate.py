# -*- coding: utf-8 -*-
"""다 된 것만 줄 선다(2026-10-03 사장님 "다 된 것만 줄 서라 / 왜 줄 서고 이걸 해서 뒤에 거를 기다리게 하나", 카드 088).

전엔 전역 락(줄)을 쥔 채 병합본 전체 시험(6~7분)·관제 관문을 돌아 뒷사람이 그동안 기다렸다.
이제 시험·관문은 줄 밖(CPU 칸 2개)에서, 줄 안에선 커밋·push 만."""
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import track  # noqa: E402
from test_track import repo, _git, _origin_head  # noqa: E402,F401
from test_finish_speed import _LightGate, _make_track_commit, _ok_video  # noqa: E402


def test_시험은_줄_밖에서_돈다(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    _make_track_commit(repo, "줄밖")
    seen = {}

    class G(_LightGate):
        def snapshot(self, cwd=None, **kw):
            probe = track._FileLock(track._finish_lock_path(), "")
            import msvcrt
            probe.fh = open(probe.path, "a+")
            try:
                msvcrt.locking(probe.fh.fileno(), msvcrt.LK_NBLCK, 1)
                seen["free"] = True
                probe.fh.seek(0)
                msvcrt.locking(probe.fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                seen["free"] = False
            finally:
                probe.fh.close()
            return super().snapshot(cwd, **kw)
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    track.finish("줄밖", repo=repo, gate=G(), video_gate=_ok_video)
    assert seen.get("free") is True, "전체 시험 도는 동안 줄(전역 락)을 쥐고 있었다"


def test_새로_깨진_시험은_여전히_막힌다(repo, monkeypatch):
    _make_track_commit(repo, "줄밖막힘", fname="b.py", body="X = 1\n")
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    before = _origin_head(repo)
    with pytest.raises(track.TrackError, match="새로 깨진"):
        track.finish("줄밖막힘", repo=repo, gate=_LightGate(after_failed=["t/b.py::new"]), video_gate=_ok_video)
    assert _origin_head(repo) == before


def test_시험_프로세스_합계는_8개_이하(tmp_path, monkeypatch):
    """병합이 몰려도 동시에 도는 시험 프로세스 합계는 GATE_WORKER_TOKENS(코어 절반) 이하(카드 092)."""
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    monkeypatch.setattr(track, "_free_mb", lambda: 100000)
    using, peak = [0], [0]
    lk = threading.Lock()

    def work():
        with track._gate_slot() as n:
            with lk:
                using[0] += n
                peak[0] = max(peak[0], using[0])
            time.sleep(0.6)
            with lk:
                using[0] -= n
    ts = [threading.Thread(target=work) for _ in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    assert peak[0] <= track.GATE_WORKER_TOKENS == 4, peak[0]


def test_메모리가_모자라면_병렬을_줄이고_최소도_안되면_기다린다(tmp_path, monkeypatch):
    monkeypatch.delenv("GATE_XDIST_N", raising=False)
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    assert track._gate_target_workers(100000) == 4
    assert track._gate_target_workers(track.GATE_RESERVE_MB + 3 * track.GATE_WORKER_MB) == 3
    assert track._gate_target_workers(track.GATE_RESERVE_MB + track.GATE_WORKER_MB) == 0
    seq = iter([track.GATE_RESERVE_MB] * 2 + [100000] * 50)
    monkeypatch.setattr(track, "_free_mb", lambda: next(seq))
    monkeypatch.setattr(track.time, "sleep", lambda s: None)
    with track._gate_slot() as n:
        assert n == 4 and __import__("os").environ["GATE_XDIST_N"] == "4"
    assert "GATE_XDIST_N" not in __import__("os").environ


def test_merge_gate_는_정해준_병렬_수를_쓴다(monkeypatch):
    import merge_gate
    monkeypatch.setenv("GATE_XDIST_N", "3")
    assert merge_gate._xdist_args()[-1] == "3" or merge_gate._xdist_args() == []

def test_선검사는_기본으로_안_돈다(repo, monkeypatch):
    """시험이 줄 밖에서 돌게 됐으니 같은 시험을 한 번 더 하는 선검사는 중복이다."""
    _make_track_commit(repo, "선검사없음")
    called = []
    monkeypatch.setattr(track, "_precheck", lambda *a, **k: called.append(1))
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    track.finish("선검사없음", repo=repo, gate=_LightGate(), video_gate=_ok_video)
    assert called == []


# ───────── 카드 092: 재시도는 끼어든 코드 관련만 ─────────
def _commit_main(repo, rel, body):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", "main 쪽 끼어든 커밋 " + rel)
    _git(repo, "push", "origin", "HEAD:main")


def test_재시도_범위_비코드면_생략_코드면_관련만(repo):
    _commit_main(repo, "shopping_shorts/tests/test_mod.py", "import shopping_shorts.mod\n")
    _commit_main(repo, "shopping_shorts/tests/test_other.py", "import shopping_shorts.other\n")
    track.start("재시도범위", repo=repo)
    stage = track._open_stage(repo, "재시도범위")
    try:
        base = _git(stage, "rev-parse", "HEAD").strip()
        _commit_main(repo, "handoff/x.md", "문서\n")
        _git(stage, "fetch", "origin")
        _git(stage, "reset", "--hard", "origin/main")
        assert track._retry_test_subset(stage, base, ["app.py"]) == [], "끼어든 게 문서뿐이면 시험 생략"
        base2 = _git(stage, "rev-parse", "HEAD").strip()
        _commit_main(repo, "shopping_shorts/mod.py", "X = 2\n")
        _git(stage, "fetch", "origin")
        _git(stage, "reset", "--hard", "origin/main")
        assert track._retry_test_subset(stage, base2, []) == ["shopping_shorts/tests/test_mod.py"]
    finally:
        track._close_stage(repo, stage)


def test_재시도_내_변경과_안_겹치면_내_파일_관련_시험은_안_넣는다(repo):
    """관제 212(2026-10-15): 종전엔 내 app.py 까지 넣어 거의 모든 시험이 걸려 매번 전체로 갔다(재시험 83회·약 700분)."""
    _commit_main(repo, "shopping_shorts/tests/test_mod.py", "import shopping_shorts.mod\n")
    _commit_main(repo, "shopping_shorts/tests/test_app_a.py", "import shopping_shorts.app\n")
    _commit_main(repo, "shopping_shorts/tests/test_app_b.py", "import shopping_shorts.app\n")
    track.start("재시도겹침", repo=repo)
    stage = track._open_stage(repo, "재시도겹침")
    try:
        base = _git(stage, "rev-parse", "HEAD").strip()
        _commit_main(repo, "shopping_shorts/mod.py", "X = 3\n")
        _git(stage, "fetch", "origin")
        _git(stage, "reset", "--hard", "origin/main")
        mine = ["shopping_shorts/app.py"]
        assert track._retry_test_subset(stage, base, mine) == ["shopping_shorts/tests/test_mod.py"], \
            "안 겹치면 끼어든 mod 관련만"
        # 같은 파일을 둘 다 고쳤으면 내 변경 관련까지(맞물림)
        sub = track._retry_test_subset(stage, base, ["shopping_shorts/mod.py", "shopping_shorts/app.py"])
        assert sub is None or "shopping_shorts/tests/test_app_a.py" in sub
    finally:
        track._close_stage(repo, stage)


def test_재시도_안_겹치는_화면파일은_그_이름을_읽는_시험만_없으면_생략(repo):
    _commit_main(repo, "shopping_shorts/tests/test_js.py", "P = 'static/a.js'\n")
    track.start("재시도화면", repo=repo)
    stage = track._open_stage(repo, "재시도화면")
    try:
        base = _git(stage, "rev-parse", "HEAD").strip()
        _commit_main(repo, "shopping_shorts/static/a.js", "var a=1\n")
        _git(stage, "fetch", "origin")
        _git(stage, "reset", "--hard", "origin/main")
        assert track._retry_test_subset(stage, base, ["shopping_shorts/app.py"]) == ["shopping_shorts/tests/test_js.py"]
        base2 = _git(stage, "rev-parse", "HEAD").strip()
        _commit_main(repo, "shopping_shorts/static/zz.html", "<b>\n")
        _git(stage, "fetch", "origin")
        _git(stage, "reset", "--hard", "origin/main")
        assert track._retry_test_subset(stage, base2, ["shopping_shorts/app.py"]) == [], "읽는 시험 없음 → 생략"
    finally:
        track._close_stage(repo, stage)


def test_같은_트랙_finish_는_하나만(repo):
    """관제 212: 같은 트랙 둘은 병합 폴더 _merge-<트랙> 을 같이 써 서로 지운다(10-15 실측)."""
    a = track._track_finish_lock("중복", repo)
    try:
        assert a is not None
        assert track._track_finish_lock("중복", repo) is None, "둘째는 거절"
        assert track._track_finish_lock("다른트랙", repo) is not None, "다른 트랙은 상관없다"
        with pytest.raises(track.TrackError, match="이미 돌고"):
            track.finish("중복", repo=repo)
    finally:
        a.close()
    b = track._track_finish_lock("중복", repo)
    assert b is not None, "앞이 끝나면 다시 잡힌다"
    b.close()


def test_재시험은_시험자원_줄에서_자기_순번(monkeypatch, tmp_path):
    import inspect
    assert "priority" in inspect.signature(track._gate_slot).parameters
    src = inspect.getsource(track._merge_and_gate)
    assert "priority=bool(prev_base)" in src


def test_재시도는_통과한_뒤_끼어든_코드_관련만_다시_돌린다(repo, monkeypatch):
    monkeypatch.setenv("TRACK_SOLO", "1")   # 옛 경로(혼자 병합·끼어듦 재시험) 시험 — 묶음 병합에선 끼어듦이 없다(관제 212)
    _commit_main(repo, "shopping_shorts/tests/test_mod.py", "import shopping_shorts.mod\n")
    _make_track_commit(repo, "재시도시험")
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    calls = {"push": 0}
    real = track._commit_and_push

    def fake_push(*a, **k):
        calls["push"] += 1
        if calls["push"] == 1:
            _commit_main(repo, "shopping_shorts/mod.py", "X = 3\n")      # 시험하는 사이 main 에 코드가 끼어든다
            return "raced"
        return real(*a, **k)
    monkeypatch.setattr(track, "_commit_and_push", fake_push)
    seen = []

    class G(_LightGate):
        def snapshot(self, cwd=None, paths=None, **kw):
            seen.append(paths)
            return super().snapshot(cwd, **kw)
    track.finish("재시도시험", repo=repo, gate=G(), video_gate=_ok_video)
    assert seen[0] is None and seen[1] == ["shopping_shorts/tests/test_mod.py"], seen


def test_재시도에서도_끼어든_코드와_맞물려_깨지면_막는다(repo, monkeypatch):
    monkeypatch.setenv("TRACK_SOLO", "1")   # 옛 경로(혼자 병합·끼어듦 재시험) 시험 — 묶음 병합에선 끼어듦이 없다(관제 212)
    _commit_main(repo, "shopping_shorts/tests/test_mod.py", "import shopping_shorts.mod\n")
    _make_track_commit(repo, "재시도막힘")
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    state = {"n": 0}
    real = track._commit_and_push

    def fake_push(*a, **k):
        state["n"] += 1
        if state["n"] == 1:
            _commit_main(repo, "shopping_shorts/mod.py", "X = 4\n")
            return "raced"
        return real(*a, **k)
    monkeypatch.setattr(track, "_commit_and_push", fake_push)

    class G(_LightGate):
        def snapshot(self, cwd=None, paths=None, **kw):
            failed = ["shopping_shorts/tests/test_mod.py::t"] if paths else []
            return self._snap(failed)
    before = _origin_head(repo)
    with pytest.raises(track.TrackError, match="새로 깨진"):
        track.finish("재시도막힘", repo=repo, gate=G(), video_gate=_ok_video)
    assert state["n"] == 1


def test_병렬_수_환경값은_시험_자식에_새지_않는다(tmp_path, monkeypatch):
    """092 실측: GATE_XDIST_N 이 자식 pytest 에 새어 그 값을 검사하는 시험 4건이 게이트 안에서만 깨졌다."""
    import merge_gate
    monkeypatch.setenv("GATE_XDIST_N", "3")
    rc, out = merge_gate._run([sys.executable, "-c", "import os;print('N=' + os.environ.get('GATE_XDIST_N', '없음'))"], tmp_path)
    assert "N=없음" in out, out
