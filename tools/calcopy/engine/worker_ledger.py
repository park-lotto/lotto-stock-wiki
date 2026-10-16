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
import time
from contextlib import contextmanager
from pathlib import Path

YT_PER_HOUR = 300
GEMINI_PER_HOUR = 10       # 10-16 보정: 엔진이 광고·과거 소재를 물어오는 동안 낮춤(처음 40)
PAUSE_429_SEC = 30 * 60
KINDS = ("yt", "gemini", "topic", "script", "limit", "pause", "error", "rescore", "rescore_done")


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
            used, cap, who = sum(r["n"] for r in rows if r["kind"] == "gemini" and r["worker"] == worker), GEMINI_PER_HOUR, worker
        else:
            raise ValueError(kind)
        if used + n > cap:
            why = f"한도: {kind} 시간당 {cap}({who}) — 지금 {used} + {what} {n}"
            _append(p, {"t": time.time(), "worker": worker, "kind": "limit", "n": 1, "note": why[:200]})
            raise LimitHit(why)
        _append(p, {"t": time.time(), "worker": worker, "kind": kind, "n": int(n), "note": what[:200]})


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
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--hours", type=float, default=1)
    a = ap.parse_args()
    print(json.dumps(summary(a.hours), ensure_ascii=False, indent=1))
