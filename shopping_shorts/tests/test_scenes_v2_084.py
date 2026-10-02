# -*- coding: utf-8 -*-
"""관제 084 3단계 시간 배분(scene_play.js scenesV2) — 서버 러너(화면·미리보기·완성본·캡컷이 쓰는 그 계산)로 검사.
사장님 규칙: 컷 수=장면 수 · 고르게 · 짧은 장면은 가진 만큼(옆 장면이 더) · 모자라면 칸 전체 같은 배속 · 전환은 가까운 자막 경계."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
SCENE_PLAY = HERE / "static" / "scene_play.js"


def _data(segs, dur, caps=None, rule="scenes_v2", reel=60.0):
    ids = list(segs)
    d = {"beats": [{"beat_idx": 0, "narration": "가",
                    "primary": {"video_id": "s0", "seg_id": ids[0], "start": segs[ids[0]][0], "end": segs[ids[0]][1]},
                    "alternates": [{"video_id": "s0", "seg_id": k, "start": segs[k][0], "end": segs[k][1]} for k in ids[1:]]}],
         "segments": {k: {"video_id": "s0", "start": v[0], "end": v[1]} for k, v in segs.items()},
         "tts_dur": {"0": dur}, "src_duration": {"s0": reel}, "max_slowmo": 1.2,
         "captions": {"0": caps or [{"text": "가", "start": 0.0, "end": dur}]}}
    if rule:
        d["cut_rule"] = rule
    return d


def _run(data, tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(SCENE_PLAY), str(p)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)[0]["c"]


def test_한_장면_자막_세_줄이어도_컷_하나(tmp_path):
    caps = [{"text": "a", "start": 0, "end": 0.8}, {"text": "b", "start": 0.8, "end": 1.7}, {"text": "c", "start": 1.7, "end": 2.5}]
    c = _run(_data({"a": (10.0, 13.0)}, 2.5, caps), tmp_path)
    assert len(c) == 1 and abs(c[0]["d"] - 2.5) < 0.02


def test_옛_작업은_종전대로_자막_줄마다_컷(tmp_path):
    caps = [{"text": "a", "start": 0, "end": 0.8}, {"text": "b", "start": 0.8, "end": 1.7}, {"text": "c", "start": 1.7, "end": 2.5}]
    c = _run(_data({"a": (10.0, 13.0)}, 2.5, caps, rule=None), tmp_path)
    assert len(c) == 3                                    # 표식 없는 작업은 그대로(청소본 시간축 보호)


def test_두_장면_고르게_나눈다(tmp_path):
    c = _run(_data({"a": (10.0, 13.0), "b": (20.0, 23.0)}, 2.5), tmp_path)
    assert [x["seg"] if "seg" in x else None for x in c] and len(c) == 2
    assert abs(c[0]["d"] - 1.25) < 0.02 and abs(c[1]["d"] - 1.25) < 0.02


def test_짧은_장면은_가진_만큼_옆_장면이_더(tmp_path):
    c = _run(_data({"a": (10.0, 13.0), "b": (20.0, 20.8)}, 3.0), tmp_path)
    assert len(c) == 2
    assert abs(c[1]["d"] - 0.8) < 0.02 and abs(c[0]["d"] - 2.2) < 0.02     # 0.8초 장면은 0.8초만, 나머지는 a
    assert all(abs(x.get("sd", x["d"]) - x["d"]) < 0.02 for x in c)         # 속도 그대로


def test_다_합쳐도_모자라면_칸_전체_같은_배속(tmp_path):
    c = _run(_data({"a": (10.0, 11.0), "b": (20.0, 21.0)}, 2.3), tmp_path)
    ra = c[0]["d"] / c[0]["sd"]; rb = c[1]["d"] / c[1]["sd"]
    assert abs(ra - rb) < 0.02 and ra <= 1.2 + 1e-3 and abs(c[0]["d"] + c[1]["d"] - 2.3) < 0.03


def test_전환은_가까운_자막_경계로(tmp_path):
    caps = [{"text": "a", "start": 0, "end": 0.8}, {"text": "b", "start": 0.8, "end": 1.5}, {"text": "c", "start": 1.5, "end": 2.5}]
    c = _run(_data({"a": (10.0, 13.0), "b": (20.0, 23.0)}, 2.5, caps), tmp_path)
    assert len(c) == 2 and abs(c[0]["d"] - 1.5) < 0.02                     # 1.25 → 0.25초 옆 경계 1.5


def test_원본에서_이어지는_장면은_느리게_말고_진짜_화면으로(tmp_path):
    d = _data({"a": (10.0, 11.0), "b": (20.0, 21.0)}, 3.0)
    d["scenecuts"] = {"s0": [9.0, 13.0, 19.0, 21.0]}          # a 는 13초까지 같은 장면, b 는 21초에서 장면 전환
    c = _run(d, tmp_path)
    assert len(c) == 2 and abs(c[0]["d"] - 1.5) < 0.02
    assert abs(c[0].get("sd", c[0]["d"]) - 1.5) < 0.02         # a: 원본을 이어 읽어 속도 그대로
