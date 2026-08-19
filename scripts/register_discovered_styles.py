# -*- coding: utf-8 -*-
"""유튜브 스타일 3종 채널을 platform_seeds에 등록 + channel_styles에 스타일 못 박기.

  썰쇼핑     70개  (/tmp/harvest_state.json — 오용형 루프 결과 + 살림킹왕짱)
  연예인결합  30개  (/tmp/style_candidates.json)
  레시피쇼핑  30개  (/tmp/style_candidates.json)

★kind는 반드시 'account' — 'ko'(언어코드)로 넣으면 kind=='account' 필터에 안 걸려
  수집이 조용히 0건이 된다(memory: 새플랫폼탭_조용한0건).
★채널명이 아니라 **채널ID**로 스타일을 못 박는다(채널명은 바뀐다).
"""
import sqlite3, json, datetime, os

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
db = sqlite3.connect(DB)

# channel_styles 테이블(없으면 만든다) — channel_categories와 같은 모양
db.execute("""CREATE TABLE IF NOT EXISTS channel_styles (
                 channel_id TEXT PRIMARY KEY,
                 title      TEXT,
                 style      TEXT,
                 set_at     TEXT)""")

buckets = {}
if os.path.exists("/tmp/harvest_state.json"):
    st = json.load(open("/tmp/harvest_state.json"))
    v = dict(st.get("verified") or {})
    v.setdefault("UCBFu04us6bv9OFcwrJDXdMg",
                 {"title": "살림킹왕짱", "subs": 14600, "misuse": 20})
    buckets["썰쇼핑"] = [{"cid": c, "title": i["title"], "subs": i.get("subs", 0),
                        "score": i.get("misuse", 0)} for c, i in v.items()]
if os.path.exists("/tmp/style_candidates.json"):
    sc = json.load(open("/tmp/style_candidates.json"))
    for style, rows in sc.items():
        buckets[style] = [{"cid": r["cid"], "title": r["title"],
                           "subs": r.get("subs", 0), "score": r.get("score", 0)} for r in rows]

have = set()
for (val,) in db.execute("select value from platform_seeds where platform='youtube'").fetchall():
    if "channel/" in val:
        have.add(val.rstrip("/").split("channel/")[-1])

now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
tot_new = 0
for style, rows in buckets.items():
    rows.sort(key=lambda x: -x["score"])
    new = 0
    for r in rows:
        cid = r["cid"]
        if cid not in have:
            db.execute("insert into platform_seeds(platform,kind,value,added_at) values(?,?,?,?)",
                       ("youtube", "account", "https://www.youtube.com/channel/" + cid, now))
            have.add(cid); new += 1
        db.execute("INSERT INTO channel_styles(channel_id,title,style,set_at) VALUES(?,?,?,?) "
                   "ON CONFLICT(channel_id) DO UPDATE SET title=excluded.title, "
                   "style=excluded.style, set_at=excluded.set_at",
                   (cid, r["title"], style, now))
    tot_new += new
    print("[%s] 채널 %d개 (신규 시드 %d)" % (style, len(rows), new))
    for r in rows[:5]:
        print("     %-22s 구독 %9s  점수 %2d" % (r["title"][:22], format(r["subs"], ","), r["score"]))
db.commit()

print()
print("신규 시드 등록: %d개" % tot_new)
tot = db.execute("select count(*) from platform_seeds where platform='youtube' and kind='account'").fetchone()[0]
bad = db.execute("select count(*) from platform_seeds where platform='youtube' and kind!='account'").fetchone()[0]
print("유튜브 account 시드 총: %d (kind 이상치 %d)" % (tot, bad))
print("channel_styles 분포:", db.execute(
    "select style,count(*) from channel_styles group by style").fetchall())
