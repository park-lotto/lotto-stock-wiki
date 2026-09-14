# -*- coding: utf-8 -*-
"""제품명 표기 차이가 동일 소재를 동률로 갈라놓은 사고의 회귀 테스트."""

from shopping_shorts import topic_contract
from shopping_shorts import app as app_mod


ACTUAL_WORK_ID = "20f6aeb39b1a"


def _source(source_id, product, observation, *, full_text=""):
    return {
        "source_id": source_id,
        "source_brief": {"product": product},
        "full_text": full_text,
        "segments": [{
            "seg_id": source_id + "-0",
            "scene_desc": observation,
            "change": "",
            "text": "",
        }],
    }


def _actual_container_sources():
    """실서버 작업의 세 제품명과 각 소스에서 실제 관측된 문장을 보존한다."""
    return [
        _source(
            "grab_tiktok_171146a81bd0",
            "과일 세척 및 보관용기",
            "용기를 들고 수도꼭지 아래에서 딸기를 씻는 장면.",
        ),
        _source(
            "grab_instagram_8eaf5fe8a343",
            "신축성 뚜껑 보관 용기(채반 포함)",
            "채반이 내장된 유리 용기를 한 손으로 잡고 수도 아래에서 포도를 씻는 모습",
        ),
        _source(
            "grab_instagram_605b207ffbb0",
            "채소 및 과일 세척 보관 용기",
            "수도꼭지 아래에서 방울토마토가 담긴 바구니를 세척함",
        ),
    ]


def _one_container_group(rows):
    expected = {x["source_id"] for x in _actual_container_sources()}
    assert {x["source_id"] for x in rows} == expected
    return {"groups": [{
        "product": "과일 세척 및 보관용기",
        "source_ids": sorted(expected),
        "supports": [
            {"source_id": "grab_tiktok_171146a81bd0", "quote": "수도꼭지 아래에서 딸기를 씻는"},
            {"source_id": "grab_instagram_8eaf5fe8a343", "quote": "채반이 내장된 유리 용기"},
            {"source_id": "grab_instagram_605b207ffbb0", "quote": "방울토마토가 담긴 바구니를 세척"},
        ],
    }]}


def test_actual_three_container_sources_resolve_to_one_material_family():
    result = topic_contract.resolve_membership(
        _actual_container_sources(), judge=_one_container_group)

    assert result["version"] == 1
    assert result["method"] == "semantic"
    assert result["product"] in {
        "과일 세척 및 보관용기",
        "신축성 뚜껑 보관 용기(채반 포함)",
        "채소 및 과일 세척 보관 용기",
    }
    assert result["ambiguous"] is False
    assert len(result["groups"]) == 1
    assert len(set(result["membership"].values())) == 1
    assert set(result["membership"]) == {
        "grab_tiktok_171146a81bd0",
        "grab_instagram_8eaf5fe8a343",
        "grab_instagram_605b207ffbb0",
    }


def test_spacing_parenthetical_and_word_order_variants_resolve_as_one_family():
    sources = [
        _source("a", "과일 세척 보관용기", "과일을 씻고 물을 뺀 뒤 보관하는 용기"),
        _source("b", "보관 용기 (과일 세척용)", "용기에서 과일을 세척하고 보관하는 모습"),
        _source("c", "과일용 세척·보관 용기", "과일 세척 후 같은 용기에 보관함"),
    ]

    def variants_group(rows):
        return {"groups": [{
            "product": rows[0]["product"],
            "source_ids": [x["source_id"] for x in rows],
            "supports": [
                {"source_id": "a", "quote": "과일을 씻고 물을 뺀 뒤 보관하는 용기"},
                {"source_id": "b", "quote": "용기에서 과일을 세척하고 보관"},
                {"source_id": "c", "quote": "과일 세척 후 같은 용기에 보관"},
            ],
        }]}

    result = topic_contract.resolve_membership(sources, judge=variants_group)
    assert result["method"] == "semantic"
    assert result["ambiguous"] is False
    assert len(set(result["membership"].values())) == 1


def test_same_core_terms_in_different_order_are_exact_without_ai():
    sources = [
        _source("a", "과일 채소 보관 용기", "과일과 채소를 용기에 보관"),
        _source("b", "용기 보관 채소 과일", "채소와 과일을 용기에 보관"),
    ]

    def no_ai(_rows):
        raise AssertionError("동일한 핵심어의 어순 차이는 의미판정 호출이 불필요하다")

    result = topic_contract.resolve_membership(sources, judge=no_ai)
    assert result["method"] == "exact"
    assert result["ambiguous"] is False
    assert len(set(result["membership"].values())) == 1


def test_generic_mount_head_does_not_merge_different_products():
    sources = [
        _source("phone", "차량용 휴대폰 거치대", "차량 대시보드에 휴대폰을 고정하는 모습"),
        _source("sponge", "주방 수세미 거치대", "싱크대에 수세미를 걸어 두는 모습"),
        _source("cup", "차량용 컵홀더 거치대", "차량 컵홀더에 음료 받침을 끼우는 모습"),
    ]

    def separate(rows):
        return {"groups": [
            {"product": row["product"], "source_ids": [row["source_id"]],
             "supports": [{"source_id": row["source_id"], "quote": row["product"]}]}
            for row in rows
        ]}

    result = topic_contract.resolve_membership(sources, judge=separate)
    assert result["ambiguous"] is True
    assert len(set(result["membership"].values())) == 3


def test_generic_container_head_does_not_merge_different_uses():
    sources = [
        _source("kitchen", "주방 밀폐 용기", "반찬을 담고 뚜껑을 닫아 냉장 보관하는 모습"),
        _source("cosmetic", "화장품 소분 용기", "화장품을 작은 병에 덜어 여행 가방에 넣는 모습"),
    ]

    def separate(rows):
        return {"groups": [
            {"product": row["product"], "source_ids": [row["source_id"]],
             "supports": [{"source_id": row["source_id"], "quote": row["product"]}]}
            for row in rows
        ]}

    result = topic_contract.resolve_membership(sources, judge=separate)
    assert result["ambiguous"] is True
    assert result["membership"]["kitchen"] != result["membership"]["cosmetic"]


def test_multi_product_roundups_are_excluded_from_single_product_membership():
    sources = [
        _source("toilet-a", "차량용 휴대용 변기", "아이 급할 때 차 안에서 변기를 펼치는 모습"),
        _source("toilet-b", "휴대용 간이 화장실", "접이식 변기를 펼쳐 사용하는 모습"),
        _source(
            "vehicle-roundup",
            "차량용 필수 액세서리 4종(컵홀더, 휴대용 화장실, 냉온장고, 점프 스타터)",
            "서로 다른 차량용품 네 개를 차례로 보여주는 영상",
        ),
        _source("toilet-roundup", "휴대용 변기 4종 모음", "서로 다른 변기 네 개를 비교하는 영상"),
    ]

    def toilet_group(rows):
        assert {x["source_id"] for x in rows} == {"toilet-a", "toilet-b"}
        return {"groups": [{
            "product": "차량용 휴대용 변기",
            "source_ids": ["toilet-a", "toilet-b"],
            "supports": [
                {"source_id": "toilet-a", "quote": "차 안에서 변기를 펼치는"},
                {"source_id": "toilet-b", "quote": "접이식 변기를 펼쳐 사용하는"},
            ],
        }]}

    result = topic_contract.resolve_membership(sources, judge=toilet_group)
    assert result["ambiguous"] is False
    assert set(result["membership"]) == {"toilet-a", "toilet-b"}
    assert "vehicle-roundup" not in result["membership"]
    assert "toilet-roundup" not in result["membership"]


def test_semantic_group_requires_source_local_support_quote():
    sources = _actual_container_sources()

    def cross_source_support(_rows):
        # 세 번째 소스의 근거를 첫 번째 source_id에 붙이면 provenance가 끊긴다.
        return {"groups": [{
            "product": sources[0]["source_brief"]["product"],
            "source_ids": [x["source_id"] for x in sources],
            "supports": [
                {"source_id": sources[0]["source_id"], "quote": "방울토마토가 담긴 바구니를 세척"},
                {"source_id": sources[1]["source_id"], "quote": "채반이 내장된 유리 용기"},
                {"source_id": sources[2]["source_id"], "quote": "방울토마토가 담긴 바구니를 세척"},
            ],
        }]}

    result = topic_contract.resolve_membership(sources, judge=cross_source_support)
    assert result["method"] == "unresolved"
    assert result["ambiguous"] is True
    assert len(set(result["membership"].values())) == 3


def test_full_generate_and_partial_regen_reuse_identical_membership(monkeypatch):
    sources = _actual_container_sources()
    job = {"extract": {s["source_id"]: s for s in sources}}
    calls = []

    def judge(rows):
        calls.append([x["source_id"] for x in rows])
        return _one_container_group(rows)

    monkeypatch.setattr(topic_contract, "_judge_membership", judge)

    full_topic = app_mod._topic_product_for_generate({}, {}, job, None)
    full_sources = app_mod._sources_for_generate(
        {}, job, topic_product=full_topic)
    frozen_signature = job["_topic_resolution"]["signature"]
    full_membership = {
        x["source_id"]: x["topic_membership"] for x in full_sources
    }

    regen_topic = app_mod._topic_product_for_generate(
        {}, {"topic_product": full_topic}, job, None)
    regen_sources = app_mod._sources_for_generate(
        {}, job, topic_product=regen_topic)

    assert regen_topic == full_topic
    assert job["_topic_resolution"]["signature"] == frozen_signature
    assert {x["source_id"]: x["topic_membership"] for x in regen_sources} == full_membership
    assert len(calls) == 1
