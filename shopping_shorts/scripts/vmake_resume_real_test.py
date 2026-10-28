# -*- coding: utf-8 -*-
"""업체 결과 받기 끊김 → 다시 누르면 과금 없이 이어받기 — **진짜 업체** 시험 (2026-09-27).

1차: 진짜 업체에 맡기되, 결과 내려받기를 전부 강제로 끊는다 → job failed(중단) + 장부에 작업 번호.
2차: 고객이 다시 누른 것처럼 같은 청소를 다시 돌린다 → 업로드·consume 없이 이어받아 ready.
SDK 진행 로그에서 'consume' 줄 수를 세어 1차 1번 / 2차 0번인지 본다.
실행(트랙 폴더): py shopping_shorts/scripts/vmake_resume_real_test.py --job <job> --db <lab.db> --keyfile <키> --pick 4
"""
import argparse
import io
import os
import sys
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHORTS_CLEAN_FINAL", "1")
ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True); ap.add_argument("--db", required=True)
ap.add_argument("--keyfile", required=True); ap.add_argument("--pick", required=True)
ap.add_argument("--tier", default="basic")
a = ap.parse_args()

from shopping_shorts import config as cfg            # noqa: E402
cfg.DB_PATH = a.db
from shopping_shorts import mix_pipeline as mp       # noqa: E402
from shopping_shorts import vmake_client as vc       # noqa: E402
from shopping_shorts import clean_base as cb         # noqa: E402
from shopping_shorts.store import Store              # noqa: E402
from shopping_shorts.app import clean_failure_kind   # noqa: E402

keys = [k for k in Path(a.keyfile).read_text(encoding="utf-8").splitlines() if k.strip()]
mp._vmake_keys = lambda s, c=0: keys
store = Store(a.db); store.set_setting("clean_base_enabled", "1")
work_root = ROOT / "shopping_shorts" / "data" / "mix_jobs"; work = work_root / a.job
for f in list(work.glob("final_clean_*")) + [work / cb.BASE_FILE, work / vc._PENDING_FILE]:
    if f.exists():
        f.unlink()
store.update_mix_job(a.job, subtitle_removal=1, clean_status=None, clean_cuts=None, clean_tier=a.tier)
cuts = mp.clean_pick_cuts(store.get_mix_job(a.job), work)
sel = [cuts[int(i)]["key"] for i in a.pick.split(",")]
store.update_mix_job(a.job, clean_cuts=sel)
print("고른 컷:", sel, "%.2f초" % sum(cuts[int(i)]["dur"] for i in a.pick.split(",")))

_real_get = urllib.request.urlretrieve


def _run(block_download):
    def _get(url, dst, *x, **k):
        if block_download and "upload" not in url:
            raise ConnectionAbortedError("[시험] 결과 받기 강제 끊김")
        return _real_get(url, dst, *x, **k)
    urllib.request.urlretrieve = _get
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            mp.run_clean_sources(a.job, a.db, str(work_root))
    finally:
        urllib.request.urlretrieve = _real_get
    logs = buf.getvalue()
    j = store.get_mix_job(a.job)
    return j, logs


print("== 1차 (결과 받기 강제로 끊음)")
j, logs = _run(True)
print("   consume 줄:", logs.count("consume.json"), "| 상태:", j["clean_status"], "| 분류:", clean_failure_kind(j.get("clean_error")))
print("   오류문:", (j.get("clean_error") or "")[:160])
print("   장부:", (work / vc._PENDING_FILE).read_text(encoding="utf-8") if (work / vc._PENDING_FILE).exists() else "없음")
print("== 2차 (다시 누름)")
j, logs = _run(False)
print("   consume 줄:", logs.count("consume.json"), "| 업로드 줄:", logs.count("OSS upload start"),
      "| 이어받기 줄:", logs.count("이어받는다"), "| 상태:", j["clean_status"], j.get("clean_error") or "")
b = cb.load_base(work)
if b:
    print("   청소본:", Path(b["path"]).name, "| 프레임 조립본?/청소본", mp._probe_fps_frames(b["path"])[2])
print("   장부 남음:", (work / vc._PENDING_FILE).read_text(encoding="utf-8") if (work / vc._PENDING_FILE).exists() else "없음(정리됨)")
