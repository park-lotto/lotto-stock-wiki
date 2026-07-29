"""인스타 신규 계정 발굴 — 해시태그 탐색(게시물 단위)을 작성자별로 집계해
'잘 나오는 계정' 리더보드를 만든다(2026-07-30, xiaohongshu_discovery.py와 동일 패턴).

- 점수 = 해시태그 등장 횟수(appear count) — 해시태그 검색 SERP엔 좋아요/댓글 수가
  없어(실측) 샤오홍슈처럼 참여도 합산은 못 한다. 대신 여러 해시태그에 걸쳐
  반복 등장하는 계정일수록 그 카테고리에서 활발하다고 본다.
- 최소 등장 2회(플루크 1차 필터)
- 블랙리스트(사장님이 쳐낸 계정) 영구 제외
- search_fn 주입 → 외부 IO 없는 순수 함수(단위 테스트 쉬움)
"""


def profile_url(username):
    return f"https://www.instagram.com/{username}/"


def discover_accounts(search_fn, hashtags_by_category, min_appear=2, blacklist=frozenset()):
    """카테고리별 해시태그 시드를 순회하며 검색 → username별 집계 → 리더보드.

    - search_fn(tag) -> [dict]  (instagram_playwright.search_hashtag 형태:
      username, full_name, is_verified, pk, code, url, taken_at)
    - hashtags_by_category: {카테고리: [해시태그...]} (공백·# 없는 순수 태그 문자열)
    - blacklist: 제외할 username 집합(소문자 비교)
    반환: 계정 dict 리스트, appear_count 내림차순.
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
                a = accounts.get(key)
                if a is None:
                    a = accounts[key] = {
                        "username": uname,
                        "full_name": it.get("full_name") or "",
                        "is_verified": bool(it.get("is_verified")),
                        "appear_count": 0,
                        "categories": set(),
                        "sample_url": it.get("url") or "",
                    }
                a["appear_count"] += 1
                a["categories"].add(cat)
                if it.get("full_name"):
                    a["full_name"] = it["full_name"]
                if it.get("is_verified"):
                    a["is_verified"] = True
                if it.get("url") and not a["sample_url"]:
                    a["sample_url"] = it["url"]

    out = []
    for a in accounts.values():
        if a["appear_count"] < min_appear:
            continue
        out.append({
            "username": a["username"],
            "full_name": a["full_name"],
            "is_verified": a["is_verified"],
            "profile_url": profile_url(a["username"]),
            "appear_count": a["appear_count"],
            "categories": sorted(a["categories"]),
            "sample_url": a["sample_url"],
        })
    out.sort(key=lambda x: x["appear_count"], reverse=True)
    return out
