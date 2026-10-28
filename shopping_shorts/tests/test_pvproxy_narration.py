"""편집 화면 미리보기 합본(app._pvproxy_build)의 소리 = 완성본과 **같은 함수**(video_assemble.narration_track) — 실제로 구워 잰다.

왜 (2026-09-27): 미리보기는 칸마다 음성을 `-af apad -t … -c:a aac` 로 따로 굽고 concat 했다. 완성본이 같은 방식에서
  칸당 20~40ms 채움 표본이 쌓여 목소리가 그림보다 늦었던 결함(소리 에이전트 서버 실측)이 미리보기에도 그대로 있었다.
  그리고 미리보기는 head_trim/tail_trim 을 몰라 다듬은 칸이 완성본보다 길었다.
검사: 칸마다 색이 다른 소스 + 칸마다 다른 사인 스윕 10칸을 실제 _pvproxy_build 로 굽고
  패킷 잉여 < 0.03초 · 칸마다 목소리 시작 = 영상 칸 첫 프레임 ±0.02초 · narration_track 을 실제로 부르는지(스파이).
  head_trim 칸: 다듬은 목소리가 칸 첫 프레임에서 시작하고 칸 길이가 완성본 식(_effective_dur)과 같다.
사보타주: 종전 칸별 AAC 방식으로 되돌리면 잉여·칸별 오차가 빨강.
"""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from shopping_shorts import video_assemble as va

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg 없음")

_P = Path(__file__).resolve().parent / "test_narration_track.py"
_sp = importlib.util.spec_from_file_location("_narr_helpers", str(_P))
H = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(H)
mats = H.mats          # 같은 합성 재료(10칸 색 소스 + 스윕 mp3)


def _build(mats, monkeypatch, tmp_path, beats=None):
    from shopping_shorts import app

    class _Store:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, *_a, **_k):
            return {"edit_plan": {"beats": beats}} if beats else None

    calls = []
    real = va.narration_track

    def spy(*a, **k):
        calls.append(a)
        return real(*a, **k)

    monkeypatch.setattr(app, "Store", _Store)
    monkeypatch.setattr(va, "narration_track", spy)
    pv = tmp_path / "pv"
    monkeypatch.setattr(app, "_pvproxy_dir", lambda _j: pv)
    cuts, trims = [], {}
    for i, du in enumerate(H.DURS):
        b = (beats or [{}] * len(H.DURS))[i]
        eff = va._effective_dur(va._probe_duration(mats["tts"][i]), b.get("head_trim", 0.0), b.get("tail_trim", 0.0))
        cuts.append({"video_id": "V%d" % i, "start": 0.2, "dur": round(eff, 3), "src_dur": round(eff, 3)})
    app._pvproxy_build("narrjob", "signarr", cuts, dict(mats["srcs"]), [1] * len(H.DURS), dict(mats["tts"]))
    out = pv / "signarr.mp4"
    assert out.exists(), "합본 굽기 실패"
    return out, calls, json.loads((pv / "signarr.json").read_text(encoding="utf-8"))


def test_preview_narration_sample_exact(mats, monkeypatch, tmp_path):
    out, calls, meta = _build(mats, monkeypatch, tmp_path)
    assert len(calls) == 1, "미리보기가 완성본과 같은 narration_track 을 안 부른다(0순위-B)"
    sur = H._packet_surplus(out)
    errs, sig = H._starts_err(out, mats)
    print("\n[미리보기] 패킷 잉여 %+.3fs · 칸별 목소리-영상칸 %s" % (sur, [round(e, 3) for e in errs]))
    assert sur < 0.03, sur
    assert max(abs(e) for e in errs) <= 0.02, errs
    # 칸 시작(서버가 화면에 주는 offs) = 완성본 칸 첫 프레임
    f0s, tot = H._frame_starts(mats)
    assert [round(o * 30) for o in meta["offs"]] == f0s, (meta["offs"], f0s)
    assert abs(len(sig) / 16000 - tot / 30) < 0.03


def test_preview_head_trim_same_as_final(mats, monkeypatch, tmp_path):
    beats = [{"beat_idx": i} for i in range(len(H.DURS))]
    beats[3]["head_trim"] = 0.25
    beats[3]["tail_trim"] = 0.2
    out, calls, meta = _build(mats, monkeypatch, tmp_path, beats)
    # 칸 길이 = 완성본 식(_beat_effective_dur) 누적
    cum, f0s = 0.0, []
    for i in range(len(H.DURS)):
        f0s.append(int(round(cum * 30)))
        cum += va._beat_effective_dur(beats[i], mats["tts"][i])
    assert [round(o * 30) for o in meta["offs"]] == f0s, (meta["offs"], f0s)
    sig = H._decode(out)
    t = H._decode(mats["tts"][3])[int(0.25 * 16000):int(1.2 * 16000)]
    off, v = H._ncc_at(sig, t, int(round(f0s[3] / 30 * 16000)), int(0.4 * 16000))
    assert v > 0.5 and abs(off / 16000) <= 0.02, ("칸3 다듬은 목소리 자리", off / 16000, v)
