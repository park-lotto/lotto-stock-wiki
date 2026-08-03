#!/usr/bin/env bash
# 미리보기 인스턴스(2026-07-30) — 라이브에 내보내기 **전에** 내 브랜치 화면을 실제 서버 환경에서
# 브라우저로 확인하는 용도.
#
# 왜 필요한가: finish 게이트는 파이썬 테스트만 본다. HTML/JS가 깨져도 통과한다(실사고 있음 —
# 미해결 병합 마커가 든 JS가 라이브로 나가 화면이 죽었다). 로컬 PC로는 서버 환경·실데이터 구조를
# 재현하기 어렵다. 그래서 **같은 서버, 다른 포트**에 내 브랜치를 띄운다.
#
# 안전 설계(라이브를 절대 건드리지 않는다):
#   · 별도 워크트리(/home/ubuntu/preview) — 라이브 repo의 작업트리를 손대지 않는다.
#     ⚠️ 라이브 repo에서 `git add/commit`은 절대 금지지만(CLAUDE.md 9번), worktree는 작업트리를
#        더럽히지 않아 auto_deploy의 reset --hard와 충돌하지 않는다.
#   · 별도 DB — 워크트리 자기 data/ 폴더를 쓴다(라이브 reference.db를 열지 않는다).
#     실데이터가 필요하면 `--with-db`로 **복사**해 온다(원본은 읽기만).
#   · 127.0.0.1:8850 로컬 바인딩 — nginx에 붙이지 않으므로 외부에서 접근 불가. 내가 볼 때는
#     SSH 터널을 쓴다:  ssh -L 8850:127.0.0.1:8850 ubuntu@<서버>  → http://localhost:8850
#   · **상시 실행 안 함**(systemd enable 하지 않는다). 이 서버는 메모리가 빡빡해서
#     (2GB, 한가할 때도 swap 800MB+) 앱을 하나 더 상주시키면 렌더가 느려진다.
#     쓸 때 start, 확인 끝나면 stop.
#
# 사용법:
#   deploy/preview.sh start track/<트랙명> [--with-db]
#   deploy/preview.sh stop
#   deploy/preview.sh status
set -uo pipefail
LIVE=/home/ubuntu/lotto-stock-wiki
DIR=/home/ubuntu/preview
PORT=8850
PIDFILE=/tmp/ss_preview.pid
LOG=/tmp/ss_preview.log
ENVFILE=/etc/shopping-shorts.env

_stop() {
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    kill "$(cat "$PIDFILE")" 2>/dev/null
    sleep 1
    kill -9 "$(cat "$PIDFILE")" 2>/dev/null || true
    echo "미리보기 중지(pid $(cat "$PIDFILE"))"
  else
    echo "미리보기: 실행 중 아님"
  fi
  rm -f "$PIDFILE"
}

case "${1:-status}" in
  start)
    BRANCH="${2:-}"
    [ -n "$BRANCH" ] || { echo "브랜치를 주세요: preview.sh start track/<트랙명>"; exit 1; }
    _stop
    cd "$LIVE" || exit 1
    git fetch origin "$BRANCH" --quiet || { echo "fetch 실패: $BRANCH"; exit 1; }
    if [ -d "$DIR" ]; then
      git -C "$DIR" checkout --quiet --detach "origin/$BRANCH" || { echo "checkout 실패"; exit 1; }
      git -C "$DIR" reset --hard --quiet "origin/$BRANCH"
    else
      git worktree add --detach "$DIR" "origin/$BRANCH" || { echo "worktree 생성 실패"; exit 1; }
    fi
    mkdir -p "$DIR/shopping_shorts/data"
    if [ "${3:-}" = "--with-db" ]; then
      # 라이브 DB를 '복사'해 온다 — 미리보기가 라이브 DB에 쓰는 일은 절대 없다.
      # sqlite3 .backup은 쓰기 중에도 일관된 사본을 뜬다(cp는 찢어진 파일이 될 수 있다).
      python3 - "$LIVE/shopping_shorts/data/reference.db" "$DIR/shopping_shorts/data/reference.db" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
d = sqlite3.connect(dst)
s.backup(d); d.close(); s.close()
print("라이브 DB 사본 생성:", dst)
PY
    fi
    cd "$DIR" || exit 1
    set -a; . "$ENVFILE" 2>/dev/null || true; set +a
    nohup /usr/bin/python3 -m uvicorn shopping_shorts.app:app \
      --host 127.0.0.1 --port "$PORT" >>"$LOG" 2>&1 &
    echo $! >"$PIDFILE"
    sleep 3
    if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "미리보기 시작: $BRANCH @ 127.0.0.1:$PORT (pid $(cat "$PIDFILE"))"
      echo "  내 PC에서:  ssh -L $PORT:127.0.0.1:$PORT ubuntu@3.39.179.148"
      echo "  그다음:     http://localhost:$PORT"
      echo "  로그:       tail -f $LOG"
    else
      echo "기동 실패 — 로그 확인: tail -30 $LOG"; tail -20 "$LOG"; exit 1
    fi
    ;;
  stop)   _stop ;;
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "실행 중 (pid $(cat "$PIDFILE"), 포트 $PORT)"
      git -C "$DIR" log --oneline -1 2>/dev/null
    else
      echo "실행 중 아님"
    fi
    ;;
  *) echo "사용법: preview.sh {start <브랜치> [--with-db]|stop|status}"; exit 1 ;;
esac
