"""효과음(sfx) 렌더 믹스 테스트 (스펙 §4·§8).

- 실 ffmpeg: sfx 오버레이 후 최종 길이 불변(싱크 자물쇠) + 오디오 스트림 생존.
- 커맨드 검사: BGM+sfx → amix inputs=3 / sfx만 → filter_complex 경로 / 회귀(sfx없음) 그대로.
"""
import subprocess
from pathlib import Path

from shopping_shorts import video_assemble as va


def _mk_video(path, color, dur, size="720x1280"):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c={color}:s={size}:r=30:d={dur}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _mk_audio(path, dur, freq=440):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"sine=frequency={freq}:duration={dur}",
                    "-c:a", "libmp3lame", str(path)], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


def _has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    return "audio" in out


def _mean_volume_db(path):
    """volumedetect의 mean_volume(dB). 무음이면 -91dB 근처(거의 -inf)."""
    import re
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path),
                          "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", err)
    return float(m.group(1)) if m else None


def _plan_one_beat(role, tts_dur, sfx=None):
    beat = {"beat_idx": 0, "role": role, "narration": "여기 효과음 자리", "target_seconds": tts_dur,
            "primary": {"video_id": 0, "seg_id": "s0", "start": 0.0, "end": tts_dur},
            "alternates": [], "effect": "cut", "fit": 0}
    if sfx:
        beat["sfx"] = sfx
    return {"structure": "t", "beats": [beat]}


# ── 실 ffmpeg: 길이 불변 + 오디오 생존 ──────────────────────────

def test_sfx_render_preserves_length_and_keeps_audio(tmp_path):
    src = tmp_path / "src.mp4"; _mk_video(src, "red", 4)
    tts = tmp_path / "t0.mp3"; _mk_audio(tts, 2.5, freq=300)
    sfx = tmp_path / "sfx.mp3"; _mk_audio(sfx, 0.5, freq=1200)
    work = tmp_path / "w"; work.mkdir()

    plan = _plan_one_beat("hook", 2.5,
                          sfx={"asset_id": 1, "match_type": "role", "position": "first"})
    mix = va._render_mix(plan, {0: str(tts)}, {0: str(src)}, work, cutaway_paths=None)
    before = va._probe_duration(mix)

    out = tmp_path / "out.mp4"
    va._burn_captions(mix, plan, {0: str(tts)}, str(out), work, deco={},
                      sfx_paths={0: str(sfx)})

    # ① 최종 길이가 sfx 삽입 뒤에도 불변(duration=first가 나레이션 길이로 고정)
    assert abs(va._probe_duration(str(out)) - before) < 0.15
    # ② 오디오 스트림 생존 + 무음 아님(나레이션+효과음이 실제로 섞임)
    assert _has_audio(str(out))
    mv = _mean_volume_db(str(out))
    assert mv is not None and mv > -50.0


# ── 커맨드 검사: amix 입력 개수 ─────────────────────────────────

def _capture_burn(monkeypatch, tmp_path, plan, tts, deco, sfx_paths=None):
    captured = {}

    def fake_run(cmd, cwd=None):
        captured["cmd"] = cmd
        return 0
    monkeypatch.setattr(va, "_run_ffmpeg", fake_run)
    out = tmp_path / "out.mp4"
    work = tmp_path / "w"; work.mkdir(exist_ok=True)
    va._burn_captions("in.mp4", plan, {0: str(tts)}, str(out), work, deco=deco,
                      sfx_paths=sfx_paths)
    return " ".join(str(c) for c in captured.get("cmd", []))


def test_bgm_plus_sfx_amix_inputs_three(monkeypatch, tmp_path):
    tts = tmp_path / "t0.mp3"; _mk_audio(tts, 2.0)
    bgm = tmp_path / "bgm.mp3"; _mk_audio(bgm, 2.0)
    plan = _plan_one_beat("cta", 2.0,
                          sfx={"asset_id": 1, "match_type": "role", "position": "last"})
    deco = {"bgm": {"_abspath": str(bgm), "volume": 15}, "sfx_volume": 60}
    cmd = _capture_burn(monkeypatch, tmp_path, plan, tts, deco, sfx_paths={0: "/x/1.mp3"})
    assert "amix=inputs=3" in cmd          # 나레이션 + bgm + sfx1
    assert "adelay=" in cmd                 # 효과음이 오프셋으로 지연
    assert "-c:a aac" in cmd                # 재믹스 → aac 인코드


def test_sfx_only_uses_filtercomplex(monkeypatch, tmp_path):
    tts = tmp_path / "t0.mp3"; _mk_audio(tts, 2.0)
    plan = _plan_one_beat("hook", 2.0,
                          sfx={"asset_id": 1, "match_type": "role", "position": "first"})
    cmd = _capture_burn(monkeypatch, tmp_path, plan, tts, {}, sfx_paths={0: "/x/1.mp3"})
    assert "-filter_complex" in cmd         # 단순복사 경로로 안 빠짐(has_sfx 분기)
    assert "amix=inputs=2" in cmd           # 나레이션 + sfx1
    assert "adelay=0:all=1" in cmd          # hook=first → 오프셋 0


def test_no_sfx_bgm_only_regression_amix_two(monkeypatch, tmp_path):
    tts = tmp_path / "t0.mp3"; _mk_audio(tts, 2.0)
    bgm = tmp_path / "bgm.mp3"; _mk_audio(bgm, 2.0)
    plan = _plan_one_beat("본문", 2.0)      # sfx 없음
    deco = {"bgm": {"_abspath": str(bgm), "volume": 15}}
    cmd = _capture_burn(monkeypatch, tmp_path, plan, tts, deco, sfx_paths=None)
    assert "amix=inputs=2" in cmd           # 기존과 동일: 나레이션 + bgm
    assert "adelay=" not in cmd and "[sfx" not in cmd   # 효과음 필터 미생성


def test_no_audio_extras_simple_copy(monkeypatch, tmp_path):
    tts = tmp_path / "t0.mp3"; _mk_audio(tts, 2.0)
    plan = _plan_one_beat("본문", 2.0)      # sfx·bgm·overlay·motion 전부 없음
    cmd = _capture_burn(monkeypatch, tmp_path, plan, tts, {}, sfx_paths=None)
    assert "-filter_complex" not in cmd     # 단순 -vf 복사 경로
    assert "-c:a copy" in cmd
