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


# ── 관제 138(2026-10-06): 자동 배치 후보의 주인 = edit_plan.non_edge_segs/auto_segs/auto_sources ──
#   라이브 6일 씨앗 표식 작업 82건 중 36건에서 씨앗 컷이 자동 컷으로 샜다. 아래는 샌 길 하나씩.
_LONG = "이 문장은 화면을 여러 개 붙여야 할 만큼 충분히 길게 쓴 대사입니다 정말로 아주 길게 이어지는 설명이에요"


def _seeded(n_other=5):
    seed, other = _src("s0", 8), _src("s1", n_other)
    seed["auto_exclude"] = True
    return seed, other


def _is_seed(ref):
    return bool(ref) and str(ref.get("seg_id") or "").startswith("s0-")


def _beat(seg_map, sid, narration=_LONG, **kw):
    return dict({"beat_idx": 0, "role": "demo", "narration": narration, "target_seconds": edit_plan.narr_secs(narration),
                 "primary": edit_plan._ground_ref({"seg_id": sid}, seg_map), "alternates": []}, **kw)


def test_fill_screen_time_never_adds_seed_cut():
    seed, other = _seeded()
    seg_map, _ = edit_plan._build_inventory([seed, other])
    beats = edit_plan._fill_beat_screen_time([_beat(seg_map, "s1-2")], seg_map)
    refs = [beats[0]["primary"]] + list(beats[0].get("alternates") or [])
    assert len(refs) > 1                                   # 실제로 채웠고
    assert not any(_is_seed(r) for r in refs)              # 씨앗 컷은 안 붙였다


def test_repick_candidates_shown_to_model_exclude_seed():
    seed, other = _seeded()
    seg_map, _ = edit_plan._build_inventory([seed, other])
    seen = {}

    def _call(prompt, *a, **k):
        seen["prompt"] = prompt
        return {}
    edit_plan._repick_weak_beats([_beat(seg_map, "s1-2", fit=2)], seg_map, call=_call)
    assert "[s1-1]" in seen["prompt"] and "[s0-" not in seen["prompt"]


def test_inherit_plan_drops_seed_cut_named_by_stage2_but_keeps_human_pin():
    seed, other = _seeded(8)
    script = "첫 문장은 이렇게 시작합니다.\n둘째 문장은 이렇게 이어집니다."
    bs = [{"role": "hook", "seg": "s0-3", "segs": ["s0-3"]}, {"role": "demo", "seg": "s1-3", "segs": ["s1-3"]}]
    plan = edit_plan.build_inherit_plan([seed, other], script, bs)
    refs = [r for b in plan["beats"] for r in [b["primary"]] + list(b.get("alternates") or [])]
    assert not any(_is_seed(r) for r in refs)              # 2단계가 지목해도 자동으론 안 잇는다
    bs[0]["pinned"] = True                                 # 사람이 스토리보드에서 직접 고른 줄은 그대로
    plan = edit_plan.build_inherit_plan([seed, other], script, bs)
    assert plan["beats"][0]["primary"]["seg_id"] == "s0-3"


def test_save_gate_does_not_put_seed_source_cut():
    from shopping_shorts import store as _store
    seed, other = _seeded(8)
    seg_map, _ = edit_plan._build_inventory([seed, other])
    beats = [_beat(seg_map, "s1-2")]
    _store._apply_beat_sources(beats, {"beat_sources": [{"role": "demo", "seg": "s0-3"}]}, seg_map)
    assert beats[0]["primary"]["seg_id"] == "s1-2"
    _store._apply_beat_sources(beats, {"beat_sources": [{"role": "demo", "seg": "s1-4"}]}, seg_map)
    assert beats[0]["primary"]["seg_id"] == "s1-4"         # 재료 컷은 종전대로 꽂는다


def test_exit_check_strips_seed_and_counts_leaks():
    seed, other = _seeded(8)
    seg_map, _ = edit_plan._build_inventory([seed, other])
    g = lambda sid: edit_plan._ground_ref({"seg_id": sid}, seg_map)
    beats = [dict(_beat(seg_map, "s0-2"), alternates=[g("s1-2"), g("s0-4")]),      # 대표가 씨앗 → 대안이 올라온다
             dict(_beat(seg_map, "s0-3"), beat_idx=1),                               # 씨앗뿐 → 후보 컷으로 바뀐다
             dict(_beat(seg_map, "s0-5"), beat_idx=2, pinned=True)]                  # 사람이 고른 줄은 그대로
    assert edit_plan.enforce_auto_exclude(beats, seg_map) == 3
    assert beats[0]["primary"]["seg_id"] == "s1-2" and beats[0]["alternates"] == []
    assert beats[1]["primary"]["seg_id"].startswith("s1-")
    assert beats[2]["primary"]["seg_id"] == "s0-5"
    assert edit_plan.enforce_auto_exclude(beats, seg_map) == 0


def test_mark_is_skipped_when_seed_is_the_only_material():
    ex = {"s0": _src("s0")}
    mix_pipeline.mark_auto_exclude(ex, {"script_structure": {"no_auto_idx": [0]}})
    assert "auto_exclude" not in ex["s0"]                  # 달면 자동 배치 후보가 0이 돼 편집안을 못 만든다


def test_auto_pick_code_does_not_hand_write_the_filter():
    """자동 배치 후보 조건을 주인(edit_plan) 밖에서 직접 적지 않는다 — 적으면 다음 조건이 또 한쪽에만 들어간다."""
    import pathlib, re
    root = pathlib.Path(__file__).resolve().parents[1]
    bad = []
    for p in root.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        for i, line in enumerate(src.splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"_is_edge_seg\(|\.get\(\"auto_exclude\"\)", code) and not (
                    p.name == "edit_plan.py" and re.search(
                        r"def _is_edge_seg|def _auto_blocked|return \{sid: s for sid, s in auto_segs|"
                        r"return bool\(isinstance\(x, dict\)|\"auto_exclude\": bool\(script|if is_edge or script", code)):
                bad.append("%s:%d %s" % (p.name, i, code.strip()[:80]))
    assert not bad, bad
