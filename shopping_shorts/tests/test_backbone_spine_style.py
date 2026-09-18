# -*- coding: utf-8 -*-
"""조립기가 스파인 문장틀·역할순서를 그대로 쓰는지(2026-09-17 사장님: "이븐쇼핑 스타일" = 천재·떼돈·「이건 바로 OO」·CTA 없음)."""
from shopping_shorts import backbone_assemble as ba

ROLES = ["title", "bait", "fame", "reveal", "limit", "solve", "more", "twist", "land"]
TPL = {"title": ["{나라} 천재가 만들어 떼돈 번 {제품군}의 정체"], "bait": ["평범한 이 {제품군}가"],
       "fame": ["천재가 떼돈을 벌었다는데"], "reveal": ["이건 바로 {제품}"], "limit": ["기존 {제품군}은 한계였는데"],
       "solve": ["이건 {효능}"], "more": ["심지어 {효능2}"], "twist": ["진짜 충격은 {효능3}"], "land": ["이러니 떼돈을 벌었다고"]}


def test_효능_자리만_특징줄이다():
    assert ba._feature_roles(ROLES, TPL) == ["solve", "more", "twist"]


def test_특징3개면_틀_그대로_9줄():
    plan = ba._spine_plan(ROLES, TPL, 3)
    assert [r for r, _ in plan] == ROLES
    assert [g for _, g in plan] == [-1, -1, -1, -1, -1, 0, 1, 2, -1]


def test_특징이_많으면_more를_twist_앞에_반복():
    plan = ba._spine_plan(ROLES, TPL, 5)
    assert [r for r, _ in plan] == ["title", "bait", "fame", "reveal", "limit", "solve", "more", "more", "more", "twist", "land"]
    assert [g for _, g in plan if g >= 0] == [0, 1, 2, 3, 4]


def test_특징이_적으면_남는_효능줄을_뺀다():
    plan = ba._spine_plan(ROLES, TPL, 1)
    assert [r for r, _ in plan] == ["title", "bait", "fame", "reveal", "limit", "solve", "land"]


def test_프롬프트에_CTA_금지와_문장틀이_들어간다():
    p = ba._spine_prompt({"product": "카메라", "order": [0, 1, 2]}, {"name": "이건 바로 OO"}, ROLES, TPL, ["  1. [0] a", "  2. [1] b", "  3. [2] c"], 20)
    assert "이건 바로 {제품}" in p and "CTA를 덧붙이지 마라" in p and "role=twist" in p


def test_틀_없는_스파인은_옛_경로():
    assert ba._spine_style({"name": "x"}) == ([], {})


def _idx(**kw):
    return {k: {"vid": "sub", "secs": v[0], "desc": v[1]} for k, v in kw.items()}


def test_구조줄이_특징_컷을_먼저_먹지_않는다():
    """job bb4c2734ce80 실측: title·bait·fame이 박스 컷 7개를 다 먹어 '패키지' 줄에 거리 풍경만 남았다."""
    idx = _idx(box1=(3.0, "박스 뚜껑을 열어 카메라가 드러남"), box2=(3.0, "구성품을 꺼내 보여줌"),
               whole=(3.0, "손으로 카메라 전체 형태를 보여줌"), street=(3.0, "거리 풍경 결과물"))
    groups = {"product": "카메라", "groups": [{"name": "패키지", "cuts": ["box1", "box2"]}], "order": [0]}
    lines = [{"role": "title", "text": "가" * 8, "group": -1},
             {"role": "bait", "text": "가" * 8, "group": -1},
             {"role": "solve", "text": "가" * 8, "group": 0}]
    bs, rep = ba.assign_cuts(lines, groups, idx, "bb")
    assert bs[2]["segs"][0] in ("box1", "box2"), bs
    assert bs[0]["segs"][0] in ("box1", "box2", "whole"), "구조 줄은 제품 컷(예약 외관→묶음 잔여)을 먼저, 거리 컷은 뒤: %s" % bs
    assert "street" not in bs[0]["segs"][:1]
    assert [b["role"] for b in bs] == ["title", "bait", "solve"], "출력 순서는 대본 순서 그대로"


def test_프롬프트의_group은_묶음_원번호다():
    g = {"product": "x", "order": [2, 0]}          # 순서 1번 = 묶음 2, 순서 2번 = 묶음 0
    p = ba._spine_prompt(g, {"name": "s"}, ROLES, TPL, ["a", "b"], 20)
    assert "role=solve, group=2 (특징 1번)" in p and "role=more, group=0 (특징 2번)" in p


def test_구조줄은_남은_제품컷을_먼저_사람컷은_맨뒤():
    idx = _idx(box1=(3.0, "박스를 열어 카메라가 드러남"), box2=(3.0, "구성품을 꺼냄"), box3=(3.0, "본체를 꺼내 보여줌"),
               face=(3.0, "남성이 카메라를 들고 구매처를 언급함"), cta=(3.0, "댓글 유도 화면"))
    groups = {"product": "카메라", "groups": [{"name": "패키지", "cuts": ["box1", "box2", "box3"]}], "order": [0]}
    lines = [{"role": "title", "text": "가" * 8, "group": -1}, {"role": "solve", "text": "가" * 8, "group": 0}]
    bs, _ = ba.assign_cuts(lines, groups, idx, "bb")
    assert bs[1]["segs"] and all(x.startswith("box") for x in bs[1]["segs"])
    assert bs[0]["segs"][0].startswith("box"), "묶음에서 남은 제품 컷을 먼저 쓴다: %s" % bs
    assert "face" not in bs[0]["segs"][:1] and "cta" not in bs[0]["segs"][:1]


def test_외관컷은_구조줄_몫으로_예약된다():
    """job bb50a7ba99ba: 특징 줄이 '옆면·뒷면 마감' 컷까지 써서 정체 줄엔 거리 풍경만 남았다."""
    idx = _idx(whole=(3.0, "손으로 카메라의 옆면과 뒷면을 돌려가며 마감을 보여줌"), open1=(3.0, "포장을 벗김"),
               open2=(3.0, "박스에서 꺼냄"), street=(3.0, "거리 풍경 결과물"))
    groups = {"product": "카메라", "groups": [{"name": "언박싱", "cuts": ["open1", "whole", "open2"]}], "order": [0]}
    lines = [{"role": "title", "text": "가" * 8, "group": -1}, {"role": "solve", "text": "가" * 20, "group": 0}]
    bs, _ = ba.assign_cuts(lines, groups, idx, "bb")
    assert bs[0]["segs"][0] in ("whole", "open2"), "구조 줄은 예약된 외관·박스 컷을 받는다: %s" % bs
    assert bs[1]["segs"][0] == "open1", "특징 줄은 예약 안 된 컷을 먼저 쓴다: %s" % bs


def test_seed가_문자열이어도_틀을_고른다():
    """배치는 seed=job id 문자열을 넘긴다(2026-09-18 4건 전부 TypeError)."""
    g = {"product": "x", "order": [0]}
    p1 = ba._spine_prompt(g, {"name": "s"}, ROLES, TPL, ["a"], 20, seed="iba25602b41")
    p2 = ba._spine_prompt(g, {"name": "s"}, ROLES, TPL, ["a"], 20, seed=3)
    assert "role=solve" in p1 and "role=solve" in p2


def test_어미_겹침을_잡고_기계로_고친다():
    """2026-09-18 실측 4건(job bba3a1e8f7a1·bbe6fcfabec1)."""
    bad = ["심지어 칸막이로 소품을 분류한다는는데.", "이건 틈새 공간을 최대로 활용한다는는데.",
           "연기를 강력하게 싹 빨아들여 주는는데.", "심지어 진짜 대박인 건 어디서나 가볍게 쓰는 건까지 해 준다는데.",
           "근대 진짜 충격적인 포인트는 설치 후 정리가 너무 완벽하다는 거."]
    for b in bad[:4]:
        assert ba._bad_join(b), b
    fixed = [ba._fix_join(b) for b in bad]
    assert fixed[0] == "심지어 칸막이로 소품을 분류한다는데." and fixed[2] == "연기를 강력하게 싹 빨아들여 주는데."
    assert fixed[3] == "심지어 진짜 대박인 건 어디서나 가볍게 쓰까지 해 준다는데." or "건까지 해" not in fixed[3]
    assert fixed[4].startswith("근데 ")
    for f in fixed[:3]:
        assert not ba._bad_join(f), f


def test_정상_문장은_안_건드린다():
    ok = ["이건 보풀 없이 식기 물기를 닦아낼 수 있다는 거.", "이게 말도 안 되는게 그냥 필터만 갈아 끼워주면 되는데.",
          "최근 누가 봐도 평범한 이 미니 후드 하나가 전 세계에서 미친 듯이 품절 대란이라는데.", "완벽하다고."]
    for o in ok:
        assert not ba._bad_join(o), o
        assert ba._fix_join(o) == o


class _FakeStore:
    def __init__(self, spines): self._s = spines
    def list_spines(self, status=None): return self._s


def test_유형을_주면_그_유형_스파인들을_순번대로_돈다():
    """2026-09-18 사장님: 오용형 고르면 그 유형 스파인들이 순번대로."""
    sp = [{"id": 60, "hook_3s": "x", "fit_categories": ["발명품형"]}, {"id": 65, "hook_3s": "x", "fit_categories": ["발명품형"]},
          {"id": 66, "hook_3s": "x", "fit_categories": ["발명품형"]}, {"id": 56, "hook_3s": "x", "fit_categories": ["오용형"]}]
    st = _FakeStore(sp)
    assert [ba.pick_hook_spine(st, seed=i, style="발명품형")["id"] for i in range(4)] == [60, 65, 66, 60]
    assert ba.pick_hook_spine(st, seed="jobid-abc", style="오용형")["id"] == 56
    assert ba.pick_hook_spine(st, spine_id=56, seed=0, style="발명품형")["id"] == 56, "spine_id가 우선"
    assert ba.pick_hook_spine(st, seed=0, style="없는유형")["id"] in (56, 60, 65, 66), "유형에 스파인이 없으면 무작위 폴백"


def test_특징이_많아도_틀_밖_반복은_2줄까지():
    plan = ba._spine_plan(ROLES, TPL, 7)      # 효능 자리 3개 + 특징 7개
    assert len([1 for r, g in plan if g >= 0]) == 3 + ba.MAX_EXTRA_FEATURE_LINES
