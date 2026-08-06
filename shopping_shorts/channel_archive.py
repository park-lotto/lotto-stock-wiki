"""추적 채널 릴스 전체 아카이브 크롤러(2026-08-03).

매일 수집(collect)은 최근 48h 창만 봐서, 추적 시작 전 히트작이 DB에 없었다
(실측: 집코드 채널에서 334만 조회 릴스가 미보유). 이 크롤러가 채널 릴스 페이지를
스크롤 페이지네이션으로 끝까지 훑어 channel_archive에 채운다.

운영 원칙(사장님 지시 2026-08-03):
- **대형 채널(팔로워순)부터**, 되는 만큼 계속.
- **사용하면서 수집**: 렌더·믹스가 도는 동안은 대기(양보). 채널 사이 랜덤 휴식.
- 신규 채널 자동 편입: 대상 = (엑셀 ∪ 발굴등록 − 차단) − 아카이브 done.
- 429/로그인벽 감지 시 30분 백오프, 2연속이면 그 회차 중단(상태 남김 → 재실행 시 이어짐).

**비전태깅은 이 모듈이 하지 않는다(2026-08-04 분리).** 여기는 릴스를 모으기만 한다.
태깅은 `archive_tagger`가 DB를 읽어 채널당 N개씩 라운드로빈으로 돌린다 — 이유는
run() 안의 주석 참고(요약: 붙여두면 채널당 34분 → 691채널 16일).

실행: python -m shopping_shorts.channel_archive [--limit N] [--max-scrolls M]
서버에서 nohup로 돌려두면 전 채널 완주 후 종료. 재실행하면 미완 채널만 이어서.
"""
import argparse
import os
import random
import time
from datetime import datetime, timezone

from shopping_shorts import config
from shopping_shorts.channels import load_channels
from shopping_shorts.config import DB_PATH
from shopping_shorts.instagram_parse import (extract_reel_nodes, parse_reel_node,
                                             shortcode_to_timestamp)
from shopping_shorts.store import Store

_MAX_SCROLLS = 200       # 채널당 스크롤 상한(약 12개/스크롤 → 대략 2400개까지)
_STALL_LIMIT = 6         # 연속 N회 새 릴스 0이면 바닥으로 판정
# 프록시 대역폭을 먹는 리소스 유형. 데이터는 전부 graphql(xhr) 응답 후킹으로
# 받으므로 아래는 화면 그리기에만 쓰이고 우리는 쓰지 않는다 → 받을 이유가 없다.
# ⚠️ stylesheet는 절대 넣지 마라(2026-08-06 실측). CSS를 막으면 레이아웃이 안 잡혀
# 스크롤이 무한로딩을 못 깨우고, 같은 30스크롤에서 372건 → 12건으로 죽는다.
# 대역폭은 조금 줄지만 데이터가 통째로 날아가므로 순손실이다.
_BLOCKED_RESOURCES = ("image", "media", "font")
_SCROLL_PAUSE_MS = 2200
_CHANNEL_GAP_S = (15, 35)    # 채널 사이 랜덤 휴식
_BACKOFF_S = 30 * 60         # 로그인벽/차단 의심 시 대기
_BUSY_POLL_S = 60            # 렌더 양보 중 재확인 주기


def session_slots():
    """적립된 계정 세션 파일 목록(uid.json). 없으면 단일 세션으로 폴백.

    2026-08-05: 히트작은 채널당 400여 개를 다 긁어야 해서(최신 100개만으론
    조회수 상위 100개 중 0~5개밖에 안 걸린다 — 실측) 한 계정이 몇 시간 만에
    scraping_warning에 걸린다. 재로그인으로 세션을 새로 뽑으면 즉시 살아나므로,
    계정 여러 개를 적립해두고 막힐 때마다 넘긴다."""
    d = os.getenv("INSTAGRAM_SESSION_DIR", "")
    if d and os.path.isdir(d):
        slots = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".json"))
        if slots:
            return slots
    return [config.INSTAGRAM_SESSION_PATH] if config.INSTAGRAM_SESSION_PATH else []


def slot_proxy(index):
    """계정 슬롯 index에 고정 배정되는 한국 주거용 출구.

    2026-08-05: 계정만 바꾸고 IP가 같으면 인스타가 한 기계로 묶어 본다(새로 만든
    계정도 몇 시간 만에 scraping_warning). Webshare 회전주거용은 username에
    `-kr-N` 접미사를 붙이면 슬롯마다 다른 한국 가정회선으로 나간다(실측:
    kr-1 LG POWERCOMM, kr-3 SK브로드밴드 …). 계정↔IP를 1:1로 붙여 서로 다른
    사용자처럼 보이게 한다. 미설정이면 None(직결) — 기존 동작 유지."""
    user = os.getenv("WEBSHARE_USER", "")
    pw = os.getenv("WEBSHARE_PASS", "")
    if not user or not pw:
        return None
    host = os.getenv("WEBSHARE_HOST", "p.webshare.io:80")
    cc = os.getenv("WEBSHARE_COUNTRY", "kr")
    return f"http://{user}-{cc}-{index + 1}:{pw}@{host}"


def crawl_channel(username, max_scrolls=_MAX_SCROLLS, session_path=None, proxy=None):
    """채널 1개를 바닥(또는 상한)까지 스크롤 크롤. (items, final_url, error) 반환.

    instagram_playwright._scrape_one_playwright와 같은 캡처 방식(응답 후킹)에
    스크롤 루프만 얹었다. 발행시각은 shortcode에서 복원(REST 왕복 0)."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    url = f"https://www.instagram.com/{username}/reels/"
    seen = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled"])
            ctx_kw = {}
            sess = session_path or config.INSTAGRAM_SESSION_PATH
            if sess and os.path.exists(sess):
                ctx_kw["storage_state"] = sess
            # 세션과 프록시는 배타가 아니다 — 계정마다 전용 출구를 붙여야 IP로
            # 묶이지 않는다(2026-08-05). proxy 인자가 없을 때만 구 설정으로 폴백.
            p = proxy or config.INSTAGRAM_PROXY
            if p:
                rest = p.split("://", 1)[-1]
                if "@" in rest:
                    cred, hostport = rest.rsplit("@", 1)
                    user, _, pw = cred.partition(":")
                    ctx_kw["proxy"] = {"server": "http://" + hostport,
                                       "username": user, "password": pw}
                else:
                    ctx_kw["proxy"] = {"server": p}
            ctx = browser.new_context(**ctx_kw)
            Stealth().apply_stealth_sync(ctx)
            page = ctx.new_page()

            # 대역폭 절감(2026-08-06): 주거용 프록시는 GB 과금인데 채널당 87MB를
            # 쓰고 있었다(실측). 그중 이미지·폰트·CSS는 우리가 한 바이트도 안 쓴다
            # — 릴스 데이터는 전부 아래 _on_response의 graphql 후킹으로 들어온다.
            # 실측: 26.4MB → 13.7MB(-48%), 같은 스크롤 수에서 수집 건수 동일.
            # 인스타가 렌더를 막아 데이터가 안 나오는 날을 대비해 끌 수 있게 뒀다.
            if os.getenv("ARCHIVE_BLOCK_ASSETS", "1") != "0":
                def _route(route):
                    if route.request.resource_type in _BLOCKED_RESOURCES:
                        return route.abort()
                    return route.continue_()

                page.route("**/*", _route)

            def _on_response(resp):
                if "graphql" not in resp.url and "/api/v1/clips/user/" not in resp.url:
                    return
                try:
                    for n in extract_reel_nodes(resp.json()):
                        it = parse_reel_node(n, username)
                        if it and it["shortcode"] not in seen:
                            seen[it["shortcode"]] = it
                except Exception:   # noqa: BLE001 — 무관한 graphql 응답은 그냥 무시
                    pass

            page.on("response", _on_response)
            page.goto(url, timeout=config.INSTAGRAM_PW_TIMEOUT_MS,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            # 삭제·개명된 채널 감지(2026-08-05): 인스타가 에러 라우트를 렌더한다.
            # 이걸 error로 두면 pick_targets(팔로워순)가 매일 같은 죽은 대형 채널로
            # 40개 한도를 채워 진도가 영영 안 나간다 → "gone"으로 영구 제외.
            if "/accounts/scraping_warning" in page.url:
                ctx.close()
                browser.close()
                return [], page.url, "scraping_warning"
            _body = page.content()
            if ("페이지를 사용할 수 없습니다" in _body
                    or "Sorry, this page isn't available" in _body):
                ctx.close()
                browser.close()
                return [], url, "page_gone"
            stall = 0
            prev = len(seen)
            for _ in range(max_scrolls):
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(_SCROLL_PAUSE_MS)
                if len(seen) == prev:
                    stall += 1
                    if stall >= _STALL_LIMIT:
                        break          # 바닥
                else:
                    stall = 0
                prev = len(seen)
            final_url = page.url
            ctx.close()
            browser.close()
        items = []
        for it in seen.values():
            items.append({
                "shortcode": it["shortcode"], "url": it["url"],
                "thumbnail": it.get("displayUrl", ""),
                "views": it.get("videoViewCount") or 0,
                "likes": it.get("likesCount") or 0,
                "comments": it.get("commentsCount") or 0,
                "posted_at": shortcode_to_timestamp(it["shortcode"]) or "",
                # 채널 표시명(2026-08-06 사장님 "채널명 안 바뀐 것도 많다").
                # 이미 후킹해 받은 응답의 user.full_name — **추가 요청 0건**이다.
                # 노드마다 있기도 없기도 해서 빈 값이 섞인다 → 저장 쪽이 빈 값은 무시한다.
                "name": it.get("ownerFullName") or "",
            })
        return items, final_url, None
    except Exception as e:              # noqa: BLE001 — 채널 하나 실패로 전체가 죽지 않게
        return [], url, str(e)[:200]


def pick_targets(store):
    """(엑셀 ∪ 발굴등록 − 차단) − done − gone, 팔로워 내림차순 — 대형 채널부터."""
    removed = {(u or "").strip().lstrip("@").lower() for u in store.removed_usernames()}
    done = store.archive_done_usernames() | store.archive_gone_usernames()
    best = {}
    for c in list(load_channels()) + list(store.discovered_channels()):
        u = (c.get("username") or "").strip().lstrip("@")
        if not u or u.lower() in removed or u in done:
            continue
        f = c.get("followers") or 0
        if u not in best or f > best[u]:
            best[u] = f
    return [u for u, _ in sorted(best.items(), key=lambda x: -x[1])]


def run(limit=None, max_scrolls=_MAX_SCROLLS, sleep=time.sleep, log=print):
    store = Store(DB_PATH)
    targets = pick_targets(store)
    if limit:
        targets = targets[:limit]
    slots = session_slots()
    slot_i = 0
    log(f"[아카이브] 대상 {len(targets)}채널 (팔로워순, done 제외) · 계정 세션 {len(slots)}개")
    walls = 0
    ok = 0
    for idx, u in enumerate(targets, 1):
        while store.heavy_job_running():   # 사용하면서 수집 — 렌더에 양보
            log(f"[아카이브] 렌더 진행 중 → {_BUSY_POLL_S}s 대기")
            sleep(_BUSY_POLL_S)
        # 계정 로테이션: scraping_warning이 뜨면 그 계정은 태운 것 — 다음 세션으로
        # 넘겨 같은 채널을 재시도한다. 전 세션이 소진되면 회차를 끝낸다(재로그인 필요).
        while True:
            sess = slots[slot_i] if slot_i < len(slots) else None
            items, final_url, err = crawl_channel(u, max_scrolls=max_scrolls,
                                                  session_path=sess,
                                                  proxy=slot_proxy(slot_i))
            if err != "scraping_warning":
                break
            burnt = os.path.basename(sess or "?").replace(".json", "")
            slot_i += 1
            if slot_i >= len(slots):
                log(f"[아카이브] 계정 {burnt} 차단 — 남은 세션 없음, 회차 종료"
                    f" (재로그인 후 ig_session_capture.py로 갱신)")
                return ok
            log(f"[아카이브] 계정 {burnt} 차단 → 다음 계정으로 전환"
                f" ({slot_i + 1}/{len(slots)})")
            sleep(random.uniform(*_CHANNEL_GAP_S))
        now = datetime.now(timezone.utc).isoformat()
        if items:
            store.archive_upsert_many(u, items, now)
            store.archive_mark(u, "done", reels=len(items))
            walls = 0
            ok += 1
            log(f"[아카이브] {idx}/{len(targets)} @{u}: {len(items)}개 저장")
            # 비전태깅은 여기서 하지 않는다(2026-08-04 분리) — archive_tagger가 맡는다.
            #
            # 원래는 크롤 직후 채널당 500건을 태깅했다. 근거는 "썸네일이 CDN 만료토큰이라
            # 크롤 직후가 골든타임"이었는데, 실측해보니 만료는 **약 4일**이었다
            # (oe 파라미터 = hex 유닉스타임. 4.2h 지난 썸네일 40/40 다운로드 성공,
            #  oe를 과거로 조작하면 403 → 서명은 실제로 강제되지만 유효기간이 길다).
            # 4일이면 전 채널 크롤(약 3일)이 끝나고도 남는다.
            #
            # 붙여두면 채널당 34분(태깅 500건 × ~2.2s)이라 691채널에 16일이 걸렸고,
            # 그 사이 뒤쪽 채널은 아카이브에 아예 없었다. 게다가 큰 채널은 2,300개 중
            # 500개만 태깅되고 done으로 닫혀 나머지는 영영 안 붙었다.
            # 떼면 채널당 ~5.7분 → 3일이면 전 채널이 목록에 올라온다.
        elif err == "page_gone":
            store.archive_mark(u, "gone", note="페이지 없음(삭제/개명)")
            log(f"[아카이브] @{u} 페이지 없음 → gone(영구 제외)")
        elif "/accounts/login" in (final_url or ""):
            walls += 1
            store.archive_mark(u, "login_wall", note=final_url[:120])
            log(f"[아카이브] @{u} 로그인벽 — {_BACKOFF_S//60}분 백오프 ({walls}연속)")
            if walls >= 2:
                log("[아카이브] 로그인벽 2연속 → 이번 회차 중단(재실행 시 이어짐)")
                break
            sleep(_BACKOFF_S)
        else:
            store.archive_mark(u, "error", note=(err or "empty")[:120])
            log(f"[아카이브] @{u} 실패: {err or '결과 0'}")
        sleep(random.uniform(*_CHANNEL_GAP_S))
    log(f"[아카이브] 회차 종료 — 성공 {ok}채널")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-scrolls", type=int, default=_MAX_SCROLLS)
    a = ap.parse_args()
    run(limit=a.limit, max_scrolls=a.max_scrolls)


if __name__ == "__main__":
    main()
