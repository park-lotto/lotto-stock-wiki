"""관제 058 B단계 — '템플릿 없이 완성본'의 기본 자막·제목 스타일을 새 편집기 한 곳(ensureLegacyStyleDefaults)이 넣는다.
옛 피팅룸(applyDefaultStyleOnEntry·applyErasedRegion)과 같은 규칙: 비어 있을 때만 심플 화이트 · 새로 넣은 경우만 지운 자리로."""
import json, pathlib, re, subprocess


def _fn_block(src):
    i = src.index("const SIMPLE_WHITE_CAP=")
    j = src.index("window.openSceneStyleEditor=async()=>{")
    return src[i:j]


def _run(state, status_json, tmp_path):
    src = (pathlib.Path(__file__).resolve().parents[1] / "static" / "scene-style-produce.js").read_text(encoding="utf-8")
    js = f"""
const STATE={json.dumps(state)};
globalThis.fetch=async()=>({{json:async()=>({json.dumps(status_json)})}});
{_fn_block(src)}
ensureLegacyStyleDefaults('j1').then(()=>console.log(JSON.stringify(STATE)));
"""
    (tmp_path / "t.js").write_text(js, encoding="utf-8")
    return json.loads(subprocess.run(["node", str(tmp_path / "t.js")], capture_output=True, check=True).stdout.decode("utf-8"))


def test_empty_state_gets_simple_white_and_snaps_to_erased_region(tmp_path):
    out = _run({"captionStyle": None, "headcopy": None}, {"clean_regions": {"primary": {"x_pct": 48.6, "y_pct": 71.2}}}, tmp_path)
    cs, hc = out["captionStyle"], out["headcopy"]
    assert cs["font"] == "Pretendard-ExtraBold.otf" and cs["size"] == 50 and cs["shadow"] is True and cs["effect"] == "fade"
    assert (cs["x_pct"], cs["y_pct"]) == (49, 71)                 # 지운 자리로 옮김(반올림)
    assert hc["font"] == "Pretendard-ExtraBold.otf" and hc["size"] == 54 and hc["text"] == ""


def test_empty_state_without_region_keeps_default_position(tmp_path):
    out = _run({"captionStyle": None, "headcopy": None}, {"clean_regions": None}, tmp_path)
    assert (out["captionStyle"]["x_pct"], out["captionStyle"]["y_pct"]) == (50, 37)


def test_saved_style_is_never_touched(tmp_path):
    saved = {"font": "NanumGothic-Bold.ttf", "size": 54, "y_pct": 84, "x_pct": 50, "shadow": False}
    out = _run({"captionStyle": dict(saved), "headcopy": {"text": "제목", "size": 60}},
               {"clean_regions": {"primary": {"x_pct": 10, "y_pct": 10}}}, tmp_path)
    assert out["captionStyle"] == saved and out["headcopy"] == {"text": "제목", "size": 60}
