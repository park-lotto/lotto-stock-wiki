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


def _unit_status(unit):
    """Result + 마지막 종료 시각(부팅 후 경과 monotonic us). 벽시계 파싱(요일·로캘 의존)
    대신 /proc/uptime과 짝지어 age를 구한다."""
    p = subprocess.run(
        ["systemctl", "show", f"{unit}.service", "-p", "Result", "-p", "ExecMainExitTimestampMonotonic"],
        capture_output=True, text=True, timeout=10)
    kv = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
    return kv.get("Result", ""), kv.get("ExecMainExitTimestampMonotonic", "0")


def _read_uptime_s():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:  # noqa: BLE001 — 윈도우 개발기 등 /proc 없는 곳
        return None


def measure(ctx):
    """★리뷰 지적(2026-09-07): 옛 코드는 `res in ("success", "")`라 유닛이 없거나 systemctl이
    아무것도 안 줘도 OK였고, 마지막 실행 시각을 안 봐서 몇 달 전 성공한 타이머도 초록이었다.
    지금은 (1) 빈 결과는 회색(판정 불가) (2) Result=success여도 MAX_AGE_S(26시간)보다 오래됐으면
    빨강 — h_ranking_fresh 등 기존 계열과 같은 임계값을 쓴다."""
    out = []
    uptime_s = _read_uptime_s()
    for u in UNITS:
        item = f"h_batch_alive::{u}"
        name = f"{META['name']} — {u}"
        try:
            res, mono_us_raw = _unit_status(u)
            if not res:
                out.append(Sample(item, name, None, None,
                                  detail="Result 없음(유닛이 없거나 아직 안 돌았음) — 판정 불가"))
                continue
            mono_us = int(mono_us_raw or 0)
            if mono_us <= 0 or uptime_s is None:
                out.append(Sample(item, name, None, None,
                                  detail=f"Result={res} (마지막 실행 시각 관측 불가) — 판정 불가"))
                continue
            age_h = (uptime_s - mono_us / 1e6) / 3600
            ok = (res == "success") and (age_h * 3600 < MAX_AGE_S)
            out.append(Sample(item, name, round(age_h, 1), ok,
                              detail=f"Result={res}, {age_h:.1f}시간 전"))
        except Exception as e:  # noqa: BLE001
            out.append(Sample(item, name, None, None, detail=repr(e)))
    if os.path.exists(DAILY_BATCH_LOG):
        age = time.time() - os.path.getmtime(DAILY_BATCH_LOG)
        out.append(Sample("h_batch_alive::daily_batch", f"{META['name']} — daily_batch",
                          round(age / 3600, 1), age < MAX_AGE_S, detail=f"{age/3600:.1f}시간 전"))
    else:
        out.append(Sample("h_batch_alive::daily_batch", f"{META['name']} — daily_batch", None, None,
                          detail="로그 파일 없음(/tmp 소실?)"))
    return out
