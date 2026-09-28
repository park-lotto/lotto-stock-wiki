"""구절맞춤·꼬다리맞춤(scene_play.js planClips 의 finish = fitBeatCuts, 2026-09-28 사장님 "버튼 만들고 시뮬레이션까지 — 결정만 하게").

규칙: 컷이 읽는 원본은 같은 샷 · 고른 조각 · 청소 구간 안뿐(샷 넘김 0).
  구절맞춤(phrase, 기본): 컷 경계 = 구절 경계 고정, 모자란 컷만 느리게(≤1.15)→정지.
  꼬다리맞춤(tail): 합계 가용 ≥ 칸 길이면 여유 있는 컷이 모자란 몫을 나눠 가진다(경계 이동의 최댓값 최소) — 정지 0.
검사는 **서버 러너**(node screen_clips_runner.js scene_play.js data.json) — 화면·미리보기·완성본·캡컷이 쓰는 그 계산.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
SCENE_PLAY = HERE / "static" / "scene_play.js"
MAX_SLOWMO = 1.15


def _data(mode=None, *, segs=None, cuts=None, caps=((0, 1.5), (1.5, 3.0), (3.0, 4.5)), spans=None, reel=60.0):
    segs = segs or {"a": ("s0", 10.0, 12.0), "b": ("s1", 20.0, 22.0), "c": ("s2", 30.0, 30.6)}
    cuts = cuts if cuts is not None else {"s0": [9.0, 13.0], "s1": [19.0, 23.0], "s2": [30.0, 30.6]}
    ids = list(segs)
    tts = caps[-1][1]
    d = {"beats": [{"beat_idx": 0, "narration": "가나다",
                    "primary": {"video_id": segs[ids[0]][0], "seg_id": ids[0], "start": segs[ids[0]][1], "end": segs[ids[0]][2]},
                    "alternates": [{"video_id": segs[i][0], "seg_id": i, "start": segs[i][1], "end": segs[i][2]} for i in ids[1:]]}],
         "segments": {i: {"video_id": v, "start": a, "end": b} for i, (v, a, b) in segs.items()},
         "tts_dur": {"0": tts}, "src_duration": {v: reel for v, _, _ in segs.values()},
         "captions": {"0": [{"text": "가", "start": a, "end": b} for a, b in caps]},
         "scenecuts": cuts}
    if mode:
        d["cut_fit"] = mode
    if spans is not None:
        d["clean_spans"] = spans
    return d


def _run(data, tmp_path, js=SCENE_PLAY):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(js), str(p)], capture_output=True, text=True, timeout=60, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout)[0]["c"]


def _end(c):
    return c["s"] + (c["sd"] if c["sd"] is not None else c["d"])


def _crosses(c, cuts):
    s, e = c["s"], _end(c)
    return [x for x in cuts.get(c["v"], []) if s + 1e-3 < x < e - 1e-3]


def _freezes(c):
    sd = c["sd"] if c["sd"] is not None else c["d"]
    return not c.get("fit") and sd * MAX_SLOWMO < c["d"] - 1e-3


def _bounds(cs):
    out, t = [], 0.0
    for c in cs[:-1]:
        t += c["d"]
        out.append(round(t, 3))
    return out


# ── 3조각(1·2 여유, 3 짧음) ─────────────────────────────────────────────────────────────
def test_phrase_mode_keeps_bounds_and_only_short_cut_freezes(tmp_path):
    d = _data("phrase")
    cs = _run(d, tmp_path)
    assert [c["v"] for c in cs] == ["s0", "s1", "s2"]
    assert _bounds(cs) == [1.5, 3.0]                                  # 구절 경계 그대로
    assert [_freezes(c) for c in cs] == [False, False, True]           # 3번만 느리게→정지
    assert all(not _crosses(c, d["scenecuts"]) for c in cs), cs        # 샷 넘김 0
    assert _end(cs[2]) <= 30.6 + 1e-3


def test_default_mode_is_phrase(tmp_path):
    assert _run(_data(None), tmp_path) == _run(_data("phrase"), tmp_path)


def test_tail_mode_no_freeze_and_minimal_shift(tmp_path):
    d = _data("tail")
    cs = _run(d, tmp_path)
    assert not any(_freezes(c) for c in cs), cs                       # 멈춤 0
    assert all(not _crosses(c, d["scenecuts"]) for c in cs), cs
    assert abs(sum(c["d"] for c in cs) - 4.5) < 0.01                  # 칸 길이 그대로
    b = _bounds(cs)
    assert abs(b[0] - 1.5) < 0.02, b                                  # 첫 경계는 안 움직인다(최대 이동 최소화 — 한 곳만 0.9)
    assert abs(b[1] - 3.9) < 0.02, b                                  # 3번이 가진 0.6초만큼만 앞당겨진다
    assert abs(cs[2]["d"] - 0.6) < 0.02 and abs(cs[2]["sd"] - 0.6) < 0.02


def test_fit_cut_lens_minimax():
    """순수 함수 — 원래 경계에서 가장 멀리 움직이는 폭이 최소인가(손 계산 대조)."""
    js = SCENE_PLAY.read_text(encoding="utf-8")
    m = re.search(r"function fitCutLens\(.*?\n}\n", js, re.S)
    assert m
    prog = ("const EPS=1e-3;" + m.group(0) + "console.log(JSON.stringify(["
            "fitCutLens([1.5,1.5,1.5],[3,3,0.6],[false,false,false],0.5),"
            "fitCutLens([1,1,1,1],[2,0.5,2,0.5],[false,false,false,false],0.3),"
            "fitCutLens([1,1],[0.5,0.5],[false,false],0.3),"
            "fitCutLens([1,2],[5,0.5],[false,true],0.3)]))")
    r = subprocess.run(["node", "-e", prog], capture_output=True, text=True, timeout=30)
    a, b, c, e = json.loads(r.stdout)
    assert [round(x, 3) for x in a["x"]] == [1.5, 2.4, 0.6] and abs(a["shift"] - 0.9) < 1e-6
    assert abs(sum(b["x"]) - 4) < 1e-6 and all(x <= cap + 1e-6 for x, cap in zip(b["x"], [2, 0.5, 2, 0.5]))
    assert abs(b["shift"] - 0.5) < 1e-6                               # 1·3번이 0.5씩 받으면 경계 최대 이동 0.5
    assert [round(x, 3) for x in c["x"]] == [1.0, 1.0]                # 합계 부족(둘 다 모자람) = 같은 배율 → 길이 그대로
    assert [round(x, 3) for x in e["x"]] == [1.0, 2.0]                # 고정 묶음은 안 움직인다


# ── 합계 부족: 두 모드 모두 남는 몫만 정지 ────────────────────────────────────────────────
@pytest.mark.parametrize("mode", ["phrase", "tail"])
def test_short_total_only_residual_freezes(tmp_path, mode):
    segs = {"a": ("s0", 10.0, 10.8), "b": ("s1", 20.0, 20.8), "c": ("s2", 30.0, 30.6)}
    cuts = {"s0": [10.0, 10.8], "s1": [20.0, 20.8], "s2": [30.0, 30.6]}
    d = _data(mode, segs=segs, cuts=cuts)
    cs = _run(d, tmp_path)
    assert all(not _crosses(c, cuts) for c in cs), cs
    assert all(_end(c) <= {"s0": 10.8, "s1": 20.8, "s2": 30.6}[c["v"]] + 1e-3 for c in cs), cs
    assert abs(sum(c["d"] for c in cs) - 4.5) < 0.01
    read = sum(c["sd"] if c["sd"] is not None else c["d"] for c in cs)
    assert read <= 2.2 + 1e-3                                         # 쓸 수 있는 원본(0.8+0.8+0.6)을 넘지 않는다
    if mode == "tail":
        assert abs(read - 2.2) < 0.01                                 # 꼬다리맞춤은 가용을 다 쓴다


# ── 청소 구간: 지운 구간 밖으로 늘리지 않는다(과금·원본 자막 방지) ───────────────────────────
@pytest.mark.parametrize("mode", ["phrase", "tail"])
def test_clean_spans_limit(tmp_path, mode):
    spans = {"s0": [[10.0, 12.3]], "s1": [[20.0, 22.0]], "s2": [[30.0, 30.6]]}
    d = _data(mode, spans=spans)
    cs = _run(d, tmp_path)
    for c in cs:
        a, b = spans[c["v"]][0]
        assert c["s"] >= a - 1e-3 and _end(c) <= b + 1e-3, (c, spans)


def test_film_piece_not_extended(tmp_path):
    segs = {"film_x": ("s0", 10.0, 10.6), "b": ("s1", 20.0, 22.0)}
    d = _data("tail", segs=segs, caps=((0, 1.5), (1.5, 3.0)))
    cs = _run(d, tmp_path)
    f = [c for c in cs if c["v"] == "s0"][0]
    assert f["s"] >= 10.0 - 1e-3 and _end(f) <= 10.6 + 1e-3, cs      # 사람이 정한 구간 그대로(꼬다리 부활 금지)


def test_unknown_scenecuts_not_extended(tmp_path):
    """전환 목록이 없는 소재는 샷 끝을 모른다 → 조각 끝까지만(샷 넘김이 없다고 보장 못 하면 안 늘린다)."""
    d = _data("phrase")
    d.pop("scenecuts")
    cs = _run(d, tmp_path)
    ends = {"s0": 12.0, "s1": 22.0, "s2": 30.6}
    assert all(_end(c) <= ends[c["v"]] + 1e-3 for c in cs), cs


# ── 모드 저장 · 화면 데이터 · 서버 러너 ────────────────────────────────────────────────────
def test_modes_differ_only_by_data_field(tmp_path):
    a, b = _run(_data("phrase"), tmp_path), _run(_data("tail"), tmp_path)
    assert a != b


def test_scene_lab_data_carries_cut_fit():
    src = (HERE / "app.py").read_text(encoding="utf-8")
    i = src.index("def api_mix_scene_lab_data(")
    body = src[i:src.index("\n@app.", i)]
    assert '"cut_fit": _cut_fit_of(plan)' in body


def test_cut_fit_of_default_and_values():
    from shopping_shorts import app as appmod
    assert appmod._cut_fit_of({}) == "phrase"
    assert appmod._cut_fit_of({"cut_fit": "tail"}) == "tail"
    assert appmod._cut_fit_of({"cut_fit": "weird"}) == "phrase"


def test_cut_fit_endpoint_saves_plan(monkeypatch):
    from shopping_shorts import app as appmod
    saved = {}

    class FakeStore:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, jid):
            return {"job_id": jid, "status": "ready_for_review", "edit_plan": {"beats": [{"beat_idx": 0}]}}

        def update_mix_job(self, jid, **kw):
            saved.update(kw)

    monkeypatch.setattr(appmod, "Store", FakeStore)
    r = appmod.api_mix_scene_lab_cut_fit("j1", {"mode": "tail"})
    assert r["ok"] and r["mode"] == "tail" and saved["edit_plan"]["cut_fit"] == "tail"
    bad = appmod.api_mix_scene_lab_cut_fit("j1", {"mode": "x"})
    assert getattr(bad, "status_code", 200) == 422


def test_scene_lab_has_two_mode_buttons():
    html = (HERE / "static" / "scene_lab.html").read_text(encoding="utf-8")
    assert 'id="cutFitPhrase"' in html and 'id="cutFitTail"' in html
    assert "setCutFit('phrase')" in html and "setCutFit('tail')" in html
