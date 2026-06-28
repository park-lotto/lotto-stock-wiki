"""수급빈집 탑픽 산출 — signal_snapshot(9점표·빈집·RS·소르티노) + 원자DB 근거 결합.

일반 브리핑과의 차별점: 운영자 고유 신호의 교집합으로 '오늘 진짜 봐야 할 종목'을 뽑는다.
  주도섹터(소르티노 상위) ∩ 수급빈집A ∩ 다중신호(score) → score·RS 랭킹 → 원자DB '왜' 부착
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "output" / "signal" / "signal_snapshot.json"
ATOMS_DB = ROOT / "pipeline" / "atoms" / "atoms.db"

# 플래그 → 사람이 읽는 근거 문구
FLAG_KO = {
    "빈집": "기관 수급 빈집",
    "수출": "수출 증가",
    "컨센신고가": "목표가 신고가 경신",
    "어닝서프": "어닝 서프라이즈",
    "판가": "판가 인상",
    "미국커플링": "美 강세 동조",
    "정책": "정책 수혜",
    "D30": "단기 모멘텀(D30)",
}


def _num(v):
    return v if isinstance(v, (int, float)) else 0


def _atom_reason(name: str) -> dict | None:
    """원자DB에서 해당 종목의 최신 고신뢰 원자 1건(왜 + 출처 + 날짜)."""
    if not ATOMS_DB.exists():
        return None
    try:
        con = sqlite3.connect(str(ATOMS_DB))
        row = con.execute(
            "SELECT content, source_name, date FROM atoms "
            "WHERE (asset = ? OR content LIKE ?) AND content IS NOT NULL "
            "ORDER BY COALESCE(strength_score,0) DESC, date DESC LIMIT 1",
            (name, f"%{name}%"),
        ).fetchone()
        con.close()
        if row and row[0]:
            return {"why": row[0].strip(), "source": row[1] or "", "date": row[2] or ""}
    except Exception:
        return None
    return None


def get_picks(top_n: int = 5, min_score: int = 3,
              snapshot_path: Path = None, lead_count: int = 5) -> dict:
    """수급빈집 탑픽 + 시장/섹터 컨텍스트를 반환."""
    path = Path(snapshot_path) if snapshot_path else SNAPSHOT
    if not path.exists():
        return {"date": "", "market": {}, "lead_sectors": [], "picks": [], "source": ""}

    snap = json.loads(path.read_text(encoding="utf-8"))
    s1 = snap.get("stage1", {})
    s2 = snap.get("stage2", {})
    stocks = snap.get("stage3", {}).get("stocks", [])

    # 주도섹터: 소르티노 상위 lead_count (sortino는 {섹터:점수} dict 또는 [[섹터,점수]] list)
    sortino = s2.get("sortino", {})
    if isinstance(sortino, dict):
        lead_pairs = sorted(sortino.items(), key=lambda kv: _num(kv[1]), reverse=True)[:lead_count]
    elif isinstance(sortino, list):
        lead_pairs = sortino[:lead_count]
    else:
        lead_pairs = []
    lead_names = [p[0] if isinstance(p, (list, tuple)) else p for p in lead_pairs]

    # 시황 점검 항목(미장/VIX/이벤트 등) — {label, ok} 간소화
    reasons = [{"label": r.get("label", ""), "ok": bool(r.get("ok"))}
               for r in (s1.get("reasons") or []) if r.get("label")]
    market = {
        "verdict": s1.get("verdict", ""),
        "vix": s1.get("vix"),
        "vix_chg": s1.get("vix_chg"),
        "us_strong_sectors": s1.get("us_strong_sectors", []),
        "reasons": reasons,
    }

    # 교집합: 주도섹터 ∩ 빈집A ∩ score>=min_score → score·RS 내림차순
    cand = [x for x in stocks
            if x.get("sector") in lead_names
            and x.get("vacancy") == "A"
            and _num(x.get("score")) >= min_score]
    cand.sort(key=lambda x: (_num(x.get("score")), _num(x.get("rs"))), reverse=True)

    picks = []
    for x in cand[:top_n]:
        signals = [FLAG_KO.get(k, k) for k, v in x.get("flags", {}).items() if v]
        picks.append({
            "name": x.get("name", ""),
            "code": x.get("code", ""),
            "sector": x.get("sector", ""),
            "score": _num(x.get("score")),
            "rs": round(_num(x.get("rs")), 1),
            "vacancy": x.get("vacancy", ""),
            "signals": signals,
            "atom": _atom_reason(x.get("name", "")),
        })

    return {
        "date": snap.get("date", ""),
        "market": market,
        "lead_sectors": [{"name": (p[0] if isinstance(p, (list, tuple)) else p),
                          "sortino": round(p[1], 1) if isinstance(p, (list, tuple)) and len(p) > 1 else None}
                         for p in lead_pairs],
        "picks": picks,
        "source": path.name,
    }
