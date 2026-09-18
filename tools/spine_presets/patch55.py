# -*- coding: utf-8 -*-
"""스파인 55의 문장틀을 **칸마다 5개**로 늘린다 (2026-09-18 사장님 "1번 대본스타일에 5개").

왜: 틀이 3개뿐이면 모델이 빈칸을 자기 관성으로 채워 한 어미를 복제한다
    (실측: 68번 `미쳤다는 거` 3줄 연속, 67번 `~함` 5줄). 틀을 늘려 **데이터가 어미를 정하게** 한다.
    사장님: "5~10개 어미·연결어를 조금씩 바꿔 그 안에서 랜덤으로 고르면 반려고 뭐고 없다."

★어미·연결어는 지어내지 않고 **히트작 200편 자막 실측**에서 가져왔다:
    연결어  근데 진짜 45 · 진짜 미친 15 · 하지만 진짜 12 · 근데 진짜는 5 · 심지어 …
    more 어미  ~다는 거(버렸다는·없다는·사용했다는) · ~해 버림(완성해·지워) · ~함(시작함·막아줌) · ~거임 · ~는데
    twist 어미 ~다는 거(버린다는) · ~해 버림(만들어·환생해·탄생시켜) · 따로 있음/있어 · ~있었음/있었어
  꼬리가 매우 길다(대부분 1회) = 원본은 매번 다르게 쓴다. 그래서 5개를 서로 다른 어미로 채운다.

적용 대상은 **55번 하나**(근거 52편). 괜찮으면 나머지에 퍼뜨린다 — 8개를 한 번에 바꾸면 되돌릴 게 많다.
"""
import json
import sqlite3
import sys

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
SPINE_ID = 55
APPLY = "--apply" in sys.argv

# 칸 → 문장틀 5개. 연결어·어미가 **서로 겹치지 않게** 짝지었다.
NEW = {
    "solve": [
        "이건 {효능}다는 거",
        "근데 이건 {효능}더라",
        "그런데 이건 {효능}해 버림",
        "이게 {효능}는 거임",
        "알고 보니 {효능}했음",
    ],
    "more": [
        "심지어 {효능2}다는 거",
        "게다가 {효능2}해 버림",
        "거기다 {효능2}다고",
        "무엇보다 {효능2}는 거임",
        "특히 {효능2}더라",
    ],
    "twist": [
        "근데 진짜 충격적인 포인트는 {효능3}다는 거",
        "더 대박인 건 {효능3}해 버림",
        "근데 진짜는 여기서부터인데 {효능3}",
        "하지만 진짜 미친 건 {효능3}라는 거",
        "진짜 소름 돋는 건 {효능3}였음",
    ],
}

con = sqlite3.connect(DB)
row = con.execute("select name, templates_json from spine where id=?", (SPINE_ID,)).fetchone()
if not row:
    sys.exit("스파인 %s 없음" % SPINE_ID)
name, tj = row
tpl = json.loads(tj or "{}")

print("[%s] %s" % (SPINE_ID, name))
for slot, arr in NEW.items():
    old = tpl.get(slot) or []
    print("\n  %s : %d개 → %d개" % (slot, len(old), len(arr)))
    print("     전:")
    for t in old:
        print("        -", t)
    print("     후:")
    for t in arr:
        print("        -", t)
    tpl[slot] = list(arr)

if APPLY:
    con.execute("update spine set templates_json=?, updated_at=datetime('now') where id=?",
                (json.dumps(tpl, ensure_ascii=False), SPINE_ID))
    con.commit()
    print("\n적용 완료 (백업: /tmp/spine_templates_backup.json)")
else:
    print("\n(미리보기 — 적용하려면 --apply)")
