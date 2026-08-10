"""랭킹 검색용 썸네일 비전 주제태그 저장/조회(2026-07-19)."""
from shopping_shorts.store import Store


def test_save_get_vision_tags(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    assert st.get_vision_tags("p1") is None                 # 없으면 None
    st.save_vision_tags("p1", "오이무침", ["오이", "다이어트반찬"])
    got = st.get_vision_tags("p1")
    assert got["subject"] == "오이무침"
    assert got["keywords"] == ["오이", "다이어트반찬"]


def test_vision_tags_overwrite_no_dup(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_vision_tags("p1", "베이글", ["베이글"])
    st.save_vision_tags("p1", "블루투스 스피커", ["스피커", "조명"])   # 같은 shortcode 덮어씀
    got = st.get_vision_tags("p1")
    assert got["subject"] == "블루투스 스피커"
    assert got["keywords"] == ["스피커", "조명"]


def test_vision_tags_map(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_vision_tags("p1", "오이무침", ["오이"])
    st.save_vision_tags("p2", "소파", ["소파", "거실"])
    m = st.vision_tags_map(["p1", "p2", "p3"])   # p3는 태그 없음 → 결과에서 빠짐
    assert set(m.keys()) == {"p1", "p2"}
    assert m["p2"]["keywords"] == ["소파", "거실"]
    assert st.vision_tags_map([]) == {}
