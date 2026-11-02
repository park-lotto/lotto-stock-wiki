"""server_ai._clip_json — 응답 모양이 {"text"}든 옛 {"clips":[…]}든 글이 빈칸으로 둔갑하지 않는다(10-18 CLI 빈 글 사고)."""
from tools.calcopy.hybrid import server_ai as S
from tools.calcopy.engine import gemini_server as E


def test_text_shape():
    assert S._clip_json({"json": {"text": "가나", "speakers": 1}})["text"] == "가나"


def test_old_clips_shape():
    j = S._clip_json({"json": {"clips": [{"i": 0, "text": "다라", "speakers": 2}]}})
    assert j["text"] == "다라" and j["speakers"] == 2


def test_list_and_raw():
    assert S._clip_json({"json": [{"text": "마"}]})["text"] == "마"
    assert S._clip_json({"text": "바"})["text"] == "바"


def test_prompt_single_owner():
    assert S.ASR_PROMPT is E.ASR_PROMPT
