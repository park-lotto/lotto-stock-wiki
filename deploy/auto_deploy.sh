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
# [2026-07-19] 렌더 중 배포 연기: 최종 렌더는 shopping-shorts 프로세스 내 백그라운드 작업이라
# systemctl restart가 진행 중 렌더를 SIGKILL한다(job status가 'rendering'에 얼어붙어 UI 무한 '렌더 중').
# 들어온 변경이 shopping_shorts/를 건드려(=재시작 유발) 살아있는 렌더가 있으면 이번 배포를 통째로
# 미루고 다음 크론(3분)에 재시도한다. dashboard/scripts만 바뀐 배포는 여기 안 걸림(렌더 무관).
# ★좀비 가드: 30분 넘게 status 안 바뀐 렌더는 죽은 것으로 보고 미루지 않는다 — 안 그러면 죽은 job
#   하나가 모든 배포를 영영 막는다(배포 멈춤은 이 repo 역사상 최악 사고, 9번 규칙 참고).
# ★DB 읽기 실패도 '렌더 없음'(exit 1)으로 처리 = 배포 진행이 안전(멈춤보다 낫다).
DEPLOY_CHANGED=$(git diff --name-only "$LOCAL" origin/main)
if echo "$DEPLOY_CHANGED" | grep -qE '^shopping_shorts/'; then
  if python3 - <<'PY' 2>>"$LOG"
import sqlite3, sys
try:
    con = sqlite3.connect("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db", timeout=5)
    n = con.execute(
        # updated_at은 파이썬 ISO형('...T...+00:00')이라 SQLite 표준형(공백구분)과
        # 문자열 비교하면 'T'>' '로 항상 크게 나와 좀비 가드가 무력화된다(실측 2026-07-19).
        # datetime(updated_at)로 정규화해야 시각 비교가 맞다.
        # ★2026-07-24: 최종 렌더(status)뿐 아니라 **미리보기(preview_status='rendering')**도
        #   본다 — 예전엔 preview를 안 봐서 재시작이 미리보기 ffmpeg를 계속 죽였다(사장님 실측).
        "SELECT COUNT(*) FROM mix_jobs "
        "WHERE (status IN ('rendering','removing_subtitles') OR preview_status='rendering') "
        "AND datetime(updated_at) > datetime('now','-30 minutes')").fetchone()[0]
    sys.exit(0 if n > 0 else 1)   # exit 0 = 살아있는 렌더 있음 → 배포 연기
except Exception as e:
    print("render_check 오류(배포진행): %r" % e)
    sys.exit(1)
PY
  then
    echo "$(date '+%F %T') 렌더 중 → shopping_shorts 배포 연기(다음 크론 재시도) ${REMOTE:0:7}" >>"$LOG"
    exit 0
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
  fi
  if ! echo "$CHANGED" | grep -qE '^dashboard/|^scripts/|^shopping_shorts/'; then
    echo "$(date '+%F %T') 코드변경없음(데이터/문서만) 재시작생략 $(git rev-parse --short HEAD)" >>"$LOG"
  fi
else
  echo "$(date '+%F %T') reset실패 스킵-수동확인필요(디스크풀·권한·손상 의심)" >>"$LOG"
fi
