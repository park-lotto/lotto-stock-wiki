"""발굴 '업데이트'를 백그라운드 스레드로 실행 + 진행상황 폴링(2026-07-12).

업데이트는 Apify를 여러 번(검색 6 + 릴스수집 + 프로필) 돌려 수 분 걸린다.
동기로 처리하면 (1) 프론트가 몇 분 멈춘 것처럼 보이고 (2) 그 사이 서버가
재시작되면 HTTP 응답 자체가 HTML 에러로 깨진다. 그래서 시작만 걸고(job)
프론트가 상태를 폴링하게 한다. 단일 워커(uvicorn 기본) 기준 모듈 전역
상태로 충분하다 — 프로세스가 죽으면(배포 재시작) 상태가 idle로 리셋되고
프론트는 '중단됨'으로 처리한다."""
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts.channels import load_channels
from shopping_shorts.apify_client import fetch_reels, fetch_profiles
from shopping_shorts import discovery, instagram_search

CATEGORIES = ["#주방템", "#살림템", "#인테리어", "#자취템", "#생활꿀템", "#뷰티템"]

_LOCK = threading.Lock()
_JOB = {"status": "idle", "phase": "", "count": 0, "items": [],
        "error": None, "started": 0.0}


def _known_usernames(store):
    known = {d["username"] for d in store.discovered_channels()}
    try:
        known |= {c["username"] for c in load_channels()}
    except Exception:
        pass
    return known


def _parallel_fetch(usernames, per, days, chunk=40, workers=3):
    """채널 릴스 수집을 40개씩 병렬 청크로 — 순차(청크마다 Apify run 대기)보다 빠름."""
    chunks = [usernames[i:i + chunk] for i in range(0, len(usernames), chunk)] or [[]]
    if len(chunks) == 1:
        return fetch_reels(chunks[0], results_per_channel=per, only_newer_than=f"{days} days")
    out = []
    with ThreadPoolExecutor(max_workers=min(workers, len(chunks))) as pool:
        for res in pool.map(
            lambda c: fetch_reels(c, results_per_channel=per, only_newer_than=f"{days} days"),
            chunks,
        ):
            out.extend(res)
    return out


def _run(days, max_total, accumulate):
    store = Store(DB_PATH)
    per = 12 if max_total <= 40 else 18
    try:
        _JOB["phase"] = "검색"
        items = discovery.discover_multi(
            CATEGORIES, known=_known_usernames(store),
            search_fn=instagram_search.search_channels,
            fetch_reels_fn=lambda us: _parallel_fetch(us, per, days),
            profiles_fn=fetch_profiles,
            prev_comments=store.prev_comments, prev_delta=store.prev_delta,
            window_hours=days * 24, max_channels_per=per, max_total=max_total,
        )
        if accumulate:
            prev, _ = store.load_discovery_feed()
            items = discovery.merge_feeds(prev, items)
        store.save_discovery_feed(items)
        store.save_run(
            time.strftime("%Y-%m-%d %H:%M"),
            [{"shortcode": i["shortcode"], "username": i["username"],
              "comments": i["comments"], "delta": i["delta"]} for i in items],
        )
        with _LOCK:
            _JOB.update(status="done", phase="완료", count=len(items), items=items, error=None)
    except Exception as e:
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        with _LOCK:
            _JOB.update(status="error", phase="", error=msg)


def start(days, max_total, accumulate):
    """업데이트 시작. 이미 실행 중이면 그 상태 반환(중복 방지)."""
    with _LOCK:
        if _JOB["status"] == "running" and time.time() - _JOB["started"] < 600:
            return {"status": "running", "elapsed": int(time.time() - _JOB["started"])}
        _JOB.update(status="running", phase="시작", count=0, items=[],
                    error=None, started=time.time())
    threading.Thread(target=_run, args=(days, max_total, accumulate), daemon=True).start()
    return {"status": "running", "elapsed": 0}


def status(include_items=True):
    with _LOCK:
        s = {"status": _JOB["status"], "phase": _JOB["phase"], "count": _JOB["count"],
             "error": _JOB["error"], "elapsed": int(time.time() - _JOB["started"]) if _JOB["started"] else 0}
        if include_items and _JOB["status"] == "done":
            s["items"] = _JOB["items"]
    return s
