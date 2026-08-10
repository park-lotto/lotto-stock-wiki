"""증거검증형 날조 검사(2026-08-10) — job 890c2f41e35a 실사고 기반.

핵심 계약: LLM이 뭐라고 답하든, ①대본에 실재하고 ②원본 소재에 없는
인용(6자+)만 유효 — 오탐이 회귀를 못 만든다.
"""
import re
from pathlib import Path

from shopping_shorts import single_source as ss

MAT = ("이거 만든 사람 진짜 천재 아닌가요? 친구만 카페를 하는데요 역대급 디저트가 "
       "나왔다고 먹어보라더니 이게 뭐냐니까 그냥 우유 구운거야 가격이 만원이라 "
       "레시피 받아서 조카 간식으로 해주니까 댓글에 우유 남겨주세요")

BEATS = [
    {"n": 1, "covers": [1], "narration": "카페 하는 친구가 케이크 만드는 법을 알려주더라고요."},
    {"n": 2, "covers": [2], "narration": "굳혀 썰어 에어프라이어에 돌리면 끝이에요."},
    {"n": 3, "covers": [3], "narration": "가격이 만원이라 좀 비싸긴 해요."},
]


def _call_returning(items):
    def call(prompt, schema):
        return {"fabrications": items}
    return call


def test_verified_fabrication_kept():
    fabs = ss.fact_fabrications(
        BEATS, MAT, _call_returning([{"quote": "에어프라이어에 돌리면", "reason": "원본에 없음"}]))
    assert fabs == ["에어프라이어에 돌리면"]


def test_quote_present_in_material_dropped():
    # 오탐 보호: 원본에 있는 사실을 날조라고 찍어도 코드가 버린다.
    fabs = ss.fact_fabrications(
        BEATS, MAT, _call_returning([{"quote": "가격이 만원이라", "reason": "x"}]))
    assert fabs == []


def test_quote_not_in_script_dropped():
    # 모델이 인용 대신 바꿔 쓰면 무효.
    fabs = ss.fact_fabrications(
        BEATS, MAT, _call_returning([{"quote": "오븐에 굽는다", "reason": "x"}]))
    assert fabs == []


def test_short_quote_dropped():
    fabs = ss.fact_fabrications(
        BEATS, MAT, _call_returning([{"quote": "케이크", "reason": "x"}]))
    assert fabs == []


def test_whitespace_insensitive_match():
    # 공백 차이는 무시하고 대본/소재 대조.
    fabs = ss.fact_fabrications(
        BEATS, MAT, _call_returning([{"quote": "에어프라이어에  돌리면", "reason": "x"}]))
    assert fabs and "에어프라이어" in fabs[0]


def test_call_failure_returns_empty():
    def boom(p, s):
        raise RuntimeError("429")
    assert ss.fact_fabrications(BEATS, MAT, boom) == []


def test_empty_inputs_return_empty():
    assert ss.fact_fabrications([], MAT, _call_returning([])) == []
    assert ss.fact_fabrications(BEATS, "", _call_returning([])) == []
    assert ss.fact_fabrications(BEATS, MAT, None) == []


def test_fix_prompt_lists_quotes_and_locks_cta():
    p = ss.fix_fabrication_prompt(BEATS, MAT, ["에어프라이어에 돌리면"])
    assert "에어프라이어에 돌리면" in p
    assert "CTA" in p and "covers" in p


def test_wiring_locked_in_edit_plan():
    # 배선 잠금: 두 경로(1소스·scene_first) 모두 fact_fabrications를 부른다.
    src = Path(ss.__file__).with_name("edit_plan.py").read_text(encoding="utf-8")
    assert src.count("fact_fabrications(") >= 2
    assert src.count('SCRIPT_FACT_GATE') >= 2


# ── 사실표(v7) ───────────────────────────────────────────────────────────────

def test_factsheet_block_empty_is_noop():
    assert ss.factsheet_block([]) == ""
    assert ss.factsheet_block(None) == ""


def test_build_factsheet_failure_returns_empty():
    def boom(p, s):
        raise RuntimeError("429")
    assert ss.build_factsheet(MAT, boom) == []
    assert ss.build_factsheet("", _call_returning([])) == []
    assert ss.build_factsheet(MAT, None) == []


def test_build_factsheet_returns_trimmed_facts():
    def call(p, s):
        return {"facts": [" 이름: 우유 구운 것 ", "", "가격은 만원", 3]}
    assert ss.build_factsheet(MAT, call) == ["이름: 우유 구운 것", "가격은 만원"]


def test_factsheet_injected_into_prompts():
    blk = ss.factsheet_block(["이름: 우유 구운 것"])
    order = [{"seg_id": "s", "_dur": 3.0, "scene_desc": "", "text": "", "is_key": False}]
    p1 = ss.script_prompt(order, 10.0, "훅블록", facts_block=blk)
    p2 = ss.restyle_prompt([{"narration": "문장"}], facts_block=blk)
    assert "사실표" in p1 and "우유 구운 것" in p1
    assert "사실표" in p2 and "우유 구운 것" in p2
    # 무주입이면 종전과 동일(사실표 흔적 없음)
    assert "사실표" not in ss.script_prompt(order, 10.0, "훅블록")


def test_factsheet_wiring_locked_in_edit_plan():
    src = Path(ss.__file__).with_name("edit_plan.py").read_text(encoding="utf-8")
    assert src.count("SCRIPT_FACTSHEET") >= 2          # 1소스 + scene_first
    assert src.count("facts_block=_facts_block") >= 2   # 생성 + 리스타일(1소스)
    assert src.count("facts_block=_sf_facts_block") >= 6  # scene_first 리스타일1+생성5(2026-08-10 믹스 접지)
