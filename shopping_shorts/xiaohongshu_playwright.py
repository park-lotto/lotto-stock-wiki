"""샤오홍슈 레퍼런스 채널 수집 — 프로필 페이지 크롤(2026-07-29).

로그인 세션(storageState) 재사용 + 서버 데이터센터 IP 직결로 rednote.com 프로필 페이지를
헤드리스로 연다(Phase 0 스파이크: 검색결과 크롤 가능 검증 / 이 Task: 프로필 페이지 실측).
build_overseas_items가 기대하는 raw dict 스키마로 반환 — 해외HOT과 랭킹 공식을 그대로 공유한다.

채널 하나가 실패해도 전체가 죽지 않는다(instagram_playwright.py와 동일 원칙).
테스트는 _scrape_one을 주입해 브라우저 없이 돈다(test_xiaohongshu_playwright.py).

★2026-07-29 서버 실측으로 계획서 원안(앵커 href 정규식 파싱)을 폐기하고 아래 방식으로 교체:

1) window.__INITIAL_STATE__를 **라이브 JS 객체로 읽지 않는다.** 실측 결과 Vue 하이드레이션 이후
   (본인 소유가 아닌) 프로필의 user.notes가 null로 리셋된다(스크롤/추가 fetch 전까지). 대신
   page.content()가 돌려주는 <script> 원문 텍스트에서 `window.__INITIAL_STATE__=` 뒤의 JSON을
   균형괄호 스캔으로 직접 추출한다 — SSR이 최초 렌더에 박아둔 값이라 타이밍 문제가 없다.
2) 이 텍스트는 엄밀히는 JS 리터럴이라 `undefined` 같은 비-JSON 토큰이 섞여 있다(실측: 최상위
   global 설정 안에 `"pwaAddDesktopPrompt":undefined` 발견) — json.loads 전에 `null`로 치환한다.
3) 구조(실측): state["user"]["notes"] = [[note, note, ...], [], [], ...] (페이지네이션 배열,
   첫 페이지만 채워져 있음). note 하나 = {"id": noteId, "noteCard": {"displayTitle",
   "interactInfo": {"likedCount": "5"(문자열!)}, "cover": {"infoList":[{"url"}], "urlDefault"},
   "user": {"nickname"}, "noteId", "xsecToken"}, "xsecToken"}. comments/collects/shares 필드는
   이 그리드 응답에 아예 없다 — 0으로 채운다(ranking.build_overseas_items의 기존 방어적 관례).
4) **로그인월 판정**: state["user"]["loggedIn"] 불리언이 신뢰할 수 있는 신호다(실측: 세션 없이
   접근하면 커버 이미지·제목은 SEO용으로 그대로 SSR되지만 note id는 전부 빈 문자열이고
   loggedIn=false). URL은 안 바뀐다(리다이렉트 없음) — instagram처럼 URL 패턴으로 로그인월을
   판별할 수 없다.
5) **날짜 필드가 없다.** 이 그리드 응답엔 createTime/publishTime이 전혀 없다. 대신 noteId가
   MongoDB ObjectId 형식(24자리 hex)이라는 가설을 서버에서 실측 검증했다 — 앞 8자리 hex를
   유닉스초로 해석하면 실제 게시일과 일치했다(예: 6a68b29000000000010336d5 → 2026-07-28,
   이 계정의 최신글로 표시 순서·날짜 내림차순이 30개 노트 전부 일관됨). 정확도는 시(時) 단위까지
   보장 안 되지만 48h 윈도우 필터링엔 충분하다.
"""
import re
from datetime import datetime, timezone

from shopping_shorts import config

LAST_TALLY = {"ok": 0, "login_wall": 0, "not_found": 0, "error": 0}

_STATE_KEY = "window.__INITIAL_STATE__="
# JS 값 위치(콜론 뒤, 콤마/닫는괄호 앞)의 undefined 토큰만 null로 치환한다. \bundefined\b로
# 블롭 전체를 훑으면 안 된다 — 노트 제목·닉네임 문자열 안에 영어 단어 "undefined"가 들어있어도
# (해외용 rednote라 영어 캡션이 섞일 수 있다) 그것까지 null로 깨진다. 콜론 바로 뒤(공백만 허용,
# 따옴표 없음)에 오는 경우만 실제 JS undefined 리터럴이다 — 문자열 값은 항상 콜론 뒤에 "가 온다.
_UNDEFINED_VALUE_RE = re.compile(r":\s*undefined\s*([,}])")


def _profile_username(url):
    """프로필 URL에서 표시용 계정 식별자 추출(URL 마지막 path segment, 쿼리스트링 제외)."""
    path = (url or "").split("?", 1)[0].rstrip("/")
    return path.rsplit("/", 1)[-1]


def _extract_state_from_html(html):
    """페이지 HTML 원문에서 window.__INITIAL_STATE__ 값을 파싱해 dict로 반환.

    ★정규식 `.*?}` 로 자르면 틀린다 — 실측 데이터 안에 문자열 값 속 `}` 뒤에 실제 개행이
    섞여 있어 최초 매치에서 조기 종료된다. 문자열 인용부호를 인지하는 균형괄호 스캔만 안전하다.
    JSON이 아니라 JS 리터럴이라 `undefined` 토큰이 섞여 나온다 — null로 치환 후 파싱."""
    import json

    start = (html or "").find(_STATE_KEY)
    if start < 0:
        return None
    start += len(_STATE_KEY)
    depth = 0
    in_str = False
    esc = False
    end = None
    for i in range(start, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    raw = html[start:end]
    raw = _UNDEFINED_VALUE_RE.sub(r": null\1", raw)
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _published_at_from_note_id(note_id):
    """noteId(24자리 hex, MongoDB ObjectId 형식)의 앞 8자리 hex = 유닉스초 타임스탬프.
    실서버 실측으로 검증된 가설(같은 계정 30개 노트가 날짜 내림차순으로 전부 일치)."""
    if not note_id or len(note_id) < 8:
        return ""
    try:
        ts = int(note_id[:8], 16)
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OSError, OverflowError):
        return ""


def _thumbnail_from_cover(cover):
    cover = cover or {}
    info_list = cover.get("infoList") or []
    if info_list and isinstance(info_list[0], dict) and info_list[0].get("url"):
        return info_list[0]["url"]
    return cover.get("urlDefault") or cover.get("urlPre") or ""


def _num(v):
    """정수 변환 가능하면 int, 아니면 None(xiaohongshu_search._num과 동일 로직 — 코드베이스
    관례 재사용). likedCount가 항상 순수 숫자 문자열("5")이라는 보장이 없다 — 실측은 순수
    숫자만 봤지만, 인기 노트는 "1.2만"류 축약 표기로 올 수 있다(실측된 리스크, 가정 아님:
    이전엔 int(raw)가 그런 값에 ValueError를 던지고 그냥 0으로 뭉개져, 정작 랭킹이 가장
    잡아야 할 고참여 노트가 likes=0으로 조용히 사라졌다). None으로 반환해 "파싱 실패(값 불명)"과
    "실제 좋아요 0"을 구분한다 — 최종 스키마 조립 시점(fetch_notes)에서만 or 0으로 접는다."""
    if isinstance(v, bool):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _likes_from_interact_info(interact_info):
    return _num((interact_info or {}).get("likedCount"))


def _note_url(note_id, xsec_token):
    base = f"https://www.rednote.com/explore/{note_id}"
    if xsec_token:
        return f"{base}?xsec_token={xsec_token}&xsec_source=pc_note"
    return base


def _notes_from_state(data):
    """state["user"]["notes"](페이지 배열) → 이 모듈의 note dict 리스트.

    id가 빈 문자열인 항목(비로그인 SEO용 SSR 응답)은 제외한다 — 로그인월 판정은
    호출부(_scrape_one_playwright)가 state["user"]["loggedIn"]으로 먼저 하지만,
    이 함수 자체도 방어적으로 빈 id를 건너뛴다."""
    user_state = (data or {}).get("user") or {}
    pages = user_state.get("notes") or []
    out = []
    seen = set()
    for page in pages:
        if not isinstance(page, list):
            continue
        for item in page:
            if not isinstance(item, dict):
                continue
            note_card = item.get("noteCard") or {}
            note_id = item.get("id") or note_card.get("noteId") or ""
            if not note_id or note_id in seen:
                continue
            seen.add(note_id)
            xsec_token = item.get("xsecToken") or note_card.get("xsecToken") or ""
            out.append({
                "note_id": note_id,
                "title": note_card.get("displayTitle") or "",
                "published_at": _published_at_from_note_id(note_id),
                "likes": _likes_from_interact_info(note_card.get("interactInfo")),
                "comments": 0,   # 프로필 그리드 응답엔 없음(노트 상세페이지에만 있음)
                "collects": 0,
                "shares": 0,
                "thumbnail": _thumbnail_from_cover(note_card.get("cover")),
                "url": _note_url(note_id, xsec_token),
            })
    return out


def _scrape_one_playwright(profile_url):
    """계정 1개 → (notes, page_url, error). 브라우저를 실제로 띄우는 유일한 함수."""
    from playwright.sync_api import sync_playwright   # 지연 import — 미설치 환경에서 모듈 로드가 죽지 않게

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(storage_state=config.XIAOHONGSHU_SESSION_PATH)
            page = ctx.new_page()
            page.goto(profile_url, timeout=config.XIAOHONGSHU_PW_TIMEOUT_MS,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(3500)         # SSR 노트 그리드가 채워질 여유
            final_url = page.url
            html = page.content()
            ctx.close()
            browser.close()

        data = _extract_state_from_html(html)
        if data is None:
            return [], final_url, "no_initial_state"
        if (data.get("user") or {}).get("loggedIn") is False:
            return [], final_url, "login_wall"
        notes = _notes_from_state(data)
        return notes, final_url, None
    except Exception as e:                        # noqa: BLE001 — 계정 하나의 실패로 전체가 죽지 않게
        return [], profile_url, str(e)[:200]


def fetch_notes(profile_urls, on_progress=None, _scrape_one=None):
    """profile_urls → build_overseas_items 스키마 raw dict 리스트.

    on_progress(done, total, items_so_far, tally): 계정 1개 끝날 때마다 호출(선택).
    _scrape_one: 테스트 주입용. 기본은 실제 Playwright 스크레이퍼.
    """
    scrape = _scrape_one or _scrape_one_playwright
    urls = [(u or "").strip() for u in (profile_urls or [])]
    urls = [u for u in urls if u]
    total = len(urls)
    tally = {"ok": 0, "login_wall": 0, "not_found": 0, "error": 0}
    items = []
    for i, url in enumerate(urls, start=1):
        notes, page_url, error = scrape(url)
        if error == "login_wall":
            verdict = "login_wall"
        elif error:
            verdict = "error"
        elif not notes:
            verdict = "not_found"
        else:
            verdict = "ok"
        tally[verdict] = tally.get(verdict, 0) + 1
        uname = _profile_username(url)
        for n in notes:
            items.append({
                "video_id": n.get("note_id", ""),
                "title": n.get("title", ""),
                "published_at": n.get("published_at", ""),
                "views": 0,
                "likes": int(n.get("likes") or 0),
                "comments": int(n.get("comments") or 0),
                "collects": int(n.get("collects") or 0),
                "shares": int(n.get("shares") or 0),
                "channel_title": uname,
                "thumbnail": n.get("thumbnail", ""),
                "url": n.get("url", ""),
                "media_platform": "xiaohongshu",
                "duration": None,
            })
        if on_progress:
            on_progress(i, total, len(items), dict(tally))
    LAST_TALLY.clear()
    LAST_TALLY.update(tally)
    return items
