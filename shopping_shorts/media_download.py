"""소스 URL을 플랫폼별로 다운로드 — instagram=Apify, youtube/tiktok=yt-dlp(무료)."""
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from shopping_shorts import config


def _cookies_arg(url):
    """플랫폼별 yt-dlp 쿠키 옵션 — 파일이 있을 때만 넣는다(없으면 기존처럼 무쿠키로
    시도해 회귀가 없다). 2026-07-20: 유튜브·틱톡이 비로그인 요청을 봇으로 보고 막기
    시작해서(사장님 실측: 최신 yt-dlp로도 재현) 로그인 세션 쿠키 없인 다운로드·메타
    조회가 전부 실패한다. 쿠키파일은 사장님이 브라우저에서 직접 내보낸 것(config.py).

    유튜브는 쿠키만으론 부족했다 — 실측: 메타(-j)는 쿠키로 되는데 실제 다운로드는
    "No video formats found!"로 유명 공개영상(최초 유튜브 영상)까지 재현되는 별개
    문제였다. 원인은 유튜브의 URL 서명 난독화("n challenge")를 yt-dlp가 못 풀어서 —
    Deno(외부 JS 런타임, 로컬에 설치함)+해독 스크립트(--remote-components ejs:github,
    최초 1회 다운로드 후 ~/.cache/yt-dlp/challenge-solver에 캐시)가 있어야 실제
    포맷이 나온다. 캐시되면 다음부터 이 플래그 없이도 되지만, 캐시가 비어있는
    새 환경(서버·캐시삭제 후)에서도 자동 복구되도록 유튜브 호출에 상시 포함한다
    (이미 캐시 있으면 그냥 빠르게 스킵 — 매 호출 재다운로드 아님)."""
    u = (url or "").lower()
    if "youtube.com" in u or "youtu.be" in u:
        path = config.YTDLP_COOKIES_YOUTUBE
        extra = ["--remote-components", "ejs:github"]
    elif "tiktok.com" in u:
        path = config.YTDLP_COOKIES_TIKTOK
        extra = []
    else:
        return []
    cookies = ["--cookies", path] if path and Path(path).exists() else []
    return cookies + extra


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
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "-j", "--no-warnings",
                            *_cookies_arg(url), url],
                           capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout)
            for key, src in (("thumbnail", "thumbnail"), ("title", "title"),
                             ("channel", "uploader"), ("views", "view_count"),
                             ("likes", "like_count"), ("comments", "comment_count"),
                             ("shares", "repost_count"), ("duration", "duration"),
                             ("followers", "channel_follower_count"), ("ts", "timestamp")):
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


def _download_ytdlp(url, dest_dir, max_attempts=3):
    """유튜브/틱톡 다운로드 → (mp4경로, caption). yt-dlp 경로는 캡션 없음(빈 문자열).

    틱톡은 JS 챌린지·IP 레이트리밋으로 추출이 간헐적으로 깨진다(rehydration 에러) — 같은 URL도
    됐다 안 됐다 한다(2026-07-23 서버 실측: 같은 영상이 성공↔실패 반복, 버전·쿠키·curl_cffi 다 정상).
    단발 호출이면 그 한 번의 실패가 그대로 사용자 에러가 되므로, 백오프를 두고 재시도해 간헐적
    실패를 자가치유한다. 비공개·삭제 영상은 매 시도 같은 에러라 max_attempts 뒤 그대로 실패한다."""
    out = str(Path(dest_dir) / (uuid.uuid4().hex[:8] + ".%(ext)s"))
    stem = Path(out).stem.split('.')[0]
    last_err = ""
    for attempt in range(max_attempts):
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "-f", "mp4/bestvideo+bestaudio/best",
             "--no-playlist", *_cookies_arg(url), "-o", out, url],
            capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            files = sorted(Path(dest_dir).glob(stem + "*"))
            if files:
                return str(files[0]), ""
            last_err = "산출물 없음"
        else:
            last_err = r.stderr[-300:]
        if attempt < max_attempts - 1:
            time.sleep(2 * (attempt + 1))   # 2s·4s 백오프 — 틱톡 챌린지/레이트리밋 완화
    raise RuntimeError(f"yt-dlp 실패({url}, {max_attempts}회 시도): {last_err}")


def _download_via_relay(url, dest_dir):
    """유튜브 URL을 로컬 릴레이 큐에 넣고, 사장님 PC 에이전트가 주거용 IP로 받아
    서버에 올린 mp4를 회수한다(2026-07-24). 서버 데이터센터 IP는 유튜브에 봇차단당하므로
    직접 yt-dlp는 못 쓴다. 큐잉 후 done될 때까지 폴링(상한=YT_RELAY_POLL_TIMEOUT).
    에이전트가 안 떠 있거나 시간초과면 명확한 에러를 던진다(믹스는 이 소스만 스킵).
    ★서버는 파일을 만들지 않고 CPU도 안 쓴다 — 무거운 다운로드는 전부 PC로 오프로드된다."""
    import shutil
    from shopping_shorts.store import Store
    store = Store()
    req_id = store.enqueue_yt_relay(url)
    deadline = time.monotonic() + config.YT_RELAY_POLL_TIMEOUT
    while time.monotonic() < deadline:
        rec = store.get_yt_relay(req_id)
        if rec and rec["status"] == "done" and rec["out_path"]:
            src = Path(rec["out_path"])
            if not src.exists():
                raise RuntimeError(f"릴레이 완료 보고했으나 파일 없음: {src}")
            dst = Path(dest_dir) / src.name
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
            return str(dst), ""
        if rec and rec["status"] == "failed":
            raise RuntimeError(f"유튜브 릴레이 실패({url}): {rec.get('error') or '알 수 없음'}")
        time.sleep(2)
    raise RuntimeError(
        f"유튜브 릴레이 시간초과({url}, {config.YT_RELAY_POLL_TIMEOUT}s) — PC 에이전트가 켜져 있나 확인")


def _is_direct_video(u):
    """페이지가 아니라 **직접 재생 mp4/CDN 영상 파일** URL인지. 쿼리스트링은 떼고 판단.
    샤오홍슈 검색이 주는 url_720p(직접 mp4, xhscdn 계열)를 믹스가 그대로 받게 하려는 용도.
    ⚠️ xiaohongshu.com/rednote.com 같은 '페이지' 호스트는 여기 안 걸리고 아래 yt-dlp로 간다."""
    path = u.split("?", 1)[0]
    if path.endswith((".mp4", ".m4v", ".mov", ".webm")):
        return True
    # 알려진 영상 CDN 호스트(샤오홍슈=xhscdn, 도우인=zjcdn/douyinvod). 페이지 도메인은 제외.
    return any(h in u for h in ("xhscdn.com", "sns-video", "zjcdn.com", "douyinvod.com"))


def download_any(url, dest_dir):
    """소스 URL 다운로드 → (mp4경로, caption) 튜플. caption은 인스타에서만 채워짐."""
    u = (url or "").lower()
    # ★yt-dlp는 rednote.com 도메인을 모른다(Unsupported URL) — 같은 사이트인 xiaohongshu.com으로
    # 정규화해야 추출기가 인식한다. 렌즈가 로그인벽 우회용으로 '원본 열기'를 rednote로 바꾼 URL이
    # 믹스 소스로 그대로 넘어와 다운로드가 통째로 막혔다(2026-07-19 라이브 실측: explore+xsec_token
    # 노트를 xiaohongshu.com으로만 바꿔주면 yt-dlp가 정상 다운로드). 토큰·경로는 그대로 보존된다.
    if "rednote.com" in u:
        url = re.sub(r"://(www\.)?rednote\.com", "://www.xiaohongshu.com", url, flags=re.I)
        u = url.lower()
    # ★yt-dlp XiaoHongShuIE의 _VALID_URL은 /explore/{id}·/discovery/item/{id}만 허용(서버 실측).
    # 검색 그리드에서 담은 노트는 /search_result/{id}?xsec_token=… 모양이라 같은 노트인데도
    # Unsupported URL로 떨어졌다 → 경로만 /explore/로 바꾼다(쿼리의 xsec_token은 그대로 보존).
    if "xiaohongshu.com" in u and "/search_result/" in u:
        url = url.replace("/search_result/", "/explore/")
        u = url.lower()
    if "instagram.com" in u:
        return _download_instagram(url, dest_dir)
    # 직접 mp4(예: 샤오홍슈 url_720p) — 담긴 샤오홍슈 url은 rednote.com/search_result 검색결과
    # '페이지'라 yt-dlp로 못 받는다. 프론트가 이미 확보한 직접 mp4(play_url)를 넘기면 이 경로로
    # 그대로 HTTP 다운로드한다(Apify 재호출 없음 = 추가 비용 0). CDN URL은 만료될 수 있어
    # 담은 지 오래면 실패할 수 있다(인스타 CDN과 동일 특성) — 그땐 다시 담으면 된다.
    if _is_direct_video(u):
        from shopping_shorts.frame_extract import download_video
        return str(download_video(url, Path(dest_dir))), ""
    # 유튜브·틱톡·샤오홍슈는 yt-dlp 무료(2026-07-18 샤오홍슈 실증). 도우인은 쿠키가 필요해
    # 실패할 수 있으나 그때는 yt-dlp가 명확한 에러를 낸다(원클릭 담기 후 제작소 다운로드용).
    # ★유튜브는 서버(데이터센터 IP)서 봇차단당해 yt-dlp가 통째로 막힌다 → 릴레이가 켜져 있으면
    # 사장님 PC 에이전트로 오프로드한다(주거용 IP). 로컬/에이전트는 YT_RELAY_ENABLED=0이라
    # 아래 직접 yt-dlp 경로로 간다(회귀0). 틱톡·샤오홍슈 등은 서버서도 되므로 릴레이 안 탄다.
    if config.YT_RELAY_ENABLED and ("youtube.com" in u or "youtu.be" in u):
        return _download_via_relay(url, dest_dir)
    if any(s in u for s in ("youtube.com", "youtu.be", "tiktok.com",
                             "xiaohongshu.com", "xhslink.com", "douyin.com",
                             "iesdouyin.com", "rednote.com")):
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
             "--no-warnings", *_cookies_arg(page), page],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    except Exception:
        return ""
    if r.returncode != 0 or not r.stdout.strip():
        return ""
    return r.stdout.strip().splitlines()[0]
