from shopping_shorts.mix_pipeline import _apply_motion_pack

TL = [
    {"beat_idx": 0, "t0": 0.0, "dur": 3.0, "narration": "훅", "role": "hook"},
    {"beat_idx": 1, "t0": 3.0, "dur": 4.0, "narration": "본문", "role": "body"},
]

PACKS = {"p1": {
    "id": "p1",
    "transition": {"asset_id": "swipe_left", "dur": 0.5, "lead": 0.25, "policy": "every_beat"},
    "caption": {"effect": "pop"},
    "headcopy": {"policy": "hook_only"},
    "color_filter": "eq=saturation=1.2",
}}


def test_pack_id가_레이어와_색감_자막효과를_채운다():
    deco, cs = _apply_motion_pack({"motion": {"pack_id": "p1"}}, {}, TL, PACKS)
    assert [L["asset_id"] for L in deco["motion"]["layers"]] == ["swipe_left"]
    assert deco["motion"]["color_filter"] == "eq=saturation=1.2"
    assert deco["motion"]["_headcopy_enable"] == "between(t,0,3.000)"
    assert cs["effect"] == "pop"


def test_사용자_지정값이_팩보다_우선():
    deco, cs = _apply_motion_pack(
        {"motion": {"pack_id": "p1", "color_filter": "eq=contrast=2"}},
        {"effect": "slide"}, TL, PACKS)
    assert deco["motion"]["color_filter"] == "eq=contrast=2"
    assert cs["effect"] == "slide"


def test_수동_레이어는_팩_레이어_뒤에_보존된다():
    manual = {"asset_id": "sparkle", "start": 9.0, "dur": 1.0}
    deco, _ = _apply_motion_pack(
        {"motion": {"pack_id": "p1", "layers": [manual]}}, {}, TL, PACKS)
    assert [L["asset_id"] for L in deco["motion"]["layers"]] == ["swipe_left", "sparkle"]


def test_모르는_pack_id는_모션없이_통과():
    deco, cs = _apply_motion_pack({"motion": {"pack_id": "없음"}}, {}, TL, PACKS)
    assert deco["motion"].get("layers", []) == []
    assert cs == {}


def test_pack_id가_없으면_deco_무변경():
    src = {"motion": {"layers": [{"asset_id": "sparkle", "start": 1.0, "dur": 1.0}]}}
    deco, cs = _apply_motion_pack(src, {}, TL, PACKS)
    assert deco["motion"]["layers"] == src["motion"]["layers"]


def test_motion이_아예_없어도_안전():
    deco, cs = _apply_motion_pack({}, None, TL, PACKS)
    assert deco == {}
    assert cs is None


def test_headcopy_enable_문자열_포맷을_못박는다():
    """motion_packs._headcopy_enable이 between(t,0,...)로 시작을 0에 하드코딩한다.
    현재는 timeline[0]["t0"]가 항상 0이라 결과가 같지만, 계약이 고정돼 있지 않다.
    첫 비트 t0=0.0, dur=3.0 → "between(t,0,3.000)" 정확한 포맷을 못박는다(Task2 리뷰어 권고)."""
    deco, _ = _apply_motion_pack({"motion": {"pack_id": "p1"}}, {}, TL, PACKS)
    assert deco["motion"]["_headcopy_enable"] == "between(t,0,3.000)"
