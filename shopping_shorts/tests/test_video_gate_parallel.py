# -*- coding: utf-8 -*-
"""영상 관문 main·병합본 동시 측정(2026-10-03 사장님 "둘 다 해", 카드 088).
작업을 먼저 고르고(같은 작업) 두 쪽을 동시에 재되, 병합본 판정은 main 기준이 나온 뒤에 한다 → 판정은 차례 실행과 같다."""
import threading
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_video_gate_delta import FakeServer, JOBS, side, vg, _run  # noqa: F401


class ParServer(FakeServer):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.live = {"main": 0, "merged": 0}
        self.overlap = False
        self.lock = threading.Lock()

    def __call__(self, cmd, stdin=None, timeout=120):
        if "gate_pick_" in cmd:
            self.cmds.append(cmd)
            return 0, "IDS=" + " ".join(JOBS)
        if "done.txt" in cmd and "/out/" in cmd:
            w = self._which(cmd)
            with self.lock:
                self.live[w] += 1
                if self.live["main"] and self.live["merged"]:
                    self.overlap = True
            time.sleep(0.2)
            with self.lock:
                self.live[w] -= 1
        return super().__call__(cmd, stdin, timeout)


def test_두_쪽이_같은_작업을_동시에_잰다(monkeypatch):
    srv = ParServer(main=side(), merged=side())
    ok, fails, notes = _run(monkeypatch, srv)
    assert ok, fails
    for s in ("main", "merged"):
        assert all(j in srv.side[s]["evf_args"] for j in JOBS), "%s 쪽이 고른 작업을 안 받았다" % s
    assert srv.overlap, "두 쪽 측정이 겹치지 않았다(차례 실행)"
    assert any("동시 측정" in n for n in notes)


def test_동시여도_main에_있던_결함은_통과_더_나빠지면_막힘(monkeypatch):
    ok, fails, _ = _run(monkeypatch, ParServer(main=side(ghost=3, cc=1), merged=side(ghost=3, cc=1)))
    assert ok, fails
    ok, fails, _ = _run(monkeypatch, ParServer(main=side(ghost=3), merged=side(ghost=5)))
    assert not ok and any("잔상 5프레임" in f for f in fails)
    ok, fails, _ = _run(monkeypatch, ParServer(main=side(narr=0), merged=side(narr=2)))
    assert not ok and any("나레이션" in f for f in fails)


def test_동시여도_main을_못_재면_절대기준(monkeypatch):
    bad = side()
    bad["evf"] = "깨진 출력\n"
    ok, fails, notes = _run(monkeypatch, ParServer(main=bad, merged=side(ghost=3)))
    assert not ok and any("잔상 3프레임" in f for f in fails)
    assert any("main 을 못 재" in n for n in notes)


def test_작업을_못_고르면_종전_차례_실행(monkeypatch):
    srv = FakeServer(main=side(), merged=side())
    ok, fails, notes = _run(monkeypatch, srv)
    assert ok and not any("동시 측정" in n for n in notes)
