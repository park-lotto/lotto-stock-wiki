"""한국어 소재 → 중국어 검색어 캐시(2026-07-25) — 트렌드 검색카드용."""
from shopping_shorts.store import Store


def test_save_get_cn_keyword(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    assert st.get_cn_keyword("텀블러건조대") is None          # 캐시 미스 → None(폴백 B)
    st.save_cn_keyword("텀블러건조대", "杯架沥水架")
    assert st.get_cn_keyword("텀블러건조대") == "杯架沥水架"


def test_cn_keyword_overwrite(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_cn_keyword("오이무침", "凉拌黄瓜")
    st.save_cn_keyword("오이무침", "拍黄瓜")                    # 같은 ko 덮어씀
    assert st.get_cn_keyword("오이무침") == "拍黄瓜"


def test_cn_keyword_map_only_has_zh(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_cn_keyword("오이무침", "拍黄瓜")
    st.save_cn_keyword("빈것", "")                             # zh 빈 값은 맵에서 빠짐(미스로 취급)
    m = st.cn_keyword_map(["오이무침", "빈것", "없는것"])
    assert m == {"오이무침": "拍黄瓜"}
    assert st.cn_keyword_map([]) == {}


def test_cn_keyword_ignores_blank_key(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_cn_keyword("   ", "x")                             # 공백 키는 저장 안 함
    assert st.get_cn_keyword("") is None
    assert st.cn_keyword_map(["", "  "]) == {}
