#!/bin/bash
# 썰쇼핑·홈템·신기템 채널 발굴 루프 지킴이(2026-09-08).
# 왜: harvest_styles_forever.py는 8/19에 손으로 띄운 뒤 3주간 한 번도 안 돌았다
#     (크론·타이머 없음). 서버가 재시작되면 또 통째로 멈춘다.
#
# ★pgrep에 -x가 아니라 파이썬 실행파일 경로를 함께 본다. 그냥 -f 'harvest_styles_forever'로
#   찾으면 **이 문자열을 인자로 가진 아무 명령이나** 걸린다 — 실제로 같은 셸에서
#   pgrep을 함께 돌리자 자기 명령줄을 잡고 '이미 돌고 있다'로 오판해 재시작을 걸렀다.
#   그래서 python 프로세스만 세고, 자기 자신($$)과 부모는 제외한다.
RUNNING=$(pgrep -f 'python.*harvest_styles_forever' | grep -v "^$$$" | head -1)
[ -n "$RUNNING" ] && exit 0
cd /home/ubuntu/lotto-stock-wiki || exit 1
set -a; . /etc/shopping-shorts.env 2>/dev/null; set +a
echo "$(date '+%F %T') 발굴 루프가 멈춰 있어 다시 띄운다" >> /tmp/harvest_keepalive.log
nohup setsid /home/ubuntu/venv/bin/python -u scripts/harvest_styles_forever.py   >> /tmp/harvest_forever.out 2>&1 < /dev/null &
