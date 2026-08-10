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
#
# ★scripts/test_*.py도 같은 이유로 제외한다 (2026-08-10).
#   scripts/test_wisereport.py는 테스트가 아니라 **Playwright 스크래퍼**다 —
#   def test_* 가 하나도 없고 모듈 최상위에서 바로 실행된다(브라우저를 띄워 외부
#   사이트에 접속하고 xls를 내려받는다). 이름이 test_로 시작해서 pytest가 수집 중에
#   import → 실제로 크롤링이 돌고, 그 부작용으로 캡처가 깨져
#   **저장소 루트에서 pytest를 돌리면 'no tests ran'으로 전체가 죽었다**(실측).
#   finish 게이트는 pytest shopping_shorts/tests로 범위를 좁혀 돌아서 영향이 없었지만,
#   사람이나 도구가 루트에서 돌리면 0개가 나와 "테스트가 없다"로 오인한다.
#   → scripts/는 수동 실행 스크립트 폴더라는 전제를 명시적으로 박는다.
#
# ★scratchpad/ 도 통째로 제외 (2026-08-10).
#   임시 probe·fixture를 던져두는 폴더다. scratchpad/auth_test.py는 import 시점에
#   `C:\Users\TheRose\Desktop\...\db\.session_secret`(옛 집PC 절대경로)를 열어서
#   FileNotFoundError로 수집을 깬다. 이름이 *_test.py라 pytest가 주워간다.
#
# ★docs/ 도 제외 (2026-08-10) — 문서 폴더다. 테스트가 있을 곳이 아니다.
#   docs/어미교정/gen_style_test.py 가 `*_test.py` 패턴에 걸리는데 def test_*가 0개고
#   import 시점에 load_dotenv + 외부 API를 때린다. **이게 저장소 전체 수집을 죽인 범인**이다:
#   다른 빈 폴더는 rc=5(no tests)인데 docs만 rc=1로 죽어서, 인자 없이 pytest를 돌리면
#   "collected 0 items"로 전부 무너졌다(실측 2026-08-10 — 폴더별 rc 대조로 특정).
collect_ignore_glob = ["scripts/_*.py", "scripts/test_*.py", "scratchpad/*", "docs/*"]
