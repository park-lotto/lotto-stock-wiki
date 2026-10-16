# -*- coding: utf-8 -*-
"""대본 규칙 문장의 주인 = style_writer 한 곳(0순위-B, 관제 097 10-16).
script_engine(소재→대본 엔진)과 style_writer(자막·나레 작가)가 같은 규칙을 두 벌 들고 있었다 → 한 벌로."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy import style_writer as SW  # noqa: E402
from tools.calcopy.engine import script_engine as SE  # noqa: E402


def test_draft_and_fix_prompt_same_string_both_paths():
    assert SE.DRAFT_PROMPT == SW.DRAFT_PROMPT
    assert SE.FIX_PROMPT == SW.FIX_PROMPT


def test_every_prompt_carries_shared_rule_sentences():
    assert SW.rule_fact_ids() in SW.DRAFT_PROMPT
    assert SW.rule_fact_ids("위 [f…]·[o…]·[c…]") in SW.NARR_PROMPT      # 나레도 근거 번호 포함
    for p in (SW.DRAFT_PROMPT, SW.CAP_PROMPT):
        assert SW.RULE_NO_DESCRIBE in p
    assert SW.RULE_ENDING in SW.DRAFT_PROMPT


def test_prompts_still_format():
    SW.DRAFT_PROMPT.format(slug="a", kind="b", topic="c", angle="d", grounds="e", n=1, slots="f", honor="g", honor_rule="h", orig="i")
    SW.NARR_PROMPT.format(topic="t", points="p", orig="o", n=1, structure="s")
    SW.CAP_PROMPT.format(style="s", n=1, topic="t", structure="x", points="p", honorific="반말")
