"""funnel.py — '시스템 복사': 그의 종목선정 규칙을 오늘 데이터에 적용.

태린이아빠의 핵심 퍼널(수급빈집 → 컨센/TP 상향 → 정렬)을 taerini_stock.json에
투명하게 적용해 "그라면 오늘 이 종목들" 후보를 재현한다. 각 임계값은 조정 가능
상수(THRESHOLDS)이며, 결과는 규칙 기반 재현이지 매수 추천이 아니다.

한계: RS/소라티노(주도섹터)는 이 파일에 없어 미반영 — 빈집×컨센 축만. 후속 보강.

CLI:
    python -m pipeline.people.funnel            # 오늘의 종목선정 상위
"""
import sys
import io
import json
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_ROOT = Path(__file__).parent.parent.parent
_STOCK_PATH = _ROOT / "pipeline" / "taerini_stock.json"

# 조정 가능한 임계값 (그의 규칙을 수치화 — 관찰로 튜닝)
THRESHOLDS = {
    "mode": "his",            # "his"=주도(RS or 소라티노) 필수 + 빈집/컨센 (그의 루틴) / "strict"=빈집 AND 컨센
    "vacuum_pct_max": 35.0,   # 수급빈집: osc 백분위 이 값 이하 (낮을수록 빈집)
    "min_up_count": 1,        # 컨센/TP 상향: up_count 최소
    "require_up_gt_down": True,  # up_count > down_count 필요 (strict 경로에서)
    "require_leader": False,  # True면 주도주찾기(RS) 리스트 종목만
    "top_n": 20,
}

_SECTOR_MAP = None


def _sector_map():
    """{종목명: 섹터} — 소라티노 섹터매칭 폭 확대용. 1회 로드."""
    global _SECTOR_MAP
    if _SECTOR_MAP is None:
        import json
        p = _ROOT / "pipeline" / "atoms" / "stock_sector_map.json"
        try:
            _SECTOR_MAP = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _SECTOR_MAP = {}
    return _SECTOR_MAP


def _load():
    if not _STOCK_PATH.exists():
        return {"date": None, "stocks": {}}
    return json.loads(_STOCK_PATH.read_text(encoding="utf-8"))


def _osc_pct(s):
    o = s.get("osc") or {}
    return o.get("pct")


def select(data=None, th=None, rs=None, sortino=None) -> dict:
    """오늘의 종목선정 재현. 퍼널 단계별 카운트 + 후보 리스트 반환.
    rs/sortino=None이면 파일 로드; 테스트는 rs={}, sortino={'names':[],'sectors':[]} 주입해 I/O 회피."""
    th = {**THRESHOLDS, **(th or {})}
    data = data or _load()
    if rs is None:
        from pipeline.people.rs_data import load_rs
        rs = load_rs()
    if sortino is None:
        from pipeline.people.sortino_data import load_sortino_top
        sortino = load_sortino_top()
    s_names = set(sortino.get("names") or [])
    s_sectors = [kw for kw in (sortino.get("sectors") or []) if kw]
    smap = _sector_map()
    stocks = data.get("stocks", {})
    total = len(stocks)
    mode = th.get("mode", "his")

    def _sortino_match(name, sector):
        if name in s_names:
            return True
        sec = sector or ""
        return any(kw and kw in sec for kw in s_sectors)

    # 종목별 4신호 계산 → 게이트 → 점수
    scored = []
    n_vac = n_material = n_leading = 0
    for code, s in stocks.items():
        pct = _osc_pct(s)
        tp = s.get("tp") or {}
        up, down = tp.get("up_count", 0) or 0, tp.get("down_count", 0) or 0
        nm = s.get("name") or ""
        rsinfo = rs.get(nm)
        sector = smap.get(nm) or (rsinfo or {}).get("sector")
        vac_ok = pct is not None and pct <= th["vacuum_pct_max"]
        up_ok = up >= th["min_up_count"] and (up > down if th["require_up_gt_down"] else True)
        is_leader = rsinfo is not None
        s_match = _sortino_match(nm, sector)
        leading = is_leader or s_match          # 주도 = RS주도주 or 소라티노섹터
        if vac_ok: n_vac += 1
        if up_ok: n_material += 1
        if leading: n_leading += 1

        # 게이트: his=주도 필수 + (빈집 or 컨센) / strict=빈집 AND 컨센
        if mode == "strict":
            keep = vac_ok and up_ok
        else:
            keep = leading and (vac_ok or up_ok)
        if not keep:
            continue
        if th["require_leader"] and not is_leader:
            continue

        m3 = (rsinfo or {}).get("m3") or 0
        score = (is_leader * 1000) + (s_match * 500) + m3 \
            + (th["vacuum_pct_max"] - (pct if pct is not None else 100)) + up * 2
        scored.append((score, code, s, sector, is_leader, s_match))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: th["top_n"]]

    leaders = 0
    candidates = []
    for score, code, s, sector, is_leader, s_match in top:
        osc = s.get("osc") or {}
        tp = s.get("tp") or {}
        rsinfo = rs.get(s.get("name") or "")
        if is_leader:
            leaders += 1
        parts = [f"빈집(pct {osc.get('pct')})" if (osc.get('pct') is not None and osc.get('pct') <= th['vacuum_pct_max']) else None,
                 f"컨센↑{tp.get('up_count')}/↓{tp.get('down_count')}" if (tp.get('up_count') or 0) else None,
                 f"🔥주도주(3M {rsinfo.get('m3')}%)" if is_leader else None,
                 "📊소라티노주도" if s_match else None]
        candidates.append({
            "code": code,
            "name": s.get("name", code),
            "sector": sector,
            "vacuum_pct": osc.get("pct"),
            "vacuum_trend": osc.get("trend"),
            "tp_dir": tp.get("dir"),
            "tp_up": tp.get("up_count"),
            "tp_down": tp.get("down_count"),
            "tp_target": tp.get("target"),
            "is_leader": is_leader,
            "sortino_match": s_match,
            "rs_m3": (rsinfo or {}).get("m3"),
            "rs_m1": (rsinfo or {}).get("m1"),
            "reason": " · ".join(p for p in parts if p),
        })

    gate_txt = ("주도(RS or 소라티노) 필수 + 빈집/컨센" if mode == "his"
                else "빈집 AND 컨센")
    return {
        "date": data.get("date"),
        "thresholds": th,
        "rs_universe": len(rs),
        "sortino_available": sortino.get("available", False),
        "sortino_date": sortino.get("date"),
        "sortino_top": sortino.get("names") or [],
        "sortino_sectors": s_sectors,
        "funnel": [
            {"step": "전체 종목", "count": total},
            {"step": "주도섹터풀 (RS주도주 ∪ 소라티노섹터)", "count": n_leading},
            {"step": f"빈집(pct≤{th['vacuum_pct_max']})", "count": n_vac},
            {"step": "컨센/TP 상향(재료)", "count": n_material},
            {"step": f"→ 게이트[{gate_txt}] 통과", "count": len(scored)},
            {"step": f"→ 상위 {th['top_n']} 선정 (그중 🔥주도주 {leaders})", "count": len(top)},
        ],
        "candidates": candidates,
        "note": (f"[{mode}모드] {gate_txt}. 🔥=주도주(RS), 📊=소라티노 주도섹터. "
                 "빈집·컨센은 그 안에서 가점. 매수추천 아님."),
    }


if __name__ == "__main__":
    r = select()
    print(f"[오늘의 종목선정 재현] {r['date']}")
    for f in r["funnel"]:
        print(f"  {f['step']}: {f['count']}")
    print("--- 후보 ---")
    for c in r["candidates"]:
        print(f"  {c['name']:12s} {c['reason']}")
