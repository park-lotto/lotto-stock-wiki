"""자연어 검색 — Gemini가 문장을 분석해 검색 전략(키워드·정렬·필터)을 짜고,
find_and_rank() 결과를 다시 의도에 맞게 재랭킹한다.
호출#1(분석)·호출#2(재랭킹) 둘 다 실패해도 항상 안전한 결과를 반환한다
(폴백: 원문 그대로 검색 / 재랭킹 생략)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import hot_clips
import gemini_client as G

_SORT_OPTIONS = ("view_per_sub", "views_per_day", "engage_pct", "view_count", "heat")


def analyze_query(sentence: str, base_days: int, base_shorts: bool, base_news: bool) -> dict:
    """문장 → {keywords, sort, days, exclude_shorts, exclude_news, reasoning}.
    Gemini 실패/이상 응답이면 폴백 dict(원문 그대로 검색) 반환 — 예외를 던지지 않는다."""
    fallback = {
        "keywords": [sentence], "sort": "view_per_sub",
        "days": base_days, "exclude_shorts": base_shorts, "exclude_news": base_news,
        "reasoning": "", "ai_ok": False,
    }
    prompt = f"""사용자가 유튜브 레퍼런스 검색창에 아래 문장을 입력했다:
"{sentence}"

이 문장의 의도를 분석해서 실제 유튜브 검색에 쓸 전략을 JSON으로 짜라.

1. keywords: 이 문장을 2~4개의 실제 유튜브 검색어로 분해하라. 각각은 유튜브에 직접 쳐서
   결과가 나올만한 짧고 구체적인 한국어 키워드여야 한다(예: "반도체 급등", "HBM 수혜주").
   문장을 그대로 복사하지 말 것.
2. sort: 다음 중 하나만 선택 — {", ".join(_SORT_OPTIONS)}.
   view_per_sub=구독자 대비 배수(소재가 캐리했는지), views_per_day=최근 화제성(속도),
   engage_pct=참여율(내용이 좋아서 반응했는지), view_count=단순 조회수,
   heat=구독자 대비 하루 속도(급상승). "제일 좋은/반응좋은"류는 engage_pct,
   "터진/화제"는 view_per_sub나 heat, "요즘 뜨는"은 views_per_day나 heat 추천.
3. days: 문장에 기간 언급 있으면 그 값(30/90/180/365 중 가장 가까운 것), 없으면 {base_days} 유지.
4. exclude_shorts: 문장에 "쇼츠 말고"/"긴 영상만" 등 있으면 true, 없으면 {base_shorts} 유지.
5. exclude_news: 문장에 "뉴스도 포함" 등 있으면 false, 없으면 {base_news} 유지.
6. reasoning: 왜 이렇게 해석했는지 한국어 한 문장(사용자에게 그대로 보여줄 것).

JSON만 출력. 예: {{"keywords": ["...", "..."], "sort": "engage_pct", "days": 90, "exclude_shorts": true, "exclude_news": true, "reasoning": "..."}}"""
    try:
        d = G.call_json(prompt)
        keywords = [str(k).strip() for k in (d.get("keywords") or []) if str(k).strip()]
        if not keywords:
            return fallback
        sort = d.get("sort") if d.get("sort") in _SORT_OPTIONS else "view_per_sub"
        return {
            "keywords": keywords[:4],
            "sort": sort,
            "days": int(d.get("days", base_days) or base_days),
            "exclude_shorts": bool(d.get("exclude_shorts", base_shorts)),
            "exclude_news": bool(d.get("exclude_news", base_news)),
            "reasoning": str(d.get("reasoning", "")).strip(),
            "ai_ok": True,
        }
    except Exception:
        return fallback


def rerank(sentence: str, rows: list[dict]) -> "list[str] | None":
    """검색 결과를 사용자 의도에 맞는 순서로 재배열 — video_id 리스트 반환.
    실패하거나 응답이 불완전하면 None(재랭킹 생략, 호출측이 기존 순서 유지)."""
    if not rows:
        return None
    cand = rows[:50]
    lines = []
    for i, r in enumerate(cand):
        lines.append(
            f"{i}: {r.get('title','')} / 구독자{r.get('subscriber_count',0):,} / "
            f"배수{r.get('view_per_sub',0)}x / 참여율{r.get('engage_pct',0)}% / "
            f"{r.get('days_since',0)}일전"
        )
    prompt = f"""사용자 검색 의도: "{sentence}"

아래는 이미 필터링된 유튜브 영상 후보 목록이다(번호: 제목 / 구독자 / 배수 / 참여율 / 게시시점):
{chr(10).join(lines)}

사용자 의도에 가장 잘 맞는 순서대로 번호만 나열하라. 후보 전부를 좋은 순서로 포함해야 한다.
JSON만 출력: {{"order": [3, 1, 5, 2, ...]}}"""
    try:
        d = G.call_json(prompt)
        order = d.get("order")
        if not isinstance(order, list) or not order:
            return None
        seen = set()
        ids = []
        for idx in order:
            if isinstance(idx, int) and 0 <= idx < len(cand) and idx not in seen:
                seen.add(idx)
                ids.append(cand[idx]["video_id"])
        # 응답에서 빠진 후보는 뒤에 원래 순서대로 붙임(재랭킹 누락분 유실 방지)
        for i, r in enumerate(cand):
            if i not in seen:
                ids.append(r["video_id"])
        return ids
    except Exception:
        return None


def ai_search(sentence: str, base_days: int = 0, base_shorts: bool = False,
              base_news: bool = True) -> dict:
    """오케스트레이터: 분석 → find_and_rank → 재랭킹. 항상 {results, analysis} 반환."""
    analysis = analyze_query(sentence, base_days, base_shorts, base_news)
    rows = hot_clips.find_and_rank(
        analysis["keywords"], days=analysis["days"],
        exclude_shorts=analysis["exclude_shorts"], exclude_news=analysis["exclude_news"],
        sort=analysis["sort"],
    )
    order = rerank(sentence, rows) if analysis["ai_ok"] else None
    if order:
        by_id = {r["video_id"]: r for r in rows}
        rows = [by_id[vid] for vid in order if vid in by_id]
        for i, r in enumerate(rows):
            r["ai_rank"] = i
        analysis["reranked"] = True
    else:
        for i, r in enumerate(rows):
            r["ai_rank"] = i
        analysis["reranked"] = False
    return {"results": rows, "analysis": analysis}
