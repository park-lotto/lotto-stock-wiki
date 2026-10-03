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


def test_시험_칸은_동시에_두_개까지(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    inside, peak = [0], [0]
    lk = threading.Lock()

    def work():
        with track._gate_slot():
            with lk:
                inside[0] += 1
                peak[0] = max(peak[0], inside[0])
            time.sleep(0.6)
            with lk:
                inside[0] -= 1
    ts = [threading.Thread(target=work) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)
    assert peak[0] == track.GATE_SLOTS == 2, peak[0]


def test_선검사는_기본으로_안_돈다(repo, monkeypatch):
    """시험이 줄 밖에서 돌게 됐으니 같은 시험을 한 번 더 하는 선검사는 중복이다."""
    _make_track_commit(repo, "선검사없음")
    called = []
    monkeypatch.setattr(track, "_precheck", lambda *a, **k: called.append(1))
    monkeypatch.setattr(track, "_known_main_failures", lambda *a, **k: set())
    track.finish("선검사없음", repo=repo, gate=_LightGate(), video_gate=_ok_video)
    assert called == []
