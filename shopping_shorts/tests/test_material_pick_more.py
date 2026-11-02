# -*- coding: utf-8 -*-
"""CS #109(11-02) — 재료 후보에 같은 제품이 없을 때와 답 칸 이름.
1. 같은 제품 0개 + 재료_더찾기 = 사진만으로 대본에 가지 않고 그 자리에서 다시 찾는다
2. 재료_더찾기 없이 0개 = 종전처럼 한 번 다시 묻는다
3. 어느 형식의 질문이든 need 칸 이름이 글에 있다
"""
from tools.calcopy.hybrid import flow as f


def _st():
    return {"version": "썰템쇼판", "fmt": "쇼핑형", "tries": {}, "log": [], "bench": {"id": "BENCH"}, "origin": {}, "read": {}, "research": {"exclude": ["모음"]},
            "product": {"product_id": "1", "name": "제품"}, "screen_rows": [{"id": "a"}, {"id": "b"}], "_screen_sheets": []}


def test_zero_same_product_searches_again():
    st = _st()
    r = f.ph_material_pick(st, {}, {"screen_pick": {"chosen": [{"id": "BENCH"}], "재료_더찾기": ["브랜드 제품명 리뷰"]}}, {})
    assert r["then"] == "material_got" and r["do"][0]["cmd"] == "screen" and r["do"][0]["queries"] == ["브랜드 제품명 리뷰"]
    assert r["do"][0]["bench_id"] == "BENCH" and st["tries"]["more_material"] == 1


def test_search_limit_then_old_path():
    st = _st()
    st["tries"].update(more_material=f.MORE_MATERIAL_MAX, pick_more=1)
    r = f.ph_material_pick(st, {}, {"screen_pick": {"chosen": [], "재료_더찾기": ["x"]}}, {})
    assert r["then"] == "material_dl"


def test_zero_without_queries_asks_again():
    st = _st()
    r = f.ph_material_pick(st, {}, {"screen_pick": {"chosen": []}}, {})
    assert r["then"] == "material_pick" and "재료_더찾기" in r["review"][0]["ask"]


def test_need_names_always_in_ask():
    assert '"대본"' in f._rv("x", "글", need=("대본", "재료"))["ask"]
    assert f._rv("x", '{"chosen": []}', need=("chosen",))["ask"] == '{"chosen": []}'
