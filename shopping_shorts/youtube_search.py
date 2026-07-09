"""YouTube Data API v3로 키워드 검색 → 정규화된 후보 리스트.

키 풀(YOUTUBE_API_KEYS) 로테이션 지원(2026-07-09) — 계정 하나가 일일 무료
할당량(10,000 유닛/일)을 소진해도 다음 계정으로 넘어간다. apify_client.py와
동일한 "마지막 성공 인덱스 저장" 패턴 재사용."""
import json
from pathlib import Path
import requests
from shopping_shorts.config import YOUTUBE_API_KEYS

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_KEY_STATE_PATH = Path(__file__).parent / "data" / "youtube_key_index.json"


def _load_key_index():
    try:
        return json.loads(_KEY_STATE_PATH.read_text(encoding="utf-8")).get("index", 0)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def _save_key_index(index):
    _KEY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEY_STATE_PATH.write_text(json.dumps({"index": index}), encoding="utf-8")


def _is_quota_error(exc):
    resp = getattr(exc, "response", None)
    return resp is not None and resp.status_code in (403, 429)


def _parse_items(data):
    out = []
    for item in data.get("items", []):
        vid = item.get("id", {}).get("videoId")
        if not vid:
            continue
        snippet = item.get("snippet", {})
        thumb = snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
        out.append({
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": snippet.get("title", ""),
            "thumbnail": thumb,
        })
    return out


def search(keyword, max_results=10):
    """키워드 → [{url, title, thumbnail}, ...]. 키 풀 전체 소진 시 마지막 오류를 던진다."""
    if not YOUTUBE_API_KEYS:
        raise RuntimeError("youtube_search: YOUTUBE_API_KEY가 설정되지 않았습니다")

    start = _load_key_index() % len(YOUTUBE_API_KEYS)
    last_err = None
    for offset in range(len(YOUTUBE_API_KEYS)):
        idx = (start + offset) % len(YOUTUBE_API_KEYS)
        key = YOUTUBE_API_KEYS[idx]
        try:
            resp = requests.get(_SEARCH_URL, params={
                "part": "snippet", "q": keyword, "type": "video",
                "maxResults": max_results, "key": key,
            }, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            last_err = e
            if _is_quota_error(e):
                continue
            raise
        if idx != start:
            _save_key_index(idx)
        return _parse_items(resp.json())

    raise RuntimeError(f"youtube_search: 키 {len(YOUTUBE_API_KEYS)}개 전부 소진(마지막 오류: {last_err})")
