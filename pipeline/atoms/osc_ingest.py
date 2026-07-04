"""
osc_ingest.py — 수급 오실레이터 결과 → 원자 DB 저장

calc_oscillator.py 계산 결과를 원자화해서 atoms.db + ChromaDB에 저장.
오실레이터는 직접 계산 데이터라 source_trust='A' (최고 신뢰도).

사용법:
    # calc_oscillator.py 결과 직접 파이프
    python calc_oscillator.py --all | python -m pipeline.atoms.osc_ingest --stdin

    # JSON 파일에서 읽기
    python -m pipeline.atoms.osc_ingest results.json

    # 단일 종목 직접 입력
    python -m pipeline.atoms.osc_ingest --stock 삼성전자 --sector 반도체 --osc 0.0023 --trend "↑ 재진입"
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, date

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stdin.encoding and sys.stdin.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .atomizer import _make_id
from .db import init_db, insert_atom, get_conn
from .vector_db import embed_and_store


def osc_to_signal(osc_value: float, trend: str) -> str:
    """오실레이터 값 + 트렌드 → signal 분류."""
    if osc_value > 0 and "재진입" in trend:
        return "bullish"   # 양수 + 재진입 = 강한 매수세
    if osc_value > 0:
        return "catalyst"  # 양수지만 재진입 아님 = 주목
    if "빈집심화" in trend:
        return "bearish"   # 빈집 심화 = 매도세
    if osc_value < 0:
        return "risk"      # 음수 = 위험
    return "neutral"


def osc_to_content(name: str, osc_value: float, trend: str,
                   macd: float = None, signal_line: float = None) -> str:
    """오실레이터 결과 → content 텍스트."""
    direction = "양(+)" if osc_value > 0 else "음(-)"
    trend_text = trend.replace("↑", "상승").replace("↓", "하락").replace("→", "횡보")
    content = f"{name} 수급오실레이터 {osc_value:.4f} ({direction}), 트렌드 {trend_text}."

    if macd is not None and signal_line is not None:
        if macd > signal_line:
            content += f" MACD({macd:.4f}) > Signal({signal_line:.4f}) — 상승 크로스 구간."
        else:
            content += f" MACD({macd:.4f}) < Signal({signal_line:.4f}) — 하락 크로스 구간."

    # 해석 추가
    sig = osc_to_signal(osc_value, trend)
    if sig == "bullish":
        content += " 외인+기관 순매수 유입, 수급 빈집 재진입 신호."
    elif sig == "bearish":
        content += " 수급 이탈 지속, 빈집 심화 구간."
    elif sig == "risk":
        content += " 외인+기관 순매도 우세, 주의 구간."
    elif sig == "catalyst":
        content += " 수급 개선 중, 방향 전환 가능성 모니터링."

    return content


def make_osc_atom(name: str, sector: str, osc_value: float, trend: str,
                  date_str: str = None,
                  macd: float = None, signal_line: float = None) -> dict:
    """단일 종목 오실레이터 결과 → 원자 dict."""
    today = date_str or date.today().strftime("%Y-%m-%d")
    content = osc_to_content(name, osc_value, trend, macd, signal_line)
    signal = osc_to_signal(osc_value, trend)

    return {
        "id": _make_id(today, f"osc_{name}", 0),
        "date": today,
        "source_type": "oscillator",
        "source_name": "calc_oscillator",
        "source_trust": "A",
        "raw_file": f"oscillator/{today}",
        "layer": "L6",
        "sector": sector,
        "asset": name,
        "asset_level": "stock",
        "signal": signal,
        "event_type": "data",
        "magnitude": "major" if abs(osc_value) > 0.005 else "minor",
        "content_type": "data",
        "strength_score": 90 if signal in ("bullish", "bearish") else 60,
        "validity_type": "date",
        "validity_until": today,  # 당일 데이터 — 다음날이면 새 원자
        "is_active": 1,
        "content": content,
        "relations": [],
    }


def ingest_osc_results(results: list[dict], date_str: str = None) -> int:
    """오실레이터 결과 리스트 → DB 저장. 반환: 저장된 원자 수."""
    today = date_str or date.today().strftime("%Y-%m-%d")
    count = 0
    for r in results:
        try:
            atom = make_osc_atom(
                name=r["name"],
                sector=r["sector"],
                osc_value=r["osc"],
                trend=r.get("trend", "→ 횡보"),
                date_str=today,
                macd=r.get("macd"),
                signal_line=r.get("signal_line"),
            )
            # 같은 날짜 같은 종목 중복 방지
            conn = get_conn()
            exists = conn.execute(
                "SELECT 1 FROM atoms WHERE date=? AND asset=? AND source_type='oscillator'",
                (today, r["name"])
            ).fetchone()
            conn.close()
            if exists:
                continue

            insert_atom(atom)
            embed_and_store(atom)
            count += 1
            print(f"  [OSC] {r['name']} | {r['sector']} | osc={r['osc']:.4f} | {r.get('trend','')}")
        except Exception as e:
            # Excel COM에서 종목명이 손상돼 넘어오는 경우가 있음(예: 깨진 서로게이트 문자) —
            # 종목 하나 때문에 전체 배치가 죽지 않도록 건너뛰고 계속한다.
            print(f"  [OSC][SKIP] {r.get('name', '?')!r} 처리 실패: {e}")

    return count


def main():
    parser = argparse.ArgumentParser(description="수급 오실레이터 결과 → 원자 DB")
    parser.add_argument("file", nargs="?", help="JSON 파일 경로")
    parser.add_argument("--stdin", action="store_true", help="stdin에서 JSON 읽기")
    parser.add_argument("--stock", help="단일 종목명")
    parser.add_argument("--sector", default="기타", help="섹터")
    parser.add_argument("--osc", type=float, help="오실레이터 값")
    parser.add_argument("--trend", default="→ 횡보", help="트렌드 문자열")
    parser.add_argument("--macd", type=float, default=None)
    parser.add_argument("--signal-line", type=float, default=None)
    parser.add_argument("--date", default=None, help="날짜 YYYY-MM-DD")
    args = parser.parse_args()

    init_db()
    today = args.date or date.today().strftime("%Y-%m-%d")

    if args.stock:
        # 단일 종목 직접 입력
        results = [{"name": args.stock, "sector": args.sector,
                    "osc": args.osc, "trend": args.trend,
                    "macd": args.macd, "signal_line": args.signal_line}]
    elif args.stdin:
        data = sys.stdin.read()
        results = json.loads(data)
    elif args.file:
        results = json.loads(Path(args.file).read_text(encoding="utf-8"))
    else:
        parser.print_help()
        return

    count = ingest_osc_results(results, today)
    print(f"\n완료: {count}개 오실레이터 원자 저장 ({today})")


if __name__ == "__main__":
    main()
