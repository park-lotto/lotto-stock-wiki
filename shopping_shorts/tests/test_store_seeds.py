from shopping_shorts.store import Store


def test_seed_crud(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.add_seed("youtube", "keyword", "살림꿀팁")
    st.add_seed("youtube", "keyword", "냉장고정리")
    st.add_seed("tiktok", "account", "@salim")
    yt = [s["value"] for s in st.list_seeds("youtube")]
    assert yt == ["살림꿀팁", "냉장고정리"]
    assert st.list_seeds("tiktok")[0]["value"] == "@salim"
    st.remove_seed("youtube", "살림꿀팁")
    assert [s["value"] for s in st.list_seeds("youtube")] == ["냉장고정리"]


def test_platform_scoped_snapshots(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_run_platform("youtube", "2026-07-13 10:00",
                         [{"shortcode": "v1", "base": 100, "delta": 100}])
    st.save_run_platform("youtube", "2026-07-13 11:00",
                         [{"shortcode": "v1", "base": 300, "delta": 200}])
    assert st.prev_base_platform("youtube", "v1") == 300     # 최신
    assert st.prev_delta_platform("youtube", "v1") == 200
    assert st.prev_base_platform("youtube", "nope") is None
