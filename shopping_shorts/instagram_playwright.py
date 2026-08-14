"""인스타 릴스 수집 — Playwright + 세션 로그인(2026-07-29 프로덕션 전환, 이전 주거용 프록시안 대체).

apify_client.fetch_reels와 **같은 계약**(10키 dict 리스트)을 돌려준다. 그래서
service.py는 어느 쪽을 쓰든 하류가 무변경이다.

설계 요점:
- DOM을 파싱하지 않는다. page.on("response")로 인스타가 스스로 부르는 JSON을 가로챈다.
  DOM에는 조회수·댓글수가 축약("1.2만")으로만 나오고, 인스타가 마크업을 수시로 바꾼다.
- 채널 하나가 실패해도 전체가 죽지 않는다(Apify 403이 통째로 죽이던 문제).
- 채널마다 on_progress를 부른다 — 50분간 아무 표시가 없어 사장님이 취소한 게 발단이다.
- **로그인 세션(`config.INSTAGRAM_SESSION_PATH`)이 핵심** — 이게 있어야 캡차·로그인벽 없이
  서버 데이터센터 IP로 직결된다. 세션 생성·재발급 절차는 config.py의 해당 항목 주석과
  `handoff/AI픽자동적재.md`("세션 만료 시 재발급 절차") 참고. 서버 실측(2026-07-29):
  192채널 ok187·not_found5·login_wall0·error0, 19.1분(Apify 28분보다 빠름).

테스트는 _scrape_one을 주입해 브라우저 없이 돈다(test_instagram_playwright.py).
"""
import itertools
import json
import os
from contextlib import contextmanager

from shopping_shorts import config
from shopping_shorts.instagram_parse import (
    classify_channel_result, extract_follower_count, extract_hashtag_search_items,
    extract_reel_nodes, parse_hashtag_search_item, parse_reel_node,
)

# 마지막 실행의 분류 집계 — 호출부(service/app)가 job 결과에 담아 화면·보고에 쓴다.
# ★이 숫자가 부계정(B안) 도입 여부의 판단 근거다.
LAST_TALLY = {"ok": 0, "login_wall": 0, "not_found": 0, "error": 0}

# 인스타가 릴스 목록을 채울 때 부르는 내부 API 경로 조각. 이 중 하나가 들어간
# 응답만 JSON으로 읽는다(이미지·폰트 등 나머지는 무시).
_REEL_API_HINTS = ("/api/v1/clips/user/", "/api/v1/feed/reels_media", "/graphql")

# 인스타 웹 클라이언트가 자기 자신도 쓰는 공개 앱ID(비밀 아님 — 오랫동안 커뮤니티에 널리
# 알려진 값). /api/v1/media/{pk}/info/ 같은 REST 엔드포인트를 직접 부를 때 필요하다.
_IG_APP_ID = "936619743392459"


def _scrape_one_playwright(username, session_path=None, proxy=None):
    """채널 1개 → (nodes, page_url, error). 브라우저를 실제로 띄우는 유일한 함수.

    반환 계약을 (nodes, page_url, error) 세 값으로 고정한 이유: 분류(classify_channel_result)가
    이 세 가지만 있으면 판정할 수 있어, 테스트에서 통째로 대체하기 쉽다.
    """
    from playwright.sync_api import sync_playwright   # 지연 import — 미설치 환경에서 모듈 로드가 죽지 않게
    from playwright_stealth import Stealth   # navigator.webdriver 등 자동화 흔적 위장(2026-07-29 실사고)

    url = f"https://www.instagram.com/{username}/reels/"
    captured = []
    # 반환 계약을 (nodes, page_url, error) 3값으로 유지하려고 팔로워는 노드에 실어 보낸다
    # (계약을 4값으로 늘리면 _scrape_one 주입 테스트가 통째로 깨진다).
    follower_box = [0]
    # AutomationControlled 끄기 — 로그인 세션(storage_state)이 CDP 흔적만으로 캡차 벽에
    # 걸리는 걸 막는다(2026-07-29 실사고, scripts/instagram_setup_session.py와 동일 조치).
    launch_kw = {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}
    ctx_kw = {}
    # 계정 로테이션(2026-08-09): fetch_reels가 세션·프록시를 지정하면 그걸 쓴다.
    # 단일 계정이 scraping_warning에 걸렸던 사고 후, 아카이브 방식(계정↔IP 1:1)을 이식.
    if session_path and os.path.exists(session_path):
        ctx_kw["storage_state"] = session_path
        if proxy:
            rest = proxy.split("://", 1)[-1]
            if "@" in rest:
                cred, hostport = rest.rsplit("@", 1)
                puser, _, ppw = cred.partition(":")
                ctx_kw["proxy"] = {"server": "http://" + hostport,
                                   "username": puser, "password": ppw}
            else:
                ctx_kw["proxy"] = {"server": proxy}
    # 세션(storage_state)이 있으면 그걸로 로그인 상태 직결한다 — 샤오홍슈에서 검증된 대로
    # 프록시 없이도 되므로 프록시보다 우선한다. 없으면 기존 경로(프록시/직결)로 폴백.
    #
    # ★단, 로테이션이 계정을 지정했으면 절대 덮어쓰지 않는다(2026-08-09 버그수정).
    # 예전엔 무조건 덮어써서, 어떤 계정을 골라도 항상 config의 단일 계정이 쓰이고
    # **프록시만 로테이션 계정 것이 남았다** = 계정↔IP가 어긋난 채로 나간다.
    # 인스타는 이 불일치를 수상하게 보고 update_risky_contactpoint 챌린지를 띄운다
    # (실측 2026-08-09: 같은 계정·프록시로 단독 goto는 정상인데 이 경로만 챌린지 →
    #  수집이 전 채널 0건, tally가 전부 not_found로 잡혔다).
    if not ctx_kw.get("storage_state"):
        if config.INSTAGRAM_SESSION_PATH and os.path.exists(config.INSTAGRAM_SESSION_PATH):
            ctx_kw["storage_state"] = config.INSTAGRAM_SESSION_PATH
        elif config.INSTAGRAM_PROXY:
            from shopping_shorts.channel_archive import playwright_proxy_kw
            _pk = playwright_proxy_kw(config.INSTAGRAM_PROXY)
            if _pk:
                ctx_kw["proxy"] = _pk
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kw)
            ctx = browser.new_context(**ctx_kw)
            Stealth().apply_stealth_sync(ctx)
            page = ctx.new_page()

            def _on_response(resp):
                if not any(h in resp.url for h in _REEL_API_HINTS):
                    return
                try:
                    payload = resp.json()
                except Exception:      # noqa: BLE001 — JSON이 아니거나 모양이 다르면 그냥 무시
                    return
                # ★팔로워는 이미 이 페이지에 온다(2026-08-14 실측). /{계정}/reels/를 열면
                # 인스타가 graphql로 data.user.follower_count를 함께 내려주는데
                # (실측 roomoftem.kr=6653), 여기서 릴스 모양만 꺼내 쓰고 나머지는
                # 버리고 있었다. 그래서 발굴 채널은 팔로워가 영영 안 채워졌고
                # (실측 316건 중 212건=67% 결측), 엑셀에 있는 값도 낡아 있었다
                # (같은 채널 엑셀 3811 vs 실제 6653). 같은 응답에서 주워 담으면
                # 추가 요청·프록시 트래픽이 0이다.
                try:
                    _fc = extract_follower_count(payload)
                    if _fc:
                        follower_box[0] = _fc
                except Exception:      # noqa: BLE001 — 팔로워는 부가정보. 실패해도 릴스는 살린다
                    pass
                try:
                    captured.extend(extract_reel_nodes(payload))
                except Exception:      # noqa: BLE001
                    pass

            page.on("response", _on_response)
            page.goto(url, timeout=config.INSTAGRAM_PW_TIMEOUT_MS,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(2500)          # 릴스 목록 XHR이 도착할 여유
            # 간헐 챌린지 재시도(2026-08-09): 같은 계정·프록시로 단독 방문은 정상인데
            # 수집 경로에서만 update_risky_contactpoint가 간헐적으로 뜬다(실측).
            # 챌린지면 잠깐 쉬고 최대 2회 재진입 — 대개 두 번째엔 정상 페이지가 온다.
            for _retry in range(2):
                if not any(k in page.url for k in ("challenge", "scraping_warning", "risky", "suspended")):
                    break
                page.wait_for_timeout(8000)
                page.goto(url, timeout=config.INSTAGRAM_PW_TIMEOUT_MS,
                          wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
            final_url = page.url

            # 목록 응답(clips_connection)엔 taken_at·video_versions·caption이 없다
            # (2026-07-29 실측). 예전엔 상위 N개마다 media info REST를 한 번씩 더 불러
            # 보충했는데, 채널 219개 × 3건 = 하루 650건이 되면서 **429의 주범**이 됐다
            # (2026-07-30 실사고: 429로 taken_at이 비자 ranking이 릴스를 통째로 버려
            # 수집 결과가 80건으로 급감). 이제 발행시각은 shortcode에서 계산하므로
            # (instagram_parse.shortcode_to_timestamp) 이 왕복이 필요 없다.
            #   - caption: 랭킹 표시에 필수 아님. 담을 때 다운로드가 같이 가져온다.
            #   - video_versions(직접 mp4): 담는 시점에 릴스 페이지 URL로 받는다
            #     (media_download.download_any가 instagram.com 페이지를 처리한다).
            # 켜야 할 일이 생기면 config.INSTAGRAM_REEL_DETAIL=1 (기본 꺼짐).
            if config.INSTAGRAM_REEL_DETAIL:
                for media in captured[:config.RESULTS_PER_CHANNEL]:
                    if "taken_at" in media:
                        continue
                    pk = media.get("pk")
                    if not pk:
                        continue
                    detail = _fetch_reel_detail(ctx, pk, media.get("code") or "")
                    if detail:
                        media["taken_at"] = detail.get("taken_at")
                        media["video_versions"] = detail.get("video_versions")
                        media["caption"] = detail.get("caption")

            ctx.close()
            browser.close()
        if follower_box[0]:
            for _n in captured:
                if isinstance(_n, dict):
                    _n["_owner_follower_count"] = follower_box[0]
        return captured, final_url, None
    except Exception as e:                        # noqa: BLE001 — 채널 하나의 실패로 전체가 죽지 않게
        return [], url, str(e)[:200]


@contextmanager
def _detail_context():
    """세션·스텔스가 적용된 Playwright 컨텍스트 하나(REST 몇 건만 부를 때 쓴다).

    스크레이프 본류와 달리 페이지를 열지 않고 ctx.request로 REST만 부르는 용도 —
    카테고리 백필처럼 '캡션 1건만' 필요한 작업이 브라우저를 통째로 돌리지 않게 한다."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    ctx_kw = {}
    # ★세션 선택(2026-08-10): 구 단일 세션(INSTAGRAM_SESSION_PATH)이 본인확인
    # 챌린지에 걸려 상세 조회가 통째로 None을 돌려주는 사고가 났다(발굴 0건과
    # 같은 뿌리, 0순위-B). 로테이션 풀(reference — 신선 계정)을 1순위로 쓰고,
    # 풀이 비어 있을 때만 기존 단일 세션으로 폴백한다 — 동작 불변.
    session_path = ""
    try:
        from shopping_shorts.channel_archive import POOL_REFERENCE, session_slots
        slots = session_slots(POOL_REFERENCE)
        if slots:
            session_path = slots[0]
    except Exception:                       # noqa: BLE001 — 풀 조회 실패 시 기존 경로
        pass
    if not session_path and config.INSTAGRAM_SESSION_PATH \
            and os.path.exists(config.INSTAGRAM_SESSION_PATH):
        session_path = config.INSTAGRAM_SESSION_PATH
    if session_path:
        ctx_kw["storage_state"] = session_path
    elif config.INSTAGRAM_PROXY:
        from shopping_shorts.channel_archive import playwright_proxy_kw
        _pk = playwright_proxy_kw(config.INSTAGRAM_PROXY)
        if _pk:
            ctx_kw["proxy"] = _pk
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(**ctx_kw)
        Stealth().apply_stealth_sync(ctx)
        try:
            yield ctx
        finally:
            ctx.close()
            browser.close()


class InstagramEndpointDead(RuntimeError):
    """인스타가 우리가 쓰던 통로를 갈아엎었을 때. '왜 실패했는지'를 위로 올린다.

    ★조용한 실패 금지(2026-08-04 실사고). 예전엔 여기서 그냥 None을 반환해서,
    08-03 13:45부터 다운로드가 통째로 죽어 있었는데 **아무도 몰랐다** — 화면엔
    "생성이 취소됨"만 떴고 로그에도 사유가 안 남았다. 사유를 못 올리면 사고가
    길어진다."""


def _fetch_reel_detail(ctx, pk, code=""):
    """미디어 상세(taken_at·video_versions)를 얻는다. 실패하면 None.

    ★경로가 두 번 갈아엎혔다 — 인스타는 비공식 통로를 한두 달 주기로 바꾼다:
      - ~2026-07-28: REST `/api/v1/clips/user/`        → GraphQL 통합으로 폐지
      - ~2026-08-03: REST `/api/v1/media/{pk}/info/`   → **JSON 대신 앱껍데기 HTML**

    08-03 실측: 이 REST는 이제 200을 주면서 `text/html`(로그인된 상태의 앱 HTML)을
    돌려준다. 세션·계정·App-ID 문제가 아니다(응답 HTML 안에 로그인된 내 username이
    그대로 박혀 있었고, 브라우저 자체 fetch로 불러도 똑같이 HTML이었다) — **엔드포인트가
    없어진 것**이다. 그래서 REST를 먼저 시도하되, HTML이 오면 릴 페이지를 열어
    GraphQL 응답을 가로채는 경로로 폴백한다(서버 실측 5/5 성공, taken_at도 릴마다 정확).

    code(shortcode)가 있으면 폴백을 쓸 수 있다. 없으면 REST만 시도한다."""
    # ① 옛 REST — 살아 있으면 가장 싸다(페이지를 안 연다). 부활할 수도 있으니 남긴다.
    try:
        resp = ctx.request.get(
            f"https://www.instagram.com/api/v1/media/{pk}/info/",
            headers={"X-IG-App-ID": _IG_APP_ID},
        )
        if "json" in (resp.headers.get("content-type") or ""):
            nodes = extract_reel_nodes(resp.json())
            if nodes:
                return nodes[0]
    except Exception:      # noqa: BLE001 — 폴백 사유일 뿐
        pass
    # ② GraphQL 가로채기 폴백 — 릴 페이지가 스스로 쏘는 요청의 응답을 줍는다.
    if code:
        return _reel_detail_via_page(ctx, code)
    return None


def _reel_detail_via_page(ctx, code, timeout_ms=60000):
    """/reel/{code}/를 열어 GraphQL 응답에서 **code가 일치하는** 노드만 집어온다.

    ★code 일치 검사가 핵심이다. 이 페이지는 광고풀(PolarisClipsAdsPoolQuery)과 다음 릴
    프리페치까지 함께 받아오므로, 먼저 온 응답을 그냥 쓰면 **엉뚱한 영상**을 받는다
    (2026-08-04 실측: 요청한 DWYK8uAk9jo 대신 광고 DaUzcP6gUX8가 잡혔다). 2026-07-29에
    폐기했던 '페이지 가로채기'가 발행시각을 틀리게 준 것도 같은 원인 — 그때는 code를
    안 맞춰봤다. 지금은 맞춰보므로 taken_at이 릴마다 정확하다(실측 5/5).

    doc_id를 우리가 만들어 쏘지 않는 이유: doc_id는 인스타 배포마다 바뀌고 커서(after)에
    묶여 있어 하드코딩하면 다음 배포에 또 죽는다. 페이지가 스스로 만든 요청을 줍는 쪽이
    갈아엎힘에 강하다."""
    found = {}
    page = ctx.new_page()

    def _on_resp(res):
        if found:
            return
        if "/graphql/query" not in res.url and "/api/v1/" not in res.url:
            return
        try:
            if "json" not in (res.headers.get("content-type") or ""):
                return
            body = res.text()
            if code not in body or "video_versions" not in body:
                return
            payload = json.loads(body)
        except Exception:      # noqa: BLE001 — 남의 응답 하나 못 읽는 건 치명적이지 않다
            return

        def _walk(node):
            if isinstance(node, dict):
                if node.get("code") == code and node.get("video_versions"):
                    found["node"] = node
                    return True
                return any(_walk(v) for v in node.values())
            if isinstance(node, list):
                return any(_walk(v) for v in node)
            return False

        _walk(payload)

    page.on("response", _on_resp)
    try:
        page.goto(f"https://www.instagram.com/reel/{code}/",
                  wait_until="domcontentloaded", timeout=timeout_ms)
        for _ in range(24):        # 최대 ~12초. 응답이 오는 즉시 빠져나온다.
            if found:
                break
            page.wait_for_timeout(500)
    except Exception:              # noqa: BLE001
        pass
    finally:
        try:
            page.close()
        except Exception:          # noqa: BLE001
            pass
    return found.get("node")


_DISCOVER_SLOT_COUNTER = itertools.count()


def _discover_session_proxy():
    """발굴이 쓸 (세션경로, 프록시) 짝 — 계정↔IP를 **함께** 정한다(0순위-B).

    2026-08-10 사고: 수집·아카이브는 로테이션(ig_sessions + 주거용 출구)으로
    이관됐는데 발굴만 구 단일 세션(INSTAGRAM_SESSION_PATH)+서버직결로 남아,
    그 계정이 본인확인 챌린지(update_risky_contactpoint)에 걸리자 나흘째 0건.
    A/B 실측: 구세션·직결=0건(챌린지 리다이렉트) / 로테이션 슬롯0+kr 출구=24건.
    수집과 같은 레퍼런스 풀을 태그마다 순환해 쓴다(한 계정에 몰리지 않게).
    풀이 비면 기존 단일 세션으로 폴백(session_slots가 처리) — 동작 불변.
    """
    from shopping_shorts.channel_archive import (POOL_REFERENCE, session_slots,
                                                 slot_proxy)
    slots = session_slots(POOL_REFERENCE)
    if not slots:
        return None, None
    i = next(_DISCOVER_SLOT_COUNTER) % len(slots)
    return slots[i], slot_proxy(i, POOL_REFERENCE)


def _search_hashtag_playwright(tag):
    """해시태그 1개 → (게시물 dict 리스트, error). 계정발굴 전용(2026-07-30).

    /explore/tags/{tag}/ 진입 시 인스타가 자체적으로 부르는
    xdt_fbsearch__top_serp_graphql 응답을 가로챈다(실측: 로그인벽 없이 세션
    재사용 — hashtag당 게시물 20여개·고유계정 20개 안팎).
    세션·프록시는 _discover_session_proxy()가 짝으로 정한다(2026-08-10).
    """
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    url = f"https://www.instagram.com/explore/tags/{tag}/"
    captured = []
    launch_kw = {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}
    ctx_kw = {}
    from shopping_shorts.channel_archive import playwright_proxy_kw
    session_path, proxy = _discover_session_proxy()
    if session_path and os.path.exists(session_path):
        ctx_kw["storage_state"] = session_path
        # ★인증은 반드시 분리(2026-08-11): {"server": "http://u:p@h"}는 Playwright가
        # 인증을 무시해 조용히 실패한다 — 신규 계정을 넣고도 발굴 0건이던 뿌리.
        pk = playwright_proxy_kw(proxy)
        if pk:
            ctx_kw["proxy"] = pk
    else:
        pk = playwright_proxy_kw(config.INSTAGRAM_PROXY)
        if pk:
            ctx_kw["proxy"] = pk
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kw)
            ctx = browser.new_context(**ctx_kw)
            Stealth().apply_stealth_sync(ctx)
            page = ctx.new_page()

            def _on_response(resp):
                if "graphql" not in resp.url:
                    return
                try:
                    captured.extend(extract_hashtag_search_items(resp.json()))
                except Exception:      # noqa: BLE001 — JSON 아니거나 모양 다르면 무시
                    pass

            page.on("response", _on_response)
            # 주거용 프록시 경유는 서버직결(20s 기준)보다 훨씬 느리다 — 실측(2026-08-10):
            # 같은 태그가 20s 제한에선 goto 타임아웃으로 전 태그 0건, 60s 제한에선 24건.
            page.goto(url, timeout=max(60000, config.INSTAGRAM_PW_TIMEOUT_MS),
                      wait_until="domcontentloaded")
            page.wait_for_timeout(5000)     # SERP graphql 응답 도착 여유 — 3.5초는 서버
            # 재실측(2026-07-30)에서 0/24건으로 불안정했다, 5초는 3회 연속 24건 안정.

            # 챌린지 리다이렉트를 조용히 삼키지 않는다(2026-08-10) — 나흘 0건의
            # 원인이 로그에 한 줄도 안 남아 규명에 A/B 실측까지 필요했다.
            # URL 판정은 실제 리다이렉트 목적지(/accounts/, /challenge)로만 한다
            # (본문 문자열 검사는 CSS 변수명 오탐 전례가 있어 금지 — 0순위-B).
            if not captured and ("/accounts/" in page.url or "/challenge" in page.url):
                redirected = page.url
                ctx.close()
                browser.close()
                return [], f"challenge_redirect: {redirected[:150]}"

            # SERP 응답엔 좋아요·댓글수가 없다(실측) — 릴스수집과 같은 media info REST를
            # 상위 표본만 한 번씩 더 불러 참여도를 보강한다(2026-07-30, 샤오홍슈 발굴처럼
            # 참여도 기반 정렬을 하려면 필수 — 등장횟수만으로는 신호가 약하다는 지적 반영).
            for it in captured[:config.INSTAGRAM_DISCOVERY_DETAIL_TOP_N]:
                pk = it.get("pk")
                if not pk:
                    continue
                detail = _fetch_reel_detail(ctx, pk, it.get("code") or "")
                if detail:
                    it["like_count"] = detail.get("like_count")
                    it["comment_count"] = detail.get("comment_count")
                    it["play_count"] = detail.get("play_count")

            ctx.close()
            browser.close()
        return captured, None
    except Exception as e:                  # noqa: BLE001 — 태그 하나 실패가 전체를 죽이지 않게
        return [], str(e)[:200]


def search_hashtag(tag, _search_one=None):
    """해시태그 1개 → 발굴용 게시물 dict 리스트(파싱 완료, 참여도 포함 — discovery 전용 스키마).

    _search_one: 테스트 주입용(브라우저 없이). 기본은 실제 Playwright.
    """
    search = _search_one or _search_hashtag_playwright
    raw_items, error = search(tag)
    if error:
        return []
    out = []
    for it in raw_items:
        parsed = parse_hashtag_search_item(it)
        if parsed:
            out.append(parsed)
    return out


def fetch_reels(usernames, on_progress=None, _scrape_one=None):
    """usernames → 10키 reel dict 리스트. apify_client.fetch_reels와 동일 계약.

    on_progress(done, total, items_so_far, tally): 채널 1개 끝날 때마다 호출(선택).
    _scrape_one: 테스트 주입용. 기본은 실제 Playwright 스크레이퍼.
    """
    scrape = _scrape_one or _scrape_one_playwright
    names = [(u or "").strip().lstrip("@") for u in (usernames or [])]
    names = [u for u in names if u]
    total = len(names)
    tally = {"ok": 0, "login_wall": 0, "not_found": 0, "error": 0}
    items = []
    # 계정 로테이션(2026-08-09): 기본은 기존 단일 계정(서버 IP 직결) — 사장님 지시로
    # 아카이브 크롤이 끝나기 전까지 그 3계정을 수집에 돌려쓰지 않는다. 아카이브 종료 후
    # /etc/shopping-shorts.env에 INSTAGRAM_COLLECT_ROTATION=1을 추가하면 켜진다
    # (ig_sessions 계정들 × 계정별 주거용 출구, 아카이브와 같은 계정↔IP 1:1).
    #
    # ★풀 분리(2026-08-09): 로테이션을 켜도 **레퍼런스 전용 풀만** 본다
    # (ig_sessions/reference/). 아카이브 계정을 그대로 돌려쓰면 아침 아카이브가 태운
    # 한도를 저녁 수집이 물려받아 첫 채널부터 0건이 된다 — 분리의 핵심이 여기다.
    # reference 폴더가 없으면 기존처럼 상위 폴더 전체로 폴백한다(동작 불변).
    slots = []
    if _scrape_one is None and os.getenv("INSTAGRAM_COLLECT_ROTATION", "") == "1":
        from shopping_shorts.channel_archive import (POOL_REFERENCE, session_slots,
                                                     slot_proxy)
        slots = [(gi, sp) for gi, sp in enumerate(session_slots(POOL_REFERENCE))]
    for i, uname in enumerate(names, start=1):
        if slots:
            gi, sp = slots[(i - 1) % len(slots)]
            nodes, page_url, error = scrape(uname, session_path=sp,
                                            proxy=slot_proxy(gi, POOL_REFERENCE))
        else:
            nodes, page_url, error = scrape(uname)
        verdict = classify_channel_result(nodes, page_url, error)
        tally[verdict] = tally.get(verdict, 0) + 1
        if verdict == "ok":
            for n in nodes[:config.RESULTS_PER_CHANNEL]:
                d = parse_reel_node(n, uname)
                if d:
                    items.append(d)
        if on_progress:
            on_progress(i, total, len(items), dict(tally))
    LAST_TALLY.clear()
    LAST_TALLY.update(tally)
    return items


def fetch_profiles(usernames, _fetch_all=None):
    """apify_client.fetch_profiles(유료)와 동일 계약의 무료 대체(2026-07-30).

    {username소문자: {followers, posts, full_name}} 반환 — discover_jobs.py의
    profiles_fn 주입 지점을 코드 변경 없이 그대로 쓸 수 있게 한다. 프로필 페이지
    (/{username}/) 진입 시 인스타가 자체 호출하는 graphql user 응답에
    follower_count/media_count/full_name이 그대로 있다(실측). 브라우저 1개를
    열어 계정마다 새 탭만 여닫는다(브라우저 재시작 오버헤드 회피 — 발굴 채널은
    보통 ≤40개라 순차라도 탭 재사용이면 충분히 빠르다, 실측 계정당 ~3~4초).
    한 계정 실패는 그 계정만 빠뜨리고 나머지는 계속(발굴 부가 데이터라
    fetch_reels_fn과 달리 실패해도 전체를 죽이면 안 된다, discovery._safe_profiles 참고).
    """
    names = [(u or "").strip().lstrip("@") for u in (usernames or [])]
    names = [u for u in names if u]
    if not names:
        return {}
    fetch_all = _fetch_all or _fetch_profiles_playwright
    return fetch_all(names)


def _fetch_profiles_playwright(usernames):
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    launch_kw = {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}
    ctx_kw = {}
    if config.INSTAGRAM_SESSION_PATH and os.path.exists(config.INSTAGRAM_SESSION_PATH):
        ctx_kw["storage_state"] = config.INSTAGRAM_SESSION_PATH
    elif config.INSTAGRAM_PROXY:
        from shopping_shorts.channel_archive import playwright_proxy_kw
        _pk = playwright_proxy_kw(config.INSTAGRAM_PROXY)
        if _pk:
            ctx_kw["proxy"] = _pk
    out = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kw)
            ctx = browser.new_context(**ctx_kw)
            Stealth().apply_stealth_sync(ctx)
            for uname in usernames:
                captured = {}
                page = ctx.new_page()

                def _on_response(resp, captured=captured):
                    if "graphql" not in resp.url:
                        return
                    try:
                        d = resp.json().get("data") or {}
                        u = d.get("user")
                        if isinstance(u, dict) and u.get("username"):
                            captured["user"] = u
                    except Exception:      # noqa: BLE001
                        pass

                page.on("response", _on_response)
                try:
                    page.goto(f"https://www.instagram.com/{uname}/",
                              timeout=config.INSTAGRAM_PW_TIMEOUT_MS, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                except Exception:      # noqa: BLE001 — 계정 하나 실패가 전체를 죽이지 않게
                    pass
                page.close()
                u = captured.get("user")
                if u:
                    out[uname.lower()] = {"followers": int(u.get("follower_count") or 0),
                                          "posts": int(u.get("media_count") or 0),
                                          "full_name": u.get("full_name") or "",
                                          # 소개글 — 같은 응답에 들어 있어 추가 호출이 없다.
                                          # 카테고리 판정의 **약한 보조 신호**로만 쓴다:
                                          # 여러 분야를 함께 다루는 채널이 많다는 사장님 지적
                                          # (2026-07-30) → 해시태그·캡션이 없을 때만 참고.
                                          "biography": u.get("biography") or ""}
            ctx.close()
            browser.close()
    except Exception:      # noqa: BLE001 — 브라우저 자체가 안 뜨는 등 전체 실패면 빈 dict
        return out
    return out


def search_channels(keyword, max_results=30, **_ignored):
    """instagram_search.search_channels(Apify 유료)와 동일 계약의 무료 대체(2026-07-30).

    [{"username","url","title","thumbnail"}, ...] 형태로 맞춰 discovery.py/discover_jobs.py의
    search_fn 주입 지점을 코드 변경 없이 그대로 쓸 수 있게 한다("신규채널 픽업" 화면
    discover.html은 이 어댑터 하나로 무료 전환된다). keyword는 "#주방템"처럼 #이 붙어
    올 수 있어(_DISCOVER_CATEGORIES) 해시태그 탐색 URL엔 그대로(#은 인코딩됨), 순수
    태그 문자열 전달이 필요한 search_hashtag엔 #을 떼고 넘긴다. **_ignored로 Apify
    전용 파라미터(token/timeout/poll_interval/max_pages)를 조용히 무시 — 같은 자리에
    끼워도 TypeError가 안 나게.
    한글 해시태그 실측(2026-07-30): #주방템·#살림템·#인테리어 전부 24건 안정적으로 캡처,
    영문과 동일하게 로그인벽 없음."""
    tag = (keyword or "").lstrip("#").strip()
    if not tag:
        return []
    items = search_hashtag(tag)
    out = []
    for it in items[:max_results]:
        out.append({
            "username": it["username"],
            "url": it.get("url") or "",
            "title": it.get("full_name") or "",
            "thumbnail": "",   # SERP 응답엔 프레임 썸네일이 없다(실측) — 카드 썸네일은 빈 값으로 폴백
        })
    return out
