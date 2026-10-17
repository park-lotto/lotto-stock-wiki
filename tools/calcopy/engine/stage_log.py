# -*- coding: utf-8 -*-
"""단계 시간 장부 — 주인 한 곳(2026-10-18, 사장님 "손으로 재지 말고 도구가 기록"). hybrid/common.Timer 와 preset_make 가 이걸 쓴다.

파일 꼴(stage_log.json): {"stages":[{"stage","sec","note","at", …extra}]}  — 하이브리드 run.py 가 쓰던 꼴 그대로.

    from tools.calcopy.engine.stage_log import Timer, timed
    tm = Timer(work / "stage_log.json")
    with timed(tm, "render"): …            # 끝나면(예외도) 초를 적는다
    tm.done("tts", 12.3, calls=1)          # 직접 적기
    tm.summary()                           # "render 310.2 · tts 12.3"

모아 보기: py tools/calcopy/engine/stage_log.py <폴더…>   — 폴더 아래 stage_log.json 전부를 단계별 중앙값·최대로.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path


def _jload(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _jsave(p: Path, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


class Timer:
    """단계별 소요 초 장부 — '어디서 시간이 가나'를 도구가 숫자로 남긴다."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        try:
            self.cur: dict = _jload(self.path) if self.path.exists() else {"stages": []}
        except Exception:  # noqa: BLE001 — 깨진 장부는 새로 시작(이유를 적는다)
            self.cur = {"stages": [], "note": "이전 장부 깨짐 — 새로 시작"}

    def done(self, stage: str, sec: float, note: str = "", **extra):
        from tools.calcopy.engine.filelock import locked
        row = {"stage": stage, "sec": round(float(sec), 1), "note": note, "at": time.strftime("%Y-%m-%d %H:%M:%S"), **extra}
        with locked(self.path):                      # 두 판을 동시에 돌려도(--parallel · 세션 둘) 줄이 사라지지 않게 — 다시 읽고 덧붙인다(10-18 한혜진)
            try:
                self.cur = _jload(self.path) if self.path.exists() else self.cur
            except Exception:  # noqa: BLE001
                pass
            self.cur.setdefault("stages", []).append(row)
            _jsave(self.path, self.cur)

    def summary(self, last: int = 12) -> str:
        return " · ".join(f"{r['stage']} {r['sec']}" for r in self.cur["stages"][-last:])

    def total(self) -> float:
        return round(sum(r["sec"] for r in self.cur["stages"]), 1)


def timed(timer: Timer, stage: str, **extra):
    """with timed(tm, "render"): … — 끝나면 장부에 적는다(예외도 '실패: …' 로 적고 다시 올린다)."""
    class _T:
        def __enter__(self_):
            self_.t0 = time.time()
            return self_

        def __exit__(self_, et, ev, tb):
            timer.done(stage, time.time() - self_.t0, "실패: " + str(ev)[:200] if ev else "", **extra)
            return False
    return _T()


def collect(roots: list[str | Path]) -> dict:
    """폴더들 아래 stage_log.json 을 모두 읽어 단계별 n·중앙값·최대(초)."""
    by: dict[str, list[float]] = {}
    files = 0
    for r in roots:
        for p in Path(r).rglob("stage_log.json"):
            try:
                d = _jload(p)
            except Exception:  # noqa: BLE001
                continue
            files += 1
            for s in d.get("stages", []):
                by.setdefault(str(s.get("stage")).split(":")[0], []).append(float(s.get("sec", 0)))
    return {"files": files, "stages": {k: {"n": len(v), "median": round(statistics.median(v), 1), "max": round(max(v), 1)} for k, v in sorted(by.items())}}


if __name__ == "__main__":
    print(json.dumps(collect(sys.argv[1:] or ["."]), ensure_ascii=False, indent=1))
