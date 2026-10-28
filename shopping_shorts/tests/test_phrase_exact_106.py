# -*- coding: utf-8 -*-
"""관제 106 — 새 규칙 작업의 [구절 맞춤](beat.phrase_exact): 장면 전환을 자막 경계에 정확히, 컷 수는 장면 수 그대로.
[컷 리듬](표식 없음)은 관제 084 배분 그대로다. 서버 러너(화면·미리보기·완성본·캡컷이 쓰는 그 계산)로 검사."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shopping_shorts import edit_plan

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
SCENE_PLAY = HERE / "static" / "scene_play.js"


def _caps(bounds, dur):
    t = [0.0] + list(bounds) + [dur]
    return [{"text": "줄%d" % i, "start": t[i], "end": t[i + 1]} for i in range(len(t) - 1)]


def _data(segs, dur, bounds, exact, rule="scenes_v2"):
    ids = list(segs)
    ref = lambda k: {"video_id": "s0", "seg_id": k, "start": segs[k][0], "end": segs[k][1]}
    beat = {"beat_idx": 0, "narration": "가", "primary": ref(ids[0]), "alternates": [ref(k) for k in ids[1:]]}
    if exact:
        beat["phrase_exact"] = True
    d = {"beats": [beat], "segments": {k: {"video_id": "s0", "start": v[0], "end": v[1]} for k, v in segs.items()},
         "tts_dur": {"0": dur}, "src_duration": {"s0": 0}, "max_slowmo": 1.2, "captions": {"0": _caps(bounds, dur)}}
    if rule:
        d["cut_rule"] = rule
    return d


def _run(data, tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(SCENE_PLAY), str(p)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)[0]["c"]


def _trans(c):
    out, t = [], 0.0
    for x in c[:-1]:
        t += x["d"]
        out.append(t)
    return out


# 사장님 캡쳐(job 49e10cb2c30b 4번 칸): 자막 1.5/1.8/1.2초, 셋째 장면 재료 1.0초
SEGS = {"a": (9.067, 10.967), "b": (26.533, 28.65), "c": (45.74, 46.74)}
BOUNDS, DUR = (1.515, 3.308), 4.512


def test_컷_리듬은_084_그대로_재료_한계에서_전환(tmp_path):
    c = _run(_data(SEGS, DUR, BOUNDS, exact=False), tmp_path)
    assert len(c) == 3 and abs(c[2]["d"] - 1.0) < 0.02           # 1.2배 상한에 걸려 자막 경계(3.308)로 못 옮긴다
    assert abs(_trans(c)[1] - 3.308) > 0.15


def test_구절_맞춤은_전환이_자막_경계(tmp_path):
    c = _run(_data(SEGS, DUR, BOUNDS, exact=True), tmp_path)
    assert len(c) == 3
    assert all(abs(t - b) < 0.02 for t, b in zip(_trans(c), BOUNDS))
    assert c[2]["fit"] == 1 and abs(c[2]["sd"] - 1.0) < 0.02      # 재료 1.0초를 1.2초에 정확히 느리게(정지 없이)
    assert abs(sum(x["d"] for x in c) - DUR) < 0.03


def test_장면이_자막_줄보다_적으면_컷은_장면_수(tmp_path):
    segs = {"a": (10.0, 13.0), "b": (20.0, 23.0)}
    c = _run(_data(segs, 4.0, (0.9, 2.2, 3.1), exact=True), tmp_path)
    assert len(c) == 2 and abs(_trans(c)[0] - 2.2) < 0.02         # 고른 자리(2.0)에서 가장 가까운 경계


def test_장면이_자막_줄보다_많으면_남는_전환은_고르게(tmp_path):
    segs = {"a": (10.0, 13.0), "b": (20.0, 23.0), "c": (30.0, 33.0)}
    c = _run(_data(segs, 4.5, (1.4,), exact=True), tmp_path)
    t = _trans(c)
    assert len(c) == 3 and abs(t[0] - 1.4) < 0.02 and abs(sum(x["d"] for x in c) - 4.5) < 0.03
    assert abs(c[1]["d"] - c[2]["d"]) < 0.03


def test_짧은_자막_줄도_맞춘다_하한_0점3초(tmp_path):
    segs = {"a": (10.0, 13.0), "b": (20.0, 23.0)}
    c = _run(_data(segs, 2.112, (0.49,), exact=True), tmp_path)   # 실측 8380a0fdb4a3 2번 칸
    assert abs(c[0]["d"] - 0.49) < 0.02


def test_옛_규칙_작업은_표식이_있어도_그대로(tmp_path):
    a = _run(_data(SEGS, DUR, BOUNDS, exact=True, rule=None), tmp_path)
    b = _run(_data(SEGS, DUR, BOUNDS, exact=False, rule=None), tmp_path)
    assert a == b


def test_저장은_켠_칸만_표식을_남긴다():
    seg_map = {k: {"video_id": "s0", "start": v[0], "end": v[1]} for k, v in SEGS.items()}
    plan = {"beats": [{"beat_idx": 0, "narration": "가", "primary": {"video_id": "s0", "seg_id": "a", "start": 9.067, "end": 10.967}}]}
    edit_plan.apply_scene_lab(plan, seg_map, {"beats": [{"beat_idx": 0, "list": ["a", "b"], "phrase": True, "exact": True}]})
    assert plan["beats"][0].get("phrase_exact") is True
    edit_plan.apply_scene_lab(plan, seg_map, {"beats": [{"beat_idx": 0, "list": ["a", "b"], "phrase": True, "exact": False}]})
    assert "phrase_exact" not in plan["beats"][0]
