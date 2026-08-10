"""change(사물이 주어인 변화·감각) 필드 — 추출 → 인벤토리 → 앵커 중복제거까지 배선 검증.

왜(2026-07-31 사장님): 레퍼런스 3편의 진짜 포인트가 전부 사물 주어의 변화였다
("프린팅이 갈라지다→매끈해지다", "양념이 튀다/가림막이 막아주다", "촉감이 모찌같다").
action(ACTION_VOCAB 30개)은 **전부 사람 손동작**이라 이걸 하나도 못 담았고,
그래서 대본이 화면의 중요 행동과 계속 어긋났다.
"""
from shopping_shorts import edit_plan, script_extract


def _seg(sid_n, desc, change="", **kw):
    d = {"start": sid_n, "end": sid_n + 1, "text": "", "scene_desc": desc, "change": change}
    d.update(kw)
    return d


def test_assign_seg_ids_carries_change():
    out = script_extract._assign_seg_ids("v1", [_seg(0, "티셔츠", " 프린팅이 갈라져 있다 ")])
    assert out[0]["change"] == "프린팅이 갈라져 있다"


def test_old_extract_without_change_is_empty_not_crash():
    """옛 추출본엔 필드가 없다 — 빈 문자열로 떨어져야 하류가 그 칸을 통째로 생략한다."""
    out = script_extract._assign_seg_ids("v1", [{"start": 0, "end": 1, "text": "",
                                                 "scene_desc": "티셔츠"}])
    assert out[0]["change"] == ""


def _inv(segs):
    return edit_plan._build_inventory([{"video_id": "v1", "segments": segs}])


def test_inventory_line_shows_change():
    segs = [_seg(i, "머리", "") for i in range(3)]
    segs[1] = dict(segs[1], seg_id="v1-1", change="크랙이 사라지고 매끈해졌다")
    for i, s in enumerate(segs):
        s["seg_id"] = f"v1-{i}"
    _, block = _inv(segs)
    assert "변화:크랙이 사라지고 매끈해졌다" in block


def test_inventory_omits_change_when_empty():
    segs = [dict(_seg(i, "머리"), seg_id=f"v1-{i}") for i in range(3)]
    _, block = _inv(segs)
    assert "변화:" not in block


def test_dedup_keeps_opposite_changes_on_same_object():
    """대상이 같고 일어난 일이 반대인 컷은 서로 다른 앵커다(예전엔 scene_desc 토큰만 봐서 접혔다)."""
    a = {"seg_id": "v1-1", "scene_desc": "가림막 후드 주변", "change": "기름이 사방으로 튄다"}
    b = {"seg_id": "v1-5", "scene_desc": "가림막 후드 주변", "change": "가림막이 기름을 막아준다"}
    assert len(edit_plan._dedup_anchors([a, b])) == 2


def test_dedup_still_collapses_true_duplicates():
    a = {"seg_id": "v1-1", "scene_desc": "가림막 후드 주변", "change": "기름이 사방으로 튄다"}
    b = {"seg_id": "v1-2", "scene_desc": "가림막 후드 주변", "change": "기름이 사방으로 튄다"}
    assert len(edit_plan._dedup_anchors([a, b])) == 1


def test_prompt_demands_screen_match():
    """대본 프롬프트가 '변화' 칸을 근거로 화면 일치를 요구하는지."""
    import inspect
    src = inspect.getsource(edit_plan._scene_first_candidates)
    assert "화면 일치" in src and "변화:" in src
