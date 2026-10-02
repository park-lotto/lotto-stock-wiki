# -*- coding: utf-8 -*-
"""finish 시간 단축(2026-10-02 사장님 "이게 제일 시간 많이 잡아먹는 거야 / 할 수 있는 거 검증해서 다 해", 카드 081).

실측: 기준선 전체 테스트 7~10분이 거의 매번(오늘 main 커밋 108개 중 72개가 관제·핸드오프 — 커밋 번호 캐시가 안 먹음),
병합 폴더 전체 풀기 45초+지우기 19초, 대기열 선착순 아님(최대 2시간 26분), 대기 중 Claude 시간 제한으로 꺼짐."""
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_gate  # noqa: E402
import track  # noqa: E402
from test_track import repo, _git, _origin_head  # noqa: E402,F401  (픽스처 재사용)


def _make_track_commit(repo, name, fname="app.py", body="VALUE = 2\n"):
    track.start(name, repo=repo)
    wt = track.worktree_path(name, repo)
    _git(wt, "config", "user.email", "t@t.t")
    _git(wt, "config", "user.name", "t")
    p = wt / fname
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    _git(wt, "add", fname)
    _git(wt, "commit", "-m", f"{name} 작업")
    return wt


class _LightGate:
    """snapshot_light 가 있는 게이트 스텁 — 전체 snapshot 이 몇 번 불렸나 센다."""

    def __init__(self, after_failed=(), still=None):
        self.after_failed = list(after_failed)
        self.full = 0
        self.light = 0
        self.still = still

    def _snap(self, failed):
        return {"compile_ok": True, "import_ok": True, "pytest_rc": 0 if not failed else 1,
                "failed": list(failed), "import_out": "", "pytest_out": ""}

    def snapshot_light(self, cwd=None, **kw):
        self.light += 1
        return self._snap([])

    def snapshot(self, cwd=None, **kw):
        self.full += 1
        return self._snap(self.after_failed)

    def baseline_warnings(self, before):
        return []

    def compare(self, before, after):
        return merge_gate.compare(before, after)

    def rerun_ids(self, cwd, ids):
        return set(ids) if self.still is None else set(self.still) & set(ids)


_ok_video = lambda stage, br: __import__("video_gate").GateResult(True, False, "")   # noqa: E731


def test_기준선은_가볍게_전체_테스트는_한_번(repo, monkeypatch):
    _make_track_commit(repo, "가벼움")
    g = _LightGate()
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    track.finish("가벼움", repo=repo, gate=g, video_gate=_ok_video)
    assert g.light == 1 and g.full == 1, "기준선 전체 테스트를 돌렸다(light %d, full %d)" % (g.light, g.full)


def test_main에서도_실패하는_것은_통과_새로_깨진_것은_막힘(repo, monkeypatch):
    _make_track_commit(repo, "실패분류")
    monkeypatch.setattr(track, "_known_main_failures", lambda repo_, stage, ids, ref="HEAD": {"t/a.py::old"} & set(ids))
    track.finish("실패분류", repo=repo, gate=_LightGate(after_failed=["t/a.py::old"]), video_gate=_ok_video)
    _make_track_commit(repo, "실패분류2", fname="b.py", body="X = 1\n")
    before = _origin_head(repo)
    with pytest.raises(track.TrackError, match="새로 깨진"):
        track.finish("실패분류2", repo=repo, gate=_LightGate(after_failed=["t/a.py::old", "t/b.py::new"]), video_gate=_ok_video)
    assert _origin_head(repo) == before


def test_한_번만_실패하고_다시_돌리면_통과하면_우연한_실패로_본다(repo, monkeypatch):
    _make_track_commit(repo, "흔들림")
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    g = _LightGate(after_failed=["t/x.py::flaky"], still=[])           # 재실행하니 통과
    track.finish("흔들림", repo=repo, gate=g, video_gate=_ok_video)


def test_비코드_병합은_테스트를_생략한다(repo, monkeypatch):
    _make_track_commit(repo, "문서만", fname="handoff/문서만.md")
    g = _LightGate()
    track.finish("문서만", repo=repo, gate=g, video_gate=_ok_video)
    assert g.full == 0, "코드 없는 병합인데 전체 테스트를 돌렸다"


def test_main_실패_재확인은_코드_트리가_같으면_캐시(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(track, "_code_key", lambda cwd, ref="HEAD": "k1")
    monkeypatch.setattr(track, "_rerun_on_main", lambda stage, ids: calls.append(list(ids)) or {"a"})
    r = tmp_path / "repo"
    (r / track.TRACKS_DIR).mkdir(parents=True)
    assert track._known_main_failures(r, tmp_path, ["a", "b"]) == {"a"}
    assert track._known_main_failures(r, tmp_path, ["a", "b"]) == {"a"}
    assert calls == [["a", "b"]], "같은 코드 트리인데 main 재실행을 또 했다"


def test_대기열은_선착순(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    order = []
    first = track._FileLock(track._finish_lock_path(), "", queue=True).acquire()

    def waiter(tag, delay):
        time.sleep(delay)
        lk = track._FileLock(track._finish_lock_path(), "", queue=True).acquire()
        order.append(tag)
        time.sleep(0.2)
        lk.release()
    ts = [threading.Thread(target=waiter, args=("먼저", 0.1)), threading.Thread(target=waiter, args=("나중", 0.6))]
    for t in ts:
        t.start()
    time.sleep(1.2)
    first.release()
    for t in ts:
        t.join(20)
    assert order == ["먼저", "나중"], order


def test_영상_관문_뒤_다시_잡을_땐_줄_맨_앞(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    a = track._FileLock(track._finish_lock_path(), "", queue=True).acquire()
    a.release()
    b_ticket = track._FileLock(track._finish_lock_path(), "", queue=True)._new_ticket()
    a.acquire(priority=True)
    assert a._ticket.name < b_ticket.name, "다시 잡는 쪽이 줄 맨 뒤로 갔다"
    a.release()
    b_ticket.unlink()


def test_관련_테스트_고르기():
    tests = {"shopping_shorts/tests/test_tts.py": "from shopping_shorts import tts\n",
             "shopping_shorts/tests/test_app_x.py": "import shopping_shorts.app as a\n",
             "tools/test_track.py": "import track\n"}
    sel = track._select_related_tests(["shopping_shorts/tts.py", "tools/track.py", "README.md"], tests)
    assert sel == ["shopping_shorts/tests/test_tts.py", "tools/test_track.py"]
    assert track._select_related_tests(["handoff/x.md"], tests) == []


def test_finish_명령은_기본으로_분리_실행(monkeypatch):
    called = {}
    monkeypatch.setattr(track, "_finish_detached", lambda name: called.setdefault("d", name) and 0)
    monkeypatch.setattr(track, "finish", lambda name, **kw: called.setdefault("a", name) and 0)
    monkeypatch.delenv("TRACK_FINISH_CHILD", raising=False)
    monkeypatch.setenv("TRACK_REEXEC", "1")          # 최신 판본 바꿔 실행(카드 083)은 따로 시험
    track.main(["finish", "x"])
    assert called.get("d") == "x" and "a" not in called
    called.clear()
    track.main(["finish", "x", "--attached"])
    assert called.get("a") == "x" and "d" not in called


@pytest.mark.skipif(os.name != "nt", reason="윈도 콘솔 동작")
def test_분리_실행은_출력을_로그에_남기고_창을_띄우지_않는다(tmp_path):
    """10-02 실측 결함: 로그 0바이트 + finish 에 새 콘솔 창이 떠 닫히며 0xC000013A 로 죽었다. 실제 프로세스로 잰다."""
    import subprocess
    log, rcf = tmp_path / "x.log", tmp_path / "x.rc"
    child = [sys.executable, "-u", "-c",
             "import ctypes;print('보임=%s' % bool(ctypes.windll.user32.IsWindowVisible(ctypes.windll.kernel32.GetConsoleWindow())))"]
    subprocess.Popen([sys.executable, "-c", track._LAUNCHER, str(log), str(rcf), str(tmp_path)] + child,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    t = time.time()
    while not rcf.exists() and time.time() - t < 30:
        time.sleep(0.3)
    assert rcf.read_text().strip() == "0"
    assert "보임=False" in log.read_text(encoding="utf-8", errors="replace")


# ───────── 카드 083 후속 ─────────
def test_저장된_전체_실패목록이_있으면_그것이_기준선(repo, monkeypatch):
    """10-02 실측: 전체로 돌릴 때만 깨지는 원래 실패 15건이 '우연한 실패'로 통과됐다 → 병합 때 전체 실패 목록을 코드 트리별로 저장해 정확히 비교."""
    _make_track_commit(repo, "정확기준")
    monkeypatch.setattr(track, "_code_key", lambda cwd, ref="HEAD": "K1")
    track._store_full_failures(repo, "K1", ["t/a.py::old"])
    def boom(*a, **k):
        raise AssertionError("저장된 기준선이 있는데 재확인을 돌렸다")
    monkeypatch.setattr(track, "_known_main_failures", boom)
    g = _LightGate(after_failed=["t/a.py::old"])
    g.rerun_ids = boom
    track.finish("정확기준", repo=repo, gate=g, video_gate=_ok_video)
    assert g.full == 1


def test_병합되면_그_코드의_전체_실패목록을_저장한다(repo, monkeypatch):
    _make_track_commit(repo, "저장")
    keys = iter(["BEFORE", "AFTER", "AFTER", "AFTER"])
    monkeypatch.setattr(track, "_code_key", lambda cwd, ref="HEAD": next(keys, "AFTER"))
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: {"t/z.py::known"})
    track.finish("저장", repo=repo, gate=_LightGate(after_failed=["t/z.py::known"]), video_gate=_ok_video)
    assert track._load_full_failures(repo, "AFTER") == ["t/z.py::known"]


def test_재확인은_파일_단위로_돌린다():
    seen = []
    def fake_run(cmd, cwd):
        seen.append(cmd)
        return 1, "FAILED t/a.py::x - boom\nFAILED t/a.py::other - boom\n"
    got = merge_gate.rerun_ids(".", ["t/a.py::x", "t/a.py::y"], run=fake_run)
    args = seen[0]
    assert "t/a.py" in args and "t/a.py::x" not in args, "같은 파일 안 순서 영향을 재현하려면 파일 통째로 돌려야 한다"
    assert got == {"t/a.py::x"}, "물어본 id 만 돌려준다"


def test_옛_판본_트랙에서도_main_폴더의_최신_track_py로_돈다(tmp_path, monkeypatch):
    newer = tmp_path / "tools" / "track.py"
    newer.parent.mkdir(parents=True)
    newer.write_text("# 더 새 판본\n", encoding="utf-8")
    monkeypatch.setattr(track, "main_worktree", lambda cwd=None: tmp_path)
    monkeypatch.delenv("TRACK_REEXEC", raising=False)
    calls = []
    monkeypatch.setattr(track.subprocess, "call", lambda cmd, env=None, **kw: calls.append((cmd, env)) or 7)
    assert track.main(["list"]) == 7
    cmd, env = calls[0]
    assert str(newer) in cmd and env.get("TRACK_REEXEC") == "1"


def test_번호표를_먼저_받고_선검사한다(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    _make_track_commit(repo, "번호표먼저")
    q = Path(str(tmp_path / "f_queue"))
    seen = {}
    def pre(name, repo_, wt, br, gate):
        seen["tickets"] = len(list(q.glob("*_*_*"))) if q.exists() else 0
    monkeypatch.setattr(track, "_precheck", pre)
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    track.finish("번호표먼저", repo=repo, gate=_LightGate(), video_gate=_ok_video)
    assert seen.get("tickets") == 1, "선검사 때 이미 줄(번호표)에 서 있어야 한다"


def test_track_py를_고치는_트랙은_바꿔_실행하지_않는다(tmp_path, monkeypatch):
    newer = tmp_path / "tools" / "track.py"
    newer.parent.mkdir(parents=True)
    newer.write_text("# main 판본\n", encoding="utf-8")
    monkeypatch.setattr(track, "main_worktree", lambda cwd=None: tmp_path)
    monkeypatch.delenv("TRACK_REEXEC", raising=False)
    def fake_sh(cmd, cwd):
        if cmd[:2] == ["git", "show"]:
            return 0, "# origin/main 판본\n"
        if cmd[:2] == ["git", "diff"]:
            return 0, "tools/track.py\n"
        return 1, ""
    monkeypatch.setattr(track, "_sh", fake_sh)
    assert track._reexec_latest(["list"]) == (False, 0)
