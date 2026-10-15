"""소스 원음 깔기 + 나레 덕킹(관제 097) — 결과물(소리 파일)의 구간별 RMS 로 검사한다.

주인 함수: video_assemble.source_audio_settings / source_audio_track / speech_spans / duck_source_audio /
          mix_narration_bed / source_audio_bed. 렌더(_render_mix·assemble)와 캡컷(capcut_draft)이 같은 함수를 부른다.
"""
import re
import subprocess

import pytest

from shopping_shorts import video_assemble as va

DUCK_DB = 12
VOL = 35


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


def _rms_db(path, t0, dur):
    """[t0, t0+dur] 구간 전체(채널 합) RMS dB — ffmpeg astats 로 잰다."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", str(path),
                        "-af", "astats=measure_perchannel=none:measure_overall=RMS_level", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    m = re.findall(r"RMS level dB:\s*(-?[\d.]+|-inf)", r.stderr)
    assert m, r.stderr[-800:]
    return float("-inf") if m[-1] == "-inf" else float(m[-1])


def _mk_narr(path, dur=6.0, a=2.0, b=4.0, ext_args=("-c:a", "pcm_s16le")):
    # 말소리 대용: a~b 초에만 440Hz, 나머지는 무음
    _ff("-f", "lavfi", "-i", f"aevalsrc='if(between(t,{a},{b}),0.5*sin(2*PI*440*t),0)':s=48000:d={dur}",
        *ext_args, str(path))


def _mk_noise(path, dur=6.0):
    _ff("-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.5:sample_rate=48000:duration={dur}",
        "-ac", "2", "-c:a", "pcm_s16le", str(path))


def test_settings_off_and_zero_values():
    assert va.source_audio_settings(None) is None
    assert va.source_audio_settings({}) is None
    assert va.source_audio_settings({"source_audio": {"keep": False, "volume": 50}}) is None
    assert va.source_audio_settings({"source_audio": {"keep": "false"}}) is None
    s = va.source_audio_settings({"source_audio": {"keep": True}})
    assert s == {"volume": VOL / 100.0, "duck_db": float(DUCK_DB)}
    # 0 은 유효값 — 기본값으로 튀지 않는다
    z = va.source_audio_settings({"source_audio": {"keep": True, "volume": 0, "duck_db": 0}})
    assert z == {"volume": 0.0, "duck_db": 0.0}


def test_speech_spans_finds_narration(tmp_path):
    narr = tmp_path / "n.wav"
    _mk_narr(narr)
    spans = va.speech_spans(narr)
    assert len(spans) == 1
    a, b = spans[0]
    assert abs(a - 2.0) < 0.05 and abs(b - 4.0) < 0.05


def test_duck_depth_matches_setting(tmp_path):
    narr, src = tmp_path / "n.wav", tmp_path / "s.wav"
    _mk_narr(narr)
    _mk_noise(src)
    out, spans = va.duck_source_audio(narr, src, {"volume": VOL / 100.0, "duck_db": DUCK_DB}, tmp_path / "d.wav")
    base_src = _rms_db(src, 0.3, 1.2)
    quiet = _rms_db(out, 2.3, 1.4)          # 나레 구간(경사 0.15초 밖)
    loud1 = _rms_db(out, 0.3, 1.2)          # 나레 전
    loud2 = _rms_db(out, 4.5, 1.2)          # 나레 뒤
    # 바탕 크기 = 원음 × 35% (≈ -9.1dB)
    assert abs((loud1 - base_src) - 20 * __import__("math").log10(VOL / 100.0)) < 1.0
    # 덕킹 깊이 = duck_db ± 2dB (앞뒤 양쪽)
    assert abs((loud1 - quiet) - DUCK_DB) <= 2.0, (loud1, quiet)
    assert abs((loud2 - quiet) - DUCK_DB) <= 2.0, (loud2, quiet)


def test_mix_keeps_narration_full_level(tmp_path):
    """normalize=0 — 나레가 입력 개수로 나뉘어 -6dB 되지 않는다(amix 기본값 함정)."""
    narr, src = tmp_path / "n.wav", tmp_path / "s.wav"
    _mk_narr(narr)
    _mk_noise(src)
    silent = tmp_path / "z.wav"
    _ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "6", "-c:a", "pcm_s16le", str(silent))
    bed = va.mix_narration_bed(narr, silent, tmp_path / "bed.wav")
    assert abs(_rms_db(bed, 2.3, 1.4) - _rms_db(narr, 2.3, 1.4)) < 0.5
    assert abs(va._probe_duration(bed) - va._probe_duration(narr)) < 0.01


def _mk_video_with_audio(path, dur):
    _ff("-f", "lavfi", "-i", f"color=c=red:s=720x1280:r=30:d={dur}",
        "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.5:sample_rate=48000:duration={dur}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-shortest", str(path))


def _plan_one_beat(tts_dur):
    return {"structure": "t", "beats": [
        {"beat_idx": 0, "role": "본문", "narration": "x", "target_seconds": tts_dur,
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0.0, "end": tts_dur},
         "alternates": [], "effect": "cut", "fit": 0}]}


@pytest.mark.parametrize("keep", [False, True])
def test_render_mix_source_bed(tmp_path, keep):
    """렌더 경로(_render_mix) — keep=false 면 종전대로 소리 = 나레만(나레 무음 구간 = 무음),
    keep=true 면 narration_bed.wav 에 원음이 깔리고 나레 구간에서 duck_db 만큼 낮다."""
    src = tmp_path / "src.mp4"
    _mk_video_with_audio(src, 6.5)
    tts = tmp_path / "t0.mp3"
    _mk_narr(tts, ext_args=("-c:a", "libmp3lame"))
    work = tmp_path / "w"
    work.mkdir()
    kw = {"source_audio": {"volume": VOL / 100.0, "duck_db": DUCK_DB}} if keep else {}
    mix = va._render_mix(_plan_one_beat(6.0), {0: str(tts)}, {0: str(src)}, work, **kw)
    narr = work / "narration.wav"
    bed = work / "narration_bed.wav"
    assert narr.exists()
    # 나레 무음 구간(0.3~1.5초) — 나레 한 줄은 늘 무음(원음을 버린다 = 종전)
    assert _rms_db(narr, 0.3, 1.2) < -80
    assert _rms_db(mix, 0.3, 1.2) < -80      # mix_raw(자막제거 입력)도 종전 그대로 나레만
    if not keep:
        assert not bed.exists()
        return
    assert bed.exists()
    # 표본 수 = 나레 한 줄과 같다(칸 프레임 자 유지)
    assert abs(va._probe_duration(bed) - va._probe_duration(narr)) < 0.005
    ducked = work / "source_audio_ducked.wav"
    loud, quiet = _rms_db(ducked, 0.3, 1.2), _rms_db(ducked, 2.4, 1.2)
    assert abs((loud - quiet) - DUCK_DB) <= 2.0, (loud, quiet)
    assert _rms_db(bed, 0.3, 1.2) > -40      # 나레 무음 구간에 원음이 들린다


def test_pvproxy_signature_only_changes_when_on():
    """편집 화면 합본 서명 — 원음 깔기가 꺼진 작업은 종전 서명 그대로(다시 굽지 않음), 켜면 달라진다."""
    from shopping_shorts import app
    beats = [{"beat_idx": 0, "tts_path": ""}]
    base = app._pvproxy_beat_meta(beats, {})
    assert app._pvproxy_beat_meta(beats, {}, deco={}) == base
    assert app._pvproxy_beat_meta(beats, {}, deco={"source_audio": {"keep": False}}) == base
    on = app._pvproxy_beat_meta(beats, {}, deco={"source_audio": {"keep": True}})
    assert on != base and on[-1][0] == "source_audio"
