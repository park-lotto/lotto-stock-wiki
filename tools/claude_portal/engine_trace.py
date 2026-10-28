"""엔진이 실제로 쓰는 파일만 재기 — 고객 설치팩 엔진 묶음의 목록 근거(관제 234 5판, 2026-10-19).

엔진(칼카피) 코드는 서버 코드와 얽혀 있어 '짐작으로 고른 목록'은 빠지거나(고객 PC 에서 ModuleNotFoundError) 넘친다
(우리 서버 코드·벤치 원본이 고객에게 감). 그래서 **실제로 돌려서** 불러온 모듈 파일과 연 파일을 적는다.

  py tools/claude_portal/engine_trace.py --root <엔진 사본> --out <trace.json> -- <스크립트.py> [인자…]

- 파이썬 쪽: 불러온 모듈의 파일 + open() 한 파일(감사 훅) 중 --root 아래 것만.
- 노드 렌더러(render_scene_style.js)가 여는 showcase 묶음은 여기서 못 본다 → build_engine_bundle 이 showcase html 의
  src/href·@font-face 를 읽어 따로 넣는다.
여러 번 돌린 trace 를 build_engine_bundle.py 가 합친다.
"""
from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if "--" not in argv:
        print(__doc__)
        return 2
    i = argv.index("--")
    opts, cmd = argv[:i], argv[i + 1:]
    root = Path(opts[opts.index("--root") + 1]).resolve()
    out = Path(opts[opts.index("--out") + 1]).resolve()
    opened: set[str] = set()

    def under(p) -> str | None:
        try:
            r = Path(os.fsdecode(p)).resolve()
            return r.relative_to(root).as_posix()
        except (ValueError, TypeError, OSError):
            return None

    def hook(event, args):
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            rel = under(args[0])
            if rel:
                opened.add(rel)

    sys.addaudithook(hook)
    sys.path.insert(0, str(root))
    os.chdir(root)
    script = str((root / cmd[0]).resolve()) if not Path(cmd[0]).is_absolute() else cmd[0]
    sys.argv = [script] + cmd[1:]
    code = 0
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        mods = set()
        for m in list(sys.modules.values()):
            f = getattr(m, "__file__", None)
            rel = under(f) if f else None
            if rel:
                mods.add(rel)
        third = sorted({n.split(".")[0] for n in sys.modules
                        if n.split(".")[0] not in sys.stdlib_module_names and not under(getattr(sys.modules[n], "__file__", "") or "")
                        and not n.startswith("_")})
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"cmd": cmd, "rc": code, "modules": sorted(mods),
                                   "opened": sorted(opened - mods), "third_party": third},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[trace] rc={code} 모듈 {len(mods)} · 연 파일 {len(opened - mods)} · 외부 {len(third)} → {out}")
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
