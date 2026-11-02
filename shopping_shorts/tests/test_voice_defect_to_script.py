"""목소리 결함(받아쓰기 확정 결함·말속도·이름 끊김)은 재료 질문이 아니라 대본 고치기로(10-27 이브라인 편: L5 TTS 되풀이를
'재료를 고쳐라'로 10번 물어 멈춤 — Claude 는 매번 '재료로는 못 고친다, 문장을 바꿔야' 라고 답했다)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402

OVER = "나레 줄별 받아쓰기 확정 결함: L5 TTS 되풀이: 들림 '을쭉올려보더니' · 글 '이라' — 그 줄 문장을 바꿔 다시 합성"


def _st():
    return {"version": "잇템로그판_v2", "fmt": "해외원본형", "research_md": "", "log": [], "tries": {},
            "_msheets": {"list": [], "sheets": [], "shots": {}}, "script": {"S": {"lines": []}, "M": {"cuts": {}}}}


def test_plan_voice_defect_goes_to_script_not_material():
    st = _st()
    r = F.ph_plan_got(st, {"plan": {"over": OVER}}, {}, {})
    assert r["then"] == "script_got" and r["review"][0]["id"].startswith("script_")
    assert "L5 TTS 되풀이" in r["review"][0]["ask"]


def test_plan_look_voice_defect_even_with_material_answer():
    st = _st()
    st["_plan_over"] = [OVER]
    r = F.ph_plan_look(st, {}, {"plan_잇템로그판_v2": {"ok": False, "problems": ["재료로는 못 고친다"], "재료": {"cuts": {}}}}, {})
    assert r["then"] == "script_got"


def test_string_voice_field_is_dropped_before_plan():
    """10-27 5회차 TV: Claude 가 대본 voice 칸에 목소리 아이디 글자를 적어 계획이 'str'.get 으로 죽음 → 판 목소리로(칸을 지운다)."""
    st = {"version": "두유노판", "fmt": "쇼핑형", "log": [], "tries": {}}
    S = {"voice": "tc_6059dad0b83880769a50502f", "lines": [{"id": "L0", "kind": "tts", "tts": "좋아요.", "caps": [{"text": "좋아요"}]}]}
    F.audit_script(st, S, {"cuts": {}})
    assert "voice" not in S
