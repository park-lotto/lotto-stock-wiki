"""숏템프리셋 페이지에 칼카피숏템엔진의 최신 장부를 올린다 (관제 224, 2026-10-17 사장님).

반영 시점(사장님 10-18): 세션은 자기 트랙에 커밋만, 반영은 사장님 요청 때나 새벽 2시에 tools/calcopy/preset_publish.py 가 이 도구를 불러 한 번에.
페이지(/shortem_preset)는 main 에 있는 장부만 읽는다 — 엔진 트랙에서 커밋만 하면 페이지는 옛 숫자다.
이 도구가 엔진 트랙 **마지막 커밋**의 장부·분석 문서를 숏템프리셋 트랙으로 옮겨 커밋한다(코드는 안 옮긴다).

  py tools/calcopy/sync_preset_ledgers.py --check   # main(origin) 과 엔진 마지막 커밋이 다른 파일만 보여 준다(바꾸지 않음)
  py tools/calcopy/sync_preset_ledgers.py           # 다른 파일을 .tracks/숏템프리셋 에 복사·커밋 → 이어서 track.py finish 숏템프리셋

옮길 목록은 shopping_shorts/calcopy_board.py 의 PRESET_LEDGERS·PRESET_DOCS·referenced_docs 한 곳(페이지가 읽는 것 = 옮기는 것).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_BRANCH = "track/칼카피숏템엔진"
DST = "숏템프리셋"


def _git(*a, cwd=ROOT, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, check=check)


def _files() -> list[str]:
    """장부 3장 + 고정 문서 + 엔진 판 스타일 장부가 근거로 가리키는 문서(페이지에서 열리게)."""
    import json
    sys.path.insert(0, str(ROOT))
    from shopping_shorts.calcopy_board import PRESET_LEDGERS, PRESET_DOCS, referenced_docs
    st = _blob(SRC_BRANCH, "channel/스타일.json")
    refs = sorted(referenced_docs(json.loads(st.decode("utf-8")))) if st else []
    return list(dict.fromkeys(list(PRESET_LEDGERS) + [p for p, _ in PRESET_DOCS] + refs))


def _blob(ref: str, path: str) -> bytes | None:
    r = _git("show", f"{ref}:{path}", check=False)
    return r.stdout if r.returncode == 0 else None


def stale() -> list[tuple[str, bytes]]:
    """엔진 마지막 커밋과 origin/main 이 다른 파일 [(경로, 엔진 판 내용)]. 엔진에 없는 파일은 건너뛴다."""
    _git("fetch", "-q", "origin", check=False)
    out = []
    for p in _files():
        src = _blob(SRC_BRANCH, p)
        if src is not None and src != _blob("origin/main", p):
            out.append((p, src))
    return out


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    head = _git("log", "--oneline", "-1", SRC_BRANCH).stdout.decode("utf-8", "replace").strip()
    diff = stale()
    print(f"엔진 마지막 커밋: {head}")
    if not diff:
        print("✅ 페이지 장부 = 엔진 마지막 커밋 (올릴 것 없음)")
        return 0
    for p, _ in diff:
        print(f"  다름: {p}")
    if "--check" in argv:
        print(f"⚠️ {len(diff)}개가 페이지(main)에 아직 안 올라갔다 → py tools/calcopy/sync_preset_ledgers.py")
        return 1
    # 트랙 폴더 안에서 돌려도 본 저장소(main 폴더) 기준으로 찾는다 — git 공용 폴더의 부모가 본 저장소
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir").stdout.decode("utf-8").strip())
    wt = common.parent / ".tracks" / DST
    if not wt.exists():
        print(f"❌ {wt} 가 없다 → py tools/track.py use {DST} (없으면 start {DST} --card 224)")
        return 2
    for p, data in diff:
        f = wt / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    _git("add", "--", *[p for p, _ in diff], cwd=wt)
    msg = f"숏템프리셋 장부 반영: 칼카피숏템엔진 {head.split()[0]} 의 {len(diff)}개 (관제 224)"
    r = _git("commit", "-m", msg, cwd=wt, check=False)
    print(r.stdout.decode("utf-8", "replace").strip() or r.stderr.decode("utf-8", "replace").strip())
    print(f"→ 이어서: py tools/track.py finish {DST}  (병합 뒤 py tools/live_admin.py shot shortem_preset out.png 로 숫자 확인)")
    return 0 if r.returncode == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
