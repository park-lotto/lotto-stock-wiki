"""렌즈 oEmbed 실검증(2026-08-03) — verify_matches 계약.

구글 렌즈가 페이지의 추천영상 썸네일을 그 페이지 URL과 짝지어 주는 어긋남('링크가 다른
영상으로 연결' 제보) → 틱톡·유튜브는 oEmbed 실조회로 실제 제목·썸네일로 교체하고,
404(삭제·비공개)는 link_ok=False로 표시해 프론트가 숨긴다. 실패는 no-op이어야 한다
(검증 불가가 회수율을 깎으면 안 됨). 네트워크는 전부 모킹.
"""
from unittest.mock import patch, Mock
import requests
from shopping_shorts import lens_discover
from shopping_shorts.lens_discover import verify_matches


def _resp(status=200, json_data=None, raise_json=False):
    r = Mock()
    r.status_code = status
    if raise_json:
        r.json.side_effect = ValueError("not json")
    else:
        r.json.return_value = json_data or {}
    return r


def test_success_replaces_title_thumbnail_and_rejudges_match():
    items = [{"platform": "tiktok", "url": "https://www.tiktok.com/@a/video/1",
              "title": "구글이 준 엉뚱한 제목", "thumbnail": "wrong.jpg", "match": True}]
    with patch.object(lens_discover.requests, "get",
                      return_value=_resp(200, {"title": "Avocado Sushi Roll",
                                               "thumbnail_url": "real.jpg"})):
        verify_matches(items, keywords={"avocado"})
    assert items[0]["title"] == "Avocado Sushi Roll"
    assert items[0]["thumbnail"] == "real.jpg"
    assert items[0]["match"] is True          # 실제 제목 기준 재판정
    assert items[0]["verified"] is True


def test_404_marks_dead_link():
    items = [{"platform": "tiktok", "url": "https://www.tiktok.com/@a/video/2",
              "title": "t", "thumbnail": "x"}]
    with patch.object(lens_discover.requests, "get", return_value=_resp(404)):
        verify_matches(items)
    assert items[0]["link_ok"] is False


def test_timeout_and_non_target_are_noop():
    items = [{"platform": "tiktok", "url": "https://www.tiktok.com/@a/video/3",
              "title": "keep", "thumbnail": "keep.jpg"},
             {"platform": "instagram", "url": "https://www.instagram.com/reel/a/",
              "title": "ig", "thumbnail": "ig.jpg"}]
    with patch.object(lens_discover.requests, "get",
                      side_effect=requests.RequestException("timeout")):
        verify_matches(items)
    assert items[0]["title"] == "keep" and "link_ok" not in items[0]
    assert items[1]["title"] == "ig" and "verified" not in items[1]
