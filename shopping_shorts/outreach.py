"""소통 큐 — 릴스+draft 결합, 3가지 정렬, 완료 필터. 순수 함수."""


def goldilocks_score(item):
    """방금 올라왔는데(age 낮음) 아직 댓글 적은(comments 낮음) 것이 높은 점수."""
    age = item.get("age_hours") or 0
    comments = item.get("comments") or 0
    return (1.0 / (1.0 + comments)) * (1.0 / (1.0 + age))


def _sort_key(sort):
    if sort in ("latest", "최신"):
        return lambda i: (i.get("age_hours") if i.get("age_hours") is not None else 1e9), False
    if sort in ("hot", "터진"):
        return lambda i: (i.get("speed") or 0), True
    if sort in ("goldilocks", "골디락스"):
        return goldilocks_score, True
    return lambda i: (i.get("age_hours") if i.get("age_hours") is not None else 1e9), False


def build_queue(items, drafts_map, commented, sort="latest", hide_done=True):
    """릴스 항목 → 소통 큐. draft 결합, 완료 표시/필터, 정렬 적용.

    - drafts_map: {shortcode: [댓글...]}  - commented: set(shortcode)
    - hide_done=True면 완료 항목 제외, False면 done 플래그만 달고 유지.
    """
    out = []
    for i in items:
        sc = i.get("shortcode", "")
        done = sc in commented
        if done and hide_done:
            continue
        item = dict(i)
        item["done"] = done
        item["drafts"] = drafts_map.get(sc, [])
        out.append(item)

    keyfn, reverse = _sort_key(sort)
    out.sort(key=keyfn, reverse=reverse)
    return out
