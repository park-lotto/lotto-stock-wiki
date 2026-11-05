# -*- coding: utf-8 -*-
"""설치본 부품 전수 검사 — 엔진 코드의 import(함수 안 포함)가 설치본 파이썬에서 실제로 찾아지는가.
10-31 사고: alibabacloud_oss_v2 가 함수 안 import 라 설치 시험을 통과하고 VMake 호출 때만 터졌다.

  <설치본>/tools/python/python.exe tools/claude_portal/engine_deps_check.py <설치본>/engine

결과: 없는 모듈과 그걸 부르는 파일 목록. 없으면 rc=1 — 빌드 관문에 건다.
_vendor/ 는 남의 패키지 사본이라 안쪽 import 는 재지 않는다(옛 파이썬 갈래 StringIO·imp, 쓰지 않는 aiohttp, 시험 자료 pycryptodome_test_vectors 오탐).
_vendor 패키지 자체는 sys.path 로 찾으므로 엔진이 부르는 이름은 그대로 검사된다.
"""
import ast
import importlib.util
import sys
from pathlib import Path


# 고객 실행 경로가 아닌 자체시험 전용 import
IGNORE = {"fontpath", "torch"}   # torch = 무료 자막 엔진 자기 venv(tools/free_subclean)에서만 — 묶음 파이썬엔 없다


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


def engine_py(root: Path) -> list:
    """검사할 엔진 코드 — _vendor 밑은 뺀다."""
    return [p for p in root.rglob("*.py") if "_vendor" not in p.relative_to(root).parts]


def main(root: str) -> int:
    root = Path(root)
    sys.path.insert(0, str(root))
    sys.path.append(str(root / "_vendor"))   # 업데이트로 오는 부품 자리
    files = engine_py(root)
    local = {p.stem for p in files} | {p.name for p in root.rglob("*") if p.is_dir() and "_vendor" not in p.relative_to(root).parts}
    users = {}
    for f in files:
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
    print(f"파일 {len(files)} · 모듈 {len(users)} · 없음 {len(missing)}")
    for m, fs in sorted(missing.items()):
        print(f"  없음 {m}  ({len(fs)}파일) {fs[:3]}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
