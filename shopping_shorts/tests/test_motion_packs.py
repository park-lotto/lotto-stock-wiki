from shopping_shorts.motion_packs import build_plan

TL = [                              # 경계: 3.0, 7.0 (첫 비트 시작 0.0은 경계 아님)
    {"beat_idx": 0, "t0": 0.0, "dur": 3.0, "narration": "훅", "role": "hook"},
    {"beat_idx": 1, "t0": 3.0, "dur": 4.0, "narration": "본문", "role": "body"},
    {"beat_idx": 2, "t0": 7.0, "dur": 2.0, "narration": "마무리", "role": "cta"},
]

PACK_EVERY = {
    "id": "dynamic_pop",
    "transition": {"asset_id": "swipe_left", "dur": 0.5, "lead": 0.25, "policy": "every_beat"},
    "sticker": {"asset_id": "sparkle", "dur": 1.0, "policy": "hook_climax"},
    "color_filter": "eq=saturation=1.15",
}


def test_every_beat는_모든_경계에_전환을_넣는다():
    p = build_plan(PACK_EVERY, TL)
    tr = [L for L in p["layers"] if L["asset_id"] == "swipe_left"]
    assert [round(L["start"], 3) for L in tr] == [2.75, 6.75]     # t0 - lead
    assert all(L["dur"] == 0.5 for L in tr)


def test_hook_climax_스티커는_첫비트와_마지막비트_시작에():
    p = build_plan(PACK_EVERY, TL)
    st = [L for L in p["layers"] if L["asset_id"] == "sparkle"]
    assert [round(L["start"], 3) for L in st] == [0.0, 7.0]        # 비트 시작
    assert all(L["dur"] == 1.0 for L in st)


def test_hook_climax_전환은_첫경계와_마지막경계만():
    # 경계 3개(4비트)짜리 타임라인으로 every_beat와 hook_climax가 서로 다른 결과를
    # 내는 것을 대조한다. TL(경계 2개)로는 두 정책이 우연히 같아져 정책 차이를
    # 전혀 증명하지 못한다.
    tl4 = [
        {"beat_idx": 0, "t0": 0.0, "dur": 2.0, "narration": "훅", "role": "hook"},
        {"beat_idx": 1, "t0": 2.0, "dur": 2.0, "narration": "본문1", "role": "body"},
        {"beat_idx": 2, "t0": 4.0, "dur": 2.0, "narration": "본문2", "role": "body"},
        {"beat_idx": 3, "t0": 6.0, "dur": 2.0, "narration": "마무리", "role": "cta"},
    ]                                                       # 경계: 2.0, 4.0, 6.0

    pack_every = pack = {**PACK_EVERY, "transition": {**PACK_EVERY["transition"], "policy": "every_beat"}}
    tr_every = [L for L in build_plan(pack_every, tl4)["layers"] if L["asset_id"] == "swipe_left"]
    assert [round(L["start"], 3) for L in tr_every] == [1.75, 3.75, 5.75]     # 경계 3개 전부

    pack_climax = {**PACK_EVERY, "transition": {**PACK_EVERY["transition"], "policy": "hook_climax"}}
    tr_climax = [L for L in build_plan(pack_climax, tl4)["layers"] if L["asset_id"] == "swipe_left"]
    assert [round(L["start"], 3) for L in tr_climax] == [1.75, 5.75]          # 첫·마지막 경계만(가운데 4.0 빠짐)

    assert tr_climax != tr_every                                              # 두 정책은 서로 달라야 한다


def test_lead가_0아래로_내려가면_0으로_clamp():
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": 0.1, "narration": "", "role": "hook"},
          {"beat_idx": 1, "t0": 0.1, "dur": 3.0, "narration": "", "role": "body"}]
    tr = [L for L in build_plan(PACK_EVERY, tl)["layers"] if L["asset_id"] == "swipe_left"]
    assert tr[0]["start"] == 0.0                                   # 0.1 - 0.25 → clamp


def test_policy_none이면_해당_레이어_없음():
    pack = {"id": "x",
            "transition": {"asset_id": "swipe_left", "dur": 0.5, "lead": 0.2, "policy": "none"},
            "sticker": {"asset_id": "sparkle", "dur": 1.0, "policy": "none"}}
    assert build_plan(pack, TL)["layers"] == []


def test_빈_타임라인이면_레이어_없음():
    assert build_plan(PACK_EVERY, [])["layers"] == []


def test_비트가_하나면_경계가_없어_전환은_없지만_스티커는_있다():
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": 3.0, "narration": "훅", "role": "hook"}]
    p = build_plan(PACK_EVERY, tl)
    assert [L["asset_id"] for L in p["layers"]] == ["sparkle"]


def test_color_filter를_그대로_넘긴다():
    assert build_plan(PACK_EVERY, TL)["color_filter"] == "eq=saturation=1.15"
    assert build_plan({"id": "x"}, TL)["color_filter"] is None


import json

from shopping_shorts.motion_packs import load_packs


def test_packs_json을_id로_인덱싱한다(tmp_path):
    (tmp_path / "packs.json").write_text(json.dumps({"packs": [
        {"id": "a", "name": "A"}, {"id": "b", "name": "B"},
    ]}), encoding="utf-8")
    packs = load_packs(str(tmp_path))
    assert set(packs) == {"a", "b"}
    assert packs["a"]["name"] == "A"


def test_파일이_없으면_빈dict(tmp_path):
    assert load_packs(str(tmp_path)) == {}


def test_id없는_항목은_무시(tmp_path):
    (tmp_path / "packs.json").write_text(json.dumps({"packs": [
        {"name": "no id"}, {"id": "ok"},
    ]}), encoding="utf-8")
    assert set(load_packs(str(tmp_path))) == {"ok"}


def test_실제_packs_json이_로드되고_스키마를_지킨다():
    from shopping_shorts.motion_assets import load_manifest

    packs = load_packs()
    assert packs, "assets/motion/packs.json이 비었다"
    manifest = load_manifest()
    for pid, p in packs.items():
        assert p["id"] == pid
        assert p.get("name")
        assert p.get("intensity") in ("low", "mid", "high")
        for key in ("transition", "sticker"):
            sub = p.get(key) or {}
            if not sub:
                continue
            assert sub.get("policy") in ("every_beat", "hook_climax", "none")
            asset_id = sub.get("asset_id")
            if asset_id:
                assert asset_id in manifest, (
                    f"{pid}.{key}.asset_id={asset_id!r}가 manifest.json에 없다"
                    " — resolve_layers가 조용히 skip해 모션이 안 나온다"
                )
            if "dur" in sub:
                dur = sub["dur"]
                assert isinstance(dur, (int, float)) and not isinstance(dur, bool), (
                    f"{pid}.{key}.dur={dur!r}는 수치형이어야 한다"
                    " (문자열이면 build_plan의 float()에서 ValueError)"
                )
