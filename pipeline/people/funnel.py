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
    "vacuum_pct_max": 35.0,   # 수급빈집: osc 백분위 이 값 이하 (낮을수록 빈집)
    "min_up_count": 1,        # 컨센/TP 상향: up_count 최소
    "require_up_gt_down": True,  # up_count > down_count 필요
    "top_n": 20,
}


def _load():
    if not _STOCK_PATH.exists():
        return {"date": None, "stocks": {}}
    return json.loads(_STOCK_PATH.read_text(encoding="utf-8"))


def _osc_pct(s):
    o = s.get("osc") or {}
    return o.get("pct")


def select(data=None, th=None) -> dict:
    """오늘의 종목선정 재현. 퍼널 단계별 카운트 + 후보 리스트 반환."""
    th = {**THRESHOLDS, **(th or {})}
    data = data or _load()
    stocks = data.get("stocks", {})
    total = len(stocks)

    # 1단계 — 수급빈집: osc 백분위가 낮은(수급 안 들어온) 종목
    vacuum = []
    for code, s in stocks.items():
        pct = _osc_pct(s)
        if pct is not None and pct <= th["vacuum_pct_max"]:
            vacuum.append((code, s))

    # 2단계 — 컨센/TP 상향(재료): 목표주가 상향 종목
    materialed = []
    for code, s in vacuum:
        tp = s.get("tp") or {}
        up, down = tp.get("up_count", 0) or 0, tp.get("down_count", 0) or 0
        if up < th["min_up_count"]:
            continue
        if th["require_up_gt_down"] and not (up > down):
            continue
        materialed.append((code, s))

    # 3단계 — 정렬: 빈집 강도(낮은 pct) + 컨센 강도(up_count)
    def _score(item):
        _, s = item
        pct = _osc_pct(s) or 100
        up = (s.get("tp") or {}).get("up_count", 0) or 0
        return (th["vacuum_pct_max"] - pct) + up * 2  # 빈집강도 + 컨센가중

    materialed.sort(key=_score, reverse=True)
    top = materialed[: th["top_n"]]

    candidates = []
    for code, s in top:
        osc = s.get("osc") or {}
        tp = s.get("tp") or {}
        candidates.append({
            "code": code,
            "name": s.get("name", code),
            "vacuum_pct": osc.get("pct"),
            "vacuum_trend": osc.get("trend"),
            "tp_dir": tp.get("dir"),
            "tp_up": tp.get("up_count"),
            "tp_down": tp.get("down_count"),
            "tp_target": tp.get("target"),
            "reason": f"수급빈집(pct {osc.get('pct')}) × 컨센상향(↑{tp.get('up_count')}/↓{tp.get('down_count')})",
        })

    return {
        "date": data.get("date"),
        "thresholds": th,
        "funnel": [
            {"step": "전체 종목", "count": total},
            {"step": f"① 수급빈집 (osc pct ≤ {th['vacuum_pct_max']})", "count": len(vacuum)},
            {"step": "② 컨센/TP 상향 (재료)", "count": len(materialed)},
            {"step": f"③ 상위 {th['top_n']} 선정", "count": len(top)},
        ],
        "candidates": candidates,
        "note": "그의 규칙(수급빈집×컨센상향) 재현. RS/소라티노(주도섹터) 미반영. 매수추천 아님.",
    }


if __name__ == "__main__":
    r = select()
    print(f"[오늘의 종목선정 재현] {r['date']}")
    for f in r["funnel"]:
        print(f"  {f['step']}: {f['count']}")
    print("--- 후보 ---")
    for c in r["candidates"]:
        print(f"  {c['name']:12s} {c['reason']}")
