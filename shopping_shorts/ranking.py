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
