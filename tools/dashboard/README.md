# 대시보드 log git 동기화 (2026-08-10)

## 왜
대시보드 기록 원본 `log.json`이 `C:\Users\TheRose\.claude\dashboard\`(git 밖)에 있어
**PC마다 따로**였다. 집에서 아티팩트를 재발행하면 회사 트랙이 통째로 사라지고,
매 세션 게시본에서 수동 병합해야 했다.

## 해법
log를 repo 안 `pipeline/dashboard_log.json`으로 이동 → 평소 깃풀·깃푸시에 실려
양PC 기록이 자동으로 합쳐진다. `dashboard_cli.py`의 `LOG_PATH`가 repo 경로를
가리키고, repo 폴더가 없는 PC에서는 옛 로컬 log로 폴백한다.

## 집PC(아직 미적용 PC)에서 할 일 — 1회
```
copy "<repo>\tools\dashboard\dashboard_cli.py" "C:\Users\TheRose\.claude\dashboard\dashboard_cli.py"
```
그 뒤부터는 아무것도 안 해도 된다. 단, 옛 로컬 `log.json`에만 있는 기록이 있으면
repo `pipeline/dashboard_log.json`에 항목을 합쳐 넣고 커밋할 것 (date+category+track 중복 제거).

## 주의
- 같은 날 양PC가 동시에 기록하면 pull 때 이 JSON에 git 충돌이 날 수 있다 —
  항목 단위 append라 양쪽 항목을 다 남기는 쪽으로 해소하면 된다.
- `dashboard.html`(렌더 결과)은 여전히 PC 로컬이다. 아티팩트 발행 전 `render`가
  자동으로 돌므로 pull만 되어 있으면 전체 트랙이 나온다.
