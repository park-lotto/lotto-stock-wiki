#!/usr/bin/env bash
# 자동배포: origin/main에 새 커밋 있으면 pull. 코드(py/html/js/css/dashboard/scripts) 바뀐 경우에만 재시작.
# 새 커밋 없으면 아무것도 안 함. 작업트리 충돌 시 강제로 덮지 않고 스킵(데이터 보호).
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
if git pull --ff-only origin main >>"$LOG" 2>&1; then
  CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE")
  if echo "$CHANGED" | grep -qE '^dashboard/|^scripts/'; then
    sudo systemctl restart stockbrain >>"$LOG" 2>&1 && echo "$(date '+%F %T') stockbrain 재시작완료 $(git rev-parse --short HEAD)" >>"$LOG"
  fi
  if echo "$CHANGED" | grep -qE '^shopping_shorts/'; then
    sudo systemctl restart shopping-shorts >>"$LOG" 2>&1 && echo "$(date '+%F %T') shopping-shorts 재시작완료 $(git rev-parse --short HEAD)" >>"$LOG"
  fi
  if ! echo "$CHANGED" | grep -qE '^dashboard/|^scripts/|^shopping_shorts/'; then
    echo "$(date '+%F %T') 코드변경없음(데이터/문서만) 재시작생략 $(git rev-parse --short HEAD)" >>"$LOG"
  fi
else
  echo "$(date '+%F %T') pull실패(작업트리충돌?) 스킵-수동확인필요" >>"$LOG"
fi
