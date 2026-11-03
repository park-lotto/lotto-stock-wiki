# -*- coding: utf-8 -*-
"""우리 채널 통계 수집 — 관제 281. ★판단 주인: 지표를 모아 DB 에 쌓는 일은 여기 collect() 한 곳.
화면·분석은 DB 만 읽는다(같은 숫자를 두 곳에서 따로 부르지 않는다 — 0순위-B).

  py -m channel_stats.collect [--db 경로]      # 매시간 1회(작업 스케줄러/크론)

Buffer: 계정 키마다 채널(유튜브·틱톡) → sent 게시물 전부 → metrics 스냅샷 1행씩.
장부(~/.claude/buffer_post_ledger.json): post_id → 드라이브 폴더·파일·내용 지문(어떤 영상인지 이어 준다).
"""
import argparse, datetime as dt, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from shopping_shorts import buffer_api  # noqa: E402
from channel_stats import youtube_public  # noqa: E402
ENV = os.environ.get("CHSTATS_ENV", os.path.join(ROOT, ".env"))

KEYS = os.environ.get("CHSTATS_BUFFER_KEYS", os.path.expanduser("~/.claude/buffer_keys.json"))
LEDGER = os.environ.get("CHSTATS_LEDGER", os.path.expanduser("~/.claude/buffer_post_ledger.json"))
DB = os.environ.get("CHSTATS_DB", os.path.join(ROOT, "channel_stats", "data", "stats.db"))
KST = dt.timezone(dt.timedelta(hours=9))
METRICS = ("views", "reactions", "comments", "shares", "engagementRate", "reach",
           "totalTimeWatched", "averageTimeWatched")

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels(channel_id TEXT PRIMARY KEY, account TEXT, service TEXT, name TEXT, link TEXT);
CREATE TABLE IF NOT EXISTS posts(post_id TEXT PRIMARY KEY, channel_id TEXT, account TEXT, service TEXT,
  text TEXT, title TEXT, sent_at TEXT, due_at TEXT, link TEXT, file TEXT, fp TEXT);
CREATE TABLE IF NOT EXISTS snaps(post_id TEXT, at TEXT, metrics_at TEXT, views REAL, reactions REAL, comments REAL,
  shares REAL, engagementRate REAL, reach REAL, totalTimeWatched REAL, averageTimeWatched REAL,
  PRIMARY KEY(post_id, metrics_at));
CREATE TABLE IF NOT EXISTS yt_channels(channel_id TEXT PRIMARY KEY, account TEXT, title TEXT, thumb TEXT);
CREATE TABLE IF NOT EXISTS yt_channel_snaps(channel_id TEXT, at TEXT, subs INTEGER, views INTEGER, videos INTEGER,
  PRIMARY KEY(channel_id, at));
CREATE TABLE IF NOT EXISTS yt_videos(video_id TEXT PRIMARY KEY, channel_id TEXT, account TEXT, title TEXT, published TEXT,
  duration INTEGER, thumb TEXT);
CREATE TABLE IF NOT EXISTS yt_snaps(video_id TEXT, at TEXT, views INTEGER, likes INTEGER, comments INTEGER,
  PRIMARY KEY(video_id, at));
CREATE TABLE IF NOT EXISTS runs(at TEXT PRIMARY KEY, posts INTEGER, snaps_new INTEGER, errors TEXT);
"""
_QCH = "query($o:OrganizationId!){ channels(input:{organizationId:$o}){ id service name serviceId externalLink } }"
_Q = """query($o:OrganizationId!,$c:[ChannelId!],$a:String){ posts(first:100, after:$a,
  input:{organizationId:$o, filter:{channelIds:$c}}){ pageInfo{hasNextPage endCursor}
  edges{ node{ id status text dueAt sentAt externalLink metricsUpdatedAt metrics{ type value }
  metadata{ ... on YoutubePostMetadata { title } } } } } }"""


def _load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return d


def _sent_posts(key, org, cid):
    cur = None
    while True:
        r = buffer_api._call(key, _Q, {"o": org, "c": [cid], "a": cur})["posts"]
        for e in r["edges"]:
            if e["node"]["status"] == "sent":
                yield e["node"]
        if not r["pageInfo"]["hasNextPage"]:
            return
        cur = r["pageInfo"]["endCursor"]


def collect(db_path=DB, keys=None, ledger=None, yt_keys=None, log=print):
    keys = keys if keys is not None else _load(KEYS, {})
    led = {r["post_id"]: r for r in (ledger if ledger is not None else _load(LEDGER, [])) if r.get("post_id")}
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    now = dt.datetime.now(KST).isoformat(timespec="seconds")
    n_posts = n_new = 0
    errors = []
    for account, key in keys.items():
        try:
            org = buffer_api.organizations(key)[0]
            chs = buffer_api._call(key, _QCH, {"o": org})["channels"]
        except Exception as e:  # noqa: BLE001 — 한 계정이 죽어도 나머지는 모은다. 실패는 runs.errors 에 남는다
            errors.append(f"{account}: {e}")
            continue
        for c in chs:
            if c.get("service") not in ("youtube", "tiktok"):
                continue
            con.execute("INSERT OR REPLACE INTO channels VALUES(?,?,?,?,?)",
                        (c["id"], account, c["service"], c.get("name"), c.get("serviceId")))
            try:
                posts = list(_sent_posts(key, org, c["id"]))
            except Exception as e:  # noqa: BLE001
                errors.append(f"{account}/{c['service']}: {e}")
                continue
            for p in posts:
                lr = led.get(p["id"], {})
                text = p.get("text") or ""
                con.execute("INSERT OR REPLACE INTO posts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (p["id"], c["id"], account, c["service"], text, text.split("\n", 1)[0].strip(),
                             p.get("sentAt"), p.get("dueAt"), p.get("externalLink"), lr.get("file"), lr.get("fp")))
                n_posts += 1
                m = {x["type"]: x["value"] for x in (p.get("metrics") or [])}
                if not m:
                    continue
                cur = con.execute("INSERT OR IGNORE INTO snaps VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                  (p["id"], now, p.get("metricsUpdatedAt") or now, *[m.get(k) for k in METRICS]))
                n_new += cur.rowcount
    yt_ids = {cid: acc for cid, acc in con.execute(
        "SELECT link, account FROM channels WHERE service='youtube'")}   # link 칸 = 서비스 채널 id(UC…)
    n_yt = _collect_youtube(con, now, yt_ids, errors, yt_keys)
    con.execute("INSERT INTO runs VALUES(?,?,?,?)", (now, n_posts, n_new, json.dumps(errors, ensure_ascii=False)))
    con.commit()
    con.close()
    log(f"[channel_stats] Buffer 게시물 {n_posts} · 새 스냅샷 {n_new} · 유튜브 영상 {n_yt} · 오류 {len(errors)}")
    for e in errors:
        log("   ⚠️ " + e)
    return {"posts": n_posts, "snaps_new": n_new, "errors": errors}


def _collect_youtube(con, now, yt_ids, errors, keys=None):
    """유튜브 공개 데이터 — 채널 구독자·업로드 전부·영상별 조회/좋아요/댓글 스냅샷(매 실행 1행).
    키: 넘겨받은 것 → .env(PC) → shopping_shorts.config.YOUTUBE_API_KEYS(서버 환경) 순."""
    keys = keys or youtube_public.api_keys(ENV)
    if not keys:
        try:
            from shopping_shorts import config as _cfg
            keys = list(getattr(_cfg, "YOUTUBE_API_KEYS", []) or [])
        except Exception as e:  # noqa: BLE001 — 키를 못 찾은 사실은 아래 errors 로 화면까지 간다
            errors.append(f"유튜브 키 풀 읽기 실패: {e}")
    if not keys:
        errors.append("유튜브 API 키 없음(.env YOUTUBE_API_KEY*)")
        return 0
    yt, n = youtube_public.YT(keys), 0
    for cid, account in yt_ids.items():
        try:
            ch = yt.channel(cid)
            con.execute("INSERT OR REPLACE INTO yt_channels VALUES(?,?,?,?)", (cid, account, ch["title"], ch["thumb"]))
            con.execute("INSERT OR REPLACE INTO yt_channel_snaps VALUES(?,?,?,?,?)", (cid, now, ch["subs"], ch["views"], ch["videos"]))
            if not ch["videos"]:          # 영상 0 채널은 업로드 목록이 404 다(실측) — 건너뛴다
                continue
            for v in yt.videos(yt.upload_ids(ch["uploads"])):
                con.execute("INSERT OR REPLACE INTO yt_videos VALUES(?,?,?,?,?,?,?)",
                            (v["id"], cid, account, v["title"], v["published"], v["duration"], v["thumb"]))
                con.execute("INSERT OR REPLACE INTO yt_snaps VALUES(?,?,?,?,?)", (v["id"], now, v["views"], v["likes"], v["comments"]))
                n += 1
        except Exception as e:  # noqa: BLE001 — 한 채널 실패가 나머지를 막지 않게. runs.errors 로 보인다
            errors.append(f"유튜브 {account}: {e}")
    return n


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    collect(ap.parse_args().db)
