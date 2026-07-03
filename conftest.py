import sys
import os

_ROOT = os.path.dirname(__file__)
sys.path.insert(0, _ROOT)
# dashboard/server.py가 "python dashboard/server.py"로 직접 실행될 때 자기 폴더가
# sys.path에 자동으로 잡히는 걸 전제로 형제 모듈을 절대 import(from briefing_detect
# import ...)한다. pytest가 project root에서 dashboard.server를 모듈로 import할 땐
# dashboard/가 sys.path에 없어서 ModuleNotFoundError가 남 → 여기서도 추가.
sys.path.insert(0, os.path.join(_ROOT, "dashboard"))

# scripts/ 밑의 언더스코어 접두 파일(_c2_test.py, _kis_test.py 등)은 수동 실행용
# 진단 스크립트(관례상 이름만 test 패턴과 겹침)라 pytest 자동수집에서 제외한다.
# import 시점에 win32com(윈도우 전용)·환경변수(KIS_APP_KEY) 등을 직접 참조해서
# 서버 CI 환경에서 항상 수집 에러가 났음.
collect_ignore_glob = ["scripts/_*.py"]
