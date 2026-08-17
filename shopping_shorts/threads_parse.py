"""쓰레드 응답 → 우리 계약 dict. 네트워크 없음(그래서 fixture로 테스트된다)."""
import json
import re
from datetime import datetime, timezone

THREADS_BASE = "https://www.threads.com"

_SJS_RE = re.compile(
    r'<script[^>]+type="application/json"[^>]*>(.*?)</script>', re.S)


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _text(v):
    """캡션은 dict({"text": ...})·문자열·None 셋 다로 온다.
    ★타입 확인 전에 .strip()을 부르지 마라(라이브 500 전례)."""
    if isinstance(v, dict):
        v = v.get("text")
    return v.strip() if isinstance(v, str) else ""


def _iso(ts):
    n = _int(ts, 0)
    if not n:
        return ""
    return datetime.fromtimestamp(n, tz=timezone.utc).isoformat()


def _best_image(node):
    c = ((node.get("image_versions2") or {}).get("candidates")) or []
    if not isinstance(c, list) or not c:
        return ""
    best = max(c, key=lambda x: _int((x or {}).get("width")))
    return (best or {}).get("url") or ""


def _best_video(node):
    v = node.get("video_versions") or []
    if isinstance(v, list) and v:
        best = max(v, key=lambda x: _int((x or {}).get("width")))
        url = (best or {}).get("url") or ""
        if url:
            return url
    # 캐러셀(앨범) 게시물은 video_versions가 최상위엔 없고
    # carousel_media[i]에 각각 들어있다 (실측: media_type=8).
    carousel = node.get("carousel_media") or []
    if isinstance(carousel, list):
        for item in carousel:
            if not isinstance(item, dict):
                continue
            iv = item.get("video_versions") or []
            if isinstance(iv, list) and iv:
                best = max(iv, key=lambda x: _int((x or {}).get("width")))
                url = (best or {}).get("url") or ""
                if url:
                    return url
    return ""


def parse_post_node(node, username):
    """게시물 노드 1개 → 계약 dict. code가 없으면 None(호출부가 건너뛴다)."""
    if not isinstance(node, dict):
        return None
    code = node.get("code") or node.get("shortcode") or ""
    if not isinstance(code, str) or not code:
        return None
    info = node.get("text_post_app_info") or {}
    if not isinstance(info, dict):
        info = {}
    video_url = _best_video(node)
    return {
        "code": code,
        "url": f"{THREADS_BASE}/@{username}/post/{code}",
        "username": username,
        "caption": _text(node.get("caption")),
        "media_kind": "video" if video_url else ("image" if _best_image(node) else ""),
        "video_url": video_url,
        "thumb": _best_image(node),
        "likes": _int(node.get("like_count")),
        "comments": _int(info.get("direct_reply_count") or node.get("comment_count")),
        "reposts": _int(info.get("repost_count")),
        "shares": _int(info.get("reshare_count")),
        "views": _int(node.get("play_count") or node.get("view_count")),
        "posted_at": _iso(node.get("taken_at") or node.get("taken_at_timestamp")),
    }


def _iter_json_blobs(html):
    """HTML 안에 인라인된 JSON 블록을 하나씩 내놓는다. 못 읽는 블록은 건너뛴다."""
    for m in _SJS_RE.finditer(html or ""):
        try:
            yield json.loads(m.group(1))
        except (ValueError, TypeError):
            continue


def _walk_nodes(obj, out, seen):
    """게시물처럼 생긴 dict를 모양으로 찾는다(경로 하드코딩 금지).

    조건: code가 있고, 지표(like_count 또는 text_post_app_info)가 함께 있다.
    """
    if isinstance(obj, dict):
        code = obj.get("code")
        if (isinstance(code, str) and code
                and ("like_count" in obj or "text_post_app_info" in obj)):
            if code not in seen:
                seen.add(code)
                out.append(obj)
        for v in obj.values():
            _walk_nodes(v, out, seen)
    elif isinstance(obj, list):
        for v in obj:
            _walk_nodes(v, out, seen)


def extract_post_nodes(payload):
    """HTML 문서(또는 이미 파싱된 dict/list) → 게시물 노드 리스트. 모르면 []."""
    out, seen = [], set()
    if isinstance(payload, str):
        for blob in _iter_json_blobs(payload):
            _walk_nodes(blob, out, seen)
    else:
        _walk_nodes(payload, out, seen)
    return out
