# -*- coding: utf-8 -*-
"""화면 컷 찾기가 빗나가면 스스로 지금 편성으로 다시 준비한다 — screen_clips.lookup 한 곳(관제 149, 2026-10-07).

라이브 실측(10-07 05:28~15:46): 음성을 다시 만든 작업(tts_ver·cap_durs 바뀜)에서 자막 고르기·비교 화면이 옛 준비(warm)로
컷을 찾다 4작업 30칸이 예비 계산으로 떨어졌다(경보 `no_screen_cut diff=cap_durs,…,tts_ver`). 컷을 찾는 경로가 30곳이 넘어
호출부마다 warm 을 챙기는 대신, 찾는 함수가 못 찾으면 DB 의 지금 편성으로 스스로 준비하고 다시 찾는다.
그리고 옛 청소본 비교는 지금 화면 컷이 아니라 그 파일을 만든 컷 지도(파일 옆 .cuts.json)로 편다.
"""
import json
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import screen_clips as sc
from shopping_shorts import video_assemble as va


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(sc, "FALLBACKS", [])
    for name in ("_CACHE", "_DATA_SEEN", "_RES_SEEN", "_WARMED", "_JOB_STATE", "_OWNER", "_HEALED"):
        monkeypatch.setattr(sc, name, {})
    monkeypatch.setattr(sc, "_SEEN", set())
    monkeypatch.setenv("SCREEN_CLIPS", "1")


class _Proc:
    def __init__(self, out):
        self.returncode = 0; self.stdout = out; self.stderr = ""


def _job(jid, tmp_path, ver):
    b = {"beat_idx": 0, "narration": "가 나 다", "tts_path": str(tmp_path / "b0.mp3"), "tts_ver": ver,
         "cap_durs": [1.0 * ver], "primary": {"video_id": "s0", "seg_id": "a", "start": 1.0, "end": 4.0}, "alternates": []}
    return {"job_id": jid, "edit_plan": {"beats": [b]}}


def _fake_screen(monkeypatch):
    monkeypatch.setattr(sc, "_scene_data", lambda jid: {"beats": [{"x": 1}]})
    res = [{"t": 2.0, "c": [{"v": "s0", "s": 1.0, "d": 2.0, "sd": 2.0, "fit": 0}]}]
    calls = []
    def _run(*a, **k):
        calls.append(1)
        return _Proc(json.dumps(res))
    monkeypatch.setattr(sc.subprocess, "run", _run)
    return calls


def test_lookup_heals_after_tts_resynth(tmp_path, monkeypatch):
    """warm 은 음성 바꾸기 전 편성으로 했고, 지금(DB) 편성으로 찾는다 — 예비 계산이 아니라 화면 컷."""
    calls = _fake_screen(monkeypatch)
    old = _job("jH", tmp_path, 1)
    assert sc.warm(old) == 1
    new = _job("jH", tmp_path, 2)                          # 음성 다시 만듦(tts_ver·cap_durs)
    monkeypatch.setattr(sc, "_fresh_job", lambda jid: new if jid == "jH" else None)
    got = va.plan_beat_clips_for(new["edit_plan"]["beats"][0], 2.0, {"s0": 30.0})
    assert got and all(c.get("screen") for c in got), got
    assert sc.fallbacks_for("jH") == []
    assert len(calls) == 1                                 # 같은 화면 데이터 — 러너 재실행 없이 키만 다시 단다


def test_stale_plan_still_alarms_and_heals_once(tmp_path, monkeypatch):
    """DB 에 없는 옛 편성 칸은 다시 준비해도 못 찾는다 — 그때는 종전대로 경보. 다시 준비는 작업당 한 번(칸마다 DB 안 읽는다)."""
    _fake_screen(monkeypatch)
    cur = _job("jS", tmp_path, 2)
    assert sc.warm(cur) == 1
    seen = []
    monkeypatch.setattr(sc, "_fresh_job", lambda jid: seen.append(jid) or cur)
    stale = _job("jS", tmp_path, 1)["edit_plan"]["beats"][0]
    for _ in range(3):
        va.plan_beat_clips_for(stale, 2.0, {"s0": 30.0})
    assert seen == ["jS"]
    assert [e["why"] for e in sc.fallbacks_for("jS")] == ["no_screen_cut diff=cap_durs,tts_ver"]


def test_clean_compare_uses_clean_file_cut_map(tmp_path, monkeypatch):
    """옛 청소본 비교는 그 파일을 만든 컷 지도(.cuts.json)로 — 지금 화면 컷으로 옛 편성을 다시 계산하지 않는다."""
    work = tmp_path / "w"; work.mkdir()
    sig = "abc123"
    f = work / ("final_clean_%s.mp4" % sig)
    f.write_bytes(b"0" * 2048)
    (work / ("final_clean_%s.plan.json" % sig)).write_text(json.dumps({"beats": [{"beat_idx": 0}], "_clean_sel": []}), encoding="utf-8")
    cuts = [{"video_id": "s0", "beat_idx": 0, "src": 1.25, "fin": 0.0, "dur": 2.0, "sdur": 2.0}]
    (work / ("final_clean_%s.cuts.json" % sig)).write_text(json.dumps({"rule": mp.CLEAN_SIDECAR_RULE, "cuts": cuts}), encoding="utf-8")
    monkeypatch.setattr(mp, "clean_final_path_for_plan", lambda job, w: None)
    monkeypatch.setattr(mp, "clean_base_for", lambda job, w: None)
    monkeypatch.setattr(mp, "final_clip_pairs", lambda *a, **k: pytest.fail("옛 편성을 지금 화면 컷으로 다시 계산했다"))
    monkeypatch.setattr(mp, "_src_durs_for", lambda job, w: {})
    r = mp.clean_compare_clips({"job_id": "jC", "edit_plan": {"beats": []}}, work)
    assert r["plan_used"] == "snapshot" and r["stale"] is True
    assert [(c["video_id"], c["src"], c["fin"], c["dur"]) for c in r["clips"]] == [("s0", 1.25, 0.0, 2.0)]
