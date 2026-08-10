from shopping_shorts.overseas_seeds import load_seeds, CATEGORIES


def test_seeds_have_platform_keyword_lists():
    seeds = load_seeds()
    assert seeds
    for cat, cfg in seeds.items():
        assert isinstance(cfg.get("tiktok"), list) and cfg["tiktok"], f"{cat}: tiktok 키워드 필요"
        assert isinstance(cfg.get("cn"), list) and cfg["cn"], f"{cat}: cn 키워드 필요"


def test_categories_derived_from_keys():
    assert CATEGORIES == list(load_seeds().keys())


def test_no_reddit_subreddits_left():
    for cfg in load_seeds().values():
        assert "subreddits" not in cfg
