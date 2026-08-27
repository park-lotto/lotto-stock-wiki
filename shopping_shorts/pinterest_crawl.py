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


def _crawl(keyword, scrolls, timeout_ms):
    """실제 브라우저를 띄우는 유일한 함수 — 테스트는 이걸 주입 대체한다
    (playwright_crawl._crawl_xiaohongshu과 같은 계약)."""
    from playwright.sync_api import sync_playwright   # 지연 import — 미설치 환경 보호

    caps = []

    def on_response(resp):
        if _SEARCH_API_HINT not in resp.url:
            return
        try:
            caps.append(resp.json())
        except Exception:      # noqa: BLE001 — JSON이 아니면 무시
            pass

    url = "https://www.pinterest.com/search/pins/?q=" + urllib.parse.quote(keyword)
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


def search_videos(keyword, max_results=40, scrolls=5, timeout_ms=45000, _crawler=None):
    """키워드 → 영상 핀 목록. 실패해도 예외를 던지지 않는다(빈 목록).

    ★수집이 서비스를 죽이면 안 된다 — 브라우저가 없거나 페이지가 바뀌어도 []를 준다.
      단 **조용히 삼키지는 않는다**(아래 print) — 0건이 '없음'인지 '고장'인지 구별해야 한다.
    """
    import sys
    crawl = _crawler or _crawl
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
