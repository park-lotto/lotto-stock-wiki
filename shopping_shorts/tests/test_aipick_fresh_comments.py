"""AI PICK 댓글수는 도서관 저장 순간의 박제(script_wiki.comments)가 아니라 '지금'(reel_history
최신 크롤)을 써야 한다.

사고(2026-07-26): 같은 양말 영상인데 재료 카드는 댓글 15,430(최신), AI PICK은 6,585(도서관
저장 당시)로 갈렸다. save_to_wiki가 저장 순간 comments를 박제해, 저장 후 댓글이 늘어도 AI PICK만
옛 숫자를 보여줬다(참여밀도도 옛 기준). reel_history 최신값을 오버레이해 진짜 값으로 맞춘다.
"""
import pytest

from shopping_shorts import app as app_module
from shopping_shorts.store import Store, LEGACY_CUSTOMER_ID


def test_latest_comments_from_reel_history(tmp_path):
    s = Store(tmp_path / "t.db")
    s.save_last_run(
        [{"shortcode": "AA", "username": "u", "comments": 15430},
         {"shortcode": "BB", "username": "u", "comments": 5}],
        "2026-07-26T00:00:00",
    )
    got = s.latest_comments(["AA", "BB", "ZZ"])
    assert got["AA"] == 15430
    assert got["BB"] == 5
    assert "ZZ" not in got   # 이력 없으면 키 자체가 없다 → 호출부가 도서관 스냅샷으로 폴백


def test_latest_comments_empty_input(tmp_path):
    assert Store(tmp_path / "t.db").latest_comments([]) == {}


def test_aipick_source_uses_fresh_comments_over_snapshot(tmp_path, monkeypatch):
    """담긴 영상의 댓글이 저장 후 늘었으면 AI PICK 소스도 최신값을 쓴다(박제 아님)."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    s = Store(tmp_path / "t.db")
    item = {"shortcode": "SOCKS", "username": "살림홈", "name": "살림홈", "category": "살림",
            "url": "https://insta/SOCKS", "followers": 120000, "comments": 6585, "thumbnail": ""}
    s.save_to_wiki(item, {"full_text": "양말 대본", "segments": [{"end": 33.0}]}, {})
    s.produce_pick_toggle("SOCKS")   # 영상제작에 담기
    # 저장 뒤 크롤에서 댓글이 15,430으로 늘었다
    s.save_last_run([{"shortcode": "SOCKS", "username": "살림홈", "comments": 15430}],
                    "2026-07-26T00:00:00")

    sources = app_module._load_work_sources(None, LEGACY_CUSTOMER_ID)
    src = next(x for x in sources if x["video_id"] == "SOCKS")
    assert src["comments"] == 15430, "도서관 박제(6585)가 아니라 최신 크롤(15430)을 써야 한다"
    assert src["seconds"] == 33.0   # 원본 길이(=마지막 세그먼트 end)도 그대로
    # 서버가 이름·썸네일을 실어야 카드 숫자와 썸네일이 같은 영상이 된다(프론트 HANDOFF 추측 방지).
    assert src["name"] == "살림홈"
    assert "thumbnail" in src and "category" in src


def test_aipick_source_falls_back_to_snapshot_when_no_history(tmp_path, monkeypatch):
    """최신 크롤 이력이 없으면 도서관 스냅샷 댓글로 폴백한다(값이 사라지지 않는다)."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    s = Store(tmp_path / "t.db")
    item = {"shortcode": "BAG", "username": "살림홈", "name": "살림홈", "category": "살림",
            "url": "https://insta/BAG", "followers": 120000, "comments": 6585, "thumbnail": ""}
    s.save_to_wiki(item, {"full_text": "대본", "segments": [{"end": 20.0}]}, {})
    s.produce_pick_toggle("BAG")
    # reel_history 비어 있음(수집 이력 없음)

    sources = app_module._load_work_sources(None, LEGACY_CUSTOMER_ID)
    src = next(x for x in sources if x["video_id"] == "BAG")
    assert src["comments"] == 6585   # 이력 없으니 스냅샷 유지
