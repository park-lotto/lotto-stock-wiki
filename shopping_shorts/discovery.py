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
from shopping_shorts.ranking import build_items, apply_grades, sort_by


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


def discover(keyword, known, *, search_fn, fetch_reels_fn,
             prev_comments, prev_delta, now=None, window_hours=48, max_channels=15):
    """카테고리 키워드 → 발굴 랭킹 항목 리스트(댓글 내림차순).

    search_fn(keyword)->[{username,...}], fetch_reels_fn(usernames)->[reel,...].
    발굴 채널은 엑셀 메타(팔로워/인포크)가 없으므로 username 기반 합성 메타를
    만든다 — 팔로워 미상이라 참여밀도(density)는 0이 되지만 댓글수·속도·가속으로
    충분히 랭킹된다. 각 항목에 discovered=True 표시."""
    candidates = search_fn(keyword)
    targets = new_usernames(candidates, known, max_channels=max_channels)
    if not targets:
        return []
    reels = fetch_reels_fn(targets)
    items = []
    for r in reels:
        owner = r.get("ownerUsername") or r.get("username")
        if not owner:
            continue
        meta = {"name": owner, "username": owner,
                "followers": int(r.get("ownerFollowersCount") or 0), "inpock": ""}
        built = build_items([r], meta, prev_comments=prev_comments,
                            prev_delta=prev_delta, now=now, window_hours=window_hours)
        for it in built:
            it["discovered"] = True
        items.extend(built)
    apply_grades(items)
    return sort_by(items, "comments")


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
