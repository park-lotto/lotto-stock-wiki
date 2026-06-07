"""
query.py — 원자 검색 (벡터 의미검색 + SQL 키워드검색 하이브리드)

사용법:
    python -m pipeline.atoms.query "반도체 지금 어때?"            # 벡터 검색
    python -m pipeline.atoms.query "잠수함 FLNG" --sql           # SQL 키워드 검색
    python -m pipeline.atoms.query "조선 수주" --hybrid           # 벡터+SQL 병합
    python -m pipeline.atoms.query "오늘 리스크" --signal bearish --n 20
    python -m pipeline.atoms.query "반도체" --trust B --min-length 40
"""
import sys
import io
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .db import init_db, get_conn
from .vector_db import query_similar

_SIGNAL_KO = {
    "bullish": "[상승]",
    "bearish": "[하락]",
    "neutral": "[중립]",
    "risk": "[리스크]",
    "catalyst": "[촉매]",
    "conflict": "[충돌]",
    "data": "[데이터]",
}
_TRUST_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def _fmt_atom(a: dict, rank: int, mode: str = "") -> str:
    score = a.get("similarity_score", 0)
    score_str = f"{score:.3f}" if score else "SQL "
    date = a.get("date", "")
    sector = a.get("sector", "")
    asset = a.get("asset", "")
    signal = _SIGNAL_KO.get(a.get("signal", ""), a.get("signal", ""))
    trust = a.get("source_trust", "")
    source = a.get("source_name", "")
    content = a.get("content", "")
    short = content[:120] + ("..." if len(content) > 120 else "")
    tag = f"[{mode}] " if mode else ""
    return (
        f"\n[{rank:02d}] {tag}{score_str} | {date} | {sector}/{asset} | "
        f"{signal}[{trust}] {source}\n    {short}"
    )


def _sql_search(
    keywords: list[str],
    n: int = 10,
    sector: str = None,
    signal: str = None,
    trust_limit: int = 99,
    min_length: int = 20,
    days: int = None,
    or_mode: bool = False,   # True = 키워드 중 하나라도 매치, False = 모두 매치
) -> list[dict]:
    """키워드 기반 SQL 검색 — content/asset/sector LIKE 조건."""
    from datetime import date, timedelta
    conn = get_conn()

    conditions = ["is_active=1"]
    params = []

    # 키워드: or_mode=True면 OR, False면 AND
    kw_clauses = []
    for kw in keywords:
        kw_clauses.append(
            "(content LIKE ? OR asset LIKE ? OR sector LIKE ? OR source_name LIKE ?)"
        )
        params += [f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%"]
    if kw_clauses:
        joiner = " OR " if or_mode else " AND "
        conditions.append(f"({joiner.join(kw_clauses)})")

    if sector:
        conditions.append("sector LIKE ?")
        params.append(f"%{sector}%")
    if signal:
        conditions.append("signal = ?")
        params.append(signal)
    if trust_limit < 99:
        allowed = [k for k, v in _TRUST_ORDER.items() if v <= trust_limit]
        placeholders = ",".join("?" * len(allowed))
        conditions.append(f"source_trust IN ({placeholders})")
        params.extend(allowed)
    if min_length:
        conditions.append(f"LENGTH(content) >= {min_length}")
    if days:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conditions.append("date >= ?")
        params.append(cutoff)

    where_str = " AND ".join(conditions)
    rows = conn.execute(
        f"SELECT * FROM atoms WHERE {where_str} ORDER BY date DESC, strength_score DESC LIMIT ?",
        params + [n],
    ).fetchall()
    conn.close()

    atoms = []
    for r in rows:
        a = dict(r)
        a["similarity_score"] = 0.0  # SQL 검색은 유사도 없음
        atoms.append(a)
    return atoms


def run_query(
    question: str,
    n: int = 10,
    sector: str = None,
    signal: str = None,
    trust: str = None,
    min_length: int = 20,
    min_score: int = 0,
    mode: str = "vector",   # "vector" | "sql" | "hybrid"
    days: int = None,       # 최근 N일만 (SQL/hybrid 모드)
) -> list[dict]:
    init_db()

    trust_limit = _TRUST_ORDER.get(trust, 99) if trust else 99

    def _apply_filters(atoms: list[dict]) -> list[dict]:
        return [
            a for a in atoms
            if len(a.get("content", "")) >= min_length
            and _TRUST_ORDER.get(a.get("source_trust", "D"), 3) <= trust_limit
            and a.get("strength_score", 0) >= min_score
        ]

    filters = []
    if sector:   filters.append(f"섹터={sector}")
    if signal:   filters.append(f"신호={signal}")
    if trust:    filters.append(f"신뢰도≤{trust}")
    if days:     filters.append(f"최근{days}일")
    filter_str = f" [{', '.join(filters)}]" if filters else ""

    if mode == "sql":
        keywords = [w for w in question.split() if len(w) >= 2]
        atoms = _sql_search(keywords, n=n * 2, sector=sector, signal=signal,
                            trust_limit=trust_limit, min_length=min_length, days=days)
        filtered = _apply_filters(atoms)[:n]
        print(f"\n[SQL] 키워드: {question}{filter_str}")
        print(f"결과 {len(filtered)}개:\n{'='*70}")
        for i, a in enumerate(filtered, 1):
            print(_fmt_atom(a, i, "SQL"))

    elif mode == "hybrid":
        # 벡터 검색
        fetch_n = max(n * 3, 30)
        vec_atoms = query_similar(question, n_results=fetch_n, sector=sector, signal=signal)
        vec_filtered = _apply_filters(vec_atoms)[:n]

        # SQL 검색 (키워드 분해)
        keywords = [w for w in question.split() if len(w) >= 2]
        sql_atoms = _sql_search(keywords, n=n, sector=sector, signal=signal,
                                trust_limit=trust_limit, min_length=min_length, days=days)
        sql_filtered = _apply_filters(sql_atoms)[:n]

        # 병합: 벡터 결과 우선, SQL 전용 결과 추가
        seen_ids = {a["id"] for a in vec_filtered}
        sql_only = [a for a in sql_filtered if a["id"] not in seen_ids]
        merged = vec_filtered + sql_only

        print(f"\n[HYBRID] {question}{filter_str}")
        print(f"벡터 {len(vec_filtered)}개 + SQL추가 {len(sql_only)}개 = 총 {len(merged)}개:\n{'='*70}")
        for i, a in enumerate(vec_filtered, 1):
            print(_fmt_atom(a, i, "VEC"))
        for i, a in enumerate(sql_only, len(vec_filtered) + 1):
            print(_fmt_atom(a, i, "SQL+"))
        filtered = merged

    else:  # vector (기본)
        fetch_n = max(n * 3, 30)
        atoms = query_similar(question, n_results=fetch_n, sector=sector, signal=signal)
        filtered = _apply_filters(atoms)[:n]
        print(f"\n질문: {question}{filter_str}")
        print(f"관련 원자 {len(filtered)}개 (검색 {len(atoms)}개 중 필터):\n{'='*70}")
        for i, a in enumerate(filtered, 1):
            print(_fmt_atom(a, i))

    print("=" * 70)
    return filtered


def run_topic(
    keywords: list[str],
    trust: str = "B",
    min_length: int = 40,
    days: int = None,
) -> list[dict]:
    """섹터/주제 전수 추출 모드 — SQL로 관련 원자 전체 꺼내고 품질 필터링.

    벡터 유사도 랭킹 없이, 키워드 매칭 → 신뢰도/길이 필터 → 날짜 최신순 정렬.
    분석용 리포트 생성 전 1차 데이터 확보에 사용.
    """
    init_db()
    trust_limit = _TRUST_ORDER.get(trust, 99) if trust else 99
    # 1차: OR 조건으로 광범위 추출
    atoms = _sql_search(
        keywords, n=500,
        trust_limit=trust_limit, min_length=min_length, days=days,
        or_mode=True,
    )
    # 2차: 노이즈 제거 — "조선일보" 등 키워드 우연 매칭 제거
    #   sector나 asset에 키워드가 있거나, content 안에 2개 이상 매칭되는 것만 유지
    def _relevance(a: dict) -> bool:
        combined = (a.get("sector","") + a.get("asset","")).lower()
        content = a.get("content","").lower()
        hits = sum(1 for kw in keywords if kw.lower() in combined or kw.lower() in content)
        # sector/asset에 직접 키워드 있으면 바로 통과
        if any(kw.lower() in combined for kw in keywords):
            return True
        # content에만 있는 경우 2회 이상 매칭 필요
        return hits >= 2
    atoms = [a for a in atoms if _relevance(a)]

    # 내용 중복 제거 (앞 80자 기준)
    seen = set()
    deduped = []
    for a in atoms:
        key = a.get("content", "")[:80].strip()
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    filters = [f"키워드: {' + '.join(keywords)}", f"신뢰도≤{trust}", f"길이≥{min_length}"]
    if days:
        filters.append(f"최근{days}일")

    print(f"\n[TOPIC] {', '.join(filters)}")
    print(f"전수 추출 {len(atoms)}개 → 중복 제거 후 {len(deduped)}개:\n{'='*70}")
    for i, a in enumerate(deduped, 1):
        print(_fmt_atom(a, i, "TOPIC"))
    print("=" * 70)
    return deduped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="원자 의미·키워드 하이브리드 검색")
    parser.add_argument("question", help="검색 질문 또는 키워드 (공백 구분 시 AND 조건)")
    parser.add_argument("--n", type=int, default=10, help="결과 수 (기본 10)")
    parser.add_argument("--sector", default=None, help="섹터 필터")
    parser.add_argument("--signal", default=None, help="신호 필터 (bullish/bearish 등)")
    parser.add_argument("--trust", default=None, help="신뢰도 상한 (A/B/C/D)")
    parser.add_argument("--min-length", type=int, default=20, help="content 최소 글자 수 (기본 20)")
    parser.add_argument("--min-score", type=int, default=0, help="strength_score 최솟값")
    parser.add_argument("--sql", action="store_true", help="SQL 키워드 검색 모드")
    parser.add_argument("--hybrid", action="store_true", help="벡터+SQL 하이브리드 모드")
    parser.add_argument("--topic", action="store_true", help="전수 추출 모드 — SQL 전체 꺼내고 필터링")
    parser.add_argument("--days", type=int, default=None, help="최근 N일만 (SQL/hybrid/topic 모드)")
    args = parser.parse_args()

    if args.topic:
        keywords = [w for w in args.question.split() if len(w) >= 2]
        run_topic(keywords, trust=args.trust or "B", min_length=args.min_length, days=args.days)
    else:
        mode = "hybrid" if args.hybrid else ("sql" if args.sql else "vector")
        run_query(
            args.question, args.n, args.sector, args.signal,
            trust=args.trust, min_length=args.min_length, min_score=args.min_score,
            mode=mode, days=args.days,
        )
