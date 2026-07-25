"""틱톡 어댑터 — yt-dlp로 시드 계정의 최근 영상 목록+메타를 무료로 수집.

틱톡은 무료 키워드 검색 API가 없어(유튜브 Data API와 다름) 사용자가 등록한
관심 @계정을 훑는 '시드 계정' 방식. yt-dlp --flat-playlist가 계정 영상의
조회수·좋아요·댓글·게시시각을 반환한다(실측 2026-07-13, 썸네일은 flat엔 없음).
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone


def _account_url(username):
    """@handle / handle / 전체 URL 모두 https://www.tiktok.com/@handle 로 정규화."""
    u = (username or "").strip()
    if u.startswith("http"):
        return u
    u = u.lstrip("@")
    return f"https://www.tiktok.com/@{u}"


def _fetch_once(username, limit, timeout):
    """yt-dlp 1회 실행 → 원시 dict 리스트. 실패(비공개·삭제·차단) 시 빈 리스트."""
    url = _account_url(username)
    try:
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--flat-playlist", "-J",
             "--playlist-end", str(limit), "--no-warnings", url],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    except Exception:
        return []
    if r.returncode != 0 or not r.stdout:
        return []
    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        return []
    out = []
    for e in data.get("entries") or []:
        vid = str(e.get("id") or "")
        if not vid:
            continue
        ts = e.get("timestamp")
        published_at = (
            datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if ts else ""
        )
        out.append({
            "video_id": vid,
            "url": e.get("url") or e.get("webpage_url") or f"{url}/video/{vid}",
            "channel_title": e.get("channel") or e.get("uploader") or username.lstrip("@"),
            "title": e.get("title") or "",
            "thumbnail": e.get("thumbnail") or "",   # flat엔 대개 없음 → 카드에서 생략
            "published_at": published_at,
            "views": int(e.get("view_count") or 0),
            "likes": int(e.get("like_count") or 0),
            "comments": int(e.get("comment_count") or 0),
        })
    return out


def fetch_account_videos(username, limit=30, timeout=120):
    """틱톡 계정의 최근 영상 → 원시 dict 리스트. 실패(비공개·삭제·차단) 시 빈 리스트.

    반환 dict: video_id, url, channel_title, title, thumbnail(''), published_at(ISO),
    views, likes, comments — build_tiktok_items가 그대로 소비.
    """
    # yt-dlp 채널목록은 간헐적으로 빈 응답을 준다(2026-07-24 실측) — 짧게 재시도한다.
    # 끝내 비면 그 채널만 건너뛰고 빈 리스트(전체 수집은 계속 — 부분실패 허용).
    for attempt in range(3):
        vids = _fetch_once(username, limit, timeout)
        if vids:
            return vids
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    return []
