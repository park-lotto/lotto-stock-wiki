# -*- coding: utf-8 -*-
"""유튜브 애널리틱스(채널 허용 필요) — 관제 281 2단계. 시청시간·평균 시청 비율·구독 증감·유입 경로·이탈 곡선·일별 조회.
★판단 주인: '허용 받은 채널에서 무엇을 언제 가져오나'는 여기 한 곳. 화면은 analyze 가 엮은 data.json 만 본다.

구글 앱: 클라우드 프로젝트 shortem-chstats-281(parklotto12) · 프로덕션 게시(테스트 상태면 refresh token 7일 만료).
파일(서버 shopping_shorts/data/channel_stats/, git 밖): oauth_client.json(client_id·secret·redirect_uri) · yt_tokens.json(채널id → refresh_token)
"""
import datetime as dt, json, os, secrets, time, urllib.error, urllib.parse, urllib.request

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
DATA_API = "https://www.googleapis.com/youtube/v3/"
REPORTS = "https://youtubeanalytics.googleapis.com/v2/reports"
SCOPES = "https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/youtube.readonly"
EVERY_H = 6            # 애널리틱스 숫자는 하루 단위로 갱신된다 — 매시간 부를 이유가 없다
DETAIL_DAYS = 30       # 이 기간 안에 올린 영상만 일별·이탈 곡선까지 가져온다(호출 수를 묶는다)


def _read(d, name, default):
    try:
        with open(os.path.join(d, name), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _write(d, name, obj):
    p = os.path.join(d, name)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
    os.chmod(p, 0o600)


def _post(url, form):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _get(url, token, **q):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(q), headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.read().decode('utf-8', 'replace')[:300]}") from None


# ── 연결(허용) ─────────────────────────────────────────────
def start_url(d, hint=""):
    c = _read(d, "oauth_client.json", None)
    if not c:
        raise RuntimeError("oauth_client.json 이 없다")
    state = secrets.token_urlsafe(24)
    pend = {k: v for k, v in _read(d, "oauth_pending.json", {}).items() if time.time() - v < 900}
    pend[state] = time.time()
    _write(d, "oauth_pending.json", pend)
    q = {"client_id": c["client_id"], "redirect_uri": c["redirect_uri"], "response_type": "code", "scope": SCOPES,
         "access_type": "offline", "prompt": "consent select_account", "state": state, "include_granted_scopes": "true"}
    if hint:
        q["login_hint"] = hint
    return AUTH + "?" + urllib.parse.urlencode(q)


def finish(d, code, state):
    """콜백: 코드 → refresh token → 어느 채널인지(mine=true) 확인해 채널 id 로 저장. 돌려주는 값 = 채널 제목."""
    pend = _read(d, "oauth_pending.json", {})
    if state not in pend or time.time() - pend[state] > 900:
        raise RuntimeError("연결 요청이 만료됐거나 위조됐다 — 다시 '연결하기'를 눌러 주세요")
    pend.pop(state, None)
    _write(d, "oauth_pending.json", pend)
    c = _read(d, "oauth_client.json", None)
    tok = _post(TOKEN, {"code": code, "client_id": c["client_id"], "client_secret": c["client_secret"],
                        "redirect_uri": c["redirect_uri"], "grant_type": "authorization_code"})
    if not tok.get("refresh_token"):
        raise RuntimeError("구글이 refresh token 을 주지 않았다 — 다시 연결해 주세요")
    ch = _get(DATA_API + "channels", tok["access_token"], part="snippet", mine="true").get("items") or []
    if not ch:
        raise RuntimeError("이 구글 계정에 유튜브 채널이 없다 — 채널을 가진 계정으로 로그인해 주세요")
    toks = _read(d, "yt_tokens.json", {})
    toks[ch[0]["id"]] = {"refresh_token": tok["refresh_token"], "title": ch[0]["snippet"]["title"],
                         "connected_at": dt.datetime.now().isoformat(timespec="seconds")}
    _write(d, "yt_tokens.json", toks)
    return ch[0]["snippet"]["title"]


def connected(d):
    return {cid: {"title": v.get("title"), "connected_at": v.get("connected_at"), "error": v.get("error")}
            for cid, v in _read(d, "yt_tokens.json", {}).items()}


def _access(d, cid):
    c = _read(d, "oauth_client.json", None)
    toks = _read(d, "yt_tokens.json", {})
    try:
        r = _post(TOKEN, {"refresh_token": toks[cid]["refresh_token"], "client_id": c["client_id"],
                          "client_secret": c["client_secret"], "grant_type": "refresh_token"})
        if toks[cid].pop("error", None):
            _write(d, "yt_tokens.json", toks)
        return r["access_token"]
    except urllib.error.HTTPError as e:       # 허용 취소·만료 — 화면에 '다시 연결'로 띄운다
        toks[cid]["error"] = f"토큰 갱신 실패 {e.code}"
        _write(d, "yt_tokens.json", toks)
        raise RuntimeError(toks[cid]["error"]) from None


# ── 수집 ──────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS ya_ch_daily(channel_id TEXT, day TEXT, views INTEGER, watch_min REAL, avg_dur REAL, avg_pct REAL,
  subs_gained INTEGER, subs_lost INTEGER, likes INTEGER, shares INTEGER, PRIMARY KEY(channel_id, day));
CREATE TABLE IF NOT EXISTS ya_video(video_id TEXT PRIMARY KEY, channel_id TEXT, views INTEGER, watch_min REAL, avg_dur REAL,
  avg_pct REAL, subs_gained INTEGER, likes INTEGER, shares INTEGER, at TEXT);
CREATE TABLE IF NOT EXISTS ya_video_daily(video_id TEXT, day TEXT, views INTEGER, watch_min REAL, PRIMARY KEY(video_id, day));
CREATE TABLE IF NOT EXISTS ya_retention(video_id TEXT PRIMARY KEY, curve TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS ya_traffic(channel_id TEXT, source TEXT, views INTEGER, watch_min REAL, at TEXT, PRIMARY KEY(channel_id, source));
CREATE TABLE IF NOT EXISTS ya_runs(at TEXT PRIMARY KEY, channels INTEGER, errors TEXT);
"""


def _rows(rep):
    heads = [h["name"] for h in rep.get("columnHeaders", [])]
    return [dict(zip(heads, r)) for r in rep.get("rows") or []]


def due(con):
    r = con.execute("SELECT max(at) FROM ya_runs").fetchone()
    return not r[0] or (dt.datetime.now() - dt.datetime.fromisoformat(r[0])).total_seconds() > EVERY_H * 3600


def collect(d, con, recent_videos, log=print, force=False):
    """허용된 채널마다 일별·영상별·이탈·유입. recent_videos = {채널id: [(video_id, 게시일 YYYY-MM-DD), …]}."""
    con.executescript(SCHEMA)
    if not force and not due(con):
        return {"skipped": True}
    toks = _read(d, "yt_tokens.json", {})
    today = dt.date.today()
    start90, start28 = (today - dt.timedelta(days=90)).isoformat(), (today - dt.timedelta(days=28)).isoformat()
    now = dt.datetime.now().isoformat(timespec="seconds")
    errors = []
    for cid in toks:
        try:
            at = _access(d, cid)
            q = lambda **k: _rows(_get(REPORTS, at, ids="channel==MINE", endDate=today.isoformat(), **k))  # noqa: E731
            for r in q(startDate=start90, dimensions="day", sort="day",
                       metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost,likes,shares"):
                con.execute("INSERT OR REPLACE INTO ya_ch_daily VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (cid, r["day"], r["views"], r["estimatedMinutesWatched"], r["averageViewDuration"], r["averageViewPercentage"],
                             r["subscribersGained"], r["subscribersLost"], r["likes"], r["shares"]))
            for r in q(startDate="2020-01-01", dimensions="video", sort="-views", maxResults=200,
                       metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,shares"):
                con.execute("INSERT OR REPLACE INTO ya_video VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (r["video"], cid, r["views"], r["estimatedMinutesWatched"], r["averageViewDuration"], r["averageViewPercentage"],
                             r["subscribersGained"], r["likes"], r["shares"], now))
            for r in q(startDate=start28, dimensions="insightTrafficSourceType", metrics="views,estimatedMinutesWatched", sort="-views"):
                con.execute("INSERT OR REPLACE INTO ya_traffic VALUES(?,?,?,?,?)",
                            (cid, r["insightTrafficSourceType"], r["views"], r["estimatedMinutesWatched"], now))
            for vid, pub in recent_videos.get(cid, []):
                if (today - dt.date.fromisoformat(pub)).days > DETAIL_DAYS:
                    continue
                for r in q(startDate=pub, dimensions="day", filters=f"video=={vid}", metrics="views,estimatedMinutesWatched", sort="day"):
                    con.execute("INSERT OR REPLACE INTO ya_video_daily VALUES(?,?,?,?)", (vid, r["day"], r["views"], r["estimatedMinutesWatched"]))
                try:
                    ret = q(startDate=pub, dimensions="elapsedVideoTimeRatio", filters=f"video=={vid}",
                            metrics="audienceWatchRatio,relativeRetentionPerformance")
                    if ret:
                        con.execute("INSERT OR REPLACE INTO ya_retention VALUES(?,?,?)",
                                    (vid, json.dumps([[r["elapsedVideoTimeRatio"], r["audienceWatchRatio"], r["relativeRetentionPerformance"]] for r in ret]), now))
                except RuntimeError as e:     # 조회 적은 영상은 이탈 곡선이 없다 — 채널 전체 실패로 치지 않는다
                    log(f"[yt_analytics] 이탈 곡선 없음 {vid}: {str(e)[:80]}")
            con.commit()
        except Exception as e:  # noqa: BLE001 — 한 채널 실패가 나머지를 막지 않는다. 화면 머리에 뜬다
            errors.append(f"{toks[cid].get('title', cid)}: {str(e)[:200]}")
    con.execute("INSERT INTO ya_runs VALUES(?,?,?)", (now, len(toks), json.dumps(errors, ensure_ascii=False)))
    con.commit()
    log(f"[yt_analytics] 채널 {len(toks)} · 오류 {len(errors)}")
    return {"channels": len(toks), "errors": errors}
