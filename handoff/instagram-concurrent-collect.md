# 인스타 수집 동시 실행

## 변경

- `scripts/daily_instagram_collect.py`에서 렌더·믹스 작업 종료를 기다리던 최대 4시간 대기 로직을 제거했다.
- 16 vCPU/30 GiB 증설 서버에서는 인스타 정기 수집을 렌더와 동시에 즉시 시작한다.
- 다른 자동 수집·발굴 작업의 `heavy_job_active()` 보호 로직은 유지했다.

## 검증

- `py -m pytest shopping_shorts/tests/test_heavy_job_gate.py -q` — 15 passed
- `py -m py_compile scripts/daily_instagram_collect.py` — 통과
- `git diff --check` — 통과

## 다음 확인

- 배포 후 기존 대기 중인 systemd 서비스를 재시작하고 crawl watch 진행률로 실제 시작을 확인한다.
