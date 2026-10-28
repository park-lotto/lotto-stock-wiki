"""편집 화면 합본의 배속 컷 = 완성본과 같은 판단(screen_clips.plays_at_speed 한 곳) — 실제로 구워 프레임을 대조한다(2026-09-27).

왜 (서버 실측 68b48b12c7f5 칸5 컷1, 칸 통합 속도 1.4배): 화면 컷은 읽는 길이 1.358초·화면 길이 0.97초. 완성본(lookup → playback_speed)은
  원본 1.358초를 0.97초에 1.4배로 틀었는데, 합본(_cut_motion)은 [속도 맞추기]만 배속으로 보고 읽는 길이를 0.97초로 잘라 1배속으로 틀었다
  → 컷 끝 장면(원본 9.333초 뒤 손 장면)이 합본엔 3프레임, 완성본엔 10프레임 — 도구가 '화면에만 잔상 3'으로 잡았다.
검사: 프레임 번호 = 밝기인 합성 원본을 ① 읽는 길이 > 화면 길이(배속) ② 칸 통합 속도 0.8(읽는 길이 < 화면 길이, 느리게 끝까지)로
  합본·완성본 둘 다 굽고 프레임 순서가 같은지 본다. 사보타주(합본을 종전 판단으로) → 빨강.
"""
import importlib.util
import shutil
from pathlib import Path

import pytest

from shopping_shorts import screen_clips as sc
from shopping_shorts import video_assemble as va

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg 없음")

_P = Path(__file__).resolve().parent / "test_first_frame_no_dup.py"
_sp = importlib.util.spec_from_file_location("_ffnd", str(_P))
H = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(H)


def _editor(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start, sync=None):
    from shopping_shorts import app

    class _Store:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, *_a, **_k):
            return {"edit_plan": {"beats": [{"beat_idx": 0, **({"sync_speed": sync} if sync else {})}]}}

    pv = tmp_path / "pv"
    monkeypatch.setattr(app, "Store", _Store)
    monkeypatch.setattr(app, "_pvproxy_dir", lambda _j: pv)
    app._pvproxy_build("spdjob", "sigspd", [{"video_id": "V", "start": start, "dur": out_dur, "src_dur": src_dur}],
                       {"V": src}, [1], {0: tts})
    out = pv / "sigspd.mp4"
    assert out.exists()
    return out


def _final(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start, sync=None):
    # 완성본은 화면 컷을 lookup 이 바꾼 계획 그대로 — 배속 판단도 lookup(plays_at_speed)이 붙인 playback_speed
    p = {"video_id": "V", "seg_id": "V-0", "start": start, "src_dur": src_dur, "out_dur": out_dur}
    if sc.plays_at_speed(False, sync or 1.0, src_dur, out_dur):
        p["playback_speed"] = src_dur / out_dur
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda *a, **k: [dict(p)])
    monkeypatch.setattr(va, "_trans_sec", lambda: 0.0)
    beat = {"beat_idx": 0, "narration": "테스트", "primary": {"video_id": "V", "seg_id": "V-0", "start": 0.0, "end": 3.0}}
    work = tmp_path / "final"
    work.mkdir()
    return va._render_mix({"beats": [beat]}, {0: tts}, {"V": src}, work)


@pytest.mark.parametrize("src_dur,out_dur,sync", [(1.358, 0.97, 1.4), (1.3, 0.9, None), (0.8, 1.0, 0.8)],
                         ids=["sync1.4-long-read", "long-read-no-sync", "sync0.8-slow-to-end"])
def test_editor_speed_same_as_final(tmp_path, monkeypatch, src_dur, out_dur, sync):
    src = H._make_src(tmp_path, "30")
    tts = H._tts(tmp_path, out_dur)
    el = H._levels(_editor(tmp_path, monkeypatch, src, tts, out_dur, src_dur, 0.2, sync))
    fl = H._levels(_final(tmp_path, monkeypatch, src, tts, out_dur, src_dur, 0.2, sync))
    assert len(el) == len(fl), (len(el), len(fl))
    diff = [i for i, (a, b) in enumerate(zip(el, fl)) if abs(a - b) >= 1.5]
    assert not diff, f"합본 {el} vs 완성본 {fl} — 다른 프레임 {diff[:6]}"
    # 배속 컷은 읽는 길이 끝까지 움직인다(원본 마지막 프레임 번호 ≈ (start+src_dur)*30 - 1)
    assert max(el) >= (0.2 + src_dur) * 30 - 3, (max(el), el)


def test_plays_at_speed_rule():
    assert sc.plays_at_speed(True, 1.0, 0.5, 1.0)
    assert sc.plays_at_speed(False, 1.4, 1.0, 1.0)
    assert sc.plays_at_speed(False, 1.0, 1.3, 1.0)
    assert not sc.plays_at_speed(False, 1.0, 0.8, 1.0)          # 모자람 = 느리게(1.15배 상한)+정지
