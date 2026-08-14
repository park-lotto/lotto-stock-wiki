"""인스타 응답 JSON → 수집 표준 스키마(10키) 정규화. **순수 함수만** — 네트워크·브라우저 없음.

왜 따로 두나: 스크레이핑에서 제일 자주 깨지는 곳이 응답 파싱인데, 브라우저와 얽혀 있으면
실패 원인이 "인스타가 막았나 / 파싱이 틀렸나"로 뒤섞여 진단이 안 된다. 파서를 순수 함수로
떼어 fixture로 고정해두면 스키마 변경이 테스트에서 먼저 드러난다.

계약은 apify_client._normalize_apidojo_item(apify_client.py:190-207)이 확정한 10키다 —
이것만 지키면 ranking/화면/DB가 전부 무변경이다.
"""
from datetime import datetime, timezone

_TEN_KEYS_NUM = ("commentsCount", "likesCount", "videoViewCount")

# ── shortcode → 발행시각 (네트워크 호출 0, 2026-07-30) ─────────────────────────
# 인스타 media id(pk)의 상위 비트가 밀리초 타임스탬프다. shortcode는 그 pk를 아래
# 64진 알파벳으로 인코딩한 것이라, **shortcode만으로 발행시각을 정확히 복원**할 수 있다.
#
# 왜 중요한가: 릴스 목록(clips) 응답엔 taken_at이 없어서 릴스마다
# /api/v1/media/{pk}/info/를 한 번 더 불러 시각을 보충해왔다(하루 950건). 그게 429의
# 주범이었고, 429가 나면 시각이 비어 ranking.build_items의 `if not ts: continue`가
# 릴스를 통째로 버려 **수집 결과가 조용히 1/3로 줄었다**(2026-07-30 실사고: ok 214인데
# 결과 80건). 이 함수로 그 왕복을 전부 없앤다.
#
# 상수 검증(2026-07-30): 그날 수집된 실데이터 6건의 실제 taken_at과 대조해 6/6이
# 아래 상수로 일치했다(잔차는 저장된 age_hours가 0.1시간 반올림이라 생긴 것).
_SC_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_SC_EPOCH_MS = 1314220021721        # pk 상위비트의 기준시각(2011-08-24 UTC 근방)


def shortcode_to_pk(shortcode):
    """인스타 shortcode → media pk(정수). 알파벳 밖 문자가 섞이면 None."""
    n = 0
    for ch in (shortcode or ""):
        i = _SC_ALPHABET.find(ch)
        if i < 0:
            return None
        n = n * 64 + i
    return n or None


def shortcode_to_timestamp(shortcode):
    """인스타 shortcode → 발행시각 ISO 문자열(UTC). 못 풀면 None.

    범위를 벗어난 값(2010년 이전·현재+1일 초과)은 None을 돌려준다 — 인코딩이 바뀌었는데
    엉뚱한 시각으로 조용히 통과해 랭킹이 오염되는 게 최악이다. 차라리 비워서 기존
    `if not ts: continue`에 걸리게 둔다."""
    pk = shortcode_to_pk(shortcode)
    if not pk:
        return None
    ms = (pk >> 23) + _SC_EPOCH_MS
    try:
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    now = datetime.now(timezone.utc)
    if dt.year < 2010 or (dt - now).total_seconds() > 86400:
        return None
    return dt.isoformat().replace("+00:00", "Z")


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
        # 응답에 taken_at이 있으면 그걸 쓰고, 없으면 shortcode에서 복원한다(REST 왕복 0).
        "timestamp": (_iso(_first(node, "taken_at", "taken_at_timestamp", "device_timestamp"))
                      or shortcode_to_timestamp(code)),
        "caption": _caption_text(node),
        "commentsCount": _int(_first(node, "comment_count", "commentCount", default=0)),
        "likesCount": _int(_first(node, "like_count", "likeCount", default=0)),
        "videoViewCount": _int(_first(node, "play_count", "view_count", "playCount", default=0)),
        "displayUrl": _best_image(node),
        "videoUrl": _best_video(node),
        # ⏱ 길이(2026-08-09): clips API 노드에 video_duration이 이미 실려 온다 —
        # yt-dlp 백필(건당 수 초)로 채우던 것을 크롤이 지나가며 공짜로 채운다.
        "duration": (float(node.get("video_duration"))
                     if node.get("video_duration") else None),
        "ownerUsername": username,
        # 채널 표시명(2026-08-06) — 아카이브 카드를 한글 이름으로 띄우려고 주워 담는다.
        # ★이미 받은 응답에서 꺼낼 뿐이라 **추가 요청이 0건**이다(parse_search_item도
        #   같은 user.full_name을 읽는다). 이 경로는 계정이 차단돼 세션을 돌려쓰는 중이라
        #   요청을 한 건도 더 늘리면 안 된다.
        # 노드에 user가 없는 경우가 흔하다(응답 모양이 여러 가지) → 빈 문자열로 안전 폴백.
        "ownerFullName": ((node.get("user") or {}).get("full_name") or "")
                         if isinstance(node.get("user"), dict) else "",
        # 팔로워(2026-08-14) — instagram_playwright가 같은 페이지 응답에서 주워
        # 노드에 실어준 값(_owner_follower_count). 노드 자체의 user.follower_count도
        # 드물게 있어 함께 본다. 추가 요청 0건.
        "ownerFollowers": _int(node.get("_owner_follower_count")
                               or ((node.get("user") or {}).get("follower_count")
                                   if isinstance(node.get("user"), dict) else 0)
                               or 0),
    }


def extract_follower_count(payload):
    """인스타 응답 → 그 계정의 팔로워 수(못 찾으면 0).

    /{계정}/reels/ 를 열면 인스타가 스스로 graphql로 프로필을 함께 내려준다
    (실측 2026-08-14: data.user.follower_count). 모양이 여러 가지라 알려진 자리를
    먼저 보고, 없으면 얕게 훑는다. **추가 요청은 하지 않는다** — 이미 받은
    응답에서 꺼내는 것뿐이다.
    """
    if not isinstance(payload, dict):
        return 0
    user = (payload.get("data") or {}).get("user")
    if isinstance(user, dict):
        n = _int(user.get("follower_count") or 0)
        if n:
            return n
        # 옛 웹 모양: edge_followed_by.count
        edge = user.get("edge_followed_by")
        if isinstance(edge, dict) and _int(edge.get("count") or 0):
            return _int(edge["count"])
    # 알려진 자리에 없으면 깊이 3까지만 훑는다(전체 순회는 큰 응답에서 낭비).
    def _walk(o, depth):
        if depth > 3 or not isinstance(o, dict):
            return 0
        for k, v in o.items():
            if k == "follower_count" and _int(v or 0):
                return _int(v)
            if isinstance(v, dict):
                got = _walk(v, depth + 1)
                if got:
                    return got
        return 0
    return _walk(payload, 0)


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


def extract_hashtag_search_items(payload):
    """해시태그 탐색(/explore/tags/{tag}/) 응답 → 게시물 노드 리스트(2026-07-30 계정발굴).

    인스타는 탐색 페이지 진입 시 graphql로 xdt_fbsearch__top_serp_graphql을 불러
    해시태그 검색결과(SERP)를 채운다(실측, 로그인벽 없음). edges[].node.items[]가
    게시물이고, 각 항목의 user 필드에 발굴 대상 계정(pk/username/full_name)이 있다.
    모르는 모양이면 [] — 한 페이지 파싱 실패가 다른 태그 발굴을 막지 않는다."""
    if not isinstance(payload, dict):
        return []
    try:
        edges = payload["data"]["xdt_fbsearch__top_serp_graphql"]["edges"]
    except (KeyError, TypeError):
        return []
    if not isinstance(edges, list):
        return []
    out = []
    for edge in edges:
        node = (edge or {}).get("node") or {}
        items = node.get("items")
        if isinstance(items, list):
            out.extend(it for it in items if isinstance(it, dict))
    return out


def parse_hashtag_search_item(item):
    """해시태그 검색 게시물 1개 → 발굴용 dict. user/username 없으면 None.

    like_count/comment_count/play_count는 SERP 자체엔 없고(실측), 상위 표본만
    instagram_playwright._fetch_reel_detail로 보강된 뒤 이 키들이 채워져 들어온다
    (2026-07-30, 참여도 기반 발굴 정렬을 위함). 없으면 0."""
    if not isinstance(item, dict):
        return None
    user = item.get("user") or {}
    username = user.get("username")
    if not username:
        return None
    code = item.get("code") or ""
    return {
        "username": username,
        "full_name": user.get("full_name") or "",
        "is_verified": bool(user.get("is_verified")),
        "pk": item.get("pk") or "",
        "code": code,
        "url": f"https://www.instagram.com/p/{code}/" if code else "",
        "taken_at": _iso(item.get("taken_at")),
        "like_count": _int(item.get("like_count")),
        "comment_count": _int(item.get("comment_count")),
        "play_count": _int(item.get("play_count")),
    }


# 인스타가 "이 계정/접속을 못 믿겠다"며 릴스 대신 띄우는 관문 URL 조각들.
# not_found(=채널이 없다)와 반드시 갈라야 한다 — 원인도 대처도 정반대다.
#   login_wall  → 계정·세션·IP 문제. 세션 재발급·계정 교체로 뚫린다.
#   not_found   → 채널이 비공개/삭제. 계정을 아무리 바꿔도 안 된다.
# ★update_risky_contactpoint(2026-08-09 추가): 본인확인 요구 페이지. 이게 목록에
# 없어서 챌린지 199채널이 전부 not_found로 집계됐고, "채널이 다 없어졌다"로 오독한 뒤
# "계정이 한도소진됐다"는 엉뚱한 결론까지 갔다(진짜 원인은 계정↔IP 불일치 버그였다).
_LOGIN_WALL_URL_HINTS = (
    "/accounts/login",
    "scraping_warning",
    "update_risky_contactpoint",   # 본인확인(위험 연락처) 요구
    "/challenge",                  # 캡차·인증 관문
    "/accounts/suspended",         # 계정 정지
)


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
    url = page_url or ""
    if any(h in url for h in _LOGIN_WALL_URL_HINTS):
        return "login_wall"
    return "not_found"
