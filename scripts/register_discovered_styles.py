# -*- coding: utf-8 -*-
"""발굴한 유튜브 채널을 **수집 대상으로 등록**한다(platform_seeds + channel_styles).

    썰쇼핑 / 연예인결합 / 레시피쇼핑

★2026-08-19 수정: 옛 스크립트는 `/tmp/harvest_state.json`·`/tmp/style_candidates.json`
  만 읽었다. 그런데 지금 도는 발굴 루프(`scripts/harvest_styles_forever.py`)는
  **`/tmp/style_state.json`**에 쌓는다 — 그대로 두면 최신 결과(썰쇼핑 107 등)가
  등록에서 통째로 빠진다. 세 소스를 **cid 기준 합집합**으로 읽는다.

★kind는 반드시 'account' — 'ko'(언어코드)로 넣으면 kind=='account' 필터에 안 걸려
  수집이 조용히 0건이 된다(memory: 새플랫폼탭_조용한0건).
★채널명이 아니라 **채널ID**로 스타일을 못 박는다(채널명은 바뀐다).

실행: python3 scripts/register_discovered_styles.py [--apply]
      (--apply 없이는 무엇이 등록될지 세어서 보여주기만 한다)
"""
import sqlite3, json, datetime, os, sys

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
try:
    from shopping_shorts.app import DB_PATH as DB      # 라이브가 쓰는 DB를 그대로
except Exception:                                      # noqa: BLE001
    DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"

APPLY = "--apply" in sys.argv
db = sqlite3.connect(DB)
db.execute("""CREATE TABLE IF NOT EXISTS channel_styles (
                 channel_id TEXT PRIMARY KEY,
                 title      TEXT,
                 style      TEXT,
                 set_at     TEXT)""")

# ── 소스 세 곳을 합친다 ───────────────────────────────────────────────────
buckets = {}          # style -> {cid: {title, subs, score}}


def _add(style, cid, title, subs, score):
    b = buckets.setdefault(style, {})
    old = b.get(cid)
    # 같은 채널이 여러 소스에 있으면 **점수가 높은 쪽**을 남긴다(정보가 더 있는 쪽).
    if not old or (score or 0) > (old.get("score") or 0):
        b[cid] = {"title": title or (old or {}).get("title") or "", "subs": subs or 0,
                  "score": score or 0}


# 1) 지금 도는 발굴 루프의 상태파일 (정본)
if os.path.exists("/tmp/style_state.json"):
    st = json.load(open("/tmp/style_state.json"))
    for style, rows in (st.get("styles") or {}).items():
        for cid, i in rows.items():
            _add(style, cid, i.get("title"), i.get("subs"), i.get("score"))

# 2) 옛 오용형 루프 결과
if os.path.exists("/tmp/harvest_state.json"):
    st = json.load(open("/tmp/harvest_state.json"))
    for cid, i in (st.get("verified") or {}).items():
        _add("썰쇼핑", cid, i.get("title"), i.get("subs"), i.get("misuse"))
# 살림킹왕짱 — 이 장르의 기준 채널이라 어느 소스에도 안 들어 있어도 반드시 넣는다.
_add("썰쇼핑", "UCBFu04us6bv9OFcwrJDXdMg", "살림킹왕짱", 14600, 20)

# 3) 옛 연예인결합·레시피쇼핑 후보
if os.path.exists("/tmp/style_candidates.json"):
    for style, rows in json.load(open("/tmp/style_candidates.json")).items():
        for r in rows:
            _add(style, r["cid"], r.get("title"), r.get("subs"), r.get("score"))

# ── 이미 등록된 것 ────────────────────────────────────────────────────────
have = set()
for (val,) in db.execute("select value from platform_seeds where platform='youtube'"):
    if "channel/" in val:
        have.add(val.rstrip("/").split("channel/")[-1])

now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
tot_new = 0
for style, rows in buckets.items():
    items = sorted(rows.items(), key=lambda kv: -(kv[1].get("score") or 0))
    new = [c for c, _ in items if c not in have]
    tot_new += len(new)
    print("[%s] 채널 %d개 · 신규 시드 %d개" % (style, len(items), len(new)))
    for cid, r in items[:5]:
        print("     %-22s 구독 %9s  점수 %s%s"
              % ((r["title"] or "")[:22], format(r.get("subs") or 0, ","),
                 r.get("score"), "" if cid in have else "  ← 신규"))
    if not APPLY:
        continue
    for cid, r in items:
        if cid not in have:
            db.execute("insert into platform_seeds(platform,kind,value,added_at) values(?,?,?,?)",
                       ("youtube", "account", "https://www.youtube.com/channel/" + cid, now))
            have.add(cid)
        db.execute("INSERT INTO channel_styles(channel_id,title,style,set_at) VALUES(?,?,?,?) "
                   "ON CONFLICT(channel_id) DO UPDATE SET title=excluded.title, "
                   "style=excluded.style, set_at=excluded.set_at",
                   (cid, r["title"], style, now))

if APPLY:
    db.commit()
print("\n신규 시드 %s: %d개" % ("등록됨" if APPLY else "예정", tot_new))
tot = db.execute("select count(*) from platform_seeds where platform='youtube' and kind='account'").fetchone()[0]
bad = db.execute("select count(*) from platform_seeds where platform='youtube' and kind!='account'").fetchone()[0]
print("유튜브 account 시드 총: %d (kind 이상치 %d ← 0이어야 한다)" % (tot, bad))
print("channel_styles 분포:", db.execute(
    "select style,count(*) from channel_styles group by style").fetchall())
