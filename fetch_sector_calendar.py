#!/usr/bin/env python3
"""
fetch_sector_calendar.py
섹터별 주요 일정 수집 via Gemini API + Google Search 그라운딩
2단계: 1) 매크로 일정  2) 섹터별 개별 일정

Usage:
    python fetch_sector_calendar.py                          # 전체 16섹터
    python fetch_sector_calendar.py --sectors 반도체,방산,조선
    python fetch_sector_calendar.py --tg                     # 텔레그램 전송 포함
"""

import os, json, re, time, argparse, sys, io
import requests
from datetime import date

# Windows 터미널 한글 출력
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from dotenv import load_dotenv

from google import genai
from google.genai import types

# ─── 환경설정 ─────────────────────────────────────────────────────────────────
load_dotenv()
GEMINI_KEY  = os.getenv("GEMINI_API_KEY")
BOT_TOKEN   = os.getenv("BOT_TOKEN")
CHAT_ID     = os.getenv("CHAT_ID")
TODAY       = date.today().strftime("%Y-%m-%d")
TODAY_LABEL = date.today().strftime("%Y%m%d")

BASE   = Path(__file__).parent
CAL_DIR = BASE / "raw" / "캘린더"
CAL_DIR.mkdir(parents=True, exist_ok=True)

WATCHLIST_PATH = BASE / "watchlist.json"

DAILY_SECTORS = [
    "반도체", "방산", "조선", "LNG", "바이오", "우주", "로봇",
    "자동차", "이차전지", "전력", "원전", "신재생", "화장품", "미용", "철강", "엔터",
]

# 섹터별 쿼리에 포함할 최대 종목 수 (너무 많으면 토큰 낭비)
MAX_STOCKS_PER_QUERY = 12

# ─── Gemini 클라이언트 ─────────────────────────────────────────────────────────
client = genai.Client(api_key=GEMINI_KEY)

SEARCH_TOOL = types.Tool(google_search=types.GoogleSearch())

GENERATE_CFG = types.GenerateContentConfig(
    tools=[SEARCH_TOOL],
    temperature=0.2,
)


def ask_gemini(prompt: str, retries: int = 2) -> str:
    """Gemini 2.5 Flash에 쿼리. 검색 그라운딩 포함."""
    for attempt in range(retries + 1):
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=GENERATE_CFG,
            )
            return resp.text or ""
        except Exception as e:
            if attempt < retries:
                print(f"    재시도 {attempt+1}/{retries}: {e}")
                time.sleep(5)
            else:
                print(f"    Gemini 오류: {e}")
                return ""


def extract_json(text: str) -> list:
    """응답 텍스트에서 JSON 배열 추출. 검색 citation 등 비JSON 텍스트 무시."""
    # ```json ... ``` 코드 블록 우선
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        # 첫 번째 [ ... ] 블록 추출
        m = re.search(r"(\[.*\])", text, re.DOTALL)
        if not m:
            return []
        raw = m.group(1)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 불완전한 JSON → 마지막 } 뒤에 ] 추가 시도
        try:
            raw_fixed = raw.rsplit("}", 1)[0] + "}]"
            return json.loads(raw_fixed)
        except Exception:
            return []


# ─── 프롬프트 ─────────────────────────────────────────────────────────────────
MACRO_PROMPT = f"""
오늘은 {TODAY}입니다. 한국 주식시장 투자자 관점에서
2026년 5월 27일 ~ 2026년 6월 30일 기간의 주요 매크로·정책 일정을 검색해서 정리해줘.

포함 항목 (인터넷 검색으로 최신 정보 확인):
- 미국 FOMC 회의 일정 및 의사록 발표
- 한국 수출지표 발표일 (산업통상자원부 무역통계)
- MSCI 지수 리뷰·발표 (반기 리뷰 등)
- 한국은행 금융통화위원회 기준금리 결정
- 미국·한국 CPI / PPI / GDP 발표
- 한국 주요 정부 정책 발표 (반도체·방산·원전 관련)

반드시 순수 JSON 배열로만 응답해줘 (설명 텍스트 없이):
[
  {{"date": "YYYY-MM-DD", "event": "이벤트명", "type": "FOMC|수출지표|MSCI|금통위|경제지표|정책", "importance": "[HIGH]|[MID]|[LOW]", "desc": "주식시장 영향 1줄", "confirmed": true}},
  ...
]
날짜가 불확실하면 confirmed: false로 표시. 정보 없으면 [] 반환.
"""


def make_sector_prompt(sector: str, stocks: list[str]) -> str:
    stocks_str = "·".join(stocks[:MAX_STOCKS_PER_QUERY])
    return f"""
오늘은 {TODAY}입니다. 한국 주식 투자자 관점에서
{sector} 섹터의 2026년 5월 27일 ~ 2026년 6월 30일 주요 일정을 인터넷에서 검색해서 정리해줘.

주요 관련 종목: {stocks_str}

포함 항목:
- 주요 상장사 분기실적 발표 일정 (IR 일정 공지 포함)
- 주요 IR·NDR·애널리스트데이 이벤트
- 섹터 관련 정부 정책 발표·규제 결정 예정
- 국내외 주요 전시/컨퍼런스 (예: SEMICON, 에어쇼, 조선기자재전 등)
- 대형 수주·계약 발표 예상 이벤트
- 수출 데이터 발표 (해당 품목이 있다면)

반드시 순수 JSON 배열로만 응답해줘 (설명 텍스트 없이):
[
  {{"date": "YYYY-MM-DD", "company": "회사명 또는 null", "event": "이벤트명", "type": "실적발표|IR|정책|전시|수주|기타", "importance": "[HIGH]|[MID]|[LOW]", "desc": "투자 포인트 1줄", "confirmed": true}},
  ...
]
정보가 없거나 확인 안 되면 빈 배열 [] 반환.
"""


# ─── 텔레그램 ─────────────────────────────────────────────────────────────────
def send_tg(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")


# ─── watchlist 로드 ───────────────────────────────────────────────────────────
def load_watchlist() -> dict:
    if not WATCHLIST_PATH.exists():
        print("⚠️ watchlist.json 없음 — 종목명 없이 섹터명만으로 쿼리")
        return {}
    return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))


def get_sector_stocks(watchlist: dict, sector: str) -> list[str]:
    """섹터의 모든 종목명 플랫 리스트 반환."""
    sector_data = watchlist.get(sector, {})
    stocks = []
    for subsector, items in sector_data.items():
        for item in items:
            if item.get("name") and item["name"] not in stocks:
                stocks.append(item["name"])
    return stocks


# ─── 요약 MD 생성 ─────────────────────────────────────────────────────────────
def events_to_md_section(events: list, label: str) -> str:
    if not events:
        return f"\n### {label}\n(이벤트 없음)\n"

    lines = [f"\n### {label}"]
    # 날짜순 정렬
    sorted_ev = sorted(events, key=lambda x: x.get("date", "9999"))
    for e in sorted_ev:
        d = e.get("date", "?")
        company = e.get("company") or ""
        ev = e.get("event", "?")
        imp = e.get("importance", "[LOW]")
        desc = e.get("desc", "")
        confirmed = "" if e.get("confirmed", True) else " (추정)"
        who = f"[{company}] " if company else ""
        lines.append(f"- `{d}`{confirmed} {imp} {who}{ev} — {desc}")
    return "\n".join(lines)


def build_summary_md(macro: list, sectors: dict) -> str:
    parts = [
        f"# 섹터 캘린더 — {TODAY} 기준",
        f"> 수집일: {TODAY}  |  대상: {TODAY} ~ 2026-06-30  |  Gemini 2.5 Flash + Google Search\n",
        "---\n",
        "## [중요] 매크로 일정",
    ]

    # 매크로
    if macro:
        sorted_m = sorted(macro, key=lambda x: x.get("date", "9999"))
        for e in sorted_m:
            confirmed = "" if e.get("confirmed", True) else " (추정)"
            parts.append(
                f"- `{e.get('date','?')}`{confirmed} {e.get('importance','[LOW]')} "
                f"**{e.get('event','?')}** — {e.get('desc','')}"
            )
    else:
        parts.append("(데이터 없음)")

    parts.append("\n---\n")
    parts.append("## [일정] 섹터별 일정")

    for sector in DAILY_SECTORS:
        evs = sectors.get(sector, [])
        parts.append(events_to_md_section(evs, sector))

    parts.append("\n---")
    parts.append(f"\n*생성: {TODAY} by fetch_sector_calendar.py*")
    return "\n".join(parts)


# ─── 메인 ─────────────────────────────────────────────────────────────────────
def run(target_sectors: list[str], send_telegram: bool):
    watchlist = load_watchlist()
    result = {"generated_at": TODAY, "macro": [], "sectors": {}}

    # ── Step 1: 매크로 ──────────────────────────────────────────────
    print("\n[Step 1] 매크로 일정 수집 중...")
    macro_text = ask_gemini(MACRO_PROMPT)
    macro_events = extract_json(macro_text)
    result["macro"] = macro_events
    print(f"  → 매크로 이벤트 {len(macro_events)}건 수집")

    # 매크로 중간 저장
    macro_path = CAL_DIR / f"{TODAY_LABEL}_매크로.json"
    macro_path.write_text(json.dumps(macro_events, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {macro_path.name}")

    time.sleep(3)  # rate limit

    # ── Step 2: 섹터별 ───────────────────────────────────────────────
    print("\n[Step 2] 섹터별 일정 수집 중...")
    for i, sector in enumerate(target_sectors, 1):
        stocks = get_sector_stocks(watchlist, sector)
        prompt = make_sector_prompt(sector, stocks)

        print(f"  [{i:02d}/{len(target_sectors):02d}] {sector} ({len(stocks)}종목)...", end=" ", flush=True)
        text = ask_gemini(prompt)
        events = extract_json(text)
        result["sectors"][sector] = events
        print(f"{len(events)}건")

        # 섹터별 개별 저장 (중간에 끊겨도 보존)
        sec_path = CAL_DIR / f"{TODAY_LABEL}_{sector}.json"
        sec_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

        if i < len(target_sectors):
            time.sleep(2)  # API rate limit 방지

    # ── 통합 JSON 저장 ───────────────────────────────────────────────
    full_path = CAL_DIR / f"{TODAY_LABEL}_섹터캘린더.json"
    full_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 요약 MD 저장 ────────────────────────────────────────────────
    md_text = build_summary_md(result["macro"], result["sectors"])
    md_path = CAL_DIR / f"{TODAY_LABEL}_캘린더_요약.md"
    md_path.write_text(md_text, encoding="utf-8")

    print(f"\n[완료] 완료")
    print(f"   통합 JSON : {full_path.name}")
    print(f"   요약 MD   : {md_path.name}")

    # ── 집계 출력 ────────────────────────────────────────────────────
    total_ev = sum(len(v) for v in result["sectors"].values())
    print(f"\n[요약] 수집 결과 요약")
    print(f"   매크로 이벤트: {len(result['macro'])}건")
    print(f"   섹터 이벤트 합계: {total_ev}건")

    top = [(s, len(e)) for s, e in result["sectors"].items() if e]
    top.sort(key=lambda x: -x[1])
    for s, cnt in top[:5]:
        print(f"   {s}: {cnt}건")

    # ── 텔레그램 ─────────────────────────────────────────────────────
    if send_telegram:
        macro_str = "\n".join(
            f"• {e.get('date','?')} {e.get('importance','')} {e.get('event','')} — {e.get('desc','')}"
            for e in sorted(result["macro"], key=lambda x: x.get("date","9999"))[:5]
        )
        hot_sectors = "\n".join(f"• {s}: {cnt}건" for s, cnt in top[:5])
        msg = (
            f"[일정] <b>섹터 캘린더 수집 완료 ({TODAY})</b>\n\n"
            f"<b>이번주~6월 매크로 주요 일정:</b>\n{macro_str or '(없음)'}\n\n"
            f"<b>이벤트 많은 섹터 TOP5:</b>\n{hot_sectors or '(없음)'}\n\n"
            f"총 {total_ev}건 수집 → raw/캘린더/ 확인"
        )
        send_tg(msg)
        print("텔레그램 전송 완료")

    return result


def main():
    parser = argparse.ArgumentParser(description="섹터 캘린더 수집")
    parser.add_argument("--sectors", type=str, default="",
                        help="쉼표 구분 섹터명 (예: 반도체,방산). 생략시 전체 16섹터")
    parser.add_argument("--tg", action="store_true", help="텔레그램 전송")
    args = parser.parse_args()

    if args.sectors:
        target = [s.strip() for s in args.sectors.split(",") if s.strip()]
    else:
        target = DAILY_SECTORS

    print(f"[{TODAY}] 섹터 캘린더 수집 시작")
    print(f"대상 섹터: {', '.join(target)}")
    run(target, send_telegram=args.tg)


if __name__ == "__main__":
    main()
