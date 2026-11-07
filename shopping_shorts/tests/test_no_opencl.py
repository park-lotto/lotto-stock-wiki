# -*- coding: utf-8 -*-
"""엔진은 그래픽 드라이버의 OpenCL 을 올리지 않는다(사건 #1397) — 켜든 끄든 판정 결과는 같다."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# cv2.ORB 는 Mat 입력이어도 OpenCL 을 켤지 살피느라 OpenCL.dll 을 올린다(5.0.0 실측 — resize·dilate 등은 안 올림).
PROBE = r"""
import ctypes, hashlib, os, sys
sys.path.insert(0, sys.argv[1])
if sys.argv[2]:
    __import__(sys.argv[2])
import numpy as np, cv2
rng = np.random.default_rng(7)
g = cv2.cvtColor(cv2.GaussianBlur(rng.integers(0, 255, (360, 640, 3), dtype=np.uint8), (7, 7), 0), cv2.COLOR_BGR2GRAY)
kp, d = cv2.ORB_create(1500).detectAndCompute(g, None)
h = hashlib.sha1(np.float32([(k.pt[0], k.pt[1], k.angle, k.response) for k in kp]).tobytes() + d.tobytes()).hexdigest()
dll = bool(ctypes.windll.kernel32.GetModuleHandleW("OpenCL.dll")) if os.name == "nt" else False
print(int(dll), int(cv2.ocl.haveOpenCL()), h)
"""


def _probe(entry):
    env = {k: v for k, v in os.environ.items() if k != "OPENCV_OPENCL_RUNTIME"}
    out = subprocess.run([sys.executable, "-c", PROBE, str(ROOT), entry], env=env, cwd=str(ROOT),
                         capture_output=True, text=True, timeout=120, check=True).stdout.split()
    return int(out[0]), int(out[1]), out[2]


@pytest.mark.parametrize("entry", ["tools", "shopping_shorts"])
def test_엔진_진입은_OpenCL을_올리지_않는다(entry):
    dll, have, _ = _probe(entry)
    assert (dll, have) == (0, 0)


def test_OpenCL을_꺼도_ORB_판정은_같다():
    assert _probe("tools")[2] == _probe("")[2]
