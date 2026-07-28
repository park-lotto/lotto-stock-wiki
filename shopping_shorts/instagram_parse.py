"""인스타 응답 JSON → 수집 표준 스키마(10키) 정규화. **순수 함수만** — 네트워크·브라우저 없음.

왜 따로 두나: 스크레이핑에서 제일 자주 깨지는 곳이 응답 파싱인데, 브라우저와 얽혀 있으면
실패 원인이 "인스타가 막았나 / 파싱이 틀렸나"로 뒤섞여 진단이 안 된다. 파서를 순수 함수로
떼어 fixture로 고정해두면 스키마 변경이 테스트에서 먼저 드러난다.

계약은 apify_client._normalize_apidojo_item(apify_client.py:190-207)이 확정한 10키다 —
이것만 지키면 ranking/화면/DB가 전부 무변경이다.
"""
from datetime import datetime, timezone

_TEN_KEYS_NUM = ("commentsCount", "likesCount", "videoViewCount")


def _first(d, *names, default=None):
    """여러 후보 키 중 먼저 존재하는 값. 인스타는 같은 값을 여러 이름으로 준다."""
    for n in names:
        if isinstance(d, dict) and d.get(n) is not None:
            return d[n]
    return default


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _iso(ts):
    """unix초(또는 이미 ISO 문자열) → ISO8601 UTC 문자열.

    ★비어 있으면 안 된다 — ranking.py:32-34가 age_hours를 못 구해 항목을 드롭한다."""
    if not ts:
        return ""
    if isinstance(ts, str):
        return ts
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _caption_text(node):
    """caption은 {"text": ...} 또는 문자열로 온다(응답 종류에 따라 다름)."""
    cap = _first(node, "caption", "edge_media_to_caption", default="")
    if isinstance(cap, dict):
        return cap.get("text") or ""
    if isinstance(cap, str):
        return cap
    return ""


def _best_image(node):
    iv = _first(node, "image_versions2", "image_versions", default={}) or {}
    cands = iv.get("candidates") if isinstance(iv, dict) else None
    if isinstance(cands, list) and cands:
        return cands[0].get("url") or ""
    return _first(node, "display_url", "thumbnail_url", default="") or ""


def _best_video(node):
    vv = _first(node, "video_versions", default=[]) or []
    if isinstance(vv, list) and vv:
        return vv[0].get("url") or ""
    return _first(node, "video_url", default="") or ""


def parse_reel_node(node, username):
    """릴스 노드 1개 → 10키 dict. shortcode를 못 찾으면 None(호출부가 건너뛴다)."""
    if not isinstance(node, dict):
        return None
    code = _first(node, "code", "shortcode", default="")
    if not code:
        return None
    return {
        "shortcode": code,
        "url": f"https://www.instagram.com/reel/{code}/",
        "timestamp": _iso(_first(node, "taken_at", "taken_at_timestamp", "device_timestamp")),
        "caption": _caption_text(node),
        "commentsCount": _int(_first(node, "comment_count", "commentCount", default=0)),
        "likesCount": _int(_first(node, "like_count", "likeCount", default=0)),
        "videoViewCount": _int(_first(node, "play_count", "view_count", "playCount", default=0)),
        "displayUrl": _best_image(node),
        "videoUrl": _best_video(node),
        "ownerUsername": username,
    }


def extract_reel_nodes(payload):
    """인스타 응답 → 릴스 노드 리스트. 모르는 모양이면 [].

    두 응답 모양을 다 받는다:
    - 구 REST({"items": [...]}) — 2026-07-28 당시 관찰된 모양.
    - 신 GraphQL(data.xdt_api__v1__clips__user__connection_v2.edges[].node.media) —
      2026-07-29 실측: 인스타 웹이 /api/graphql로 통합되며 이 모양으로 바뀌었다.
      ⚠️ 이 목록 응답엔 taken_at·video_versions가 없다 — instagram_playwright가 pk로
      /api/v1/media/{pk}/info/를 한 번 더 불러 보충한다(그 응답도 구 REST 모양이라
      이 함수를 그대로 재사용한다).
    """
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if isinstance(items, list):
        out = []
        for it in items:
            if not isinstance(it, dict):
                continue
            # 항목이 {"media": {...}}로 한 겹 싸여 오는 응답 모양이 있다.
            node = it.get("media") if isinstance(it.get("media"), dict) else it
            out.append(node)
        return out
    conn = (payload.get("data") or {}).get("xdt_api__v1__clips__user__connection_v2")
    edges = (conn or {}).get("edges")
    if isinstance(edges, list):
        out = []
        for edge in edges:
            media = ((edge or {}).get("node") or {}).get("media")
            if isinstance(media, dict):
                out.append(media)
        return out
    return []


def classify_channel_result(nodes, page_url, error):
    """채널 1개의 수집 결과를 4가지로 분류한다.

    왜 나누나: "실패 30건"만으로는 부계정(로그인 세션)이 필요한지 알 수 없다.
    로그인벽이면 부계정으로 뚫리고, 비공개·삭제면 부계정으로도 안 된다.
    이 분류의 집계가 B안 도입 판단의 근거다(설계문서 참조).
    """
    if error:
        return "error"
    if nodes:
        return "ok"
    if "/accounts/login" in (page_url or ""):
        return "login_wall"
    return "not_found"
