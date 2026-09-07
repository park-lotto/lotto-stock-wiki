"""새벽 배치가 돌았나(B-49). systemd 타이머 5개의 마지막 결과 + daily_batch 크론 로그 mtime.
daily_batch는 알림 경로가 없고(설계 D13) 로그가 /tmp라 재부팅 시 사라진다 → 없으면 회색."""
import os
import subprocess
import time

from shopping_shorts.checks.verdict import Sample

META = {"name": "새벽 배치가 돌았나", "every": "1h", "source": "systemctl show / /tmp/*.log"}
UNITS = ("shopping-shorts-collect", "shopping-shorts-category-backfill",
         "shopping-shorts-instagram-collect", "shopping-shorts-instagram-discover")
DAILY_BATCH_LOG = "/tmp/shopping_shorts_daily_batch.log"
MAX_AGE_S = 26 * 3600


def _unit_result(unit):
    p = subprocess.run(["systemctl", "show", f"{unit}.service", "-p", "Result", "-p", "ExecMainExitTimestampMonotonic"],
                       capture_output=True, text=True, timeout=10)
    kv = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
    return kv.get("Result", "")


def measure(ctx):
    out = []
    for u in UNITS:
        try:
            res = _unit_result(u)
            out.append(Sample(f"h_batch_alive::{u}", f"{META['name']} — {u}", None,
                              res in ("success", ""), detail=f"Result={res or 'n/a'}"))
        except Exception as e:  # noqa: BLE001
            out.append(Sample(f"h_batch_alive::{u}", f"{META['name']} — {u}", None, None, detail=repr(e)))
    if os.path.exists(DAILY_BATCH_LOG):
        age = time.time() - os.path.getmtime(DAILY_BATCH_LOG)
        out.append(Sample("h_batch_alive::daily_batch", f"{META['name']} — daily_batch",
                          round(age / 3600, 1), age < MAX_AGE_S, detail=f"{age/3600:.1f}시간 전"))
    else:
        out.append(Sample("h_batch_alive::daily_batch", f"{META['name']} — daily_batch", None, None,
                          detail="로그 파일 없음(/tmp 소실?)"))
    return out
