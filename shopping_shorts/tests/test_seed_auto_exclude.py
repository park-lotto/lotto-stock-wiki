"""씨앗 영상: 영상 소스엔 넣되 자동 배치에서만 뺀다(2026-09-30 사장님). 표식의 주인 = mix_pipeline.mark_auto_exclude."""
from shopping_shorts import mix_pipeline, edit_plan, backbone_assemble as ba


def _src(vid, n=6):
    return {"video_id": vid, "segments": [{"seg_id": f"{vid}-{i}", "start": i * 2.0, "end": i * 2.0 + 2.0,
                                          "text": f"t{i}", "scene_desc": f"d{i}"} for i in range(n)]}


def test_mark_only_listed_index_and_ignores_garbage():
    ex = {"s0": _src("s0"), "s1": _src("s1")}
    mix_pipeline.mark_auto_exclude(ex, {"script_structure": {"no_auto_idx": [0, "x", 9]}})
    assert ex["s0"].get("auto_exclude") is True and "auto_exclude" not in ex["s1"]


def test_no_structure_changes_nothing():
    ex = {"s0": _src("s0")}
    mix_pipeline.mark_auto_exclude(ex, {})
    assert "auto_exclude" not in ex["s0"]


def test_inventory_keeps_seed_in_seg_map_but_out_of_auto_stock_and_prompt():
    seed, other = _src("s0"), _src("s1")
    seed["auto_exclude"] = True
    seg_map, prompt = edit_plan._build_inventory([seed, other])
    assert any(k.startswith("s0-") for k in seg_map)                 # 사람이 고르는 화면용엔 있다
    auto = edit_plan.non_edge_segs(seg_map)
    assert not any(k.startswith("s0-") for k in auto)                # 자동 배치 재고엔 없다
    assert any(k.startswith("s1-") for k in auto)
    assert "s0-2" not in prompt and "s1-2" in prompt                 # 모델 인벤토리에도 없다


def test_seg_index_skips_seed():
    seed, other = _src("s0"), _src("s1")
    seed["auto_exclude"] = True
    idx = ba._seg_index([seed, other])
    assert not any(k.startswith("s0-") for k in idx) and any(k.startswith("s1-") for k in idx)


def _js_fn(src, name):
    import re
    m = re.search(r"function %s\(.*?\n\}\n" % re.escape(name), src, re.S)
    assert m, name
    return m.group(0)


def test_produce_js_sends_seed_index_and_migrates_old_saves(tmp_path):
    """화면: 씨앗은 useFootage를 끄지 않고 no_auto_idx로 보낸다 · 옛 저장본(_seedFootageOff)은 새 규칙으로 옮긴다."""
    import json, pathlib, subprocess
    src = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")
    js = _js_fn(src, "collectNoAutoIdx") + _js_fn(src, "_migrateSeedFlags") + """
const HANDOFF = _migrateSeedFlags([
  {url:'https://a/1', shortcode:'A', useFootage:false, _seedFootageOff:true},
  {url:'https://b/2', shortcode:'B', useFootage:true},
  {url:'https://c/3', shortcode:'C', useFootage:false},
]);
const urls = HANDOFF.filter(h=>h.useFootage).map(h=>h.url);
console.log(JSON.stringify({urls, idx: collectNoAutoIdx(urls), a: HANDOFF[0]}));
"""
    (tmp_path / "t.js").write_text(js, encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(tmp_path / "t.js")], capture_output=True, text=True, check=True).stdout)
    assert out["urls"] == ["https://a/1", "https://b/2"]        # 씨앗 A가 job에 들어간다
    assert out["idx"] == [0]                                      # 그리고 자동배치 제외 인덱스로 표시된다
    assert out["a"]["seedNoAuto"] is True and "_seedFootageOff" not in out["a"]
