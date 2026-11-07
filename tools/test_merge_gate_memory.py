# -*- coding: utf-8 -*-
"""관문 pytest 메모리(관제 336, 2026-11-07).

사고: 관문이 전체 시험을 한 pytest 로 돌리면 xdist 일꾼이 메모리를 쌓아(4.3·4.9GB) PC 커밋이 바닥나고,
같은 PC 의 Claude 세션·훅이 'malloc failed' 로 죽었다. 수리 = merge_gate.run_pytest 한 곳이 ① 묶음마다 새 pytest
② 남은 메모리 바닥 아래면 시험 트리를 끝냄(자원 부족 실패 → 병합 거절·PC 삶).
"""
import re
import subprocess
import sys
import time
from pathlib import Path

import merge_gate
import track

TOOLS = Path(__file__).resolve().parent


def test_관문_pytest_호출은_run_pytest_한_곳뿐():
    """판단 주인 지킴이 — 관문 도구에 '-m pytest' 를 새로 적으면 묶음·메모리 감시를 건너뛴다."""
    pat = re.compile(r'"-m",\s*"pytest"')
    gate_src = (TOOLS / "merge_gate.py").read_text(encoding="utf-8")
    track_src = (TOOLS / "track.py").read_text(encoding="utf-8")
    assert len(pat.findall(gate_src)) == 1, "merge_gate 안에서 pytest 를 띄우는 곳은 run_pytest 하나여야 한다"
    body = gate_src.split("def run_pytest(", 1)[1].split("\ndef ", 1)[0]
    assert pat.search(body), "그 하나가 run_pytest 안에 있어야 한다"
    assert not pat.search(track_src), "track.py 는 pytest 를 직접 띄우지 말고 merge_gate.run_pytest 를 부른다"


def test_묶음마다_새_pytest(tmp_path):
    for i in range(5):
        (tmp_path / f"test_{i}.py").write_text("def test_x(): pass\n", encoding="utf-8")
    seen = []

    def fake(cmd, cwd):
        seen.append([c for c in cmd if c.endswith(".py")])
        return 0, "ok"
    rc, _ = merge_gate.run_pytest(tmp_path, ["."], run=fake, workers=0, chunk=2)
    assert rc == 0
    assert [len(s) for s in seen] == [2, 2, 1], "파일 5개를 2개씩 = pytest 3번"
    assert sum(seen, []) == [f"test_{i}.py" for i in range(5)], "빠지거나 겹친 파일이 없어야 한다"


def test_자원부족이면_남은_묶음을_돌리지_않는다(tmp_path):
    calls = []

    def fake(cmd, cwd):
        calls.append(cmd)
        return merge_gate.GATE_LOW_MEMORY_RC, "FAILED GATE_LOW_MEMORY::x - 부족\n"
    rc, out = merge_gate.run_pytest(tmp_path, ["a.py", "b.py", "c.py"], run=fake, workers=0, chunk=1)
    assert len(calls) == 1 and rc == merge_gate.GATE_LOW_MEMORY_RC
    assert "GATE_LOW_MEMORY::x" in merge_gate.parse_failed(out), "자원 부족은 실패로 남아 병합을 막는다"


def test_종료코드_합치기():
    assert merge_gate._merge_rc([0, 5, 0]) == 0, "시험 0개인 묶음(5)이 전체를 망치면 안 된다"
    assert merge_gate._merge_rc([0, 1, 0]) == 1
    assert merge_gate._merge_rc([1, 2, 0]) == 2, "수집·내부 오류는 숨기지 않는다"
    assert merge_gate._merge_rc([5, 5]) == 5


def test_실패_목록은_모든_묶음에서_모인다(tmp_path):
    outs = iter(["FAILED a.py::t1 - x\n", "FAILED b.py::t2 - y\n"])
    rc, out = merge_gate.run_pytest(tmp_path, ["a.py", "b.py"], run=lambda c, w: (1, next(outs)), workers=0, chunk=1)
    assert rc == 1 and merge_gate.parse_failed(out) == {"a.py::t1", "b.py::t2"}


def test_남은_메모리가_바닥이면_시험_트리를_끝낸다(monkeypatch):
    monkeypatch.setattr(merge_gate, "free_mb", lambda: 100)
    monkeypatch.setattr(merge_gate, "GATE_MEM_POLL_SEC", 0.2)
    monkeypatch.setenv("GATE_ABORT_FREE_MB", "3000")
    t0 = time.time()
    rc, out = merge_gate._run([sys.executable, "-c", "import time; time.sleep(60)"], TOOLS)
    assert time.time() - t0 < 30, "바닥인데 시험이 끝까지 돌았다"
    assert rc == merge_gate.GATE_LOW_MEMORY_RC
    assert any(f.startswith("GATE_LOW_MEMORY::") for f in merge_gate.parse_failed(out))


def test_메모리가_넉넉하면_그대로_끝난다(monkeypatch):
    monkeypatch.setattr(merge_gate, "free_mb", lambda: 10 ** 6)
    monkeypatch.setattr(merge_gate, "GATE_MEM_POLL_SEC", 0.1)
    rc, out = merge_gate._run([sys.executable, "-c", "print('hi')"], TOOLS)
    assert rc == 0 and "hi" in out and "GATE_LOW_MEMORY" not in out


def test_자원관문도_같은_메모리_값을_본다(monkeypatch):
    monkeypatch.setattr(merge_gate, "free_mb", lambda: 1234)
    assert track._free_mb() == 1234, "시작 판단과 관문 중 감시가 다른 값을 보면 어긋난다"


def test_폴더는_시험_파일로_펼친다(tmp_path):
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "test_b.py").write_text("", encoding="utf-8")
    (tmp_path / "t" / "test_a.py").write_text("", encoding="utf-8")
    (tmp_path / "t" / "helper.py").write_text("", encoding="utf-8")
    got = merge_gate.expand_test_paths(tmp_path, ["t", "x.py::id", "t/test_a.py"])
    assert got == ["t/test_a.py", "t/test_b.py", "x.py::id"]
