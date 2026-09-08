#!/bin/bash
# 썰쇼핑·신기템 채널 발굴 루프 지킴이(2026-09-08).
# 왜: harvest_styles_forever.py는 8/19에 손으로 띄운 뒤 3주간 한 번도 안 돌았다
#     (크론·타이머 없음). 서버가 재시작되면 또 통째로 멈춘다.
# 이미 돌고 있으면 아무 것도 안 한다 — 중복 실행 금지.
pgrep -f 'harvest_styles_forever' >/dev/null && exit 0
cd /home/ubuntu/lotto-stock-wiki || exit 1
set -a; . /etc/shopping-shorts.env 2>/dev/null; set +a
echo "$(date '+%F %T') 발굴 루프가 멈춰 있어 다시 띄운다" >> /tmp/harvest_keepalive.log
setsid nohup /home/ubuntu/venv/bin/python -u scripts/harvest_styles_forever.py   >> /tmp/harvest_forever.out 2>&1 < /dev/null &
