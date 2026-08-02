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
from concurrent.futures import ThreadPoolExecutor
from shopping_shorts.ranking import build_items, apply_grades, sort_by, hours_since

# 인물채널 판정에 쓸 채널당 썸네일 표본 수(2026-08-02).
FACE_SAMPLE_N = 3


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
            it["bio"] = prof.get("biography") or ""   # 카테고리 약한 보조신호(추가 호출 0)
            it["recent_count"] = counts.get(owner.lower(), 0)
        items.extend(built)
    # 채널당 썸네일 여러 장을 대표 릴스에 실어둔다(2026-08-02) — 인물채널 판정은
    # 영상 단위로 갈리므로(실측: toyland.kr 제품1·얼굴2) 한 장으로 채널을 자르면
    # 오판이 난다. _one_per_channel이 대표 1개만 남기기 전에 모아둬야 한다.
    thumbs = {}
    for it in items:
        u = (it.get("username") or "").lower()
        t = it.get("thumbnail")
        if t and len(thumbs.setdefault(u, [])) < FACE_SAMPLE_N:
            thumbs[u].append(t)
    items = _one_per_channel(items)  # 채널 단위 — 채널당 대표 릴스 1개
    for it in items:
        it["sample_thumbs"] = thumbs.get((it.get("username") or "").lower(), [])
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


def _safe_profiles(profiles_fn, reels):
    """팔로워 조회(부가 데이터)는 실패해도 발굴을 죽이지 않는다 — 프로필 액터가
    403(렌탈 소진)·오류여도 빈 dict로 넘어가 채널 랭킹은 그대로 반환(2026-07-12,
    프로필 403이 업데이트 전체를 죽이던 버그)."""
    if not profiles_fn:
        return {}
    try:
        return profiles_fn(_owners(reels))
    except Exception:
        return {}


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
    profiles = _safe_profiles(profiles_fn, reels)
    return _rank_reels(reels, prev_comments, prev_delta, now, window_hours, profiles)


def discover_multi(keywords, known, *, search_fn, fetch_reels_fn, profiles_fn=None,
                   prev_comments, prev_delta, now=None, window_hours=48,
                   max_channels_per=12, max_total=40, search_workers=6):
    """여러 카테고리를 한 번에 → "업데이트" 한 번으로 새 채널들이 랭킹으로 정렬돼
    올라오게(2026-07-12). 카테고리 검색은 병렬로 돌려 전체 소요시간을 가장 느린
    한 카테고리 수준으로 줄인다(순차로 돌면 6개 합이 몇 분 걸려 서버 재시작에
    걸려 죽던 문제, 2026-07-12). 릴스 수집·프로필은 각각 1회만 호출.

    search_workers: 검색 동시성 상한(기본 6=기존 동작 그대로, Apify는 계정별
    HTTP라 병렬이 안전). search_fn이 Playwright처럼 로컬 브라우저를 여는 경우
    search_workers=1로 순차 실행해야 한다 — 2026-07-30 실측: 6개 동시 실행 시
    브라우저 자원 경합으로 일부 태그가 조용히 0건이 났다(에러 없이, 세션이나
    CPU 스케줄링 경합으로 추정)."""
    with ThreadPoolExecutor(max_workers=min(search_workers, len(keywords) or 1)) as pool:
        results = list(pool.map(search_fn, keywords))  # 입력 순서 보존
    known_n = {_norm(k) for k in known}
    seen = set()
    targets = []
    found_by = {}          # username소문자 → 이 채널을 찾아낸 해시태그(카테고리 힌트)
    for keyword, cands in zip(keywords, results):
        for u in new_usernames(cands, known_n | seen, max_channels=max_channels_per):
            n = _norm(u)
            if n in seen:
                continue
            seen.add(n)
            found_by[n] = keyword
            targets.append(u)
            if len(targets) >= max_total:
                break
        if len(targets) >= max_total:
            break
    if not targets:
        return []
    reels = fetch_reels_fn(targets)
    profiles = _safe_profiles(profiles_fn, reels)
    items = _rank_reels(reels, prev_comments, prev_delta, now, window_hours, profiles)
    # 어느 태그에서 나온 채널인지 항목에 실어 보낸다(2026-07-30) — 자동등록이 이걸
    # 카테고리로 쓴다. 신규 채널은 이력도 캡션도 없어 '기타'로만 들어오던 문제.
    for it in items:
        it["discover_tag"] = found_by.get(_norm(it.get("username")), "")
    return items


def merge_feeds(prev, new, cap=None, now=None, ttl_days=None):
    """누적 모드 — 이전 발굴 피드에 새 결과를 채널 단위로 합친다(2026-07-12).
    같은 채널(username)은 새 데이터로 갱신(최신 지표), 나머지 이전 채널은 유지.
    새로 발굴된 채널이 위로 오도록 new 먼저, 그 뒤 겹치지 않는 prev.

    ttl_days 지정 시 **마지막으로 발굴에 잡힌 시점(last_seen)에서 그 일수만큼만
    보존**하고 넘긴 채널은 떨어뜨린다(2026-07-30, 사장님 지시 "채널은 누적개념으로
    3일간 보존"). 매 병합에서 new에 들어온 채널은 last_seen이 now로 갱신되므로,
    계속 잡히는 채널은 계속 남고 3일간 한 번도 안 잡힌 채널만 빠진다. last_seen이
    없는 옛 항목은 이번 실행 시각으로 간주해 한 번은 살려둔다(마이그레이션).

    cap 지정 시 병합 후 댓글수(comments) 내림차순 상위 cap개만 남긴다(2026-07-13
    — 매일 누적만 하고 트리밍이 없어 무한정 커지던 문제 해결. 댓글수 낮은
    채널이 자연스럽게 밀려서 빠지는 로테이션 효과)."""
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat()
    new_keys = {(_norm(i.get("username"))) for i in new}
    out = []
    for i in new:
        i = dict(i)
        i["last_seen"] = stamp
        out.append(i)
    for i in prev:
        if _norm(i.get("username")) in new_keys:
            continue
        if ttl_days and _age_days(i.get("last_seen"), now, default=0.0) > ttl_days:
            continue
        i = dict(i)
        i.setdefault("last_seen", stamp)
        out.append(i)
    if cap:
        out = sorted(out, key=lambda i: i.get("comments") or 0, reverse=True)[:cap]
    return out


def _age_days(last_seen, now, default=0.0):
    """last_seen(ISO 문자열) → now까지 경과 일수. 없거나 못 읽으면 default."""
    if not last_seen:
        return default
    try:
        dt = datetime.fromisoformat(str(last_seen))
    except (ValueError, TypeError):
        return default
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 86400.0


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
