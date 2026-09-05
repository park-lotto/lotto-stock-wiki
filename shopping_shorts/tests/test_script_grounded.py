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


def test_장면_목록이_비면_grounded를_끄고_남긴다(monkeypatch):
    """리뷰 M7: 세그 없는 소스에 grounded면 '장면 근거'가 구조적으로 3회 실패."""
    from shopping_shorts import bank_assemble
    seen = []
    monkeypatch.setattr(bank_assemble, "style_block", lambda style, seconds=30, seed="": "[스타일]")
    monkeypatch.setattr(SG, "_style_extra", lambda: "")
    monkeypatch.setattr(SG, "_speaker_judge", None)
    monkeypatch.setattr(SG, "_call_json", lambda prompt, schema, note=None: seen.append(prompt) or
                        {"beats": [{"role": "hook", "text": "a", "src_seg": ""}]})
    note = {}
    d = SG.generate_one_style([{"name": "홈템", "full_text": "x", "structure": {}, "segments": []}],
                              {"id": "t", "name": "t", "beat_roles": ["hook"], "chars_per_30s": 60},
                              target_seconds=10, grounded=True, note=note)
    assert "[장면에 보이는 것만 써라" not in seen[0] and note.get("grounded_downgraded")
    assert not any(c["name"] == "장면 근거" for c in d["checks"])


def test_장면근거_문구는_상수에서_나온다():
    ok, det = GT.scene_grounding_check([{"text": f"줄{i}", "src_seg": "", "needs_scene": False} for i in range(6)], {"s0-0"})
    assert not ok and "절반" not in det and "34%" in det


# ─── 같은 장면이 두 칸에 중복(2026-09-05 실측) ────────────────────────────────
# 실측(b1_eye 15편 flow.json): 장면 붙은 칸 66개 중 6개가 중복(9%), 6건 중 5건이 **이웃한 두 칸**.
# 원인은 재고 부족이 아니었다 — 44구간짜리 영상에서도 났고, 15편 전부 장면 수 ≥ 필요 칸 수였다.
# 진짜 원인: _GROUNDED_RULE에 "같은 장면 두 번 쓰지 마라"가 없고 게이트도 안 봤다(지시·판정 둘 다 없음).

def test_장면중복_같은_번호가_두_칸에_있으면_반려():
    beats = [{"text": "때가 쏙 빠져요", "src_seg": "s0-3", "needs_scene": True},
             {"text": "심지어 향까지 좋아요", "src_seg": "s0-3", "needs_scene": True},
             {"text": "이건 진짜 물건이에요", "src_seg": "s0-4", "needs_scene": True}]
    ok, det = GT.scene_grounding_check(beats, {"s0-3", "s0-4", "s0-5"})
    assert not ok, "같은 장면을 두 칸에 썼는데 통과했다"
    assert "s0-3" in det and ("2번" in det or "1번" in det), det


def test_장면중복_대표장면만_본다_보조는_겹쳐도_된다():
    """한 줄이 여러 장면에 걸치면 쉼표로 적고 첫 번째가 대표다(_GROUNDED_RULE).
    보조 장면까지 막으면 정당한 '여러 장면에 걸친 줄'이 통째로 반려된다."""
    beats = [{"text": "물이 세게 나와요", "src_seg": "s0-1, s0-2", "needs_scene": True},
             {"text": "창틀 때도 지워져요", "src_seg": "s0-2, s0-1", "needs_scene": True}]
    ok, det = GT.scene_grounding_check(beats, {"s0-1", "s0-2"})
    assert ok, det


def test_장면중복_재고가_칸보다_적으면_봐준다():
    """장면이 2개뿐인데 3칸을 채워야 하면 중복이 불가피하다 — 그런 소재까지 영영 반려하면 안 된다.
    (실측 15편엔 이런 소재가 없었지만, 구간 5개짜리 영상이 있었다)"""
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "s0-1", "needs_scene": True},
             {"text": "다", "src_seg": "s0-0", "needs_scene": True}]
    ok, det = GT.scene_grounding_check(beats, {"s0-0", "s0-1"})
    assert ok, det


def test_장면중복_레시피는_면제():
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "s0-0", "needs_scene": True}]
    ok, _ = GT.scene_grounding_check(beats, {"s0-0", "s0-1", "s0-2"}, is_recipe=True)
    assert ok


def test_장면중복_지시가_프롬프트에_있다():
    """지시와 판정은 짝이다 — 판정만 넣으면 모델은 규칙을 모른 채 반려당하고 재작성만 반복한다."""
    assert "한 장면은 한 줄에만" in SG._GROUNDED_RULE


# ─── 여러 소스를 넣었는데 한 편만 쓰던 것(2026-09-05 실측) ──────────────────
# 실측(b1_two_sources 프로브 3회): 소스 2편을 넣어도 2단계가 고른 장면이 **전부 첫 소스**였다.
#   빠듯 2편(5+9구간)·넉넉 2편(19+22)·같은제품 2편(14+44) — 세 번 다 s1 사용 0.
# 사장님 지시(2026-08-17, _sources_for_generate 주석): "한 편만 넣으면 그 한 편에 끌려가 편협해진다.
#   담긴 것을 다 넣으면 고를 일이 없어진다 = 복불복이 사라진다."
# 원인은 중복 때와 같다 — **지시도 판정도 없었다**. 있는 것 중 앞부터 채우면 그만이었다.
# ⚠️단, 소스가 서로 다른 제품이면 억지로 섞는 게 오히려 해롭다 → 판정은 "쓸 수 있는데 안 썼나"만 본다.

def test_소스분산_두_소스_중_한쪽만_쓰면_반려():
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "s0-1", "needs_scene": True},
             {"text": "다", "src_seg": "s0-2", "needs_scene": True}]
    ids = {"s0-0", "s0-1", "s0-2", "s1-0", "s1-1", "s1-2"}
    ok, det = GT.scene_grounding_check(beats, ids, source_count=2)
    assert not ok, "두 소스를 줬는데 한쪽만 썼다 — 통과하면 안 된다"
    assert "s1" in det or "소스" in det, det


def test_소스분산_양쪽을_쓰면_통과():
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "s1-0", "needs_scene": True},
             {"text": "다", "src_seg": "s0-1", "needs_scene": True}]
    ok, det = GT.scene_grounding_check(beats, {"s0-0", "s0-1", "s1-0"}, source_count=2)
    assert ok, det


def test_소스분산_소스가_하나면_검사_안_한다():
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "s0-1", "needs_scene": True}]
    ok, det = GT.scene_grounding_check(beats, {"s0-0", "s0-1"}, source_count=1)
    assert ok, det


def test_소스분산_안_주면_종전과_같다():
    """source_count 없이 부르는 기존 호출부는 하나도 안 바뀐다(회귀 0)."""
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "s0-1", "needs_scene": True}]
    ok, _ = GT.scene_grounding_check(beats, {"s0-0", "s0-1", "s1-0", "s1-1"})
    assert ok


def test_소스분산_장면칸이_소스수보다_적으면_면제():
    """장면 붙은 줄이 1개뿐인데 2편을 다 쓰라는 건 불가능하다."""
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "", "needs_scene": False}]
    ok, det = GT.scene_grounding_check(beats, {"s0-0", "s1-0"}, source_count=2)
    assert ok, det


def test_소스분산_레시피는_면제():
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "s0-1", "needs_scene": True}]
    ok, _ = GT.scene_grounding_check(beats, {"s0-0", "s0-1", "s1-0"},
                                     source_count=2, is_recipe=True)
    assert ok


def test_소스분산_지시가_프롬프트에_있다():
    assert "여러 영상" in SG._GROUNDED_RULE and "한 영상에서만" in SG._GROUNDED_RULE


def test_소스분산_배선_generate가_source_count를_넘긴다():
    """판정 함수만 고치고 호출부가 안 넘기면 라이브에선 아무 일도 안 일어난다
    (메모리 '배선은 층마다'). 사보타주로 배선을 지우면 이 테스트가 빨개져야 한다."""
    import ast
    import pathlib
    src = (pathlib.Path(SG.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "check"
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "script_gate"]
    assert calls, "script_gate.check 호출을 못 찾았다(테스트가 낡았다)"
    bare = [n.lineno for n in calls if not any(k.arg == "source_count" for k in n.keywords)]
    assert not bare, f"source_count 없이 script_gate.check를 부르는 줄: {bare}"


def test_소스분산_배선_gate가_판정에_흘려보낸다():
    import ast
    import pathlib
    src = (pathlib.Path(GT.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "scene_grounding_check"]
    assert calls, "scene_grounding_check 호출을 못 찾았다"
    bare = [n.lineno for n in calls if not any(k.arg == "source_count" for k in n.keywords)]
    assert not bare, f"source_count를 안 넘기는 줄: {bare}"


def test_소스분산_한_소스만_썼어도_보조로_다른_소스를_봤으면_통과():
    """★2026-09-05 실측으로 드러난 결함: '두 소스를 다 썼나'만 보면 **소재가 다른 제품**일 때
    모델이 게이트를 통과하려고 억지로 섞는다(비비크림+방수패드 실측: 8칸 중 4칸이 딴 제품 화면).
    지시문엔 이미 "소재가 다른 제품이면 억지로 섞지 마라"고 적혀 있는데 판정이 그걸 안 봤다.

    → 판정을 완화한다: 대표(primary)가 한 소스뿐이어도 **보조 번호로라도 다른 소스를 참고**했으면
      통과. 다른 소스를 아예 안 본 경우(=목록을 훑지도 않은 경우)만 반려한다."""
    beats = [{"text": "가", "src_seg": "s0-0, s1-3", "needs_scene": True},
             {"text": "나", "src_seg": "s0-1", "needs_scene": True},
             {"text": "다", "src_seg": "s0-2", "needs_scene": True}]
    ok, det = GT.scene_grounding_check(beats, {"s0-0", "s0-1", "s0-2", "s1-3"}, source_count=2)
    assert ok, det


def test_소스분산_다른_소스를_아예_안_보면_여전히_반려():
    beats = [{"text": "가", "src_seg": "s0-0", "needs_scene": True},
             {"text": "나", "src_seg": "s0-1", "needs_scene": True},
             {"text": "다", "src_seg": "s0-2", "needs_scene": True}]
    ok, _ = GT.scene_grounding_check(beats, {"s0-0", "s0-1", "s0-2", "s1-0"}, source_count=2)
    assert not ok
