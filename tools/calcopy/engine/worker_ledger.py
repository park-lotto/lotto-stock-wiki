# -*- coding: utf-8 -*-
"""소재창고 워커 장부 — 워커 여럿이 같이 쓰는 한도(관제 097, 2026-10-16 사장님 "상시로 돌려 창고에 쌓아라").

판단 주인: 한도 판정 = take() 한 곳. 워커·worker_steps 는 네트워크·제미나이를 쓰기 **전에** take 를 부른다.
  유튜브 조회(검색 결과 편수·상세 1편·재료 받기 편수) : 4워커 합 시간당 ≤ YT_PER_HOUR(300)
  제미나이 호출                                        : 워커당 시간당 ≤ GEMINI_PER_HOUR(10)
  429(쿼터)                                           : 그 워커 30분 쉼(pause_until)
넘으면 LimitHit(이유) — 부르는 쪽이 그 단계를 이유와 함께 멈춘다(조용히 넘어가지 않음). 한도에 걸린 일도 장부에 'limit' 로 남는다.
장부 = <CALCOPY_DATA_DIR>/calcopy/worker_ledger.jsonl (한 줄 = {t, worker, kind, n, note}). 여러 프로세스가 덧붙이므로 잠금 파일로 감싼다.

    py tools/calcopy/engine/worker_ledger.py --summary [--hours 1]     # 최근 N시간 종류별·워커별 합
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

YT_PER_HOUR = 300
GEMINI_PER_HOUR = 10       # 10-16 보정: 엔진이 광고·과거 소재를 물어오는 동안 낮춤(처음 40)
# 고객 PC 모드(관제 234): AI = 고객 본인 Claude — 우리 무료 키 보호 한도(10)는 맞지 않는다. 폭주만 막는 상한.
CLIENT_AI_PER_HOUR = int(os.environ.get("CALCOPY_CLIENT_AI_PER_HOUR") or 300)
PAUSE_429_SEC = 30 * 60
KINDS = ("yt", "gemini", "topic", "script", "ok", "limit", "pause", "error", "rescore", "rescore_done")   # ok = 단계 통과(note=단계 이름)


class LimitHit(Exception):
    pass


def path(data_dir=None) -> Path:
    root = Path(data_dir) if data_dir else Path(os.environ.get("CALCOPY_DATA_DIR") or (Path(__file__).resolve().parents[3] / "shopping_shorts" / "data"))
    p = root / "calcopy" / "worker_ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def _locked(p: Path, timeout: float = 20):
    lock = p.with_suffix(".lock")
    t0 = time.time()
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.time() - t0 > timeout:          # 죽은 프로세스가 남긴 잠금 — 오래되면 걷어낸다
                try:
                    if time.time() - lock.stat().st_mtime > timeout:
                        lock.unlink()
                        continue
                except OSError:
                    pass
                raise LimitHit(f"장부 잠금 {timeout}초 대기 초과({lock})")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except OSError:
            pass


def _rows(p: Path, since: float) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("t", 0) >= since:
            out.append(r)
    return out


def _append(p: Path, row: dict):
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def add(worker: str, kind: str, n: int = 1, note: str = "", data_dir=None):
    p = path(data_dir)
    with _locked(p):
        _append(p, {"t": time.time(), "worker": worker, "kind": kind, "n": int(n), "note": note[:200]})


def count(kind: str, seconds: float = 3600, worker: str | None = None, data_dir=None, now: float | None = None) -> int:
    rows = _rows(path(data_dir), (now or time.time()) - seconds)
    return sum(r.get("n", 0) for r in rows if r.get("kind") == kind and (worker is None or r.get("worker") == worker))


def take(worker: str, kind: str, n: int, what: str, data_dir=None):
    """쓰기 전에 부른다 — 한도 안이면 장부에 적고 통과, 넘으면 'limit' 줄을 남기고 LimitHit."""
    p = path(data_dir)
    with _locked(p):
        rows = _rows(p, time.time() - 3600)
        if kind == "yt":
            used, cap, who = sum(r["n"] for r in rows if r["kind"] == "yt"), YT_PER_HOUR, "4워커 합"
        elif kind == "gemini":
            cap = CLIENT_AI_PER_HOUR if os.environ.get("CALCOPY_GEMINI_BACKEND") == "client" else GEMINI_PER_HOUR
            used, who = sum(r["n"] for r in rows if r["kind"] == "gemini" and r["worker"] == worker), worker
        else:
            raise ValueError(kind)
        if used + n > cap:
            why = f"한도: {kind} 시간당 {cap}({who}) — 지금 {used} + {what} {n}"
            _append(p, {"t": time.time(), "worker": worker, "kind": "limit", "n": 1, "note": why[:200]})
            raise LimitHit(why)
        _append(p, {"t": time.time(), "worker": worker, "kind": kind, "n": int(n), "note": what[:200]})


def tail(n: int = 60, data_dir=None) -> list[dict]:
    """최근 장부 줄(작업기록 탭) — 새 것이 위."""
    p = path(data_dir)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines()[-int(n):]:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        r["at"] = time.strftime("%m-%d %H:%M:%S", time.localtime(r.get("t", 0)))
        out.append(r)
    return out[::-1]


def pause_until(worker: str, data_dir=None) -> float:
    """429 로 쉬기로 한 시각(없으면 0)."""
    rows = [r for r in _rows(path(data_dir), time.time() - PAUSE_429_SEC) if r["kind"] == "pause" and r["worker"] == worker]
    return max((r["t"] + PAUSE_429_SEC for r in rows), default=0.0)


def summary(hours: float = 1, data_dir=None) -> dict:
    rows = _rows(path(data_dir), time.time() - hours * 3600)
    out = {"hours": hours, "total": {}, "by_worker": {}, "limits": [], "errors": []}
    for r in rows:
        out["total"][r["kind"]] = out["total"].get(r["kind"], 0) + r["n"]
        w = out["by_worker"].setdefault(r["worker"], {})
        w[r["kind"]] = w.get(r["kind"], 0) + r["n"]
        if r["kind"] in ("limit", "pause", "error"):
            out["limits" if r["kind"] != "error" else "errors"].append(f"{time.strftime('%H:%M', time.localtime(r['t']))} {r['worker']} {r['note']}")
    out["kpi"] = kpi(hours, rows=rows)
    return out


_STEP_RE = re.compile(r"^(?:#\d+ )?(\w+):")


def kpi(hours: float = 1, data_dir=None, rows: list | None = None) -> dict:
    """KPI 판정 한 곳 — 시간당 새 후보·단계별 통과율·제미나이/유튜브 시간당·한도·429.
    통과 = 'ok' 줄(note=단계), 실패 = 'error' 줄('#id 단계: 이유' / 'find: 이유'). 통과율 = ok / (ok + error)."""
    rows = rows if rows is not None else _rows(path(data_dir), time.time() - hours * 3600)
    steps: dict = {}
    for r in rows:
        if r.get("kind") == "ok":
            st = (r.get("note") or "?").split()[0]
            steps.setdefault(st, {"ok": 0, "fail": 0})["ok"] += r.get("n", 1)
        elif r.get("kind") == "error":
            m = _STEP_RE.match(r.get("note") or "")
            st = m.group(1) if m else "?"
            steps.setdefault(st, {"ok": 0, "fail": 0})["fail"] += r.get("n", 1)
    for v in steps.values():
        v["rate"] = round(v["ok"] / (v["ok"] + v["fail"]), 3) if (v["ok"] + v["fail"]) else None
    tot = lambda k: sum(r.get("n", 0) for r in rows if r.get("kind") == k)   # noqa: E731
    ok_all, fail_all = sum(v["ok"] for v in steps.values()), sum(v["fail"] for v in steps.values())
    return {"hours": hours, "topics_per_hour": round(tot("topic") / hours, 2), "gemini_per_hour": round(tot("gemini") / hours, 2),
            "yt_per_hour": round(tot("yt") / hours, 2), "limit_hits": tot("limit"), "pause_429": tot("pause"),
            "steps": steps, "pass_rate": round(ok_all / (ok_all + fail_all), 3) if (ok_all + fail_all) else None,
            "script_pass_rate": (steps.get("script") or {}).get("rate")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--hours", type=float, default=1)
    a = ap.parse_args()
    print(json.dumps(summary(a.hours), ensure_ascii=False, indent=1))
