"""관제 304 — 흐림 칸만 바뀐 다시 계획은 컷을 다시 짜지 않는다.

주인: 컷을 다시 짤 입력인가 = render_bench.plan_input_sig · 지난 계획 꺼내기 = render_bench.plan_again · 멈춤 재기 캐시 = render_bench.cut_still_gate(R).
판정(foreign_text·still_spans·문턱)은 그대로다. 재는 것 = timeline·목소리가 불렸나, 조각 그림을 몇 번 읽었나.
"""
import json
import os
from pathlib import Path

import numpy as np
import pytest

from shopping_shorts.tests.test_plan_voice_len import _doc, _stub
from tools.calcopy.hybrid import flow as F
from tools.calcopy.hybrid import render_bench as RB
from tools.calcopy.hybrid import styles as STY


@pytest.fixture
def plan(monkeypatch, tmp_path):
    """가짜 목소리로 계획을 돌리는 도구. calls = {tl: timeline 횟수, tts: 합성 횟수, gate: 관문 ④ 횟수}."""
    called = []
    _stub(monkeypatch, {"N1": 12.0, "N2": 14.0}, called)
    calls = {"tl": 0, "gate": 0}
    real = RB.timeline

    def tl(*a, **k):
        calls["tl"] += 1
        return real(*a, **k)
    monkeypatch.setattr(RB, "timeline", tl)

    def gate(*a, **k):
        calls["gate"] += 1
        return []
    monkeypatch.setattr(RB, "cut_content_gate", gate)
    d = _doc(tmp_path)

    def run(**k):
        return RB.render("t", d, tmp_path / "w", plan_only=True, log=lambda *a: None, report=True, **k)
    return run, d, calls, called


def _edit(d: Path, name: str, fn):
    p = d / name
    o = json.loads(p.read_text(encoding="utf-8"))
    fn(o)
    p.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")


def test_blur_only_replan_keeps_cuts(plan):
    """흐림 칸만 늘면 timeline·목소리를 다시 안 부르고 관문만 다시 잰다. 컷·배치·길이는 첫 계획 그대로."""
    run, d, calls, called = plan
    a = run()
    _edit(d, "재료.json", lambda M: M.setdefault("blur", {}).setdefault("a.mp4", []).append([0, 0, 10, 10, 0.0, 1.0]))
    b = run()
    assert calls["tl"] == 1 and called == ["tts"]
    assert calls["gate"] == 2
    assert [c["ss"] for c in b["timeline"]["cuts"]] == [c["ss"] for c in a["timeline"]["cuts"]]
    assert b["length"] == a["length"]


def test_blur_wiped_replan_keeps_cuts(plan):
    """지시서가 흐림 칸 없는 재료로 덮어써도(서버 재료엔 엔진이 넣은 칸이 없다) 다시 짜지 않는다."""
    run, d, calls, _ = plan
    _edit(d, "재료.json", lambda M: M.update(blur={"a.mp4": [[0, 0, 10, 10, 0.0, 1.0]]}))
    run()
    _edit(d, "재료.json", lambda M: M.pop("blur"))
    run()
    assert calls["tl"] == 1


@pytest.mark.parametrize("name,fn", [
    ("재료.json", lambda M: M["cuts"]["N1"][0].update(ss=5)),
    ("대본.json", lambda S: S["lines"][0].update(tts="가나다라마바사아.")),
])
def test_cut_or_script_change_replans(plan, name, fn):
    """컷이나 대본이 바뀌면 전처럼 처음부터 짠다(반대쪽 — 재사용이 넓어지면 옛 컷으로 나간다)."""
    run, d, calls, _ = plan
    run()
    _edit(d, name, fn)
    run()
    assert calls["tl"] == 2


def test_material_file_change_replans(plan, tmp_path):
    """같은 이름으로 다시 받은 재료 파일(VMake 로 지운 원본 포함)은 다른 입력이다."""
    run, _, calls, _ = plan
    f = tmp_path / "b.mp4"
    f.write_bytes(b"1")
    run()
    run()
    assert calls["tl"] == 1
    f.write_bytes(b"22")
    run()
    assert calls["tl"] == 2


def test_style_change_replans(plan, monkeypatch):
    run, _, calls, _ = plan
    run()
    base = STY.load("t")
    monkeypatch.setattr(STY, "load", lambda name: {**base, "cps_target": 8.0})
    run()
    assert calls["tl"] == 2


def test_broken_saved_plan_replans(plan):
    """지난 계획 파일이 깨졌거나 옛 꼴(render_itssum 은 T 만 쓴다)이면 다시 짠다."""
    run, d, calls, _ = plan
    run()
    (d / "plan" / "계획_시간표.json").write_text("{}", encoding="utf-8")
    run()
    assert calls["tl"] == 2


def test_still_gate_reads_only_changed_cut(monkeypatch, tmp_path):
    """관문 ⑦ = 그 컷 근처에 흐림이 생긴 컷만 다시 읽는다. 멈춤 판정 결과는 캐시로 읽어도 그대로."""
    (tmp_path / "a.mp4").write_bytes(b"x")
    read = []

    def gray(c, src, st, M):
        read.append(c["ss"])
        return np.zeros((2, 2, 2), np.int16)
    monkeypatch.setattr(RB, "cut_gray", gray)
    monkeypatch.setattr(RB, "cut_crop", lambda c, s, win: [0, 0, 100, 100])
    from tools.calcopy.hybrid import quality_gate as QG
    monkeypatch.setattr(QG, "still_spans", lambda g: [(0.0, 1.5)])
    cut = lambda ss: {"src": "a.mp4", "ss": ss, "t0": 0.0, "t1": 1.0, "line": "L1", "kind": "tts"}      # noqa: E731
    T = {"cuts": [cut(1.0), cut(20.0)], "end": 2.0}
    st = {"frame": {"kind": "window", "window": [0, 0, 100, 100]}}
    M = {"cand_dir": str(tmp_path)}
    first = RB.cut_still_gate(T, M, st, R=tmp_path)
    assert len(first) == 2 and sorted(read) == [1.0, 20.0]
    read.clear()
    assert RB.cut_still_gate(T, M, st, R=tmp_path) == first and read == []
    M["blur"] = {"a.mp4": [[0, 0, 10, 10, 1.0, 2.0]]}
    assert RB.cut_still_gate(T, M, st, R=tmp_path) == first and read == [1.0]
    read.clear()
    assert RB.cut_still_gate(T, M, st) == first and sorted(read) == [1.0, 20.0]      # R 없는 쪽(preset_gates)은 옛 동작


def test_gate_autoblur_never_asks_flow_to_blur(monkeypatch, tmp_path):
    """계획·렌더 길(timeline_gates = autoblur)에서는 '이 칸을 그대로 넣거나' 글이 안 나온다 = flow._auto_blur 고리는 이 길에서 돌지 않는다.
    다시 계획의 진짜 입구는 흐림을 넣어도 남은 글자·흐림 면적·검수 답의 재료 고치기다(관제 304 조사)."""
    (tmp_path / "a.mp4").write_bytes(b"x")
    monkeypatch.setattr(RB, "cut_crop", lambda c, s, win: [0, 0, 100, 100])
    monkeypatch.setattr(RB, "cut_frames", lambda reqs, jobs=None: [None] * len(reqs))
    hit = {"box": [1, 2, 3, 4], "score": 1.0, "blur": 0.0}
    monkeypatch.setattr(RB, "cut_content_feats", lambda *a, **k: {"text": [[hit], [hit], [hit]], "face": []})
    monkeypatch.setattr(RB, "foreign_text", lambda f: True)
    T = {"cuts": [{"src": "a.mp4", "ss": 1.0, "t0": 0.0, "t1": 1.0, "line": "L1"}], "end": 1.0}
    st = {"frame": {"kind": "window", "window": [0, 0, 100, 100]}}
    M = {"cand_dir": str(tmp_path)}
    bad = RB.cut_content_gate(T, M, st, None, None, log=lambda *a: None, autoblur=True)
    assert bad and "흐림을 넣어도" in bad[0] and "이 칸을 그대로 넣거나" not in bad[0]
    flow_st = {"tries": {}, "log": [], "script": {"M": {}}}
    assert F._auto_blur(flow_st, " / ".join(bad)) == 0
    assert os.path.exists(tmp_path / "a.mp4")
