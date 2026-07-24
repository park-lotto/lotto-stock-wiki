from shopping_shorts.overseas_seeds import load_seeds, CATEGORIES


def test_load_seeds_has_all_categories():
    seeds = load_seeds()
    assert set(seeds.keys()) == set(CATEGORIES)
    for cat, cfg in seeds.items():
        assert isinstance(cfg["subreddits"], list) and cfg["subreddits"]
        assert isinstance(cfg["seed_accounts"], list)   # 비어도 됨(v1)
