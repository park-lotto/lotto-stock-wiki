# -*- coding: utf-8 -*-
"""2단계 '본 것만 쓰기'(grounded) — 2026-09-04 사장님 "제품형 대본은 소스 영상에 보이는 것으로만 써야 한다.
대본을 썼는데 장면이 없다는 건 말이 안 된다."

플래그 밖(grounded=False)에선 종전과 완전히 같아야 한다(회귀 0). 켜면:
  · 장면 목록을 전부(상한) 쓰임·변화·활용까지 보여준다
  · 장점·효과·동작 줄은 src_seg 필수(needs_scene) — 게이트 '장면 근거'가 반려한다
  · 지어낸 번호는 반려, 제품형은 절반 이상 장면 붙어야 한다"""
from shopping_shorts import script_generate as SG, script_gate as GT


def _segs(n, **extra):
    return [{"seg_id": f"s0-{i}", "start": i, "end": i + 1, "text": f"말{i}",
             "scene_desc": f"화면{i}", "label": f"쓰임{i}", "change": f"변화{i}", "use_point": f"활용{i}", **extra}
            for i in range(n)]


def test_기본은_장면_20개_40자_그대로고_grounded면_전부_보여준다():
    src = [{"name": "홈템", "full_text": "x", "structure": {}, "segments": _segs(30)}]
    old = SG._mix_source_block(src)
    assert "[s0-19]" in old and "[s0-20]" not in old and "쓰임0" not in old, "종전 동작이 바뀌었다"
    new = SG._mix_source_block(src, full_scenes=True)
    assert "[s0-29]" in new and "쓰임0" in new and "변화0" in new and "활용0" in new
    assert "여기서만 가져오고" in new


def test_scene_ids_of_는_목록에_실린_번호만():
    src = [{"name": "홈템", "segments": _segs(3)}]
    assert SG.scene_ids_of(src) == {"s0-0", "s0-1", "s0-2"}


def test_장면근거_검사_지어낸_번호는_반려():
    ok, det = GT.scene_grounding_check(
        [{"text": "이거 진짜 좋아요", "src_seg": "s0-1", "needs_scene": True},
         {"text": "때가 쏙 빠져요", "src_seg": "s0-99", "needs_scene": True}], {"s0-0", "s0-1"})
    assert not ok and "지어낸 장면 번호" in det and "s0-99" in det


def test_장면근거_검사_필요한_줄이_비면_반려():
    ok, det = GT.scene_grounding_check(
        [{"text": "여러분 이거 아세요", "src_seg": "", "needs_scene": False},
         {"text": "때가 쏙 빠져요", "src_seg": "", "needs_scene": True},
         {"text": "닦으면 끝", "src_seg": "s0-1", "needs_scene": True}], {"s0-0", "s0-1"})
    assert not ok and "src_seg가 비었다" in det and "때가 쏙" in det


def test_장면근거_검사_제품형은_절반_이상_장면이_붙어야_한다():
    beats = [{"text": f"줄{i}", "src_seg": "", "needs_scene": False} for i in range(4)]
    beats[0]["src_seg"] = "s0-0"
    ok, det = GT.scene_grounding_check(beats, {"s0-0"})
    assert not ok and "1/4" in det
    ok2, _ = GT.scene_grounding_check(beats, {"s0-0"}, is_recipe=True)
    assert ok2, "레시피는 비율 요구를 안 한다"


def test_장면근거_검사_통과():
    ok, det = GT.scene_grounding_check(
        [{"text": "훅", "src_seg": "", "needs_scene": False},
         {"text": "장점1", "src_seg": "s0-0", "needs_scene": True},
         {"text": "장점2", "src_seg": "s0-1", "needs_scene": True}], {"s0-0", "s0-1"})
    assert ok and "2/3" in det


def test_gate_check_는_grounded일_때만_장면근거_항목을_만든다():
    style = {"beat_roles": ["hook", "cta"], "chars_per_30s": 200}
    beats = [{"role": "hook", "text": "이거 보세요", "src_seg": ""},
             {"role": "cta", "text": "댓글에 남겨주세요", "src_seg": ""}]
    c1, _ = GT.check(style, beats)
    assert not any(c["name"] == "장면 근거" for c in c1), "플래그 밖에서 항목이 생기면 종전 대본이 반려된다"
    c2, _ = GT.check(style, beats, scene_ids={"s0-0"}, grounded=True)
    hit = [c for c in c2 if c["name"] == "장면 근거"]
    assert hit and not hit[0]["ok"]


def test_generate_one_style_grounded는_규칙과_전체장면을_넣고_게이트에_장면번호를_준다(monkeypatch):
    from shopping_shorts import bank_assemble
    seen = {"prompts": [], "gate": []}
    monkeypatch.setattr(bank_assemble, "style_block", lambda style, seconds=30, seed="": "[스타일]")
    monkeypatch.setattr(SG, "_style_extra", lambda: "")
    monkeypatch.setattr(SG, "_speaker_judge", None)

    def fake_call(prompt, schema, note=None):
        seen["prompts"].append(prompt)
        return {"beats": [{"role": "hook", "text": "이거 보세요", "src_seg": "", "needs_scene": False},
                          {"role": "cta", "text": "댓글에 남겨주세요", "src_seg": "s0-1", "needs_scene": True}]}
    monkeypatch.setattr(SG, "_call_json", fake_call)
    real_check = GT.check

    def spy_check(*a, **k):
        seen["gate"].append(k)
        return real_check(*a, **k)
    monkeypatch.setattr(GT, "check", spy_check)

    src = [{"name": "홈템", "full_text": "x", "structure": {}, "product": "방충망 청소기",
            "segments": _segs(25)}]
    style = {"id": "st", "name": "테스트", "beat_roles": ["hook", "cta"], "chars_per_30s": 60}
    SG.generate_one_style(src, style, target_seconds=10, grounded=True)
    p = seen["prompts"][0]
    assert "[장면에 보이는 것만 써라" in p and "[s0-24]" in p and "needs_scene" in p
    assert seen["gate"][0]["grounded"] is True and "s0-1" in seen["gate"][0]["scene_ids"]
    assert seen["gate"][0]["is_recipe"] is False

    seen["prompts"].clear(); seen["gate"].clear()
    SG.generate_one_style(src, style, target_seconds=10)          # 플래그 밖
    p2 = seen["prompts"][0]
    assert "[장면에 보이는 것만 써라" not in p2 and "[s0-24]" not in p2 and "참고한 대목이 딱히 없으면" in p2
    assert seen["gate"][0]["grounded"] is False and seen["gate"][0]["scene_ids"] is None


def test_레시피는_규칙이_느슨하다(monkeypatch):
    from shopping_shorts import bank_assemble
    seen = []
    monkeypatch.setattr(bank_assemble, "style_block", lambda style, seconds=30, seed="": "[스타일]")
    monkeypatch.setattr(SG, "_style_extra", lambda: "")
    monkeypatch.setattr(SG, "_speaker_judge", None)
    monkeypatch.setattr(SG, "_call_json", lambda prompt, schema, note=None: seen.append(prompt) or
                        {"beats": [{"role": "hook", "text": "a", "src_seg": ""}]})
    src = [{"name": "레시피", "full_text": "x", "structure": {}, "segments": _segs(3)}]
    SG.generate_one_style(src, {"id": "r", "name": "r", "beat_roles": ["hook"], "chars_per_30s": 60},
                          target_seconds=10, grounded=True)
    assert "레시피는 감각·전개 줄이 장면 없이도 된다" in seen[0] and "[장면에 보이는 것만 써라" not in seen[0]


def test_src_seg_는_여러_번호를_허용하고_첫_번째가_대표다(monkeypatch):
    assert GT.parse_src_segs("s3-10,s3-11, s3-12") == ["s3-10", "s3-11", "s3-12"]
    assert GT.parse_src_segs("[s0-1] / s0-2") == ["s0-1", "s0-2"] and GT.parse_src_segs("") == []
    ok, det = GT.scene_grounding_check(
        [{"text": "a", "src_seg": "s0-0,s0-1", "needs_scene": True}], {"s0-0", "s0-1"})
    assert ok
    ok2, det2 = GT.scene_grounding_check(
        [{"text": "a", "src_seg": "s0-0,s0-9", "needs_scene": True}], {"s0-0", "s0-1"})
    assert not ok2 and "s0-9" in det2 and "s0-0" not in det2.split("src_seg=")[1].split("(")[0]

    from shopping_shorts import bank_assemble
    monkeypatch.setattr(bank_assemble, "style_block", lambda style, seconds=30, seed="": "[스타일]")
    monkeypatch.setattr(SG, "_style_extra", lambda: "")
    monkeypatch.setattr(SG, "_speaker_judge", None)
    monkeypatch.setattr(SG, "_call_json", lambda prompt, schema, note=None:
                        {"beats": [{"role": "hook", "text": "a", "src_seg": "s0-1, s0-2", "needs_scene": True}]})
    d = SG.generate_one_style([{"name": "홈템", "full_text": "x", "structure": {}, "segments": _segs(3)}],
                              {"id": "t", "name": "t", "beat_roles": ["hook"], "chars_per_30s": 60},
                              target_seconds=10, grounded=True)
    assert d["beats"][0]["src_seg"] == "s0-1" and d["beats"][0]["src_segs"] == ["s0-1", "s0-2"]
