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
    result = subprocess.run(cmd, capture_output=True, check=False,
                            stdin=subprocess.DEVNULL)   # 위 extract_frame_at과 같은 이유
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 프레임 추출 실패: {result.stderr}")
    return sorted(dest_dir.glob("frame_*.jpg"))


def extract_frame_at(video_path, dest_dir, timestamp_sec, filename="frame_hint.jpg"):
    """timestamp_sec 위치의 프레임 1장만 추출.

    extract_frames()의 장면전환 감지는 제품이 잘 보이는지와 무관하게 화면이
    바뀌는 순간을 뽑아서, 얼굴·손·배경 같은 프레임이 섞여 Lens 역검색이
    헛도는 경우가 있었다(2026-07-13). Gemini가 영상 분석 중 함께 짚어준
    "제품이 가장 선명한 순간"(lens_hint_sec)으로 별도 프레임을 하나 더
    떠서 Lens 역검색 1순위로 쓴다. 실패해도 조용히 None — 기존 장면전환
    프레임만으로도 동작은 계속돼야 한다."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / filename
    cmd = [
        "ffmpeg", "-y", "-ss", str(max(0, timestamp_sec)), "-i", str(video_path),
        "-frames:v", "1", str(out_path),
    ]
    # stdin=DEVNULL — ffmpeg는 stdin을 붙잡는데, 물려줄 콘솔이 없는 자리(웹 요청
    # 처리 스레드)에서 부르면 윈도우가 OSError WinError 6(잘못된 핸들)로 죽는다.
    # 리눅스 서버에선 안 터져 여태 안 드러났다(scene_cut은 처음부터 붙여놨다).
    result = subprocess.run(cmd, capture_output=True, check=False,
                            stdin=subprocess.DEVNULL)
    if result.returncode != 0 or not out_path.exists():
        return None
    return out_path
