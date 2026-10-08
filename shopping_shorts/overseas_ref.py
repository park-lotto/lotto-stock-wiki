# -*- coding: utf-8 -*-
"""해외 레퍼런스 채널 수집(관제 162, 2026-10-08 사장님) — 관리자 전용.

해외에서 터진 영상을 만드는 채널을 **검색어 눈덩이**로 모은다:
  씨앗(해외 영상 URL 또는 검색어) → 판매자 태그 + 영어 관련 검색어
  → 유튜브 조회수순 검색(최근 N일, 미국·영어) → 해외 채널 저장
  → 걸린 영상들의 태그로 새 검색어 → 반복(라운드)

1차는 **채널을 모으는 것만** 한다. 채널이 괜찮은지·어떤 영상이 있는지는 2차 작업.
실측(2026-10-08): 씨앗 1편 태그 4개 → 영상 197편·채널 127개(10만+ 구독 91개), 렌즈 0회.

★판단 주인: 검색어 고르기 = next_keywords / 해외 판정 = is_overseas / 저장 = _save.
  화면(overseas_ref.html)은 이 모듈의 API 결과만 그린다.
비용: 유튜브 search 100단위/회(무료 키 풀) + 제미니 텍스트 1회/씨앗. 렌즈(SerpApi) 0회.
"""
import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from shopping_shorts import config
from shopping_shorts import youtube_client as yc

CATEGORIES = ["국뽕", "스포츠", "동물", "해외반응", "랭킹형", "웃긴"]
_HANGUL = re.compile(r"[가-힣]")
_TAG = re.compile(r"#([^\s#]+)")
_GENERIC = {"shorts", "short", "youtubeshorts", "viral", "trending", "fyp", "foryou",
            "foryoupage", "explore", "reels", "subscribe", "youtube", "video", "tiktok",
            "shortvideo", "shortsvideo", "shortsfeed", "ytshorts", "youtubeshort", "shortsviral", "viralshorts",
            "viralvideo", "trend", "new", "reel", "instagram", "instagood", "like", "follow", "love"}

_JOB = {"running": False, "cat": "", "log": [], "started": "", "done": ""}
_LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _db():
    c = sqlite3.connect(config.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS overseas_ref_channel (
        category TEXT NOT NULL, channel_id TEXT NOT NULL, title TEXT, subs INTEGER,
        hit_videos INTEGER DEFAULT 0, hit_views INTEGER DEFAULT 0, top_video TEXT,
        top_views INTEGER DEFAULT 0, keywords TEXT, seed TEXT, round INTEGER,
        added_at TEXT, updated_at TEXT, PRIMARY KEY (category, channel_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS overseas_ref_kw (
        category TEXT NOT NULL, kw TEXT NOT NULL, source TEXT, results INTEGER,
        new_channels INTEGER, searched_at TEXT, PRIMARY KEY (category, kw))""")
    return c


def is_overseas(title):
    """해외 영상 판정 — 제목에 한글이 없으면 해외. (국내 각색본을 거른다)"""
    return not _HANGUL.search(title or "")


def tags_of(text):
    """설명글·제목의 #태그(일반 태그 제외), 등장 순."""
    out = []
    for t in _TAG.findall(text or ""):
        t = t.strip(".,!?").lower()
        if t and t not in _GENERIC and not _HANGUL.search(t) and t not in out:
            out.append(t)
    return out


def _english_terms(text):
    """영어 관련 검색어(제미니 1회) — 확장프로그램 관련 검색어와 같은 판단(english_search_terms)."""
    try:
        from shopping_shorts import video_analysis
        r = video_analysis.english_search_terms(text, "caption", lang="en")
        return [k for k in [r.get("main", "")] + list(r.get("related") or []) if k]
    except Exception as e:                  # noqa: BLE001 — 실패해도 태그만으로 돈다(로그는 남긴다)
        _log(f"영어 검색어 실패: {e!r}"[:200])
        return []


def _log(msg):
    _JOB["log"].append(f"{datetime.now().strftime('%H:%M:%S')} {msg}")
    _JOB["log"] = _JOB["log"][-200:]


def _video_id(s):
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", s or "")
    return m.group(1) if m else (s if re.fullmatch(r"[A-Za-z0-9_-]{11}", s or "") else None)


def _is_channel_seed(seed):
    return bool(re.search(r"youtube\.com/(@|channel/|c/|user/)", seed or "")) or (seed or "").startswith("@")


def channel_seed(seed, top=10):
    """채널 씨앗(사장님 2026-10-08 "@OneinOneShorts 추가") → (채널행, 상위 영상 태그 검색어).
    채널 자체도 저장 대상이고, 그 채널의 조회수 상위 영상 태그로 눈덩이를 시작한다."""
    cid, uploads = yc._resolve_channel(seed)
    if not uploads:
        return None, []
    pl, _ = yc._first_ok(yc._PLAYLIST_ITEMS_URL, {"part": "contentDetails", "playlistId": uploads, "maxResults": 50})
    ids = [i["contentDetails"]["videoId"] for i in (pl or {}).get("items") or []]
    vd, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "snippet,statistics", "id": ",".join(ids)}) if ids else (None, None)
    vids = sorted((vd or {}).get("items") or [], key=lambda it: -int(it["statistics"].get("viewCount") or 0))[:top]
    if not vids:
        return None, []
    tags = {}
    for it in vids:
        sn = it["snippet"]
        for t in tags_of(sn.get("title", "") + " " + (sn.get("description") or "")):
            tags[t] = tags.get(t, 0) + 1
    row = {"title": vids[0]["snippet"]["channelTitle"], "videos": {it["id"] for it in vids},
           "views": sum(int(it["statistics"].get("viewCount") or 0) for it in vids),
           "top_video": vids[0]["id"], "top_views": int(vids[0]["statistics"].get("viewCount") or 0),
           "kws": set(), "subs": _subs([cid]).get(cid, 0)}
    kws = [t for t, _ in sorted(tags.items(), key=lambda kv: -kv[1])][:6]
    if len(kws) < 3:
        kws += _english_terms(" / ".join(it["snippet"]["title"] for it in vids))
    if len(kws) < 3:
        # 태그 없는 채널(One in One 실측: 태그 0) + 제미니 실패 → 상위 영상 제목(앞 6단어)으로 검색한다
        for it in vids[:4]:
            words = re.sub(r"[^\w\s']", " ", it["snippet"]["title"]).split()[:6]
            if len(words) >= 3:
                kws.append(" ".join(words).lower())
    return {cid: row}, list(dict.fromkeys(kws))


def seed_keywords(seed):
    """씨앗 → 첫 검색어. 유튜브 영상 URL이면 태그+영어 검색어, 아니면 그 글자 자체(쉼표로 여러 개)."""
    vid = _video_id(seed)
    if not vid:
        return [k.strip() for k in (seed or "").split(",") if k.strip()]
    d, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "snippet", "id": vid})
    items = (d or {}).get("items") or []
    if not items:
        return []
    sn = items[0]["snippet"]
    text = sn.get("title", "") + "\n" + (sn.get("description") or "")[:500]
    kws = tags_of(text)[:5] + _english_terms(text)
    return list(dict.fromkeys(k.lower() for k in kws))


def _search(kw, days):
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for tok in config.YOUTUBE_API_KEYS:
        code, items = yc._search_page(kw, after, 50, tok, region="US", lang="en")
        if code == 200:
            return items or []
    return None                              # 키 전부 실패 — 호출부가 멈춘다


def _stats(video_ids):
    out = {}
    for i in range(0, len(video_ids), 50):
        d, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "statistics", "id": ",".join(video_ids[i:i + 50])})
        for it in (d or {}).get("items") or []:
            out[it["id"]] = int((it.get("statistics") or {}).get("viewCount") or 0)
    return out


def _subs(channel_ids):
    out = {}
    for i in range(0, len(channel_ids), 50):
        d, _ = yc._first_ok(yc._CHANNELS_URL, {"part": "statistics", "id": ",".join(channel_ids[i:i + 50])})
        for it in (d or {}).get("items") or []:
            out[it["id"]] = int((it.get("statistics") or {}).get("subscriberCount") or 0)
    return out


def _save(c, cat, rows, seed, rnd):
    """채널 누적 저장. 같은 채널이 다시 걸리면 걸린 영상 수·조회수·검색어를 더한다."""
    new = 0
    for cid, r in rows.items():
        old = c.execute("SELECT * FROM overseas_ref_channel WHERE category=? AND channel_id=?", (cat, cid)).fetchone()
        if old is None:
            new += 1
            c.execute("""INSERT INTO overseas_ref_channel VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (cat, cid, r["title"], r["subs"], len(r["videos"]), r["views"], r["top_video"],
                       r["top_views"], json.dumps(sorted(r["kws"]), ensure_ascii=False), seed, rnd, _now(), _now()))
        else:
            kws = sorted(set(json.loads(old["keywords"] or "[]")) | r["kws"])
            top_v, top_n = (r["top_video"], r["top_views"]) if r["top_views"] > (old["top_views"] or 0) \
                else (old["top_video"], old["top_views"])
            c.execute("""UPDATE overseas_ref_channel SET title=?, subs=?, hit_videos=hit_videos+?, hit_views=hit_views+?,
                         top_video=?, top_views=?, keywords=?, updated_at=? WHERE category=? AND channel_id=?""",
                      (r["title"], r["subs"], len(r["videos"]), r["views"], top_v, top_n,
                       json.dumps(kws, ensure_ascii=False), _now(), cat, cid))
    c.commit()
    return new


def next_keywords(c, cat, found_tags, limit, top_titles=()):
    """다음 라운드 검색어 — 이번에 걸린 해외 영상 태그 중 자주 나온 것(2회+), 이 카테고리에서 아직 안 쓴 것.
    태그가 모자라면 조회수 상위 영상 제목(앞 6단어)으로 채운다."""
    used = {r[0] for r in c.execute("SELECT kw FROM overseas_ref_kw WHERE category=?", (cat,))}
    ranked = sorted(found_tags.items(), key=lambda kv: -kv[1])
    out = [t for t, n in ranked if t not in used and n >= 2][:limit]
    for title in top_titles:
        if len(out) >= limit:
            break
        words = re.sub(r"[^\w\s']", " ", title or "").split()[:6]
        q = " ".join(words).lower()
        if len(words) >= 3 and q not in used and q not in out:
            out.append(q)
    return out


def run(cat, seed, rounds=2, per_round=6, days=90):
    """눈덩이 수집 본체(블로킹). 반환: 요약 dict."""
    c = _db()
    if _is_channel_seed(seed):
        row, kws = channel_seed(seed)
        if row:
            _save(c, cat, row, seed, 0)
            _log(f"[{cat}] 씨앗 채널 저장: {list(row.values())[0]['title']}")
        else:
            _log(f"[{cat}] 채널을 못 찾음: {seed}")
    else:
        kws = seed_keywords(seed)
    _log(f"[{cat}] 씨앗 {seed[:60]} → 검색어 {kws}")
    total_new, searched = 0, 0
    for rnd in range(1, rounds + 1):
        used = {r[0] for r in c.execute("SELECT kw FROM overseas_ref_kw WHERE category=?", (cat,))}
        kws = [k for k in kws if k not in used][:per_round]
        if not kws:
            _log(f"[{cat}] {rnd}라운드: 새 검색어 없음 — 멈춤")
            break
        found_tags, top = {}, []
        for kw in kws:
            items = _search(kw, days)
            if items is None:
                _log(f"[{cat}] 유튜브 키 전부 실패 — 멈춤")
                return {"new": total_new, "searched": searched, "stopped": "youtube_keys"}
            searched += 1
            items = [it for it in items if is_overseas(it.get("title"))]
            views = _stats([it["video_id"] for it in items])
            rows = {}
            for it in items:
                r = rows.setdefault(it["channel_id"], {"title": it["channel_title"], "videos": set(), "views": 0,
                                                        "top_video": "", "top_views": 0, "kws": {kw}, "subs": 0})
                v = views.get(it["video_id"], 0)
                r["videos"].add(it["video_id"]); r["views"] += v
                top.append((v, it.get("title") or ""))
                if v > r["top_views"]:
                    r["top_video"], r["top_views"] = it["video_id"], v
                for t in tags_of((it.get("title") or "") + " " + (it.get("description") or "")):
                    found_tags[t] = found_tags.get(t, 0) + 1
            subs = _subs(list(rows))
            for cid in rows:
                rows[cid]["subs"] = subs.get(cid, 0)
            new = _save(c, cat, rows, seed, rnd)
            total_new += new
            c.execute("INSERT OR REPLACE INTO overseas_ref_kw VALUES (?,?,?,?,?,?)",
                      (cat, kw, seed[:200], len(items), new, _now()))
            c.commit()
            _log(f"[{cat}] {rnd}R '{kw}': 해외영상 {len(items)}편 · 채널 {len(rows)}개(새 {new})")
        kws = next_keywords(c, cat, found_tags, per_round, [t for _, t in sorted(top, reverse=True)[:20]])
    c.close()
    _log(f"[{cat}] 끝 — 검색 {searched}회 · 새 채널 {total_new}개")
    return {"new": total_new, "searched": searched}


def start(cat, seed, rounds=2):
    """백그라운드로 run. 이미 돌고 있으면 False."""
    with _LOCK:
        if _JOB["running"]:
            return False
        _JOB.update(running=True, cat=cat, started=_now(), done="")

    def _go():
        try:
            run(cat, seed, rounds=rounds)
        except Exception as e:              # noqa: BLE001 — 화면에 보이게 남긴다
            _log(f"[{cat}] 오류: {e!r}"[:300])
        finally:
            _JOB.update(running=False, done=_now())

    threading.Thread(target=_go, daemon=True).start()
    return True


def status():
    return {k: _JOB[k] for k in ("running", "cat", "started", "done")} | {"log": _JOB["log"][-60:]}


def channels(cat, limit=500):
    c = _db()
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM overseas_ref_channel WHERE category=? ORDER BY hit_views DESC LIMIT ?", (cat, limit))]
    kws = [dict(r) for r in c.execute(
        "SELECT kw, results, new_channels, searched_at FROM overseas_ref_kw WHERE category=? ORDER BY searched_at DESC", (cat,))]
    counts = {r[0]: r[1] for r in c.execute("SELECT category, COUNT(*) FROM overseas_ref_channel GROUP BY category")}
    c.close()
    for r in rows:
        r["keywords"] = json.loads(r.get("keywords") or "[]")
    return {"channels": rows, "keywords": kws, "counts": counts}
