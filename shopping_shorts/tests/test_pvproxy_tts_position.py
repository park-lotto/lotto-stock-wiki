# -*- coding: utf-8 -*-
"""편집 화면 합본(_pvproxy_build)에 넘기는 칸 음성은 **칸 순서**로 키잉한다(2026-09-27).

왜: _pvproxy_build 는 beat_lens 순서(enumerate)로 tts.get(칸 순서)를 찾는데, 화면 요청(api_mix_preview_proxy)·
  미리굽기(_pvproxy_prewarm)는 beat_idx 로 키잉했다. 서버 실측(읽기 전용) 2,956 job 중 16 job 이 beat_idx ≠ 순서
  (번호 빠짐 [0,1,2,4,…] 11 · 겹침 [0,…,7,7] 5) — 빠진 편성은 뒤 칸마다 옆 칸 음성, 겹친 편성은 한 칸 음성이 사라졌다.
"""
import threading

from shopping_shorts import app as A

BEAT_IDX = [0, 1, 3, 3]          # 번호 빠짐(2) + 겹침(3,3)


def _job(tmp_path):
    beats = []
    for k, bi in enumerate(BEAT_IDX):
        tp = tmp_path / ("tts_%d.wav" % k)
        tp.write_bytes(b"x" * (100 + k))
        beats.append({"beat_idx": bi, "tts_path": str(tp),
                      "primary": {"video_id": "v", "seg_id": "v-0", "start": 0.0, "end": 5.0}})
    return {"job_id": "j1", "edit_plan": {"beats": beats}}, [b["tts_path"] for b in beats]


def test_request_route_keys_tts_by_position(tmp_path, monkeypatch):
    job, paths = _job(tmp_path)

    class _S:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, j): return job
    monkeypatch.setattr(A, "Store", _S)
    monkeypatch.setattr(A, "_pvproxy_dir", lambda j: tmp_path / "pv")
    monkeypatch.setattr(A, "_resolve_sources", lambda j, w: {})
    got = {}

    class _T:
        def __init__(self, target=None, args=(), daemon=None):
            got["args"] = args
        def start(self): pass
    monkeypatch.setattr(A.threading, "Thread", _T)
    A._PVPROXY_BUSY.pop("j1", None)
    try:
        cuts = [{"video_id": "v", "start": 0.0, "dur": 1.0} for _ in BEAT_IDX]
        out = A.api_mix_preview_proxy("j1", {"cuts": cuts, "beat_lens": [1, 1, 1, 1]})
    finally:
        A._PVPROXY_BUSY.pop("j1", None)
    assert out["ok"] and "args" in got, out
    tts = got["args"][5]
    assert tts == {k: p for k, p in enumerate(paths)}, tts


def test_prewarm_keys_tts_by_position(tmp_path, monkeypatch):
    job, paths = _job(tmp_path)
    src = tmp_path / "v.mp4"; src.write_bytes(b"v" * 64)
    for p, d in [(str(src), 5.0)] + [(p, 1.0) for p in paths]:     # 길이 메모 — ffprobe 없이 잰다
        (tmp_path / (A.Path(p).name + ".len")).write_text("%.6f,%d" % (d, A.Path(p).stat().st_size))

    class _S:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, j): return job
    monkeypatch.setattr(A, "Store", _S)
    monkeypatch.setattr(A, "_pvproxy_dir", lambda j: tmp_path / "pv")
    monkeypatch.setattr(A, "_resolve_sources", lambda j, w: {"v": str(src)})
    from shopping_shorts import video_assemble as va
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda b, td, sd, **k: [
        {"video_id": "v", "start": 0.0, "out_dur": td, "src_dur": td}])
    got = {}
    monkeypatch.setattr(A, "_pvproxy_build", lambda *a: got.setdefault("args", a))
    A._PVPROXY_BUSY.pop("j1", None)
    try:
        A._pvproxy_prewarm("j1")
    finally:
        A._PVPROXY_BUSY.pop("j1", None)
    assert "args" in got
    assert got["args"][5] == {k: p for k, p in enumerate(paths)}, got["args"][5]
