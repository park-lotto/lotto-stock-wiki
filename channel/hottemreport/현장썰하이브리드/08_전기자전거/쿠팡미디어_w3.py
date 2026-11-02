# -*- coding: utf-8 -*-
"""08 워커3 — 쿠팡미디어.py 를 워커 전용 크롬 프로필(<트랙>/.coupang_w3/.coupang_profile_hr)로 부른다(공용 코드 안 고침).
    PYTHONUTF8=1 py 쿠팡미디어_w3.py <상품번호…>"""
import importlib.util, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cm", HERE.parent / "쿠팡미디어.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.ROOT = HERE.parents[3] / ".coupang_w3"
m.ROOT.mkdir(exist_ok=True)
m.main(sys.argv[1:])
