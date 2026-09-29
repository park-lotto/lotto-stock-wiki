# -*- coding: utf-8 -*-
"""한 편 안에서 같은 장면을 두 줄에 쓰지 않는다(2026-09-29 고객 제보 커피 영상 — 같은 장면 3~4번)."""
from shopping_shorts import story_writer as sw


def _idx():
    # a0 = 롱폼(근거 컷 1개뿐), b·c = 다른 소스들
    return {
        "a0-1": {"vid": "a0", "secs": 2.0, "desc": "캡슐 붓는 손"},
        "a0-2": {"vid": "a0", "secs": 2.0, "desc": "컵 위 추출"},
        "a0-3": {"vid": "a0", "secs": 2.0, "desc": "컵 위 추출"},       # 태깅이 한 샷을 둘로 가름
        "b1-1": {"vid": "b1", "secs": 2.0, "desc": "흰 본체 들기"},
        "c2-1": {"vid": "c2", "secs": 2.0, "desc": "가방에 넣기"},
    }


def _all_keys(bs, idx):
    out = []
    for b in bs:
        for c in b.get("segs") or []:
            out.append(idx[c]["desc"])
    return out


def test_근거컷이_모자라도_같은_장면을_두_줄에_안_쓴다():
    idx = _idx()
    groups = {"groups": [{"cuts": ["a0-1"]}]}
    lines = [{"text": "순간", "role": "moment", "group": 0},
             {"text": "지옥", "role": "what_happens", "group": 0},
             {"text": "없애 버림", "role": "erased", "group": 0}]
    bs = [{"role": L["role"], "seg": "a0-1", "segs": ["a0-1"]} for L in lines]   # 옛 장면 고정 결과(allowed[:1])
    fixed = sw._no_reuse(lines, bs, idx, "", groups)
    keys = _all_keys(bs, idx)
    assert fixed == 2
    assert len(keys) == len(set(keys)), keys
    assert all(b["segs"] for b in bs)


def test_설명이_같은_컷은_같은_장면으로_본다():
    idx = _idx()
    lines = [{"text": "가", "role": "hook"}, {"text": "나", "role": "bait"}]
    bs = [{"role": "hook", "seg": "a0-2", "segs": ["a0-2"]}, {"role": "bait", "seg": "a0-3", "segs": ["a0-3"]}]
    sw._no_reuse(lines, bs, idx, "", {"groups": []})
    assert bs[1]["segs"] and idx[bs[1]["segs"][0]]["desc"] != "컵 위 추출"


def test_바꿀_컷은_덜_쓴_소스에서():
    idx = _idx()
    lines = [{"text": "가", "role": "hook"}, {"text": "나", "role": "bait"}, {"text": "다", "role": "reveal"}]
    bs = [{"role": "hook", "seg": "a0-1", "segs": ["a0-1", "b1-1"]},
          {"role": "bait", "seg": "a0-2", "segs": ["a0-2"]},
          {"role": "reveal", "seg": "a0-1", "segs": ["a0-1"]}]
    sw._no_reuse(lines, bs, idx, "", {"groups": []})
    assert bs[2]["segs"] == ["c2-1"]          # a0(2번)·b1(1번)보다 안 쓴 c2


def test_남는_컷이_없으면_비워_둔다():
    idx = {"a0-1": {"vid": "a0", "secs": 2.0, "desc": "x"}}
    lines = [{"text": "가", "role": "hook"}, {"text": "나", "role": "bait"}]
    bs = [{"role": "hook", "seg": "a0-1", "segs": ["a0-1"]}, {"role": "bait", "seg": "a0-1", "segs": ["a0-1"]}]
    sw._no_reuse(lines, bs, idx, "", {"groups": []})
    assert bs[1]["segs"] == []
