# 회사 운영실 M1 + 동적 업무 배정

세 회사를 회사 → 책임 역할 → 팀 → 프로젝트 → 검증 기록으로 탐색하는 로컬 운영실이다. 프로젝트·사건·담당자 배정은 SQLite에 실제 저장된다.

## 실행

트랙 루트에서 실행한다.

```powershell
$env:COMPANY_OPS_DB="$PWD/company_ops/data/company_ops.sqlite3"
python.exe -m uvicorn company_ops.app:app --host 127.0.0.1 --port 8917
```

브라우저: http://127.0.0.1:8917

localhost 무인증 앱이다. `--host 0.0.0.0`으로 인터넷이나 사내망에 공개하지 않는다. 기본 DB는 `company_ops/data/company_ops.sqlite3`, `COMPANY_OPS_DB`로 별도 경로를 지정할 수 있다.

## 현재 가능한 일

- 메이커스랩·에이치엔엘글로벌·스탁브레인과 제품·수익 구조 탐색
- 5개 팀별 기획·구현·검수 책임 규칙 확인
- 프로젝트 생성, 접수 → 설계 → 구현 → 검증 → 완료 기록
- 단계 이동 때 Astra·Claude·Opus·Codex 담당 카드 자동 이동
- 5초 간격 자동 조회로 다른 창에서 바뀐 배정과 기록 반영
- 차단·재개·검수 반려, 변경 이력과 검증 근거 저장
- 오래된 화면의 저장 충돌을 막는 버전 확인과 409 재조회

담당자 배정과 이력 이동은 실제 동작한다. 다만 AI 실행, 숏템메이커 장애, 회계·매출은 연결되지 않았다. 화면의 Astra·Claude·Opus·Codex 카드는 지금 할 일을 표시하는 배정 원장이며, 아직 모델 세션을 자동 호출하지 않는다. 검수자 이름도 인증 계정이 아닌 수동 기록이다. 후보 수익원과 대표 제공 현황은 실제 회계 실적이 아니다.

## 안전한 검증

`browser.cjs`는 대상 서버 DB에 실제 시험 프로젝트와 사건을 생성한다. 운영 서버/기본 운영 DB와 자동으로 분리되지 않는다. **기본 운영 포트 8917에 실행하지 않는다.** `.artifacts/`는 gitignore 대상이며 시험 DB와 캡처를 보관한다.

운영과 별도의 시험 DB·빈 포트에서 서버를 실행한다. 아래 예시는 8918이 비어 있는 것을 먼저 확인한다.

```powershell
python.exe -m unittest discover -s company_ops/tests -t . -p 'test_*.py' -v

Get-NetTCPConnection -LocalPort 8918 -State Listen -ErrorAction SilentlyContinue
$env:COMPANY_OPS_DB="$PWD/company_ops/.artifacts/e2e.sqlite3"
python.exe -m uvicorn company_ops.app:app --host 127.0.0.1 --port 8918
```

서버를 띄운 터미널과 별도의 터미널에서만 아래를 실행한다.

```powershell
$env:COMPANY_OPS_E2E='1'
$env:COMPANY_OPS_URL='http://127.0.0.1:8918'
node company_ops/tests/browser.cjs
```

브라우저 시험은 명시적인 `COMPANY_OPS_E2E=1`과 `COMPANY_OPS_URL` 없이는 시작하지 않는다. `COMPANY_OPS_BROWSER`로 다른 Chrome 실행 파일을 지정할 수 있다. 기본 브라우저 경로는 이 PC의 Puppeteer Chrome Headless Shell이다.

## 다음 단계

다음 단계는 모델 실행 어댑터와 숏템메이커의 실제 job/error 구조를 확인한 뒤 read-only 사건 연결부터 시작한다. 고객 작업 재실행, API 키 교체, CS 발송, 실서버 배포는 포함되지 않는다.
