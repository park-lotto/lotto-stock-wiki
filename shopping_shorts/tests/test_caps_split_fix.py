"""자막 덩어리 자수는 형식 일 — 대본을 다시 쓰게 돌려보내지 않고 바로 나눈다(사장님 10-27 '걸림이 생기는 걸 없애라').

주인: rules.caps_split_fix(판 script.audit cap_chars 상한 — 나레 caption.chunk_max_chars · 원음 그 칸 max) · 끊는 자리 = rules._cap_cut.
옛 코드: 상한 넘는 덩어리를 script_audit 이 반려 → 회원 Claude 가 대본을 다시 씀(10-27 립글로스 회원편 '자막이 길어서 나누는 중').
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import rules as RU  # noqa: E402
from tools.calcopy.hybrid.common import nchar  # noqa: E402

ST = {"caption": {"chunk_max_chars": 9},
      "script": {"audit": [{"kind": "cap_chars", "max": "chunk_max_chars", "of": "tts"}, {"kind": "cap_chars", "max": 14, "of": "orig"}]}}


def test_long_tts_cap_is_split_at_word_ending():
    S = {"lines": [{"id": "L1", "kind": "tts", "caps": ["백탁 없다는 한국 선크림을 바르고"]}]}
    assert RU.caps_split_fix(S, ST)
    assert S["lines"][0]["caps"] == ["백탁 없다는", "한국 선크림을 바르고"]
    assert all(nchar(c) <= 9 for c in S["lines"][0]["caps"])


def test_key_stays_on_piece_with_word_and_orig_uses_own_max():
    S = {"lines": [{"id": "L1", "kind": "tts", "caps": [{"text": "충격 받은 외국인이 있는데요", "key": "충격"}]},
                   {"id": "O1", "kind": "orig", "caps": ["말도 안 돼 진짜야"]}]}
    RU.caps_split_fix(S, ST)
    assert S["lines"][0]["caps"] == [{"text": "충격 받은", "key": "충격"}, "외국인이 있는데요"]
    assert S["lines"][1]["caps"] == ["말도 안 돼 진짜야"]          # 원음 상한 14 안 — 그대로


def test_words_order_kept():
    S = {"lines": [{"id": "L2", "kind": "tts", "caps": ["아무리 발라도 하얗게 안 뜬다는 말에"]}]}
    RU.caps_split_fix(S, ST)
    assert " ".join(S["lines"][0]["caps"]) == "아무리 발라도 하얗게 안 뜬다는 말에"
