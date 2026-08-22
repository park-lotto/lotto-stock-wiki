#!/usr/bin/env bash
# 서버 상태 점검 — 증설(플랜 변경) 전후에 같은 것을 재서 대조한다.
#
# 왜: 새 인스턴스는 "스냅샷에서 복원"이라 대체로 그대로 살아나지만, 실제로 무엇이
# 안 살아났는지는 **재봐야** 안다. 2026-08-22 실측으로 이 서버가 굴리는 것은
# 서비스 2개(:8849 숏템메이커 / :8090 스탁브레인) + 워커 N개 + 타이머 5개 +
# 크론 16줄 + 아파치(80/443, Let's Encrypt 인증서 2장)다. 하나만 빠져도 조용히 죽는다.
#
# 쓰는 법:
#   bash deploy/verify_server.sh            # 사람이 읽는 점검표
#   bash deploy/verify_server.sh > before.txt   # 증설 전에 떠두고
#   bash deploy/verify_server.sh > after.txt    # 증설 후 diff before.txt after.txt
#
# ⚠️ 이 스크립트는 아무것도 고치지 않는다. 읽기만 한다.

set -u
ok=0; bad=0
say() { printf '%-42s %s\n' "$1" "$2"; }
chk() {  # chk "이름" "명령"  → 명령이 0이면 OK
  if eval "$2" >/dev/null 2>&1; then say "$1" "OK"; ok=$((ok+1));
  else say "$1" "❌ 실패"; bad=$((bad+1)); fi
}

echo "=== 서버 점검 $(date '+%F %T %Z') ==="
echo "호스트 $(hostname) · 공인IP $(curl -s --max-time 5 https://checkip.amazonaws.com || echo '(확인불가)')"
echo

echo "--- 하드웨어 (증설 후 여기가 바뀌어야 한다)"
say "vCPU" "$(nproc)"
say "메모리" "$(free -g | awk '/^Mem:/{printf "%sGB", $2}')"
say "디스크" "$(df -h / | awk 'NR==2{printf "%s 사용 / %s 여유 (%s)", $3, $4, $5}')"
say "부하(1·5·15분)" "$(uptime | sed 's/.*average: //')"
echo

echo "--- 서비스"
for u in shopping-shorts stockbrain stockbrain-dash apache2; do
  chk "$u 실행중" "systemctl is-active --quiet $u"
done
echo

echo "--- 워커 (동시 렌더 수 = 살아있는 워커 수)"
live=0
for i in $(seq 1 12); do
  if systemctl is-active --quiet "shopping-shorts-worker@$i" 2>/dev/null; then
    live=$((live+1))
    systemctl is-enabled --quiet "shopping-shorts-worker@$i" 2>/dev/null \
      || say "worker@$i" "⚠️ 실행중이나 부팅시 자동시작 아님"
  fi
done
say "살아있는 워커" "$live 개"
[ "$live" -ge 1 ] && ok=$((ok+1)) || { say "워커" "❌ 하나도 없음"; bad=$((bad+1)); }
echo

echo "--- 응답 (실제로 페이지가 뜨는가)"
chk "숏템메이커 :8849" "[ \"\$(curl -s -o /dev/null -w %{http_code} --max-time 10 http://127.0.0.1:8849/)\" = 200 ]"
chk "스탁브레인 :8090" "[ \"\$(curl -s -o /dev/null -w %{http_code} --max-time 10 http://127.0.0.1:8090/)\" != 000 ]"
chk "HTTPS shoppingshorts" "[ \"\$(curl -s -o /dev/null -w %{http_code} --max-time 15 https://shoppingshorts.duckdns.org/)\" != 000 ]"
chk "HTTPS stockbrain1" "[ \"\$(curl -s -o /dev/null -w %{http_code} --max-time 15 https://stockbrain1.duckdns.org/)\" != 000 ]"
echo

echo "--- 자동 작업"
say "크론 줄 수" "$(crontab -l 2>/dev/null | grep -vc '^\s*#' )"
say "활성 타이머" "$(systemctl list-timers --no-legend 2>/dev/null | grep -c shopping-shorts)"
chk "자동배포 크론 존재" "crontab -l 2>/dev/null | grep -q auto_deploy.sh"
echo

echo "--- 데이터·비밀 (스냅샷에 따라오지 않으면 서비스가 통째로 죽는다)"
chk "DB 존재" "[ -s /home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db ]"
chk "서비스 env" "[ -s /etc/shopping-shorts.env ]"
chk "프로젝트 .env(API키)" "[ -s /home/ubuntu/lotto-stock-wiki/.env ]"
chk "인증서 shoppingshorts" "sudo test -d /etc/letsencrypt/live/shoppingshorts.duckdns.org"
chk "인증서 stockbrain1" "sudo test -d /etc/letsencrypt/live/stockbrain1.duckdns.org"
say "DB 크기" "$(du -h /home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db 2>/dev/null | cut -f1)"
say "작업 데이터" "$(du -sh /home/ubuntu/lotto-stock-wiki/shopping_shorts/data 2>/dev/null | cut -f1)"
echo

echo "--- git (새 서버가 최신 코드인가)"
cd /home/ubuntu/lotto-stock-wiki 2>/dev/null && {
  say "브랜치" "$(git branch --show-current)"
  say "HEAD" "$(git log --oneline -1)"
  # ★배포(pull --ff-only)를 막는 건 **추적 중인 파일의 변경**뿐이다.
  #   untracked(??)는 서버가 만든 산출물(out/·backups/)이라 정상이고 pull을 막지 않는다
  #   — 실측 2026-08-22: untracked 5,768건이 쌓여 있었지만 배포는 멀쩡히 돌고 있었다.
  #   둘을 뭉뚱그리면 멀쩡한 서버를 "배포 막힘"으로 오진한다.
  tracked="$(git status --porcelain | grep -vc '^??')"
  untracked="$(git status --porcelain | grep -c '^??')"
  say "미추적 산출물" "$untracked 건 (정상 — 배포와 무관)"
  if [ "$tracked" = "0" ]; then
    say "워킹트리(추적분)" "깨끗함"
  else
    say "워킹트리(추적분)" "❌ 변경 $tracked 건 — 자동배포가 pull 실패로 멈춘다"
    bad=$((bad+1))
  fi
}
echo

echo "=== 요약: 통과 $ok · 실패 $bad ==="
[ "$bad" -eq 0 ] || echo "❌ 실패 항목을 먼저 해결하라 — 위 목록에서 '실패'로 찍힌 줄."
exit 0
