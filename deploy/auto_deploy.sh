#!/usr/bin/env bash
# 자동배포: origin/main에 새 커밋 있으면 reset --hard로 강제 동기화(서버=main의 거울). 코드(py/html/js/css/dashboard/scripts) 바뀐 경우에만 재시작.
# ⚠️ 서버 로컬 수정은 강제로 덮인다(예전엔 '충돌 시 스킵'이었으나 그게 배포를 통째로 멈췄다).
#    서버가 직접 쓰는 파일은 반드시 .gitignore로 추적에서 빼둘 것 — 추적된 채면 1분마다 초기화된다.
# 서버 크론 등록: */1 * * * * bash /home/ubuntu/lotto-stock-wiki/deploy/auto_deploy.sh
#   ★2026-08-06 3분 → 1분 (사장님: "그냥 바로 하게 안 되나"). 폴링이라 즉시는 아니지만
#     푸시 후 최대 대기가 3분→1분이 된다. 겹침은 맨 위 `flock -n 9 || exit 0`이 막으므로
#     주기를 줄여도 동시에 두 번 돌지 않는다(이미 도는 중이면 그냥 종료).
#     ⚠️ 서버를 다시 세우면 crontab은 안 따라온다(2026-08-06 증설 때 실제로 겪음) —
#        이 줄 그대로 `crontab -e`에 다시 넣을 것.
#
# ★2026-07-30 두 가지 변경 (사장님 지시: 사용자가 생겼을 때 배포가 끊김을 만들지 않게)
#   ① **연기한 재시작을 반드시 다시 시도한다(버그 수정).** 예전엔 연기한 사실을 기억하는 곳이
#      없었고, 다음 크론은 `LOCAL == REMOTE`라 맨 앞에서 종료해 **재시도 자체를 안 했다**.
#      결과: 새 커밋이 또 올 때까지 라이브가 옛 코드로 돌았다(실측 2026-07-30 14:21 worker
#      연기 → 이후 재시작 기록 없음 = 워커가 옛 코드로 계속 돌고 있었다).
#      → 남은 재시작 대상을 $PENDING에 적어두고, 새 커밋이 없어도 매 크론마다 재시도한다.
#   ② **웹 앱 재시작도 고객이 접속 중이면 미룬다.** 재시작은 수 초간 요청을 끊는다. 3분 크론이라
#      예고 없이 발생하므로, 최근 활동한 고객이 있으면 다음 크론으로 넘긴다.
#      (긴 작업=워커는 예전부터 이렇게 동작했다 — 같은 원리를 웹으로 확장한 것)
#   ⚠️ 무한 연기 방지: 대기가 $MAX_DEFER_SEC을 넘기면 웹은 **강제로** 재시작한다.
#      "배포가 영영 안 감"이 이 repo 역사상 최악 사고라, 끊김 몇 초보다 그게 더 위험하다.
#      워커는 강제하지 않는다 — 강제하면 사용자의 렌더가 죽는다. 대신 좀비 가드(heartbeat
#      2분)가 죽은 job을 걸러내므로 영영 막히지는 않는다.
#
# ★2026-08-06 두 가지 수정 (실사고: 병렬 대본 코드가 배포됐는데 워커가 옛 코드로 계속 돌았다)
#   ③ **워커 유닛이 템플릿 인스턴스로 바뀌었다**(worker@1/2/3, 동시제작용 다중화).
#      구 이름 `shopping-shorts-worker`는 **유닛 자체가 사라져**(could not be found) 재시작이
#      실패할 운명이었다. 지금 살아있는 인스턴스를 systemd에 물어서 전부 재시작한다.
#   ④ **배경작업만 도는 중이면 더 안 미룬다.** 좀비 가드는 '죽은 job'만 거른다 — 살아있는
#      배경작업(prewarm·durfill)이 **끊임없이 이어지면** busy가 영원히 참이라 재시작이
#      무한 연기됐다(실측 01:12~01:18 "연기(작업 진행 중, 360초 경과)" 반복, 그 사이
#      워커 3개가 4분 전 코드로 계속 돌았다). 고객 작업(mix·render·retype·preview·clean)이
#      돌 때만 미룬다 — 그건 죽이면 사장님이 만들던 영상이 날아가니까. 배경작업은 죽어도
#      다음 크론이 다시 큐에 넣으므로 잃는 게 없다.
set -uo pipefail
REPO=/home/ubuntu/lotto-stock-wiki
LOG=/tmp/auto_deploy.log
PENDING=/tmp/ss_pending_restart      # 한 줄에 유닛 하나: stockbrain|shopping-shorts|shopping-shorts-worker
SINCE=/tmp/ss_pending_since          # 최초 연기 시각(epoch) — 강제 재시작 판정 기준
MAX_DEFER_SEC=1800                   # 30분 넘게 못 재시작하면 웹은 강제 재시작
DB="$REPO/shopping_shorts/data/reference.db"
ACTIVE_WINDOW_SEC=300                # 이 시간 안에 활동한 고객이 있으면 '접속 중'으로 본다
exec 9>/tmp/auto_deploy.lock
flock -n 9 || exit 0
cd "$REPO" || exit 1

# ── 대기 목록 조작 ────────────────────────────────────────────────
_pending_add() {
  [ -f "$SINCE" ] || date +%s >"$SINCE"     # 최초 연기 시각은 한 번만 찍는다
  touch "$PENDING"
  grep -qxF "$1" "$PENDING" 2>/dev/null || echo "$1" >>"$PENDING"
}
_pending_del() {
  [ -f "$PENDING" ] || return 0
  grep -vxF "$1" "$PENDING" >"$PENDING.tmp" 2>/dev/null
  mv -f "$PENDING.tmp" "$PENDING" 2>/dev/null || rm -f "$PENDING.tmp"
  # 목록이 비면 대기 자체가 끝난 것 — 시각도 지워 다음 배포가 0초부터 센다.
  [ -s "$PENDING" ] || { rm -f "$PENDING" "$SINCE"; }
}
_pending_has() { grep -qxF "$1" "$PENDING" 2>/dev/null; }
# 최초 연기 시각부터 흐른 초. ★$PENDING의 mtime을 쓰면 안 된다 — _pending_del이 파일을
# 다시 쓸 때마다 mtime이 갱신돼 카운터가 리셋되고, 강제 재시작이 영원히 안 걸린다.
_pending_age() {
  [ -f "$SINCE" ] || { echo 0; return; }
  echo $(( $(date +%s) - $(cat "$SINCE" 2>/dev/null || date +%s) ))
}

# ── 진행 중 작업 확인(워커) ───────────────────────────────────────
# ★좀비 가드: heartbeat는 워커가 30초마다 찍는다. 2분 넘게 안 뛰면 죽은 워커로 보고 안 미룬다
#   (죽은 job 하나가 배포를 영영 막는 게 이 repo 역사상 최악 사고, CLAUDE.md 9번 규칙).
# ★DB 읽기 실패도 '진행 중 없음'으로 처리 = 배포 진행이 안전(멈춤보다 낫다).
_worker_busy() {
  python3 - "$DB" <<'PY' 2>>"$LOG"
import sqlite3, sys
try:
    con = sqlite3.connect(sys.argv[1], timeout=5)
    n = con.execute(
        # heartbeat_at은 SQLite datetime('now') 표준형(공백구분)으로 저장된다 —
        # 파이썬 ISO형('...T...')과 섞이면 문자열 비교가 깨지므로 datetime()으로 정규화한다
        # (2026-07-19에 그 함정을 한 번 밟았다).
        # ★고객 작업일 때만 미룬다(2026-08-06). 배경작업(prewarm·durfill·overseas)은
        #   재시작으로 죽어도 다음 크론이 다시 큐에 넣으므로 잃는 게 없다. 반면 이걸
        #   세면 배경작업이 끊임없이 이어질 때 배포가 **영원히** 안 나간다(실측 사고).
        "SELECT COUNT(*) FROM job_queue "
        "WHERE state='running' "
        "AND task IN ('mix','render','retype','preview','clean') "
        "AND datetime(heartbeat_at) > datetime('now','-2 minutes')").fetchone()[0]
    sys.exit(0 if n > 0 else 1)   # exit 0 = 진행 중 → 연기
except Exception as e:
    print("queue_check 오류(배포진행): %r" % e)
    sys.exit(1)
PY
}

# ── 접속 중 고객 확인(웹) ─────────────────────────────────────────
# customers.last_seen은 미들웨어 _track_activity가 60초 스로틀로 갱신한다. 사장님(id 0)은
# 애초에 기록하지 않으므로(falsy customer_id를 건너뜀) 내가 화면을 보고 있다고 배포가
# 미뤄지지는 않는다 — 미뤄야 하는 건 **고객**이 쓰는 중일 때다.
# DB 읽기 실패는 '아무도 없음'으로 본다(배포 진행이 안전).
_users_online() {
  python3 - "$DB" "$ACTIVE_WINDOW_SEC" <<'PY' 2>>"$LOG"
import sqlite3, sys, time
try:
    con = sqlite3.connect(sys.argv[1], timeout=5)
    cut = int(time.time()) - int(sys.argv[2])
    n = con.execute("SELECT COUNT(*) FROM customers "
                    "WHERE last_seen IS NOT NULL AND last_seen > ?", (cut,)).fetchone()[0]
    sys.exit(0 if n > 0 else 1)   # exit 0 = 접속 중 → 연기
except Exception as e:
    print("users_check 오류(배포진행): %r" % e)
    sys.exit(1)
PY
}

git fetch origin main --quiet 2>>"$LOG" || { echo "$(date '+%F %T') fetch실패" >>"$LOG"; exit 0; }
LOCAL=$(git rev-parse HEAD); REMOTE=$(git rev-parse origin/main)

# ★새 커밋이 없어도 대기 목록이 있으면 아래로 내려간다(①의 핵심 — 예전엔 여기서 끝났다).
if [ "$LOCAL" = "$REMOTE" ] && [ ! -f "$PENDING" ]; then
  exit 0
fi

if [ "$LOCAL" != "$REMOTE" ]; then
  echo "$(date '+%F %T') 새커밋 ${LOCAL:0:7}->${REMOTE:0:7} 배포시작" >>"$LOG"
  # [2026-07-16] pull --ff-only → reset --hard: 서버는 main의 '거울'이지 작업 사본이 아니다.
  # pull은 서버 워킹트리에 수정된 추적파일이 하나라도 있으면 거부하고 배포를 조용히 스킵했다.
  # 실사고: SessionEnd 훅이 git add . 로 raw/를 main에 올렸는데(a133fcba=906파일) 서버는
  # 크롤봇이 raw/를 계속 쓰는 중이라 영구 충돌 → 두 서비스 배포가 통째로 멈춤.
  # ⚠️ 전제: 서버가 '직접 쓰는' 파일은 git 추적에서 빠져 있어야 한다(autopilot_state 등).
  if ! git reset --hard origin/main >>"$LOG" 2>&1; then
    echo "$(date '+%F %T') reset실패 스킵-수동확인필요(디스크풀·권한·손상 의심)" >>"$LOG"
    exit 0
  fi
  CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE")
  if echo "$CHANGED" | grep -qE '^dashboard/|^scripts/'; then
    _pending_add stockbrain
  fi
  if echo "$CHANGED" | grep -qE '^shopping_shorts/'; then
    _pending_add shopping-shorts
    _pending_add shopping-shorts-worker
  fi
  if [ ! -f "$PENDING" ]; then
    echo "$(date '+%F %T') 코드변경없음(데이터/문서만) 재시작생략 $(git rev-parse --short HEAD)" >>"$LOG"
    exit 0
  fi
fi

[ -f "$PENDING" ] || exit 0
HEADSHORT=$(git rev-parse --short HEAD)
AGE=$(_pending_age)
FORCE=0
[ "$AGE" -ge "$MAX_DEFER_SEC" ] && FORCE=1

# ── 대기 목록 처리 ────────────────────────────────────────────────
# stockbrain(주식 대시보드)은 긴 작업도 고객 세션도 없어 언제든 재시작한다.
if _pending_has stockbrain; then
  sudo systemctl restart stockbrain >>"$LOG" 2>&1 \
    && echo "$(date '+%F %T') stockbrain 재시작완료 $HEADSHORT" >>"$LOG"
  _pending_del stockbrain
fi

# 웹 앱: 고객이 접속 중이면 연기. 단 $MAX_DEFER_SEC 넘기면 강제(배포가 영영 안 가는 게 더 위험).
if _pending_has shopping-shorts; then
  if [ "$FORCE" = "1" ] || ! _users_online; then
    [ "$FORCE" = "1" ] && echo "$(date '+%F %T') 연기 ${AGE}초 초과 → 웹 강제 재시작" >>"$LOG"
    sudo systemctl restart shopping-shorts >>"$LOG" 2>&1 \
      && echo "$(date '+%F %T') shopping-shorts 재시작완료 $HEADSHORT" >>"$LOG"
    _pending_del shopping-shorts
  else
    echo "$(date '+%F %T') 웹 재시작 연기(고객 접속 중, ${AGE}초 경과) $HEADSHORT" >>"$LOG"
  fi
fi

# 워커: 진행 중 작업이 있으면 연기 — 재시작하면 그 작업(렌더 등)이 죽는다.
# 강제하지 않는다. 좀비 가드(heartbeat 2분)가 죽은 job을 걸러내므로 영영 막히지 않는다.
if _pending_has shopping-shorts-worker; then
  if _worker_busy; then
    echo "$(date '+%F %T') worker 재시작 연기(고객작업 진행 중, ${AGE}초 경과) $HEADSHORT" >>"$LOG"
  else
    # ★살아있는 워커 유닛을 systemd에 물어본다(2026-08-06). 워커는 템플릿 인스턴스
    #   (worker@1/2/3)로 바뀌었고 구 이름 `shopping-shorts-worker`는 유닛이 없어져
    #   restart가 실패한다. 이름을 코드에 박으면 인스턴스 수가 바뀔 때마다 또 깨진다.
    WORKER_UNITS=$(systemctl list-units --type=service --state=loaded --no-pager --plain \
                     'shopping-shorts-worker*' 2>/dev/null | awk '{print $1}' | grep '\.service$')
    [ -z "$WORKER_UNITS" ] && WORKER_UNITS=shopping-shorts-worker.service
    if sudo systemctl restart $WORKER_UNITS >>"$LOG" 2>&1; then
      echo "$(date '+%F %T') worker 재시작완료 [$(echo $WORKER_UNITS | tr '\n' ' ')] $HEADSHORT" >>"$LOG"
      _pending_del shopping-shorts-worker
    else
      # 실패하면 PENDING을 지우지 않는다 — 다음 크론이 다시 시도한다(조용한 유실 방지).
      echo "$(date '+%F %T') ⚠️ worker 재시작 실패 — 다음 크론 재시도 $HEADSHORT" >>"$LOG"
    fi
  fi
fi
