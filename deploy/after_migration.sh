#!/usr/bin/env bash
# 증설 후 마무리 — **새 서버에서** 한 번 실행한다(2026-08-22).
#
# 사장님이 콘솔에서 1~4번(스냅샷 → 새 인스턴스 → SSH 개방 → 고정IP 재부착)을 끝낸 뒤,
# 새 서버에 접속해 이것만 돌리면 나머지가 끝난다:
#
#     cd /home/ubuntu/lotto-stock-wiki && bash deploy/after_migration.sh
#
# 하는 일
#   1) 코어 수를 보고 **워커를 몇 개 띄울지 스스로 정한다**(코어당 1개, 최소 3·최대 8).
#      숫자를 손으로 적지 않는다 — 다음에 또 증설해도 이 스크립트가 그대로 맞다.
#   2) 스냅샷에 딸려온 **유령 워커**를 걷어낸다(1차 증설 때 실제로 부활했다).
#   3) 점검 스크립트를 돌려 before와 대조한다.
#
# ⚠️ 데이터 델타(스냅샷 이후 들어온 작업·DB)는 이 스크립트가 하지 않는다.
#    서버끼리는 SSH 키가 없어 직접 못 옮긴다(1차 실측) → 로컬 PC 경유로 먼저 끝내라.
#    순서: 옛 서버 정지 → 델타 이관 → 고정IP 재부착 → 이 스크립트.

set -u
# 시험용 손잡이 — SUDO=echo 로 돌리면 아무것도 바꾸지 않고 "무엇을 할지"만 찍는다.
# (라이브 서버에서 진짜로 돌리기 전에 이걸로 먼저 본다)
SUDO="${SUDO:-sudo}"
cd /home/ubuntu/lotto-stock-wiki || { echo "❌ 프로젝트 폴더가 없다"; exit 1; }

CORES="$(nproc)"
# 렌더 1편이 4코어를 364% 쓴다(실측). 코어보다 워커가 많으면 서로 뺏어 **더 느려진다**.
# 그래서 코어당 1개를 기준으로 잡되, 너무 적거나 많지 않게 3~8로 묶는다.
# ★상한 6 (2026-08-22 실측으로 정한 값). 8코어에 워커를 8개 띄우면 렌더끼리
#   코어를 다 가져가 웹·수집·크론이 굶는다. 실측(4코어, 20초 인코딩):
#     동시 1개 16.2초 / 3개 55.7초 / 6개 158.6초 — 코어를 넘기면 손해가 급격히 커진다.
#   그래서 "코어당 1개, 단 2코어는 서비스 몫으로 남긴다"로 잡는다.
#   바꾸려면 여기 숫자 하나만 고치면 된다(WORKERS=8 로 실행해 덮어쓸 수도 있다).
WANT="${WORKERS:-$((CORES - 2))}"
[ "$WANT" -lt 3 ] && WANT=3
[ "$WANT" -gt 6 ] && WANT=6

echo "=== 증설 후 마무리 ==="
echo "코어 $CORES개 감지 → 워커 $WANT개로 맞춘다"
echo

echo "--- 1) 유령 워커 정리 (스냅샷에서 딸려온 것)"
# 1차 증설(2026-08-06) 때 disabled인 구 유닛이 새 서버에서 같이 떴다. 목표 개수를
# 넘는 워커는 멈추고 자동시작도 끈다 — 남겨두면 코어를 조용히 갉아먹는다.
for i in $(seq $((WANT + 1)) 12); do
  if systemctl list-units --all "shopping-shorts-worker@$i.service" --no-legend 2>/dev/null | grep -q .; then
    echo "  worker@$i 정지·비활성화"
    $SUDO systemctl disable --now "shopping-shorts-worker@$i" 2>/dev/null
  fi
done

echo "--- 2) 워커 $WANT개 기동(부팅 시 자동시작 포함)"
for i in $(seq 1 "$WANT"); do
  $SUDO systemctl enable --now "shopping-shorts-worker@$i" 2>/dev/null \
    && echo "  worker@$i OK" || echo "  worker@$i ❌ 실패"
done
echo

echo "--- 3) 점검"
bash deploy/verify_server.sh > /home/ubuntu/after_upgrade.txt 2>&1
grep -E 'vCPU|메모리|디스크|살아있는 워커|요약|❌' /home/ubuntu/after_upgrade.txt
echo
if [ -f /home/ubuntu/before_upgrade.txt ]; then
  echo "--- 4) 증설 전과 달라진 점"
  diff /home/ubuntu/before_upgrade.txt /home/ubuntu/after_upgrade.txt | head -40
else
  echo "(before_upgrade.txt 없음 — 대조 생략)"
fi

cat <<'EOS'

=== 사람이 직접 확인할 것 (스크립트가 대신 못 한다) ===
  □ 화면에서 **영상 1편을 끝까지 제작**해 본다. 페이지가 뜨는 것과 렌더가 도는 건 다르다.
    ★동시성 확인은 mix·render로 한다 — durfill·prewarm은 _EXCLUSIVE_TASKS라
      워커를 늘려도 1개만 돈다(인스타 세션 보호). 그걸로 재면 "안 늘었다"고 오진한다.
  □ 다음 날 아침 크론(8:20 keyword_news / 8:30 pregen / 8:35 ingest / 9:10·9:12)이 도는지.
  □ 그 뒤에 옛 인스턴스를 **Delete**(Stop 아님 — 중지 상태에도 요금이 나간다).
EOS
