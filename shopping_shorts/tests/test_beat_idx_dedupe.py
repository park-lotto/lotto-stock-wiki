# -*- coding: utf-8 -*-
"""칸 번호(beat_idx) 겹침 정리 — 저장 출구·/renumber·화면이 같은 번호를 쓰는지(2026-09-27).

배경(실측): 09-06 이전 job 5개가 번호가 겹쳐 렌더가 tts_paths={beat_idx: tts_path}로
마지막 칸 음성만 남겼다(CTA 반복·한 칸 누락). 그리고 scene_lab.html은 **위치 i**를
beat_idx로 보내, 칸을 지운 job에서 AI 장면·효과음·컷어웨이가 엉뚱한 칸에 붙었다.

계약:
  ① 겹친 편성은 저장 출구(update_mix_job)에서 정리된다 — 뒤 칸만 새 번호, 그 칸 음성 버림,
     scene_lab payload 같은 매핑, 경보 1회.
  ② 빠진 번호(겹침 없음)는 한 글자도 안 바뀐다(TTS 재합성·청소본 coverage 과금 방지).
  ③ /renumber는 같은 함수(store.dedupe_beat_idx)를 부른다(판단 한 곳).
  ④ 화면 세 곳(AI 장면·AI 빼기(컷어웨이)·효과음)과 AI 장면 폴링은 DATA.beats[i].beat_idx를 쓴다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts import ops_alert
from shopping_shorts import store as store_mod
from shopping_shorts.store import Store, beat_idx_duplicates, dedupe_beat_idx


def _beat(i, tts=True, **kw):
    b = {"beat_idx": i, "role": "본문", "narration": f"문장 {i}", "target_seconds": 2.0,
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0}}
    if tts:
        b["tts_path"] = f"/w/tts/beat_{i}_abc.mp3"
        b["tts_ver"] = 3
    b.update(kw)
    return b


def _dup_plan():
    # 실측 e2458d76dbb3 모양: [0,1,2,3,3,4,5,5]
    beats = [_beat(i) for i in (0, 1, 2, 3, 3, 4, 5, 5)]
    return {"structure": "free", "beats": beats,
            "scene_lab": {"beats": [{"beat_idx": b["beat_idx"], "list": [f"seg{p}"]}
                                    for p, b in enumerate(beats)]}}


@pytest.fixture
def alerts(monkeypatch):
    got = []
    monkeypatch.setattr(ops_alert, "raise_alert", lambda kind, title, *a, **k: got.append((kind, title)) or True)
    return got


def _store(tmp_path, job="j1", status="done"):
    st = Store(tmp_path / "t.db")
    st.create_mix_job(job, ["u0"], 20, "free")
    st.update_mix_job(job, status=status)
    return st


# ── ① 저장 출구에서 정리 ────────────────────────────────────────────────

def test_save_dedupes_drops_tts_and_maps_lab(tmp_path, alerts):
    st = _store(tmp_path)
    st.update_mix_job("j1", edit_plan=_dup_plan())
    plan = st.get_mix_job("j1")["edit_plan"]
    idx = [b["beat_idx"] for b in plan["beats"]]
    assert beat_idx_duplicates(plan) == []
    # 첫 칸은 번호 유지, 뒤의 겹친 칸만 최대+1부터
    assert idx == [0, 1, 2, 3, 6, 4, 5, 7], idx
    for pos, b in enumerate(plan["beats"]):
        if pos in (4, 7):          # 번호가 바뀐 칸 — 옛 번호 mp3를 버린다
            assert "tts_path" not in b and "tts_ver" not in b
        else:
            assert b["tts_path"] == f"/w/tts/beat_{b['beat_idx']}_abc.mp3" and b["tts_ver"] == 3
    # 화면 편성 payload도 칸 순서대로 같은 매핑
    lab = plan["scene_lab"]["beats"]
    assert [x["beat_idx"] for x in lab] == idx
    assert [x["list"] for x in lab] == [[f"seg{p}"] for p in range(8)]
    # 경보 한 번(job 키)
    assert [k for k, _t in alerts] == ["beat_idx_dup:j1"]
    # 정리된 편성을 다시 저장해도 경보는 더 안 나간다
    st.update_mix_job("j1", edit_plan=plan)
    assert len(alerts) == 1


def test_gapped_plan_untouched(tmp_path, alerts):
    st = _store(tmp_path)
    beats = [_beat(i) for i in (0, 2, 5, 3)]          # 빠진 번호 + 순서 뒤섞임, 겹침 없음
    plan = {"structure": "free", "beats": beats,
            "scene_lab": {"beats": [{"beat_idx": i, "list": ["x"]} for i in (0, 2, 5, 3)]}}
    before = json.loads(json.dumps(plan))
    assert dedupe_beat_idx(json.loads(json.dumps(plan))) == 0
    st.update_mix_job("j1", edit_plan=plan)
    saved = st.get_mix_job("j1")["edit_plan"]
    assert saved["beats"] == before["beats"]
    assert saved["scene_lab"] == before["scene_lab"]
    assert alerts == []


def test_duplicates_is_pure():
    p = _dup_plan()
    snap = json.loads(json.dumps(p))
    assert beat_idx_duplicates(p) == [3, 5]
    assert p == snap
    assert beat_idx_duplicates({"beats": [_beat(0), _beat(4)]}) == []
    assert beat_idx_duplicates(None) == []


def test_lab_payload_already_positional_left_alone():
    # 실측 1572bd6e8292: beats [0..5,5,5] / scene_lab.beats [0..7] — 옛 칸에 없던 6,7은 그대로
    beats = [_beat(i, tts=False) for i in (0, 1, 2, 3, 4, 5, 5, 5)]
    plan = {"beats": beats, "scene_lab": {"beats": [{"beat_idx": i, "list": ["x"]} for i in range(8)]}}
    assert dedupe_beat_idx(plan) == 2
    assert [b["beat_idx"] for b in plan["beats"]] == list(range(8))
    assert [x["beat_idx"] for x in plan["scene_lab"]["beats"]] == list(range(8))


# ── ③ /renumber = 같은 함수 ─────────────────────────────────────────────

def test_renumber_route_uses_same_function(monkeypatch, tmp_path, alerts):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", tmp_path / "work")
    client = TestClient(app_module.app)
    st = Store(db)
    st.create_mix_job("j1", ["u0"], 20, "free")
    st.update_mix_job("j1", status="done")
    # 겹친 편성을 **저장 출구를 거치지 않고** 심는다(09-06 이전 DB 상태 재현)
    with st._conn() as c:
        c.execute("UPDATE mix_jobs SET edit_plan_json=? WHERE job_id='j1'",
                  (json.dumps(_dup_plan(), ensure_ascii=False),))
    calls = []
    real = store_mod.dedupe_beat_idx
    monkeypatch.setattr(store_mod, "dedupe_beat_idx", lambda plan: calls.append(1) or real(plan))
    r = client.post("/api/mix/scene_lab/j1/renumber").json()
    assert r["ok"] and r["changed"] == 2, r
    assert calls, "/renumber가 store.dedupe_beat_idx를 안 불렀다 — 판단이 두 벌이 된다"
    plan = st.get_mix_job("j1")["edit_plan"]
    assert [b["beat_idx"] for b in plan["beats"]] == [0, 1, 2, 3, 6, 4, 5, 7]
    # 겹침 없으면 그대로
    r2 = client.post("/api/mix/scene_lab/j1/renumber").json()
    assert r2["changed"] == 0


# ── ④ 화면 세 곳 + 폴링 = 진짜 칸 번호 ─────────────────────────────────

LAB_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "scene_lab.html"
NODE = shutil.which("node")
_START = "const _AI_POLL = {};"
_END = "function setSfx("

_DRIVER = r"""
(function(){
  const sent = [];
  global.SL = {job: 'JID', server: true};
  // 칸 2개를 지운 작업 — 위치 i와 beat_idx가 다르다
  global.DATA = {ai_scene_enabled: true, beats: [{beat_idx: 0}, {beat_idx: 2}, {beat_idx: 5}]};
  global.renderBand = () => {};
  global.document = {getElementById: () => null};
  global.setInterval = (fn) => { fn(); return 1; };
  global.clearInterval = () => {};
  global.fetch = async (url, opts) => {
    if (opts && opts.body) sent.push([url.split('/').pop(), JSON.parse(opts.body).beat_idx]);
    if (url.indexOf('/api/mix/result/') === 0)
      return {json: async () => ({beats: [{beat_idx: 2, ai_scene: {state: 'running'}},
                                          {beat_idx: 5, ai_scene: {state: 'done'}, cutaway: {match_type: 'ai'}},
                                          {beat_idx: 1, ai_scene: {state: 'failed'}}]})};
    return {json: async () => ({ok: true, sfx: null})};
  };
  (async () => {
    await startAiScene(2, 'natural');
    await removeAiScene(1);
    await _sfxPost(2, {asset_id: 3});
    await new Promise(r => setTimeout(r, 20));
    console.log(JSON.stringify({sent, polled: DATA.beats[2].ai_scene}));
  })();
})();
"""


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_scene_lab_sends_real_beat_idx(tmp_path):
    src = LAB_HTML.read_text(encoding="utf-8")
    js = tmp_path / "t.js"
    # beatIdOf는 위치→번호 규칙을 scene_play.js beatKeyAt 한 곳에 맡긴다(2026-09-27) — 원본에서 떼어 붙인다.
    sp = (LAB_HTML.parent / "scene_play.js").read_text(encoding="utf-8")
    k = sp.index("function beatKeyAt(")
    conv = sp[k:sp.index(chr(10) + "}" + chr(10), k) + 3]
    js.write_text(conv + src[src.index(_START):src.index(_END)] + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    d = json.loads(out.stdout.strip().splitlines()[-1])
    posts = [s for s in d["sent"] if s[0] in ("ai_scene", "cutaway", "sfx")]
    # 위치 2 → beat_idx 5 / 위치 1 → beat_idx 2 / 위치 2 → beat_idx 5
    assert posts == [["ai_scene", 5], ["cutaway", 2], ["sfx", 5]], d["sent"]
    # 폴링도 진짜 번호(5)의 상태를 읽는다 — 위치(2)로 찾으면 'running'을 읽는다
    assert d["polled"] == {"state": "done"}, d
