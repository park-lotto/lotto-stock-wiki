# -*- coding: utf-8 -*-
"""
extract_업종오실레이터.py
업종별오실레이터.xlsm → 주도업종 분석 → raw/market/YYYYMMDD_업종수급_요약.md

실행: python extract_업종오실레이터.py
     python extract_업종오실레이터.py --tg   (텔레그램 전송)

출력:
  섹션1 — 주도업종 Top 10 (기관 매수 절대금액 기준)
  섹션2 — 급증업종 (오늘 / 5일평균 비율 상위, 평균 대비 급증)
  섹션3 — 관심 테마 (로봇/조선/방산/우주 등)
  섹션4 — 매도/이탈 업종 (기관1일 음수)
"""

import os
import sys
import re
import glob
import argparse
import traceback
from datetime import datetime, date
from pathlib import Path

import win32com.client
import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE    = Path(__file__).parent
OUT_DIR = BASE / "raw" / "market"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 관심 테마 키워드 (사용자 16개 주도섹터 기준)
INTEREST_THEMES = {
    "반도체", "로봇", "조선", "방산", "바이오", "우주", "자동차",
    "이차전지", "2차전지", "전력", "원전", "신재생", "화장품",
    "LNG", "철강", "엔터", "AI", "전기장비", "전자장비"
}

# -------------------------------------------------------------------

def find_file() -> Path:
    patterns = [
        BASE / "raw" / "매일 엑셀넣을것" / "외국인기관수급오실레이터 업종*.xlsm",
        BASE / "raw" / "매일 엑셀넣을것" / "외국인기관수급오실레이터업종*.xlsm",
    ]
    for p in patterns:
        hits = sorted(glob.glob(str(p)))
        if hits:
            return Path(hits[-1])
    raise FileNotFoundError("업종별오실레이터 파일을 찾을 수 없음")


def open_wb(path: Path):
    xl = win32com.client.Dispatch("Excel.Application")
    xl.AutomationSecurity = 1
    wb = xl.Workbooks.Open(str(path), False, True)
    return xl, wb


def read_업종비중(ws) -> tuple[list, list, list]:
    """
    업종비중 시트 파싱.
    반환: (kospi_list, kosdaq_list, theme_list)
    각 항목: dict {name, 기관1일, 기관5일평균, 가속도, 거래대금5일}
    """
    total = ws.UsedRange.Rows.Count

    def safe(v):
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def accel(d1, d5):
        if d5 and abs(d5) > 0.01:
            return round(d1 / d5, 2)
        return 0.0

    kospi, kosdaq, themes = [], [], []

    for r in range(6, total + 1):
        # KOSPI 업종 (C1-C6)
        name = ws.Cells(r, 2).Value2
        if name and str(name).strip():
            d1 = safe(ws.Cells(r, 5).Value2)
            d5 = safe(ws.Cells(r, 6).Value2)
            td = safe(ws.Cells(r, 3).Value2)
            kospi.append({
                "name":    str(name).strip(),
                "기관1일":  d1,
                "기관5일":  d5,
                "가속도":   accel(d1, d5),
                "거래대금5일": td,
            })

        # KOSDAQ 업종 (C8-C13)
        name2 = ws.Cells(r, 9).Value2
        if name2 and str(name2).strip():
            d1 = safe(ws.Cells(r, 12).Value2)
            d5 = safe(ws.Cells(r, 13).Value2)
            td = safe(ws.Cells(r, 10).Value2)
            kosdaq.append({
                "name":    str(name2).strip(),
                "기관1일":  d1,
                "기관5일":  d5,
                "가속도":   accel(d1, d5),
                "거래대금5일": td,
            })

        # 테마 (C15-C20)
        name3 = ws.Cells(r, 16).Value2
        if name3 and str(name3).strip():
            d1 = safe(ws.Cells(r, 19).Value2)
            d5 = safe(ws.Cells(r, 20).Value2)
            td = safe(ws.Cells(r, 17).Value2)
            themes.append({
                "name":    str(name3).strip(),
                "기관1일":  d1,
                "기관5일":  d5,
                "가속도":   accel(d1, d5),
                "거래대금5일": td,
            })

    return kospi, kosdaq, themes


def dedup(lst: list) -> list:
    seen = set()
    out = []
    for x in lst:
        if x["name"] not in seen:
            seen.add(x["name"])
            out.append(x)
    return out


def signal(d1, d5) -> str:
    if d1 <= 0:
        return "⚫"
    if d5 <= 0:
        return "🟡"
    r = d1 / d5 if d5 > 0.01 else 1.0
    if r >= 1.5:
        return "🔴"
    if r >= 1.0:
        return "🟠"
    return "🟡"


def fmt_num(v: float) -> str:
    if abs(v) >= 100_000:
        return f"{v/100_000:.1f}억"
    if abs(v) >= 10_000:
        return f"{v/10_000:.0f}천만"
    return f"{v:,.0f}"


def build_markdown(kospi, kosdaq, themes, file_date: str) -> str:
    today = file_date
    lines = [
        f"# 업종별 수급 분석 — {today}",
        f"> 소스: 업종별오실레이터.xlsm / 기관 = 연금+사모+투신",
        "",
    ]

    # ── 섹션1: KOSPI 주도업종 Top 10 ──────────────────────────────
    lines += ["## 섹션1 — KOSPI 주도업종 (기관 매수 상위)", ""]
    lines += ["| 업종 | 기관1일 | 5일평균 | 가속도 | 신호 |",
              "|------|--------|--------|-------|------|"]
    top_kospi = sorted(dedup(kospi), key=lambda x: -x["기관1일"])[:12]
    for x in top_kospi:
        sig = signal(x["기관1일"], x["기관5일"])
        lines.append(
            f"| {x['name']} | {fmt_num(x['기관1일'])} | {fmt_num(x['기관5일'])} "
            f"| {x['가속도']:.1f}x | {sig} |"
        )
    lines.append("")

    # ── 섹션2: 급증업종 (가속도 1.5x 이상, 기관1일 > 0) ──────────
    급증 = [x for x in dedup(kospi + kosdaq)
             if x["기관1일"] > 0 and x["가속도"] >= 1.5]
    급증.sort(key=lambda x: -x["가속도"])
    if 급증:
        lines += ["## 섹션2 — 급증업종 (오늘 5일평균 대비 1.5배↑)", ""]
        lines += ["| 업종 | 기관1일 | 5일평균 | 가속도 |",
                  "|------|--------|--------|-------|"]
        for x in 급증[:10]:
            lines.append(
                f"| {x['name']} | {fmt_num(x['기관1일'])} "
                f"| {fmt_num(x['기관5일'])} | 🔴 {x['가속도']:.1f}x |"
            )
        lines.append("")

    # ── 섹션3: 관심 테마 ──────────────────────────────────────────
    interest = [x for x in dedup(themes)
                if any(k in x["name"] for k in INTEREST_THEMES)]
    interest.sort(key=lambda x: -x["기관1일"])
    if interest:
        lines += ["## 섹션3 — 관심 테마 수급", ""]
        lines += ["| 테마 | 기관1일 | 5일평균 | 가속도 | 신호 |",
                  "|------|--------|--------|-------|------|"]
        for x in interest[:15]:
            sig = signal(x["기관1일"], x["기관5일"])
            lines.append(
                f"| {x['name']} | {fmt_num(x['기관1일'])} | {fmt_num(x['기관5일'])} "
                f"| {x['가속도']:.1f}x | {sig} |"
            )
        lines.append("")

    # ── 섹션4: 이탈업종 (기관 매도) ──────────────────────────────
    이탈 = sorted([x for x in dedup(kospi) if x["기관1일"] < 0],
                  key=lambda x: x["기관1일"])[:5]
    if 이탈:
        lines += ["## 섹션4 — 기관 이탈 업종", ""]
        lines += ["| 업종 | 기관1일 | 5일평균 |",
                  "|------|--------|--------|"]
        for x in 이탈:
            lines.append(
                f"| {x['name']} | {fmt_num(x['기관1일'])} | {fmt_num(x['기관5일'])} |"
            )
        lines.append("")

    # ── 요약 한줄 ──────────────────────────────────────────────────
    top3 = [x["name"] for x in top_kospi[:3]]
    lines += [
        "## 오늘의 한줄",
        f"> 기관 매수 집중: **{' > '.join(top3)}**  ",
    ]
    if 급증:
        lines[-1] += f"급증: **{급증[0]['name']}** ({급증[0]['가속도']:.1f}x)"

    return "\n".join(lines)


def send_tg(text: str):
    token   = os.environ.get("TG_BOT_TOKEN", "")
    chat_id = os.environ.get("TG_CHAT_ID", "")
    if not token or not chat_id:
        print("TG 환경변수 없음 — 전송 스킵")
        return
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"},
            timeout=10,
        )


def update_log(today: str, summary: str):
    log_path = BASE / "wiki" / "log.md"
    if not log_path.exists():
        return
    content  = log_path.read_text(encoding="utf-8")
    new_line = f"- {today} — 업종수급 ingest: {summary}\n"
    if "## 작업 이력" in content:
        content = content.replace("## 작업 이력\n", f"## 작업 이력\n{new_line}")
    else:
        content = new_line + content
    log_path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tg", action="store_true")
    args = parser.parse_args()

    path = find_file()
    print(f"파일: {path.name}")

    # 날짜 추출 (파일명에서 MMDD 또는 YYYYMMDD)
    m = re.search(r"(\d{4,8})", path.name)
    if m:
        raw_date = m.group(1)
        if len(raw_date) == 4:  # MMDD
            year = datetime.today().year
            file_date = f"{year}{raw_date}"
        else:
            file_date = raw_date[:8]
    else:
        file_date = datetime.today().strftime("%Y%m%d")

    today_str = f"{file_date[:4]}-{file_date[4:6]}-{file_date[6:8]}"

    xl, wb = open_wb(path)
    try:
        ws = wb.Sheets("업종비중")
        kospi, kosdaq, themes = read_업종비중(ws)
    finally:
        wb.Close(False)
        xl.Quit()

    print(f"KOSPI 업종: {len(dedup(kospi))}개  KOSDAQ: {len(dedup(kosdaq))}개  테마: {len(dedup(themes))}개")

    md = build_markdown(kospi, kosdaq, themes, today_str)

    out_path = OUT_DIR / f"{file_date}_업종수급_요약.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"저장: {out_path.name}")

    # 요약 출력
    top3 = sorted(dedup(kospi), key=lambda x: -x["기관1일"])[:3]
    summary = " > ".join(x["name"] for x in top3)
    print(f"주도업종: {summary}")

    if args.tg:
        send_tg(md[:3000])
        print("텔레그램 전송 완료")

    update_log(today_str, summary)


if __name__ == "__main__":
    main()
