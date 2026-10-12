# -*- coding: utf-8 -*-
"""실제 과금 탐침 (2026-09-27 사장님 "내 계정으로 실제 과금되는 것 정상인지 확인").

업체엔 잔액 API가 없다(SDK 통로는 config.json·consume.json 둘뿐). 대신 과금 요청(consume.json)의
**응답 본문을 그대로 찍어** 잔액·차감량 칸이 있는지 본다. 세 번 돈다:
  A) 정상 청소(컷 1개, 기본)          → consume 응답 원문 #1
  B) 결과 받기 강제 끊김 → 다시 누름   → consume 0회(이어받기), 응답 없음
  C) 다른 컷 정상 청소                 → consume 응답 원문 #2  (#1과 잔액 칸이 있으면 차이 = 실제 차감)
실행(트랙 폴더): py shopping_shorts/scripts/vmake_charge_probe.py --job bte60cb14b7d --db shopping_shorts/data/lab.db --keyfile <키>
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
ap.add_argument("--pickA", default="4"); ap.add_argument("--pickC", default="5")
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

# ── consume.json 응답 원문 기록 (키·URL은 안 찍는다) ──
CONSUME = []
_orig_consume = SkillClient._consume_permission


def _spy(self, url, task):
    r = _orig_consume(self, url, task)
    try:
        body = json.loads(json.dumps(r, ensure_ascii=False, default=str))
    except Exception:                                          # noqa: BLE001
        body = str(r)
    CONSUME.append({"task": task, "body": body})
    print("[CONSUME-RAW] task=%s body=%s" % (task, json.dumps(body, ensure_ascii=False)[:1200]), file=sys.stderr, flush=True)
    return r


SkillClient._consume_permission = _spy


def _reset(pick):
    for f in list(work.glob("final_clean_*")) + [work / cb.BASE_FILE, work / vc._PENDING_FILE] + list(work.glob("partial_clean_*")):
        if f.exists():
            f.unlink()
    store.update_mix_job(a.job, subtitle_removal=1, clean_status=None, clean_cuts=None, clean_tier="basic")
    cuts = mp.clean_pick_cuts(store.get_mix_job(a.job), work)
    sel = [cuts[int(i)]["key"] for i in pick.split(",")]
    store.update_mix_job(a.job, clean_cuts=sel)
    return sum(cuts[int(i)]["dur"] for i in pick.split(","))


_real_get = urllib.request.urlretrieve


def _run(block_download=False):
    def _get(url, dst, *x, **k):
        if block_download and "upload" not in url:
            raise ConnectionAbortedError("[시험] 결과 받기 강제 끊김")
        return _real_get(url, dst, *x, **k)
    urllib.request.urlretrieve = _get
    out, err = io.StringIO(), io.StringIO()
    n0 = len(CONSUME)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            mp.run_clean_sources(a.job, a.db, str(work_root))
    finally:
        urllib.request.urlretrieve = _real_get
    j = store.get_mix_job(a.job)
    logs = out.getvalue() + err.getvalue()
    return j, len(CONSUME) - n0, logs.count("OSS upload start"), logs.count("이어받는다")


sec = _reset(a.pickA)
print("== A) 정상 청소 (컷 %s, %.2f초, 기본 → 계산상 %d크레딧)" % (a.pickA, sec, mp.clean_credit_estimate(sec, "basic")))
j, nc, nu, nr = _run()
print("   상태 %s | consume %d | 업로드 %d | 이어받기 %d" % (j["clean_status"], nc, nu, nr))

sec = _reset(a.pickA)
print("== B) 결과 받기 강제 끊김 → 다시 누름")
j, nc, nu, nr = _run(block_download=True)
print("   1차 상태 %s | consume %d | 업로드 %d" % (j["clean_status"], nc, nu))
j, nc, nu, nr = _run()
print("   2차 상태 %s | consume %d | 업로드 %d | 이어받기 %d  ← 기대: consume 0·업로드 0·이어받기 1" % (j["clean_status"], nc, nu, nr))

sec = _reset(a.pickC)
print("== C) 다른 컷 정상 청소 (컷 %s, %.2f초 → 계산상 %d크레딧)" % (a.pickC, sec, mp.clean_credit_estimate(sec, "basic")))
j, nc, nu, nr = _run()
print("   상태 %s | consume %d | 업로드 %d" % (j["clean_status"], nc, nu))

print("== consume.json 응답 원문 %d건" % len(CONSUME))
for i, c in enumerate(CONSUME, 1):
    print("  #%d task=%s\n     %s" % (i, c["task"], json.dumps(c["body"], ensure_ascii=False)[:1500]))
keyset = set()
for c in CONSUME:
    if isinstance(c["body"], dict):
        keyset.update(c["body"].keys())
        for v in c["body"].values():
            if isinstance(v, dict):
                keyset.update("data." + k for k in v.keys())
print("== 응답에 나온 칸 이름:", sorted(keyset))
print("   잔액·차감으로 보이는 칸:", [k for k in sorted(keyset) if any(w in k.lower() for w in ("credit", "balance", "remain", "quota", "point", "cost", "left", "total"))] or "없음")
