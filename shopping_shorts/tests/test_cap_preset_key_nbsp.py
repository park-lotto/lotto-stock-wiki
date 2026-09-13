"""대사에 NBSP가 섞여도 자막 경계 나누기가 저장된다 (2026-09-13 고객 제보).

증상: 제작소 3단계(영상대본MIX) 칸 타임라인에서 [✂ 경계]를 켜고 어절 사이 `·`를 눌러도
      **1챕터(hook)만** 아무 일이 안 일어났다. 2챕터는 정상 — "챕터마다 다르다".

실측(job e020944ae71f, 고객 work 7bf7d05fafbe):
  beat 0 narration = '여러분 대파 썰어서 절대 냉동실에\xa0 그냥 넣지 마세요.'  ← NBSP 있음(실패)
  beat 1 narration = '대파가 한 덩어리로 얼어붙어 매번 속상했거든요.'          ← NBSP 없음(정상)

뿌리: 화면(scene_timeline.js tlGapClick)은 어절을 `\\s+`로 쪼개는데 그 정규식은 NBSP도
공백으로 보고 지운다 → 다시 이어붙인 lines에는 NBSP가 없다. 그런데 대조 키(cap_preset_key)는
ASCII 공백 4종만 뗐으므로 narration 쪽 키에만 NBSP가 남아 **키가 영영 달랐다**.
→ POST caplines가 422('글자가 달라졌습니다')로 거절 → 버튼을 눌러도 아무 일이 없다.
붙여넣은 대사에 NBSP는 흔하므로 특정 칸만 조용히 막히는 형태로 재발한다.

저장(app.py _caplines_locked)·렌더(_caption_segments)·대본(script_generate)이 모두 이
함수 하나를 쓰므로(0순위-B) 여기만 고치면 세 경로가 함께 풀린다.
"""
import re

from shopping_shorts.video_assemble import _caption_segments, cap_preset_key

# 고객 잡 e020944ae71f의 실제 대사 그대로(NBSP 포함) — 지어내지 않는다.
_HOOK_NBSP = "여러분 대파 썰어서 절대 냉동실에\xa0 그냥 넣지 마세요."
_OK_PLAIN = "대파가 한 덩어리로 얼어붙어 매번 속상했거든요."


def _split_like_browser(narr, cut):
    """화면이 하는 것과 똑같이 — `\\s+`로 쪼개고 보통 공백으로 다시 잇는다."""
    words = [w for w in re.split(r"\s+", narr) if w]
    return [" ".join(words[:cut]), " ".join(words[cut:])]


def test_NBSP_대사도_모든_경계에서_저장이_통과한다():
    """NBSP가 든 훅 대사 — 어느 자리에서 끊어도 키가 같아야 한다(옛 코드는 전부 실패)."""
    words = [w for w in re.split(r"\s+", _HOOK_NBSP) if w]
    assert "\xa0" in _HOOK_NBSP, "이 테스트는 NBSP가 든 대사를 검증한다"
    for cut in range(1, len(words)):
        lines = _split_like_browser(_HOOK_NBSP, cut)
        assert cap_preset_key("".join(lines)) == cap_preset_key(_HOOK_NBSP), (
            f"{cut}번째 어절 뒤 경계가 422로 거절된다 — 클릭해도 아무 일이 안 일어난다"
        )


def test_NBSP_대사의_사람이_정한_줄을_렌더가_그대로_쓴다():
    """저장만 통과하고 렌더가 폴백하면 '저장은 됐는데 반영 안 됨'이 된다.

    끝 마침표는 표시용으로 떼이므로(_strip_cap_tail) 글자가 아니라 **줄 나눔**을 본다:
    사람이 정한 2줄이 그대로 2줄인가, 그리고 각 줄의 어절이 그대로인가.
    """
    lines = _split_like_browser(_HOOK_NBSP, 4)
    got = _caption_segments(_HOOK_NBSP, preset=lines)
    assert len(got) == 2, f"사람이 정한 2줄이 규칙 폴백으로 다시 쪼개졌다: {got}"
    # 끝 마침표만 표시용으로 떼인다 — 그 외 글자는 사람이 정한 그대로여야 한다.
    assert cap_preset_key("".join(got)) == cap_preset_key("".join(lines))

    # 대조군: preset이 거절되면 규칙 폴백이 다른 줄 수(3줄)를 만든다 = 예전 실패 모습.
    assert len(_caption_segments(_HOOK_NBSP)) != len(got)


def test_NBSP_없는_대사는_원래대로_통과한다():
    """2챕터처럼 멀쩡하던 칸이 이 수정으로 깨지지 않았는지(회귀 방지)."""
    words = [w for w in re.split(r"\s+", _OK_PLAIN) if w]
    for cut in range(1, len(words)):
        lines = _split_like_browser(_OK_PLAIN, cut)
        assert cap_preset_key("".join(lines)) == cap_preset_key(_OK_PLAIN)


def test_글자가_진짜_달라지면_여전히_막는다():
    """공백만 너그럽게 봤을 뿐 — 글자를 지우거나 고치면 그대로 거절해야 한다."""
    assert cap_preset_key("여러분 대파 썰어서") != cap_preset_key(_HOOK_NBSP)
    assert cap_preset_key("여러분 대파 썰어서 절대 냉장실에 그냥 넣지 마세요.") != cap_preset_key(
        _HOOK_NBSP
    )
