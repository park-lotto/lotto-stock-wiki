import subprocess
from pathlib import Path
import pytest
from shopping_shorts import video_assemble as va


def _mk_video(path, color, dur, size="720x1280"):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c={color}:s={size}:r=30:d={dur}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _mk_audio(path, dur):
    # NOTE: mp3 muxer만 "Exactly one MP3 audio stream is required"라며 aac를 거부하는
    # ffmpeg 빌드가 있어(이 환경에서 실측) libmp3lame으로 바꿈 — 순수 테스트 픽스처
    # 헬퍼일 뿐, 프로덕션 코드(video_assemble.py)와는 무관.
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=440:duration={dur}",
                    "-c:a", "libmp3lame", str(path)], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


def _frame_rgb(video, t):
    """t초 프레임의 평균 RGB(대략) — 색으로 오버레이 여부 판정."""
    import re
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video),
                          "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True,
                         stdin=subprocess.DEVNULL).stdout
    return tuple(out[:3]) if len(out) >= 3 else (0, 0, 0)


def _plan_one_beat(tts_dur):
    return {"structure": "t", "beats": [
        {"beat_idx": 0, "role": "본문", "narration": "x", "target_seconds": tts_dur,
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0.0, "end": tts_dur},
         "alternates": [], "effect": "cut", "fit": 0}]}


def test_cutaway_keeps_beat_length_and_overlays(tmp_path):
    src = tmp_path / "src.mp4"; _mk_video(src, "red", 4)         # primary=빨강
    asset = tmp_path / "asset.mp4"; _mk_video(asset, "green", 1.5)  # 자산=초록
    tts = tmp_path / "t0.mp3"; _mk_audio(tts, 2.5)
    work = tmp_path / "w"; work.mkdir()

    mix = va._render_mix(_plan_one_beat(2.5), {0: str(tts)}, {0: str(src)}, work,
                         cutaway_paths={0: str(asset)})

    # ① 비트 길이 불변 = TTS 길이(2.5초) — 자막 싱크 자물쇠
    dur = va._probe_duration(mix)
    assert abs(dur - 2.5) < 0.15
    # ② 창 안(t=0.5)은 자산(초록), 창 밖(t=2.0, 자산 1.5초 종료 후)은 원본(빨강)
    r_in = _frame_rgb(mix, 0.5); r_out = _frame_rgb(mix, 2.0)
    assert r_in[1] > r_in[0] and r_in[1] > r_in[2]      # 초록 우세
    assert r_out[0] > r_out[1] and r_out[0] > r_out[2]  # 빨강 우세


def test_no_cutaway_path_is_unchanged(tmp_path):
    src = tmp_path / "src.mp4"; _mk_video(src, "red", 4)
    tts = tmp_path / "t0.mp3"; _mk_audio(tts, 2.5)
    work = tmp_path / "w"; work.mkdir()
    mix = va._render_mix(_plan_one_beat(2.5), {0: str(tts)}, {0: str(src)}, work,
                         cutaway_paths=None)
    assert abs(va._probe_duration(mix) - 2.5) < 0.15
    assert _frame_rgb(mix, 0.5)[0] > _frame_rgb(mix, 0.5)[1]  # 전부 빨강(오버레이 없음)
