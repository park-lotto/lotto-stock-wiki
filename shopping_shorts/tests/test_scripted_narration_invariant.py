"""확정 대본에 없는 문장을 EDL이 지어내면 되돌린다(2026-08-18 실사고 재현)."""
from shopping_shorts.edit_plan import enforce_scripted_narration, script_sentences

SCRIPT = (
    "게임 좋아하는 남편이 요즘 폰만 붙잡고 있길래 뭐 하나 봤더니, 스마트폰을 아예 "
    "휴대용 게임기로 바꿔버리는 걸 보고 제가 다 놀랐잖아요! "
    "원래는 터치로만 게임을 하니까 조작감도 너무 밋밋하고, 손맛이 전혀 없어서 맨날 금방 질려 하더라고요. "
    "근데 이건 스마트폰 하단에 바로 끼우는 물리 직결 방식이라 페어링 지연이 아예 없어요."
)


def test_창작된_훅을_빠진_대본문장으로_되돌린다():
    beats = [
        {"role": "hook", "narration": "스마트폰에 어댑터를 장착해 휴대용 게임기처럼 사용하는 모습이 정말 신기하네요."},
        {"role": "problem", "narration": "원래는 터치로만 게임을 하니까 조작감도 너무 밋밋하고, 손맛이 전혀 없어서 맨날 금방 질려 하더라고요."},
        {"role": "solution", "narration": "근데 이건 스마트폰 하단에 바로 끼우는 물리 직결 방식이라 페어링 지연이 아예 없어요."},
    ]
    out, n = enforce_scripted_narration(beats, SCRIPT)
    assert n == 1
    assert out[0]["narration"].startswith("게임 좋아하는 남편이")
    assert out[0].get("narration_restored") is True


def test_대본을_지킨_계획은_건드리지_않는다():
    beats = [{"role": "problem", "narration": "원래는 터치로만 게임을 하니까 조작감도 너무 밋밋하고,"}]
    out, n = enforce_scripted_narration(beats, SCRIPT)
    assert n == 0 and out[0]["narration"].startswith("원래는 터치로만")


def test_되돌릴_문장이_없으면_흔적을_남긴다():
    """대본이 이미 전부 화면에 쓰였는데도 창작 비트가 남으면 표시만 남기고 지우지 않는다."""
    beats = [{"role": "problem", "narration": "짧은 대본."},
             {"role": "hook", "narration": "여기 없는 완전히 다른 문장입니다."}]
    out, n = enforce_scripted_narration(beats, "짧은 대본.")
    assert n == 0
    assert out[1].get("narration_invented") is True
    assert out[1]["narration"] == "여기 없는 완전히 다른 문장입니다."   # 지우지 않는다


def test_확정대본이_없으면_아무것도_안_한다():
    beats = [{"narration": "자유 생성 문장"}]
    assert enforce_scripted_narration(beats, "") == (beats, 0)


def test_문장분리():
    assert len(script_sentences("가나다. 라마바! 사아자?")) == 3


def test_되돌린_비트는_옛_음성을_버린다():
    """2026-08-19 실사고(잡 c5249702331d beat2): 대본만 되돌리고 mp3를 남겨서
    화면 대본과 소리가 어긋났다 — 미리보기가 409로 막혀 '음성이 없다'로 보였다."""
    beats = [
        {"role": "problem", "narration": "둥근 글씨를 정성스럽게 써 내려갑니다",
         "tts_path": "/w/tts/beat_0_b78d7c7f5f.mp3",
         "caption_lines": ["옛", "자막"], "cap_durs": [1.0, 2.0], "cap_lead": 0.4},
    ]
    out, n = enforce_scripted_narration(beats, SCRIPT)
    assert n == 1
    assert out[0].get("narration_restored") is True
    assert "tts_path" not in out[0], "되돌렸는데 옛 음성이 남았다"
    assert out[0]["caption_lines"] is None and out[0]["cap_durs"] is None
    assert out[0]["cap_lead"] == 0.0


def test_대본을_지킨_비트의_음성은_건드리지_않는다():
    beats = [{"role": "problem", "narration": "원래는 터치로만 게임을 하니까 조작감도 너무 밋밋하고,",
              "tts_path": "/w/tts/beat_0_aaaaaaaaaa.mp3"}]
    out, n = enforce_scripted_narration(beats, SCRIPT)
    assert n == 0 and out[0]["tts_path"] == "/w/tts/beat_0_aaaaaaaaaa.mp3"
