"""괄호 지문 줄은 TTS 하지 않는다(표 #230, Jev 해결 0.54·0.54·위험 0.28·0.27 · 11-06).

판단 = kal_analyze.is_stage_direction(줄 통째 괄호). 줄 일부 괄호(뜻풀이 'PPL(광고)')는 지문이 아니다.
make 관문 kal.paren_gate 가 TTS 줄(원음 줄 제외)에서 잡아 failed + 줄 번호. 줄판독 초안에 _jimun 표시.
"""
import json

from tools.calcopy.engine import kal
from tools.calcopy.engine import kal_analyze as KA


def test_is_stage_direction():
    assert KA.is_stage_direction("(바로 퀵 전화해봄)")
    assert KA.is_stage_direction(" (20분 후 기사님 전화옴) ")
    assert KA.is_stage_direction("[쾅]")
    assert not KA.is_stage_direction("PPL(광고) 안받고")
    assert not KA.is_stage_direction("삘(Feel) 제대로 받았다는데 ㅋㅋㅋ")
    assert not KA.is_stage_direction("")


def test_paren_gate(tmp_path):
    (tmp_path / "대본.json").write_text(json.dumps({"lines": [
        {"text": "첫 줄"}, {"text": "(후다닥)"}, {"text": "(원음 지문)", "kind": "orig", "src": "a", "spans": []},
        {"text": "이걸(채소보관용기) 팔더라고요"}]}, ensure_ascii=False), encoding="utf-8")
    got = kal.paren_gate(tmp_path)
    assert len(got) == 1 and got[0].startswith("2줄")


def test_skeleton_marks_jimun():
    import inspect
    assert "_jimun" in inspect.getsource(KA)          # 초안 표시 칸(기계값) — check_doc 이 '_' 칸은 사람 칸으로 안 본다
