# 사용(서버): python3 add_ch.py <채널 URL|핸들> <썰쇼핑|홈템>  — 수집 등록 + 스타일표 + 탭 고정 + 전수조사
import sys, sqlite3, datetime, json
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki"); sys.path.insert(0, "/home/ubuntu/survey134")
from shopping_shorts.store import Store
from shopping_shorts.youtube_client import _resolve_channel, _first_ok, _CHANNELS_URL
import survey
DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
seed, tab = sys.argv[1], sys.argv[2]
cat = {"썰쇼핑": "제품정체형", "홈템": "홈템"}[tab]
import re, urllib.parse
m = re.search(r"(UC[\w-]{22})", seed)
if m:
    cid = m.group(1)
else:
    cid, _ = _resolve_channel(seed)
    if not cid and "@" in seed:      # 한글 핸들은 _resolve_channel 의 정규식(영문만)에 안 걸린다
        h = urllib.parse.unquote(seed.split("@", 1)[1]).split("/")[0].split("?")[0]
        dd, _ = _first_ok(_CHANNELS_URL, {"part": "id", "forHandle": "@" + h})
        cid = ((dd or {}).get("items") or [{}])[0].get("id")
if not cid: raise SystemExit("채널을 못 찾았다: " + seed)
d, _ = _first_ok(_CHANNELS_URL, {"part": "snippet,statistics", "id": cid})
it = (d or {}).get("items", [{}])[0]; title = it.get("snippet", {}).get("title", ""); subs = int(it.get("statistics", {}).get("subscriberCount") or 0)
st = Store(DB); now = datetime.datetime.now(datetime.timezone.utc).isoformat()
c0 = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
before = (c0.execute("SELECT style FROM channel_styles WHERE channel_id=?", (cid,)).fetchall(), c0.execute("SELECT category FROM channel_category_force WHERE username=?", (cid.lower(),)).fetchall())
st.add_seed("youtube", "account", "https://www.youtube.com/channel/" + cid)
with st._conn() as c:
    c.execute("INSERT INTO channel_styles(channel_id,title,style,set_at,subs) VALUES(?,?,?,?,?) "
              "ON CONFLICT(channel_id) DO UPDATE SET title=excluded.title, style=excluded.style, set_at=excluded.set_at, "
              "subs=MAX(IFNULL(channel_styles.subs,0), excluded.subs)", (cid, title, tab, now, subs))
st.set_channel_force(cid, cat)
import os
p = "/home/ubuntu/survey134/out/%s.json" % cid
if os.path.exists(p): os.remove(p)
r = survey.survey(cid, "/home/ubuntu/survey134/out")
c1 = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
print(json.dumps({"cid": cid, "title": title, "subs": subs, "before": before, "force": c1.execute("SELECT category FROM channel_category_force WHERE username=?", (cid.lower(),)).fetchall(),
                  "seed": c1.execute("SELECT COUNT(*) FROM platform_seeds WHERE value LIKE ?", ("%" + cid,)).fetchone()[0], "survey": r}, ensure_ascii=False))
