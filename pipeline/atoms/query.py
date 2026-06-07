"""
query.py — 자유 질문으로 관련 원자를 검색하고 결과를 출력.

사용법:
    python -m pipeline.atoms.query "반도체 지금 어때?"
    python -m pipeline.atoms.query "수급 빈집 종목" --sector 기타
    python -m pipeline.atoms.query "오늘 리스크" --signal bearish --n 20
"""
import sys
import io
import argparse

# Windows 콘솔 UTF-8 출력 강제
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .db import init_db
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


def _fmt_atom(a: dict, rank: int) -> str:
    score = a.get("similarity_score", 0)
    date = a.get("date", "")
    sector = a.get("sector", "")
    asset = a.get("asset", "")
    signal = _SIGNAL_KO.get(a.get("signal", ""), a.get("signal", ""))
    trust = a.get("source_trust", "")
    source = a.get("source_name", "")
    content = a.get("content", "")
    short = content[:120] + ("..." if len(content) > 120 else "")
    return (
        f"\n[{rank:02d}] {score:.3f} | {date} | {sector}/{asset} | "
        f"{signal}[{trust}] {source}\n    {short}"
    )


def run_query(
    question: str,
    n: int = 10,
    sector: str = None,
    signal: str = None,
) -> list[dict]:
    init_db()
    atoms = query_similar(question, n_results=n, sector=sector, signal=signal)
    if not atoms:
        print("[결과 없음] 관련 원자를 찾지 못했습니다.")
        return []

    filters = []
    if sector:
        filters.append(f"섹터={sector}")
    if signal:
        filters.append(f"신호={signal}")
    filter_str = f" [{', '.join(filters)}]" if filters else ""

    print(f"\n질문: {question}{filter_str}")
    print(f"관련 원자 {len(atoms)}개:\n{'='*70}")
    for i, a in enumerate(atoms, 1):
        print(_fmt_atom(a, i))
    print("=" * 70)
    return atoms


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="원자 의미 검색")
    parser.add_argument("question", help="검색 질문")
    parser.add_argument("--n", type=int, default=10, help="결과 수 (기본 10)")
    parser.add_argument("--sector", default=None, help="섹터 필터")
    parser.add_argument("--signal", default=None, help="신호 필터 (bullish/bearish 등)")
    args = parser.parse_args()
    run_query(args.question, args.n, args.sector, args.signal)
