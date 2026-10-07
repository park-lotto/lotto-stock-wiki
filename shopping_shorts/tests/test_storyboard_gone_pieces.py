# -*- coding: utf-8 -*-
"""2단계 스토리보드 — 1단계에서 뺀 영상의 장면이 보드에 남았을 때(2026-10-08 사고, work ad37c18f3be7).

스토리보드를 만든 뒤 1단계에서 영상 하나를 빼자 보드 칸에 남은 그 영상 장면 번호를 그리다 sbCellCards 가 죽어
2단계가 통째로 비었다. 판정 주인 = produce.html sbGone(지금 재료에 없는 번호). 결과물 검사 = tools/storyboard_mock/sb_gone_check.py.
"""
import json
import pathlib
import re
import subprocess

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts import storyboard as sb
from shopping_shorts.store import Store

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def _fn(name):
    """여러 줄 함수(닫는 } 가 줄 맨 앞)."""
    m = re.search(r"function %s\(.*?\n\}\n" % re.escape(name), HTML, re.S)
    assert m, name
    return m.group(0)


def _line_fn(name):
    """한 줄로 시작해 다음 function 앞에서 끝나는 옛 모양 함수."""
    m = re.search(r"\n(?:async )?function %s\(.*?(?=\n(?:async )?function |\n// )" % re.escape(name), HTML, re.S)
    assert m, name
    return m.group(0)


def _node(js, tmp_path):
    (tmp_path / "t.js").write_text(js, encoding="utf-8")
    r = subprocess.run(["node", str(tmp_path / "t.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# 영상 B 를 뺀 뒤: 재료엔 A 조각만, 보드 칸엔 B 조각 번호가 남아 있다. 2번 칸은 뺀 장면뿐.
_PRE = """
const SB={jid:'w:w1', view:'9', play:null, ord:{}, edit:{}, role:{}, cand:{}, mat:'',
  data:{min_clip:0.8, mat_sig:'2:new', pieces:{'A-0':{sec:1.5,th:'t'},'A-1':{sec:0.5,th:'t'}}},
  made:{'9':{mat_sig:'4:old', slots:[{slot:'hook',line:'첫 줄',ids:['A-0','B-0']},{slot:'reveal',line:'둘째 줄',ids:['B-1','B-2']},{slot:'cta',line:'셋째',ids:['A-1']}],
             check:[{need:3,have:3},{need:3,have:3},{need:3,have:0.5}]},
        'auto':{mat_sig:'2:new', slots:[{slot:'hook',line:'x',ids:['A-0']}]}}};
function sbE(s){ return String(s==null?'':s); } function sbA(s){ return String(s); }
function sbPieces(){ return (SB.data&&SB.data.pieces)||{}; }
function sbOrdOf(ek, i, sl){ const k=ek+'#'+i; return SB.ord[k]=SB.ord[k]||[...(sl.ids||[])]; }
function sbLine(ek, i, sl){ return sl.line||''; }
function sbCur(){ const k=SB.view; return [k, SB.made[k]]; }
function sbTh(id, w){ return sbPieces()[id]?'<th '+id+'>':''; } function sbClipV(){ return ''; }
let SYNC=0; function sbResync(){ SYNC++; }
"""


def test_뺀_영상_장면이_남아도_카드를_그린다(tmp_path):
    js = _PRE + _fn("sbGone") + _fn("sbLiveIds") + _line_fn("sbCellCards") + """
const bd=SB.made['9']; const html=bd.slots.map((sl,i)=>sbCellCards('9',i,sl,bd.check[i]));
const loading=(()=>{ const keep=SB.data.pieces; SB.data.pieces={}; const g=sbGone('B-0'); const h=sbCellCards('9',0,bd.slots[0],bd.check[0]); SB.data.pieces=keep; return [g, h.includes('sb-cc gone')]; })();
console.log(JSON.stringify({gone:html.map(h=>(h.match(/sb-cc gone/g)||[]).length), live:html.map(h=>(h.match(/<th /g)||[]).length),
  short:html[2].includes('짧은 조각'), out:bd.slots.map((sl,i)=>sbLiveIds('9',i,sl)), kept:SB.ord['9#1'], loading}));
"""
    out = _node(js, tmp_path)
    assert out["gone"] == [1, 2, 0] and out["live"] == [1, 0, 1]      # 뺀 장면은 🗑 카드, 남은 장면은 그대로
    assert out["short"] is True                                       # 0.5초 조각의 '짧은 조각' 표시는 그대로
    assert out["out"] == [["A-0"], [], ["A-1"]]                       # 내보내는 값엔 뺀 장면이 없다
    assert out["kept"] == ["B-1", "B-2"]                              # 번호는 지우지 않는다(영상을 다시 담으면 돌아온다)
    assert out["loading"] == [False, False]                           # 재료를 아직 못 받았으면 뺀 것으로 치지 않고, 그려도 안 죽는다


def test_안내_띠와_한번에_치우기(tmp_path):
    js = _PRE + _fn("sbGone") + _fn("sbLiveIds") + _fn("sbGoneBar") + _fn("sbDropGone") + """
const bar=sbGoneBar(); SB.view='auto'; const none=sbGoneBar(); SB.view='9'; sbDropGone();
console.log(JSON.stringify({n:/장면 3개/.test(bar), rows:bar.includes('1·2번 칸'), empty:bar.includes('2번 칸은 남은 장면이 없어요'), none,
  after:SB.made['9'].slots.map((sl,i)=>sbOrdOf('9',i,sl)), sync:SYNC, bar2:sbGoneBar()}));
"""
    out = _node(js, tmp_path)
    assert out["n"] and out["rows"] and out["empty"] and out["none"] == ""
    assert out["after"] == [["A-0"], [], ["A-1"]] and out["sync"] == 1 and out["bar2"] == ""


def test_예전_재료_보드는_탭마다_가른다(tmp_path):
    js = _PRE + _fn("_sbMatSig") + _fn("_sbStale") + """
const old=_sbStale(); SB.view='auto'; const fresh=_sbStale();
console.log(JSON.stringify({old, fresh}));
"""
    assert _node(js, tmp_path) == {"old": True, "fresh": False}


def test_내보내는_길은_전부_sbLiveIds():
    assert "ids:sbLiveIds(ek,i,sl)" in _line_fn("sbCurBoard")          # 확정·끼워 넣기
    assert "ids:sbLiveIds(ek,k,x)" in _line_fn("sbPicksSync")          # 초 다시 재기
    assert "sbCurBoard(ek,bd)" in _fn("sbConfirm") and "sbCurBoard(ek,bd)" in _fn("sbInsert")
    r = _fn("sbRender")
    assert "sbGoneBar()" in r and "sb-drawfail" in r and "_sbEnsureGoneCheck()" in r   # 그리다 죽어도 빈 화면으로 두지 않는다


# ── 서버: 보드에 만든 때의 재료 지문, 조회 응답에 지금 재료 지문 ──
def _ex(vids):
    return {v: {"segments": [{"seg_id": "%s-%d" % (v, i), "start": i * 2.0, "end": i * 2.0 + 2.0} for i in range(2)]} for v in vids}


def test_보드에_만든_때의_재료_지문이_찍힌다(tmp_path, monkeypatch):
    ex = _ex(["A", "B"])
    monkeypatch.setattr(sb, "_ro", lambda p: None)
    monkeypatch.setattr(sb, "_families", lambda db: [(7, {"id": 7}, None)])
    monkeypatch.setattr(sb, "_board", lambda *a, **k: {"slots": [{"slot": "hook", "ids": ["A-0"]}]})
    R = {"inventory": {"groups": [], "tag_of": {}}, "mat_sig": sb.mat_sig(ex), "styles": []}
    out = sb.make_boards(tmp_path / "x.db", "j", ["7"], R=R, ex=ex)
    assert out["7"]["mat_sig"] == sb.mat_sig(ex) != sb.mat_sig(_ex(["A"]))


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    st = Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(app_mod, "_sb_gate", lambda req: None)
    box = {"ex": _ex(["A", "B"])}
    monkeypatch.setattr(app_mod, "_extract_from_work", lambda wid, cid, st_: json.loads(json.dumps(box["ex"])))
    return st, TestClient(app_mod.app), box


def test_조회_응답의_재료_지문은_영상을_빼면_바뀐다(env):
    st, c, box = env
    wid = st.upsert_produce_work(None, {"script": "x"}, customer_id=0)
    a = c.get("/api/produce/storyboard/w:%s" % wid).json()
    assert a["mat_sig"] == sb.mat_sig(box["ex"]) and set(a["pieces"]) == {"A-0", "A-1", "B-0", "B-1"}
    box["ex"] = _ex(["A"])
    b = c.get("/api/produce/storyboard/w:%s" % wid).json()
    assert b["mat_sig"] != a["mat_sig"] and set(b["pieces"]) == {"A-0", "A-1"}
