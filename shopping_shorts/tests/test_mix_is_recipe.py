"""소스 다수결로 is_recipe 판정 — category=='레시피'가 과반이면 True."""
from shopping_shorts import mix_pipeline


def test_is_recipe_majority():
    srcs = [{"category": "레시피"}, {"category": "레시피"}, {"category": "홈템"}]
    assert mix_pipeline._sources_is_recipe(srcs) is True


def test_is_recipe_minority_false():
    srcs = [{"category": "레시피"}, {"category": "가전"}, {"category": "홈템"}]
    assert mix_pipeline._sources_is_recipe(srcs) is False


def test_is_recipe_empty_false():
    assert mix_pipeline._sources_is_recipe([]) is False
