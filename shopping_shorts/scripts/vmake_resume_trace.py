# -*- coding: utf-8 -*-
"""이어받기 실제 추적 (2026-09-27) — 과금 탐침 B에서 이어받기가 안 된 원인을 잡는다.

B1: 결과 받기 강제 끊김 → 그 순간의 clean_error·장부 파일 내용·서명을 찍는다.
B2: 다시 누름 → 장부 조회 키·HIT/MISS·consume 횟수·서명을 찍는다.
실행(트랙 폴더): py shopping_shorts/scripts/vmake_resume_trace.py --job bte60cb14b7d --db shopping_shorts/data/lab.db --keyfile <키>
"""
import argparse
import io
import json
import os
import sys
import urllib.request
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHORTS_CLEAN_FINAL", "1")
ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True); ap.add_argument("--db", required=True); ap.add_argument("--keyfile", required=True)
ap.add_argument("--pick", default="4")
a = ap.parse_args()

from shopping_shorts import config as cfg                      # noqa: E402
cfg.DB_PATH = a.db
from shopping_shorts import mix_pipeline as mp                 # noqa: E402
from shopping_shorts import vmake_client as vc                 # noqa: E402
from shopping_shorts import clean_base as cb                   # noqa: E402
from shopping_shorts.store import Store                        # noqa: E402
from shopping_shorts.vmake_sdk import SkillClient              # noqa: E402

keys = [k for k in Path(a.keyfile).read_text(encoding="utf-8").splitlines() if k.strip()]
mp._vmake_keys = lambda s, c=0: keys
store = Store(a.db); store.set_setting("clean_base_enabled", "1")
work_root = ROOT / "shopping_shorts" / "data" / "mix_jobs"; work = work_root / a.job
TRACE = []
CONSUME = [0]
_oc = SkillClient._consume_permission


def _spy(self, url, task):
    CONSUME[0] += 1; TRACE.append("consume task=%s" % task); return _oc(self, url, task)


SkillClient._consume_permission = _spy
_og, _op, _od = vc._pending_get, vc._pending_put, vc._pending_drop


def _g(out, key):
    r = _og(out, key)
    TRACE.append("get key=%s -> %s | ledger=%s" % (key, "HIT" if r else "MISS", _ledger()))
    return r


def _p(out, key, tid, sec):
    TRACE.append("put key=%s tid=%s" % (key, tid)); return _op(out, key, tid, sec)


def _d(out, key):
    TRACE.append("DROP key=%s" % key); return _od(out, key)


vc._pending_get, vc._pending_put, vc._pending_drop = _g, _p, _d
_of = vc._fetch_by_task


def _f(client, tid, out, want):
    TRACE.append("fetch_by_task tid=%s want=%s" % (tid, want))
    try:
        r = _of(client, tid, out, want); TRACE.append("fetch_by_task OK -> %s" % Path(r).name); return r
    except Exception as e:                                     # noqa: BLE001
        TRACE.append("fetch_by_task FAIL %r" % (e,)); raise


vc._fetch_by_task = _f


def _ledger():
    p = work / vc._PENDING_FILE
    return p.read_text(encoding="utf-8") if p.exists() else "없음"


def _sig():
    return mp._clean_sig(store.get_mix_job(a.job))


for f in list(work.glob("final_clean_*")) + [work / cb.BASE_FILE, work / vc._PENDING_FILE] + list(work.glob("partial_clean*")):
    if f.exists():
        f.unlink()
store.update_mix_job(a.job, subtitle_removal=1, clean_status=None, clean_cuts=None, clean_tier="basic")
cuts = mp.clean_pick_cuts(store.get_mix_job(a.job), work)
store.update_mix_job(a.job, clean_cuts=[cuts[int(i)]["key"] for i in a.pick.split(",")])
_real_get = urllib.request.urlretrieve


def _run(block):
    def _get(url, dst, *x, **k):
        if block and "upload" not in url:
            TRACE.append("download BLOCKED"); raise ConnectionAbortedError("[시험] 결과 받기 강제 끊김")
        TRACE.append("download OK"); return _real_get(url, dst, *x, **k)
    urllib.request.urlretrieve = _get
    out, err = io.StringIO(), io.StringIO(); c0 = CONSUME[0]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            mp.run_clean_sources(a.job, a.db, str(work_root))
    finally:
        urllib.request.urlretrieve = _real_get
    j = store.get_mix_job(a.job)
    return j, CONSUME[0] - c0, out.getvalue() + err.getvalue()


print("서명(전):", _sig())
print("== B1 결과 받기 강제 끊김")
j, nc, logs = _run(True)
print("   상태:", j["clean_status"], "| consume:", nc, "| 오류:", (j.get("clean_error") or "")[:200])
print("   장부:", _ledger()); print("   서명(후):", _sig())
print("== B2 다시 누름")
j, nc, logs = _run(False)
print("   상태:", j["clean_status"], "| consume:", nc, "| 오류:", (j.get("clean_error") or "")[:200])
print("   장부:", _ledger()); print("   서명(후):", _sig())
print("== 추적")
for t in TRACE:
    print("  ", t[:300])
