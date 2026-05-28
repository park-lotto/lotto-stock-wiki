"""
market_check.py — 전체 시황 투자환경 체크
매일 장 시작 전 실행. 투자할 만한 환경인지 레이어별로 판단.

사용법:
  python market_check.py        # 콘솔 출력
  python market_check.py --tg   # 텔레그램 발송
"""
import sys, os, argparse, json, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from datetime import date, datetime
import yfinance as yf
from pykrx import stock as krx

TODAY = date.today().strftime('%Y-%m-%d')
BASE  = Path(__file__).parent

# ──────────────────────────────────────────
# 1. 데이터 수집
# ──────────────────────────────────────────

def fetch_us(period='2d'):
    """미국장 + 매크로 지표"""
    symbols = {
        'sp500':    '^GSPC',
        'nasdaq':   '^IXIC',
        'dow':      '^DJI',
        'russell':  '^RUT',
        'vix':      '^VIX',
        'phlx':     '^SOX',   # 필라델피아반도체
        'wti':      'CL=F',
        'us10y':    '^TNX',
        'dxy':      'DX-Y.NYB',
        'gold':     'GC=F',
        'usdkrw':   'KRW=X',
    }
    result = {}
    for key, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period=period)
            if len(h) >= 2:
                prev = h['Close'].iloc[-2]
                cur  = h['Close'].iloc[-1]
                result[key] = {'price': cur, 'prev': prev, 'chg': (cur/prev-1)*100}
            elif len(h) == 1:
                cur = h['Close'].iloc[-1]
                result[key] = {'price': cur, 'prev': cur, 'chg': 0.0}
        except:
            result[key] = None
    return result

def fetch_kr():
    """한국장 ETF 대리 지표"""
    etfs = {
        'kospi':  ('069500', '코스피'),
        'kosdaq': ('229200', '코스닥'),
        'semi':   ('091160', '반도체'),
        'battery':('305720', '2차전지'),
        'defense':('455890', '방산'),
        'ship':   ('466920', '조선'),
    }
    result = {}
    try:
        start = TODAY.replace('-','')
        # 전거래일 포함하려면 이틀치
        from datetime import timedelta
        prev_d = (date.today() - timedelta(days=5)).strftime('%Y%m%d')
        for key, (code, name) in etfs.items():
            df = krx.get_market_ohlcv(prev_d, start, code)
            if len(df) >= 2:
                p = df['종가'].iloc[-2]
                c = df['종가'].iloc[-1]
                v = df['거래량'].iloc[-1]
                result[key] = {'name': name, 'price': c, 'prev': p,
                               'chg': (c/p-1)*100, 'vol': v}
            elif len(df) == 1:
                c = df['종가'].iloc[-1]
                result[key] = {'name': name, 'price': c, 'prev': c,
                               'chg': 0.0, 'vol': df['거래량'].iloc[-1]}
    except:
        pass
    return result

# ──────────────────────────────────────────
# 2. 신호 판단 로직
# ──────────────────────────────────────────

def signal(val, good_thresh, bad_thresh, higher_is_good=True):
    """값 → 🔴/🟠/🟡/⚫ 신호"""
    if higher_is_good:
        if val >= good_thresh:  return '🔴'
        if val <= bad_thresh:   return '⚫'
        if val > 0:             return '🟠'
        return '🟡'
    else:  # lower is good
        if val <= good_thresh:  return '🔴'
        if val >= bad_thresh:   return '⚫'
        if val < 0:             return '🟠'
        return '🟡'

def score_macro(us):
    """매크로 환경 점수 (0~5)"""
    s = 0
    checks = []

    vix = us.get('vix', {}) or {}
    v = vix.get('price', 25)
    if v < 16:
        s += 1; checks.append(f'VIX {v:.1f} ✅ 저변동성')
    elif v < 22:
        s += 0.5; checks.append(f'VIX {v:.1f} 🟠 보통')
    else:
        checks.append(f'VIX {v:.1f} ⚫ 고변동성')

    y10 = us.get('us10y', {}) or {}
    y = y10.get('price', 4.5)
    if y < 4.3:
        s += 1; checks.append(f'10년물 {y:.2f}% ✅ 완화적')
    elif y < 4.8:
        s += 0.5; checks.append(f'10년물 {y:.2f}% 🟠 중립')
    else:
        checks.append(f'10년물 {y:.2f}% ⚫ 긴축 우려')

    wti_d = us.get('wti', {}) or {}
    w = wti_d.get('price', 90)
    if w < 85:
        s += 1; checks.append(f'WTI ${w:.1f} ✅ 물가 안정')
    elif w < 95:
        s += 0.5; checks.append(f'WTI ${w:.1f} 🟠 보통')
    else:
        checks.append(f'WTI ${w:.1f} ⚫ 물가 압박')

    dxy_d = us.get('dxy', {}) or {}
    d = dxy_d.get('price', 100)
    if d < 100:
        s += 1; checks.append(f'DXY {d:.1f} ✅ 달러 약세(신흥국 우호)')
    elif d < 105:
        s += 0.5; checks.append(f'DXY {d:.1f} 🟠 중립')
    else:
        checks.append(f'DXY {d:.1f} ⚫ 달러 강세(신흥국 부담)')

    krw_d = us.get('usdkrw', {}) or {}
    k = krw_d.get('price', 1400)
    if k < 1350:
        s += 1; checks.append(f'달러원 {k:.0f} ✅ 원화 강세')
    elif k < 1430:
        s += 0.5; checks.append(f'달러원 {k:.0f} 🟠 보통')
    else:
        checks.append(f'달러원 {k:.0f} ⚫ 원화 약세(수입물가↑)')

    return round(s), checks

def score_us_market(us):
    """미국장 점수 (0~4)"""
    s = 0
    checks = []
    for key, name in [('sp500','S&P500'), ('nasdaq','나스닥'), ('dow','다우'), ('phlx','필라반')]:
        d = us.get(key, {}) or {}
        chg = d.get('chg', 0)
        if chg > 0.5:
            s += 1; checks.append(f'{name} {chg:+.2f}% ✅')
        elif chg > -0.5:
            s += 0.5; checks.append(f'{name} {chg:+.2f}% 🟠')
        else:
            checks.append(f'{name} {chg:+.2f}% ⚫')
    return round(s), checks

def score_kr_market(kr):
    """한국장 점수 (0~3)"""
    s = 0
    checks = []
    for key, name in [('kospi','코스피'), ('kosdaq','코스닥'), ('semi','반도체ETF')]:
        d = kr.get(key, {}) or {}
        chg = d.get('chg', 0)
        if chg > 0.5:
            s += 1; checks.append(f'{name} {chg:+.2f}% ✅')
        elif chg > -0.5:
            s += 0.5; checks.append(f'{name} {chg:+.2f}% 🟠')
        else:
            checks.append(f'{name} {chg:+.2f}% ⚫')
    return round(s), checks

def total_judgment(macro_s, us_s, kr_s):
    total = macro_s + us_s + kr_s
    max_s = 12
    pct   = total / max_s * 100

    if pct >= 70:
        return '🔴 투자 우호', '매수 적극 검토 — 매크로·미국·한국 모두 우호적'
    elif pct >= 50:
        return '🟠 투자 가능', '선별적 매수 — 일부 부담 있으나 진입 가능 구간'
    elif pct >= 35:
        return '🟡 관망 우선', '신규 진입 자제 — 리스크 요인 해소 확인 후 접근'
    else:
        return '⚫ 회피', '현금 비중 확대 — 매크로·시장 모두 부정적'

# ──────────────────────────────────────────
# 3. 출력 빌더
# ──────────────────────────────────────────

def build_report(us, kr, for_tg=False):
    macro_s, macro_c = score_macro(us)
    us_s,    us_c    = score_us_market(us)
    kr_s,    kr_c    = score_kr_market(kr)
    verdict, comment = total_judgment(macro_s, us_s, kr_s)
    total = macro_s + us_s + kr_s

    def v(d, key, fmt='.2f'):
        if d is None: return '—'
        val = d.get(key)
        return f'{val:{fmt}}' if val is not None else '—'

    def chg_str(d):
        if d is None: return '—'
        c = d.get('chg')
        return f'{c:+.2f}%' if c is not None else '—'

    sp  = us.get('sp500') or {}
    nq  = us.get('nasdaq') or {}
    dw  = us.get('dow') or {}
    rs  = us.get('russell') or {}
    vx  = us.get('vix') or {}
    ph  = us.get('phlx') or {}
    wt  = us.get('wti') or {}
    y10 = us.get('us10y') or {}
    dx  = us.get('dxy') or {}
    gd  = us.get('gold') or {}
    krw = us.get('usdkrw') or {}

    if for_tg:
        B = '<b>'; EB = '</b>'; I = '<i>'; EI = '</i>'
    else:
        B = EB = I = EI = ''

    lines = [
        f"{'📊 ' if for_tg else ''}  {B}전체 시황 체크{EB}  {TODAY}",
        f"  {verdict}  |  총점 {total}/12점",
        f"  {I}{comment}{EI}",
        "",
        f"  {B}① 글로벌 매크로{EB}  ({macro_s}/5점)",
    ]
    for c in macro_c:
        lines.append(f"    · {c}")

    lines += [
        "",
        f"  {B}② 미국장 (전일){EB}  ({us_s}/4점)",
        f"    S&P {chg_str(sp)}  나스닥 {chg_str(nq)}  다우 {chg_str(dw)}  러셀 {chg_str(rs)}",
        f"    필라반 {chg_str(ph)}  VIX {v(vx,'price','.1f')}",
    ]

    lines += [
        "",
        f"  {B}③ 한국장 (전일){EB}  ({kr_s}/3점)",
    ]
    for key in ['kospi','kosdaq','semi','battery','defense','ship']:
        d = kr.get(key)
        if d:
            lines.append(f"    {d['name']:8s} {d['chg']:>+6.2f}%  ({d['price']:,.0f})")

    lines += [
        "",
        f"  {B}④ 핵심 지표 현황{EB}",
        f"    WTI    ${v(wt,'price','.1f'):>7}  ({chg_str(wt)})",
        f"    10년물  {v(y10,'price','.2f'):>6}%  ({chg_str(y10)})",
        f"    DXY    {v(dx,'price','.2f'):>7}  ({chg_str(dx)})",
        f"    달러원  {v(krw,'price',',.0f'):>7}원  ({chg_str(krw)})",
        f"    금      ${v(gd,'price',',.0f'):>7}  ({chg_str(gd)})",
    ]

    return "\n".join(lines)

# ──────────────────────────────────────────
# 4. 텔레그램 발송
# ──────────────────────────────────────────

def send_telegram(text: str):
    env = BASE / '.env'
    cfg = {}
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    token   = cfg.get('BOT_TOKEN','')
    chat_id = cfg.get('CHAT_ID','')
    if not token or not chat_id:
        print('텔레그램 설정 없음'); return
    url  = f'https://api.telegram.org/bot{token}/sendMessage'
    data = urllib.parse.urlencode(
        {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}).encode()
    with urllib.request.urlopen(
            urllib.request.Request(url, data), timeout=10) as r:
        if json.loads(r.read()).get('ok'):
            print('텔레그램 전송 완료')

# ──────────────────────────────────────────
# 5. 메인
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tg', action='store_true')
    args = parser.parse_args()

    print(f'[{TODAY}] 시황 데이터 수집 중...')
    us = fetch_us()
    kr = fetch_kr()

    report = build_report(us, kr, for_tg=False)
    print()
    print(report)

    if args.tg:
        tg_report = build_report(us, kr, for_tg=True)
        print()
        send_telegram(tg_report)

    # JSON 캐시 저장 (numpy 타입 → float 변환)
    def to_py(obj):
        if isinstance(obj, dict):
            return {k: to_py(v) for k, v in obj.items()}
        if hasattr(obj, 'item'):   # numpy scalar
            return obj.item()
        return obj
    cache = {'us': to_py({k: v for k, v in us.items() if v}),
             'kr': to_py({k: v for k, v in kr.items() if v}),
             'date': TODAY}
    (BASE / 'raw' / '미국장' / f'{TODAY}_market.json').write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
