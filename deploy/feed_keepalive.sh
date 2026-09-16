#!/bin/bash
# 피드 타기 발굴(harvest_by_feed.py) 지킴이 — 2026-09-09.
# 왜: 이 도구는 씨앗이 마르면 스스로 10분 쉬었다 이어가지만, 서버 재시작·OOM으로
#     죽으면 아무도 안 살린다. harvest_styles_forever가 8/19~9/8 3주간 죽어 있던
#     것과 똑같은 사고가 난다.
#
# ★pgrep 패턴에 'python.*'을 반드시 붙인다. 그냥 -f 'harvest_by_feed'로 찾으면
#   **그 문자열을 인자로 가진 아무 명령이나** 걸려(자기 명령줄 포함) '이미 돌고
#   있다'로 오판하고 조용히 exit 0 한다(2026-09-09 실사고, 로그도 안 남았다).
RUNNING=$(pgrep -f 'python.*harvest_by_feed' | grep -v "^$$$" | head -1)
[ -n "$RUNNING" ] && exit 0
cd /home/ubuntu/lotto-stock-wiki || exit 1
set -a; . /etc/shopping-shorts.env 2>/dev/null; set +a
echo "$(date '+%F %T') 피드 발굴이 멈춰 있어 다시 띄운다" >> /tmp/feed_keepalive.log
nohup setsid /home/ubuntu/venv/bin/python -u scripts/harvest_by_feed.py \
  >> /tmp/harvest_feed.out 2>&1 < /dev/null &
