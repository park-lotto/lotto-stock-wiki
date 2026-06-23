#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sector_table.py — 섹터 종목 횡단 비교표 자동 생성.

B형 질문("조선 어디 좋아?") 대응. 섹터 폴더의 종목 페이지들에서
컨센TP·이벤트노출·다관점·등급을 추출해 한눈 비교표를 만든다.

사용:
  python scripts/sector_table.py 조선
  python scripts/sector_table.py 반도체 --out out/sector_table_반도체.md
"""
import re
import sys
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
TIERS = ROOT / "wiki" / "_schema" / "stock_tiers.yaml"

DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|?\s*$")


def load_tiers():
    m = {}
    if yaml and TIERS.exists():
        td = yaml.safe_load(TIERS.read_text(encoding="utf-8")) or {}
        for tier, names in td.items():
            if isinstance(names, list):
                for nm in names:
                    m[nm] = tier
    return m


def section(md, header_re):
    """헤더 매칭 섹션 본문(다음 ## 전까지)."""
    m = re.search(rf"^##\s*{header_re}.*?(?=^##\s|\Z)", md, re.M | re.S)
    return m.group(0) if m else ""


def _parse_tp(s):
    """'280,000원' / '380만' / '820,000~870,000원' → 정수(원). 실패 시 None."""
    s = s.replace(",", "").replace("원", "").strip()
    s = re.split(r"[~∼-]", s)[0].strip()  # 범위면 첫값
    m = re.match(r"([\d.]+)\s*만", s)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.match(r"(\d{4,})", s)
    return int(m.group(1)) if m else None


def _fmt_tp(x):
    return f"{x // 10000}만" if x >= 10000 else str(x)


def consensus_tp(md):
    """증권사 컨센서스 TP. 대표행([컨센]) 우선, 없으면 증권사별 행에서 범위 산출."""
    sec = section(md, r"(🏦\s*)?증권사 컨센서스")
    # 1) 대표행([컨센]/[기존 컨센]) 우선
    m = re.search(r"\|\s*\[[^\]]*컨센[^\]]*\]\s*\|\s*\*{0,2}([^|*]+?)\*{0,2}\s*\|", sec)
    if m:
        return m.group(1).strip()
    # 2) 폴백: 증권사별 행 TP 수집 → 범위 (N개사)
    tps = []
    for line in sec.splitlines():
        s = line.strip()
        if not s.startswith("|") or TABLE_SEP_RE.match(s):
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) < 2 or "증권사" in cols[0] or "컨센" in cols[0]:
            continue
        v = _parse_tp(cols[1])
        if v:
            tps.append(v)
    if tps:
        flo, fhi = _fmt_tp(min(tps)), _fmt_tp(max(tps))
        rng = flo if flo == fhi else f"{flo}~{fhi}"
        return f"{rng} ({len(tps)}개사)"
    return "—"


def count_rows(sec):
    pipes = sum(1 for l in sec.splitlines()
                if l.strip().startswith("|") and not TABLE_SEP_RE.match(l.strip()))
    return max(0, pipes - 1)


def school_count(md):
    sec = section(md, r"🟢\s*강세론")
    return sec.count("\n### ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sector")
    ap.add_argument("--out")
    args = ap.parse_args()

    stock_dir = ROOT / "wiki" / "L5_섹터" / args.sector / "stock"
    if not stock_dir.exists():
        print(f"섹터 폴더 없음: {stock_dir}", file=sys.stderr)
        sys.exit(1)

    tiers = load_tiers()
    rank = {"hot": 0, "watch": 1, "static": 2}
    rows = []
    for p in sorted(stock_dir.glob("*.md")):
        md = p.read_text(encoding="utf-8")
        name = p.stem.replace("stock_", "")
        tier = tiers.get(name, "static")
        tp = consensus_tp(md)
        events = count_rows(section(md, r"(📰\s*)?최신 이벤트"))
        schools = school_count(md)
        rows.append((name, tier, tp, events, schools))

    # 등급 우선 → 이벤트 노출 많은 순
    rows.sort(key=lambda r: (rank.get(r[1], 3), -r[3]))

    icon = {"hot": "🔥핫", "watch": "💧워치", "static": "🌑정적"}
    out = [f"## {args.sector} 종목 횡단 비교 (한눈에)  ← sector_table.py 자동생성",
           "",
           "| 종목 | 등급 | 컨센 TP | 이벤트(노출) | 다관점 학파 |",
           "|------|------|---------|------------|-----------|"]
    for name, tier, tp, events, schools in rows:
        sc = f"{schools}개" if schools else "—"
        out.append(f"| {name} | {icon.get(tier,tier)} | {tp} | {events} | {sc} |")
    table = "\n".join(out)

    print(table)
    if args.out:
        Path(args.out).write_text(table + "\n", encoding="utf-8")
        print(f"\n→ 저장: {args.out}")


if __name__ == "__main__":
    main()
