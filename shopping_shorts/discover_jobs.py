"""발굴 '업데이트'를 백그라운드 스레드로 실행 + 진행상황 폴링(2026-07-12).

업데이트는 검색 6 + 릴스수집 + 프로필을 돌려 수 분 걸린다(경로에 따라
Apify 또는 무료 Playwright, 2026-07-30 config.INSTAGRAM_SCRAPER로 분기 —
릴스수집과 동일 킬스위치를 공유해 한 군데서 apify↔playwright 전환).
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
from shopping_shorts import config
from shopping_shorts.apify_client import fetch_reels as _apify_fetch_reels
from shopping_shorts.apify_client import fetch_profiles as _apify_fetch_profiles
from shopping_shorts import instagram_playwright
from shopping_shorts import discovery, instagram_search

# 발굴 입구 = 이 해시태그 목록이 전부다. 6개일 때 픽업이 21곳밖에 안 나온 게
# 발단(2026-07-30) — 태그당 SERP 24건 → known 제외 → 최근 릴스 필터를 거치면
# 태그 하나가 실제로 남기는 신규 채널은 서너 곳뿐이라, 입구를 넓히는 게 가장
# 직접적인 레버다. 20개로 확장(사장님 지시). ⚠️playwright 경로는 태그를 순차로
# 도므로(자원경합 회피, search_workers=1) 소요시간이 태그 수에 비례한다.
CATEGORIES = [
    "#주방템", "#살림템", "#인테리어", "#자취템", "#생활꿀템", "#뷰티템",
    "#자취요리", "#원룸인테리어", "#주방살림", "#청소템", "#정리수납", "#수납템",
    "#가성비템", "#쿠팡추천", "#쿠팡템", "#다이소추천", "#다이소템",
    "#육아템", "#캠핑템", "#반려견용품",
]

# 누적 모드에서 채널을 며칠간 보존할지(마지막으로 발굴에 잡힌 시점 기준).
# 3일간 한 번도 다시 안 잡힌 채널은 피드에서 빠진다(2026-07-30 사장님 지시).
FEED_TTL_DAYS = 3


def _search_fn():
    """검색 경로 선택 — config.INSTAGRAM_SCRAPER를 따른다(릴스수집과 동일 킬스위치).
    playwright(기본, 무료 해시태그 탐색) / apify(유료 키워드검색)."""
    if config.INSTAGRAM_SCRAPER == "playwright":
        return instagram_playwright.search_channels
    return instagram_search.search_channels


def _fetch_reels_fn(usernames, per, days):
    if config.INSTAGRAM_SCRAPER == "playwright":
        return instagram_playwright.fetch_reels(usernames)
    return _apify_fetch_reels(usernames, results_per_channel=per, only_newer_than=f"{days} days")


def _profiles_fn():
    if config.INSTAGRAM_SCRAPER == "playwright":
        return instagram_playwright.fetch_profiles
    return _apify_fetch_profiles

_LOCK = threading.Lock()
_JOB = {"status": "idle", "phase": "", "count": 0, "items": [],
        "error": None, "started": 0.0, "registered": 0}


def _known_usernames(store):
    known = {d["username"] for d in store.discovered_channels()}
    try:
        known |= {c["username"] for c in load_channels()}
    except Exception:
        pass
    # 🚫 영구차단(2026-07-30): 차단 채널은 '이미 아는 채널'로 취급해 재발굴을 막는다.
    # 차단만 하고 목록추가는 안 한 채널은 discovered에도 엑셀에도 없어서, 이게 없으면
    # 다음 업데이트에 다시 올라온다.
    known |= store.removed_usernames()
    return known


def _parallel_fetch(usernames, per, days, chunk=40, workers=3):
    """채널 릴스 수집을 40개씩 병렬 청크로 — 순차(청크마다 Apify run 대기)보다 빠름.
    playwright 경로는 세션 하나를 여러 스레드가 동시에 열면 충돌 위험이 있어(브라우저
    프로세스 자원 경합) 청크 병렬 없이 그대로 한 번에 돈다(2026-07-30)."""
    if config.INSTAGRAM_SCRAPER == "playwright":
        return _fetch_reels_fn(usernames, per, days)
    chunks = [usernames[i:i + chunk] for i in range(0, len(usernames), chunk)] or [[]]
    if len(chunks) == 1:
        return _fetch_reels_fn(chunks[0], per, days)
    out = []
    with ThreadPoolExecutor(max_workers=min(workers, len(chunks))) as pool:
        for res in pool.map(lambda c: _fetch_reels_fn(c, per, days), chunks):
            out.extend(res)
    return out


def _run(days, max_total, accumulate, auto_register=False):
    store = Store(DB_PATH)
    per = 12 if max_total <= 40 else 18
    try:
        _JOB["phase"] = "검색"
        # playwright 경로는 검색도 로컬 브라우저라 병렬 시 자원경합으로 일부 태그가
        # 조용히 0건 남(2026-07-30 실측) — 순차(1)로 강제. apify는 기존처럼 병렬(6).
        search_workers = 1 if config.INSTAGRAM_SCRAPER == "playwright" else 6
        items = discovery.discover_multi(
            CATEGORIES, known=_known_usernames(store),
            search_fn=_search_fn(),
            fetch_reels_fn=lambda us: _parallel_fetch(us, per, days),
            profiles_fn=_profiles_fn(),
            prev_comments=store.prev_comments, prev_delta=store.prev_delta,
            window_hours=days * 24, max_channels_per=per, max_total=max_total,
            search_workers=search_workers,
        )
        if accumulate:
            prev, _ = store.load_discovery_feed()
            # 누적 상한 = max_total × 보존일수(2026-07-30). 예전엔 cap=max_total이라
            # "3일 보존"을 켜도 하루치 정원을 넘는 순간 어제 채널이 댓글수에 밀려
            # 즉시 잘려나가 보존이 무의미했다. 이제 하루치 정원 × 3일만큼 자리를
            # 주고, 그 안에서 (1) 3일 지난 채널은 TTL로 (2) 자리가 모자라면 댓글수
            # 낮은 순으로 빠진다.
            items = discovery.merge_feeds(prev, items,
                                          cap=max_total * FEED_TTL_DAYS,
                                          ttl_days=FEED_TTL_DAYS)
        store.save_discovery_feed(items)
        store.save_run(
            time.strftime("%Y-%m-%d %H:%M"),
            [{"shortcode": i["shortcode"], "username": i["username"],
              "comments": i["comments"], "delta": i["delta"]} for i in items],
        )
        registered = 0
        if auto_register:
            # 발굴 전부를 자동으로 레퍼런스 추적목록에 등록(2026-07-30) — 사람이
            # "목록추가"를 안 눌러도 다음 레퍼런스랭킹 수집(09시)부터 바로 잡히게.
            # discover()가 이미 known(기존 추적목록) 제외 후 검색한 결과라 전부 신규다.
            for it in items:
                uname = it.get("username")
                if uname:
                    store.add_discovered(uname, name=it.get("name") or uname)
                    registered += 1
        with _LOCK:
            _JOB.update(status="done", phase="완료", count=len(items), items=items,
                       error=None, registered=registered)
    except Exception as e:
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        with _LOCK:
            _JOB.update(status="error", phase="", error=msg)


def start(days, max_total, accumulate, auto_register=False):
    """업데이트 시작. 이미 실행 중이면 그 상태 반환(중복 방지)."""
    with _LOCK:
        if _JOB["status"] == "running" and time.time() - _JOB["started"] < 600:
            return {"status": "running", "elapsed": int(time.time() - _JOB["started"])}
        _JOB.update(status="running", phase="시작", count=0, items=[],
                    error=None, started=time.time(), registered=0)
    threading.Thread(target=_run, args=(days, max_total, accumulate, auto_register),
                     daemon=True).start()
    return {"status": "running", "elapsed": 0}


def status(include_items=True):
    with _LOCK:
        s = {"status": _JOB["status"], "phase": _JOB["phase"], "count": _JOB["count"],
             "error": _JOB["error"], "registered": _JOB.get("registered", 0),
             "elapsed": int(time.time() - _JOB["started"]) if _JOB["started"] else 0}
        if include_items and _JOB["status"] == "done":
            s["items"] = _JOB["items"]
    return s
