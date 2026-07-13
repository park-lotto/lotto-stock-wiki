"""소스 URL을 플랫폼별로 다운로드 — instagram=Apify, youtube/tiktok=yt-dlp(무료)."""
import subprocess
import sys
import uuid
from pathlib import Path


def _download_instagram(url, dest_dir):
    """인스타 릴스 다운로드 → (mp4경로, caption). caption은 Apify 원본 dict의
    "caption" 필드(없으면 빈 문자열) — extract_script의 캡션 힌트로 흘러간다."""
    from shopping_shorts.apify_client import fetch_single_reel
    from shopping_shorts.frame_extract import download_video
    raw = fetch_single_reel(url)
    if not raw or not raw.get("videoUrl"):
        raise RuntimeError(f"인스타 영상 해석 실패: {url}")
    path = str(download_video(raw["videoUrl"], Path(dest_dir)))
    return path, raw.get("caption", "")


def _download_ytdlp(url, dest_dir):
    """유튜브/틱톡 다운로드 → (mp4경로, caption). yt-dlp 경로는 캡션 없음(빈 문자열)."""
    out = str(Path(dest_dir) / (uuid.uuid4().hex[:8] + ".%(ext)s"))
    r = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "-f", "mp4/bestvideo+bestaudio/best",
         "--no-playlist", "-o", out, url],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp 실패({url}): {r.stderr[-300:]}")
    files = sorted(Path(dest_dir).glob(Path(out).stem.split('.')[0] + "*"))
    if not files:
        raise RuntimeError(f"yt-dlp 산출물 없음: {url}")
    return str(files[0]), ""


def download_any(url, dest_dir):
    """소스 URL 다운로드 → (mp4경로, caption) 튜플. caption은 인스타에서만 채워짐."""
    u = (url or "").lower()
    if "instagram.com" in u:
        return _download_instagram(url, dest_dir)
    if "youtube.com" in u or "youtu.be" in u or "tiktok.com" in u:
        return _download_ytdlp(url, dest_dir)
    raise RuntimeError(f"지원하지 않는 URL: {url}")
