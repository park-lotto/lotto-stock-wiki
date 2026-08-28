"""핀터레스트 영상 수집 — **무료·로그인 없음** (2026-08-28 사장님 지시).

## 왜 핀터레스트인가
사장님: "깨끗한 영상들이 많아서". 실측으로 확인했다 —
  · 720x1280 세로 9:16, 우리 쇼츠 규격 그대로
  · 자막·워터마크가 **없는 원본**이 많다(표본 2개 중 1개는 완전히 깨끗)
→ 깨끗한 건 자막제거(VMake) 비용이 **0원**이 된다.
  2026-08-25 크레딧 소진으로 고객이 9번 실패하고 신고한 그 비용이다.

## 어떻게 긁나 (실측으로 확정, 추측 아님)
★검색 페이지 HTML엔 핀이 **0개**다(껍데기). `__PWS_DATA__`에도 설정값만 82KB 들어 있고
  핀 데이터는 없다. 그래서 curl·requests로는 아무것도 못 긁는다.
★콘텐츠는 **`BaseSearchResource/get` 응답**으로 온다 — 브라우저를 띄워 그 응답을
  가로채면 나온다(샤오홍슈 `playwright_crawl`과 **같은 방식**이라 배선을 본떴다).
★**로그인·프록시가 필요 없다**(익명 컨텍스트로 핀 38개·영상 3개 확보).
★영상 파일은 `curl`로 직접 받힌다 — yt-dlp도 필요 없다(Referer만 있으면 200).

## 안 하는 것
★워터마크 자동 필터는 **넣지 않는다**(사장님 결정: "다 담고 눈으로 고른다").
  화면을 봐야 아는 판정을 코드가 대신하면 "왜 안 담기지"가 되고 근거도 남지 않는다.
"""
import re
import urllib.parse

#: 기본 검색어 — 사장님 확정 "영어 먼저"(핀터레스트는 영어권이 압도적).
#: 장비템·신박템 컨셉. 여기 없는 말은 화면에서 직접 넣는다.
DEFAULT_KEYWORDS = [
    "welding tool hack",
    "diy tool invention",
    "amazing tools gadget",
    "workshop tool trick",
    "clever tool idea",
]

_SEARCH_API_HINT = "BaseSearchResource/get"
_PIN_URL = "https://www.pinterest.com/pin/%s/"


def _best_video(videos):
    """여러 화질 중 **가장 큰 것**. 우리 렌더가 세로 고화질을 쓴다.
    반환 (url, width, height) — 못 찾으면 (None, 0, 0)."""
    vl = (videos or {}).get("video_list")
    if not isinstance(vl, dict):
        return None, 0, 0
    best, bw, bh = None, 0, 0
    for v in vl.values():
        if not isinstance(v, dict):
            continue
        u = str(v.get("url") or "")
        if not u.endswith(".mp4"):
            continue
        w = int(v.get("width") or 0)
        if w >= bw:
            best, bw, bh = u, w, int(v.get("height") or 0)
    return best, bw, bh


def parse_pins(body):
    """응답 JSON → 영상 핀 목록. 이미지 핀·광고는 버린다.

    ★고정 경로로 파지 않고 **재귀로 훑는다**. 플랫폼 응답 구조는 예고 없이 바뀌고
      (메모리 `인스타통로_주기적폐지`: 비공식 통로는 1~2달마다 폐지된다), 고정 경로면
      그날 통째로 0건이 된다. 재귀는 구조가 바뀌어도 videos 블록만 있으면 찾는다.
    """
    found = {}

    def walk(o):
        if isinstance(o, dict):
            vids = o.get("videos")
            if isinstance(vids, dict):
                url, w, h = _best_video(vids)
                if url:
                    pid = str(o.get("id") or "")
                    key = pid or url
                    if key not in found:
                        found[key] = {
                            "pin_id": pid,
                            "url": (_PIN_URL % pid) if pid else "",
                            "video_url": url,
                            "width": w,
                            "height": h,
                            # 핀터레스트는 ms로 준다 — 우리 나머지 코드는 전부 초다.
                            "duration": round(float(vids.get("duration") or 0) / 1000.0, 1),
                            "title": (o.get("grid_title") or o.get("title") or "").strip(),
                            "desc": (o.get("description") or "").strip()[:200],
                            "thumbnail": _thumb(o),
                        }
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(body)
    return list(found.values())


def _thumb(pin):
    """썸네일 — 카드에 그림이 없으면 재생이 조용히 죽는다(메모리 `인라인재생_프록시화이트리스트`)."""
    im = pin.get("images")
    if isinstance(im, dict):
        for k in ("orig", "736x", "600x", "474x", "236x"):
            v = im.get(k)
            if isinstance(v, dict) and v.get("url"):
                return v["url"]
        for v in im.values():
            if isinstance(v, dict) and v.get("url"):
                return v["url"]
    return ""


def _crawl(keyword, scrolls, timeout_ms, tab="pins"):
    """실제 브라우저를 띄우는 유일한 함수 — 테스트는 이걸 주입 대체한다
    (playwright_crawl._crawl_xiaohongshu과 같은 계약).

    tab: "pins"=일반 검색(종전 그대로) / "videos"=영상 전용 탭(2026-08-29 렌즈용).
    ★영상 핀은 일반 탭에 거의 안 나온다 — 실측: '인덕션 테이블'·'induction table'
      등 4키워드 전부 pins 탭 영상 0개, videos 탭은 12개씩."""
    from playwright.sync_api import sync_playwright   # 지연 import — 미설치 환경 보호

    caps = []

    def on_response(resp):
        if _SEARCH_API_HINT not in resp.url:
            return
        try:
            caps.append(resp.json())
        except Exception:      # noqa: BLE001 — JSON이 아니면 무시
            pass

    url = ("https://www.pinterest.com/search/%s/?q=" % (tab if tab == "videos" else "pins")
           + urllib.parse.quote(keyword))
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        pg.on("response", on_response)
        pg.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        # 무한스크롤 — 스크롤해야 다음 묶음이 온다(첫 응답만으론 20~40개뿐).
        for _ in range(max(1, scrolls)):
            pg.wait_for_timeout(1500)
            pg.mouse.wheel(0, 2500)
        pg.wait_for_timeout(2000)
        b.close()
    return caps


def search_videos(keyword, max_results=40, scrolls=5, timeout_ms=45000, _crawler=None,
                  tab="pins"):
    """키워드 → 영상 핀 목록. 실패해도 예외를 던지지 않는다(빈 목록).

    tab="videos"면 영상 전용 검색 탭을 긁는다(렌즈 '여기서' 검색용, 2026-08-29).
    기본은 종전 그대로 "pins" — 핀터레스트 탭 수집의 동작은 안 바뀐다.

    ★수집이 서비스를 죽이면 안 된다 — 브라우저가 없거나 페이지가 바뀌어도 []를 준다.
      단 **조용히 삼키지는 않는다**(아래 print) — 0건이 '없음'인지 '고장'인지 구별해야 한다.
    """
    import sys
    # ⚠️ 주입 크롤러(_crawler)의 계약은 (keyword, scrolls, timeout_ms) 3인자 그대로다
    #    — 기존 테스트·수집이 이 모양을 쓴다. tab은 기본 _crawl에만 전달한다.
    crawl = _crawler or (lambda k, s, t: _crawl(k, s, t, tab=tab))
    try:
        bodies = crawl(keyword, scrolls, timeout_ms)
    except Exception as e:  # noqa: BLE001
        print(f"[핀터레스트] 크롤 실패 {keyword!r}: {e!r}", file=sys.stderr)
        return []
    out, seen = [], set()
    for b in bodies:
        for it in parse_pins(b):
            k = it["pin_id"] or it["video_url"]
            if k in seen:
                continue
            seen.add(k)
            out.append(it)
            if len(out) >= max_results:
                return out
    return out


# ── 핀 1개 실조회: 영상인가? (렌즈·다운로드 공용, 2026-08-29) ──────────────
# 렌즈(구글렌즈)가 물어오는 핀터레스트 링크에는 영상 여부가 없다. 위 검색 크롤과 달리
# **핀 상세 페이지는 로그인·브라우저 없이 requests로 열리고**, SEO용 JSON-LD에
# 영상 핀이면 VideoObject(mp4 직링크·길이·썸네일·제목)가 박혀 있다.
# 실측(2026-08-29, 익명 requests): 영상 핀 2/2 VideoObject 있음(contentUrl=
# v1.pinimg.com mp4, duration=PT15S) / 이미지 핀 4/4 없음 / mp4·썸네일 모두
# Referer 없이 200(핫링크 차단 없음). 비공식 API(PinResource/get)는 익명 403이라 못 쓴다.
_PIN_PAGE_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_LD_JSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
# PT15S / PT1M2S / PT1H2M3S → 초. schema.org duration(ISO8601)용.
_ISO_DUR_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$")


def iso_duration_secs(raw):
    """"PT15S" → 15.0. 못 읽으면 None(0으로 뭉개지 않는다 — 길이 모름과 0초는 다르다)."""
    m = _ISO_DUR_RE.match(str(raw or "").strip())
    if not m or not any(m.groups()):
        return None
    h, mi, s = m.groups()
    return int(h or 0) * 3600 + int(mi or 0) * 60 + float(s or 0)


def pin_video_info(url, timeout=8):
    """핀 상세 페이지 URL → 영상 정보 dict / 영상 아님 None. 네트워크 실패는 예외.

    반환 dict: {video_url, duration(초|None), thumbnail, title, description}
    ★세 가지 결과를 구분해서 준다 — 호출부의 처분이 다르기 때문이다:
      dict = 영상 확정(렌즈: 남긴다·보강 / 다운로드: mp4 직접 받기)
      None = 영상 아님 확정(렌즈: 잘라낸다 — 렌즈는 숏폼 소재를 찾는 자리)
      예외 = 판정불가(렌즈: 자르면 안 된다 — 검증 불가가 회수율을 깎으면 안 됨)"""
    import json
    import requests
    # ★두 가지를 함께 고쳐야 한다(2026-08-29 라이브 버그, 실측 표본 10개).
    #
    #   ①Accept-Encoding 명시 — 서버에 brotli 1.2.0이 깔려 있어 requests가 br을
    #     자동 광고하는데 urllib3 2.0.7과의 조합에서 디코딩이 깨진다
    #     (ContentDecodingError, 영상핀 8/8 전부 예외였다).
    #   ②주거용 프록시 경유 — **진짜 원인은 IP였다.** 데이터센터 IP엔 핀터레스트가
    #     SEO용 JSON-LD를 아예 안 내려준다:  직접 None 10/10 / 프록시 dict 10/10.
    #     헤더를 브라우저처럼 갖춰도 안 되고 IP만 바꾸면 된다(둘 다 실측).
    #
    #   ⚠️①만 고치면 **오히려 나빠진다**: 예외(판정불가 → 렌즈가 안 자름)가
    #     None(영상 아님 확정 → 렌즈가 잘라냄)으로 바뀌어 멀쩡한 영상이 사라진다.
    #   프록시 dict는 reddit_source._proxies()를 재사용한다(0순위-B) — 미설정이면
    #   None을 주므로 로컬·테스트에서도 안 깨진다.
    from shopping_shorts.reddit_source import _proxies
    r = requests.get(url, headers={"User-Agent": _PIN_PAGE_UA,
                                   "Accept-Encoding": "gzip, deflate"},
                     proxies=_proxies(), timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"핀 페이지 HTTP {r.status_code}: {url}")
    for m in _LD_JSON_RE.finditer(r.text):
        try:
            block = json.loads(m.group(1))
        except ValueError:
            continue
        for it in (block if isinstance(block, list) else [block]):
            if not (isinstance(it, dict) and it.get("@type") == "VideoObject"):
                continue
            vurl = str(it.get("contentUrl") or "")
            if not vurl:
                continue
            return {
                "video_url": vurl,
                "duration": iso_duration_secs(it.get("duration")),
                "thumbnail": str(it.get("thumbnailUrl") or ""),
                "title": str(it.get("name") or "").strip(),
                "description": str(it.get("description") or "").strip()[:300],
            }
    return None
