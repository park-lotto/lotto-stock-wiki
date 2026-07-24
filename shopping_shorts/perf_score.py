"""성과 정규화(A2). perf_from_item = 랭킹 아이템 → nullable perf dict.
scoring 수학은 compute_perf_score(Task 6). DB·Gemini 의존 없음(순수함수)."""
import math
from datetime import datetime

_PERF_FIELDS = ("views", "likes", "comments", "followers")

_W_PCT = 0.75            # 백분위 가중
_W_RECENCY = 0.25        # 최근성 가중(백분위를 감쇠시키는 축)
_FOLLOWER_BONUS = 0.1    # views/followers 비율 보정 상한
_HALF_LIFE_DAYS = 30.0


def perf_from_item(item):
    """랭킹 아이템(ranking.build_* 산출)에서 성과지표만 뽑아 nullable dict로.
    플랫폼이 못 주는 값은 None(0으로 지어내지 말 것 — R3 매트릭스:
    saves=전무·followers=인스타전용·댓글=도우인/샤오홍슈 없음)."""
    out = {"platform": item.get("platform")}
    for f in _PERF_FIELDS:
        v = item.get(f)
        out[f] = v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    out["captured_at"] = item.get("collected_at")
    return out


def _blend_volume(perf):
    return (perf.get("views") or 0) + (perf.get("likes") or 0) + (perf.get("comments") or 0)


def within_platform_percentile(value, peers):
    """peers 중 value 이하인 비율(0~1). log1p 변환 후 순위(로그가중)."""
    if value is None or not peers:
        return 0.0
    lv = math.log1p(max(0.0, float(value)))
    lp = [math.log1p(max(0.0, float(p))) for p in peers if p is not None]
    if not lp:
        return 0.0
    return sum(1 for x in lp if x <= lv) / len(lp)


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "").split("+")[0])
    except Exception:
        return None


def recency_decay(captured_at_iso, now_iso=None, half_life_days=_HALF_LIFE_DAYS):
    """0.5 ** (age_days/half_life), (0,1]. 타임스탬프 없거나 파싱실패면 1.0(감쇠 없음)."""
    c = _parse(captured_at_iso)
    n = _parse(now_iso) if now_iso else None
    if c is None or n is None:
        return 1.0
    age_days = max(0.0, (n - c).total_seconds() / 86400.0)
    return 0.5 ** (age_days / half_life_days)


def compute_perf_score(perf, peers_by_platform, now_iso=None):
    """플랫폼내 로그백분위 × 최근성감쇠 + 팔로워 보정. 반환 [0,1]."""
    if not perf:
        return 0.0
    platform = perf.get("platform")
    peers = [_blend_volume(p) for p in peers_by_platform.get(platform, [])]
    pct = within_platform_percentile(_blend_volume(perf), peers)
    rec = recency_decay(perf.get("captured_at"), now_iso)
    base = _W_PCT * pct + _W_RECENCY * pct * rec   # 최근성은 백분위를 감쇠시키는 축
    followers = perf.get("followers")
    if followers:
        ratio = min(1.0, (perf.get("views") or 0) / float(followers))
        base = min(1.0, base + _FOLLOWER_BONUS * ratio)
    return max(0.0, min(1.0, base))
