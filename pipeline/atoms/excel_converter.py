import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def _atom_id(date: str, source: str, asset: str) -> str:
    """Generate a deterministic atom ID from date, source, and asset."""
    raw = f"{date}_{source}_{asset}"
    return "atom_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _next_week(date_str: str) -> str:
    """Calculate date one week from given date."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=7)).strftime("%Y-%m-%d")


def oscillator_to_atoms(file_path: str, date: str) -> list[dict]:
    """수급 오실레이터 Excel → 원자 리스트."""
    df = pd.read_excel(file_path)
    atoms = []

    # Find oscillator and name columns (flexible matching)
    osc_col = next(
        (c for c in df.columns if "오실레이터" in str(c) or "값" in str(c)), None
    )
    name_col = next(
        (c for c in df.columns if "종목" in str(c) or "이름" in str(c)), None
    )
    if not osc_col or not name_col:
        return atoms

    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        val = row[osc_col]
        if not name or pd.isna(val):
            continue
        val = float(val)
        signal = "bullish" if val > 0 else "bearish" if val < 0 else "neutral"
        magnitude = "major" if abs(val) > 50 else "minor"

        # Build direction text
        if val > 50:
            direction = "강한 매수 우위"
        elif val > 0:
            direction = "매수 우위"
        elif val > -50:
            direction = "매도 우위"
        else:
            direction = "강한 매도 우위"

        # Add vacuum signal if applicable
        vacuum = " 수급 빈집 신호 발동." if val > 60 else ""

        content = (
            f"{name} 외국인+기관 수급 오실레이터 {val:+.0f}. "
            f"수급 방향: {direction}.{vacuum}"
        )

        atoms.append({
            "id": _atom_id(date, "수급오실레이터", name),
            "date": date,
            "source_type": "excel",
            "source_name": "수급오실레이터",
            "source_trust": "A",
            "raw_file": str(file_path),
            "layer": "L6",
            "sector": "기타",
            "asset": name,
            "asset_level": "stock",
            "signal": signal,
            "event_type": "supply",
            "magnitude": magnitude,
            "content_type": "data",
            "strength_score": 3 if magnitude == "major" else 2,
            "validity_type": "date",
            "validity_until": _next_week(date),
            "is_active": 1,
            "content": content,
            "relations": [],
        })
    return atoms


def oscillator_json_to_atoms(json_file: str, date: str = None) -> list[dict]:
    """oscillator_scan.json (calc_oscillator.py 출력) → 원자 리스트.

    JSON 형식: {date, thresholds:{A:float,B:float}, A:[[종목명,값],...], B:...}
    수급빈집 역발상: A/B 등급(음수) = bullish, D 등급(양수) = bearish
    """
    data = json.loads(Path(json_file).read_text(encoding="utf-8"))
    date = date or data.get("date", datetime.now().strftime("%Y-%m-%d"))

    _GRADE_SIGNAL = {"A": "bullish", "B": "bullish", "C": "neutral", "D": "bearish"}
    _GRADE_LABEL = {"A": "완전빈집", "B": "반빈집", "C": "정상", "D": "과매수"}
    _GRADE_DESC = {
        "A": "극도 수급 빈집 — 역발상 매수 적기",
        "B": "수급 반빈집 — 매수 검토 구간",
        "C": "정상 수급 범위",
        "D": "수급 과매수 — 매도 압력 경계",
    }

    atoms = []
    for grade in ["A", "B", "C", "D"]:
        for entry in data.get(grade, []):
            name, val = entry[0], float(entry[1])
            magnitude = "major" if grade == "A" else "minor"
            content = (
                f"{name} 수급오실레이터 {val:+.5f}. "
                f"빈집등급: {grade} {_GRADE_LABEL[grade]}. "
                f"{_GRADE_DESC[grade]}."
            )
            atoms.append({
                "id": _atom_id(date, "수급오실레이터", name),
                "date": date,
                "source_type": "excel",
                "source_name": "수급오실레이터",
                "source_trust": "A",
                "raw_file": str(json_file),
                "layer": "L6",
                "sector": "기타",
                "asset": name,
                "asset_level": "stock",
                "signal": _GRADE_SIGNAL[grade],
                "event_type": "supply",
                "magnitude": magnitude,
                "content_type": "data",
                "strength_score": 4 if grade == "A" else 3,
                "validity_type": "date",
                "validity_until": _next_week(date),
                "is_active": 1,
                "content": content,
                "relations": [],
            })
    return atoms


def wisereport_json_to_atoms(json_file: str, date: str = None) -> list[dict]:
    """wisereport _parsed.json (증권사 리포트 요약) → 원자 리스트."""
    data = json.loads(Path(json_file).read_text(encoding="utf-8"))
    date = date or data.get("date", datetime.now().strftime("%Y-%m-%d"))
    atoms = []

    for entry in data.get("corp", []):
        if len(entry) < 9:
            continue
        broker = str(entry[0]).strip()
        stock_raw = str(entry[1]).strip()
        opinion = str(entry[3]).strip()
        tp_change = str(entry[4]).strip()   # ▲ 상향 / ▼ 하향 / = 유지
        tp = str(entry[5]).strip()
        title = str(entry[7]).strip()
        summary = str(entry[8]).strip()

        # 종목명에서 코드 분리: "삼성전자[005930]" → "삼성전자"
        stock = stock_raw.split("[")[0].strip()

        # 신호 결정
        if tp_change == "▲" or "상향" in tp_change:
            signal = "bullish"
        elif tp_change == "▼" or "하향" in tp_change:
            signal = "bearish"
        else:
            signal = "neutral"

        # 투자의견 기반 보정
        if opinion.upper() in ("SELL", "UNDERPERFORM", "REDUCE"):
            signal = "bearish"
        elif opinion.upper() in ("BUY", "STRONG BUY", "매수", "OVERWEIGHT"):
            if signal == "neutral":
                signal = "bullish"

        content = f"{broker} | {stock} | {opinion} | TP {tp}원({tp_change}) | {title}. {summary}"

        atoms.append({
            "id": _atom_id(date, broker, stock),
            "date": date,
            "source_type": "report",
            "source_name": broker,
            "source_trust": "A",
            "raw_file": str(json_file),
            "layer": "L5",
            "sector": "기타",
            "asset": stock,
            "asset_level": "stock",
            "signal": signal,
            "event_type": "consensus",
            "magnitude": "minor",
            "content_type": "analysis",
            "strength_score": 3,
            "validity_type": "date",
            "validity_until": _next_week(date),
            "is_active": 1,
            "content": content,
            "relations": [],
        })
    return atoms


def consensus_to_atoms(file_path: str, date: str) -> list[dict]:
    """컨센서스 변화 Excel → 원자 리스트."""
    df = pd.read_excel(file_path)
    atoms = []

    name_col = next((c for c in df.columns if "종목" in str(c)), None)
    sector_col = next((c for c in df.columns if "섹터" in str(c)), None)
    change_col = next((c for c in df.columns if "컨센" in str(c) or "변화" in str(c)), None)
    tp_col = next((c for c in df.columns if "TP" in str(c) or "목표" in str(c)), None)

    if not name_col:
        return atoms

    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name == "nan":
            continue

        sector = str(row[sector_col]).strip() if sector_col else "기타"
        change_str = str(row[change_col]).strip() if change_col else ""
        tp_str = str(row[tp_col]).strip() if tp_col else ""

        signal = "neutral"
        if change_str and change_str not in ("nan", ""):
            if "+" in change_str:
                signal = "bullish"
            elif "-" in change_str:
                signal = "bearish"

        content = f"{name} 컨센서스 변화: {change_str}."
        if tp_str and tp_str != "nan":
            content += f" 목표주가 {tp_str}원."

        atoms.append({
            "id": _atom_id(date, "컨센서스", name),
            "date": date,
            "source_type": "excel",
            "source_name": "컨센서스",
            "source_trust": "A",
            "raw_file": str(file_path),
            "layer": "L5",
            "sector": sector,
            "asset": name,
            "asset_level": "stock",
            "signal": signal,
            "event_type": "consensus",
            "magnitude": "minor",
            "content_type": "data",
            "strength_score": 2,
            "validity_type": "date",
            "validity_until": _next_week(date),
            "is_active": 1,
            "content": content,
            "relations": [],
        })
    return atoms
