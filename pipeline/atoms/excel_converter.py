import hashlib
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
