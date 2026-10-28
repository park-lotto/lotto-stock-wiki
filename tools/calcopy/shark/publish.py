# -*- coding: utf-8 -*-
"""샥탬스토리 완성본 내보내기 — 바탕화면 칼카피영상/샥탬스토리/ 복사(MD5 같음 확인) + channel/결과물.json 끝에 한 줄 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/shark/publish.py <final.mp4> <편이름 예: 1편_STORMBAG> "<판정 글>"

결과물.json 은 다른 세션도 동시에 쓴다 → 쓰기 직전에 다시 읽고 items 끝에 붙이기만(같은 path 가 이미 있으면 그 줄을 고친다).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = Path("C:/Users/CH/Desktop/칼카피영상/샥탬스토리")


def md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def publish(final: Path, ep: str, judge: str) -> dict:
    DESK.mkdir(parents=True, exist_ok=True)
    dst = DESK / f"샥탬스토리_{ep}.mp4"
    shutil.copyfile(final, dst)
    a, b = md5(final), md5(dst)
    if a != b:
        raise SystemExit(f"MD5 다름 {a} vs {b}")
    sec = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)],
                               capture_output=True, text=True).stdout.strip())
    p = ROOT / "channel/결과물.json"
    D = json.loads(p.read_text(encoding="utf-8"))
    row = {"channel": "foreignshowshow", "channel_name": "샥탬스토리", "brand": "샥탬스토리", "style": "현장썰", "title": f"샥탬_{ep}",
           "path": str(final).replace("\\", "/"), "desktop": f"칼카피영상/샥탬스토리/{dst.name}", "md5": a, "seconds": round(sec, 2),
           "preset": "channel/foreignshowshow/preset/샤크탱크_검정띠2줄 + tools/calcopy/shark/rules.json", "date": "2026-10-18",
           "judge": judge, "from": "tools/calcopy/shark/render.py"}
    old = next((x for x in D["items"] if x.get("path") == row["path"]), None)
    if old:
        old.update(row)
        n = old["n"]
    else:
        n = max(x.get("n", 0) for x in D["items"]) + 1
        D["items"].append({"n": n, **row})
    p.write_text(json.dumps(D, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"n": n, "desktop": str(dst), "md5": a, "seconds": round(sec, 2)}


if __name__ == "__main__":
    print(publish(Path(sys.argv[1]), sys.argv[2], sys.argv[3]))
