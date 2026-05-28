"""
morning_briefing.py — 아침 시황 브리핑 자동 생성

사용법:
  python morning_briefing.py           # 콘솔 미리보기
  python morning_briefing.py --tg      # 텔레그램 전송
  python morning_briefing.py --save    # out/briefing_YYYYMMDD.md 저장
  python morning_briefing.py --tg --save

흐름:
  1. yfinance + pykrx 로 시장 숫자 자동 수집
  2. raw/미국장/오늘.txt 뉴스 원문 읽기
  3. Gemini 가 스토리 생성 (JSON)
  4. 텔레그램용 / 브리핑용 두 가지 포맷 출력
"""
import sys, os, argparse, json, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from datetime import date, timedelta

TODAY  = date.today().strftime('%Y-%m-%d')
TODAY8 = TODAY.replace('-', '')
BASE   = Path(__file__).parent
NEWS   = BASE / 'raw' / '미국장' / '오늘.txt'
OUT    = BASE / 'out'


# ═══════════════════════════════════════════
# 1. 시장 데이터 수집
# ═══════════════════════════════════════════

def fetch_market():
    import yfinance as yf
    from pykrx import stock as krx

    # ── 미국 + 매크로 ──────────────────────
    SYM = {
        'sp500': '^GSPC', 'nasdaq': '^IXIC', 'dow': '^DJI',
        'russell': '^RUT', 'vix': '^VIX', 'phlx': '^SOX',
        'wti': 'CL=F', 'us10y': '^TNX',
        'dxy': 'DX-Y.NYB', 'gold': 'GC=F', 'usdkrw': 'KRW=X',
    }
    us = {}
    for k, sym in SYM.items():
        try:
            h = yf.Ticker(sym).history(period='2d')
            if len(h) >= 2:
                p, c = h['Close'].iloc[-2], h['Close'].iloc[-1]
                us[k] = {'price': float(c), 'chg': float((c/p-1)*100)}
            elif len(h) == 1:
                c = h['Close'].iloc[-1]
                us[k] = {'price': float(c), 'chg': 0.0}
        except:
            us[k] = None

    # ── 한국 ETF 대리 ──────────────────────
    ETF = {
        'kospi':   ('069500', '코스피'),
        'kosdaq':  ('229200', '코스닥'),
        'semi':    ('091160', '반도체'),
        'battery': ('305720', '2차전지'),
        'defense': ('455890', '방산'),
        'ship':    ('466920', '조선'),
        'power':   ('357870', '전력기기'),
        'bio':     ('244580', '바이오'),
    }
    prev5 = (date.today() - timedelta(days=5)).strftime('%Y%m%d')
    kr = {}
    for k, (code, name) in ETF.items():
        try:
            df = krx.get_market_ohlcv(prev5, TODAY8, code)
            if len(df) >= 2:
                p, c = float(df['종가'].iloc[-2]), float(df['종가'].iloc[-1])
                kr[k] = {'name': name, 'price': c, 'chg': round((c/p-1)*100, 2)}
        except:
            kr[k] = None

    return us, kr


def fmt_chg(d, key):
    if not d or d.get(key) is None: return '—'
    v = d[key]
    return f'{v:+.2f}%' if isinstance(v, float) else f'{v}'

def fmt_price(d, key, fmt='.1f'):
    if not d or d.get(key) is None: return '—'
    return f'{d[key]:{fmt}}'


# ═══════════════════════════════════════════
# 2. Gemini 스토리 생성
# ═══════════════════════════════════════════

PROMPT = """
당신은 주식 시장 분석가입니다. 아래 [시장데이터]와 [뉴스원문]을 바탕으로
아침 브리핑 스토리를 생성하세요.

규칙:
- JSON만 출력. 설명 없이.
- global_issue, macro_issue: 중요한 이슈가 없으면 null. 있으면 1~2줄 스토리.
- 섹터명은 한국 주식시장 기준.
- korea_links: 미국 강세/약세가 국내에 미치는 영향. 구체적 종목명 포함.
- 모든 텍스트는 한국어.

출력 형식:
{
  "one_line": "오늘 시장 전체를 한 줄로 (15~25자)",
  "global_issue": "지정학·전쟁·무역 이슈 스토리 (없으면 null)",
  "macro_issue": "금리·연준·환율·물가 이슈 스토리 (없으면 null)",
  "market_state": "투자환경 한 줄 (VIX·금리·달러 종합 해석)",
  "us_strong": [
    {"sector": "섹터명", "chg": "+X%", "reason": "이유 1줄"}
  ],
  "us_weak": [
    {"sector": "섹터명", "chg": "-X%", "reason": "이유 1줄"}
  ],
  "kr_strong": [
    {"sector": "섹터명", "chg": "+X%", "reason": "이유 1줄"}
  ],
  "kr_weak": [
    {"sector": "섹터명", "chg": "-X%", "reason": "이유 1줄"}
  ],
  "kr_special": "한국장 특징 1~2줄 (K자 쏠림, 수급 이슈 등)",
  "korea_links": [
    {"from": "미국 섹터/이슈", "to": "국내 종목/섹터", "signal": "🔴/🟠/🟡", "comment": "연결 이유 1줄"}
  ],
  "today_events": ["오늘 주의할 이벤트 (금통위, 지표 발표 등)"]
}

[시장데이터]
{market_data}

[뉴스원문]
{news_text}
"""

def call_gemini(market_str, news_text):
    from google import genai
    env = BASE / '.env'
    cfg = {}
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    api_key = cfg.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('.env에 GEMINI_API_KEY 없음')

    client = genai.Client(api_key=api_key)
    prompt = PROMPT.replace('{market_data}', market_str).replace('{news_text}', news_text[:4000])
    resp   = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)

    raw = resp.text.strip()
    if '```' in raw:
        raw = raw.split('```')[1]
        if raw.startswith('json'): raw = raw[4:]
    return json.loads(raw.strip())


# ═══════════════════════════════════════════
# 3. 시장 데이터 → 텍스트 요약
# ═══════════════════════════════════════════

def market_to_str(us, kr):
    lines = []
    # 미국 지수
    for k, name in [('sp500','S&P500'),('nasdaq','나스닥'),('dow','다우'),
                    ('russell','러셀2000'),('phlx','필라반'),('vix','VIX')]:
        d = us.get(k)
        if d: lines.append(f'{name}: {d["price"]:.2f} ({d["chg"]:+.2f}%)')
    # 매크로
    for k, name in [('wti','WTI'),('us10y','미10년물'),('dxy','DXY'),
                    ('usdkrw','달러원'),('gold','금')]:
        d = us.get(k)
        if d: lines.append(f'{name}: {d["price"]:.2f} ({d["chg"]:+.2f}%)')
    # 한국
    for k in ['kospi','kosdaq','semi','battery','defense','ship','power','bio']:
        d = kr.get(k)
        if d: lines.append(f'한국{d["name"]}: {d["price"]:.0f} ({d["chg"]:+.2f}%)')
    return '\n'.join(lines)


# ═══════════════════════════════════════════
# 4. 텔레그램 메시지 빌더
# ═══════════════════════════════════════════

def build_telegram(d: dict, us: dict, kr: dict) -> str:
    sp  = us.get('sp500') or {}
    nq  = us.get('nasdaq') or {}
    ph  = us.get('phlx') or {}
    vx  = us.get('vix') or {}
    wt  = us.get('wti') or {}
    y10 = us.get('us10y') or {}
    dx  = us.get('dxy') or {}
    krw = us.get('usdkrw') or {}

    lines = [
        f"📋 <b>STOCK BRAIN 모닝 브리핑</b>  {TODAY}",
        "",
        f"<b>「 {d.get('one_line', '')} 」</b>",
        "",
    ]

    # 글로벌/매크로 이슈 (있을 때만)
    if d.get('global_issue'):
        lines += [f"🌍 <b>글로벌</b>  {d['global_issue']}", ""]
    if d.get('macro_issue'):
        lines += [f"⚡ <b>매크로</b>  {d['macro_issue']}", ""]

    # 핵심 숫자
    lines += [
        "📊 <b>핵심 지표</b>",
        f"  VIX {vx.get('price', '—'):.1f}  |  WTI ${wt.get('price', '—'):.1f} ({wt.get('chg', 0):+.1f}%)",
        f"  10년물 {y10.get('price', '—'):.2f}%  |  달러원 {krw.get('price', '—'):,.0f}원",
        f"  DXY {dx.get('price', '—'):.1f}  |  <i>{d.get('market_state', '')}</i>",
        "",
    ]

    # 미국장
    lines += [
        f"🇺🇸 <b>미국장</b>  S&P {sp.get('chg', 0):+.2f}%  나스닥 {nq.get('chg', 0):+.2f}%  필라반 {ph.get('chg', 0):+.2f}%",
    ]
    for s in (d.get('us_strong') or [])[:3]:
        lines.append(f"  🔴 {s['sector']} {s.get('chg','')}  {s['reason']}")
    for s in (d.get('us_weak') or [])[:2]:
        lines.append(f"  ⚫ {s['sector']} {s.get('chg','')}  {s['reason']}")
    lines.append("")

    # 한국장
    kp = kr.get('kospi') or {}
    kd = kr.get('kosdaq') or {}
    lines += [
        f"🇰🇷 <b>한국장</b>  코스피 {kp.get('chg', 0):+.2f}%  코스닥 {kd.get('chg', 0):+.2f}%",
    ]
    for s in (d.get('kr_strong') or [])[:2]:
        lines.append(f"  🔴 {s['sector']} {s.get('chg','')}  {s['reason']}")
    for s in (d.get('kr_weak') or [])[:2]:
        lines.append(f"  ⚫ {s['sector']} {s.get('chg','')}  {s['reason']}")
    if d.get('kr_special'):
        lines.append(f"  📌 {d['kr_special']}")
    lines.append("")

    # 오늘 연결 포인트
    lines.append("🔗 <b>오늘 국내 연결</b>")
    for lk in (d.get('korea_links') or [])[:4]:
        sig = lk.get('signal', '·')
        lines.append(f"  {sig} {lk['from']} → {lk['to']}")
        lines.append(f"      └ {lk['comment']}")

    # 오늘 이벤트
    events = d.get('today_events') or []
    if events:
        lines += ["", "🗓 <b>오늘 이벤트</b>"]
        for e in events:
            lines.append(f"  · {e}")

    return "\n".join(lines)


# ═══════════════════════════════════════════
# 5. 아침브리핑 마크다운 빌더
# ═══════════════════════════════════════════

def build_note(d: dict, us: dict, kr: dict) -> str:
    sp  = us.get('sp500') or {}
    nq  = us.get('nasdaq') or {}
    dw  = us.get('dow') or {}
    ph  = us.get('phlx') or {}
    vx  = us.get('vix') or {}
    wt  = us.get('wti') or {}
    y10 = us.get('us10y') or {}
    dx  = us.get('dxy') or {}
    krw = us.get('usdkrw') or {}
    gd  = us.get('gold') or {}
    kp  = kr.get('kospi') or {}
    kd  = kr.get('kosdaq') or {}

    lines = [
        f"# STOCK BRAIN 모닝 브리핑  {TODAY}",
        "",
        f"> **{d.get('one_line', '')}**",
        "",
        "---",
        "",
        "## ① 지금 세상이 어떤가",
        "",
    ]

    if d.get('global_issue'):
        lines += [f"🌍 **글로벌 이슈**", f"{d['global_issue']}", ""]
    if d.get('macro_issue'):
        lines += [f"⚡ **매크로 이슈**", f"{d['macro_issue']}", ""]

    lines += [
        "📊 **핵심 숫자**",
        "",
        f"| 지표 | 현재 | 변화 | 해석 |",
        f"|------|------|------|------|",
        f"| VIX | {vx.get('price','—'):.1f} | {vx.get('chg',0):+.2f}% | {'안정' if (vx.get('price') or 25) < 20 else '불안'} |",
        f"| WTI | ${wt.get('price','—'):.1f} | {wt.get('chg',0):+.2f}% | {'물가 안정' if (wt.get('price') or 90) < 85 else '물가 부담'} |",
        f"| 미 10년물 | {y10.get('price','—'):.2f}% | {y10.get('chg',0):+.2f}% | {'완화적' if (y10.get('price') or 5) < 4.3 else '긴축 압박'} |",
        f"| DXY | {dx.get('price','—'):.2f} | {dx.get('chg',0):+.2f}% | {'달러약세(우호)' if (dx.get('price') or 101) < 100 else '달러강세'} |",
        f"| 달러원 | {krw.get('price','—'):,.0f}원 | {krw.get('chg',0):+.2f}% | — |",
        f"| 금 | ${gd.get('price','—'):,.0f} | {gd.get('chg',0):+.2f}% | — |",
        "",
        f"> {d.get('market_state', '')}",
        "",
        "---",
        "",
        "## ② 어젯밤 미국장",
        "",
        f"**S&P {sp.get('chg',0):+.2f}%  나스닥 {nq.get('chg',0):+.2f}%  다우 {dw.get('chg',0):+.2f}%  필라반 {ph.get('chg',0):+.2f}%**",
        "",
        "### 강한 섹터",
    ]
    for s in (d.get('us_strong') or []):
        lines.append(f"- 🔴 **{s['sector']}** {s.get('chg','')} — {s['reason']}")

    lines += ["", "### 약한 섹터"]
    for s in (d.get('us_weak') or []):
        lines.append(f"- ⚫ **{s['sector']}** {s.get('chg','')} — {s['reason']}")

    lines += [
        "",
        "---",
        "",
        "## ③ 전일 한국장",
        "",
        f"**코스피 {kp.get('chg',0):+.2f}%  코스닥 {kd.get('chg',0):+.2f}%**",
        "",
        "### 강한 섹터",
    ]
    for s in (d.get('kr_strong') or []):
        lines.append(f"- 🔴 **{s['sector']}** {s.get('chg','')} — {s['reason']}")

    lines += ["", "### 약한/쉬는 섹터"]
    for s in (d.get('kr_weak') or []):
        lines.append(f"- ⚫ **{s['sector']}** {s.get('chg','')} — {s['reason']}")

    if d.get('kr_special'):
        lines += ["", f"> 📌 {d['kr_special']}"]

    lines += [
        "",
        "---",
        "",
        "## ④ 오늘 국내 연결 포인트",
        "",
        "| 미국 이슈 | 국내 종목/섹터 | 신호 | 근거 |",
        "|-----------|--------------|------|------|",
    ]
    for lk in (d.get('korea_links') or []):
        lines.append(
            f"| {lk.get('from','')} | {lk.get('to','')} "
            f"| {lk.get('signal','')} | {lk.get('comment','')} |"
        )

    events = d.get('today_events') or []
    if events:
        lines += ["", "---", "", "## ⑤ 오늘 이벤트"]
        for e in events:
            lines.append(f"- {e}")

    return "\n".join(lines)


# ═══════════════════════════════════════════
# 6. 텔레그램 발송
# ═══════════════════════════════════════════

def send_telegram(text: str):
    env = BASE / '.env'
    cfg = {}
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    token, chat_id = cfg.get('BOT_TOKEN',''), cfg.get('CHAT_ID','')
    if not token or not chat_id:
        print('텔레그램 설정 없음'); return
    url  = f'https://api.telegram.org/bot{token}/sendMessage'
    data = urllib.parse.urlencode(
        {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}).encode()
    with urllib.request.urlopen(
            urllib.request.Request(url, data), timeout=10) as r:
        if json.loads(r.read()).get('ok'):
            print('✅ 텔레그램 전송 완료')
        else:
            print('❌ 텔레그램 전송 실패')


# ═══════════════════════════════════════════
# 7. 메인
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tg',   action='store_true', help='텔레그램 발송')
    parser.add_argument('--save', action='store_true', help='MD 파일 저장')
    args = parser.parse_args()

    # 뉴스 원문
    if not NEWS.exists():
        print(f'뉴스 파일 없음: {NEWS}')
        print('→ raw/미국장/오늘.txt 에 뉴스 붙여넣고 다시 실행하세요')
        return
    news_text = NEWS.read_text(encoding='utf-8')

    # 시장 데이터 수집
    print(f'[{TODAY}] 시장 데이터 수집 중...')
    us, kr = fetch_market()

    market_str = market_to_str(us, kr)
    print('Gemini 스토리 생성 중...')
    data = call_gemini(market_str, news_text)

    # 텔레그램 포맷
    tg_msg = build_telegram(data, us, kr)
    # 브리핑 노트
    note   = build_note(data, us, kr)

    # 콘솔 미리보기 (태그 제거)
    preview = tg_msg
    for tag in ['<b>','</b>','<i>','</i>','<code>','</code>']:
        preview = preview.replace(tag, '')
    print()
    print('─' * 60)
    print(preview)
    print('─' * 60)

    if args.tg:
        print()
        send_telegram(tg_msg)

    if args.save:
        OUT.mkdir(exist_ok=True)
        p = OUT / f'briefing_{TODAY}.md'
        p.write_text(note, encoding='utf-8')
        print(f'✅ 브리핑 저장: {p}')

    # 캐시 저장
    (BASE / 'raw' / '미국장' / f'{TODAY}_briefing.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
