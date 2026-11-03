# -*- coding: utf-8 -*-
"""08 전기자전거 워커3 — 렌즈쿠팡.py 를 워커 전용 크롬 프로필(.lens_profile_w3)로 부른다(공용 코드는 안 고침).
    PYTHONUTF8=1 py 렌즈_w3.py <이름> <사진…>"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent))
import tools.calcopy.lens as L  # noqa: E402
L.PROFILE = str(ROOT / ".lens_profile_w3")
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("lens_cp", HERE.parent / "렌즈쿠팡.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.HERE = HERE
m.main(sys.argv[1], sys.argv[2:])
