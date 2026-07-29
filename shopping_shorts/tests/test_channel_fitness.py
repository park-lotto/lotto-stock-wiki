from shopping_shorts.channel_fitness import channel_fitness, GOOD_CATEGORIES


def test_fitness_counts_good_categories():
    items = [
        {"name": "살림수집가", "category": "홈템"},
        {"name": "살림수집가", "category": "레시피"},
        {"name": "살림수집가", "category": "기타"},
        {"name": "연예노트", "category": "기타"},
        {"name": "연예노트", "category": "기타"},
    ]
    out = channel_fitness(items)
    assert out["살림수집가"]["total"] == 3
    assert out["살림수집가"]["good"] == 2
    assert out["살림수집가"]["other"] == 1
    assert abs(out["살림수집가"]["fitness"] - 2 / 3) < 1e-9
    assert out["연예노트"]["fitness"] == 0.0
    assert out["연예노트"]["other"] == 2


def test_beauty_is_not_good_category():
    # 뷰티는 쇼핑 소재로 치지 않는다(설계 확정)
    assert "뷰티" not in GOOD_CATEGORIES
    items = [{"name": "ch", "category": "뷰티"}]
    assert channel_fitness(items)["ch"]["fitness"] == 0.0


def test_falls_back_to_username_then_placeholder():
    items = [
        {"username": "only_user", "category": "홈템"},
        {"category": "홈템"},
    ]
    out = channel_fitness(items)
    assert out["only_user"]["total"] == 1
    assert out["?"]["total"] == 1


def test_empty_input_returns_empty_dict():
    assert channel_fitness([]) == {}
