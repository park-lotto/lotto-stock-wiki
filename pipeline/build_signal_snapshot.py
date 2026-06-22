"""태린이 엑셀 → 신호 스냅샷 JSON.

서버(/signal)가 읽을 3단 깔때기 데이터를 로컬에서 선생성한다.
- STAGE 3 (종목 9점표): 오실레이터 빈집 + 수출🔴 + 어닝서프 + 컨센신고가 자동 계산.
  판가·미국커플링·정책·D-30은 수동 플래그(기본 0).
- STAGE 1 (매크로 GO/경계/NO): 자동 소스 미연결 → 수기 macro_today.json 우선, 없으면 CAUTION.
- STAGE 2 (섹터 교집합): 수기 lead_sectors.json 우선, 없으면 빈집 분포로 추정.

실행: python -m pipeline.build_signal_snapshot
출력: output/signal/signal_snapshot.json
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "output" / "signal" / "signal_snapshot.json"

# 빈집(2점, 필수) 외 1점짜리 플래그 7종
_FLAG_KEYS = ["수출", "컨센신고가", "어닝서프", "판가", "미국커플링", "정책", "D30"]


def score_stock(stock: dict) -> int:
    """빈집(2점) 필수. 없으면 0. 있으면 + 7개 플래그 각 1점 (최대 9)."""
    f = stock.get("flags", {})
    if f.get("빈집", 0) < 2:
        return 0
    return 2 + sum(1 for k in _FLAG_KEYS if f.get(k, 0) >= 1)


def _names(rows):
    """행 리스트에서 종목명 집합."""
    out = set()
    for r in rows or []:
        if isinstance(r, dict) and r.get("name"):
            out.add(r["name"].strip())
        elif isinstance(r, str):
            out.add(r.strip())
    return out


def build_stocks() -> list:
    """오실레이터 빈집 종목을 후보로, 수출·어닝·컨센으로 플래그를 채운다."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import ingest_excel as ie

    osc_big = ie.parse_수급오실레이터(True)
    osc_sml = ie.parse_중소형주오실레이터(True)
    exp = ie.parse_수출정리(True)
    con = ie.parse_컨센움직임(True)
    liq = ie.parse_유동성체크(True)
    rs = ie.parse_rs(True)

    # 1점 플래그 집합
    export_red = set()
    for sec, info in (exp.get("results", {}) if isinstance(exp, dict) else {}).items():
        if isinstance(info, dict) and info.get("signal") == "🔴":
            export_red |= _names(info.get("stocks"))
    surprise = _names((con.get("results", {}) or {}).get("서프라이즈")) if isinstance(con, dict) else set()
    con_high = _names((liq.get("results", {}) or {}).get("컨센신고가")) if isinstance(liq, dict) else set()

    # RS 맵 (top30)
    rs_map = {}
    for r in (rs.get("top30", []) if isinstance(rs, dict) else []):
        if r.get("name"):
            rs_map[r["name"].strip()] = r.get("RS_avg")

    stocks = []
    seen = set()
    for parsed in (osc_big, osc_sml):
        if not isinstance(parsed, dict):
            continue
        for grade, key in (("A", "빈집_A"), ("B", "빈집_B")):
            for r in parsed.get(key, []):
                name = (r.get("name") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                flags = {
                    "빈집": 2,
                    "수출": 1 if name in export_red else 0,
                    "컨센신고가": 1 if name in con_high else 0,
                    "어닝서프": 1 if name in surprise else 0,
                    "판가": 0, "미국커플링": 0, "정책": 0, "D30": 0,
                }
                st = {
                    "name": name, "code": r.get("code"),
                    "sector": ie.get_stock_sector(name) or "?",
                    "vacancy": grade, "rs": rs_map.get(name),
                    "flags": flags,
                }
                st["score"] = score_stock(st)
                stocks.append(st)
    stocks.sort(key=lambda s: (s["score"], s["vacancy"] == "A"), reverse=True)
    return stocks


def build_snapshot(macro: dict, lead_sectors: list, stocks: list) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "date": today,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stage1": macro,
        "stage2": {"sectors": [
            {"name": s, "score": None, "in_us_strong": True, "in_taerini_lead": True}
            for s in lead_sectors
        ]},
        "stage3": {"stocks": stocks},
    }


def _read_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def main():
    sig_dir = ROOT / "output" / "signal"
    macro = _read_json(sig_dir / "macro_today.json", {
        "verdict": "CAUTION",
        "reasons": [{"label": "매크로", "ok": False,
                     "detail": "수기 입력(macro_today.json) 없음 — 기본 경계"}],
    })
    lead = _read_json(sig_dir / "lead_sectors.json", None)
    stocks = build_stocks()
    if lead is None:
        # 빈집 종목이 많은 섹터 상위 3개로 추정
        cnt = Counter(s["sector"] for s in stocks if s["sector"] != "?")
        lead = [name for name, _ in cnt.most_common(3)]
    snap = build_snapshot(macro, lead, stocks)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"스냅샷 기록: {OUT} (종목 {len(stocks)}, 섹터 {lead})")
    return snap


if __name__ == "__main__":
    main()
