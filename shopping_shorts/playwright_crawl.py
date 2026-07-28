"""해외HOT 발굴 — 샤오홍슈(rednote) 무료 Playwright 크롤(2026-07-29).

xiaohongshu_search.search_full(Apify)과 **같은 계약**(build_overseas_items raw dict)을
돌려준다. overseas_hot_jobs가 config.XHS_SCRAPER로 둘 중 하나를 골라 쓴다.

설계 요점(Phase 0 스파이크, docs/superpowers/specs/2026-07-26-해외HOT-무료Playwright크롤전환-design.md):
- 도메인은 반드시 rednote.com(xiaohongshu.com은 지역 게이트로 100% 막힘).
- 로그인 세션(storage_state)만 있으면 서버 데이터센터 IP 직결도 그대로 통과(2026-07-29 실측).
  프록시도 집PC 상시크롤도 불필요.
- DOM이 아니라 검색 API(`/api/sns/web/v1/search/notes`) 응답 JSON을 가로챈다(인스타 크롤과 동일 원칙).
  리스트 단계 응답에는 title/duration/정확한 타임스탬프가 없다 — display_title과 corner_tag_info의
  상대/부분 날짜 텍스트만 있음("X小时前"·"MM-DD"·"YYYY-MM-DD"). duration은 얻을 수 없어 None 고정
  (overseas_funnel.passes_shortform은 길이불명을 통과시키므로 문제 없음).
- 세션 쿠키는 언젠가 만료된다 — 파일이 없거나 로드 실패하면 조용히 빈 리스트를 반환해
  전체 수집(다른 플랫폼 포함)이 죽지 않게 한다.
"""
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from shopping_shorts import config

_SEARCH_API_HINT = "/api/sns/web/v1/search/notes"

_MIN_RE = re.compile(r"^(\d+)\s*分钟前$")
_HOUR_RE = re.compile(r"^(\d+)\s*小时前$")
_DAY_RE = re.compile(r"^(\d+)\s*天前$")
_YMD_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MD_RE = re.compile(r"^(\d{2})-(\d{2})$")


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_publish_time(text, now=None):
    """corner_tag_info의 publish_time 텍스트 → ISO(UTC). 못 알아보면 빈 문자열.

    정확한 시각이 없는 부분 날짜(MM-DD·YYYY-MM-DD)는 정오(12:00 UTC)로 근사한다 —
    build_overseas_items가 14일 신선도 창으로 걸러내므로 오래된 항목은 어차피 탈락한다."""
    if not text:
        return ""
    text = text.strip()
    now = now or datetime.now(timezone.utc)
    if text == "刚刚":
        return _iso(now)
    m = _MIN_RE.match(text)
    if m:
        return _iso(now - timedelta(minutes=int(m.group(1))))
    m = _HOUR_RE.match(text)
    if m:
        return _iso(now - timedelta(hours=int(m.group(1))))
    m = _DAY_RE.match(text)
    if m:
        return _iso(now - timedelta(days=int(m.group(1))))
    m = _YMD_RE.match(text)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            return _iso(datetime(y, mo, d, 12, 0, tzinfo=timezone.utc))
        except ValueError:
            return ""
    m = _MD_RE.match(text)
    if m:
        mo, d = (int(x) for x in m.groups())
        try:
            return _iso(datetime(now.year, mo, d, 12, 0, tzinfo=timezone.utc))
        except ValueError:
            return ""
    return ""


def _num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _parse_note(entry, now=None):
    """search/notes 응답 items[] 원소 하나 → raw dict(또는 None=제외 대상).

    제외 대상: 노트가 아닌 항목(광고 슬롯 등 note_card 없음), 영상이 아닌 노트(type!=video),
    발행시각을 못 알아본 경우(build_overseas_items가 published_at 없으면 어차피 드롭)."""
    if entry.get("model_type") != "note":
        return None
    nc = entry.get("note_card") or {}
    if nc.get("type") != "video":
        return None
    note_id = entry.get("id")
    if not note_id:
        return None
    corner = nc.get("corner_tag_info") or []
    pub_text = next((c.get("text") for c in corner if c.get("type") == "publish_time"), None)
    published_at = _parse_publish_time(pub_text, now=now)
    if not published_at:
        return None
    interact = nc.get("interact_info") or {}
    xsec = entry.get("xsec_token") or ""
    url = f"https://www.rednote.com/search_result/{note_id}?xsec_token={xsec}&type=video" if xsec \
        else f"https://www.rednote.com/search_result/{note_id}?type=video"
    return {
        "video_id": str(note_id),
        "title": nc.get("display_title") or "",
        "published_at": published_at,
        "views": 0,
        "likes": _num(interact.get("liked_count")),
        "comments": _num(interact.get("comment_count")),
        "collects": _num(interact.get("collected_count")),
        "shares": _num(interact.get("shared_count")),
        "channel_title": (nc.get("user") or {}).get("nickname", ""),
        "thumbnail": (nc.get("cover") or {}).get("url_default", ""),
        "url": url,
        "media_platform": "xiaohongshu",
        "duration": None,
    }


def _parse_search_response(body_json, now=None):
    """search/notes 응답 dict 하나 → raw dict 리스트."""
    items = ((body_json or {}).get("data") or {}).get("items") or []
    out = []
    for entry in items:
        parsed = _parse_note(entry, now=now)
        if parsed:
            out.append(parsed)
    return out


def _crawl_xiaohongshu(keyword, session_path, timeout_ms):
    """실제 브라우저를 띄우는 유일한 함수. 세션 로드 → 검색 페이지 방문 →
    검색 API 응답 JSON들을 캡처해 리스트로 반환. 테스트는 이 함수를 주입 대체한다."""
    from playwright.sync_api import sync_playwright   # 지연 import — 미설치 환경 보호

    captured = []

    def _on_response(resp):
        if _SEARCH_API_HINT not in resp.url:
            return
        try:
            captured.append(resp.json())
        except Exception:      # noqa: BLE001 — JSON이 아니면 무시
            pass

    url = f"https://www.rednote.com/search_result?keyword={urllib.parse.quote(keyword)}&type=video"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=session_path)
        page = ctx.new_page()
        page.on("response", _on_response)
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        browser.close()
    return captured


def search_full(keyword, max_results=40, session_path=None, timeout_ms=None, _crawl=None):
    """xiaohongshu_search.search_full과 동일 계약. 세션 파일이 없으면 빈 리스트
    (만료·미설정으로 전체 수집이 죽지 않게)."""
    session_path = session_path or config.REDNOTE_SESSION_PATH
    if not session_path or not os.path.exists(session_path):
        return []
    timeout_ms = timeout_ms or config.XHS_PW_TIMEOUT_MS
    crawl = _crawl or _crawl_xiaohongshu
    responses = crawl(keyword, session_path, timeout_ms)
    seen = set()
    out = []
    for body in responses:
        for item in _parse_search_response(body):
            vid = item["video_id"]
            if vid in seen:
                continue
            seen.add(vid)
            out.append(item)
            if len(out) >= max_results:
                return out
    return out
