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
    assert set(d) == {
        "shortcode", "url", "timestamp", "caption", "commentsCount",
        "likesCount", "videoViewCount", "displayUrl", "videoUrl", "ownerUsername",
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
