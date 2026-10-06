"""2단계 스토리보드 — 씨앗 거름·옛 스타일 줄 숨김·보드 기억(관제 120 장면배분, 2026-10-06 사장님).

씨앗 판정의 주인은 기존 표식 하나(auto_exclude) — 다는 곳 mix_pipeline.mark_seed_sources, 읽는 곳 edit_plan._auto_blocked.
"""
import json
import pathlib
import re
import subprocess

from shopping_shorts import mix_pipeline, storyboard as sb

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def _src(vid, n=3):
    return {"segments": [{"seg_id": f"{vid}-{i}", "start": i * 2.0, "end": i * 2.0 + 2.0, "scene_desc": f"{vid} 장면{i}"}
                         for i in range(n)]}


# ── 씨앗 표식(주인 한 곳) ──
def test_handoff_seed_keys_and_mark():
    hand = [{"shortcode": "A", "useFootage": True, "seedNoAuto": True},
            {"shortcode": "B", "useFootage": True},
            {"shortcode": "C", "useFootage": False, "seedNoAuto": True}]     # 재료에서 빠진 영상은 씨앗 표식도 안 단다
    assert mix_pipeline.seed_keys_from_handoff(hand) == ["A"]
    ex = {"A": _src("A"), "B": _src("B")}
    mix_pipeline.mark_seed_sources(ex, ["A"])
    assert ex["A"].get("auto_exclude") is True and "auto_exclude" not in ex["B"]


def test_seed_only_material_is_not_marked():
    ex = {"A": _src("A")}
    mix_pipeline.mark_seed_sources(ex, ["A"])
    assert "auto_exclude" not in ex["A"]                       # 씨앗뿐이면 빼지 않는다(관제 138 규칙 그대로)
    segs, _t, order, _r = sb._materials(None, "j", ex)
    assert set(order) == {"A-0", "A-1", "A-2"}


def test_job_path_still_uses_same_owner():
    ex = {"s0": _src("s0"), "s1": _src("s1")}
    mix_pipeline.mark_auto_exclude(ex, {"script_structure": {"no_auto_idx": [0]}})
    assert ex["s0"].get("auto_exclude") is True and "auto_exclude" not in ex["s1"]


# ── 스토리보드 재료에서 거름 ──
def test_materials_drop_seed_but_keep_human_picks():
    ex = {"A": _src("A"), "B": _src("B")}
    mix_pipeline.mark_seed_sources(ex, ["A"])
    segs, _t, order, rows = sb._materials(None, "j", ex)
    assert not any(c.startswith("A-") for c in order) and "B-0" in segs
    assert not any("A 장면" in r for r in rows)               # AI 장면 목록 프롬프트에도 없다
    # 사람이 1단계 '꼭 쓰고 싶은 장면' 상자에 담은 씨앗 조각은 존중해 남긴다
    keep = sb._keep_ids("", "훅=A-1|CTA·가격=B-2")
    assert keep == {"A-1", "B-2"}
    segs2, _t, order2, _r = sb._materials(None, "j", ex, keep=keep)
    assert "A-1" in segs2 and "A-0" not in segs2
    assert sb._keep_ids("A-0,B-1", "") == {"A-0", "B-1"}


def test_role_pick_places_seed_scene_human_chose():
    slots = [{"slot": "hook", "ids": ["B-0"]}, {"slot": "result", "ids": ["B-1"]}]
    moved, left = sb._apply_role_picks(slots, "훅: A-1")
    assert slots[0]["ids"][0] == "A-1" and not left


# ── 화면(JS) ──
def _js_fn(name):
    m = re.search(r"function %s\(.*?\n\}\n" % re.escape(name), HTML, re.S)
    assert m, name
    return m.group(0)


def _node(js, tmp_path):
    (tmp_path / "t.js").write_text(js, encoding="utf-8")
    r = subprocess.run(["node", str(tmp_path / "t.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_old_style_band_hidden_only_when_storyboard_on(tmp_path):
    assert 'id="s2StyleBand"' in HTML
    js = """
const els={s2StyleBand:{style:{display:''}}, s1Storyboard:{style:{},innerHTML:''}, s2Storyboard:{style:{},innerHTML:''}};
const document={getElementById:id=>els[id]||null}; const window={scrollY:0, scrollTo(){}};
const SB={jid:''}; function _sbSaveSoon(){}
""" + _js_fn("sbRender") + """
window.STORYBOARD_ON=false; sbRender(); const off=els.s2StyleBand.style.display;
window.STORYBOARD_ON=true; sbRender(); const on=els.s2StyleBand.style.display;
console.log(JSON.stringify({off, on}));
"""
    assert _node(js, tmp_path) == {"off": "", "on": "none"}


def test_board_snapshot_restores_same_work_only(tmp_path):
    js = """
const window={STORYBOARD_ON:true}; let WORK_ID='w1';
const SB={jid:'w:w1', data:{pieces:{'B-0':{},'A-1':{seed:true}}}, made:{auto:{slots:[{slot:'hook',line:'첫 줄',ids:['B-0'],meme_pick:7}]}},
  view:'auto', edit:{auto:{0:'고친 첫 줄'}}, ord:{'auto#0':['B-0']}, pick:new Set(['auto','3']), role:{'훅':new Set(['A-1'])}, mat:''};
""" + "\n".join(_js_fn(n) for n in ["_sbMatSig", "_sbSnapshot", "_sbApplySaved"]) + """
var _SB_SAVED=null;
SB.mat=_sbMatSig();
const snap=JSON.parse(JSON.stringify(_sbSnapshot()));
// 다른 단계 갔다 옴 / 새로고침 = 메모리가 비고 작업 state.sb 만 남는다
Object.assign(SB,{made:{}, view:'', edit:{}, ord:{}, pick:new Set(), role:{}, mat:''});
_SB_SAVED=snap; _sbApplySaved('w:w1');
const back={view:SB.view, line:SB.edit.auto[0], meme:SB.made.auto.slots[0].meme_pick, pick:[...SB.pick].sort(), role:[...SB.role['훅']], mat:SB.mat===snap.mat};
// 다른 작업 것이면 안 되살린다
Object.assign(SB,{made:{}, view:''}); _SB_SAVED=Object.assign({},snap,{work_id:'w2'}); _sbApplySaved('w:w1');
console.log(JSON.stringify({snapWork:snap.work_id, back, other:Object.keys(SB.made).length}));
"""
    out = _node(js, tmp_path)
    assert out["snapWork"] == "w1"
    assert out["back"] == {"view": "auto", "line": "고친 첫 줄", "meme": 7, "pick": ["3", "auto"], "role": ["A-1"], "mat": True}
    assert out["other"] == 0


def test_work_state_carries_sb_and_hydrate_wired():
    assert "_st.sb = _sb" in _js_fn("_workState")
    assert "_sbHydrate(w)" in _js_fn("_s2Hydrate")
