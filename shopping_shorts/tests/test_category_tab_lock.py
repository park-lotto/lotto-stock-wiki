"""탭 잠금(2026-10-06, 관제 134) — 사장님 "홈템이랑 썰쇼핑은 다른거 들어오지 못하게 막아놔".

설정 yt_category_lock 에 적힌 카테고리는 사람이 그 카테고리로 지정한 채널·영상만 들어간다.
자동판정만으로 들어오려는 유튜브 영상은 '기타'로 간다.
"""
from shopping_shorts.store import Store


def _items():
    return [
        {"platform": "youtube", "username": "UCpicked", "shortcode": "a", "category": "기타"},
        {"platform": "youtube", "username": "UCother", "shortcode": "b", "category": "제품정체형"},
        {"platform": "youtube", "username": "UCother", "shortcode": "c", "category": "오용형"},
        {"platform": "youtube", "username": "UCother", "shortcode": "d", "category": "홈템"},
        {"platform": "youtube", "username": "UCother", "shortcode": "e", "category": "레시피"},
        {"platform": "youtube", "username": "UChome", "shortcode": "f", "category": "뷰티"},
        {"platform": "youtube", "username": "UCother", "shortcode": "g", "category": "기타"},
        {"platform": "instagram", "username": "insta_home", "shortcode": "h", "category": "홈템"},
    ]


def _store(tmp_path, lock="제품정체형,오용형,홈템"):
    st = Store(str(tmp_path / "t.db"))
    st.set_channel_force("UCpicked", "제품정체형")
    st.set_channel_force("UChome", "홈템")
    st.set_category_overrides({"g": "홈템"})
    if lock:
        st.set_setting("yt_category_lock", lock)
    return st


def _cats(items):
    return {x["shortcode"]: x["category"] for x in items}


def test_잠금이_켜지면_고른_채널_밖_영상은_기타로(tmp_path):
    got = _cats(_store(tmp_path)._apply_overrides(_items()))
    assert got["a"] == "제품정체형"      # 고른 채널은 그대로 썰쇼핑
    assert got["f"] == "홈템"            # 고른 홈템 채널
    assert got["b"] == got["c"] == got["d"] == "기타"   # 자동판정만으로는 못 들어온다
    assert got["e"] == "레시피"          # 잠그지 않은 탭은 그대로
    assert got["g"] == "홈템"            # 영상을 사람이 직접 옮긴 것은 들어간다
    assert got["h"] == "홈템"            # 유튜브만 잠근다


def test_잠금이_꺼져_있으면_예전_그대로(tmp_path):
    got = _cats(_store(tmp_path, lock="")._apply_overrides(_items()))
    assert (got["b"], got["c"], got["d"]) == ("제품정체형", "오용형", "홈템")
