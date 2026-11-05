import os

# OpenCV 가 그래픽 드라이버의 OpenCL 을 올리지 않게 한다 — 엔진 진입(runner_ops 는 tools, make.py 는 shopping_shorts)이 cv2 보다 먼저 이 패키지를 연다.
#   cv2.ORB 가 OpenCL.dll(드라이버)을 올리는데 계산은 Mat 이라 CPU 로 한다 — 켜든 끄든 결과 같다(test_no_opencl).
#   사건 #1397: AMD 드라이버가 실행기 끝내기에서 커널 대기로 프로세스를 못 닫게 한 짐작.
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"
