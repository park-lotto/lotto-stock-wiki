#!/usr/bin/env python3
"""
daily_scenario.py — 증권사 리포트 + 텔레그램 + 블로그 종합 → 시장 시나리오

사용:
  python daily_scenario.py                      # 오늘
  python daily_scenario.py --date 2026-06-05   # 특정 날짜
"""

import sys, os, json, re, argparse
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')

BASE      = Path(__file__).parent
CRAWL_BOT = Path(r"C:\Users\TheRose\crawling_bot_data")
OUT_DIR   = BASE / "out"

# 텔레그램 우선 채널 (인사이트 밀도 높은 순)
TG_PRIORITY = ['그로스리서치', '리포트요약', '키움시황', '하나반도체',
               '대신시황', '태린이아빠', '잠실개미고급수집', '신한리서치']

PROMPT = """\
한국 주식 유튜버의 AI 분석 파트너다.
아래 데이터를 보고 오늘의 시장 브리핑 카드를 만들어라.

날짜: {date}

=== 증권사 리포트 ===
{wisereport}

=== 블로그 분석가 ===
{blogs}

=== 텔레그램 ===
{telegram}

---

아래 형식을 그대로 써라. 형식 밖으로 나오지 마라.

규칙:
- 한 줄 = 한 문장. 절대 길게 쓰지 마라.
- 숫자 없으면 쓰지 마라. 막연한 표현 금지.
- 종목 표는 칸 맞춰서.
- 주식 1년차도 바로 이해하는 쉬운 말로 써라.
- 전문용어 변환 규칙 (반드시 지켜라):
  ETF → 펀드 / TP → 목표주가 / 리밸런싱 → 비중 조정
  Capex → 설비 투자 / 지정학 → 전쟁·분쟁 / 역성장 → 판매 감소
  수급 → 돈 흐름 / 자금 쏠림 → 돈이 몰리는 중
- 말투: "~야", "~있어", "~중", "~예정" 처럼 자연스럽게. 딱딱한 명사형 금지.
- 핵심 이유는 "왜 중요한지" 한 줄로. "~해서 주가 오를 수 있어" 처럼.

━━━ {date} 시장 브리핑 ━━━

📌 오늘 핵심
• (자금 흐름 한 줄 — 어디서 빠져서 어디로)
• (오늘 가장 중요한 이슈 한 줄)
• (시장 분위기 한 줄)

🔴 강세 종목
종목명        TP·수치          핵심 이유
(종목1)       TP XXX만 (+XX%) 이유 10자
(종목2)       TP XXX만 (+XX%) 이유 10자
(종목3)       수치             이유 10자

🔵 리스크 종목 (있으면)
종목명        수치             이유 10자

⚠️ 리스크
• (리스크1 — 수치 포함)
• (리스크2 — 수치 포함)
• (리스크3 — 수치 포함)

📅 챙길 일정
• (날짜/시점 + 이벤트)
• (날짜/시점 + 이벤트)

💡 시나리오
강세: (조건) → (흐름)
약세: (조건) → (흐름)

🎯 오늘 한 줄
(행동 지침 포함, 20자 이내)
"""

def get_gemini():
    from google import genai
    env = BASE / '.env'
    cfg = {}
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    api_key = cfg.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
    return genai.Client(api_key=api_key)

def load_wisereport(date_str):
    f = BASE / "raw" / "wisereport" / f"{date_str}_parsed.json"
    if not f.exists():
        return "데이터 없음"
    data = json.loads(f.read_text(encoding='utf-8'))
    corps = data.get('corp', [])
    lines = []
    for c in corps:
        if len(c) < 8:
            continue
        broker, ticker_full = str(c[0]), str(c[1])
        tp_dir, tp, title   = str(c[4]), str(c[5]), str(c[7])
        content             = str(c[8]) if len(c) > 8 else ''
        name = re.sub(r'\[.*?\]', '', ticker_full).strip()
        row  = f"- [{broker}] {name} | TP {tp_dir} {tp}"
        if title:
            row += f" | {title[:40]}"
        lines.append(row)
        if content:
            lines.append(f"  {content[:80]}")
    return "\n".join(lines)

def load_blogs(date_str):
    blog_dir = CRAWL_BOT / date_str / "blog"
    if not blog_dir.exists():
        return "데이터 없음"
    files = sorted(blog_dir.glob("*.md"))
    parts = []
    for f in files:
        name    = f.stem[13:45] if len(f.stem) > 13 else f.stem
        content = f.read_text(encoding='utf-8', errors='replace')[:1000]
        parts.append(f"[{name}]\n{content}")
    return "\n\n---\n\n".join(parts)

def load_telegram(date_str):
    tg_dir = CRAWL_BOT / date_str / "telegram"
    if not tg_dir.exists():
        tg_dir = BASE / "raw" / "telegram" / date_str
    if not tg_dir.exists():
        return "데이터 없음"
    parts = []
    for name in TG_PRIORITY:
        matched = list(tg_dir.glob(f"*{name}*.md"))
        if not matched:
            continue
        content = matched[0].read_text(encoding='utf-8', errors='replace')[:700]
        parts.append(f"[{name}]\n{content}")
    return "\n\n".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=date.today().strftime('%Y-%m-%d'))
    args = ap.parse_args()
    date_str = args.date

    print(f"\n{'='*50}\n daily_scenario — {date_str}\n{'='*50}\n")

    print("📊 wisereport...", end=' ', flush=True)
    wr = load_wisereport(date_str)
    print(f"{wr.count(chr(10))+1}줄")

    print("📝 블로그...", end=' ', flush=True)
    bl = load_blogs(date_str)
    bl_kb = len(bl.encode('utf-8')) // 1024
    print(f"~{bl_kb}KB ({bl.count('---')+1}개)")

    print("📱 텔레그램...", end=' ', flush=True)
    tg = load_telegram(date_str)
    print(f"~{len(tg.encode('utf-8'))//1024}KB")

    print("\n🤖 Gemini 시나리오 생성 중...\n")

    client = get_gemini()
    prompt = (PROMPT
        .replace('{date}',      date_str)
        .replace('{wisereport}', wr[:3500])
        .replace('{blogs}',      bl[:9000])
        .replace('{telegram}',   tg[:3500]))

    resp     = client.models.generate_content(model='gemini-3-flash-preview', contents=prompt)
    scenario = resp.text

    OUT_DIR.mkdir(exist_ok=True)
    out_file = OUT_DIR / f"scenario_{date_str}.md"
    out_file.write_text(scenario, encoding='utf-8')

    print(scenario)
    print(f"\n✅ 저장: {out_file}")
    return out_file

if __name__ == '__main__':
    main()
