"""프리셋 저장·재사용(tools/calcopy/engine/preset_save.py) — 왕복·manifest 필수 항목·변수 자리·변수 채우기."""
import copy
import json
from pathlib import Path

import pytest

from shopping_shorts.calcopy_frame import schema
from tools.calcopy.engine import preset_save as P

ROOT = Path(__file__).resolve().parents[2]
FRAME_A = json.loads((ROOT / "shopping_shorts/calcopy_frame/examples/frame_A_auto_ZdeZRtCeAC4.json").read_text(encoding="utf-8"))
J = {"engine": "합성", "measured_at": "2026-10-16", "unknown": ["시험"]}


def title(f):
    return next(l for l in f["layers"] if l.get("role") == "title")


def other_video(f):
    """같은 틀의 다른 편: 창·제목 자리·크기·줄 색·글자만 다르다(1_V 꼴)."""
    g = copy.deepcopy(f); g.pop("made_from", None)
    v = next(l for l in g["layers"] if l["kind"] == "video"); v["y"], v["h"] = 352, 1269
    t = title(g); t.update(y=140, size=106.8, line_h=110, line_rgb=[[0, 0, 0], [186, 0, 120]], text="다이소 기획자도 감탄한\n공간 활용 끝판왕")
    return g


def test_save_load_roundtrip_and_manifest(tmp_path):
    d = tmp_path / "sseolpulda" / "preset" / "A_흰바탕창"
    M = P.save(J, FRAME_A, d, "ZdeZRtCeAC4", "x/뜯기.json")
    pre, M2 = P.load(d)
    assert M2 == M and all(k in M2 for k in P.REQUIRED_MANIFEST)
    assert M2["slug"] == "sseolpulda" and M2["style"] == "A_흰바탕창" and M2["made_by"] == P.MADE_BY
    assert [s["id"] for s in M2["sources"]] == ["ZdeZRtCeAC4"] and M2["sources"][0]["font_confidence"] == FRAME_A["made_from"]["font_confidence"]
    assert M2["variables"] == ["layers[text:title].text"]               # 처음엔 제목 글자만 변수
    # 왕복: 변수에 원래 값을 넣으면 원래 설명서와 같다(정규화 기준)
    back = P.apply(pre, FRAME_A)
    assert schema.validate(back) == schema.validate({k: v for k, v in FRAME_A.items() if k != "made_from"})


def test_merge_marks_only_differing_places(tmp_path):
    d = tmp_path / "s" / "preset" / "A"
    P.save(J, FRAME_A, d, "ZdeZRtCeAC4", "x")
    M = P.save(J, other_video(FRAME_A), d, "1_VtwOkbbVE", "y")
    assert set(M["variables"]) == {"layers[video].y", "layers[video].h", "layers[text:title].y", "layers[text:title].size",
                                   "layers[text:title].line_h", "layers[text:title].line_rgb", "layers[text:title].text"}
    pre, _ = P.load(d)
    assert next(l for l in pre["layers"] if l.get("role") == "brand")["font"] == "TmonMonsori"   # 같은 값은 고정
    assert [s["id"] for s in M["sources"]] == ["ZdeZRtCeAC4", "1_VtwOkbbVE"]
    with pytest.raises(ValueError):
        P.save(J, FRAME_A, d, "ZdeZRtCeAC4", "x")                        # 같은 편 두 번 = 거절


def test_apply_fills_variables_and_refuses_unfilled(tmp_path):
    d = tmp_path / "s" / "preset" / "A"
    P.save(J, FRAME_A, d, "ZdeZRtCeAC4", "x")
    P.save(J, other_video(FRAME_A), d, "1_VtwOkbbVE", "y")
    pre, _ = P.load(d)
    target = other_video(FRAME_A)
    out = P.apply(pre, target)
    assert title(out)["line_rgb"] == [[0, 0, 0], [186, 0, 120]] and title(out)["text"].startswith("다이소")
    assert next(l for l in out["layers"] if l["kind"] == "video")["y"] == 352
    out2 = P.apply(pre, target, {"layers[text:title].text": "새 제목\n둘째 줄"})   # 덮어쓰기가 먼저
    assert title(out2)["text"] == "새 제목\n둘째 줄"
    with pytest.raises(ValueError) as e:
        P.apply(pre, None, {"layers[text:title].text": "x"})                # 그 편 값 없이 = 못 채운 변수 목록으로 멈춤
    assert "layers[video].y" in str(e.value)


def test_exclude_layer_is_not_compared(tmp_path):
    d = tmp_path / "s" / "preset" / "A"
    P.save(J, FRAME_A, d, "Z", "x")
    g = copy.deepcopy(FRAME_A); g.pop("made_from", None)
    next(l for l in g["layers"] if l.get("role") == "caption")["y"] = 132   # 분석기가 자막을 제목으로 잘못 읽은 편(D9)
    M = P.save(J, g, d, "7D", "y", exclude=("text:caption",))
    assert not any("caption" in v for v in M["variables"]) and M["sources"][1]["excluded_layers"] == ["text:caption"]
