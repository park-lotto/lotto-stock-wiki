# -*- coding: utf-8 -*-
"""대본 글 형식 결함은 코드가 고친다(사장님 10-27 "오푸스가 생각하면서 만들고, 코드가 반려 못 하게 수정까지 끝내면 안 되나").
10-27 TV 스탠드 편: 대본 판정 34번(46분) — 줄 끝 부호 없음 ↔ 영문 'TV' 를 opus 가 대본을 통째로 다시 쓰며 번갈아 깨뜨렸다.
줄은 그 편 반려 답에서 그대로 옮겼다."""
from tools.calcopy.hybrid import script_audit as SA


def _script():
    return {"lines": [
        {"id": "L1", "kind": "tts", "tts": "전셋집이라 벽에 TV 구멍을 못 뚫겠더라고요",
         "caps": [{"text": "전셋집이라 벽에"}, {"text": "TV 구멍을 못 뚫겠더라고요", "key": "못 뚫겠더라고요"}]},
        {"id": "L2", "kind": "tts", "tts": "원래 TV 고정해 두던 사람도 막상 써 보면 자리를 자주 옮기게 된대요",
         "caps": [{"text": "원래 TV 고정해 두던 사람도"}, {"text": "막상 써 보면 자리를 자주 옮긴대요"}]},
        {"id": "L3", "kind": "tts", "tts": "바퀴 잠그고 화면만 휙 돌려요."},
    ]}


def test_old_script_is_rejected():
    rules = {x["rule"] for x in SA.text_defects(_script())}
    assert {"end_mark", "latin", "caps_say"} <= rules


def test_text_fix_leaves_nothing_to_reject():
    S = _script()
    fixed = SA.text_fix(S)
    assert fixed
    assert SA.text_defects(S) == []
    assert "TV" not in S["lines"][0]["tts"] and "티비" in S["lines"][0]["tts"]
    assert S["lines"][0]["caps"][1]["text"].startswith("TV")       # 자막은 원문 그대로
    assert S["lines"][0]["caps"][1]["key"] == "못 뚫겠더라고요"        # 강조 칸 유지


def test_text_fix_is_idempotent():
    S = _script()
    SA.text_fix(S)
    assert SA.text_fix(S) == []
