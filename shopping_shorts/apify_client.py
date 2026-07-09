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


def _start_run(payload, tokens):
    """토큰 풀을 순환하며 run 시작 시도. 사용량 소진(401/402/429)이면 다음 토큰.
    성공한 토큰과 그 인덱스를 반환(폴링·데이터셋 조회에 같은 토큰 재사용)."""
    start = _load_key_index() % len(tokens)
    last_err = None
    for offset in range(len(tokens)):
        idx = (start + offset) % len(tokens)
        token = tokens[idx]
        headers = {"Authorization": f"Bearer {token}"}
        try:
            run = requests.post(
                _RUNS_URL.format(actor=APIFY_ACTOR), headers=headers, json=payload, timeout=60
            )
            if run.status_code in _EXHAUSTED_STATUSES:
                last_err = requests.HTTPError(
                    f"apify 계정 {idx+1}/{len(tokens)} 사용량 소진/거부(status={run.status_code})"
                )
                continue
            run.raise_for_status()
            if idx != start:
                _save_key_index(idx)
            return token, headers, run.json()["data"]
        except requests.RequestException as e:
            last_err = e
    raise RuntimeError(f"apify 토큰 {len(tokens)}개 전부 사용 불가: {last_err}")


def fetch_reels(usernames, token=None, results_per_channel=RESULTS_PER_CHANNEL,
                only_newer_than=ONLY_NEWER_THAN, timeout=900, poll_interval=5):
    """usernames 리스트 → reel dict 리스트. Apify가 채널별 최신 N개(48h 여유) 반환.

    비동기 run 시작 → 완료까지 폴링 → 데이터셋 조회 (동기 엔드포인트의
    서버측 타임아웃 회피). token 미지정 시 계정 풀(APIFY_TOKENS)을 순환."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("APIFY_TOKEN 미설정 (환경변수 APIFY_TOKEN)")
    payload = {
        "username": usernames,
        "resultsLimit": results_per_channel,
        "onlyPostsNewerThan": only_newer_than,
        "skipPinnedPosts": True,
    }
    _, headers, run_data = _start_run(payload, tokens)
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
