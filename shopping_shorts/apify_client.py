"""Apify Instagram Reel Scraper HTTP 클라이언트."""
import json
import time
import requests
from pathlib import Path
from shopping_shorts.config import APIFY_TOKENS, APIFY_ACTOR, RESULTS_PER_CHANNEL, ONLY_NEWER_THAN

# run-sync-get-dataset-items는 Apify 서버측 자체 타임아웃(약 5분)이 있어
# 채널이 많으면(443개) 끝나기 전에 408로 끊긴다(2026-07-09 실측). 시작만
# 비동기로 걸고 완료까지 폴링하는 방식으로 전환 — 서버측 시간 제한이 없다.
_RUNS_URL = "https://api.apify.com/v2/acts/{actor}/runs"
_RUN_STATUS_URL = "https://api.apify.com/v2/actor-runs/{run_id}"
_DATASET_ITEMS_URL = "https://api.apify.com/v2/datasets/{dataset_id}/items"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}

# 계정 하나가 사용량 소진(402)되면 다음 계정으로 자동 로테이션(2026-07-09).
# 마지막으로 성공한 토큰의 인덱스를 저장해 다음 호출부터 그 지점에서 시작
# (매번 소진된 앞 계정부터 다시 두드리지 않음).
_KEY_STATE_PATH = Path(__file__).parent / "data" / "apify_key_index.json"
_EXHAUSTED_STATUSES = {401, 402, 429}


def _load_key_index() -> int:
    try:
        return json.loads(_KEY_STATE_PATH.read_text(encoding="utf-8")).get("index", 0)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def _save_key_index(index: int) -> None:
    _KEY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEY_STATE_PATH.write_text(json.dumps({"index": index}), encoding="utf-8")


def _start_run(token, payload, actor=APIFY_ACTOR):
    """지정 토큰·액터로 run 시작. 사용량 소진(401/402/429)이면 None 반환(호출부가
    다음 토큰 시도). actor 기본값은 인스타 릴스 스크래퍼(기존 동작 유지) —
    다른 플랫폼 스크래퍼(예: 틱톡)는 호출부가 명시적으로 지정한다(2026-07-09)."""
    headers = {"Authorization": f"Bearer {token}"}
    run = requests.post(
        _RUNS_URL.format(actor=actor), headers=headers, json=payload, timeout=60
    )
    if run.status_code in _EXHAUSTED_STATUSES:
        return None
    run.raise_for_status()
    return headers, run.json()["data"]


def _run_to_completion(headers, run_data, timeout, poll_interval):
    """폴링으로 run 완료까지 대기 → 데이터셋 아이템 반환.
    실행 도중 실패(FAILED/ABORTED/TIMED-OUT)도 사용량 소진과 동일하게 취급해
    호출부가 다음 토큰으로 전체 재시도할 수 있게 RuntimeError를 던진다."""
    run_id = run_data["id"]
    deadline = time.monotonic() + timeout
    status = run_data["status"]
    while status not in _TERMINAL_STATUSES:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Apify run {run_id} 시간초과({timeout}s, 마지막 상태={status})")
        time.sleep(poll_interval)
        poll = requests.get(_RUN_STATUS_URL.format(run_id=run_id), headers=headers, timeout=30)
        poll.raise_for_status()
        run_data = poll.json()["data"]
        status = run_data["status"]

    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify run {run_id} 실패(status={status})")

    dataset_id = run_data["defaultDatasetId"]
    items = requests.get(
        _DATASET_ITEMS_URL.format(dataset_id=dataset_id), headers=headers, timeout=60
    )
    items.raise_for_status()
    return items.json()  # list of reel dicts


# 채널 하나의 run에 유저네임을 너무 많이(443개) 넣으면 액터가 인스타그램 자체
# 차단으로 추정되는 지점(실측: ~124번째 채널)에서 나머지를 아예 시도조차 안 하고
# 조용히 SUCCEEDED로 끝내버린다(2026-07-09 실측 — 443개 중 26개만 결과에 나타남,
# 에러조차 없이 나머지 316개가 그냥 누락됨). 30개 단위 테스트는 항상 전체가
# 정상 처리됐던 것에 근거해 여유있게 청크로 나눠 순차 호출한다.
CHUNK_SIZE = 40


def _run_with_rotation(payload, tokens, timeout, poll_interval, actor=APIFY_ACTOR):
    """지정 payload로 run 시작 → 토큰 로테이션 포함 완료까지 실행.
    fetch_reels(채널 목록)와 fetch_single_reel(단일 URL) 둘 다 이 공통
    로테이션 루프를 재사용한다(2026-07-09). actor를 다르게 지정하면 인스타
    외 다른 플랫폼 스크래퍼(예: tiktok_search.py)도 같은 토큰 풀·로테이션
    로직을 그대로 재사용할 수 있다."""
    start = _load_key_index() % len(tokens)
    last_err = None
    for offset in range(len(tokens)):
        idx = (start + offset) % len(tokens)
        current_token = tokens[idx]
        try:
            started = _start_run(current_token, payload, actor=actor)
            if started is None:
                last_err = requests.HTTPError(
                    f"apify 계정 {idx+1}/{len(tokens)} 사용량 소진/거부(시작 거부)"
                )
                continue
            headers, run_data = started
            items = _run_to_completion(headers, run_data, timeout, poll_interval)
            if idx != start:
                _save_key_index(idx)
            return items
        except (requests.RequestException, RuntimeError, TimeoutError) as e:
            last_err = e
            continue
    raise RuntimeError(f"apify 토큰 {len(tokens)}개 전부 실패(마지막 오류: {last_err})")


def fetch_reels(usernames, token=None, results_per_channel=RESULTS_PER_CHANNEL,
                only_newer_than=ONLY_NEWER_THAN, timeout=900, poll_interval=5,
                chunk_size=CHUNK_SIZE):
    """usernames 리스트 → reel dict 리스트. Apify가 채널별 최신 N개(48h 여유) 반환.

    usernames를 chunk_size 단위로 나눠 별도 run으로 순차 처리한다(액터의 대량
    입력 조용한 부분처리 회피, 2026-07-09). 청크별로 비동기 run 시작 → 완료까지
    폴링 → 데이터셋 조회 (동기 엔드포인트의 서버측 타임아웃 회피). token 미지정
    시 계정 풀(APIFY_TOKENS)을 순환하며, 시작 시점 거부(401/402/429)뿐 아니라
    실행 도중 계정이 소진돼 run 자체가 실패한 경우도 다음 계정으로 그 청크를
    이어서 재시도한다."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("APIFY_TOKEN 미설정 (환경변수 APIFY_TOKEN)")
    payload_extra = {
        "resultsLimit": results_per_channel,
        "onlyPostsNewerThan": only_newer_than,
        "skipPinnedPosts": True,
    }

    all_items = []
    for i in range(0, len(usernames), chunk_size):
        chunk = usernames[i:i + chunk_size]
        payload = {"username": chunk, **payload_extra}
        all_items.extend(_run_with_rotation(payload, tokens, timeout, poll_interval))
    return all_items


_PROFILE_ACTOR = "apify~instagram-profile-scraper"


def fetch_profiles(usernames, token=None, timeout=300, poll_interval=5):
    """usernames 리스트 → {username_소문자: {followers, posts, full_name}} (2026-07-12).

    릴스 스크래퍼엔 팔로워 정보가 없어(실측) 발굴 채널의 구독자수·참여밀도를
    채우려면 프로필 액터를 따로 호출한다. 여러 username을 한 run에 넣어 1회로
    끝낸다(발굴 채널은 보통 ≤40개). 토큰 로테이션은 공통 로직 재사용."""
    if not usernames:
        return {}
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("APIFY_TOKEN 미설정")
    items = _run_with_rotation({"usernames": list(usernames)}, tokens,
                               timeout, poll_interval, actor=_PROFILE_ACTOR)
    out = {}
    for it in items:
        u = it.get("username")
        if not u:
            continue
        out[u.lower()] = {
            "followers": int(it.get("followersCount") or 0),
            "posts": int(it.get("postsCount") or 0),
            "full_name": it.get("fullName") or "",
        }
    return out


def fetch_single_reel(url, token=None, timeout=180, poll_interval=5):
    """추적 채널 목록에 없는 임의의 인스타 릴스 URL 하나를 즉시 조회(2026-07-09,
    제품찾기에서 "우리 목록에 없는 영상"도 분석할 수 있게 추가). "username"
    필드 하나로 유저네임과 직접 릴스 URL을 둘 다 받는다 — 청크 분할
    불필요(항목 1개), 토큰 로테이션은 fetch_reels와 동일 로직 재사용.
    결과 없으면(비공개 계정·삭제된 게시물 등) None.

    2026-07-10: 액터가 이날 새 빌드(0.0.468)로 "directUrls" 필드를 완전히
    없애고 "username" 필드 하나로 통합했음(실측: directUrls로 호출하면
    모든 계정에서 균일하게 400 "input.username is required" — 특정 URL이나
    토큰 문제가 아니라 액터 자체의 스키마 변경이었음). "username" 필드는
    유저네임/프로필URL/ID/릴스URL을 전부 받는다고 액터 설명에 명시됨."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("APIFY_TOKEN 미설정 (환경변수 APIFY_TOKEN)")
    payload = {
        "username": [url],
        "resultsLimit": 1,
        "skipPinnedPosts": True,
    }
    items = _run_with_rotation(payload, tokens, timeout, poll_interval)
    return items[0] if items else None
