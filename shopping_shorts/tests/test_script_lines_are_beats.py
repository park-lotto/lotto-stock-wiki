"""줄 모드 — 2단계가 나눠 준 칸(줄)이 곧 3단계 칸이다 (2026-09-03).

실사고(job 8b86200f50b3): B안 8줄(첫말/문제/반전/증거/시연/결과/가격/약속)이 공백으로
이어져 서버에 갔고, EDL이 9칸으로 다시 잘라 첫말+문제가 훅 한 칸(5.5초)에 뭉쳤다.
"""
from shopping_shorts import edit_plan as ep

LINES = [
    "여러분 다이소 가면 이거 무조건 사오세요.",
    "필기하다 틀리면 화이트 칠하고 지저분해져서 스트레스였거든요.",
    "제 지인이 다이소 매니저로 있거든요.",
    "학생들 사이에서 지워지는 젤펜 중 가장 핫한 게 이 제품이라네요.",
    "펜 뒤 팁으로 슥 문지르면 흔적도 없이 사라져요. 이게 끝이에요.",
    "와 글씨가 깨끗하게 지워지는 거 있죠. 필기감도 부드럽더라고요.",
    "심지어 이 퀄리티에 가격도 착해서 더 놀랐어요.",
    "어떤 제품인지 궁금하시면 댓글 남겨주세요. 정보 알려드릴게요.",
]
SCRIPT = "\n".join(LINES)


def _beat(i, narr, sec):
    return {"role": "r%d" % i, "narration": narr, "target_seconds": sec,
            "primary": {"seg_id": "s%d" % i}, "alternates": []}


def test_lines_are_units_not_sentences():
    assert ep.script_sentences(SCRIPT) == LINES
    # 줄이 없는 통짜 대본은 종전대로 문장 분리
    assert len(ep.script_sentences(" ".join(LINES))) > len(LINES)


def test_nine_ai_beats_fold_to_eight_lines_one_to_one():
    # 실사고 모양: 훅에 두 줄이 뭉치고, 5번째 줄은 두 칸으로 갈렸다
    ai = [_beat(0, LINES[0] + " " + LINES[1], 5.5), _beat(1, LINES[2], 2.1),
          _beat(2, LINES[3], 3.7), _beat(3, "펜 뒤 팁으로 슥 문지르면 흔적도 없이 사라져요.", 2.7),
          _beat(4, "이게 끝이에요.", 0.8), _beat(5, LINES[5], 3.2), _beat(6, LINES[6], 2.5),
          _beat(7, "어떤 제품인지 궁금하시면 댓글 남겨주세요.", 2.2), _beat(8, "정보 알려드릴게요.", 1.3)]
    beats, fixed = ep.enforce_script_order(ai, SCRIPT)
    assert len(beats) == 8
    assert [b["narration"] for b in beats] == LINES
    # 접힌 칸의 화면은 앞 칸 alternates로 살아 있다
    # 줄4(두 칸으로 갈렸던 줄)는 s3+s4, 줄8은 s7+s8 화면을 모아 갖는다
    assert beats[4]["primary"]["seg_id"] == "s3" and [a["seg_id"] for a in beats[4]["alternates"]] == ["s4"]
    assert beats[7]["primary"]["seg_id"] == "s7" and [a["seg_id"] for a in beats[7]["alternates"]] == ["s8"]
    # 두 줄이 뭉쳤던 훅 칸(s0)은 첫 줄이 갖고, 둘째 줄도 화면 없이 남지 않는다
    assert beats[0]["primary"]["seg_id"] == "s0" and beats[1]["primary"] is not None
    assert all(b["target_seconds"] > 0 for b in beats)
    assert fixed >= 1


def test_prompt_states_one_line_one_beat():
    p = ep._SCRIPTED_PROMPT
    assert "{line_rule}" in p
