"""컷 읽는 창 가드(scene_play.js guardReadWindow) — 창 머리·꼬리 0.1초 안의 장면 전환을 빼는지, 서버 러너가 같은 결과를 내는지(2026-09-27).

왜: 편집 화면 미리보기 컷 가장자리에 딴 장면 1~3프레임(서버 6 job 23프레임 — 조각 끝이 원본 장면 전환을 1~3프레임 넘음).
  조각 좌표를 고치면(경계 붙이기) 30일 job 90%의 좌표가 바뀌고 창이 통째로 밀려 새 잔상이 생겼다 → 좌표는 두고 읽는 창만 줄인다.
  가드는 컷을 확정하는 planClips 의 finish 한 곳 — 서버(screen_clips_runner.js)가 같은 JS·같은 DATA 를 돌린다.
검사는 전부 **서버 러너**(node screen_clips_runner.js scene_play.js data.json)로 — 화면이 쓰는 그 함수를 그대로 돈다.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
SCENE_PLAY = HERE / "static" / "scene_play.js"
F = 1 / 30.0


def _data(seg_start, seg_end, cuts, dur=None):
    dur = dur if dur is not None else round(seg_end - seg_start, 3)
    d = {"beats": [{"beat_idx": 0, "narration": "가", "primary": {"video_id": "s0", "seg_id": "a", "start": seg_start, "end": seg_end},
                    "alternates": []}],
         "segments": {"a": {"video_id": "s0", "start": seg_start, "end": seg_end}},
         "tts_dur": {"0": dur}, "src_duration": {"s0": 60.0}, "captions": {}}
    if cuts is not None:
        d["scenecuts"] = {"s0": cuts}
    return d


def _run(data, tmp_path, js=SCENE_PLAY):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(js), str(p)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    c = json.loads(r.stdout)[0]["c"]
    assert len(c) == 1, c
    return c[0]


def test_no_scenecuts_unchanged(tmp_path):
    c = _run(_data(10.0, 11.5, None), tmp_path)
    assert c["s"] == 10.0 and abs(c["sd"] - 1.5) < 1e-6 and abs(c["d"] - 1.5) < 1e-6


@pytest.mark.parametrize("frames", [1, 2, 3])
def test_head_cut_moves_start_inside(tmp_path, frames):
    cut = round(10.0 + frames * F, 3)
    c = _run(_data(10.0, 11.5, [3.0, cut, 20.0]), tmp_path)
    assert abs(c["s"] - cut) < 1e-6, c                     # 앞 장면 프레임을 안 읽는다
    assert abs((c["s"] + c["sd"]) - 11.5) < 1.5e-3, c      # 끝은 그대로
    assert abs(c["d"] - 1.5) < 1e-6, c                     # 컷 길이(화면 시간)는 그대로 — 모자람은 느리게·정지


@pytest.mark.parametrize("frames", [1, 2, 3])
def test_tail_cut_shrinks_window(tmp_path, frames):
    cut = round(11.5 - frames * F, 3)
    c = _run(_data(10.0, 11.5, [cut]), tmp_path)
    assert c["s"] == 10.0
    assert c["s"] + c["sd"] <= cut + 1e-9, c               # 다음 장면 첫 프레임부터는 안 읽는다
    assert c["s"] + c["sd"] > cut - 1.5e-3, c
    assert abs(c["d"] - 1.5) < 1e-6


@pytest.mark.parametrize("cut", [round(10.0 + 4 * F, 3), round(11.5 - 4 * F, 3), round(10.0 + 5 * F, 3), 10.0, 11.5])
def test_beyond_three_frames_or_on_edge_untouched(tmp_path, cut):
    """4프레임(0.133초) 밖이거나 딱 창 끝(이미 경계)이면 그대로."""
    c = _run(_data(10.0, 11.5, [cut]), tmp_path)
    assert c["s"] == 10.0 and abs(c["sd"] - 1.5) < 1e-6, (cut, c)


def test_both_ends(tmp_path):
    c = _run(_data(10.0, 11.5, [10.067, 11.433]), tmp_path)
    assert abs(c["s"] - 10.067) < 1e-6 and c["s"] + c["sd"] <= 11.433 + 1e-9


def test_other_source_cuts_ignored(tmp_path):
    d = _data(10.0, 11.5, None)
    d["scenecuts"] = {"s9": [10.067]}
    c = _run(d, tmp_path)
    assert c["s"] == 10.0 and abs(c["sd"] - 1.5) < 1e-6


def test_guard_called_once_in_finish():
    """가드는 컷을 확정하는 finish 한 곳에서만(0순위-B) — 다른 자리에 또 적으면 두 번 줄어든다."""
    src = SCENE_PLAY.read_text(encoding="utf-8")
    body = "\n".join(ln.split("//")[0] for ln in src.splitlines())
    assert body.count("guardReadWindow(") == 2, "정의 1 + 호출 1(finish) 이어야 한다"
    i = src.index("function planClips(")
    f0 = src.index("const finish = base =>", i)
    fin = src[f0:src.index("const segments =", f0)]
    assert "guardReadWindow(" in fin


def test_server_screen_clips_same_window(monkeypatch):
    """서버 러너(screen_clips.warm → lookup → plan_beat_clips_for)도 같은 가드 창을 받는다 — 미리보기·완성본·캡컷이 쓰는 경로."""
    from shopping_shorts import screen_clips as sc
    from shopping_shorts import video_assemble as va
    for name in ("_CACHE", "_DATA_SEEN", "_JOB_STATE", "_OWNER"):
        monkeypatch.setattr(sc, name, {})
    monkeypatch.setattr(sc, "FALLBACKS", [])
    monkeypatch.setattr(sc, "_SEEN", set())
    monkeypatch.setenv("SCREEN_CLIPS", "1")
    d = _data(10.0, 11.5, [10.067, 11.433])
    monkeypatch.setattr(sc, "_scene_data", lambda jid: d)
    job = {"job_id": "g", "edit_plan": {"beats": d["beats"]}}
    assert sc.warm(job) == 1
    got = va.plan_beat_clips_for(d["beats"][0], 1.5, {"s0": 60.0})
    assert len(got) == 1, got
    c = got[0]
    assert abs(c["start"] - 10.067) < 1e-6 and c["start"] + c["src_dur"] <= 11.433 + 1e-9, c
    assert abs(c["out_dur"] - 1.5) < 1e-6
