#!/usr/bin/env bash
# 자동배포: origin/main에 새 커밋 있으면 reset --hard로 강제 동기화(서버=main의 거울). 코드(py/html/js/css/dashboard/scripts) 바뀐 경우에만 재시작.
# 새 커밋 없으면 아무것도 안 함.
# ⚠️ 서버 로컬 수정은 강제로 덮인다(예전엔 '충돌 시 스킵'이었으나 그게 배포를 통째로 멈췄다).
#    서버가 직접 쓰는 파일은 반드시 .gitignore로 추적에서 빼둘 것 — 추적된 채면 3분마다 초기화된다.
# 서버 크론 등록: */3 * * * * /home/ubuntu/lotto-stock-wiki/deploy/auto_deploy.sh
set -uo pipefail
REPO=/home/ubuntu/lotto-stock-wiki
LOG=/tmp/auto_deploy.log
exec 9>/tmp/auto_deploy.lock
flock -n 9 || exit 0
cd "$REPO" || exit 1
git fetch origin main --quiet 2>>"$LOG" || { echo "$(date '+%F %T') fetch실패" >>"$LOG"; exit 0; }
LOCAL=$(git rev-parse HEAD); REMOTE=$(git rev-parse origin/main)
[ "$LOCAL" = "$REMOTE" ] && exit 0
echo "$(date '+%F %T') 새커밋 ${LOCAL:0:7}->${REMOTE:0:7} 배포시작" >>"$LOG"
# [2026-07-29 독립워커] 긴 작업(믹스·해외HOT 수집)이 전부 job_queue를 거치고, 실행은 서버가
# 아니라 별도 systemd 서비스(shopping-shorts-worker)가 한다. 그래서 판정이 단순해졌다:
#   - 서버(shopping-shorts)는 안에 긴 작업이 없으므로 **언제든 재시작해도 안전** → 배포를 안 미룬다.
#   - 워커만 진행 중인 작업이 있으면 재시작을 미룬다(다음 크론 3분 뒤 재시도).
# 예전 가드(2026-07-19)는 mix_jobs의 rendering 상태만 봐서, 해외HOT 수집(프로세스 메모리에만
# 있었음)과 믹스 매칭 단계가 그물에 안 걸렸다 — 배포가 그걸 죽였다(2026-07-29 하루 3건 실사고).
# ★좀비 가드: heartbeat는 워커가 30초마다 찍는다. 2분 넘게 안 뛰면 죽은 워커로 보고 안 미룬다
#   (죽은 job 하나가 배포를 영영 막는 게 이 repo 역사상 최악 사고, 9번 규칙 참고).
# ★DB 읽기 실패도 '진행 중 없음'(exit 1)으로 처리 = 배포 진행이 안전(멈춤보다 낫다).
WORKER_BUSY=0
DEPLOY_CHANGED=$(git diff --name-only "$LOCAL" origin/main)
if echo "$DEPLOY_CHANGED" | grep -qE '^shopping_shorts/'; then
  if python3 - <<'PY' 2>>"$LOG"
import sqlite3, sys
try:
    con = sqlite3.connect("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db", timeout=5)
    n = con.execute(
        # heartbeat_at은 SQLite datetime('now') 표준형(공백구분)으로 저장된다 —
        # 파이썬 ISO형('...T...')과 섞이면 문자열 비교가 깨지므로 datetime()으로 정규화한다
        # (2026-07-19에 그 함정을 한 번 밟았다).
        "SELECT COUNT(*) FROM job_queue "
        "WHERE state='running' "
        "AND datetime(heartbeat_at) > datetime('now','-2 minutes')").fetchone()[0]
    sys.exit(0 if n > 0 else 1)   # exit 0 = 진행 중 작업 있음 → 워커 재시작만 연기
except Exception as e:
    print("queue_check 오류(배포진행): %r" % e)
    sys.exit(1)
PY
  then
    WORKER_BUSY=1
    echo "$(date '+%F %T') 작업 진행 중 → worker 재시작만 연기(서버는 재시작) ${REMOTE:0:7}" >>"$LOG"
  fi
fi
# [2026-07-16] pull --ff-only → reset --hard: 서버는 main의 '거울'이지 작업 사본이 아니다.
# pull은 서버 워킹트리에 수정된 추적파일이 하나라도 있으면 거부하고 배포를 조용히 스킵했다.
# 실사고: SessionEnd 훅이 git add . 로 raw/를 main에 올렸는데(a133fcba=906파일) 서버는
# 크롤봇이 raw/를 계속 쓰는 중이라 영구 충돌 → 두 서비스 배포가 통째로 멈춤. 되돌려도
# 크롤봇이 즉시 다시 써서 경합에 짐 = 일회성 정리로 안 풀리는 구조적 문제였다.
# reset --hard는 그 로컬 수정을 무시하고 main을 강제로 씌운다.
# ⚠️ 전제: 서버가 '직접 쓰는' 파일은 git 추적에서 빠져 있어야 한다(같은 커밋에서 .gitignore
# 처리함 — autopilot_state 등). 추적된 채로 두면 3분마다 상태가 초기화된다.
if git reset --hard origin/main >>"$LOG" 2>&1; then
  CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE")
  if echo "$CHANGED" | grep -qE '^dashboard/|^scripts/'; then
    sudo systemctl restart stockbrain >>"$LOG" 2>&1 && echo "$(date '+%F %T') stockbrain 재시작완료 $(git rev-parse --short HEAD)" >>"$LOG"
  fi
  if echo "$CHANGED" | grep -qE '^shopping_shorts/'; then
    sudo systemctl restart shopping-shorts >>"$LOG" 2>&1 && echo "$(date '+%F %T') shopping-shorts 재시작완료 $(git rev-parse --short HEAD)" >>"$LOG"
    # 워커는 진행 중 작업이 있으면 건너뛴다 — 재시작하면 그 작업이 죽는다(이 전환의 목적).
    # 건너뛰어도 다음 크론(3분)이 다시 시도하므로, 작업이 끝나는 대로 새 코드로 갈아탄다.
    if [ "$WORKER_BUSY" = "0" ]; then
      sudo systemctl restart shopping-shorts-worker >>"$LOG" 2>&1 && echo "$(date '+%F %T') worker 재시작완료 $(git rev-parse --short HEAD)" >>"$LOG"
    else
      echo "$(date '+%F %T') worker 재시작 연기(작업 진행 중) $(git rev-parse --short HEAD)" >>"$LOG"
    fi
  fi
  if ! echo "$CHANGED" | grep -qE '^dashboard/|^scripts/|^shopping_shorts/'; then
    echo "$(date '+%F %T') 코드변경없음(데이터/문서만) 재시작생략 $(git rev-parse --short HEAD)" >>"$LOG"
  fi
else
  echo "$(date '+%F %T') reset실패 스킵-수동확인필요(디스크풀·권한·손상 의심)" >>"$LOG"
fi
