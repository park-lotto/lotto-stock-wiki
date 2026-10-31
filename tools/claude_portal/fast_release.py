# -*- coding: utf-8 -*-
"""숏클 빠른 배포 — 고객 프로그램 수리를 병합·전체 빌드 없이 켤 때 자동 업데이트로 내보낸다(사장님 10-31).

  py tools/claude_portal/fast_release.py --rev <커밋> --notes "한 줄"            # 시험+묶기까지만(올리지 않음)
  py tools/claude_portal/fast_release.py --rev <커밋> --notes "한 줄" --publish  # 서버 등록까지
  py tools/claude_portal/fast_release.py --rollback --publish                   # 바로 앞 판 내용을 새 번호로

판단(새 판인가)은 서버 claude_portal.update_info, 묶기는 publish_update.make_zip — 여기는 순서만.
장부 = <STAGES>/releases.json. 판마다 <STAGES>/<판>/Shortem/{server,engine} 를 남겨 다음 판의 바탕·되돌리기로 쓴다.
막는 것: ① 커밋의 파일이 바탕 판과 다른 바탕에서 나왔을 때(딴 수정이 딸려 갈 때)
         ② 자동 업데이트로 못 바꾸는 파일(파이썬 부품·설치 도구) ③ shortem_client 시험 실패가 기준선보다 늘었을 때
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.claude_portal import upload_release as U          # noqa: E402
from tools.claude_portal.publish_update import make_zip      # noqa: E402

STAGES = Path("C:/t/shortem_stages")
LEDGER = STAGES / "releases.json"
BASELINE = Path(__file__).with_name("fast_release_baseline.json")   # 알려진 실패(시험 이름) — 고치면 빼고, 새 실패는 막는다
TESTS = ROOT / "shortem_client"


def target(path: str) -> str | None:
    """저장소 파일 → 설치본 자리. '' = 고객에게 안 가는 파일, None = 자동 업데이트로 못 가는 파일."""
    if path.startswith("shortem_client/server/"):
        return "server/" + path[len("shortem_client/server/"):]
    if path.startswith(("shortem_client/test/", "handoff/", "wiki/", "관제/", "tools/claude_portal/")):
        return ""
    if path.startswith(("tools/calcopy/", "shopping_shorts/", "channel/")):
        return "engine/" + path
    return None


def git(*a) -> bytes:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, check=True).stdout


def changed(rev: str) -> list:
    return [x for x in git("-c", "core.quotepath=false", "show", "--name-only", "--format=", rev).decode("utf-8").splitlines() if x]


def norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def failed_tests() -> set:
    r = subprocess.run("node --test --test-reporter=tap test/*.test.js", shell=True, cwd=TESTS, capture_output=True, encoding="utf-8", errors="replace")
    return {m.group(1).strip() for m in re.finditer(r"^not ok \d+ - (.+)$", r.stdout, re.M)}


def bump(v: str) -> str:
    a, b, c = v.split(".")
    return f"{a}.{b}.{int(c) + 1}"


def live() -> str:
    return json.loads(U.ssh(f"cat {U.STORE}/updates/latest.json"))["version"]


def register(uz: Path, version: str, notes: str, sha: str) -> None:
    U.scp([uz], f"{U.UPLOAD}/")
    reg = ("import json;from pathlib import Path;from shopping_shorts import claude_portal as cp;"
           f"p=Path('{U.UPLOAD}/{uz.name}');sha,size=cp.put_blob(p);p.unlink();"
           f"cp.update_path().write_text(json.dumps({{'version':'{version}','sha256':sha,'size':size,'notes':{notes!r}}},ensure_ascii=False),encoding='utf-8');print(sha)")
    got = U.ssh(f"cd {U.REPO} && echo {base64.b64encode(reg.encode()).decode()} | base64 -d | /usr/bin/python3 -").strip().splitlines()[-1]
    if got != sha:
        raise SystemExit("[빠른배포] 서버 확인값이 다르다 — 등록 상태를 확인하라")


def plan_files(rev: str, src: Path) -> list:
    files = changed(rev)
    bad = [f for f in files if target(f) is None]
    if bad:
        raise SystemExit(f"[빠른배포] 자동 업데이트로 못 가는 파일 — 전체 빌드가 필요하다: {bad}")
    files = [f for f in files if target(f)]
    if not files:
        raise SystemExit("[빠른배포] 고객에게 갈 파일이 없다")
    drift = []
    for f in files:
        have = src / target(f)
        try:
            before = git("show", f"{rev}~1:{f}")
        except subprocess.CalledProcessError:
            continue                  # 새 파일
        if not have.is_file() or norm(have.read_bytes()) != norm(before):
            drift.append(f)
    if drift:
        raise SystemExit(f"[빠른배포] 바탕 판과 달라 딴 수정이 딸려 간다 — 수리를 바탕 판 위에 다시 만들거나 전체 빌드: {drift}")
    new = failed_tests() - set(json.loads(BASELINE.read_text(encoding="utf-8")))
    if new:
        raise SystemExit(f"[빠른배포] 시험 실패가 늘었다: {sorted(new)}")
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev")
    ap.add_argument("--notes", default="")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    a = ap.parse_args(argv)
    if not LEDGER.is_file():
        raise SystemExit(f"[빠른배포] 장부가 없다: {LEDGER}")
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    cur = rows[-1]
    if a.publish and live() != cur["version"]:
        raise SystemExit(f"[빠른배포] 서버 판 {live()} ≠ 장부 끝 {cur['version']} — 전체 빌드가 올라갔다면 장부에 그 바탕을 먼저 넣어라")
    if a.rollback:
        if len(rows) < 2:
            raise SystemExit("[빠른배포] 되돌릴 앞 판이 없다")
        src, files, notes = STAGES / rows[-2]["version"] / "Shortem", [], f"되돌리기: {rows[-2]['version']} 내용"
    else:
        if not a.rev:
            raise SystemExit("--rev 가 필요하다")
        src, notes = STAGES / cur["version"] / "Shortem", a.notes
        files = plan_files(a.rev, src)
    version = bump(cur["version"])
    dst = STAGES / version / "Shortem"
    if dst.parent.exists():
        shutil.rmtree(dst.parent)
    dst.mkdir(parents=True)
    for d in ("server", "engine"):
        shutil.copytree(src / d, dst / d)
    for f in files:
        p = dst / target(f)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(git("show", f"{a.rev}:{f}"))
    uz = dst.parent / f"shortem-app-{version}.zip"
    uz.write_bytes(make_zip(dst, version))
    sha = U.sha256(uz)
    if a.publish:
        register(uz, version, notes, sha)
        rows.append({"version": version, "sha256": sha, "rev": a.rev, "notes": notes, "files": files})
        LEDGER.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"version": version, "published": a.publish, "mb": round(uz.stat().st_size / 1e6, 1), "sha": sha[:12], "files": files}, ensure_ascii=False))
    if not a.publish:
        shutil.rmtree(dst.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
