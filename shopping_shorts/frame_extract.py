"""영상 다운로드 + ffmpeg 장면전환 기반 프레임 추출. 순수 함수."""
import subprocess
import uuid
from pathlib import Path
import requests


def download_video(video_url, dest_dir):
    """video_url → dest_dir에 mp4로 다운로드, 저장된 경로 반환."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{uuid.uuid4().hex}.mp4"
    resp = requests.get(video_url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    return path


def extract_frames(video_path, dest_dir, max_frames=6):
    """video_path에서 장면전환 감지로 대표 프레임을 최대 max_frames장 추출.

    감지된 장면전환이 max_frames보다 적으면 있는 만큼만 반환(빈 리스트일 수도 있음
    — 호출부가 처리). ffmpeg 실패 시 RuntimeError.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    pattern = dest_dir / "frame_%02d.jpg"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"select='gt(scene,0.3)',showinfo",
        "-vsync", "vfr", "-frames:v", str(max_frames),
        str(pattern),
    ]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 프레임 추출 실패: {result.stderr}")
    return sorted(dest_dir.glob("frame_*.jpg"))
