# 연결 파일 — 주인은 tools/calcopy/engine/sound/narr_report.py (10-20 한 벌로 옮김). 여기서 고치지 마라.
import importlib.util as _u, pathlib as _p, runpy as _r, sys as _s
_own = _p.Path(__file__).resolve().parents[3] / "tools/calcopy/engine/sound" / "narr_report.py"
_s.path.insert(0, str(_own.parent))
if __name__ == "__main__":
    _r.run_path(str(_own), run_name="__main__")
else:
    _sp = _u.spec_from_file_location("_eng_narr_report", _own); _m = _u.module_from_spec(_sp); _sp.loader.exec_module(_m)
    globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})
