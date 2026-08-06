# -*- coding: utf-8 -*-
"""채널 스타일 주입 (대본퀄 v6) — 블록 내용·스위치·실제 배선."""
import os
from unittest.mock import patch

from shopping_shorts import style_profiles
from shopping_shorts.edit_plan import _scene_first_candidates


def test_maison_block_has_fewshot_and_guide():
    b = style_profiles.style_block("maison")
    assert "스타일 예시" in b and "158만 회" in b
    assert "소리 질렀어요" in b            # few-shot 원문이 전문으로 실린다
    assert "인물을 통과한다" in b          # 가이드
    assert "CTA 규칙(명분+보상형)" in b    # CTA는 우리 규칙 우선


def test_switch_off_and_unknown():
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert style_profiles.active_style() is None
        assert style_profiles.style_block() == ""
    with patch.dict(os.environ, {"SCRIPT_STYLE": "0"}):
        assert style_profiles.style_block() == ""
    assert style_profiles.style_block("모르는스타일") == ""


def _clean_env(**over):
    """SCRIPT_STYLE·SCRIPT_TRIO를 지운 환경(서버 env가 테스트에 새는 걸 막는다)."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("SCRIPT_STYLE", "SCRIPT_TRIO")}
    env.update(over)
    return patch.dict(os.environ, env, clear=True)


def test_default_is_trio_and_candidate_rotation():
    with _clean_env():
        assert style_profiles.active_style() == "trio"
        # 2026-08-07 C안 교체: standard → hometerior(홈테리어픽)
        assert [style_profiles.candidate_style(i) for i in range(3)] == \
            ["maison", "chae", "hometerior"]
    with patch.dict(os.environ, {"SCRIPT_STYLE": "maison"}):
        assert style_profiles.candidate_style(2) == "maison"  # 단일 모드
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert style_profiles.candidate_style(0) is None
    # standard는 목록에 남아 단일 지정으로 계속 쓸 수 있다(교체가 아니라 자리만 양보)
    with patch.dict(os.environ, {"SCRIPT_STYLE": "standard"}):
        assert style_profiles.candidate_style(0) == "standard"
        assert "등짝 스매싱" in style_profiles.style_block()


def test_trio_overridable_by_env_for_rollback():
    """코드 배포 없이 C안을 되돌리는 통로(서버 env 한 줄)."""
    with _clean_env(SCRIPT_TRIO="maison,chae,standard"):
        assert [style_profiles.candidate_style(i) for i in range(3)] == \
            ["maison", "chae", "standard"]
    with _clean_env(SCRIPT_TRIO="  ,,  "):        # 쓰레기 값이면 기본값
        assert style_profiles.candidate_style(2) == "hometerior"
    with _clean_env(SCRIPT_TRIO="없는스타일"):     # 모르는 이름만 있으면 기본값
        assert style_profiles.candidate_style(2) == "hometerior"


def test_hometerior_block_has_fewshot_and_guide():
    b = style_profiles.style_block("hometerior")
    assert "스타일 예시" in b and "271만 회" in b
    assert "멘탈 지켜줍니다" in b               # few-shot 원문 전문
    assert "마지막 한 문장은 합쇼체로" in b      # 이 채널의 서명
    assert "CTA 규칙(명분+보상형)" in b
    # ★중복 대본(애플힙 재업로드)이 예시로 새면 한 소재로 쏠린다 — 3편이 서로 달라야 한다
    assert b.count("애플힙") == 0


def test_hometerior_hapsyo_ending_is_not_penalized():
    """★시킨 대로 쓴 후보가 감점당해 추천에서 밀려나던 구조를 막는다.

    홈테리어픽은 끝맺음 합쇼체가 스타일 지시다(실측: 35편 중 34편). 스타일을 안 넘기면
    종전대로 감점 — 하위호환."""
    from shopping_shorts.style_profiles import style_penalty
    ht = ["나가실 때 원상 복구해 주세요, 이 소리 제일 무섭잖아요.",
          "문틀 다 까졌더라고요.", "이거 미리 챙겨두세요. 멘탈 지켜줍니다."]
    with _clean_env():
        assert style_penalty(ht, "hometerior") == 0.0    # 지시대로 쓴 것 → 감점 없음
        assert style_penalty(ht) > 0.0                   # 스타일 미지정 → 종전 동작
        assert style_penalty(ht, "maison") > 0.0         # 다른 스타일이면 여전히 이탈
        # 허용치를 넘겨 본문까지 합쇼체면 홈테리어픽에서도 감점된다(전면 면제 아님)
        allsyo = ["이겁니다.", "저겁니다.", "그겁니다.", "끝입니다."]
        assert style_penalty(allsyo, "hometerior") > 0.0


def test_story_frame_matches_assigned_style():
    """구도와 스타일이 어긋나면 프롬프트 두 블록이 서로 싸운다."""
    with _clean_env():
        assert style_profiles.story_frame(0)[0] == "발견담"
        assert style_profiles.story_frame(1)[0] == "가족 에피소드"
        # C안이 hometerior로 바뀌었으니 구도도 문제해결담이어야 한다(지인 목격담 X)
        assert style_profiles.story_frame(2)[0] == "문제해결담"
        assert "문제해결담" in style_profiles.story_frame_block(2)
        # 이름을 직접 주면 그 스타일의 구도
        assert style_profiles.story_frame(0, "hometerior")[0] == "문제해결담"
        assert style_profiles.story_frame(2, "standard")[0] == "지인 목격담"
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert style_profiles.story_frame(0) is None


def test_restyle_prompt_does_not_contradict_itself_on_hapsyo():
    """★라이브 실사고(job cc794cf30b4b): 리라이트 [절대규칙]에 "합쇼체 금지"가 모든
    스타일에 하드코딩돼, 끝맺음 합쇼체가 서명인 홈테리어픽에서 스타일 블록과 규칙이
    같은 프롬프트 안에서 싸우고 '절대'가 이겼다 → C안 합쇼체 0건(서명 실종).

    한 프롬프트가 같은 것을 시키면서 동시에 금지하면 안 된다."""
    from shopping_shorts.single_source import restyle_prompt
    beats = [{"n": 1, "covers": [1], "narration": "테스트 문장이에요."}]
    with _clean_env():
        ht = restyle_prompt(beats, style_name="hometerior")
        assert "합쇼체(~습니다) 금지" not in ht          # 서명을 막던 금지가 없어야
        assert "마지막 한 문장만** 합쇼체로 짧게 닫아라" in ht
        assert "마지막 한 문장은 합쇼체로" in ht          # 스타일 블록 쪽 지시도 살아있고
        # 다른 스타일·미지정은 종전 그대로(회귀 0)
        for name in ("maison", "chae", "standard", None):
            p = restyle_prompt(beats, style_name=name)
            assert "합쇼체(~습니다) 금지" in p, name
            assert "마지막 한 문장만** 합쇼체로 짧게 닫아라" not in p, name


def test_hapsyo_rule_not_hardcoded_in_restyle_prompt():
    """배선 잠금 — 문구를 다시 하드코딩하면 위 테스트가 통과해도 이게 잡는다."""
    from shopping_shorts import single_source
    src = open(single_source.__file__, encoding="utf-8").read()
    assert "hapsyo_rule(style_name)" in src
    # 절대규칙 안에 리터럴 금지문이 되살아나면 실패
    assert "심지어). 합쇼체(~습니다) 금지." not in src


def test_style_penalty_wired_with_style_name():
    """배선 잠금 — 스타일 인자를 지워도 함수 테스트는 통과한다(이 트랙 실사고 패턴)."""
    from shopping_shorts import edit_plan
    src = open(edit_plan.__file__, encoding="utf-8").read()
    assert src.count("style_penalty(narrs, ") == 2      # 1소스·2소스 두 경로 모두


def test_chae_and_standard_blocks():
    c = style_profiles.style_block("chae")
    assert "표정이 싹 굳으시면서" in c and "631만 회" in c and "티키타카" in c
    s = style_profiles.style_block("standard")
    assert "등짝 스매싱" in s and "286만 회" in s and "유머" in s
    # trio 공통 생성 블록은 메종
    assert "소리 질렀어요" in style_profiles.style_block("trio")


def test_wired_into_scene_first_prompt():
    """배선 테스트 — 함수만 검증하면 배선 한 줄 지워도 통과한다(이 트랙 실사고)."""
    seen = {}

    def fake_call(prompt, schema):
        seen["prompt"] = prompt
        return {"candidates": []}

    _scene_first_candidates("인벤토리", "제품설명", 30, call=fake_call)
    assert "스타일 예시" in seen["prompt"] and "소리 질렀어요" in seen["prompt"]

    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        _scene_first_candidates("인벤토리", "제품설명", 30, call=fake_call)
        assert "스타일 예시" not in seen["prompt"]  # off면 종전과 동일


def test_wired_into_single_source_prompt():
    """1소스 엔진 배선 — 3엔진 중 1개만 배선해 '적용 안 됨' 제보 났던 실사고(2026-08-05)."""
    from shopping_shorts.single_source import script_prompt
    order = [{"seg_id": "s0-1", "_dur": 3.0, "scene_desc": "장면", "text": "말", "is_key": True}]
    p = script_prompt(order, 10.0, "[훅블록]")
    assert "스타일 예시" in p and "소리 질렀어요" in p
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert "스타일 예시" not in script_prompt(order, 10.0, "[훅블록]")


def test_single_source_line_count_longer_sentences_when_style_on():
    """스타일 ON이면 문장 수가 줄어 긴 호흡이 된다 (30초: 8~9문장 → 6문장)."""
    from shopping_shorts.single_source import line_count
    assert line_count(30.0, 13) == 6
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert line_count(30.0, 13) == 9  # 종전과 동일


def _mk_beats():
    return [{"n": 1, "covers": [1], "narration": "다이소에서 역대급 스팀기를 발견했어요."},
            {"n": 2, "covers": [2, 3], "narration": "물만으로 살균까지 되니 정말 편해요."},
            {"n": 3, "covers": [4], "narration": "댓글에 '정보' 남겨주시면 링크 드릴게요."}]


def test_apply_restyle_swaps_narration_keeps_covers():
    from shopping_shorts.single_source import apply_restyle
    def fake_call(prompt, schema):
        assert "스타일 예시" in prompt      # few-shot이 실려 간다
        return {"beats": [{"n": 1, "narration": "와, 저 이거 보고 소리 질렀거든요."},
                          {"n": 2, "narration": "물만으로 살균까지 되는 게 편하더라고요."},
                          {"n": 3, "narration": "댓글에 '정보' 남겨주시면 링크 드릴게요."}]}
    out = apply_restyle(_mk_beats(), fake_call)
    assert out[0]["narration"].startswith("와,") and out[0]["covers"] == [1]
    assert out[1]["covers"] == [2, 3]      # 컷 매핑 보존


def test_apply_restyle_falls_back_on_bad_response():
    from shopping_shorts.single_source import apply_restyle
    src = _mk_beats()
    assert apply_restyle(src, lambda *a: None) == src              # 실패 → 원본
    assert apply_restyle(src, lambda *a: {"beats": [{"n": 1, "narration": "x"}]}) == src  # 개수 불일치
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert apply_restyle(src, lambda *a: (_ for _ in ()).throw(AssertionError)) == src  # off=무호출


def test_apply_restyle_retries_on_cliche():
    from shopping_shorts.single_source import apply_restyle
    calls = {"n": 0}
    def fake_call(prompt, schema):
        calls["n"] += 1
        word = "꿀템이에요" if calls["n"] == 1 else "괜찮더라고요"
        return {"beats": [{"n": i + 1, "narration": f"이 제품 써봤는데 진짜 {word}."}
                          for i in range(3)]}
    out = apply_restyle(_mk_beats(), fake_call)
    assert calls["n"] == 2 and "꿀템" not in out[0]["narration"]


def test_style_penalty_flags_copy_tone_and_off_is_zero():
    from shopping_shorts.style_profiles import style_penalty
    copy = ["싱크대 냄새 고민이라면 꼭 써보세요.", "거품이 오염물을 밀어냅니다.",
            "즉시 녹여줍니다.", "댓글에 '정보' 남겨주세요."]
    maison = ["와, 저 이거 보고 소리 질렀어요.", "기름때가 바로 녹더라고요.",
              "댓글에 '정보' 남겨주시면 보내드릴게요."]
    assert style_penalty(copy) > 0.2 > style_penalty(maison)
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert style_penalty(copy) == 0.0


def test_wired_into_script_generate_prompts():
    """도서관 3안(generate_variations)·믹스(script_generate) 엔진 배선."""
    from shopping_shorts import script_generate as sg
    assert "스타일 예시" in sg._style_extra()
    src = open(sg.__file__, encoding="utf-8").read()
    # 배선 줄 자체를 잠근다(함수만 검증하면 배선 삭제도 통과하는 함정 회피)
    assert src.count("+ _style_extra()") >= 2
