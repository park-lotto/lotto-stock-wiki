# -*- coding: utf-8 -*-
"""설치본 부품 전수 검사 — 엔진 코드의 import(함수 안 포함)가 설치본 파이썬에서 실제로 찾아지는가.
10-31 사고: alibabacloud_oss_v2 가 함수 안 import 라 설치 시험을 통과하고 VMake 호출 때만 터졌다.

  <설치본>/tools/python/python.exe tools/claude_portal/engine_deps_check.py <설치본>/engine

결과: 없는 모듈과 그걸 부르는 파일 목록. 없으면 rc=1 — 빌드 관문에 건다.
"""
import ast
import importlib.util
import sys
from pathlib import Path


# 고객 실행 경로가 아닌 자체시험 전용 import
IGNORE = {"fontpath"}


def imports_of(path: Path) -> set:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module.split(".")[0])
    return out


def main(root: str) -> int:
    root = Path(root)
    sys.path.insert(0, str(root))
    sys.path.append(str(root / "_vendor"))   # 업데이트로 오는 부품 자리
    local = {p.stem for p in root.rglob("*.py")} | {p.name for p in root.rglob("*") if p.is_dir()}
    users = {}
    for f in root.rglob("*.py"):
        for m in imports_of(f):
            users.setdefault(m, []).append(f.relative_to(root).as_posix())
    missing = {}
    for m, fs in users.items():
        if m in sys.stdlib_module_names or m in local or m in IGNORE:
            continue
        try:
            if importlib.util.find_spec(m) is None:
                missing[m] = fs
        except (ImportError, ValueError):
            missing[m] = fs
    print(f"파일 {sum(1 for _ in root.rglob('*.py'))} · 모듈 {len(users)} · 없음 {len(missing)}")
    for m, fs in sorted(missing.items()):
        print(f"  없음 {m}  ({len(fs)}파일) {fs[:3]}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
