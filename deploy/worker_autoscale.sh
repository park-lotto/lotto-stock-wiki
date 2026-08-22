#!/usr/bin/env bash
# 워커 수를 **코어 수에 맞춰 자동으로** 맞춘다 — 부팅할 때마다 실행된다(2026-08-22).
#
# 왜 이게 필요한가
#   증설은 "플랜 변경"이 아니라 **스냅샷 → 새 인스턴스**다. 새 서버는 옛 서버의 설정을
#   그대로 물고 뜨므로, 코어가 4→8로 늘어도 **워커는 3개 그대로**다. 즉 돈을 더 내고도
#   동시 처리량은 그대로인 상태로 서비스가 시작된다. 사람이 스크립트를 기억해서 돌려야
#   하는 구조라면 언젠가 반드시 잊는다 — 그래서 부팅에 묶는다.
#
#   ★1차 증설(2026-08-06) 때 실제로 겪은 것: 스냅샷에서 뜬 새 서버에 구 워커 유닛이
#     disabled인데도 살아나 코어를 갉아먹었다. 여기서 같이 정리한다.
#
# 정책 (2026-08-22 실측으로 정한 값)
#   워커 = 코어 - 2, 단 3~6개로 묶는다.
#   · 2개를 빼는 이유: 렌더가 코어를 다 가져가면 웹·수집·크론이 굶는다.
#   · 상한 6인 이유: 실측(4코어, 20초 인코딩) 동시 1개 16.2초 / 3개 55.7초 /
#     6개 158.6초. 코어를 넘기는 순간 손해가 급격히 커진다.
#   바꾸려면 /etc/shopping-shorts.env 에 SHORTS_WORKERS=8 처럼 적으면 된다(재부팅 불필요,
#   이 스크립트를 다시 돌리면 즉시 반영).
#
# 안전
#   · 몇 번을 돌려도 결과가 같다(idempotent). 이미 맞으면 아무것도 안 한다.
#   · **줄이지 않는다** — 목표보다 많이 떠 있어도 돌고 있는 워커는 건드리지 않는다.
#     렌더 중인 워커를 죽이면 만들던 영상이 날아간다. 다만 '자동시작'만 꺼서
#     다음 부팅부터 정리되게 한다. (유일한 예외: 아무 일도 안 하는 워커는 즉시 정리)

set -u
ENV_FILE=/etc/shopping-shorts.env
[ -f "$ENV_FILE" ] && . "$ENV_FILE" 2>/dev/null

CORES="$(nproc)"
WANT="${SHORTS_WORKERS:-$((CORES - 2))}"
[ "$WANT" -lt 3 ] && WANT=3
[ "$WANT" -gt 6 ] && WANT=6

echo "[워커자동조정] $(date '+%F %T') 코어 ${CORES}개 → 워커 ${WANT}개 목표"

# ── 목표까지 켠다(이미 켜져 있으면 systemd가 알아서 아무 일도 안 한다) ──
for i in $(seq 1 "$WANT"); do
  systemctl enable --now "shopping-shorts-worker@$i" >/dev/null 2>&1 \
    && echo "  worker@$i 가동" || echo "  worker@$i ❌ 실패"
done

# ── 목표를 넘는 워커: 자동시작만 끄고, **일감이 없을 때만** 멈춘다 ──
for i in $(seq $((WANT + 1)) 12); do
  unit="shopping-shorts-worker@$i"
  systemctl list-units --all "$unit.service" --no-legend 2>/dev/null | grep -q . || continue
  systemctl disable "$unit" >/dev/null 2>&1        # 다음 부팅부터는 안 뜬다
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    # 렌더 중인 워커를 죽이면 만들던 영상이 날아간다. 지금 무언가 물고 있는지 본다.
    busy="$(python3 - <<'PY' 2>/dev/null || echo unknown
import sqlite3, sys
try:
    c = sqlite3.connect('/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db', timeout=5)
    n = c.execute("SELECT COUNT(*) FROM job_queue WHERE state='running'").fetchone()[0]
    print('busy' if n else 'idle')
except Exception:
    print('unknown')
PY
)"
    if [ "$busy" = "idle" ]; then
      systemctl stop "$unit" >/dev/null 2>&1 && echo "  worker@$i 정리(놀고 있었음)"
    else
      echo "  worker@$i 자동시작만 해제 — 작업 중이라 지금은 안 멈춘다"
    fi
  fi
done

live="$(systemctl list-units 'shopping-shorts-worker@*' --no-legend 2>/dev/null | grep -c active)"
echo "[워커자동조정] 완료 — 현재 가동 ${live}개"
