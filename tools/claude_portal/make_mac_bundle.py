"""맥 설치 묶음 만들기(관제 328) — 서버에서 돈다. 맥 PC 없이 만든다.

지금 윈도 설치 묶음(install/latest-win-x64.json)에서 윈도 실행 도구(tools/)·VC 런타임(server/vcrt/)만 빼고,
맥 한 줄 설치(installer/install.sh)가 고객 맥에서 실행 도구를 받을 때 쓰는 목록 3개를 mac/ 에 넣는다.
엔진·서버·모델·효과음 팩·플러그인은 윈도와 같은 파일이다(플랫폼과 무관한 JS·파이썬·모델).
같은 묶음을 install/latest-mac-arm64.json · latest-mac-x64.json 둘 다 가리킨다(칩 차이는 install.sh 가 도구 받을 때 가른다).

  python3 tools/claude_portal/make_mac_bundle.py            서버 저장소(claude_portal.store_dir)에 만든다
  python3 tools/claude_portal/make_mac_bundle.py --dry      몇 개 빼고 몇 개 넣는지만

판단 주인: 무엇을 빼나 = DROP 한 곳 · 넣는 목록 = MAC_FILES(진짜 주인은 각 파일 — tools.lock.json·mac_requirements.py·write_manifest.js).
결과물 검사: 만든 zip 을 다시 열어 server/index.js·postinstall.js·mac/ 3개가 있고 tools/ 가 0개인지 본다(아니면 표를 안 쓴다).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DROP = ("tools/", "server/vcrt/")
MAC_FILES = {
    "mac/tools.lock.json": ROOT / "installer" / "common" / "tools.lock.json",
    "mac/requirements-engine-py312-mac.txt": ROOT / "installer" / "common" / "requirements-engine-py312-mac.txt",
    "mac/write_manifest.js": ROOT / "installer" / "common" / "write_manifest.js",
}
MUST = ("server/index.js", "postinstall.js", "server/license.js", "claude-plugin/") + tuple(MAC_FILES)


def build(src: Path, dst: Path) -> dict:
    kept = dropped = 0
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zo:
        for info in zi.infolist():
            if info.filename.startswith(DROP) or info.filename.startswith(tuple(MAC_FILES)):
                dropped += 1
                continue
            with zi.open(info) as f:
                zo.writestr(info, f.read(), compress_type=info.compress_type)
            kept += 1
        for arc, p in MAC_FILES.items():
            zo.write(p, arc)
    with zipfile.ZipFile(dst) as zc:
        names = zc.namelist()
    missing = [m for m in MUST if not any(n == m or n.startswith(m) for n in names)]
    leftover = sum(1 for n in names if n.startswith(DROP))
    if missing or leftover:
        raise SystemExit(f"맥 묶음 검사 실패: 없음 {missing} · 남은 윈도 도구 {leftover}")
    return {"kept": kept, "dropped": dropped, "added": len(MAC_FILES), "files": len(names)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    for p in MAC_FILES.values():
        if not p.is_file():
            raise SystemExit(f"없음: {p}")
    sys.path.insert(0, str(ROOT))
    from shopping_shorts import claude_portal as cp
    win = json.loads(cp.install_path("win-x64").read_text(encoding="utf-8"))
    src = cp.store_dir() / "assets" / win["sha256"]
    if a.dry:
        with zipfile.ZipFile(src) as z:
            n = z.namelist()
        print(json.dumps({"from": win["version"], "files": len(n), "drop": sum(1 for x in n if x.startswith(DROP))}))
        return 0
    with tempfile.TemporaryDirectory(dir=str(cp.store_dir())) as td:
        out = Path(td) / f"shortem-mac-{win['version']}.zip"
        rep = build(src, out)
        sha, size = cp.put_blob(out)
    row = {"version": win["version"], "sha256": sha, "size": size, "from_win_sha256": win["sha256"]}
    for plat in ("mac-arm64", "mac-x64"):
        p = cp.install_path(plat)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(row), encoding="utf-8")
    print(json.dumps({**rep, **row}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
