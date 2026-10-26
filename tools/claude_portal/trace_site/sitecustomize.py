"""엔진 실행 추적(관제 234) — PYTHONPATH 맨 앞에 이 폴더를 두면 **모든 파이썬 프로세스**(make.py 가 띄우는 remake.py 같은 자식까지)가
끝날 때 SHORTEM_TRACE_DIR/<pid>.json 에 '불러온 모듈 파일·연 파일'(SHORTEM_TRACE_ROOT 아래만)을 남긴다.
build_engine_bundle.py 가 이것들을 합쳐 고객 묶음 목록을 만든다(짐작 목록 금지 — 실제로 쓴 것만)."""
import atexit
import json
import os
import sys

_ROOT = os.environ.get("SHORTEM_TRACE_ROOT")
_OUT = os.environ.get("SHORTEM_TRACE_DIR")
if _ROOT and _OUT:
    _root = os.path.normcase(os.path.abspath(_ROOT))
    _opened = set()

    def _rel(p):
        try:
            raw = os.path.abspath(os.fsdecode(p))
        except Exception:
            return None
        if os.path.normcase(raw).startswith(_root + os.sep):   # 비교만 대소문자 무시 — 적는 이름은 원래 대소문자(10-19: 소문자로 적혀 ZdeZRtCeAC4 가 망가짐)
            return raw[len(_root) + 1:].replace("\\", "/")
        return None

    def _hook(ev, args):
        if ev == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            r = _rel(args[0])
            if r:
                _opened.add(r)

    sys.addaudithook(_hook)

    def _dump():
        mods = set()
        for m in list(sys.modules.values()):
            f = getattr(m, "__file__", None)
            r = _rel(f) if f else None
            if r:
                mods.add(r)
        third = sorted({n.split(".")[0] for n, m in list(sys.modules.items())
                        if not n.startswith("_") and n.split(".")[0] not in sys.stdlib_module_names
                        and not _rel(getattr(m, "__file__", "") or "")})
        os.makedirs(_OUT, exist_ok=True)
        with open(os.path.join(_OUT, f"{os.getpid()}.json"), "w", encoding="utf-8") as f:
            json.dump({"argv": sys.argv[:4], "modules": sorted(mods), "opened": sorted(_opened - mods), "third_party": third},
                      f, ensure_ascii=False)
    atexit.register(_dump)
