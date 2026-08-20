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


def test_구어체_대본도_칸별로_쪼개진다():
    """★2026-08-20 실사고(job 087e03b69dc2). 스파인이 뽑는 8칸 구어체 대본은 칸 사이가
    종결어미로만 끊겨 마침표가 하나뿐이다. 마침표만 보던 분리기는 2조각(141자·131자)으로만
    잘랐고, 그 덩이가 2.9초짜리 hook 칸에 통째로 들어가 화면·음성 초가 어긋났다
    ('끝나고 계속 반복'). 칸 수만큼 갈라져야 한다."""
    from shopping_shorts.edit_plan import script_sentences
    script = ("여러분 다이소 가면 이거 무조건 사오세요 "
              "아니 아무리 닦아도 안 지워지는 샤워부스 물때 때문에 진짜 스트레스였거든요 "
              "저희 언니가 다이소 점장인데 뿌옇게 굳은 샤워부스 물때 잡는 걸로 가장 많이 나가는 게 바로 이 제품이라는 거예요 "
              "방법도 진짜 간단해요. 크림을 스펀지에 묻혀 살살 문지르기, 이게 끝이에요 "
              "와 뿌옇게 굳은 샤워부스 물때부터 운동화까지 뿌옇던 유리가 새것처럼 투명해지는 거 있죠 "
              "심지어 저렴한 가격밖에 안 해서 더 놀랐어요 "
              "댓글에 정보 남겨주시면 제품 정보 바로 보내드릴게요")
    parts = script_sentences(script)
    assert len(parts) >= 7, f"구어체 대본이 {len(parts)}조각으로만 잘렸다 — 칸에 덩이가 들어간다"
    assert max(len(p) for p in parts) < 80, "조각 하나가 너무 길다 — 칸 예산을 넘긴다"


def test_칸_예산을_넘는_조각은_안_꽂는다():
    """분리가 또 실패해도(새 말투·외국어) 덩이를 칸에 통째로 넣지 않는다 — 2차 방어."""
    from shopping_shorts.edit_plan import enforce_scripted_narration
    long_script = "아주아주 긴 한 문장인데 마침표가 없어서 통째로 남는 대본이다" * 6
    beats = [{"beat_idx": 0, "narration": "EDL이 지어낸 문장", "target_seconds": 2.9}]
    out, fixed = enforce_scripted_narration(beats, long_script)
    assert fixed == 0, "예산의 두 배가 넘는 덩이를 꽂았다"
    assert out[0].get("narration_invented"), "못 되돌렸다는 표시가 없다"
