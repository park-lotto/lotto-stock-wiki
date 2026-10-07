"""장면 시간 배분(scenesV2) 이어 틀기는 원본의 다음 장면 전환 앞까지(관제 150, 2026-10-07).

사고: 짧은 장면을 1.2초로 늘리거나 옆 장면이 더 보여 줄 때 '다른 칸 장면 앞까지'만 보고 원본 장면 전환을 안 봐서
엉뚱한 다음 장면이 끼었다(실측 새 규칙 114작업 중 169컷 → 수리 뒤 78컷, 남은 건 멈춤 대신 겹쳐 틀기 단계).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
HERE = Path(__file__).resolve().parents[1]


def _run(d, tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "screen_clips_runner.js"), str(HERE / "static" / "scene_play.js"), str(p)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-400:]
    return json.loads(r.stdout)[0]["c"]


def _data(cuts_s0, stop=1):
    return {"cut_rule": "scenes_v2", "scene_stop": stop,
            "beats": [{"beat_idx": 0, "narration": "가",
                       "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 0.6},
                       "alternates": [{"video_id": "s1", "seg_id": "b", "start": 10.0, "end": 20.0}]}],
            "segments": {"a": {"video_id": "s0", "start": 0.0, "end": 0.6}, "b": {"video_id": "s1", "start": 10.0, "end": 20.0}},
            "tts_dur": {"0": 4.0}, "src_duration": {"s0": 30.0, "s1": 30.0},
            "captions": {"0": [{"text": "가", "start": 0.0, "end": 4.0}]},
            "scenecuts": {"s0": cuts_s0, "s1": [5.0, 25.0]}}


def test_short_scene_not_stretched_into_next_scene(tmp_path):
    """0.6초 장면 바로 뒤(0.6초)에 장면 전환 — 1.2초로 늘리지 않고 남는 시간은 옆 장면(s1)이 맡는다."""
    c = _run(_data([0.6, 8.0]), tmp_path)
    s0 = [x for x in c if x["v"] == "s0"]
    assert s0, c
    for x in s0:
        assert x["s"] + (x["sd"] if x["sd"] is not None else x["d"]) <= 0.6 + 1e-3, ("다음 장면을 읽었다", x)
    assert abs(sum(x["d"] for x in c) - 4.0) < 0.02, c


def test_no_scene_change_keeps_old_stretch(tmp_path):
    """장면이 원본에서 그대로 이어지면(전환이 멀다) 종전처럼 1.2초까지 진짜 화면으로 보여 준다."""
    c = _run(_data([8.0]), tmp_path)
    s0 = [x for x in c if x["v"] == "s0"]
    assert s0 and max(x["s"] + (x["sd"] if x["sd"] is not None else x["d"]) for x in s0) > 0.6 + 0.3, c


def test_old_job_without_marker_unchanged(tmp_path):
    """표식(scene_stop) 없는 옛 작업은 종전 그대로 — 이미 청소한 작업은 청소 당시 컷과 같아야 재생된다(관제 110·135)."""
    c = _run(_data([0.6, 8.0], stop=0), tmp_path)
    s0 = [x for x in c if x["v"] == "s0"]
    assert s0 and abs(s0[0]["d"] - 1.2) < 0.02, c


def test_new_plan_gets_marker():
    """새 계획에 표식이 박힌다 — 계획 만드는 곳(mix_pipeline cut_rule 옆)과 화면 데이터 입구(app)가 짝."""
    src = (HERE / "mix_pipeline.py").read_text(encoding="utf-8")
    assert 'plan["scene_stop"] = _SCENE_STOP' in src
    assert '"scene_stop": 1 if plan.get("scene_stop") else 0' in (HERE / "app.py").read_text(encoding="utf-8")
