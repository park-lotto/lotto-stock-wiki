# -*- coding: utf-8 -*-
"""script_engine 설명서 경로(3판, 관제 097 10-16 밤) — 답을 아는 시험.
① 설명서 있는 채널(homedesignnote)은 brief 경로: 창작 허용선·예문·서사 노드가 프롬프트에 들고, 줄마다 shot_kind 가 붙는다(재료.json kind 꼴).
② 설명서 없는 채널(sseolpulda)은 ROLES 폴백 + 경보 로그.
③ 폴드메이트 LOO 2판 초안(channel/homedesignnote/대본설명서/LOO2_시연.json, 사람이 읽은 흠): '절대 안 혼나요' 줄은 최상급 반려,
   가격 줄에서 근거 번호를 빼면 '근거 필수 줄에 번호 없음'으로 반려, '순식간에'(속도 효과) 줄도 근거 필수로 잡힌다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.calcopy import style_writer as SW  # noqa: E402
from tools.calcopy.engine import script_engine as SE  # noqa: E402
from tools.calcopy.engine.topic_find import LLM  # noqa: E402

D = REPO / "channel" / "homedesignnote" / "대본설명서"
LOO2 = json.loads((D / "LOO2_시연.json").read_text(encoding="utf-8"))
FACTS2 = {f["id"]: {"text": f["text"], "url": ""} for f in json.loads((D / "LOO2_상품사실.json").read_text(encoding="utf-8"))["facts"]}
PROD2 = json.loads((D / "LOO2_상품사실.json").read_text(encoding="utf-8"))["product"]


def _fake(lines):
    seen = []

    def fn(prompt, tag):
        seen.append((tag, prompt))
        return {"title": "t", "lines": lines, "_model": "fake"}, None
    return LLM(fn=fn, budget=5), seen


def test_frame_path_uses_brief_and_shot_kinds():
    frame = SE.find_frame("homedesignnote")
    assert frame is not None
    llm, seen = _fake([{"text": "와이프가 이걸 사왔는데 저 이거 보고 바로 버렸어요.", "node": "극단행동", "facts": []},
                       {"text": "잘 펴서 넣어주기만 하면 알아서 접힌대요.", "node": "원리스펙", "facts": ["f4"]}])
    dr = SE.draft(PROD2, frame, FACTS2, llm, "homedesignnote", exclude=("EINoAh8C9rQ",), log=lambda *a: None)
    assert dr["path"] == "frame"
    p = seen[0][1]
    assert SW.RULE_CREATIVE_LINE in p and "[예문]" in p and "결과과장" in p and SW.RULE_NO_SUPERLATIVE in p
    assert all(l["shot_kind"] for l in dr["lines"])
    plan = SE.materials_plan(dr["lines"])
    assert [s["kind"] for s in plan["shots"]] == [l["shot_kind"] for l in dr["lines"]]   # 재료.json shots[i].kind 꼴


def test_no_frame_falls_back_with_alarm():
    logs = []
    llm, seen = _fake([{"fn": "발견", "text": "x", "facts": ["f1"]}])
    assert SE.find_frame("sseolpulda") is None
    dr = SE.draft(PROD2, None, FACTS2, llm, "sseolpulda", log=logs.append)
    assert dr["path"] == "fallback" and dr["roles"] == SE.ROLES["sseolpulda"]
    assert any("[경보]" in m for m in logs)
    assert SE.ROLES["sseolpulda"][0] in seen[0][1]


def test_foldimate_draft_rejected_for_superlative_and_ungrounded():
    lines = [dict(l) for l in LOO2["EINoAh8C9rQ"]["draft_lines"]]
    frame = SE.find_frame("homedesignnote")
    chk = SE.check_frame(lines, frame, FACTS2, [], {}, None, PROD2)
    k_abs = next(k for k, l in enumerate(lines) if "절대" in l["text"])
    assert any("최상급" in w for w in chk["bad"].get(k_abs, [])), chk["bad"]
    k_fast = next(k for k, l in enumerate(lines) if "순식간" in l["text"])
    assert any("근거 필수" in w for w in chk["bad"].get(k_fast, [])), chk["bad"]
    k_price = next(k for k, l in enumerate(lines) if "가격" in l["text"])
    lines[k_price]["facts"] = []
    chk2 = SE.check_frame(lines, frame, FACTS2, [], {}, None, PROD2)
    assert any("근거 필수" in w for w in chk2["bad"].get(k_price, [])), chk2["bad"]
    assert not chk["ok"] and not chk2["ok"]


def test_frame_prompts_format():
    SW.FRAME_FALLBACK_PROMPT.format(slug="s", product="p", slots="a > b", grounds="g")
