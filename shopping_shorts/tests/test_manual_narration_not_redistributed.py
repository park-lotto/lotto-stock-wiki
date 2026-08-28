"""사람이 고친 대본은 저장 출구가 다시 흔들지 않는다 (2026-08-28 사장님 제보).

제보: "tts음성 단계에서 자막을 수정하니까 니멋대로 기존자막이 위로 붙고 아래로 붙고
      그대로 남아요"

실측한 라이브 사례:
  job 85a4a28c702a — beat7을 "이 과일 궁금하면 댓글에 '프른' 남겨주세요 알려드릴게요."
    로 고쳤는데, beat5="이 방법 궁금하면 댓글에 '나도' 남겨주세요" / beat6="알려드릴게요."
    가 자동으로 꽂혀 있었다(= 지운 옛 문장이 위·아래로 쪼개져 붙었다).
  job 0e5b770d3656 — beat2가 beat0+beat1을 합친 옛 문장 그대로.

뿌리: enforce_script_order가 고친 칸을 대상에서 빼되, **그 칸 몫의 대본 문장을
'누락 금지'로 남은 칸에 다시 배분**한다. 칸 단위로 표식을 존중하는 것만으론 못 막는다.
"""
import pytest

from shopping_shorts import edit_plan as ep


SCRIPT = ("묵직한 아랫배 때문에 고생하시는 분들, 이거 모르면 손해예요. "
          "솔직히 전에는 화장실 가는 것 하나 때문에 일상이 엉망이었거든요. "
          "이 방법 궁금하면 댓글에 '나도' 남겨주세요 알려드릴게요.")


def _beats():
    return [
        {"beat_idx": 0, "target_seconds": 4.0,
         "narration": "묵직한 아랫배 때문에 고생하시는 분들, 이거 모르면 손해예요."},
        {"beat_idx": 1, "target_seconds": 4.0,
         "narration": "솔직히 전에는 화장실 가는 것 하나 때문에 일상이 엉망이었거든요."},
        {"beat_idx": 2, "target_seconds": 3.0,
         "narration": "이 방법 궁금하면 댓글에 '나도' 남겨주세요 알려드릴게요."},
    ]


def test_order_enforcer_redistributes_the_edited_sentence():
    """★뿌리 재현 — 고친 칸의 옛 문장이 남은 칸으로 흘러간다."""
    beats = _beats()
    beats[2]["narration"] = "이 과일 궁금하면 댓글에 '프른' 남겨주세요."
    beats[2]["narration_manual"] = True
    out, _ = ep.enforce_script_order([dict(b) for b in beats], SCRIPT)
    moved = "'나도'" in (out[0]["narration"] + out[1]["narration"])
    assert moved, "이 테스트가 깨지면 뿌리가 바뀐 것 — 아래 게이트를 다시 확인하라"


def _ensured(beats, script=SCRIPT):
    """저장 출구(store._ensure_screen_time)를 그 형태 그대로 부른다."""
    from shopping_shorts import store as st

    class _FakeStore:
        def get_mix_job(self, job_id):
            return {"given_script": script,
                    "extract": {"v1": {"segments": [
                        {"seg_id": f"v1_{i}", "start": i * 5, "end": i * 5 + 5,
                         "text": "", "scene_desc": "장면", "label": "",
                         "use_point": "", "action": None, "change": ""}
                        for i in range(6)]}},
                    "script_structure": {}}

    seg_map, _ = ep._build_inventory(
        [{"video_id": "v1",
          "segments": _FakeStore().get_mix_job("job")["extract"]["v1"]["segments"]}])
    assert seg_map, "하네스가 어긋났다 — _ensure_screen_time이 조기 반환하면 전부 가짜 통과다"
    return st._ensure_screen_time({"beats": beats}, _FakeStore(), "job")


def test_edited_plan_is_left_alone():
    """사람이 고친 계획은 저장 출구가 대사를 하나도 안 바꾼다."""
    beats = _beats()
    beats[2]["narration"] = "이 과일 궁금하면 댓글에 '프른' 남겨주세요."
    beats[2]["narration_manual"] = True
    before = [b["narration"] for b in beats]
    out = _ensured([dict(b) for b in beats])
    assert [b["narration"] for b in out["beats"]] == before


def test_edited_beat_survives_verbatim():
    """고친 문장 자체가 글자 하나 안 틀리고 남아야 한다."""
    beats = _beats()
    mine = "이 과일 궁금하면 댓글에 '프른' 남겨주세요 알려드릴게요."
    beats[2]["narration"] = mine
    beats[2]["narration_manual"] = True
    out = _ensured([dict(b) for b in beats])
    assert out["beats"][2]["narration"] == mine


def test_old_sentence_does_not_reappear_anywhere():
    """★제보의 핵심 — 지운 옛 문장이 다른 칸에 나타나면 안 된다."""
    beats = _beats()
    beats[2]["narration"] = "이 과일 궁금하면 댓글에 '프른' 남겨주세요."
    beats[2]["narration_manual"] = True
    out = _ensured([dict(b) for b in beats])
    joined = " ".join(b["narration"] for b in out["beats"])
    assert "'나도'" not in joined, "옛 문장이 위·아래 칸으로 흘러갔다"


def test_untouched_plan_still_guarded():
    """★AI 창작 방어는 살아 있어야 한다 — 사람 손이 안 닿은 계획은 그대로 검사한다."""
    beats = _beats()
    beats[0]["narration"] = "이 장면은 고양이가 화장실에 들어가는 모습입니다."   # EDL 창작
    out = _ensured([dict(b) for b in beats])
    assert out["beats"][0]["narration"] != "이 장면은 고양이가 화장실에 들어가는 모습입니다."


def test_one_manual_beat_disables_the_guard_for_the_whole_plan():
    """표식이 하나라도 있으면 계획 전체가 사람 것이다(칸 단위로는 못 막는다 — 위 재현 참조)."""
    beats = _beats()
    beats[0]["narration"] = "이 장면은 고양이가 화장실에 들어가는 모습입니다."
    beats[2]["narration_manual"] = True
    out = _ensured([dict(b) for b in beats])
    assert out["beats"][0]["narration"] == "이 장면은 고양이가 화장실에 들어가는 모습입니다."


def test_screen_time_still_filled():
    """대사만 안 건드리는 것이지, 화면 길이 채우기는 계속 돌아야 한다."""
    beats = _beats()
    beats[2]["narration_manual"] = True
    out = _ensured([dict(b) for b in beats])
    assert len(out["beats"]) == 3 and all("narration" in b for b in out["beats"])
