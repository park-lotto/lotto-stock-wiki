"""샤오홍슈 계정 발굴 — 검색 발굴(포스트 단위)을 작성자별로 집계해 '잘하는 계정'
리더보드를 만든다. 새 크롤러 없이 xiaohongshu_search 결과만 재집계한다.

설계: docs/superpowers/specs/2026-07-29-샤오홍슈-계정발굴-design.md
- 점수 = Σ(노트 참여도), 참여도 = 좋아요+댓글+수집+공유
- 최소 노트 2개(플루크·쓰레기 1차 필터)
- 블랙리스트(사장님이 쳐낸 계정) 영구 제외
- search_fn 주입 → 외부 IO 없는 순수 함수(단위 테스트 쉬움)
"""

_PROFILE_BASE = "https://www.rednote.com/user/profile/"  # xiaohongshu.com은 지역차단→rednote


def profile_url(userid):
    return _PROFILE_BASE + str(userid)


def _note_engagement(note):
    """노트 참여도 = 좋아요+댓글+수집+공유. 없는 필드는 0."""
    return (int(note.get("likes") or 0)
            + int(note.get("comments") or 0)
            + int(note.get("collects") or 0)
            + int(note.get("shares") or 0))


def discover_accounts(search_fn, seeds_by_category, min_notes=2,
                      blacklist=frozenset(), keyword_field="cn"):
    """카테고리 시드팩을 순회하며 검색 → userid별 집계 → 리더보드.

    - search_fn(keyword) -> [note dict]  (xiaohongshu_search.search_full 형태:
      channel_id, channel_title, likes/comments/collects/shares, url, thumbnail)
    - seeds_by_category: {카테고리: {keyword_field: [키워드...]}}  (overseas_seeds)
    - blacklist: 제외할 userid 집합
    반환: 계정 dict 리스트, engagement_sum 내림차순.
    """
    bl = set(str(x) for x in blacklist)
    accounts = {}
    for cat, packs in seeds_by_category.items():
        for kw in (packs or {}).get(keyword_field, []) or []:
            try:
                notes = search_fn(kw) or []
            except Exception:
                # 한 키워드 검색 실패(브라우저 닫힘·차단·타임아웃 등)가 전체 발굴을
                # 죽이지 않게 건너뛴다. 되는 키워드만큼은 결과를 낸다(부분 성공).
                continue
            for note in notes:
                uid = str(note.get("channel_id") or "")
                if not uid or uid in bl:
                    continue  # userid 없으면 계정 집계 불가(닉네임은 바뀔 수 있어 키로 못 씀)
                eng = _note_engagement(note)
                a = accounts.get(uid)
                if a is None:
                    a = accounts[uid] = {
                        "userid": uid,
                        "nickname": note.get("channel_title") or "",
                        "note_count": 0,
                        "engagement_sum": 0,
                        "categories": set(),
                        "sample_url": note.get("url") or "",
                        "sample_thumbnail": note.get("thumbnail") or "",
                        "_best_eng": -1,
                    }
                a["note_count"] += 1
                a["engagement_sum"] += eng
                a["categories"].add(cat)
                if eng >= a["_best_eng"]:  # 가장 잘된 노트를 대표(썸네일·링크)로
                    a["_best_eng"] = eng
                    a["sample_url"] = note.get("url") or a["sample_url"]
                    a["sample_thumbnail"] = note.get("thumbnail") or a["sample_thumbnail"]
                    if note.get("channel_title"):
                        a["nickname"] = note["channel_title"]

    out = []
    for a in accounts.values():
        if a["note_count"] < min_notes:
            continue
        n = a["note_count"]
        out.append({
            "userid": a["userid"],
            "nickname": a["nickname"],
            "profile_url": profile_url(a["userid"]),
            "note_count": n,
            "engagement_sum": a["engagement_sum"],
            "avg_engagement": round(a["engagement_sum"] / n, 1),
            "categories": sorted(a["categories"]),
            "sample_url": a["sample_url"],
            "sample_thumbnail": a["sample_thumbnail"],
        })
    out.sort(key=lambda x: x["engagement_sum"], reverse=True)
    return out
