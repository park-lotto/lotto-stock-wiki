import os

# OpenCL 끄기 — 까닭은 tools/__init__.py 한 곳에 적었다(make.py 는 이 패키지로 들어온다).
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"
