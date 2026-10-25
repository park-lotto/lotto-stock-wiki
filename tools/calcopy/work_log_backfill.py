# -*- coding: utf-8 -*-
"""작업 기록지 소급(관제 263/265, 10-25) — 기록지가 생기기 전 편을 파일에서 알 수 있는 만큼만 채운다. 다시 돌려도 같은 줄을 두 번 쓰지 않는다.

  PYTHONUTF8=1 py tools/calcopy/work_log_backfill.py [--dry]

채우는 것(추측 금지 — 모르는 칸은 null, note 에 "소급"):
  ① 드라이브 G:/내 드라이브/칼카피영상 의 mp4(_이전판·해외 원본영상·기타 제외) → status=delivered
     our_channel = 드라이브 맨 위 폴더 이름 · bench_channel = 그 폴더의 벤치_*.txt 가 딱 하나일 때 그 이름(둘 이상이면 null)
     final_md5·duration = 파일을 직접 잰 값 · date = 드라이브 파일 수정 시각(만든 날이 아니라 올린 날 — note 에 적는다)
     final_path = 작업 폴더 final.mp4 중 md5 가 같은 것(없으면 null)
  ② 작업 폴더 C:/숏템_칼카피/<폴더>/…/final.mp4 중 드라이브 어느 파일과도 md5 가 다른 것 → status=made(완성본은 있으나 납품 기록 없음)
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy import work_log as WL  # noqa: E402
from tools.calcopy.engine.finalize import md5  # noqa: E402

DRIVE = Path("G:/내 드라이브/칼카피영상")
WORK = Path("C:/숏템_칼카피")
SKIP_DRIVE = {"_이전판", "해외 원본영상", "기타"}
SKIP_WORK = {"flowtest", "test_remake", "창고", "packs", "plan"}


def dur(p: Path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    try:
        return round(float(json.loads(r.stdout)["format"]["duration"]), 3)
    except Exception:  # noqa: BLE001
        return None


def kst(ts: float) -> str:
    return datetime.fromtimestamp(ts, WL.KST).isoformat(timespec="seconds")


def local_finals() -> list[Path]:
    out = []
    for ch in sorted(WORK.iterdir()):
        if not ch.is_dir() or ch.name.startswith(("_", ".")) or ch.name in SKIP_WORK:
            continue
        out += [p for p in ch.rglob("final.mp4") if len(p.relative_to(WORK).parts) <= 6]
    return out


def bench_of(top: Path):
    b = sorted(top.glob("벤치_*.txt"))
    return b[0].stem[len("벤치_"):] if len(b) == 1 else None


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry" in argv
    have = WL.read(WL.LOG)
    have_drive = {r.get("drive_path") for r in have if r.get("drive_path")}
    have_final = {r.get("final_path") for r in have if r.get("final_path")}
    loc = {}
    for p in local_finals():
        loc.setdefault(md5(p), []).append(p)
    print(f"[소급] 작업 폴더 final.mp4 {sum(len(v) for v in loc.values())}개 (md5 {len(loc)}가지)", flush=True)
    drive_files = [p for p in DRIVE.rglob("*.mp4") if not (set(p.relative_to(DRIVE).parts) & SKIP_DRIVE)]
    print(f"[소급] 드라이브 mp4 {len(drive_files)}개", flush=True)
    n_d = n_m = 0
    seen_md5 = set()
    for i, p in enumerate(sorted(drive_files), 1):
        if str(p) in have_drive:
            seen_md5.update(r.get("final_md5") for r in have if r.get("drive_path") == str(p))
            continue
        h = md5(p)
        seen_md5.add(h)
        top = DRIVE / p.relative_to(DRIVE).parts[0]
        fp = loc.get(h, [None])[0]
        rec = {"date": kst(p.stat().st_mtime), "our_channel": top.name, "bench_channel": bench_of(top),
               "final_path": str(fp) if fp else None, "final_md5": h, "drive_path": str(p), "duration": dur(p),
               "made_by": "owner", "status": "delivered",
               "note": "소급 · date=드라이브 파일 수정 시각" + (" · bench=폴더의 벤치_*.txt" if bench_of(top) else "")}
        if not dry:
            WL.append(rec)
        n_d += 1
        print(f"[소급 {i}/{len(drive_files)}] {p.relative_to(DRIVE)} · {h[:8]}" + (f" · 작업본 {fp.parent.parent.name}" if fp else ""), flush=True)
    for h, ps in loc.items():
        if h in seen_md5:
            continue
        for p in ps:
            if str(p) in have_final:
                continue
            rec = {"date": kst(p.stat().st_mtime), "final_path": str(p), "final_md5": h, "duration": dur(p), "made_by": "owner",
                   "status": "made", "note": f"소급 · 작업폴더 {p.relative_to(WORK).parts[0]} · 드라이브 납품 기록 없음 · date=파일 수정 시각"}
            if not dry:
                WL.append(rec)
            n_m += 1
    print(f"[소급 끝] 드라이브 납품 {n_d}줄 · 작업폴더만 {n_m}줄" + (" (dry — 안 씀)" if dry else ""), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
