"""해외HOT 발굴 백그라운드 잡 — discover_jobs 패턴 복제. 카테고리 시드팩을 순회하며
Reddit rising+top을 무료 수집 → build_reddit_items+apply_grades → 병합·로테이션 →
Store.save_overseas_feed. 단일 워커 전역상태로 진행폴링."""
import threading
import time
from datetime import datetime, timezone

from shopping_shorts import config
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts.overseas_seeds import load_seeds
from shopping_shorts import tiktok_search, douyin_search, xiaohongshu_search, playwright_crawl
from shopping_shorts import gap_check, overseas_funnel, video_analysis
from shopping_shorts.ranking import build_overseas_items, apply_grades, sort_by

_LOCK = threading.Lock()
_JOB = {"status": "idle", "phase": "", "count": 0, "error": None, "started": 0.0}
_CAP = 120          # 피드 최대 유지 개수(로테이션)
_PER_KEYWORD = 40   # 카테고리·플랫폼·키워드당 수집 상한(=과금단위)
_REQ_PAUSE = 0.5    # Apify 호출 간 간격
_GAP_CAP = 40       # 선점검색 배치당 상한(유튜브 무료쿼터 보호) — 생존자 상위만
PICKUP_CATEGORY = "🖐 픽업"   # 무료크롤+판단으로 고른 걸 수동 URL로 픽업하는 카테고리


def _now():
    return datetime.now(timezone.utc)


def _merge_rotate(prev, new, cap):
    """post_id(shortcode) 단위 병합 — 새 데이터가 이기고(최신 지표), 겹치지 않는
    이전 항목은 유지. 병합 후 자막등급 우선, 같은 등급 내 score 내림차순 상위 cap개만(성과 낮은 것 자연 탈락).

    new 내부도 shortcode로 dedup한다 — 같은 서브레딧이 여러 카테고리 시드에 겹치면
    (예: BuyItForLife ∈ 살림·가전) 같은 포스트가 카테고리별로 중복 수집되므로,
    shortcode당 score 최고 1개만 남긴다.

    discovery.merge_feeds는 username(=서브레딧)으로 병합해 서브레딧당 1행으로
    붕괴하므로 재사용 불가 — 발굴은 포스트 단위여야 한다.

    정렬은 1차 자막등급(자막 없는 것이 앞), 2차 score 내림차순이다(2026-07-29).
    상한 cap으로 자를 때도 같은 기준이라 자막 없는 항목이 우선 살아남는다."""
    best = {}
    for i in new:
        sc = i.get("shortcode")
        if sc not in best or (i.get("score") or 0) > (best[sc].get("score") or 0):
            best[sc] = i
    new_keys = set(best)
    out = list(best.values()) + [i for i in prev if i.get("shortcode") not in new_keys]
    return sorted(out, key=lambda i: (overseas_funnel.caption_rank(i),
                                      -(i.get("score") or 0)))[:cap]


def _annotate_text_level(items, store):
    """생존자 **전부**의 썸네일을 봐서 text_level(자막 오버레이 정도)을 매긴다.

    2026-07-29 변경: 예전엔 앞 cap(=15)개만 봤는데, 이 시점의 items는 아직
    score가 없어(build_overseas_items 전) '상위'가 아니라 그냥 수집순 앞 15개였다.
    판정 안 된 항목은 자막 여부를 모르니 정렬에서 줄을 세울 수 없어 상한을 없앴다.
    대신 shortcode 캐시로 재판정을 막아 Gemini 쿼터를 지킨다 — 피드는 _merge_rotate로
    유지되므로 매 수집에서 새로 들어온 것만 실제로 비전을 탄다.

    판정 실패·썸네일 없음은 text_level을 안 붙이고 캐시에도 안 남긴다
    (overseas_funnel.passes_caption_clutter가 통과시켜 과필터를 막고, 다음 수집에서 재시도)."""
    judged = cached = 0
    for it in items:
        # 이 시점의 it는 크롤러 raw dict 그대로다(build_overseas_items 전) —
        # crawler는 "shortcode"가 아니라 "video_id" 키로 넣는다(playwright_crawl.py 등).
        # shortcode는 나중에 ranking.build_overseas_items가 video_id로부터 만든다.
        # 여기서 shortcode만 보면 항상 None이라 캐시가 100% 미스한다(2026-07-29 Critical 1).
        sc = it.get("shortcode") or it.get("video_id")
        hit = store.get_thumb_text_level(sc) if sc else None
        if hit:
            it["text_level"] = hit
            cached += 1
            continue
        img = video_analysis.fetch_thumb_bytes(it.get("thumbnail"))
        if not img:
            continue
        level = video_analysis.text_level_vision(img).get("text_level")
        if level:
            it["text_level"] = level
            judged += 1
            if sc:
                store.save_thumb_text_level(sc, level)
    # 카테고리마다 호출되므로 "수집" 단계 표시를 지우지 않고 판정 카운트만 갱신한다
    # (예전엔 phase="자막판정..."으로 통째로 덮어써 락도 없고 마지막 카테고리 값만 남았다).
    with _LOCK:
        _JOB["phase"] = f"수집·자막판정 신규{judged}·캐시{cached}"
    return items


def _collect_category(cat, cfg, store):
    allow = list(cfg.get("tiktok", [])) + list(cfg.get("cn", []))
    raw = []
    if config.OVERSEAS_TIKTOK_ENABLED:
        for kw in cfg.get("tiktok", []):
            raw += tiktok_search.search_full(kw, max_results=_PER_KEYWORD)
            time.sleep(_REQ_PAUSE)
    for kw in cfg.get("cn", []):
        if config.OVERSEAS_DOUYIN_ENABLED:
            raw += douyin_search.search_full(kw, max_results=_PER_KEYWORD)
            time.sleep(_REQ_PAUSE)
        if config.XHS_SCRAPER == "playwright":
            raw += playwright_crawl.search_full(kw, max_results=_PER_KEYWORD)
        else:
            raw += xiaohongshu_search.search_full(kw, max_results=_PER_KEYWORD)
        time.sleep(_REQ_PAUSE)
    # STAGE 1·2·상한: 형식·관련성·안터진
    kept = [r for r in raw
            if overseas_funnel.passes_format(r)
            and overseas_funnel.passes_shortform(r)
            and overseas_funnel.passes_relevance(r, allow)
            and overseas_funnel.under_view_ceiling(r)]
    # STAGE 3: 자막(텍스트 오버레이) 판정 — 생존자 전부를 보고(캐시로 증분), 자막 과다는 컷
    kept = _annotate_text_level(kept, store)
    kept = [r for r in kept if overseas_funnel.passes_caption_clutter(r)]
    for r in kept:
        r["category"] = cat   # 시드 카테고리 고정
    items = build_overseas_items(
        kept,
        prev_base=lambda sc: store.prev_base_platform("overseas", sc),
        prev_delta=lambda sc: store.prev_delta_platform("overseas", sc),
        now=_now(),
    )
    return apply_grades(items)


def _run():
    store = Store(DB_PATH)
    try:
        with _LOCK:
            _JOB["phase"] = "수집"
        all_items = []
        for cat, cfg in load_seeds().items():
            all_items += _collect_category(cat, cfg, store)
        all_items = sort_by(all_items, "속도")
        prev, _ = store.load_overseas_feed()
        # 현재 시드에 없는 카테고리(폐기된 레딧 만족감/신기템 등)는 퇴출 — 소스·카테고리
        # 개편 시 옛 데이터가 피드에 눌러앉아 잡탕이 되는 걸 막는다(셀프힐링).
        valid_cats = set(load_seeds().keys()) | {PICKUP_CATEGORY}
        prev = [i for i in prev if i.get("category") in valid_cats]
        merged = _merge_rotate(prev, all_items, cap=_CAP)
        # 선점뱃지 — 아직 미판정인 상위 항목만(쿼터 보호). 기존 뱃지는 유지.
        with _LOCK:
            _JOB["phase"] = "선점확인"
        checked = 0
        for it in merged:
            if it.get("gap_badge"):
                continue
            if checked >= _GAP_CAP:
                break
            is_cn = it.get("platform") in ("douyin", "xiaohongshu")
            it["gap_badge"] = gap_check.gap_badge(
                it.get("caption") or it.get("title") or "", translate=is_cn)
            checked += 1
        store.save_overseas_feed(merged)
        store.save_run_platform(
            "overseas", _now().strftime("%Y-%m-%d %H:%M"),
            [{"shortcode": i["shortcode"], "base": i["base_count"], "delta": i["delta"]} for i in all_items],
        )
        with _LOCK:
            _JOB.update(status="done", phase="완료", count=len(merged), error=None)
    except Exception as e:
        with _LOCK:
            _JOB.update(status="error", phase="", error=str(e))


# 진행 중 재실행 방지 창. 익명 RSS 429 백오프가 켜지면 _run이 배치당 수십 분까지
# 길어질 수 있어(실측 2026-07-25: 6서브 5.5분·재시도 다수) 겹치면 Reddit 부하가 배가된다.
# stale 판정을 30분으로 늘려 정상적으로 긴 실행이 중복 트리거되지 않게 한다.
_RUN_STALE_SEC = 1800


def start():
    with _LOCK:
        if _JOB["status"] == "running" and time.time() - _JOB["started"] < _RUN_STALE_SEC:
            return {"status": "running", "elapsed": int(time.time() - _JOB["started"])}
        _JOB.update(status="running", phase="시작", count=0, error=None, started=time.time())
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "running", "elapsed": 0}


def status():
    with _LOCK:
        return {"status": _JOB["status"], "phase": _JOB["phase"], "count": _JOB["count"],
                "error": _JOB["error"],
                "elapsed": int(time.time() - _JOB["started"]) if _JOB["started"] else 0}


def add_pickup(urls):
    """무료크롤로 고른 틱톡 URL들을 Apify로 풀데이터 픽업 → '픽업' 카테고리로 피드에 병합·저장.

    수동 선택이라 신선도 창(14일)에 안 걸리게 window를 크게 두고, 픽업은 랭킹 점수로
    밀려나지 않게 cap을 넉넉히 준다. 반환: 실제 추가된 건수."""
    store = Store(DB_PATH)
    raw = tiktok_search.fetch_urls(urls)
    for r in raw:
        r["category"] = PICKUP_CATEGORY
    items = build_overseas_items(
        raw,
        prev_base=lambda sc: store.prev_base_platform("overseas", sc),
        prev_delta=lambda sc: store.prev_delta_platform("overseas", sc),
        now=_now(),
        window_hours=24 * 3650,   # 수동 픽업은 오래된 것도 허용(신선도 필터 우회)
    )
    items = apply_grades(items)
    for it in items:
        it["gap_badge"] = gap_check.gap_badge(it.get("caption") or it.get("title") or "")
    prev, _ = store.load_overseas_feed()
    valid_cats = set(load_seeds().keys()) | {PICKUP_CATEGORY}
    prev = [i for i in prev if i.get("category") in valid_cats]
    merged = _merge_rotate(prev, items, cap=_CAP + len(items))
    store.save_overseas_feed(merged)
    return len(items)
