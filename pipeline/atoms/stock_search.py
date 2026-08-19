"""검색 시점 종목명 정규화 — 적재(ingest)와 **같은 별칭 사전**을 쓴다.

## 왜 필요한가 (2026-08-15 실측)

별칭 정규화(`stock_resolve`)가 **적재 시점에만** 돌고, 검색은 raw 토큰을 그대로
`LIKE '%kw%'`에 넣고 있었다. 그래서 두 방향으로 다 샜다:

  ① **오염** — '현대차'로 긁으면 `현대차증권`(증권사)이 딸려온다.
     실측: 「현대차」 원자 519건 중 **58건(11%)이 현대차증권**이었다.
  ② **누락** — '하이닉스'로 치면 `SK하이닉스`로 저장된 원자를 놓친다
     (content에 우연히 '하이닉스'가 있는 것만 걸린다).

고치는 방법은 새 사전을 만드는 게 아니라 **이미 있는 정규화를 검색에도 태우는 것**이다.
`stock_aliases.json` 하나만 보므로 적재와 검색이 어긋날 수 없다(0순위-B).
"""
from __future__ import annotations

import re

from .telegram_registry import resolve_alias, _ALIASES  # 같은 사전을 공유한다
from .codemap import code_for

# 종목명 뒤에 붙어 **다른 회사**가 되는 접미사.
# '현대차' 검색에 '현대차증권'이 섞이는 게 대표 사례다. 접두어가 같을 뿐 다른 법인이다.
_OTHER_ENTITY_SUFFIX = (
    "증권", "투자증권", "자산운용", "캐피탈", "카드", "해상", "화재", "생명",
    "은행", "저축은행", "인베스트먼트", "리서치", "파트너스", "홀딩스에너지",
)

# 이 글자 수 이하로는 접두어 오염을 걸러도 남는 게 너무 많다 — 화면에 경고를 띄우기 위한 값.
_TOO_SHORT = 2


def canonical_name(q: str) -> str:
    """검색어 → 정규화된 종목명. '하이닉스' → 'SK하이닉스'."""
    return resolve_alias((q or "").strip())


def expand_terms(q: str) -> list[str]:
    """검색에 쓸 문자열들. 정규화명 + 원문 + **역방향 별칭**.

    역방향이 핵심이다 — 'SK하이닉스'로 저장된 원자를 찾으려면 '하이닉스'도 같이 봐야
    content 안에서 줄여 부른 발언까지 걸린다.
    """
    raw = (q or "").strip()
    if not raw:
        return []
    canon = canonical_name(raw)
    terms = [canon]
    if raw != canon:
        terms.append(raw)
    # 같은 정규명을 가리키는 다른 별칭들도 검색어에 넣는다
    low_canon = canon.lower()
    for alias, target in _ALIASES.items():
        if target.lower() == low_canon and alias.lower() not in (t.lower() for t in terms):
            terms.append(alias)
    return terms


def exclusion_terms(q: str) -> list[str]:
    """제외할 문자열들. 정규화명 + 다른법인 접미사 조합.

    '현대차' → ['현대차증권', '현대차투자증권', ...]. 접두어가 같은 **다른 회사**만 걸러낸다.
    실제로 없는 조합('삼성전자증권')이 섞여도 무해하다 — 매칭될 원자가 없다.
    """
    canon = canonical_name(q)
    if not canon:
        return []
    return [canon + suf for suf in _OTHER_ENTITY_SUFFIX]


def is_too_short(q: str) -> bool:
    """'현대'처럼 짧으면 현대차·현대건설·현대백화점이 다 걸린다 — 화면에서 경고할 것."""
    return len(canonical_name(q)) <= _TOO_SHORT


def build_where(q: str, *, since: str = "") -> tuple[str, list]:
    """원자 검색용 WHERE 절과 파라미터.

    - 포함: asset / content 중 한 곳이라도 검색어를 담은 원자
    - 제외: 접두어가 같은 다른 법인(content·source_name 양쪽에서)
    """
    terms = expand_terms(q)
    if not terms:
        return "0", []

    params: list = []
    ors = []
    for t in terms:
        ors.append("(asset LIKE ? OR content LIKE ?)")
        params += [f"%{t}%", f"%{t}%"]
    where = "(" + " OR ".join(ors) + ")"

    for ex in exclusion_terms(q):
        where += " AND content NOT LIKE ? AND (source_name IS NULL OR source_name NOT LIKE ?)"
        params += [f"%{ex}%", f"%{ex}%"]

    if since:
        where += " AND date >= ?"
        params.append(since)
    return where, params


_WORD = re.compile(r"[가-힣A-Za-z0-9]+")


def relevance(row_asset: str, row_content: str, q: str) -> int:
    """연관도. 높을수록 이 종목 얘기일 가능성이 크다.

    `asset`에 잡힌 것이 가장 확실하다 — 원자화가 '이 발언의 대상 종목'으로 지목한 값이다.
    content에만 있으면 지나가는 언급일 수 있다.
    """
    terms = [t.lower() for t in expand_terms(q)]
    a = (row_asset or "").lower()
    c = (row_content or "").lower()
    score = 0
    for t in terms:
        if not t:
            continue
        if a == t:
            score += 10          # asset 정확 일치
        elif t in a:
            score += 6           # asset에 포함 ("삼성전자, SK하이닉스")
        if t in c:
            score += 2           # 본문 언급
    return score


def search(conn, q: str, *, since: str = "", limit: int = 400) -> list[dict]:
    """정규화·오염제외·연관도 정렬까지 끝낸 원자 목록."""
    where, params = build_where(q, since=since)
    rows = conn.execute(
        f"""SELECT id, date, source_type, source_name, raw_file, sector, asset, signal,
                   content, speaker, yt_timestamp, msg_ts, deeplink, source_trust
            FROM atoms WHERE {where}
            ORDER BY date DESC LIMIT ?""",
        params + [limit * 2],
    ).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        d["rel"] = relevance(d.get("asset"), d.get("content"), q)
        out.append(d)
    # 연관도 우선, 같으면 최신순 (sorted는 안정 정렬이라 날짜 → 연관도 순으로 두 번)
    out.sort(key=lambda d: d.get("date") or "", reverse=True)
    out.sort(key=lambda d: d["rel"], reverse=True)
    return out[:limit]
