"""Apify Instagram Reel Scraper HTTP 클라이언트."""
import requests
from shopping_shorts.config import APIFY_TOKEN, APIFY_ACTOR, RESULTS_PER_CHANNEL, ONLY_NEWER_THAN

# 동기 실행 + 데이터셋 즉시 반환 엔드포인트
_RUN_SYNC_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def fetch_reels(usernames, token=None, results_per_channel=RESULTS_PER_CHANNEL,
                only_newer_than=ONLY_NEWER_THAN, timeout=300):
    """usernames 리스트 → reel dict 리스트. Apify가 채널별 최신 N개(48h 여유) 반환."""
    token = token or APIFY_TOKEN
    if not token:
        raise RuntimeError("APIFY_TOKEN 미설정 (환경변수 APIFY_TOKEN)")
    payload = {
        "username": usernames,
        "resultsLimit": results_per_channel,
        "onlyPostsNewerThan": only_newer_than,
        "skipPinnedPosts": True,
    }
    url = _RUN_SYNC_URL.format(actor=APIFY_ACTOR)
    resp = requests.post(url, params={"token": token}, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()  # list of reel dicts
