# -*- coding: utf-8 -*-
"""통계 분석 — DB(collect 가 쌓은 것) → 화면용 data.json 한 벌. ★판단 주인: '무엇이 잘됐나'의 기준(히트·분류·비교)은 여기 한 곳.
화면(web/index.html)은 이 JSON 을 그리기만 한다.

  py -m channel_stats.analyze [--db …] [--out …/data.json]

기준
- 히트 = 그 채널 중앙값의 2배 이상 조회(채널마다 체급이 달라 절대값으로 자르지 않는다)
- 나이 보정: 게시 24시간 안 된 영상은 '진행 중'으로 표시하고 비교 집계에서 뺀다(조회가 아직 차는 중)
- 묶음 표본 5편 미만은 '표본 적음' 표시(숫자 하나로 결론 내지 않게)
"""
import argparse, datetime as dt, json, os, re, sqlite3, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("CHSTATS_DB", os.path.join(ROOT, "channel_stats", "data", "stats.db"))
OUT = os.environ.get("CHSTATS_OUT", os.path.join(ROOT, "channel_stats", "web", "data.json"))
KST = dt.timezone(dt.timedelta(hours=9))
MATURE_H = 24
MIN_N = 5

# 채널 = 소재 축(사장님 운영 방식: 채널마다 콘셉트가 하나)
CONCEPT = {"950": "해외 바이럴 신기템", "987": "샤크탱크 제품", "994": "브랜드 비하인드 썰", "995": "과자·식품 비하인드",
           "998": "외국인 K제품 반응", "999": "연예인 쇼핑", "21": "신기한 발명품", "숏템07": "생활 꿀템"}

# 상품 분류 — 제목 낱말. 먼저 맞는 것 하나
PRODUCT = [("식품", r"과자|라면|우유|카레|요플레|김\b|김이|스프레드|핫도그|편의점|밥|감자칩|썬칩|통조림|불닭|땅콩|커피|아웃백|빼빼로|새우깡|라테|오나오|크림 만드"),
           ("뷰티", r"선크림|비비|비누|로션|파데|쿠션|염색|스킨|기미|화장|바디"),
           ("패션·잡화", r"신발|샌들|로퍼|팔찌|수건|요가"),
           ("전자·기기", r"모니터|마우스|노트북|로봇|우퍼|다리미|건조기|세탁기|가습기|녹음기|목걸이|귀마개|헬멧|손난로|발난로"),
           ("생활·주방", r"주걱|컵|텀블러|생수|보관통|수세미|스티커|쿨러|구멍|틈|연필|공놀이|의자|담요|인퓨저")]

PERSON_CH = {"999"}   # 연예인 쇼핑 채널 — 제목마다 연예인 이름(이름 패턴은 '공구없이'·'한국인이'를 잘못 잡았다)
# 제목 형태 — 여러 개 붙을 수 있다
FORMS = [("인물 언급", r"원장|유튜버|회장|박사|사장님|선생님|감독"),
         ("외국·해외", r"외국|미국|영국|북한|덴마크|전 세계|해외|두바이"),
         ("질문·물음표", r"\?"),
         ("숫자", r"\d"),
         ("비밀·반전·이유", r"비밀|반전|이유|원래|실체|따로|처음엔|근황|영업기밀"),
         ("감탄·과장", r"환장|난리|대박|미친|펑!|혼쭐|블랙홀")]


def _q(con, sql, *a):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, a)]


def _acct_key(account):
    m = re.match(r"(\d+|숏템\d+)", account or "")
    return m.group(1) if m else account


def _med(xs):
    return st.median(xs) if xs else 0


def _bucket_dur(s):
    return "30초 미만" if s < 30 else "30~34초" if s < 35 else "35~39초" if s < 40 else "40초 이상"


def build(db=DB):
    con = sqlite3.connect(db)
    now = dt.datetime.now(KST)
    last_run = _q(con, "SELECT * FROM runs ORDER BY at DESC LIMIT 1")
    # 영상마다 최신 스냅샷 + 첫 스냅샷(증가량)
    vids = _q(con, """
      SELECT v.*, s.views, s.likes, s.comments, s.at snap_at,
             (SELECT views FROM yt_snaps f WHERE f.video_id=v.video_id ORDER BY at LIMIT 1) first_views,
             (SELECT at FROM yt_snaps f WHERE f.video_id=v.video_id ORDER BY at LIMIT 1) first_at
      FROM yt_videos v JOIN yt_snaps s ON s.video_id=v.video_id
      WHERE s.at=(SELECT max(at) FROM yt_snaps x WHERE x.video_id=v.video_id)""")
    # 틱톡: Buffer 게시물 최신 스냅샷. 유튜브 영상과는 같은 Buffer 계정·같은 제목으로 짝짓는다
    tik = _q(con, """
      SELECT p.post_id, p.account, p.title, p.sent_at, p.link, p.file, s.* FROM posts p JOIN snaps s USING(post_id)
      WHERE p.service='tiktok' AND s.metrics_at=(SELECT max(metrics_at) FROM snaps x WHERE x.post_id=p.post_id)""")
    yt_post = {r["link"]: r for r in _q(con, "SELECT link, file, account FROM posts WHERE service='youtube'")}
    tik_by = {(_acct_key(t["account"]), (t["title"] or "").strip()): t for t in tik}
    chans = _q(con, """SELECT c.*, s.subs, s.views tot_views, s.videos FROM yt_channels c JOIN yt_channel_snaps s USING(channel_id)
                       WHERE s.at=(SELECT max(at) FROM yt_channel_snaps x WHERE x.channel_id=c.channel_id) AND s.videos>0""")
    subs_first = {r["channel_id"]: r["subs"] for r in _q(con, """SELECT channel_id, subs FROM yt_channel_snaps a
                   WHERE at=(SELECT min(at) FROM yt_channel_snaps b WHERE b.channel_id=a.channel_id)""")}

    series = {}
    for r in _q(con, "SELECT video_id, at, views FROM yt_snaps ORDER BY at"):
        series.setdefault(r["video_id"], []).append((r["at"], r["views"]))
    tseries = {}
    for r in _q(con, "SELECT post_id, metrics_at, views FROM snaps ORDER BY metrics_at"):
        tseries.setdefault(r["post_id"], []).append((r["metrics_at"], r["views"]))

    ya = _ya(con)

    out_v = []
    for v in vids:
        pub = dt.datetime.fromisoformat(v["published"].replace("Z", "+00:00")).astimezone(KST)
        age_h = (now - pub).total_seconds() / 3600
        key = _acct_key(v["account"])
        file = next((p["file"] for l, p in yt_post.items() if l and v["video_id"] in l), None)
        t = tik_by.get((key, v["title"].strip()))
        title = v["title"]
        pts = _pts(series.get(v["video_id"], []), pub)
        out_v.append({
            "id": v["video_id"], "ch": key, "title": title, "thumb": v["thumb"], "file": file,
            "url": f"https://www.youtube.com/shorts/{v['video_id']}",
            "published": pub.isoformat(timespec="minutes"), "hour": pub.hour, "weekday": "월화수목금토일"[pub.weekday()],
            "age_h": round(age_h, 1), "mature": age_h >= MATURE_H, "dur": v["duration"], "dur_bucket": _bucket_dur(v["duration"]),
            "views": v["views"], "likes": v["likes"], "comments": v["comments"],
            "like_rate": round(v["likes"] / v["views"] * 100, 2) if v["views"] else 0,
            "views_per_day": round(v["views"] / max(age_h / 24, 1), 1),
            "gain": (v["views"] - (v["first_views"] or v["views"])), "gain_since": v["first_at"],
            "pts": pts, "vph": _vph(pts),
            "ya": ya["video"].get(v["video_id"]), "retention": ya["retention"].get(v["video_id"]),
            "daily": _daily_pts(ya["video_daily"].get(v["video_id"], []), pub),
            "product": next((n for n, rx in PRODUCT if re.search(rx, title)), "기타"),
            "forms": [n for n, rx in FORMS if re.search(rx, title) or (n == "인물 언급" and key in PERSON_CH)],
            "tiktok": ({"pts": _pts(tseries.get(t["post_id"], []), pub), "views": int(t["views"] or 0), "avg_watch": t["averageTimeWatched"], "watch_min": t["totalTimeWatched"],
                        "likes": t["reactions"], "shares": t["shares"], "url": t["link"]} if t else None)})

    # 채널별 히트 기준(성숙 영상 중앙값 ×2)
    ch_med = {}
    for c in {v["ch"] for v in out_v}:
        ch_med[c] = _med([v["views"] for v in out_v if v["ch"] == c and v["mature"]])
    for v in out_v:
        m = ch_med.get(v["ch"]) or 0
        v["hit"] = bool(v["mature"] and m and v["views"] >= 2 * m)
        v["vs_median"] = round(v["views"] / m, 2) if m else None

    curves = {}
    for c in {v["ch"] for v in out_v}:
        curves[c] = _typical_curve([v["pts"] for v in out_v if v["ch"] == c])

    mature = [v for v in out_v if v["mature"]]

    def group(keyf, label, absolute=False):
        g = {}
        for v in mature:
            for k in (keyf(v) if isinstance(keyf(v), list) else [keyf(v)]):
                g.setdefault(k, []).append(v)
        rows = []
        for k, vs in g.items():
            rows.append({"key": k, "n": len(vs), "median": _med([x["views"] for x in vs]),
                         "mean": round(st.mean([x["views"] for x in vs])), "hits": sum(x["hit"] for x in vs),
                         "hit_rate": round(sum(x["hit"] for x in vs) / len(vs) * 100),
                         "vs_median": round(_med([x["vs_median"] or 0 for x in vs]), 2),
                         "like_rate": round(_med([x["like_rate"] for x in vs]), 2), "thin": len(vs) < MIN_N})
        rows.sort(key=(lambda r: -r["median"]) if absolute else (lambda r: (-r["vs_median"], -r["median"])))
        return {"label": label, "rows": rows, "measure": "median" if absolute else "vs_median"}

    no_form = lambda v: v["forms"] or ["형태 없음"]  # noqa: E731
    breakdowns = [group(lambda v: CONCEPT.get(v["ch"], v["ch"]), "채널 콘셉트", absolute=True),
                  group(lambda v: v["product"], "상품 분류"),
                  group(no_form, "제목 형태"),
                  group(lambda v: f"{v['hour']:02d}시", "게시 시각"),
                  group(lambda v: v["dur_bucket"], "영상 길이"),
                  group(lambda v: v["weekday"] + "요일", "게시 요일")]

    channels = []
    for c in chans:
        key = _acct_key(c["account"])
        vs = [v for v in out_v if v["ch"] == key]
        mv = [v for v in vs if v["mature"]]
        tk = [t for t in tik if _acct_key(t["account"]) == key]
        best = max(vs, key=lambda v: v["views"]) if vs else None
        channels.append({
            "key": key, "name": c["title"], "folder": c["account"], "concept": CONCEPT.get(key, ""), "thumb": c["thumb"], "id": c["channel_id"],
            "subs": c["subs"], "subs_gain": c["subs"] - subs_first.get(c["channel_id"], c["subs"]),
            "videos": len(vs), "views": sum(v["views"] for v in vs), "median": ch_med.get(key, 0),
            "hits": sum(v["hit"] for v in mv), "hit_rate": round(sum(v["hit"] for v in mv) / len(mv) * 100) if mv else 0,
            "like_rate": round(_med([v["like_rate"] for v in vs]), 2),
            "last7": sum(v["views"] for v in vs if v["age_h"] <= 24 * 7),
            "best": {"title": best["title"], "views": best["views"], "id": best["id"]} if best else None,
            "ya": ya["channel"].get(c["channel_id"]), "traffic": ya["traffic"].get(c["channel_id"], []),
            "tiktok": {"posts": len(tk), "views": int(sum(t["views"] or 0 for t in tk)),
                       "avg_watch": round(_med([t["averageTimeWatched"] or 0 for t in tk if t["views"]]), 1)} if tk else None})
    channels.sort(key=lambda c: -c["views"])

    pairs = [{"title": v["title"], "ch": v["ch"], "yt": v["views"], "tt": v["tiktok"]["views"],
              "tt_avg_watch": v["tiktok"]["avg_watch"], "dur": v["dur"]} for v in out_v if v["tiktok"]]

    insights = _insights(breakdowns, channels, out_v)
    data = {"generated_at": now.isoformat(timespec="minutes"), "collected_at": last_run[0]["at"] if last_run else None,
            "rules": {"hit": "채널 중앙값의 2배 이상", "mature_h": MATURE_H, "min_n": MIN_N},
            "coverage": {"youtube_videos": len(out_v), "tiktok_posts": len(tik), "channels": len(channels),
                         "pending": "유튜브 시청시간·유지율·유입경로는 채널 허용(유튜브 애널리틱스) 뒤에 붙는다"},
            "analytics": {"channels": len(ya["channel"]), "last_run": ya["last_run"],
                          "watch_min_28": round(sum(c["watch_min_28"] for c in ya["channel"].values())),
                          "views_28": sum(c["views_28"] for c in ya["channel"].values()),
                          "subs_net_28": sum(c["subs_net_28"] for c in ya["channel"].values())} if ya["channel"] else None,
            "totals": {"views": sum(v["views"] for v in out_v), "videos": len(out_v), "subs": sum(c["subs"] for c in channels),
                       "hits": sum(v["hit"] for v in out_v), "last7": sum(v["views"] for v in out_v if v["age_h"] <= 168),
                       "tiktok_views": int(sum(t["views"] or 0 for t in tik)), "likes": sum(v["likes"] for v in out_v)},
            "channels": channels, "videos": sorted(out_v, key=lambda v: -v["views"]), "curves": curves,
            "breakdowns": breakdowns, "pairs": pairs, "insights": insights}
    con.close()
    return data


def _ya(con):
    """유튜브 애널리틱스 표(허용된 채널만 있다). 표가 없으면 빈 묶음."""
    out = {"video": {}, "retention": {}, "video_daily": {}, "channel": {}, "traffic": {}, "last_run": None}
    have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "ya_video" not in have:
        return out
    for r in _q(con, "SELECT * FROM ya_video"):
        out["video"][r["video_id"]] = {"watch_min": round(r["watch_min"] or 0, 1), "avg_dur": round(r["avg_dur"] or 0, 1),
                                       "avg_pct": round(r["avg_pct"] or 0, 1), "subs": r["subs_gained"], "shares": r["shares"]}
    for r in _q(con, "SELECT * FROM ya_retention"):
        out["retention"][r["video_id"]] = json.loads(r["curve"])
    for r in _q(con, "SELECT * FROM ya_video_daily ORDER BY day"):
        out["video_daily"].setdefault(r["video_id"], []).append([r["day"], r["views"], round(r["watch_min"] or 0, 1)])
    since = (dt.date.today() - dt.timedelta(days=28)).isoformat()
    for cid in {r["channel_id"] for r in _q(con, "SELECT DISTINCT channel_id FROM ya_ch_daily")}:
        rows = _q(con, "SELECT * FROM ya_ch_daily WHERE channel_id=? ORDER BY day", cid)
        last = [r for r in rows if r["day"] >= since]
        v28 = sum(r["views"] for r in last)
        out["channel"][cid] = {
            "daily": [[r["day"], r["views"], round(r["watch_min"] or 0, 1), round(r["avg_pct"] or 0, 1),
                       r["subs_gained"] - r["subs_lost"], r["likes"], r["shares"]] for r in rows],
            "views_28": v28, "watch_min_28": round(sum(r["watch_min"] or 0 for r in last), 1),
            "avg_pct_28": round(sum((r["avg_pct"] or 0) * r["views"] for r in last) / v28, 1) if v28 else 0,
            "avg_dur_28": round(sum((r["avg_dur"] or 0) * r["views"] for r in last) / v28, 1) if v28 else 0,
            "subs_net_28": sum(r["subs_gained"] - r["subs_lost"] for r in last)}
    for r in _q(con, "SELECT * FROM ya_traffic ORDER BY views DESC"):
        out["traffic"].setdefault(r["channel_id"], []).append([r["source"], r["views"], round(r["watch_min"] or 0, 1)])
    lr = _q(con, "SELECT max(at) at FROM ya_runs")
    out["last_run"] = lr[0]["at"] if lr else None
    return out


def _daily_pts(rows, pub):
    """애널리틱스 일별 조회 → 누적 [[게시 후 시간(그날 끝), 누적 조회]] — 수집 전 구간(게시 첫날부터)을 채운다."""
    out, tot = [], 0
    for day, views, _wm in rows:
        tot += views
        end = dt.datetime.fromisoformat(day).replace(tzinfo=KST) + dt.timedelta(days=1)
        out.append([round(max((end - pub).total_seconds() / 3600, 0.5), 1), tot])
    return out


AGE_MARKS = [1, 2, 3, 6, 12, 24, 48, 72, 120, 168, 336, 720]   # 게시 후 시간(평소 곡선의 눈금)


def _pts(rows, pub):
    """스냅샷 → [[게시 후 시간, 조회]] (같은 조회 반복은 첫 점만 — 그래프가 평평한 구간을 늘어뜨리지 않게, 마지막 점은 남긴다)."""
    out = []
    for i, (at, views) in enumerate(rows):
        t = dt.datetime.fromisoformat(at.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=KST)
        h = round((t - pub).total_seconds() / 3600, 2)
        if h < 0 or views is None:
            continue
        if out and out[-1][1] == views and i != len(rows) - 1:
            continue
        out.append([h, int(views)])
    return out


def _vph(pts):
    """지금 시간당 몇 회씩 느나 — 마지막 두 스냅샷이 1시간 이상 떨어져 있을 때만(짧으면 흔들린다)."""
    if len(pts) < 2:
        return None
    (h0, v0), (h1, v1) = pts[-2], pts[-1]
    return round((v1 - v0) / (h1 - h0), 1) if h1 - h0 >= 1 else None


def _typical_curve(all_pts):
    """채널 평소 곡선: 눈금 시간마다, 그 시간 ±25% 안에 찍힌 스냅샷이 있는 영상들의 조회 중앙값(3편 이상일 때만)."""
    out = []
    for m in AGE_MARKS:
        vals = []
        for pts in all_pts:
            near = [v for h, v in pts if m * .75 <= h <= m * 1.25]
            if near:
                vals.append(near[len(near) // 2])
        if len(vals) >= 3:
            out.append([m, _med(vals), len(vals)])
    return out


def _insights(breakdowns, channels, vids):
    """숫자에서 바로 읽히는 문장만 — 표본 5편 미만 묶음으로는 결론을 만들지 않는다."""
    out = []
    for b in breakdowns:
        rows = [r for r in b["rows"] if not r["thin"]]
        if len(rows) >= 2:
            top, low = rows[0], rows[-1]
            if b.get("measure") == "median":
                out.append({"kind": "compare", "axis": b["label"],
                            "text": f"{b['label']} — 한 편 보통 조회 '{top['key']}' {top['median']:,.0f}회({top['n']}편)가 가장 높고 "
                                    f"'{low['key']}' {low['median']:,.0f}회({low['n']}편)가 가장 낮다"})
            elif top["vs_median"] > low["vs_median"]:
                out.append({"kind": "compare", "axis": b["label"],
                            "text": f"{b['label']} — 가장 잘됨 '{top['key']}' 평소의 {top['vs_median']}배({top['n']}편) · "
                                    f"가장 약함 '{low['key']}' {low['vs_median']}배({low['n']}편)"})
    mv = [v for v in vids if v["mature"]]
    if mv:
        floor = sum(1 for v in mv if v["views"] < 2000)
        out.append({"kind": "dist", "text": f"24시간 지난 {len(mv)}편 중 {floor}편({round(floor / len(mv) * 100)}%)이 2,000회 아래에서 멈췄다 — "
                                            f"쇼츠 첫 노출 구간을 넘긴 건 {len(mv) - floor}편"})
    hits = sorted([v for v in vids if v["hit"]], key=lambda v: -v["vs_median"])
    for v in hits[:3]:
        out.append({"kind": "hit", "text": f"'{v['title']}' — 채널 평소의 {v['vs_median']}배 ({v['views']:,}회)"})
    tk = [c for c in channels if c["tiktok"] and c["tiktok"]["views"]]
    if tk:
        b = max(tk, key=lambda c: c["tiktok"]["views"])
        out.append({"kind": "tiktok", "text": f"틱톡 — '{b['name']}' {b['tiktok']['views']:,}회로 가장 많이 봤다 (평균 시청 {b['tiktok']['avg_watch']}초)"})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    d = build(a.db)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    print(f"[analyze] 영상 {d['totals']['videos']} · 채널 {len(d['channels'])} · 히트 {d['totals']['hits']} → {a.out}")
