"""해외HOT 발굴 백그라운드 잡 — discover_jobs 패턴 복제. 카테고리 시드팩을 순회하며
Reddit rising+top을 무료 수집 → build_reddit_items+apply_grades → 병합·로테이션 →
Store.save_overseas_feed. 단일 워커 전역상태로 진행폴링."""
import threading
import time
from datetime import datetime, timezone

from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts.overseas_seeds import load_seeds
from shopping_shorts import reddit_source
from shopping_shorts.ranking import build_reddit_items, apply_grades, sort_by

_LOCK = threading.Lock()
_JOB = {"status": "idle", "phase": "", "count": 0, "error": None, "started": 0.0}
_CAP = 120        # 피드 최대 유지 개수(로테이션)
_REQ_PAUSE = 2.0  # Reddit RSS 요청 간격 — 연타 시 429(실측)라 매 요청 사이 쉰다


def _now():
    return datetime.now(timezone.utc)


def _merge_rotate(prev, new, cap):
    """post_id(shortcode) 단위 병합 — 새 데이터가 이기고(최신 지표), 겹치지 않는
    이전 항목은 유지. 병합 후 score 내림차순 상위 cap개만(성과 낮은 것 자연 탈락).

    new 내부도 shortcode로 dedup한다 — 같은 서브레딧이 여러 카테고리 시드에 겹치면
    (예: BuyItForLife ∈ 살림·가전) 같은 포스트가 카테고리별로 중복 수집되므로,
    shortcode당 score 최고 1개만 남긴다.

    discovery.merge_feeds는 username(=서브레딧)으로 병합해 서브레딧당 1행으로
    붕괴하므로 재사용 불가 — 발굴은 포스트 단위여야 한다."""
    best = {}
    for i in new:
        sc = i.get("shortcode")
        if sc not in best or (i.get("score") or 0) > (best[sc].get("score") or 0):
            best[sc] = i
    new_keys = set(best)
    out = list(best.values()) + [i for i in prev if i.get("shortcode") not in new_keys]
    return sorted(out, key=lambda i: i.get("score") or 0, reverse=True)[:cap]


def _collect_category(cat, cfg, store):
    raw = []
    for sub in cfg.get("subreddits", []):
        raw += reddit_source.fetch_subreddit(sub, category=cat, sort="rising")
        time.sleep(_REQ_PAUSE)   # 429 완화 — 매 요청 사이 간격
        raw += reddit_source.fetch_subreddit(sub, category=cat, sort="top")
        time.sleep(_REQ_PAUSE)
    # 같은 post_id 중복 제거(rising+top 겹침)
    seen, uniq = set(), []
    for r in raw:
        if r["post_id"] in seen:
            continue
        seen.add(r["post_id"])
        uniq.append(r)
    items = build_reddit_items(
        uniq,
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
        merged = _merge_rotate(prev, all_items, cap=_CAP)
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


def start():
    with _LOCK:
        if _JOB["status"] == "running" and time.time() - _JOB["started"] < 600:
            return {"status": "running", "elapsed": int(time.time() - _JOB["started"])}
        _JOB.update(status="running", phase="시작", count=0, error=None, started=time.time())
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "running", "elapsed": 0}


def status():
    with _LOCK:
        return {"status": _JOB["status"], "phase": _JOB["phase"], "count": _JOB["count"],
                "error": _JOB["error"],
                "elapsed": int(time.time() - _JOB["started"]) if _JOB["started"] else 0}
