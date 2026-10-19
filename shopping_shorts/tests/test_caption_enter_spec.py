"""범용 등장 스펙(관제 235) — 서버 정리 한 곳(clean_caption_enter)과 계약 파일 표."""
import pytest
from shopping_shorts import scene_style as ss


def test_clean_keeps_valid_spec():
    out = ss.clean_caption_enter({"keyframes": [{"t": 0, "scale": 22}, {"t": .4, "scale": 100}], "cps": 12, "cursor": {"char": "_", "blink_ms": 400},
                                  "glow": {"decay_ms": 300}, "exit": {"kind": "fade", "ms": 200}})
    assert out["cps"] == 12 and out["exit"] == {"kind": "fade", "ms": 200} and len(out["keyframes"]) == 2


@pytest.mark.parametrize("bad", [{"kind": "nope"}, {"kind": "pop", "ms": 99999}, {"keyframes": [{"t": 0, "alpha": 300}]}, {}, "pop", {"kind": "pop", "exit": {"kind": "spin"}}])
def test_clean_rejects(bad):
    assert ss.clean_caption_enter(bad) is None


def test_snapshot_rejects_bad_caption_enter():
    from tools.caption_pack.check_bench_packs import snapshot
    with pytest.raises(ValueError):
        ss.validate_snapshot({**snapshot("kitchit"), "captionEnter": {"kind": "pop", "ms": 99999}})


def test_new_motion_and_packs_in_contract():
    assert {"shake", "glPop"} <= set(ss.caption_motion_keys()) and {"recipe", "goodletter"} <= set(ss.caption_pack_keys())
