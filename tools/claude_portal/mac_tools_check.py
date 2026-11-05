"""맥 실행 도구 출처 검사(관제 328) — tools.lock.json 의 darwin-arm64·darwin-x64 항목을 실제로 받아
적힌 sha256(크롬은 md5_b64·size)과 맞는지 본다. 맥 한 줄 설치(installer/install.sh)가 고객 맥에서 같은 값으로 대조하므로,
여기서 틀리면 고객 설치가 '확인값이 다릅니다'로 멈춘다.

  py tools/claude_portal/mac_tools_check.py [--plat darwin-arm64] [--keep <폴더>]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "installer" / "common" / "tools.lock.json"
NEED = ("node", "chrome-headless-shell", "python", "ffmpeg", "ffprobe")


def fetch(url: str, dst: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "shortem-mac-tools-check"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plat", action="append")
    ap.add_argument("--keep")
    a = ap.parse_args(argv)
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    plats = a.plat or ["darwin-arm64", "darwin-x64"]
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        base = Path(a.keep) if a.keep else Path(td)
        base.mkdir(parents=True, exist_ok=True)
        for plat in plats:
            for name in NEED:
                e = lock.get(plat, {}).get(name)
                if not e:
                    print(f"✗ {plat} {name}: 잠금 파일에 없음"); bad += 1; continue
                f = base / f"{plat}-{name}-{Path(e['url']).name}"
                if not f.exists():
                    fetch(e["url"], f)
                data = f.read_bytes()
                if e.get("sha256"):
                    ok = hashlib.sha256(data).hexdigest() == e["sha256"]
                    how = "sha256"
                else:
                    ok = base64.b64encode(hashlib.md5(data).digest()).decode() == e["md5_b64"] and len(data) == e["size"]
                    how = "md5·size"
                print(f"{'✓' if ok else '✗'} {plat} {name} {e['version']} {len(data) // 1048576}MB {how}")
                bad += 0 if ok else 1
    print(f"결과: 실패 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
