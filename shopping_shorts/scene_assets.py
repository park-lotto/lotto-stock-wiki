"""장면 라이브러리(재사용 짤 뱅크) — 구간컷·오디오추출·썸네일·Gemini 자동태깅.

순수 함수만 둔다(DB·HTTP 없음). frame_extract.py와 같은 골격:
ffmpeg는 subprocess로, 치명적 실패는 RuntimeError, 없어도 되는 것은 조용한 None.
"""
import json
import subprocess
from pathlib import Path

from . import frame_extract

# 페이즈2 concat이 -c copy(video_assemble.py:346)라 자산 클립도 비트 클립과
# **같은 규격**이어야 붙는다. video_assemble._OUT_W/_OUT_H와 같은 값.
_OUT_W, _OUT_H = 720, 1280
_SPEC_VF = (f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,"
            f"crop={_OUT_W}:{_OUT_H}")


def probe_duration(path):
    """미디어 길이(초). 실패하면 0.0 — 길이는 표시용이라 파이프라인을 끊지 않는다.

    ffprobe가 아예 없으면 subprocess.run은 returncode가 아니라 FileNotFoundError를
    던지므로 OSError도 삼킨다(ffprobe 없는 환경에서도 저장은 되어야 한다)."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, check=False)
    except OSError:
        return 0.0
    if r.returncode != 0:
        return 0.0
    try:
        return float((r.stdout or b"").decode().strip())
    except ValueError:
        return 0.0


def make_clip(src_path, start, end, out_path):
    """src_path의 [start,end] 구간을 잘라 규격(720x1280/30fps/libx264/aac)으로 통일.

    페이즈2에서 이 클립이 비트 클립들과 concat -c copy로 붙으므로 규격이
    어긋나면 렌더가 깨진다. 구간이 비었거나 뒤집혔으면 ValueError, ffmpeg
    실패면 RuntimeError."""
    dur = float(end) - float(start)
    if dur <= 0:
        raise ValueError(f"scene_assets: 구간이 잘못됨(start={start}, end={end})")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{float(start):.3f}", "-i", str(src_path),
        "-t", f"{dur:.3f}",
        "-vf", _SPEC_VF, "-r", "30",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 구간컷 실패: {r.stderr}")
    return out_path


def extract_audio(clip_path, out_path):
    """클립에서 오디오만 뽑아 mp3로(효과음 자산 소스). ffmpeg 실패면 RuntimeError."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(clip_path), "-vn",
           "-c:a", "libmp3lame", "-q:a", "2", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 오디오 추출 실패: {r.stderr}")
    return out_path


def make_poster(media_path, out_path):
    """첫 프레임 썸네일. 실패해도 None(썸네일은 없어도 목록이 뜬다).
    프레임 1장 추출은 frame_extract.extract_frame_at이 이미 하는 일이라 위임."""
    out_path = Path(out_path)
    return frame_extract.extract_frame_at(media_path, out_path.parent, 0,
                                          filename=out_path.name)
