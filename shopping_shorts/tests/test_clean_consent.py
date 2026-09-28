# -*- coding: utf-8 -*-
"""돈이 나가는 자막제거는 **서버가 고객 동의를 강제**한다 (2026-09-27 사장님 승인).

왜: 증분 청소·등급 상향·전체 청소 전부 화면 확인창에만 기대고 있었다 — 확인창 호출이 실패하면 catch 로 조용히
  통과해 서버가 확인 없이 과금했다. 이제 과금 초 > 0 이면 요청에 confirm_clean + confirm_secs(확인창이 본 초)가
  있어야 하고, 없거나 판정과 ±10%(최소 0.5초) 넘게 다르면 409 + 안내. 워커도 실행 직전 같은 판정으로 다시 잰다.
판정은 mix_pipeline.clean_charge_plan 한 곳(라우트·워커·확인창 문구).
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from shopping_shorts import app as A
from shopping_shorts import clean_base as cb
from shopping_shorts import mix_pipeline as mp

HTML = Path(A.__file__).parent / "static" / "produce.html"


class _S:
    def __init__(self, job): self.job = job; self.q = []; self.updates = []
    def get_mix_job(self, j): return self.job
    def get_setting(self, k, d=None): return "1"
    def update_mix_job(self, j, **kw): self.updates.append(kw); self.job.update(kw)
    def enqueue(self, task, args, owner=None, prio=None): self.q.append((task, args))
    def queue_has_pending(self, *a): return False


def _setup(tmp_path, monkeypatch, *, base=True, tier="basic"):
    plan = {"beats": [
        {"beat_idx": 0, "target_seconds": 2.0, "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 2.0, "primary": {"video_id": "s1", "seg_id": "s1-0", "start": 0.0, "end": 2.5}, "alternates": []}]}
    work = tmp_path / "jobx"; work.mkdir(parents=True)
    if base:       # 정본은 0번 칸만 덮는다 → 1번 칸 = 바뀐 장면(증분 과금)
        (work / "final_clean_x.mp4").write_bytes(b"c" * 4096)
        cb.save_base(work, sig="x", path=str(work / "final_clean_x.mp4"), plan={"beats": plan["beats"][:1]},
                     cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    job = {"job_id": "jobx", "edit_plan": plan, "subtitle_removal": 1, "customer_id": 0, "clean_tier": tier,
           "urls": ["a", "b"]}
    store = _S(job)
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    monkeypatch.setattr(A, "Store", lambda db: store)
    monkeypatch.setattr(mp, "Store", lambda db: store)
    monkeypatch.setattr(A, "_need_own_key_or_402", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_resolve_sources", lambda j, w: {"s0": str(work / "s0.mp4"), "s1": str(work / "s1.mp4")})
    monkeypatch.setattr(mp, "_src_durs_for", lambda j, w: {"s0": 60.0, "s1": 60.0})
    charges = []
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: charges.append(1) or 1)
    mp._JUDGE_CACHE.clear()
    return job, work, store, charges


class _Req:
    class state:
        customer_id = 0
    headers = {}
    cookies = {}


def _render(body, monkeypatch):
    monkeypatch.setattr(A, "_cid", lambda request: 0)
    return A.api_mix_render(_Req(), None, dict({"job_id": "jobx"}, **body))


def _status(r):
    return getattr(r, "status_code", 200), (json.loads(r.body) if hasattr(r, "body") else r)


# ── 라우트(최종 렌더) ────────────────────────────────────────────────────────────

def test_render_needs_confirm_409_no_charge(tmp_path, monkeypatch):
    job, work, store, charges = _setup(tmp_path, monkeypatch)
    code, d = _status(_render({}, monkeypatch))
    assert code == 409 and d["need_clean_confirm"] and d["why"] == "confirm_missing"
    assert d["reason"] == "changed" and d["seconds"] > 0 and d["credits"] == mp.clean_credit_estimate(d["seconds"], "basic")
    assert "추가 과금 없음" in d["message"] and ("%.1f초" % d["seconds"]) in d["message"]
    assert store.q == [] and charges == [] and job.get("status") != "rendering"      # 상태·큐·과금 전부 그대로


def test_render_with_confirm_proceeds_and_queues_consent(tmp_path, monkeypatch):
    job, work, store, charges = _setup(tmp_path, monkeypatch)
    secs = _status(_render({}, monkeypatch))[1]["seconds"]
    code, d = _status(_render({"confirm_clean": True, "confirm_secs": secs}, monkeypatch))
    assert code == 200 and d["ok"] and job["status"] == "rendering"
    assert store.q == [("render", {"job_id": "jobx", "confirm_clean": True, "confirm_secs": secs})]
    assert charges == []                      # 라우트는 과금하지 않는다(워커가 실행)


def test_render_amount_mismatch_409(tmp_path, monkeypatch):
    job, work, store, charges = _setup(tmp_path, monkeypatch)
    secs = _status(_render({}, monkeypatch))[1]["seconds"]
    code, d = _status(_render({"confirm_clean": True, "confirm_secs": round(secs * 0.5, 2)}, monkeypatch))
    assert code == 409 and d["why"] == "amount_changed" and store.q == []
    code, d = _status(_render({"confirm_clean": True, "confirm_secs": round(secs * 1.05, 2)}, monkeypatch))
    assert code == 200                        # ±10% 안


def test_render_skip_clean_no_confirm_needed(tmp_path, monkeypatch):
    job, work, store, charges = _setup(tmp_path, monkeypatch)
    code, d = _status(_render({"skip_clean": True}, monkeypatch))
    assert code == 200 and store.q == [("render", {"job_id": "jobx", "skip_clean": True})] and charges == []


def test_render_no_charge_no_confirm(tmp_path, monkeypatch):
    job, work, store, charges = _setup(tmp_path, monkeypatch)
    job["edit_plan"]["beats"] = job["edit_plan"]["beats"][:1]            # 정본이 다 덮는다
    code, d = _status(_render({}, monkeypatch))
    assert code == 200 and store.q == [("render", {"job_id": "jobx"})]


def test_render_no_base_and_tier_upgrade_reasons(tmp_path, monkeypatch):
    job, work, store, charges = _setup(tmp_path, monkeypatch, base=False)
    prev = work / "preview.mp4"; prev.write_bytes(b"p" * 2048); job["preview_path"] = str(prev)
    monkeypatch.setattr(mp, "_probe_seconds", lambda p: 30.4)
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    code, d = _status(_render({}, monkeypatch))
    assert code == 409 and d["reason"] == "no_base" and d["seconds"] == 30.4 and d["credits"] == 62
    job2, work2, store2, _ = _setup(tmp_path / "t2", monkeypatch, tier="pro")
    job2["edit_plan"]["beats"] = job2["edit_plan"]["beats"][:1]
    prev2 = work2 / "preview.mp4"; prev2.write_bytes(b"p" * 2048); job2["preview_path"] = str(prev2)
    code, d = _status(_render({}, monkeypatch))
    assert code == 409 and d["reason"] == "tier_upgrade" and d["credits"] == 124 and "고급" in d["message"]


# ── 워커(실행 직전 재검사) ──────────────────────────────────────────────────────

def test_worker_blocks_when_amount_grew(tmp_path, monkeypatch):
    """요청 때 본 초보다 실행 시점 판정이 늘면 청소·과금 없이 멈추고 안내한다(버튼 워커)."""
    job, work, store, charges = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_vmake_keys", lambda *a, **k: ["k"])
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    incr = []
    monkeypatch.setattr(mp, "incremental_clean", lambda *a, **k: incr.append(1) or a[6])
    mp.run_clean_sources("jobx", "db", str(tmp_path), confirm_clean=True, confirm_secs=0.3)
    assert job["clean_status"] == "failed" and "비용 확인" in job["clean_error"]
    assert charges == [] and incr == []
    secs = mp.clean_charge_plan(store, job, work, mode="button")["seconds"]
    job["clean_status"] = None
    mp.run_clean_sources("jobx", "db", str(tmp_path), confirm_clean=True, confirm_secs=secs)
    assert incr == [1]                                   # 같은 금액이면 진행


def test_render_worker_without_consent_stops_before_clean(tmp_path, monkeypatch):
    job, work, store, charges = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    incr = []
    monkeypatch.setattr(mp, "incremental_clean", lambda *a, **k: incr.append(1) or a[6])
    monkeypatch.setattr(mp, "assemble", lambda *a, **k: pytest.fail("동의 없이 조립(과금 경로)까지 갔다"))
    mp.run_render("jobx", "db", str(tmp_path))
    assert job["status"] == "failed" and "비용 확인" in job["error"] and incr == [] and charges == []


# ── 버튼 라우트 ─────────────────────────────────────────────────────────────────

def test_button_route_needs_confirm_and_keeps_cuts_unsaved(tmp_path, monkeypatch):
    job, work, store, charges = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    monkeypatch.setattr(A, "_clean_cuts_from_body", lambda job, jid, cuts: ["0|s0|1.00"])
    r = A.api_produce_mix_clean(None, {"job_id": "jobx", "cuts": ["0|s0|1.00"]})
    code, d = _status(r)
    assert code == 409 and d["need_clean_confirm"] and store.q == [] and "clean_cuts" not in job
    r = A.api_produce_mix_clean(None, {"job_id": "jobx", "cuts": ["0|s0|1.00"],
                                       "confirm_clean": True, "confirm_secs": d["seconds"]})
    code, d2 = _status(r)
    assert code == 200 and job["clean_cuts"] == ["0|s0|1.00"]
    assert store.q == [("clean", {"job_id": "jobx", "confirm_clean": True, "confirm_secs": d["seconds"]})]


# ── 화면(node): 409 → 확인창 → 표식 실어 재요청 ───────────────────────────────────

def _block(src, start, end):
    i = src.index(start); j = src.index(end, i)
    return src[i:j]


def _node(js):
    if shutil.which("node") is None:
        pytest.skip("node 없음")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js); p = f.name
    r = subprocess.run(["node", p], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


RENDER_START = "  const _intro = !!(document.getElementById('thumbIntro')||{}).checked;\n"
RENDER_END = "  if(!r.ok||!d.ok){ _finalRenderRestore('❌ 렌더 시작 실패')"


def _render_harness(answers):
    src = HTML.read_text(encoding="utf-8").replace("\r\n", "\n")
    block = _block(src, RENDER_START, RENDER_END)
    return """
const sent=[]; const answers=%s; let asked=[];
global.document={getElementById:()=>({checked:false})};
global.MIX_JOB='jobx'; global._rfTimer=0; global.clearInterval=()=>{};
let restored=null; global._finalRenderRestore=(m)=>{restored=m;};
global.confirm=(m)=>{asked.push(m); return answers.shift();};
global.fetch=async (url,opt)=>{ const b=JSON.parse(opt.body); sent.push(b);
  if(!b.skip_clean && !b.confirm_clean) return {status:409, ok:false, json:async()=>({ok:false,need_clean_confirm:true,seconds:12.3,reason:'changed',message:'바뀐 장면 12.3초'})};
  return {status:200, ok:true, json:async()=>({ok:true})}; };
(async()=>{ let r,d; await (async()=>{ %s
  })(); console.log(JSON.stringify({sent, asked:asked.length, restored})); })();
""" % (json.dumps(answers), block)


def test_js_render_confirm_sends_consent():
    out = _node(_render_harness([True]))
    assert len(out["sent"]) == 2 and not out["sent"][0].get("confirm_clean")
    assert out["sent"][1]["confirm_clean"] is True and out["sent"][1]["confirm_secs"] == 12.3


def test_js_render_decline_then_skip_clean():
    out = _node(_render_harness([False, True]))
    assert out["sent"][-1]["skip_clean"] is True and "confirm_clean" not in out["sent"][-1]
    out = _node(_render_harness([False, False]))
    assert len(out["sent"]) == 1 and out["restored"] == "렌더를 취소했어요"


BUTTON_START = "    let _cbody={job_id:myJob, cuts:_cuts"   # 뒤에 화면 등급이 붙는다(2026-09-28)
BUTTON_END = "    if(CLEAN_GEN!==myGen) return;\n    if(!d.ok){"


def test_js_button_confirm_sends_consent():
    src = HTML.read_text(encoding="utf-8").replace("\r\n", "\n")
    block = _block(src, BUTTON_START, BUTTON_END)
    js = """
const sent=[]; global.confirm=()=>true; global.STATE={cleanTier:'pro'}; const myJob='jobx', _cuts=null, myGen=1; global.CLEAN_GEN=1;
const box={innerHTML:''}, btn=null;
global.fetch=async (url,opt)=>{ const b=JSON.parse(opt.body); sent.push(b);
  if(!b.confirm_clean) return {status:409, json:async()=>({ok:false,need_clean_confirm:true,seconds:7.5,message:'m'})};
  return {status:200, json:async()=>({ok:true})}; };
(async()=>{ await (async()=>{ %s })(); console.log(JSON.stringify({sent})); })();
""" % block
    out = _node(js)
    assert len(out["sent"]) == 2 and out["sent"][1]["confirm_clean"] is True and out["sent"][1]["confirm_secs"] == 7.5
    assert out["sent"][0]["clean_tier"] == "pro" and out["sent"][1]["clean_tier"] == "pro"   # 화면 등급이 동의 재요청에도 실린다
