# -*- coding: utf-8 -*-
"""후보별 채널 스타일이 **생성 단계에서** 실리는지 (2026-08-09).

배경: 종전엔 후보 3개가 전부 maison few-shot으로 생성되고, 채널 결은 리라이트가
뒤에서 문체만 갈아끼웠다. 리라이트는 완성 문장의 어미·표현만 만지므로 훅 구조·
스토리 전개·포인트 방식은 maison 골격 그대로 남았다 — 실측 job 316ab18389f7·
325f609056db에서 세 후보의 훅이 전부 "문제 제기"로 수렴(사장님 "3개가 비슷하게 읽힌다").

★배선 잠금이 핵심이다: 함수만 테스트하면 edit_plan이 cand_idx를 안 넘겨도 통과한다
(2026-08-07 style_penalty에서 같은 함정을 이미 밟았다).
"""
import inspect
import re

import pytest

from shopping_shorts import single_source, style_profiles


# few-shot 원문에만 나오는 지문 — 어느 채널이 실렸는지 식별한다.
# ⚠️여기 문구는 반드시 **현재 few-shot에 살아 있는 예시**에서 골라라. 2026-08-09에
#   채이 631만 예시(응답 차단)를 뺐더니 그 예시에만 있던 "시어머니한테 욕 바가지"를
#   쓰던 이 표가 통째로 오탐했다 — 코드는 멀쩡한데 테스트만 빨개진다.
_SIGNATURES = {
    "maison": "무인양품",
    "chae": "500만 원 날릴",          # 536만 회 예시(살아 있음)
    "hometerior": "원상 복구해 주세요",
    "standard": "식세기",
}


def _which_channel(text):
    return {name for name, sig in _SIGNATURES.items() if sig in text}


def _order(n=6):
    return [{"seg_id": "s%d" % i, "_dur": 3.0, "scene_desc": "화면%d" % i,
             "text": "원본대사%d" % i, "is_key": i == 0} for i in range(n)]


def test_candidate_style_block_differs_per_candidate():
    """후보 0/1/2가 서로 다른 채널 few-shot을 받는다."""
    if style_profiles.active_style() != "trio":
        pytest.skip("trio 모드가 아니면 후보별 분화 자체가 대상이 아니다")
    trio = style_profiles._trio()
    seen = []
    for i in range(len(trio)):
        block = style_profiles.candidate_style_block(i)
        assert block, "후보%d 스타일 블록이 비었다" % i
        found = _which_channel(block)
        assert found == {trio[i]}, (
            "후보%d는 %s여야 하는데 실린 few-shot=%s" % (i, trio[i], found))
        seen.append(found)
    assert len({frozenset(s) for s in seen}) == len(trio), "후보끼리 같은 채널이 실렸다"


def test_script_prompt_carries_candidate_style():
    """script_prompt(cand_idx=i)가 그 후보의 채널 few-shot을 프롬프트에 싣는다."""
    if style_profiles.active_style() != "trio":
        pytest.skip("trio 모드 전용")
    trio = style_profiles._trio()
    for i, name in enumerate(trio):
        p = single_source.script_prompt(_order(), 18.0, "[훅]",
                                        frame_block="[구도]", cand_idx=i)
        assert _which_channel(p) == {name}, (
            "후보%d 프롬프트에 %s가 아닌 %s가 실렸다" % (i, name, _which_channel(p)))


def test_script_prompt_without_cand_idx_is_unchanged():
    """★하위호환: cand_idx를 안 주면 종전과 100% 동일(회귀 0)."""
    args = (_order(), 18.0, "[훅]")
    before = single_source.script_prompt(*args, frame_block="[구도]")
    # 종전 동작 = style_block() 공통 블록(trio면 maison)
    assert style_profiles.style_block() in before or not style_profiles.active_style()


def test_edit_plan_passes_cand_idx():
    """★배선 잠금 — edit_plan이 script_prompt에 cand_idx를 실제로 넘기는지.

    이게 없으면 위 함수 테스트는 다 통과하는데 라이브는 종전 그대로가 된다."""
    from shopping_shorts import edit_plan
    src = inspect.getsource(edit_plan._single_source_candidates)
    assert "cand_idx=i" in src, (
        "edit_plan._single_source_candidates가 script_prompt에 cand_idx를 안 넘긴다 "
        "— 후보별 스타일이 생성에 반영되지 않는다")


def test_scene_first_passes_candidate_style():
    """★2소스(scene_first) 배선 잠금 — 슬롯 경로(n=1)가 후보별 채널을 싣는지.

    슬롯 경로는 벌마다 n=1로 따로 부르고 frame_start가 곧 후보 인덱스다."""
    from shopping_shorts import edit_plan
    src = inspect.getsource(edit_plan._scene_first_candidates)
    assert "_style_extra(frame_start" in src, (
        "_scene_first_candidates가 _style_extra에 후보 인덱스를 안 넘긴다 "
        "— 2소스 후보 3개가 전부 같은 채널로 생성된다")


def test_scene_first_n1_injects_distinct_styles():
    """n=1 호출에서 frame_start별로 서로 다른 few-shot이 실린다."""
    if style_profiles.active_style() != "trio":
        pytest.skip("trio 모드 전용")
    from shopping_shorts import edit_plan
    trio = style_profiles._trio()
    seen = []
    for fs in range(len(trio)):
        captured = []

        def _cap(prompt, schema, **kw):
            captured.append(prompt)
            return {"candidates": []}

        try:
            edit_plan._scene_first_candidates("인벤", "제품", 30, n=1,
                                              call=_cap, frame_start=fs)
        except Exception:
            pass
        assert captured, "프롬프트가 생성되지 않았다"
        found = _which_channel(captured[0])
        assert found == {trio[fs]}, (
            "frame_start=%d는 %s여야 하는데 %s" % (fs, trio[fs], found))
        seen.append(found)
    assert len({frozenset(s) for s in seen}) == len(trio)


def test_hapsyo_guard_only_targets_hometerior():
    """합쇼체 보장은 홈테리어픽 전용 — 다른 스타일엔 no-op(회귀 0)."""
    beats = [{"n": 1, "covers": [1], "narration": "첫 문장이에요."},
             {"n": 2, "covers": [2], "narration": "식어도 눅눅하지 않더라고요."},
             {"n": 3, "covers": [3], "narration": "댓글에 '정보' 남겨주세요"}]
    assert single_source.hapsyo_tail_missing(beats, "hometerior") is True
    for other in ("chae", "maison", "standard", None, ""):
        assert single_source.hapsyo_tail_missing(beats, other) is False, other


def test_hapsyo_detects_all_hapsyo_verbs():
    """★고정 목록(습니다|입니다|됩니다)이 아니라 '~ㅂ니다' 전반을 잡는다.

    2026-08-09 실측에서 "추천합니다"·"훌륭합니다"를 놓쳐 판정이 틀렸다."""
    cta = {"n": 9, "covers": [9], "narration": "댓글에 '정보' 남겨주세요"}
    for tail in ("차 아끼는 분들께 강력 추천합니다.", "맛이 정말 훌륭합니다.",
                 "단면이 완성됩니다.", "멘탈 지켜줍니다", "감성 미쳤습니다",
                 "한 번에 쏙 꺼내집니다."):
        beats = [{"n": 1, "covers": [1], "narration": "앞 문장."},
                 {"n": 2, "covers": [2], "narration": tail}, cta]
        assert single_source.hapsyo_tail_missing(beats, "hometerior") is False, tail
    for tail in ("식감이 살더라고요", "바삭해지는 거 있죠?", "비밀이 있거든요."):
        beats = [{"n": 1, "covers": [1], "narration": "앞 문장."},
                 {"n": 2, "covers": [2], "narration": tail}, cta]
        assert single_source.hapsyo_tail_missing(beats, "hometerior") is True, tail


def test_edit_plan_wires_hapsyo_guard_both_paths():
    """★배선 잠금 — 1소스·2소스 양쪽이 합쇼체 보장을 실제로 부르는지."""
    from shopping_shorts import edit_plan
    one = inspect.getsource(edit_plan._single_source_candidates)
    assert "hapsyo_tail_missing" in one, "1소스에 합쇼체 보장이 안 걸렸다"
    whole = inspect.getsource(edit_plan)
    assert whole.count("hapsyo_tail_missing") >= 2, (
        "2소스(scene_first) 경로에 합쇼체 보장이 안 걸렸다")


def test_chae_person_guard_only_targets_chae():
    """채이 인물 보장은 채이 전용 — 다른 스타일엔 no-op(회귀 0)."""
    no_person = [{"n": 1, "covers": [1], "narration": "이 선반을 넣으니 좋더라고요."},
                 {"n": 2, "covers": [2], "narration": "공간이 두 배가 됐어요."},
                 {"n": 3, "covers": [3], "narration": "댓글에 '정보' 남겨주세요"}]
    assert single_source.chae_person_missing(no_person, "chae") is True
    for other in ("hometerior", "maison", "standard", None, ""):
        assert single_source.chae_person_missing(no_person, other) is False, other


def test_chae_person_guard_detects_family():
    """가족·지인이 본문에 있으면 통과. CTA에만 있는 건 인정하지 않는다."""
    cta = {"n": 3, "covers": [3], "narration": "댓글에 '정보' 남겨주세요"}
    for who in ("시어머니", "엄마", "남편", "친정", "아내", "친구"):
        beats = [{"n": 1, "covers": [1], "narration": "%s가 보시더니 놀라시는 거예요." % who},
                 {"n": 2, "covers": [2], "narration": "공간이 두 배가 됐어요."}, cta]
        assert single_source.chae_person_missing(beats, "chae") is False, who
    # CTA에만 인물이 있으면 본문은 여전히 비어 있다 → 보장 대상
    only_cta = [{"n": 1, "covers": [1], "narration": "공간이 두 배가 됐어요."},
                {"n": 2, "covers": [2], "narration": "정말 편해졌어요."},
                {"n": 3, "covers": [3], "narration": "엄마도 댓글 남겨주세요"}]
    assert single_source.chae_person_missing(only_cta, "chae") is True


def test_edit_plan_wires_chae_guard_both_paths():
    """★배선 잠금 — 1소스·2소스 양쪽이 채이 인물 보장을 부르는지."""
    from shopping_shorts import edit_plan
    one = inspect.getsource(edit_plan._single_source_candidates)
    assert "chae_person_missing" in one, "1소스에 채이 인물 보장이 안 걸렸다"
    whole = inspect.getsource(edit_plan)
    assert whole.count("chae_person_missing") >= 2, (
        "2소스(scene_first) 경로에 채이 인물 보장이 안 걸렸다")


def test_style_block_signature_accepts_name():
    """candidate_style_block이 candidate_style을 그대로 따른다(트리오 교체 시 자동 반영)."""
    for i in range(3):
        name = style_profiles.candidate_style(i)
        block = style_profiles.candidate_style_block(i)
        if not name:
            assert block == ""
        else:
            assert block == style_profiles.style_block(name)


def test_cta_keyword_comes_from_material():
    """★CTA 폴백 키워드는 소재에서 뽑는다(2026-08-09).

    종전엔 '나도'/'정보' 둘뿐이라 파전·곰팡이 영상에도 "댓글에 '정보'"가 나갔다
    (10회 실측 6번). 인포크 자동응답 키워드가 대본과 어긋나는 원인이기도 하다."""
    kw = single_source.cta_keyword_for(
        [], "파전이 눅눅해서 시어머니께 여쭤봤더니 파전 비법을 알려주셨어요 파전이 바삭해졌어요")
    assert kw == "파전", kw
    kw2 = single_source.cta_keyword_for(
        [], "욕실 곰팡이가 안 지워졌는데 젤을 바르니 곰팡이가 사라졌어요 곰팡이 재발도 없어요")
    assert kw2 == "곰팡이", kw2


def test_cta_keyword_prefers_script_keyword():
    """대본이 이미 쓴 키워드가 있으면 그걸 따른다(후보 간 일관성)."""
    beats = [{"narration": "앞 문장"}, {"narration": "댓글에 '바삭' 남겨주세요"}]
    assert single_source.cta_keyword_for(beats, "아무 소재나") == "바삭"


def test_cta_keyword_falls_back_when_no_signal():
    """소재에 반복되는 명사가 없으면 종전 폴백('정보')로 떨어진다 — 회귀 0."""
    assert single_source.cta_keyword_for([], "정보 방법 그냥 이거") == "정보"
