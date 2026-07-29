"""인스타 신규 계정 발굴 — 해시태그 탐색(게시물 단위)을 작성자별로 집계해
'잘하는 계정' 리더보드를 만든다(2026-07-30, xiaohongshu_discovery.py와 동일 패턴으로
참여도 합산 — 최초 버전은 등장횟수만 셌으나, 샤오홍슈처럼 좋아요·댓글수까지
반영해야 신호가 정확하다는 지적을 반영해 교체).

- 점수 = Σ(게시물 참여도), 참여도 = 좋아요+댓글(+조회수는 플랫폼 특성상 별도 표시,
  합산엔 과체중이라 제외 — 조회수는 자릿수가 좋아요·댓글보다 훨씬 커서 그대로 더하면
  참여도 합계가 조회수에 압도된다)
- 최소 게시물 2개(플루크 1차 필터)
- 블랙리스트(사장님이 쳐낸 계정) 영구 제외
- search_fn 주입 → 외부 IO 없는 순수 함수(단위 테스트 쉬움)
"""


def profile_url(username):
    return f"https://www.instagram.com/{username}/"


def _post_engagement(item):
    """게시물 참여도 = 좋아요+댓글. 없는 필드는 0."""
    return int(item.get("like_count") or 0) + int(item.get("comment_count") or 0)


def discover_accounts(search_fn, hashtags_by_category, min_posts=2, blacklist=frozenset()):
    """카테고리별 해시태그 시드를 순회하며 검색 → username별 집계 → 리더보드.

    - search_fn(tag) -> [dict]  (instagram_playwright.search_hashtag 형태:
      username, full_name, is_verified, pk, code, url, taken_at,
      like_count, comment_count, play_count)
    - hashtags_by_category: {카테고리: [해시태그...]} (공백·# 없는 순수 태그 문자열)
    - blacklist: 제외할 username 집합(소문자 비교)
    반환: 계정 dict 리스트, engagement_sum 내림차순.
    """
    bl = {str(x).lower() for x in blacklist}
    accounts = {}
    for cat, tags in hashtags_by_category.items():
        for tag in tags or []:
            try:
                items = search_fn(tag) or []
            except Exception:
                # 해시태그 하나 실패(브라우저 닫힘·차단·타임아웃)가 전체 발굴을
                # 죽이지 않게 건너뛴다. 되는 태그만큼은 결과를 낸다(부분 성공).
                continue
            for it in items:
                uname = (it.get("username") or "").strip()
                key = uname.lower()
                if not key or key in bl:
                    continue
                eng = _post_engagement(it)
                views = int(it.get("play_count") or 0)
                a = accounts.get(key)
                if a is None:
                    a = accounts[key] = {
                        "username": uname,
                        "full_name": it.get("full_name") or "",
                        "is_verified": bool(it.get("is_verified")),
                        "post_count": 0,
                        "engagement_sum": 0,
                        "view_sum": 0,
                        "categories": set(),
                        "sample_url": it.get("url") or "",
                        "_best_eng": -1,
                    }
                a["post_count"] += 1
                a["engagement_sum"] += eng
                a["view_sum"] += views
                a["categories"].add(cat)
                if it.get("full_name"):
                    a["full_name"] = it["full_name"]
                if it.get("is_verified"):
                    a["is_verified"] = True
                if eng >= a["_best_eng"]:   # 가장 반응 좋은 게시물을 대표(링크)로
                    a["_best_eng"] = eng
                    a["sample_url"] = it.get("url") or a["sample_url"]

    out = []
    for a in accounts.values():
        n = a["post_count"]
        if n < min_posts:
            continue
        out.append({
            "username": a["username"],
            "full_name": a["full_name"],
            "is_verified": a["is_verified"],
            "profile_url": profile_url(a["username"]),
            "post_count": n,
            "engagement_sum": a["engagement_sum"],
            "avg_engagement": round(a["engagement_sum"] / n, 1),
            "view_sum": a["view_sum"],
            "categories": sorted(a["categories"]),
            "sample_url": a["sample_url"],
        })
    out.sort(key=lambda x: x["engagement_sum"], reverse=True)
    return out
