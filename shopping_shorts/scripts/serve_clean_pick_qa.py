# -*- coding: utf-8 -*-
"""장면 골라 지우기 화면 QA 서버 (2026-09-26) — clean_base_lab.py가 쓰는 LAB DB·job으로 제작소를 띄운다.

실행(트랙 폴더):  py shopping_shorts/scripts/serve_clean_pick_qa.py [--db shopping_shorts/data/lab.db] [--port 8769]
브라우저:         http://127.0.0.1:8769/produce  → 콘솔에서 MIX_JOB 지정 후 자막제거 패널을 연다.
★업체 호출은 가짜(아래 1/4 검은 띠)로 바꾼다 — 화면 QA에서 돈이 나가면 안 된다.
★'clean' 작업은 워커 대신 이 프로세스의 스레드가 바로 돌린다(진짜 run_clean_sources — 가짜는 업체 호출뿐).
"""
import argparse
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ap = argparse.ArgumentParser()
ap.add_argument("--db", default=str(ROOT / "shopping_shorts" / "data" / "lab.db"))
ap.add_argument("--port", type=int, default=8769)
a = ap.parse_args()
sys.argv = [sys.argv[0]]
import os                                           # noqa: E402
os.environ.setdefault("SHORTS_CLEAN_FINAL", "1")    # 라이브 서버와 같은 경로(완성본 1편 청소)

from shopping_shorts import config as cfg          # noqa: E402
cfg.DB_PATH = a.db
from shopping_shorts import app as A               # noqa: E402
from shopping_shorts import mix_pipeline as mp     # noqa: E402
from shopping_shorts import store as store_mod     # noqa: E402
import uvicorn                                     # noqa: E402

WORK_ROOT = ROOT / "shopping_shorts" / "data" / "mix_jobs"
A.DB_PATH = a.db
A._MIX_WORK_DIR = WORK_ROOT
A._need_own_key_or_402 = lambda *x, **k: None
CALLS = []


def _fake_vmake(src, keys, out, tier=None):
    CALLS.append((Path(src).name, tier, mp._probe_seconds(src)))
    print("[QA] 가짜 업체 호출: %s tier=%s %.2f초" % CALLS[-1], file=sys.stderr)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                    "-vf", "drawbox=x=0:y=ih*3/4:w=iw:h=ih/4:color=black@1:t=fill",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", str(out)], check=True)
    return str(out)


mp._vmake_clean = _fake_vmake
mp._vmake_keys = lambda s, c=0: ["qa-key"]
mp._charge_clean = lambda s, c, n: 0
_orig_enqueue = store_mod.Store.enqueue


def _enqueue(self, kind, payload, *x, **k):
    if kind == "clean":
        threading.Thread(target=mp.run_clean_sources, args=(payload["job_id"], a.db, str(WORK_ROOT)),
                         daemon=True).start()
        return 0
    return _orig_enqueue(self, kind, payload, *x, **k)


store_mod.Store.enqueue = _enqueue

if __name__ == "__main__":
    uvicorn.run(A.app, host="127.0.0.1", port=a.port, log_level="warning")
