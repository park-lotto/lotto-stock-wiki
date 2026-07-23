from shopping_shorts.store import Store


def test_append_bank_usage_caps_and_persists(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    for i in range(55):
        lst = store.append_bank_usage({"i": i}, cap=50)
    assert len(lst) == 50
    assert lst[0]["i"] == 5        # 앞 5개 밀려남
    assert lst[-1]["i"] == 54
    # 재조회로 영속 확인
    import json
    saved = json.loads(store.get_setting("bank_usage_recent"))
    assert len(saved) == 50
