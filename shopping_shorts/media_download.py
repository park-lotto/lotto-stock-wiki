"""소스 URL을 플랫폼별로 다운로드 — instagram=Apify, youtube/tiktok=yt-dlp(무료)."""
import json
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def _oembed(url):
    """틱톡·유튜브 oEmbed → {thumbnail_url,title,author_name} (무료·무인증). 실패 시 {}.
    yt-dlp가 틱톡에서 자주 깨져(rehydration) 썸네일·작성자를 이걸로 보강한다(2026-07-18 실측)."""
    u = (url or "").lower()
    if "tiktok.com" in u:
        base = "https://www.tiktok.com/oembed?url="
    elif "youtube.com" in u or "youtu.be" in u:
        base = "https://www.youtube.com/oembed?format=json&url="
    else:
        return {}
    try:
        req = urllib.request.Request(base + urllib.parse.quote(url, safe=""),
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except Exception:
        return {}


def probe_grab_meta(url, timeout=40):
    """원클릭 담기 URL → {thumbnail,title,channel,views,likes,comments,duration}(있는 것만).
    yt-dlp -j(유튜브·샤오홍슈 등은 통계까지 무료) 우선, 실패·썸네일없음 시 oEmbed(틱톡·유튜브)
    폴백. 전부 실패하면 {}. 백그라운드 보강용이라 조용히 실패."""
    out = {}
    try:
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "-j", "--no-warnings", url],
                           capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout)
            for key, src in (("thumbnail", "thumbnail"), ("title", "title"),
                             ("channel", "uploader"), ("views", "view_count"),
                             ("likes", "like_count"), ("comments", "comment_count"),
                             ("duration", "duration")):
                v = d.get(src)
                if v not in (None, ""):
                    out[key] = v
            if not out.get("channel") and d.get("channel"):
                out["channel"] = d["channel"]
    except Exception:
        pass
    if not out.get("thumbnail"):
        oe = _oembed(url)
        if oe.get("thumbnail_url"):
            out.setdefault("thumbnail", oe["thumbnail_url"])
        if oe.get("title"):
            out.setdefault("title", oe["title"])
        if oe.get("author_name"):
            out.setdefault("channel", oe["author_name"])
    return {k: v for k, v in out.items() if v not in (None, "")}


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
    # 유튜브·틱톡·샤오홍슈는 yt-dlp 무료(2026-07-18 샤오홍슈 실증). 도우인은 쿠키가 필요해
    # 실패할 수 있으나 그때는 yt-dlp가 명확한 에러를 낸다(원클릭 담기 후 제작소 다운로드용).
    if any(s in u for s in ("youtube.com", "youtu.be", "tiktok.com",
                             "xiaohongshu.com", "xhslink.com", "douyin.com", "iesdouyin.com")):
        return _download_ytdlp(url, dest_dir)
    raise RuntimeError(f"지원하지 않는 URL: {url}")


def resolve_media_url(platform, video_id, timeout=30):
    """유튜브/틱톡 영상ID → 진행형 mp4 direct URL(다운로드 없이). yt-dlp -g로
    재생 가능한 단일 mp4 포맷 URL만 뽑는다. 실패(비공개·지역차단) 시 "".
    캡처(canvas)를 위해 우리 <video>로 same-origin 재생하려는 용도(2026-07-14).
    embed(iframe)은 크로스도메인이라 canvas 캡처가 안 돼 mp4로 직접 재생한다."""
    page = {
        "youtube": f"https://www.youtube.com/watch?v={video_id}",
        "tiktok": f"https://www.tiktok.com/@x/video/{video_id}",
    }.get(platform)
    if not page:
        return ""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "-g", "-f",
             "best[ext=mp4][vcodec!=none][acodec!=none]/best[ext=mp4]/best",
             "--no-warnings", page],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    except Exception:
        return ""
    if r.returncode != 0 or not r.stdout.strip():
        return ""
    return r.stdout.strip().splitlines()[0]
