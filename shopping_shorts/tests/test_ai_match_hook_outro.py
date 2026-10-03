# -*- coding: utf-8 -*-
"""ai_match: 뒷컷은 목록·검증·채우기 어디서도 안 쓰고, 훅 유형을 AI 에게 보여준다 (2026-10-01, 카드 055 라이브 실측 사고).
고치기 전: AI 가 고른 뒷컷(인사)이 그대로 통과했다 → 이 검사가 FAIL."""
from shopping_shorts import ai_match as am


def _idx():
    return {
        "s1-0": {"secs": 3.0, "desc": "엄지 치켜세우며 인사", "vid": "s1", "role": "after", "hook": "", "outro": True},
        "s1-1": {"secs": 3.0, "desc": "접힌 막대가 십자로 펴짐", "vid": "s1", "role": "조작", "hook": "반전", "outro": False},
        "s1-2": {"secs": 3.0, "desc": "제품 외관", "vid": "s1", "role": "완성", "hook": "", "outro": False},
        "s0-0": {"secs": 3.0, "desc": "씨앗 원본", "vid": "s0", "role": "완성", "hook": "", "outro": False},
    }


def test_cut_block_hides_outro_and_shows_hook():
    idx = _idx()
    blk = am._cut_block(idx, "s0", sorted(idx))
    assert "s1-0" not in blk and "s0-0" not in blk
    assert "s1-1" in blk and "훅:반전" in blk


def test_ai_pick_of_outro_is_dropped_and_not_filled_with_outro(monkeypatch):
    idx = _idx()
    monkeypatch.setattr(am._sg, "_call_json", lambda *a, **k: {"picks": [{"line": 1, "cuts": ["s1-0", "s1-2"], "why": "x"}]})
    out = am.match([{"role": "훅", "text": "해외 천재가 만든 제품의 정체"}], idx, "s0", note={})
    assert out and out[0]["segs"] == ["s1-2"], out


def test_brief_mentions_hook_rule():
    assert "훅 표시" in am.BRIEF and "미끼" in am.BRIEF and "최고 전문가" in am.BRIEF


def test_fill_stops_at_different_scene(monkeypatch):
    """같은 영상 다음 컷이 딴 장면(label 다름)이면 채우지 않는다 — 배수구 다음 감자(2026-10-01)."""
    idx = {
        "s1-38": {"secs": 0.8, "desc": "배수구로 물 버림", "vid": "s1", "role": "실증", "label": "물 빼기 과정", "outro": False},
        "s1-39": {"secs": 0.9, "desc": "익은 감자 가득", "vid": "s1", "role": "after", "label": "조리 후 결과 확인", "outro": False},
        "s1-40": {"secs": 0.8, "desc": "완성 요리 접시", "vid": "s1", "role": "완성", "label": "제품 활용 예시", "outro": False},
        "s0-0": {"secs": 3.0, "desc": "씨앗", "vid": "s0", "role": "완성", "label": "", "outro": False},
    }
    monkeypatch.setattr(am._sg, "_call_json", lambda *a, **k: {"picks": [{"line": 1, "cuts": ["s1-38"], "why": "x"}]})
    out = am.match([{"role": "고조1", "text": "뜨거운 물 버리다 손 데이고 싱크대에 면발을 쏟던 지옥을"}], idx, "s0", note={})
    assert out and out[0]["segs"] == ["s1-38"], out


def test_lock_does_not_repeat_same_cut_across_group_lines():
    """묶음 안 여러 줄을 고정할 때 같은 컷을 또 박지 않는다 — 고조1 세 줄 = 같은 배수구 컷(2026-10-01)."""
    import io as _io, os as _os, re as _re
    src = _io.open(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "story_writer.py"), encoding="utf-8").read()
    body = src[src.index("_locked = 0"):src.index('n["locked_lines"]')]
    code = "
".join(l.split("#")[0] for l in body.splitlines())
    assert "_taken" in code and "or allowed[:1]" not in code     # 2026-10-03: 근거 컷이 다 쓰였으면 첫 컷 재사용 금지
    # '안 쓴 컷'을 먼저 고르는 줄이 있어야 한다
    assert _re.search(r"c not in _taken", body)


def test_recheck_asks_again_for_duplicate_lines(monkeypatch):
    """1차 답에 중복 컷이 있으면 걸린 줄만 다시 묻는다(호출 2회) — 2026-10-01 사장님 "다시 묻는 과정이 없나"."""
    idx = {
        "s1-1": {"secs": 3.0, "desc": "접힌 막대가 십자로 펴짐", "vid": "s1", "role": "조작", "hook": "반전", "outro": False, "label": "펼침"},
        "s1-2": {"secs": 3.0, "desc": "제품 외관", "vid": "s1", "role": "완성", "hook": "", "outro": False, "label": "외관"},
        "s2-1": {"secs": 3.0, "desc": "가방에 넣음", "vid": "s2", "role": "정리", "hook": "", "outro": False, "label": "수납"},
        "s0-0": {"secs": 3.0, "desc": "씨앗", "vid": "s0", "role": "완성", "hook": "", "outro": False, "label": ""},
    }
    calls = []

    def fake(prompt, schema, **k):
        calls.append(prompt)
        if len(calls) == 1:
            return {"steps": "생각", "picks": [{"line": 1, "cuts": ["s1-1"]}, {"line": 2, "cuts": ["s1-1"]}]}   # 2번 줄이 1번 컷을 또 씀
        return {"picks": [{"line": 2, "cuts": ["s2-1"]}]}
    monkeypatch.setattr(am._sg, "_call_json", fake)
    note = {}
    out = am.match([{"role": "훅", "text": "해외 천재가 만든 제품의 정체"}, {"role": "전환", "text": "이건 바로 거치대"}], idx, "s0", note=note)
    assert len(calls) == 2 and "다시 고를 줄" in calls[1] and "s1-1" in calls[1]
    assert out[0]["segs"] == ["s1-1"] and out[1]["segs"] == ["s2-1"], out
    assert note.get("matcher_recheck") == {"2": "중복 s1-1(줄1)"} and note.get("matcher_left") == {}


def test_prompt_has_expert_role_topic_and_steps(monkeypatch):
    seen = {}
    monkeypatch.setattr(am._sg, "_call_json", lambda prompt, schema, **k: seen.setdefault("p", prompt) and {"picks": [{"line": 1, "cuts": ["s1-1"]}]})
    idx = {"s1-1": {"secs": 3.0, "desc": "x", "vid": "s1", "role": "", "hook": "클로즈업", "outro": False, "label": "l", "use": "자석이라 착", "kind": "기능", "tempo": "보통"},
           "s0-0": {"secs": 3.0, "desc": "씨앗", "vid": "s0", "role": "", "hook": "", "outro": False, "label": ""}}
    am.match([{"role": "훅", "text": "정체"}], idx, "s0", note={}, product="접이식 거치대")
    p = seen["p"]
    assert "최고 전문가" in p and "[주제] 이 영상이 파는 것: 접이식 거치대" in p and "steps" in p
    assert "소구점:자석이라 착" in p and "종류:기능" in p and "훅:클로즈업" in p and "속도:보통" in p


def test_only_mode_picks_just_that_line(monkeypatch):
    """3단계 「채우기」: 대본 전체를 보여주되 그 줄만 고른다 — 프롬프트에 '2번 줄만', 다른 줄은 빈 segs."""
    idx = {"s1-1": {"secs": 3.0, "desc": "펼침", "vid": "s1", "role": "", "hook": "반전", "outro": False, "label": "펼침"},
           "s1-2": {"secs": 3.0, "desc": "가방", "vid": "s1", "role": "", "hook": "", "outro": False, "label": "수납"}}
    seen = {}

    def fake(prompt, schema, **k):
        seen["p"] = prompt
        return {"picks": [{"line": 1, "cuts": ["s1-1"]}, {"line": 2, "cuts": ["s1-2"]}]}
    monkeypatch.setattr(am._sg, "_call_json", fake)
    out = am.match([{"role": "훅", "text": "정체"}, {"role": "전환", "text": "가방에 쏙"}], idx, None, note={}, only=[1])
    assert "2번 줄만" in seen["p"] and "1. [훅]" in seen["p"]
    assert out[0]["segs"] == [] and out[1]["segs"] == ["s1-2"], out


def test_apply_merges_ai_with_code_and_falls_back(monkeypatch):
    """3단계 매칭 전문가 합치기(백본·이야기작가 공용): AI 줄은 AI 컷, 비운 줄은 코드 컷 중 안 겹친 것, 실패면 코드 그대로."""
    code = [{"role": "훅", "seg": "a", "segs": ["a"]}, {"role": "고조", "seg": "b", "segs": ["b", "c"]}]
    monkeypatch.setattr(am, "match", lambda *a, **k: [{"role": "훅", "seg": "c", "segs": ["c"]}, {"role": "고조", "seg": "", "segs": []}])
    n = {}
    out = am.apply([{"text": "x"}, {"text": "y"}], code, {}, None, note=n)
    assert n["matcher"] == "ai" and out[0]["segs"] == ["c"] and out[1]["segs"] == ["b"]
    monkeypatch.setattr(am, "match", lambda *a, **k: [])
    n = {}
    out = am.apply([{"text": "x"}, {"text": "y"}], code, {}, None, note=n)
    assert n["matcher"].startswith("code") and out == code


def test_check_flags_long_line_with_one_scene_only_when_spare_cuts_exist():
    """2.5초↑ 줄에 장면 1개면 다시 묻는다 — 단 남은 쓸 컷이 없으면(재료 부족) 묻지 않는다(2026-10-02)."""
    idx = {"a-1": {"secs": 4.0, "vid": "a", "outro": False, "label": "x"},
           "a-2": {"secs": 2.0, "vid": "a", "outro": False, "label": "y"}}
    long_line = [{"text": "가" * 30}]            # 5.7자/초 → 약 5초
    bad = am.check({0: ["a-1"]}, long_line, idx, None)
    assert 0 in bad and "장면 1개" in bad[0]
    bad2 = am.check({0: ["a-1"]}, long_line, {"a-1": idx["a-1"]}, None)   # 남은 컷 없음
    assert not any("장면 1개" in w for w in bad2.values())
    assert "2.5초가 넘는 줄은 서로 다른 장면" in am.BRIEF
