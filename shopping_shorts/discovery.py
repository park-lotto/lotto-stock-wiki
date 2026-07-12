"""카테고리 기반 새 채널 발굴 + 죽은 채널(영상 안 올라오는) 판별.

레퍼런스 랭킹은 사용자가 준 엑셀 목록에 고정돼 있다. 여기서는 그 목록 밖으로
확장한다:
  1) discover(): 카테고리 키워드로 인스타를 검색해 "내가 모르던 채널" 중
     최근 48h 릴스에 댓글이 빠르게 쌓이는 곳을 기존 랭킹엔진 그대로 캐치.
  2) find_inactive(): 수집 결과 릴스가 하나도 안 잡힌(=영상 안 올라오는) 채널을
     골라 삭제(추적 제외) 후보로 반환.

엔진(build_items/apply_grades/sort_by)·수집(fetch_reels)·검색(search_channels)은
전부 재사용하고, 이 모듈은 그것들을 엮는 순수 오케스트레이션만 담당한다
(의존성 주입 → 테스트 시 Apify 없이 검증 가능)."""
from datetime import datetime, timezone
from shopping_shorts.ranking import build_items, apply_grades, sort_by, hours_since


def _norm(u):
    return (u or "").strip().lstrip("@").lower()


def new_usernames(candidates, known, max_channels=15):
    """검색 후보 → 이미 아는 채널(known) 제외한 고유 username 리스트(입력 순서 보존).

    known: 소문자 정규화된 username 집합. candidates: [{username, ...}]."""
    known = {_norm(k) for k in known}
    seen = set()
    out = []
    for c in candidates:
        u = c.get("username")
        n = _norm(u)
        if not n or n in known or n in seen:
            continue
        seen.add(n)
        out.append(u)
        if len(out) >= max_channels:
            break
    return out


def _recent_counts(reels, now, window_hours):
    """owner_소문자 → 창(window) 이내 릴스 개수(최근 이틀 영상수 표시용)."""
    counts = {}
    for r in reels:
        owner = r.get("ownerUsername") or r.get("username")
        ts = r.get("timestamp")
        if not owner or not ts:
            continue
        try:
            age = hours_since(ts, now=now)
        except (ValueError, AttributeError):
            continue
        if 0 <= age <= window_hours:
            counts[owner.lower()] = counts.get(owner.lower(), 0) + 1
    return counts


def _rank_reels(reels, prev_comments, prev_delta, now, window_hours, profiles=None):
    """발굴 릴스 원본 → 지표·등급 채워 정렬. 발굴 채널은 엑셀 메타가 없으므로
    합성 메타를 만들되, 프로필 액터로 받은 팔로워(profiles)를 넣어 참여밀도까지
    계산되게 한다. 각 항목에 discovered=True, followers, recent_count 부착."""
    profiles = profiles or {}
    now = now or datetime.now(timezone.utc)
    counts = _recent_counts(reels, now, window_hours)
    items = []
    for r in reels:
        owner = r.get("ownerUsername") or r.get("username")
        if not owner:
            continue
        prof = profiles.get(owner.lower(), {})
        followers = int(prof.get("followers") or 0)
        meta = {"name": prof.get("full_name") or owner, "username": owner,
                "followers": followers, "inpock": ""}
        built = build_items([r], meta, prev_comments=prev_comments,
                            prev_delta=prev_delta, now=now, window_hours=window_hours)
        for it in built:
            it["discovered"] = True
            it["followers"] = followers
            it["recent_count"] = counts.get(owner.lower(), 0)
        items.extend(built)
    items = _one_per_channel(items)  # 채널 단위 — 채널당 대표 릴스 1개
    apply_grades(items)
    return sort_by(items, "comments")


def _one_per_channel(items):
    """채널당 댓글 최다 릴스 1개만 남긴다(채널 단위 발굴 — 같은 채널이 여러 릴스로
    중복 노출되지 않게, 2026-07-12). 최근2일 영상수(recent_count)는 채널 전체 값이라
    대표 릴스에 그대로 유지된다."""
    best = {}
    for it in items:
        u = (it.get("username") or "").lower()
        if u not in best or (it.get("comments") or 0) > (best[u].get("comments") or 0):
            best[u] = it
    return list(best.values())


def _owners(reels):
    """릴스 리스트의 고유 owner username(원형 유지, 중복 제거)."""
    seen, out = set(), []
    for r in reels:
        u = r.get("ownerUsername") or r.get("username")
        if u and u.lower() not in seen:
            seen.add(u.lower())
            out.append(u)
    return out


def discover(keyword, known, *, search_fn, fetch_reels_fn, profiles_fn=None,
             prev_comments, prev_delta, now=None, window_hours=48, max_channels=15):
    """카테고리 키워드 하나 → 발굴 랭킹 항목 리스트(댓글 내림차순).

    search_fn(keyword)->[{username,...}], fetch_reels_fn(usernames)->[reel,...],
    profiles_fn(usernames)->{username소문자:{followers,...}} (팔로워·참여밀도용)."""
    targets = new_usernames(search_fn(keyword), known, max_channels=max_channels)
    if not targets:
        return []
    reels = fetch_reels_fn(targets)
    profiles = profiles_fn(_owners(reels)) if profiles_fn else {}
    return _rank_reels(reels, prev_comments, prev_delta, now, window_hours, profiles)


def discover_multi(keywords, known, *, search_fn, fetch_reels_fn, profiles_fn=None,
                   prev_comments, prev_delta, now=None, window_hours=48,
                   max_channels_per=15, max_total=80):
    """여러 카테고리를 한 번에 → "업데이트" 한 번으로 새 채널들이 랭킹으로 정렬돼
    올라오게(2026-07-12). 카테고리별로 검색해 새 username을 모으되 전체에서
    중복 제거하고, 릴스 수집(fetch_reels)·프로필(fetch_profiles)은 각각 1회만 호출."""
    known_n = {_norm(k) for k in known}
    seen = set()
    targets = []
    for kw in keywords:
        for u in new_usernames(search_fn(kw), known_n | seen, max_channels=max_channels_per):
            n = _norm(u)
            if n in seen:
                continue
            seen.add(n)
            targets.append(u)
            if len(targets) >= max_total:
                break
        if len(targets) >= max_total:
            break
    if not targets:
        return []
    reels = fetch_reels_fn(targets)
    profiles = profiles_fn(_owners(reels)) if profiles_fn else {}
    return _rank_reels(reels, prev_comments, prev_delta, now, window_hours, profiles)


def find_inactive(channels, active_usernames):
    """엑셀 채널 목록 중 "영상 안 올라오는" 채널 = 이번 수집에서 릴스가 하나도
    안 잡힌 채널을 삭제 후보로 반환(입력 순서 보존).

    channels: [{name, username, ...}], active_usernames: 릴스가 잡힌 username 집합.
    둘 다 정규화(소문자·@제거)해 비교한다."""
    active = {_norm(u) for u in active_usernames}
    out = []
    for ch in channels:
        if _norm(ch.get("username")) not in active:
            out.append({"name": ch.get("name"), "username": ch.get("username")})
    return out
