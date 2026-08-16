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
    elif "instagram.com" in u:
        # ★인스타 세션 쿠키(2026-08-03 실사고 DbhC6twy0IA): 무쿠키 yt-dlp에 인스타가
        # "empty media response"를 주고, Apify 폴백은 17계정 소진 → 담기 예열이 통째로
        # 죽고 실패 래치까지 걸렸다. 수집기(instagram_playwright)가 이미 로그인 세션
        # (storage_state JSON)으로 잘 붙고 있으므로 같은 세션을 cookies.txt로 변환해 쓴다.
        path = _ig_cookies_file()
        extra = []
    else:
        return []
    cookies = ["--cookies", path] if path and Path(path).exists() else []
    return cookies + extra


def _ig_cookies_file():
    """INSTAGRAM_SESSION_PATH(Playwright storage_state JSON) → yt-dlp용 Netscape cookies.txt.

    세션 파일 옆에 파생 파일로 캐시하고, 원본 mtime이 바뀌면(재로그인) 다시 만든다.
    실패하면 "" — 종전(무쿠키) 동작 그대로라 회귀가 없다."""
    src = config.INSTAGRAM_SESSION_PATH
    # 2026-08-09: 메인 세션이 죽으면(만료 쿠키에 인스타가 404) 제한 게시물 재생이
    # 전부 원본 새탭으로 튄다(사장님 제보). 아카이브 크롤이 실제로 쓰는 로테이션
    # 세션(INSTAGRAM_SESSION_DIR)이 매일 갱신되는 살아있는 계정이므로, 메인 포함
    # 후보 중 **가장 최근 갱신된** 세션을 쿠키 소스로 쓴다.
    import os as _os
    _d = _os.getenv("INSTAGRAM_SESSION_DIR", "")
    _cands = [src] if (src and Path(src).exists()) else []
    if _d and Path(_d).is_dir():
        _cands += [str(p) for p in Path(_d).glob("*.json")]
    if not _cands:
        return ""
    src = max(_cands, key=lambda p: Path(p).stat().st_mtime)
    out = Path(src).with_suffix(".ytdlp-cookies.txt")
    try:
        if out.exists() and out.stat().st_mtime >= Path(src).stat().st_mtime:
            return str(out)
        state = json.loads(Path(src).read_text(encoding="utf-8"))
        lines = ["# Netscape HTTP Cookie File"]
        for c in state.get("cookies") or []:
            domain = c.get("domain") or ".instagram.com"
            lines.append("\t".join([
                domain, "TRUE" if domain.startswith(".") else "FALSE",
                c.get("path") or "/", "TRUE" if c.get("secure") else "FALSE",
                str(int(c.get("expires") or 0) if (c.get("expires") or 0) > 0 else 2147483647),
                c.get("name") or "", c.get("value") or ""]))
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(out)
    except Exception:  # noqa: BLE001 — 변환 실패는 무쿠키 폴백 사유일 뿐
        return ""


def _proxy_arg(url):
    """B안(2026-07-24): 유튜브만 프록시로 보낸다(config.YTDLP_PROXY 설정 시). 서버 데이터센터 IP가
    유튜브에 봇차단당하는 걸 주거용 프록시로 우회 → PC 릴레이 없이 서버가 직접 받는다. 틱톡·샤오홍슈
    등은 서버서도 되므로 프록시를 안 태워(대역폭·비용 절약). 미설정이면 [](회귀0)."""
    u = (url or "").lower()
    if config.YTDLP_PROXY and ("youtube.com" in u or "youtu.be" in u):
        # 회전 주거용 프록시는 죽은 IP로 라우팅되면 502(Tunnel failed)를 뱉는다 — 재시도하면
        # 새 IP로 성공한다(2026-07-24 실측: GB풀 불량, DE/CA/FR 정상). 재시도를 넉넉히 줘서
        # 드문 502에 소스가 통째로 스킵되지 않게 한다.
        return ["--proxy", config.YTDLP_PROXY,
                "--extractor-retries", "10", "--retries", "10", "--socket-timeout", "30"]
    return []


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
                            *_cookies_arg(url), *_proxy_arg(url), url],
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


_IG_CODE_RE = re.compile(r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)")


def _ig_video_via_session(code):
    """shortcode → 세션 REST(video_versions)의 직접 mp4 URL. 실패·세션 없음이면 "".

    수집기(instagram_playwright)가 매일 쓰는 로그인 세션 경로를 그대로 재사용한다 —
    yt-dlp 인스타 추출기가 깨져 있을 때의 무료 안전망(2026-08-03).

    ★code를 반드시 넘긴다(2026-08-04): 인스타가 REST(/media/{pk}/info/)를 없애고 HTML을
    돌려주기 시작해, _fetch_reel_detail이 code로 GraphQL 폴백을 타야 mp4를 얻는다.
    code 없이 부르면 REST만 시도하다 그대로 실패한다."""
    from shopping_shorts import config as _cfg
    if not (_cfg.INSTAGRAM_SESSION_PATH and Path(_cfg.INSTAGRAM_SESSION_PATH).exists()):
        return ""
    from shopping_shorts.instagram_parse import shortcode_to_pk
    from shopping_shorts.instagram_playwright import _detail_context, _fetch_reel_detail
    pk = shortcode_to_pk(code)
    if not pk:
        return ""
    with _detail_context() as ctx:
        node = _fetch_reel_detail(ctx, pk, code)
    vv = (node or {}).get("video_versions") or []
    return (vv[0] or {}).get("url") or "" if vv else ""


def _download_instagram(url, dest_dir):
    """인스타 릴스 다운로드 → (mp4경로, caption).

    ★Apify는 **폴백**이다(2026-07-31 순서 뒤집음). 예전엔 Apify가 유일한 경로라
    크레딧이 마르는 순간 담기·대본추출·예열이 통째로 죽었다(실측:
    "apify 토큰 17개 전부 실패 — 계정 17/17 소진" → 담은 영상 2개 모두 대본 0,
    화면엔 "대본을 아직 분석하지 못했어요"만 떴다).
    수집은 이미 무료 Playwright로 옮겼는데 다운로드만 유료 경로에 남아 있었다.

    순서: ① 세션 쿠키 기반 yt-dlp(무료, resolve_media_url과 같은 경로) →
          ② 실패 시 Apify(유료, 남아 있으면) → ③ 둘 다 실패해야 에러.
    caption은 Apify에서만 온다(무료 경로는 빈 문자열) — 추출은 캡션 없이도 돈다.
    """
    from shopping_shorts.frame_extract import download_video

    m = _IG_CODE_RE.search(url or "")
    code = m.group(1) if m else ""
    # ① 무료 경로 — 릴스 페이지에서 mp4 direct URL을 뽑는다(오늘 서버 실측으로 동작 확인).
    if code:
        try:
            direct = resolve_media_url("instagram", code)
            if direct:
                return str(download_video(direct, Path(dest_dir))), ""
        except Exception:      # noqa: BLE001 — 무료 경로 실패는 폴백 사유일 뿐
            pass
    # ①-b 무료 폴백(2026-08-03 실사고 DbhC6twy0IA): yt-dlp 인스타 추출기는 세션 쿠키를
    # 태워도 400/empty media로 자주 죽는다(서버 실측). 수집기와 **같은 세션 REST**
    # (/api/v1/media/{pk}/info/)로 video_versions 직접 mp4를 받는다 — 수집이 이 경로로
    # 매일 성공 중이라 가장 믿을 만한 무료 경로다. Apify(유료)는 그 다음.
    if code:
        try:
            direct = _ig_video_via_session(code)
            if direct:
                return str(download_video(direct, Path(dest_dir))), ""
        except Exception:      # noqa: BLE001 — 폴백 사유일 뿐
            pass
    # ② 유료 폴백 — 크레딧이 남아 있으면 캡션까지 얻는다.
    # ★킬스위치를 따른다(2026-08-04). 수집은 INSTAGRAM_SCRAPER=playwright로 이미 Apify를
    # 떠났는데 **다운로드만 이 분기를 안 보고** 무조건 Apify로 폴백하고 있었다. 그래서
    # 08-03 사고 때 "안 쓰는 Apify가 17개 토큰 전부 소진"이라는 엉뚱한 에러가 사용자에게
    # 떴고, 진짜 원인(인스타가 REST를 없앰)이 그 뒤에 가려졌다. 안 쓰는 유료 경로는
    # 시도도 하지 말고, 사유는 무료 경로 기준으로 정확히 말한다.
    from shopping_shorts import config as _cfg
    if _cfg.INSTAGRAM_SCRAPER != "playwright":
        try:
            from shopping_shorts.apify_client import fetch_single_reel
            raw = fetch_single_reel(url)
            if raw and raw.get("videoUrl"):
                return str(download_video(raw["videoUrl"], Path(dest_dir))), raw.get("caption", "")
        except Exception as e:     # noqa: BLE001
            raise RuntimeError(f"인스타 영상 해석 실패(무료·유료 경로 모두): {url} — {e}") from e
    raise RuntimeError(
        f"인스타 영상을 받지 못했습니다: {url} — 무료 경로(yt-dlp·세션 GraphQL)가 모두 "
        f"실패했습니다. 인스타가 통로를 또 바꿨거나(주기적으로 발생) 로그인 세션이 "
        f"만료됐을 수 있습니다. 관리자 확인이 필요합니다.")


def _download_douyin(url, dest_dir, timeout=180):
    """도우인 다운로드 → (mp4경로, ""). douyin_fetch를 **서브프로세스**로 돌린다 —
    호출부(FastAPI 백그라운드)가 asyncio 루프 위라 sync_playwright를 인프로세스로
    못 돌리기 때문(yt-dlp를 서브프로세스로 부르는 기존 패턴과 동일). 상세 근거는
    douyin_fetch.py 도크스트링."""
    r = subprocess.run(
        [sys.executable, "-m", "shopping_shorts.douyin_fetch", url, str(dest_dir)],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"도우인 다운로드 실패({url}): {(r.stderr or '')[-300:]}")
    try:
        path = json.loads(r.stdout.strip().splitlines()[-1])["path"]
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"도우인 다운로드 출력 해석 실패({url}): {r.stdout[-200:]}") from e
    if not Path(path).exists():
        raise RuntimeError(f"도우인 다운로드 산출물 없음: {path}")
    return path, ""


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
        # ★화질 천장(2026-07-27 사장님 "원본 동일"): 예전 -f "mp4/..."는 mp4(progressive
        #   단일 스트림)를 먼저 잡아 유튜브에서 720p·360p 저화질을 받았다(원본이 고화질이어도).
        #   최고 해상도 영상+음성을 따로 받아 mp4로 머지한다 — 이래야 원본 해상도가 천장이 된다.
        #   (틱톡 등 분리 스트림이 없으면 best 단일로 폴백; 그 best는 보통 원본 해상도다.)
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp",
             "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
             "--merge-output-format", "mp4",
             "--no-playlist", *_cookies_arg(url), *_proxy_arg(url), "-o", out, url],
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
    # db_path는 필수 인자다(2026-08-11 실사고): 릴레이 경로가 프록시 도입 이후 한 번도
    # 안 불려서, Store 시그니처가 바뀐 걸 아무도 못 밟았다 — 프록시가 죽어 릴레이로
    # 되돌리는 순간 첫 줄에서 TypeError로 터졌다.
    store = Store(config.DB_PATH)
    req_id = store.enqueue_yt_relay(url)
    deadline = time.monotonic() + config.YT_RELAY_POLL_TIMEOUT
    while time.monotonic() < deadline:
        rec = store.get_yt_relay(req_id)
        if rec and rec["status"] == "done" and rec["out_path"]:
            src = Path(rec["out_path"])
            if not src.exists():
                raise RuntimeError(f"릴레이 완료 보고했으나 파일 없음: {src}")
            # yt-dlp 경로는 -o가 폴더를 알아서 만들지만 릴레이는 copy2라 직접 만들어야
            # 한다(2026-08-11): 없으면 FileNotFoundError로 다운로드가 통째로 실패한다.
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
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
    # 우선순위: 프록시(B) > 릴레이(A) > 직접. 프록시가 있으면 서버가 직접 받으므로(아래 _download_ytdlp가
    # _proxy_arg로 프록시를 붙인다) PC 릴레이를 건너뛴다 — PC 의존 없이 고객 다중 처리 가능.
    if config.YT_RELAY_ENABLED and not config.YTDLP_PROXY and ("youtube.com" in u or "youtu.be" in u):
        return _download_via_relay(url, dest_dir)
    # ★도우인은 yt-dlp가 서버·가정 IP 양쪽에서 "Fresh cookies needed"로 전멸(2026-08-16 실측,
    # 최신·master 동일). 유일하게 되는 경로 = headless chromium으로 modal_id 페이지 SSR에서
    # 서명 CDN URL을 뽑아 직접 받는 것(douyin_fetch, 서버서 1080p mp4 실증). 실패하면 종전
    # 동작(yt-dlp) 그대로 폴백해 회귀 0.
    if "douyin.com" in u or "iesdouyin.com" in u:
        try:
            return _download_douyin(url, dest_dir)
        except Exception:  # noqa: BLE001 — 폴백 사유일 뿐, 최종 에러는 yt-dlp가 말한다
            pass
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
        # 인스타 추가(2026-07-30): 수집이 더 이상 직접 mp4(video_versions)를 담지 않는다
        # — 그걸 채우던 릴스 상세 REST가 429의 주범이었다. 그 결과 랭킹 카드 썸네일의
        # 인라인 재생이 사라졌으므로(video_url이 비어 onclick이 안 붙음), **볼 때 그 자리에서**
        # 해석한다. 하루 950건 긁던 것을 사람이 실제로 누른 몇 건으로 바꾸는 셈이다.
        "instagram": f"https://www.instagram.com/reel/{video_id}/",
    }.get(platform)
    if not page:
        return ""

    def _try(cookies):
        """cookies=False면 쿠키 없이 — 만료 세션이 오히려 막을 때의 탈출구."""
        try:
            r = subprocess.run(
                [sys.executable, "-m", "yt_dlp", "-g", "-f",
                 "best[ext=mp4][vcodec!=none][acodec!=none]/best[ext=mp4]/best",
                 "--no-warnings", *(_cookies_arg(page) if cookies else []),
                 *_proxy_arg(page), page],
                capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        except Exception:
            return ""
        if r.returncode != 0 or not r.stdout.strip():
            return ""
        return r.stdout.strip().splitlines()[0]

    url = _try(cookies=True)
    if url:
        return url
    # ★쿠키가 있는데 실패했으면 **쿠키 없이 한 번 더** (2026-08-04 실사고).
    # 만료된 인스타 세션을 붙이면 인스타가 404를 주는데, 같은 릴스가 무쿠키로는 멀쩡히
    # 열린다(실측 10건: 쿠키 0/10 성공 · 무쿠키 8/10 성공). 쿠키는 비공개/제한 게시물을
    # 열어주는 '추가 수단'이지 필수가 아니므로, 실패 시 무쿠키가 항상 더 나은 하한선이다.
    # 세션이 살아 있으면 첫 시도에서 끝나 이 경로는 안 탄다(비용 0).
    if _cookies_arg(page):
        return _try(cookies=False)
    return ""
