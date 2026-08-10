"""인스타 JSON 응답 → 10키 계약 정규화(네트워크 없음).

이 계약은 apify_client._normalize_apidojo_item(apify_client.py:190-207)이 확정한 것이다.
Playwright 경로가 같은 키를 못 채우면 ranking.build_items 이후가 통째로 깨진다.
특히 timestamp가 없으면 age_hours 계산이 실패해 항목이 드롭된다(ranking.py:32-34).
"""
from shopping_shorts.instagram_parse import extract_reel_nodes, parse_reel_node

# 인스타 응답에서 실제로 관찰되는 모양(중첩·별칭 포함)을 축약한 것.
_NODE = {
    "code": "DbMmu39Sph9",
    "taken_at": 1769500000,
    "caption": {"text": "다이소 이거 꼭 사세요"},
    "comment_count": 3388,
    "like_count": 12045,
    "play_count": 508549,
    "image_versions2": {"candidates": [{"url": "https://cdn/thumb.jpg", "width": 640}]},
    "video_versions": [{"url": "https://cdn/video.mp4", "width": 720}],
}


def test_parse_reel_node_fills_all_ten_keys():
    d = parse_reel_node(_NODE, "homeinon")
    # ownerFullName 추가(2026-08-06): 아카이브 카드를 @아이디 대신 한글 이름으로 띄우려고
    # 이미 받은 응답의 user.full_name을 주워 담는다(추가 요청 0건).
    # duration 추가(2026-08-09 '⏱길이 전면화' 21ca1a0b4): clips API 노드의
    # video_duration을 그대로 주워 담는다(추가 요청 0건). 이 테스트는 키 집합을
    # **정확히** 대조해서 조용한 누락을 잡는 게 목적이므로, 키가 늘면 여기도 같이 늘린다.
    assert set(d) == {
        "shortcode", "url", "timestamp", "caption", "commentsCount",
        "likesCount", "videoViewCount", "displayUrl", "videoUrl", "ownerUsername",
        "ownerFullName", "duration",
    }
    assert d["shortcode"] == "DbMmu39Sph9"
    assert d["url"] == "https://www.instagram.com/reel/DbMmu39Sph9/"
    assert d["caption"] == "다이소 이거 꼭 사세요"
    assert d["commentsCount"] == 3388
    assert d["likesCount"] == 12045
    assert d["videoViewCount"] == 508549
    assert d["displayUrl"] == "https://cdn/thumb.jpg"
    assert d["videoUrl"] == "https://cdn/video.mp4"
    assert d["ownerUsername"] == "homeinon"
    # 노드에 video_duration이 없으면 None(있는 척하지 않는다 — 0으로 채우면 '0초 영상'이 된다).
    assert d["duration"] is None


def test_parse_reel_node_reads_video_duration():
    """⏱길이(2026-08-09): 노드에 video_duration이 실려 오면 float로 담는다."""
    node = dict(_NODE, video_duration=12.34)
    assert parse_reel_node(node, "homeinon")["duration"] == 12.34


def test_parse_reel_node_timestamp_is_iso_utc():
    """★timestamp 없으면 항목이 드롭된다(ranking.py:32-34) — unix초를 ISO로."""
    d = parse_reel_node(_NODE, "homeinon")
    assert d["timestamp"].startswith("2026-")
    assert d["timestamp"].endswith("Z")


def test_parse_reel_node_missing_numbers_become_zero():
    d = parse_reel_node({"code": "X1", "taken_at": 1769500000}, "u")
    assert d["commentsCount"] == 0
    assert d["likesCount"] == 0
    assert d["videoViewCount"] == 0


def test_parse_reel_node_missing_strings_become_empty_not_none():
    d = parse_reel_node({"code": "X1", "taken_at": 1769500000}, "u")
    for k in ("caption", "displayUrl", "videoUrl"):
        assert d[k] == "", f"{k}가 None이면 하류에서 터진다"


def test_parse_reel_node_without_shortcode_returns_none():
    assert parse_reel_node({"taken_at": 1769500000}, "u") is None


def test_parse_reel_node_accepts_plain_caption_string():
    """caption이 dict가 아니라 문자열로 오는 응답도 있다."""
    d = parse_reel_node({"code": "X1", "taken_at": 1, "caption": "그냥 문자열"}, "u")
    assert d["caption"] == "그냥 문자열"


def test_extract_reel_nodes_from_items_shape():
    payload = {"items": [_NODE, {"code": "B2", "taken_at": 1769500001}]}
    assert [n["code"] for n in extract_reel_nodes(payload)] == ["DbMmu39Sph9", "B2"]


def test_extract_reel_nodes_from_media_wrapper_shape():
    """항목이 {"media": {...}}로 한 겹 싸여 오는 응답 모양."""
    payload = {"items": [{"media": _NODE}]}
    assert [n["code"] for n in extract_reel_nodes(payload)] == ["DbMmu39Sph9"]


def test_extract_reel_nodes_unknown_shape_returns_empty():
    assert extract_reel_nodes({"data": {"something_else": 1}}) == []
    assert extract_reel_nodes({}) == []


def test_extract_reel_nodes_from_graphql_clips_connection_shape():
    """2026-07-29 실측: 인스타가 /api/graphql로 통합된 뒤의 목록 응답 모양.
    ⚠️ 이 모양엔 taken_at·video_versions가 없다 — instagram_playwright가 pk로
    /api/v1/media/{pk}/info/를 한 번 더 불러 보충한다(그 응답은 구 REST 모양이라
    이 함수로 다시 파싱된다 — 별도 파서 불필요)."""
    payload = {
        "data": {
            "xdt_api__v1__clips__user__connection_v2": {
                "edges": [
                    {"node": {"media": {"code": "G1", "like_count": 10}}},
                    {"node": {"media": {"code": "G2", "like_count": 20}}},
                ],
                "page_info": {},
            }
        }
    }
    assert [n["code"] for n in extract_reel_nodes(payload)] == ["G1", "G2"]


from shopping_shorts.instagram_parse import classify_channel_result


def test_classify_ok_when_nodes_found():
    assert classify_channel_result([{"code": "A"}], "https://www.instagram.com/u/reels/", None) == "ok"


def test_classify_login_wall_by_redirect():
    """인스타가 막으면 /accounts/login/ 으로 튕긴다 — 이게 부계정 필요 신호다."""
    assert classify_channel_result(
        [], "https://www.instagram.com/accounts/login/?next=/u/reels/", None) == "login_wall"


def test_classify_error_takes_priority_over_empty():
    assert classify_channel_result([], "https://www.instagram.com/u/reels/", "Timeout") == "error"


def test_classify_not_found_when_empty_without_error():
    """비공개·삭제 계정 — 로그인벽과 구분해야 한다(부계정을 붙여도 안 되는 쪽)."""
    assert classify_channel_result([], "https://www.instagram.com/u/reels/", None) == "not_found"


# ── 해시태그 탐색 발굴(2026-07-30) — 서버 실측: /explore/tags/{tag}/ 진입 시
# xdt_fbsearch__top_serp_graphql 응답에 게시물+작성자가 실린다(로그인벽 없음). ──
from shopping_shorts.instagram_parse import extract_hashtag_search_items, parse_hashtag_search_item

_SERP_PAYLOAD = {
    "data": {
        "xdt_fbsearch__top_serp_graphql": {
            "edges": [
                {"node": {"__typename": "XDTTopSerpMediaGridUnit", "items": [
                    {"pk": "123", "code": "AbCdEf1", "taken_at": 1699873401,
                     "user": {"pk": "5954695110", "username": "casa.geraldine",
                              "full_name": "Geraldine Stauche", "is_verified": True}},
                    {"pk": "456", "code": "GhIjKl2", "taken_at": 1699873500,
                     "user": {"pk": "111", "username": "nouser_missing_pk"}},
                ]}},
            ]
        }
    }
}


def test_extract_hashtag_search_items_reads_serp_edges():
    items = extract_hashtag_search_items(_SERP_PAYLOAD)
    assert len(items) == 2
    assert items[0]["code"] == "AbCdEf1"


def test_extract_hashtag_search_items_unknown_shape_returns_empty():
    assert extract_hashtag_search_items({"data": {}}) == []
    assert extract_hashtag_search_items({}) == []
    assert extract_hashtag_search_items(None) == []


def test_parse_hashtag_search_item_fills_discovery_fields():
    items = extract_hashtag_search_items(_SERP_PAYLOAD)
    d = parse_hashtag_search_item(items[0])
    assert d["username"] == "casa.geraldine"
    assert d["full_name"] == "Geraldine Stauche"
    assert d["is_verified"] is True
    assert d["url"] == "https://www.instagram.com/p/AbCdEf1/"
    assert d["taken_at"]  # ISO 문자열로 채워짐
    # SERP 원본엔 참여도가 없다 — instagram_playwright가 media info REST로 보강한 뒤
    # like_count/comment_count/play_count가 이 딕셔너리에 채워져 들어온다(2026-07-30).
    assert d["like_count"] == 0
    assert d["comment_count"] == 0
    assert d["play_count"] == 0


def test_parse_hashtag_search_item_reads_engagement_when_enriched():
    """상세조회로 보강된 뒤(2026-07-30)의 형태 — like_count 등이 items[i]에 얹혀 온다."""
    enriched = dict(extract_hashtag_search_items(_SERP_PAYLOAD)[0])
    enriched["like_count"] = 34623
    enriched["comment_count"] = 6680
    enriched["play_count"] = 4786371
    d = parse_hashtag_search_item(enriched)
    assert d["like_count"] == 34623
    assert d["comment_count"] == 6680
    assert d["play_count"] == 4786371


def test_parse_hashtag_search_item_without_username_returns_none():
    assert parse_hashtag_search_item({"pk": "1", "user": {}}) is None
    assert parse_hashtag_search_item({}) is None
    assert parse_hashtag_search_item(None) is None


# ── 관문 URL 분류(2026-08-09 실사고) ──
# update_risky_contactpoint가 목록에 없어 챌린지 199채널이 전부 not_found로 집계됐다.
# "채널이 다 없어졌다"로 오독 → "계정 한도소진"이라는 엉뚱한 결론까지 갔다.
# 원인·대처가 정반대라(계정 교체 vs 포기) 반드시 갈라야 한다.
import pytest


@pytest.mark.parametrize("url", [
    "https://www.instagram.com/accounts/update_risky_contactpoint/?challenge_id=1",
    "https://www.instagram.com/challenge/action/12345/",
    "https://www.instagram.com/accounts/suspended/",
    "https://www.instagram.com/accounts/scraping_warning/",
])
def test_classify_login_wall_covers_all_gate_urls(url):
    assert classify_channel_result([], url, None) == "login_wall"


def test_classify_gate_url_is_not_confused_with_missing_channel():
    """관문(계정 교체로 뚫림)과 없는 채널(못 뚫음)이 같은 값이면 원인을 못 읽는다."""
    gate = classify_channel_result(
        [], "https://www.instagram.com/accounts/update_risky_contactpoint/", None)
    gone = classify_channel_result([], "https://www.instagram.com/u/reels/", None)
    assert gate == "login_wall" and gone == "not_found" and gate != gone
