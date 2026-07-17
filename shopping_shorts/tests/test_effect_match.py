from shopping_shorts import effect_match as em

BEATS = [
    # "5분"(숫자)과 "완전"(강조어)을 한 비트에 같이 둔다: match_rules의 count 분기
    # continue가 지워지면 이 비트에서 impact까지 추가로 잡혀 아래 단언이 죽는다.
    {"s": 0.0, "e": 2.0, "text": "이거 5분이면 완전 쉬워요"},
    {"s": 2.0, "e": 4.0, "text": "재료 3가지만 있으면 돼요"},
    {"s": 4.0, "e": 6.0, "text": "진짜 대박이에요"},
]


def test_theme_for_recipe_is_warm():
    assert em.theme_for("레시피") == "warm"
    assert em.theme_for("주식") == "tech"
    assert em.theme_for("모르는장르") == "warm"  # 기본


def test_rules_detect_count_impact_no_empty_list():
    fx = em.match_rules(BEATS)
    comps = {f["comp"] for f in fx}
    assert "count" in comps   # "5분"
    assert "impact" in comps  # "대박"
    # list 규칙은 items 소스가 없어 비활성 — 빈 카드가 생기면 안 된다(최종리뷰 I-1 봉인).
    assert "list" not in comps
    assert all(f["comp"] != "list" for f in fx)

    # "5분" 비트(BEATS[0], s=0.0~e=2.0)는 정확히 count 효과 하나만 만들어야 한다.
    # match_rules의 숫자(_NUM) 분기가 continue 없이 impact 분기로 흘러
    # 같은 비트에서 두 번째 fx가 추가되면 이 단언이 죽는다.
    beat0_fx = [f for f in fx if BEATS[0]["s"] <= f["s"] < BEATS[0]["e"]]
    beat0_comps = [f["comp"] for f in beat0_fx]
    assert beat0_comps.count("count") == 1
    assert beat0_comps.count("impact") == 0


def test_build_plan_shape_is_fullreel_props():
    plan = em.build_plan(BEATS, "레시피", "full.mp4", 180)
    assert plan["videoSrc"] == "full.mp4"
    assert plan["durationInFrames"] == 180
    assert plan["themeName"] == "warm"
    assert isinstance(plan["beats"], list) and isinstance(plan["fx"], list)
    for f in plan["fx"]:
        assert f["comp"] in {"impact", "count", "list", "callout"}
        assert 0.0 <= f["s"] < f["e"]


def test_suggest_without_client_is_rules_only(monkeypatch):
    plan = em.suggest(BEATS, "레시피", "f.mp4", 180, client=None)
    assert plan["themeName"] == "warm"
    # 규칙만: count·impact 존재(list는 items 소스 없어 비활성)
    assert {f["comp"] for f in plan["fx"]} >= {"count", "impact"}
    assert "list" not in {f["comp"] for f in plan["fx"]}


class _BoomClient:
    class models:
        @staticmethod
        def generate_content(*a, **k):
            raise RuntimeError("LLM down")


def test_suggest_llm_failure_falls_back_to_rules(monkeypatch):
    plan = em.suggest(BEATS, "레시피", "f.mp4", 180, client=_BoomClient())
    # 폴백: 규칙 결과가 그대로 나온다(예외 삼킴)
    assert {f["comp"] for f in plan["fx"]} >= {"count", "impact"}
