"""장면 점검(관제 257) — storyboard.scene_review 가 AI 판정을 코드로 거르는지, 대화창이 장면 요청을 넘기는지."""
import pytest

from shopping_shorts import script_chat, storyboard as sb

SEGS = {"a1": 2.0, "a2": 1.5, "b1": 3.0, "b2": 2.5, "c1": 1.2}
TEXTS = {k: "설명 " + k for k in SEGS}
ORDER = list(SEGS)
ROWS = ["  %s | %.1f초 | 설명 %s | 쓰임:- | 소구점:-" % (k, v, k) for k, v in SEGS.items()]
MATS = (SEGS, TEXTS, ORDER, ROWS)
SLOTS = [
    {"slot": "hook", "line": "이거 하나면 끝나요", "ids": ["a1"]},
    {"slot": "problem", "line": "얼룩이 안 지워져서 고생했죠", "ids": ["a2"]},
    {"slot": "method", "line": "", "ids": []},
    {"slot": "cta", "line": "지금 확인해 보세요", "ids": ["b1"]},
]


def _calls(*answers):
    seen = []

    def call(prompt, schema):
        seen.append(prompt)
        return answers[min(len(seen) - 1, len(answers) - 1)]
    return call, seen


def test_keep_and_rows_default_skip_empty():
    call, seen = _calls({"reply": "대부분 맞아요", "reviews": [
        {"line_no": 1, "verdict": "keep", "why": "a1 이 끝나는 장면"},
        {"line_no": 2, "verdict": "keep", "why": "a2 얼룩"},
        {"line_no": 4, "verdict": "keep", "why": "b1 제품"}]})
    r = sb.scene_review(SLOTS, None, MATS, call=call)
    assert [v["i"] for v in r["reviews"]] == [0, 1, 3]      # 빈 줄(3번)은 점검하지 않는다
    assert all(v["verdict"] == "keep" and v["ids"] == [] for v in r["reviews"])
    assert r["reviews"][0]["cur_ids"] == ["a1"]
    assert "[다른 줄 사용중: 1번]" in seen[0]                  # 다른 줄이 쓰는 조각을 AI 에게 알린다
    assert len(seen) == 1


def test_swap_filters_bad_and_used_ids():
    call, _ = _calls({"reply": "", "reviews": [
        {"line_no": 2, "verdict": "swap", "why": "b2 가 얼룩을 보여줌", "ids": ["zz", "b1", "b2", "b2"]}]})
    v = sb.scene_review(SLOTS, [1], MATS, call=call)["reviews"][0]
    # zz = 목록 밖, b1 = 4번 줄이 쓰는 중, 중복 b2 한 번만
    assert v["verdict"] == "swap" and v["ids"] == ["b2"]
    assert v["have"] == 2.5 and v["cur_ids"] == ["a2"]


def test_swap_same_as_current_becomes_keep():
    call, _ = _calls({"reply": "", "reviews": [{"line_no": 1, "verdict": "swap", "why": "그대로가 낫다", "ids": ["a1"]}]})
    v = sb.scene_review(SLOTS, [0], MATS, call=call)["reviews"][0]
    assert v["verdict"] == "keep" and v["ids"] == []


def test_unusable_swap_retries_then_ok():
    call, seen = _calls({"reply": "", "reviews": [{"line_no": 1, "verdict": "swap", "why": "x", "ids": ["b1"]}]},
                        {"reply": "", "reviews": [{"line_no": 1, "verdict": "swap", "why": "c1 이 더 맞다", "ids": ["c1"]}]})
    v = sb.scene_review(SLOTS, [0], MATS, call=call)["reviews"][0]
    assert len(seen) == 2 and "다시 판정하라" in seen[1]
    assert v["verdict"] == "swap" and v["ids"] == ["c1"]


def test_missing_row_marked_error_not_silent():
    call, seen = _calls({"reply": "", "reviews": [{"line_no": 1, "verdict": "keep", "why": "맞음"}]})
    r = sb.scene_review(SLOTS, [0, 1], MATS, call=call)
    assert len(seen) == 2
    assert [v["verdict"] for v in r["reviews"]] == ["keep", "error"]


def test_none_with_line():
    call, _ = _calls({"reply": "", "reviews": [{"line_no": 4, "verdict": "none", "why": "구매 화면이 없다", "line": "이 제품 한번 보세요"}]})
    v = sb.scene_review(SLOTS, [3], MATS, call=call)["reviews"][0]
    assert v["verdict"] == "none" and v["line"] == "이 제품 한번 보세요" and v["ids"] == []


def test_all_fail_raises():
    call, _ = _calls({})
    with pytest.raises(ValueError):
        sb.scene_review(SLOTS, [0], MATS, call=call)


def test_empty_materials_raises():
    with pytest.raises(ValueError):
        sb.scene_review(SLOTS, [0], ({}, {}, [], []), call=lambda p, s: {})


def test_chat_flags_scene_request():
    r = script_chat.revise(["가", "나", "다"], "2번째 줄 장면 더 역동적인 걸로",
                           call=lambda p, s: {"reply": "장면을 점검할게요", "edit": False, "scenes": True, "scene_rows": [2, 9]})
    assert r["scenes"] is True and r["scene_rows"] == [1] and r["changed"] == []


def test_chat_no_scene_flag_by_default():
    r = script_chat.revise(["가", "나"], "이 대본 어때?", call=lambda p, s: {"reply": "좋아요", "edit": False})
    assert r["scenes"] is False and r["scene_rows"] == []


def test_only_row_scene_request_not_error():
    r = script_chat.revise(["가", "나"], "장면 바꿔줘", only=1,
                           call=lambda p, s: {"reply": "", "edit": False, "scenes": True})
    assert r["scenes"] is True and r["scene_rows"] == [1] and r["lines"] == ["가", "나"]


def test_why_ids_become_scene_names():
    texts = {"grab_youtube_94f4e8849925-3": "티셔츠가 부풀어 오르며 마른다. 바람이", "grab_youtube_aa11bb22cc33-0": "바지"}
    w = sb._sr_names("기존 grab_youtube_94f4e8849925-3은 티셔츠, aa11bb22cc33-0(바지)로", texts)
    assert "grab_" not in w and "94f4e8849925" not in w and "aa11bb22cc33" not in w
    assert "「티셔츠가 부풀어 오르며 마른다」" in w and "「바지」" in w
