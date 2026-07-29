"""랭킹 엔진 — 48h 필터 + 강도지표 계산 + 정렬. 순수 함수 모음."""
from datetime import datetime, timezone
from shopping_shorts.config import GRADE_THRESHOLDS
from shopping_shorts.categorize import categorize


def hours_since(ts_iso, now=None):
    """ISO timestamp → 지금까지 경과 시간(h)."""
    now = now or datetime.now(timezone.utc)
    dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600.0


def grade_from_scores(score):
    """0~1 종합점수 → 등급 뱃지."""
    for threshold, badge in GRADE_THRESHOLDS:
        if score >= threshold:
            return badge
    return "—"


def build_items(reels, meta, prev_comments, prev_delta, now=None, window_hours=48):
    """reel 원본 + 채널메타 → 지표 채워진 항목 리스트 (48h 이내만).

    prev_comments(shortcode)->int|None, prev_delta(shortcode)->int|None : 이력 조회 콜백.
    """
    now = now or datetime.now(timezone.utc)
    items = []
    for r in reels:
        ts = r.get("timestamp")
        if not ts:
            continue
        age = hours_since(ts, now=now)
        if age > window_hours or age < 0:
            continue
        comments = int(r.get("commentsCount") or 0)
        sc = r.get("shortcode") or r.get("url") or ""
        prev_c = prev_comments(sc)
        is_new = prev_c is None
        delta = comments if is_new else comments - prev_c
        prev_d = prev_delta(sc)
        accel = None if prev_d is None else delta - prev_d
        followers = meta.get("followers") or 0
        items.append({
            "shortcode": sc,
            "name": meta.get("name"),
            "username": meta.get("username"),
            "inpock": meta.get("inpock", ""),
            "followers": followers,
            "thumbnail": r.get("displayUrl", ""),
            "video_url": r.get("videoUrl", ""),
            "url": r.get("url", ""),
            "comments": comments,
            "likes": int(r.get("likesCount") or 0),
            "views": int(r.get("videoViewCount") or r.get("videoPlayCount") or 0),
            "age_hours": round(age, 1),
            "delta": delta,
            "is_new": is_new,
            "accel": accel,
            "speed": comments / age if age > 0 else float(comments),
            "density": (comments / followers) if followers else 0.0,
            "category": categorize(meta.get("name"), r.get("caption", "")),
            "caption": r.get("caption", ""),
        })
    return items


def _normalize(items, key):
    """항목 리스트의 key값을 0~1로 정규화한 dict{shortcode:score}. None은 0."""
    vals = [(i.get(key) or 0) for i in items]
    hi = max(vals) if vals else 0
    if hi <= 0:
        return {i["shortcode"]: 0.0 for i in items}
    return {i["shortcode"]: max(0.0, (i.get(key) or 0) / hi) for i in items}


def apply_grades(items):
    """속도·가속·밀도를 정규화 후 균등 종합 → grade 채움. items를 in-place 갱신."""
    ns = _normalize(items, "speed")
    na = _normalize(items, "accel")
    nd = _normalize(items, "density")
    for i in items:
        sc = i["shortcode"]
        score = (ns[sc] + na[sc] + nd[sc]) / 3.0
        i["score"] = round(score, 3)
        i["grade"] = grade_from_scores(score)
    return items


def sort_by(items, tab):
    """탭 기준 내림차순 정렬. tab: 'comments'|'speed'|'accel'|'density'."""
    key = {"전체": "comments", "comments": "comments",
           "속도": "speed", "speed": "speed",
           "가속": "accel", "accel": "accel",
           "밀도": "density", "density": "density"}.get(tab, "comments")
    return sorted(items, key=lambda i: (i.get(key) or 0), reverse=True)


def build_youtube_items(raw, prev_base, prev_delta, now=None, window_hours=48):
    """유튜브 원시 dict → 공통 item(조회수 기반 지표). 48h 이내만.

    prev_base(shortcode)->int|None: 직전 base_count(조회수). prev_delta 동일.
    speed=조회수/경과h, density=(좋아요+댓글)/조회수, accel=Δ−직전Δ.
    """
    now = now or datetime.now(timezone.utc)
    items = []
    for r in raw:
        ts = r.get("published_at")
        if not ts:
            continue
        age = hours_since(ts, now=now)
        if age > window_hours or age < 0:
            continue
        views = int(r.get("views") or 0)
        sc = r.get("video_id") or ""
        prev = prev_base(sc)
        is_new = prev is None
        delta = views if is_new else views - prev
        prev_d = prev_delta(sc)
        accel = None if prev_d is None else delta - prev_d
        likes = int(r.get("likes") or 0)
        comments = int(r.get("comments") or 0)
        items.append({
            "platform": "youtube",
            "shortcode": sc,
            "name": r.get("channel_title"),
            "username": r.get("channel_id"),
            "inpock": "",
            "followers": None,
            "thumbnail": r.get("thumbnail", ""),
            "video_url": "",                       # 인라인은 mix 다운로드 시 해석
            "url": f"https://www.youtube.com/watch?v={sc}",
            "comments": comments,
            "likes": likes,
            "views": views,
            "base_count": views,
            "age_hours": round(age, 1),
            "delta": delta,
            "is_new": is_new,
            "accel": accel,
            "speed": views / age if age > 0 else float(views),
            "density": (likes + comments) / views if views else 0.0,
            "category": categorize(r.get("channel_title"), r.get("title", "")),
            "caption": r.get("title", ""),
        })
    return items


def aggregate_channels(items, sort="views"):
    """공통 item 리스트 → 채널(username=channel_id)별 집계 리더보드.

    레퍼런스 랭킹과 같은 지표를 채널 단위로 굴린다:
      조회수(views) = 채널 영상 조회수 합
      속도(speed)   = 채널 영상 최고 속도(가장 빨리 도는 영상)
      참여율(density)= 채널 영상 참여율 평균
      가속(accel)   = 채널 영상 가속 합(음수 가능)
    sort: 'views'|'speed'|'density'|'accel'|'count' 내림차순.
    반환 각 원소: {channel_id, name, channel_url, video_count, views, speed,
                   density, accel, grade, thumbnail}."""
    by = {}
    for i in items:
        cid = i.get("username")
        if not cid:
            continue
        g = by.setdefault(cid, {"channel_id": cid, "name": i.get("name") or "",
                                "channel_url": f"https://www.youtube.com/channel/{cid}",
                                "video_count": 0, "views": 0, "_speed": [], "_density": [],
                                "accel": 0, "_score": 0.0, "thumbnail": ""})
        g["video_count"] += 1
        g["views"] += int(i.get("views") or 0)
        g["_speed"].append(float(i.get("speed") or 0))
        g["_density"].append(float(i.get("density") or 0))
        g["accel"] += int(i.get("accel") or 0)
        sc = float(i.get("score") or 0)
        if sc >= g["_score"]:                       # 대표=최고점 영상(썸네일·등급)
            g["_score"] = sc
            g["grade"] = i.get("grade") or "—"
            g["thumbnail"] = i.get("thumbnail") or ""
            if i.get("name"):
                g["name"] = i.get("name")
    out = []
    for g in by.values():
        speeds, dens = g.pop("_speed"), g.pop("_density")
        g["speed"] = round(max(speeds), 2) if speeds else 0
        g["density"] = round(sum(dens) / len(dens), 4) if dens else 0.0
        g["score"] = round(g.pop("_score"), 3)
        g.setdefault("grade", "—")
        out.append(g)
    key = {"views": "views", "speed": "speed", "density": "density",
           "accel": "accel", "count": "video_count"}.get(sort, "views")
    out.sort(key=lambda x: (x.get(key) or 0), reverse=True)
    return out


def build_tiktok_items(raw, prev_base, prev_delta, now=None, window_hours=336):
    """틱톡 원시 dict(tiktok_client) → 공통 item(조회수 기반 지표). 유튜브와 동일 구조.

    tiktok_client가 이미 url·published_at(ISO)·views/likes/comments를 채워 온다.
    speed=조회수/경과h, density=(좋아요+댓글)/조회수, accel=Δ−직전Δ."""
    now = now or datetime.now(timezone.utc)
    items = []
    for r in raw:
        ts = r.get("published_at")
        if not ts:
            continue
        age = hours_since(ts, now=now)
        if age > window_hours or age < 0:
            continue
        views = int(r.get("views") or 0)
        sc = r.get("video_id") or ""
        prev = prev_base(sc)
        is_new = prev is None
        delta = views if is_new else views - prev
        prev_d = prev_delta(sc)
        accel = None if prev_d is None else delta - prev_d
        likes = int(r.get("likes") or 0)
        comments = int(r.get("comments") or 0)
        items.append({
            "platform": "tiktok",
            "shortcode": sc,
            "name": r.get("channel_title"),
            "username": r.get("channel_title"),
            "inpock": "",
            "followers": None,
            "thumbnail": r.get("thumbnail", ""),
            "video_url": "",
            "url": r.get("url", ""),
            "comments": comments,
            "likes": likes,
            "views": views,
            "base_count": views,
            "age_hours": round(age, 1),
            "delta": delta,
            "is_new": is_new,
            "accel": accel,
            "speed": views / age if age > 0 else float(views),
            "density": (likes + comments) / views if views else 0.0,
            "category": categorize(r.get("channel_title"), r.get("title", "")),
            "caption": r.get("title", ""),
        })
    return items


def build_reddit_items(raw, prev_base, prev_delta, now=None, window_hours=48):
    """Reddit 정규화 dict(reddit_source) → 공통 item(upvote 기반 지표). 48h 이내만.

    주신호=upvote: base_count=ups, speed=ups/경과h, density=댓글/ups, accel=Δ−직전Δ.
    build_tiktok_items와 동일 구조라 apply_grades/sort_by를 그대로 태운다."""
    now = now or datetime.now(timezone.utc)
    items = []
    for r in raw:
        ts = r.get("published_at")
        if not ts:
            continue
        age = hours_since(ts, now=now)
        if age > window_hours or age < 0:
            continue
        ups = int(r.get("ups") or 0)
        sc = r.get("post_id") or ""
        prev = prev_base(sc)
        is_new = prev is None
        delta = ups if is_new else ups - prev
        prev_d = prev_delta(sc)
        accel = None if prev_d is None else delta - prev_d
        comments = int(r.get("num_comments") or 0)
        items.append({
            "platform": "reddit",
            "source": "reddit",
            "shortcode": sc,
            "post_id": sc,
            "name": r.get("subreddit", ""),
            "username": r.get("subreddit", ""),
            "thumbnail": r.get("thumbnail", ""),
            "url": r.get("permalink", ""),
            "media_url": r.get("media_url", ""),
            "media_platform": r.get("media_platform", ""),
            "comments": comments,
            "likes": ups,
            "views": ups,
            "base_count": ups,
            "ups": ups,
            "age_hours": round(age, 1),
            "delta": delta,
            "is_new": is_new,
            "accel": accel,
            "speed": ups / age if age > 0 else float(ups),
            "density": comments / ups if ups else 0.0,
            "category": r.get("category", ""),
            "caption": r.get("title", ""),
            "title": r.get("title", ""),
        })
    return items


def build_overseas_items(raw, prev_base, prev_delta, now=None, window_hours=336):
    """해외HOT 다중플랫폼(틱톡/도우인/샤오홍슈) raw → 공통 item.

    CN(도우인·샤오홍슈)은 조회수를 안 줘서(2026-07-26 실측) 랭킹 기준을 '참여'로 통일한다:
    base = 좋아요+댓글+수집+공유, speed = base/경과h. views는 표시용(없으면 0).
    platform은 raw.media_platform 보존(gap 번역분기·UI 뱃지용). window 336h=14일."""
    now = now or datetime.now(timezone.utc)
    items = []
    for r in raw:
        ts = r.get("published_at")
        if not ts:
            continue
        age = hours_since(ts, now=now)
        if age > window_hours or age < 0:
            continue
        likes = int(r.get("likes") or 0)
        comments = int(r.get("comments") or 0)
        collects = int(r.get("collects") or 0)
        shares = int(r.get("shares") or 0)
        views = int(r.get("views") or 0)
        base = likes + comments + collects + shares
        sc = r.get("video_id") or ""
        prev = prev_base(sc)
        is_new = prev is None
        delta = base if is_new else base - prev
        prev_d = prev_delta(sc)
        accel = None if prev_d is None else delta - prev_d
        items.append({
            "platform": r.get("media_platform") or "tiktok",
            "shortcode": sc,
            "name": r.get("channel_title"),
            "username": r.get("channel_title"),
            "inpock": "",
            "followers": None,
            "thumbnail": r.get("thumbnail", ""),
            "video_url": "",
            "url": r.get("url", ""),
            "comments": comments,
            "likes": likes,
            "collects": collects,
            "shares": shares,
            "views": views,
            "base_count": base,
            "age_hours": round(age, 1),
            "delta": delta,
            "is_new": is_new,
            "accel": accel,
            "speed": base / age if age > 0 else float(base),
            "density": (collects + shares) / base if base else 0.0,
            "category": r.get("category") or "",
            "caption": r.get("title", ""),
            # _annotate_text_level(overseas_hot_jobs.py)이 raw dict에 붙인 판정을
            # item으로 옮겨 싣는다 — 여기서 안 옮기면 caption_rank가 항상 미판정으로
            # 보여 정렬이 no-op이 된다(2026-07-29 Critical 2).
            "text_level": r.get("text_level"),
        })
    return items
