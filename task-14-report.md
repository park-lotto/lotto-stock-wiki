# Task14 정정 — 버튼 전수 훑기 거짓 빨강(클릭 실패=회색) + 이름 정정 (2026-09-07)

## 상태
완료. 서버 미리보기(8850) 2회 연속 실측 완료, 미리보기 정지함.

## 커밋
`cd4898a34` — track/검수뼈대 (origin push 완료)

## 수정 내용
- `_press()`: 클릭/입력 자체가 실패(TimeoutError 등, "누르지 못함")하면 **GRAY**.
  실제로 눌렀는데 그 결과 pageerror/4xx-5xx/백지가 나는 경우만 `classify()`를 거쳐 **RED** —
  두 경로를 분리해서 유지(단언 테스트 2건으로 고정).
- `hit_test` 실패("가려짐")도 같은 이유로 RED→GRAY (`_sweep_panel_buttons`, `sweep_url`).
- `_display_name()` 신설: 텍스트 → aria-label/title → onclick 함수명 → "이름 없는 버튼 N번째" 순,
  패널 라벨을 문맥으로 앞에 붙임. `signature_of()`는 그대로 둬 이력(새로 빨강 계산)이 안 흔들림.
- 시간예산 초과분: `checks_sweep_rotation.json`에 마지막 시작 패널을 남겨 다음 run이 그 다음
  패널부터 시작하도록 회전(run_checks.py가 매번 `panels=range(10)` 기본값으로만 부르므로 자동
  이어받기는 아니지만, 여러 날에 걸쳐 뒤 패널도 앞자리를 받게 됨).

## 테스트
로컬: `pytest shopping_shorts/tests/test_checks_sweep.py` 49 passed, 2 skipped.
전체 checks 관련: `pytest shopping_shorts/tests -k checks` 153 passed, 5 skipped.
새로 추가한 8건 중 핵심 2건이 GRAY/RED 분리를 단언:
- `test_press_click_timeout_is_gray_not_red` — 클릭 타임아웃 → GRAY, "누르지 못함" 문구 확인
- `test_press_real_error_after_successful_click_stays_red` — 클릭 성공 뒤 pageerror → RED 유지

## 서버 실측 (미리보기 8850, track/검수뼈대 cd4898a34)
- 1회차: L1(버튼 전수) green 81 / gray 14 / **red 0**
- 2회차: L1 green 89 / gray 11 / **red 0**
- 두 실행 모두 L1 계층 RED 없음 — 이전 17건 빨강(대부분 "조작 실패 TimeoutError")이 전부
  회색으로 옮겨감. 회색 사유 예: "버튼을 누르지 못함(3초 안에 클릭 불가 — 가려졌거나 비활성일
  수 있음): TimeoutError: Page.click: Timeout 3000ms exceeded."
- 남은 전체 RED 11건은 L0/L2 쪽(키 로테이션·틱톡/threads 랭킹 등) — 이번 수정 범위 밖, 진짜
  서비스 이슈로 보이며 두 회차 모두 재현됨(값 자체는 이 작업과 무관).
- rotation 상태 파일: 1회차 뒤 `next_start=1`, 2회차 뒤 `next_start=2` — 회전이 실제로 진행됨을
  확인.

## 이름 예시(실측)
- `영상추출/분석 — 이 칸 지우기`
- `영상추출/분석 — addMixUrl`
(패널 문맥 + 버튼 텍스트/onclick 함수명 조합. 다만 `영상추출/분석 — on`처럼 checkbox의
value="on" 같은 값이 그대로 텍스트로 잡히는 잔여 케이스가 하나 관측됨 — 오작동은 아니지만
표시 이름이 완전히 이상적이진 않음, 추후 개선 여지로 남김.)

## 재현성
2회 연속 서버 실측 모두 L1 RED=0, 동일 패턴(회색화 확인). 완전히 동일한 카운트는 아님(회전으로
매번 다른 패널 서브셋을 도는 게 의도된 설계라 정상적인 차이).

## 안전 규칙 준수
- 라이브(8849) 미접촉, systemd 무손댐, `track.py finish`/main 병합 없음.
- `taskkill`/`pkill -f python` 없음, 서버 워킹트리에서 git add/commit 없음.
- `allow_mutations.py` 미수정.
- 작업 종료 후 미리보기 정지 완료.
