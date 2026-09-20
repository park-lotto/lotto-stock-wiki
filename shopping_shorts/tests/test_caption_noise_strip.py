# -*- coding: utf-8 -*-
"""원문형 스파인의 자막 잡음(`[음악]`)이 대본에 새지 않는다 (2026-09-21 사장님 제보).

사장님: "음악저게 이번에도 나오는게 구조적으로 뭐가있네 문제"
실사고: 스파인 387 원문 "…아이템이 [음악] 있어." → 생성된 대본에 그대로 나왔다.
백본은 원문을 그대로 베끼는 게 일이므로, 원문에 잡음이 있으면 반드시 샌다.
DB만 고치면 새로 넣는 스파인에서 재발하므로 **읽는 자리**(spine_origin)에서 막는다.
"""
import json

from shopping_shorts import backbone_assemble as ba


def _spine(cells, hook_tpl=""):
    return {"templates_json": json.dumps(
        {"_origin": {"cells": cells, "hook_tpl": hook_tpl}}, ensure_ascii=False)}


def test_음악_태그가_칸에서_사라진다():
    o = ba.spine_origin(_spine([
        {"role": "전환", "text": "그런데 이런 아이템이 [음악] 있어."},
        {"role": "감정", "text": "진짜 편해졌어요."},
    ]))
    assert "[음악]" not in o["cells"][0]["text"]
    # 잡음만 빠지고 말은 그대로여야 한다 — 문장을 새로 쓰면 안 된다
    assert o["cells"][0]["text"] == "그런데 이런 아이템이 있어."
    assert o["cells"][1]["text"] == "진짜 편해졌어요."


def test_훅틀에서도_사라진다():
    o = ba.spine_origin(_spine([{"role": "훅", "text": "정상."}],
                               hook_tpl="모르고 썼다가 [박수] 큰일 나는 {제품군}."))
    assert "[박수]" not in o["hook_tpl"]
    assert o["hook_tpl"] == "모르고 썼다가 큰일 나는 {제품군}."


def test_박수_웃음_영문도_걸린다():
    for tag in ("[박수]", "[웃음]", "[Music]", "[Applause]"):
        o = ba.spine_origin(_spine([{"role": "훅", "text": "이거 %s 봐요." % tag}]))
        assert tag not in o["cells"][0]["text"], tag
        assert o["cells"][0]["text"] == "이거 봐요."


def test_잡음이_없으면_원본을_그대로_준다():
    """흔한 길에서 사본을 만들지 않는다(불필요한 복사 방지)."""
    sp = _spine([{"role": "훅", "text": "깨끗한 문장입니다."}])
    o = ba.spine_origin(sp)
    assert o["cells"][0]["text"] == "깨끗한 문장입니다."


def test_원본_dict를_고치지_않는다():
    """호출부가 DB에서 읽은 객체를 그대로 들고 있을 수 있다."""
    raw = {"_origin": {"cells": [{"role": "훅", "text": "아이템이 [음악] 있어."}]}}
    sp = {"templates_json": json.dumps(raw, ensure_ascii=False),
          "templates": raw}
    ba.spine_origin(sp)
    assert "[음악]" in sp["templates"]["_origin"]["cells"][0]["text"]
