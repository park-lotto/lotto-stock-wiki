import json as _json

from shopping_shorts.mix_pipeline import _apply_motion_pack
import shopping_shorts.mix_pipeline as mp
from shopping_shorts.store import Store

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


def test_run_render_pack_id_reads_packs_from_MOTION_ASSETS_DIR(tmp_path, monkeypatch):
    """리뷰 Important I-1 회귀 테스트.

    run_render는 pack_id가 있으면 load_packs()를 호출해 팩 카탈로그를 읽고,
    resolve_layers(..., MOTION_ASSETS_DIR)로 asset_id를 실경로로 해석한다. 팩과
    매니페스트·자산 파일을 **한 tmp 디렉터리**에 같이 두고 MOTION_ASSETS_DIR만
    그 디렉터리로 monkeypatch하면: load_packs가 인자 없이(=repo 기본경로) 불리는
    회귀가 있을 경우 "p1" 팩이 repo 카탈로그엔 없어 조용히 '모르는 pack_id'로
    무시되고 layers가 비어버린다. load_packs(MOTION_ASSETS_DIR)로 고치면 팩이
    tmp에서 발견되고 resolve_layers도 같은 tmp에서 자산을 찾아 레이어가 채워진다
    — 즉 이 테스트는 "팩과 자산이 같은 디렉터리에서 읽힌다"를 못박는다.
    """
    adir = tmp_path / "assets"
    adir.mkdir()
    (adir / "swipe_left.mov").write_bytes(b"\x00")
    (adir / "manifest.json").write_text(_json.dumps({"assets": [
        {"id": "swipe_left", "type": "transition", "file": "swipe_left.mov",
         "default": {"width": 1080, "x": 50, "y": 50}}]}), encoding="utf-8")
    (adir / "packs.json").write_text(_json.dumps({"packs": [
        {"id": "p1", "transition": {"asset_id": "swipe_left", "dur": 0.5, "lead": 0.0,
                                     "policy": "hook_climax"}}]}), encoding="utf-8")
    monkeypatch.setattr(mp, "MOTION_ASSETS_DIR", str(adir))

    # _beat_timeline은 tts mp3를 ffprobe로 실측한다 — 팩/자산 디렉터리 일치 여부와
    # 무관한 관심사라 고정 타임라인으로 대체해 테스트 범위를 좁힌다.
    # 2비트 이상 필요: transition은 비트 "경계"에 배치되므로(motion_packs._boundaries가
    # timeline[1:]) 1비트짜리 타임라인은 경계가 없어 팩이 정상 동작해도 레이어가 0이 된다.
    fixed_tl = [
        {"beat_idx": 0, "t0": 0.0, "dur": 3.0, "narration": "n1", "role": "hook"},
        {"beat_idx": 1, "t0": 3.0, "dur": 2.0, "narration": "n2", "role": "body"},
    ]
    monkeypatch.setattr(mp, "_beat_timeline", lambda plan, tts_paths: fixed_tl)

    db = tmp_path / "t.db"
    store = Store(db)
    store.create_mix_job("jm", ["u0"], 20, "free")
    store.update_mix_job("jm", status="ready_for_review",
        edit_plan={"structure": "free", "beats": [
            {"beat_idx": 0, "role": "훅", "narration": "n", "tts_path": str(tmp_path / "t.mp3")}]},
        deco={"motion": {"pack_id": "p1"}})
    work = tmp_path / "work" / "jm"; work.mkdir(parents=True)
    (work / "s0").mkdir(); (work / "s0" / "a.mp4").write_bytes(b"\x00")
    (tmp_path / "t.mp3").write_bytes(b"\x00")

    captured = {}
    monkeypatch.setattr(mp, "assemble", lambda *a, **k: captured.update(k) or "x")
    mp.run_render("jm", str(db), str(tmp_path / "work"))

    deco = captured["deco"]
    layers = (deco.get("motion") or {}).get("layers") or []
    assert layers, "팩의 레이어가 채워지지 않음 — load_packs가 MOTION_ASSETS_DIR을 안 보고 있다"
    assert layers[0]["asset_id"] == "swipe_left"
    assert layers[0]["_abspath"].endswith("swipe_left.mov")
