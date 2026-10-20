"""켤 때 자동 업데이트 묶음 올리기(관제 234 5판) — 설치팩 빌드 폴더(<out>/win-x64/Shortem)의 server/·engine/ 을 zip 으로 묶어
서버 저장소(claude_portal.store_dir)에 내용주소로 넣고 updates/latest.json 을 쓴다. 고객 PC 는 켤 때 /api/claude/update 로 받는다.

  py tools/claude_portal/publish_update.py --stage <빌드 폴더>/win-x64/Shortem --version 1.0.1 [--notes "…"]
  py tools/claude_portal/publish_update.py --install <dist>/shortem-win-x64-1.0.0.zip --plat win-x64 --version 1.0.0
    = exe 없이 까는 묶음(실행 도구까지 든 설치 폴더 통째, build_win 이 만든다) → install/latest-<plat>.json
  (서버에서 돌리거나, CLAUDE_STORE_DIR 를 서버 저장소와 같은 곳으로 두고 돌린다)

판단 주인: 무엇을 묶나 = UPDATE_DIRS(server·engine) 한 곳. 실행 도구(tools/)·모델(models/)은 설치팩을 다시 받는다.
결과물 검사: shortem_client/test/update.test.js — 받은 묶음을 풀어 바꾼 뒤 서버가 새 판으로 뜨는가.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path

UPDATE_DIRS = ("server", "engine")
SKIP = re.compile(r"(^|/)(__pycache__|\.git)(/|$)|\.pyc$")


def make_zip(stage: Path, version: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in UPDATE_DIRS:
            root = stage / d
            if not root.is_dir():
                raise SystemExit(f"[publish_update] {root} 없음")
            for p in sorted(root.rglob("*")):
                rel = p.relative_to(stage).as_posix()
                if p.is_file() and not SKIP.search(rel):
                    z.write(p, rel)
        z.writestr("app_version.json", json.dumps({"version": version}))
    return buf.getvalue()


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage")
    ap.add_argument("--install", help="설치 묶음 zip(build_win 이 만든 것) — 주면 업데이트 대신 설치 묶음을 올린다")
    ap.add_argument("--plat", default="win-x64")
    ap.add_argument("--version", required=True)
    ap.add_argument("--notes", default="")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"\d+\.\d+\.\d+", a.version):
        raise SystemExit("버전은 1.2.3 꼴")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from shopping_shorts import claude_portal as cp
    if a.install:
        if a.plat not in cp.INSTALL_PLATS:
            raise SystemExit(f"plat 은 {cp.INSTALL_PLATS} 중 하나")
        sha, size = cp.put_blob(Path(a.install))
        cp.install_path(a.plat).parent.mkdir(parents=True, exist_ok=True)
        cp.install_path(a.plat).write_text(json.dumps({"version": a.version, "sha256": sha, "size": size}), encoding="utf-8")
        print(json.dumps({"install": a.plat, "version": a.version, "sha256": sha, "mb": round(size / 1e6, 1)}, ensure_ascii=False))
        return 0
    if not a.stage:
        raise SystemExit("--stage 또는 --install")
    data = make_zip(Path(a.stage), a.version)
    tmp = cp.store_dir() / "updates" / f"shortem-app-{a.version}.zip"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    sha, size = cp.put_blob(tmp)
    tmp.unlink()
    cp.update_path().write_text(json.dumps({"version": a.version, "sha256": sha, "size": size, "notes": a.notes}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"version": a.version, "sha256": sha, "mb": round(size / 1e6, 1)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
