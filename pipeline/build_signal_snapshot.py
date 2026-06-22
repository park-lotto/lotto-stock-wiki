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


def _load_sector_master():
    """루트 sector_map.json → (name→sector, code→sector). 515종목 마스터 매핑."""
    by_name, by_code = {}, {}
    p = ROOT / "sector_map.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for name, info in data.items():
                sec = (info or {}).get("섹터")
                code = (info or {}).get("코드")
                if sec:
                    by_name[name.strip()] = sec
                    if code:
                        by_code[str(code).strip().lstrip("A").zfill(6)] = sec
        except Exception:
            pass
    return by_name, by_code


def _resolve_sector(name, code, by_name, by_code, ie):
    """종목 섹터 해석: 마스터(이름) → 마스터(코드) → wiki 페이지 → ?"""
    if name in by_name:
        return by_name[name]
    if code:
        c = str(code).strip().lstrip("A").zfill(6)
        if c in by_code:
            return by_code[c]
    return ie.get_stock_sector(name) or "?"


# 소르티노 ETF/종목명 → 우리 섹터 키워드 매칭
SECTOR_KEYWORDS = {
    "반도체": ["반도체", "하이닉스", "삼성전자", "전공정", "후공정", "HBM"],
    "전력": ["전력", "전선", "변압", "그리드"],
    "신재생": ["태양광", "친환경에너지", "ESS", "신재생", "풍력"],
    "로봇": ["로봇"],
    "자동차": ["자동차", "모빌리티"],
    "조선": ["조선", "중공업", "엔진"],
    "이차전지": ["2차전지", "이차전지", "배터리"],
    "바이오": ["바이오", "헬스케어", "제약"],
    "방산": ["방산", "우주방산", "K방산"],
    "원전": ["원자력", "원전", "SMR"],
    "통신": ["네트워크", "통신"],
    "화장품": ["화장품", "뷰티"],
    "미용": ["미용", "에스테틱"],
}


def _match_sector(name):
    for sec, kws in SECTOR_KEYWORDS.items():
        if any(k in name for k in kws):
            return sec
    return None


def sortino_strength(ie):
    """소르티노 ETF상대강도 top20 → {섹터: norm_RS_avg(0~100)}. ETF명 키워드 매칭."""
    parsed = ie.parse_한국ETF상대강도(True)
    rows = parsed.get("top20", []) if isinstance(parsed, dict) else []
    out = {}
    for r in rows:
        sec = _match_sector(r.get("name", ""))
        norm = r.get("norm_RS_avg")
        if sec and norm is not None:
            out[sec] = max(out.get(sec, 0), norm)
    return out


def select_sectors_ab(us_sectors, sortino, vac_cnt):
    """섹터 좁히기 2방식. A=교집합(미장강세∩소르티노∩빈집), B=점수합산 top6."""
    def us_avg(s):
        return (us_sectors.get(s) or {}).get("avg")
    cands = [s for s in vac_cnt if vac_cnt.get(s, 0) > 0]  # 빈집 있는 섹터만
    # A: 미장강세(≥0.5%) AND 소르티노(≥50=코스피상회) AND 빈집보유
    a = [s for s in cands if (us_avg(s) or -99) >= 0.5 and sortino.get(s, 0) >= 50]
    a.sort(key=lambda s: (us_avg(s) or 0) + sortino.get(s, 0) / 100, reverse=True)

    def score_b(s):
        us = max(0.0, (us_avg(s) or 0)) / 3.0          # 미장등락 ~0~3%→0~1
        so = sortino.get(s, 0) / 100.0                  # 0~1
        va = min(vac_cnt.get(s, 0), 10) / 10.0          # 0~1
        return round(us + so + va, 3)
    b = sorted(cands, key=score_b, reverse=True)
    b = [s for s in b if score_b(s) > 0][:6]
    return a, b


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

    # 섹터 마스터(515) + 컨센 파서 섹터 폴백
    by_name, by_code = _load_sector_master()
    for bucket in (con.get("results", {}) if isinstance(con, dict) else {}).values():
        for r in (bucket or []):
            nm, sec = (r.get("name") or "").strip(), r.get("sector")
            if nm and sec and sec != "—" and nm not in by_name:
                by_name[nm] = sec

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
                    "sector": _resolve_sector(name, r.get("code"), by_name, by_code, ie),
                    "vacancy": grade, "rs": rs_map.get(name),
                    "flags": flags,
                }
                st["score"] = score_stock(st)
                stocks.append(st)
    stocks.sort(key=lambda s: (s["score"], s["vacancy"] == "A"), reverse=True)
    return stocks


def build_snapshot(macro: dict, lead_sectors: list, stocks: list, us_sectors: dict = None) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    us_sectors = us_sectors or {}
    return {
        "date": today,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stage1": macro,
        "stage2": {"sectors": [
            {"name": s,
             "score": (us_sectors.get(s) or {}).get("avg"),
             "us_leaders": (us_sectors.get(s) or {}).get("leaders", []),
             "in_us_strong": ((us_sectors.get(s) or {}).get("avg") or 0) >= 0.5,
             "in_taerini_lead": True}
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
    vac_cnt = Counter(s["sector"] for s in stocks if s["sector"] != "?")
    us_sectors = macro.get("us_sectors", {}) if isinstance(macro, dict) else {}

    # 소르티노 섹터강도 + A/B 두 방식
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import ingest_excel as ie
    sortino = sortino_strength(ie)
    method_a, method_b = select_sectors_ab(us_sectors, sortino, vac_cnt)

    if lead is None:
        # 화면 기본 표시 = B(점수합산). 비면 빈집 상위.
        lead = method_b or [name for name, _ in vac_cnt.most_common(3)]
    snap = build_snapshot(macro, lead, stocks, us_sectors)
    snap["stage2"]["methods"] = {"A_교집합": method_a, "B_점수합산": method_b}
    snap["stage2"]["sortino"] = sortino
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"스냅샷 기록: {OUT} (종목 {len(stocks)}, A {method_a}, B {method_b})")
    return snap


if __name__ == "__main__":
    main()
