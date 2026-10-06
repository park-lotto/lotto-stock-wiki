# -*- coding: utf-8 -*-
"""대본 줄별 장면 검색어 → 플랫폼 검색 결과 수 측정(모델 호출 없음). 서버 /tmp/banggu_pkg 에서:
  python3 scene_search_probe.py beats.txt   (줄: 소재|검색어)
유튜브 = youtube_search.search(YouTube Data API, 쿼터 내 무료). 틱톡·인스타 등은 유료 백엔드가 섞여 있어 이번엔 안 부른다."""
import sys
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts import youtube_search

for line in open(sys.argv[1], encoding="utf-8"):
    if "|" not in line:
        continue
    topic, kw = [x.strip() for x in line.split("|", 1)]
    try:
        rows = youtube_search.search(kw, max_results=15, duration="short", language="ko") or []
    except Exception as e:      # noqa: BLE001
        print("%s | %s | 실패 %r" % (topic, kw, e)); continue
    print("%s | %s | 쇼츠 %d건 | %s" % (topic, kw, len(rows), " / ".join((r.get("title") or "")[:28] for r in rows[:3])), flush=True)
