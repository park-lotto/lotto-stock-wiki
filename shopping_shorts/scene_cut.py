"""컷 경계 검출·프레임 절단 — DB도 HTTP도 Gemini도 모르는 순수 함수.

★초로 반올림하지 마라. 30fps 영상은 프레임이 1/30초 간격에만 존재하므로
반올림된 초(4.13)는 '프레임이 없는 시각'이 되고, ffmpeg가 다음 프레임에
붙이면서 다음 컷의 첫 프레임이 딸려 들어온다(설계 §3.4 실측 증명).
"""
import re
import subprocess
from pathlib import Path


def _ffprobe(args):
    r = subprocess.run(["ffprobe", "-v", "error"] + args,
                       capture_output=True, text=True, check=False)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"ffprobe 실패: {r.stderr.strip() or '출력 없음'}")
    return r.stdout.strip()


def video_fps(path):
    """r_frame_rate를 유리수로 정확히 읽는다(30/1 → 30.0)."""
    raw = _ffprobe(["-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                    "-of", "csv=p=0", str(path)])
    num, _, den = raw.partition("/")
    try:
        return int(num) / int(den or 1)
    except (ValueError, ZeroDivisionError) as e:
        raise RuntimeError(f"fps 해석 실패: {raw!r}") from e


def video_frame_count(path):
    """★비디오 스트림의 총 프레임 수. format=duration을 쓰면 안 된다 —
    그건 오디오와 비디오 중 긴 값이라 화면 없는 꼬리가 붙는다(설계 §3.5)."""
    raw = _ffprobe(["-select_streams", "v:0", "-count_frames",
                    "-show_entries", "stream=nb_read_frames",
                    "-of", "csv=p=0", str(path)])
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"프레임 수 해석 실패: {raw!r}") from e
