"""2차전지 섹터 상세 분석"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pykrx import stock
import pandas as pd

TICKERS = {
    '373220': 'LG에너지솔루션',
    '006400': '삼성SDI',
    '247540': '에코프로비엠',
    '086520': '에코프로',
    '003670': '포스코퓨처엠',
    '066970': '엘앤에프',
    '361610': 'SKIET',
    '305720': 'TIGER2차전지ETF',
    '069500': 'KODEX200(코스피)',   # 비교 기준
}

START = '20260101'
END   = '20260527'

def ma_state(cur, ma5, ma20, ma60, ma120):
    if cur > ma5 > ma20 > ma60:
        return '✅ 정배열'
    elif cur > ma5 and cur > ma20 and cur > ma60:
        return '✅ 정배열(변형)'
    elif cur > ma20 and cur > ma60:
        return '🟡 5선이탈'
    elif cur > ma60:
        return '🟠 20선이탈'
    elif cur > ma120:
        return '🔴 60선이탈'
    else:
        return '❌ 역배열'

def ret_from(df, from_date):
    sub = df[df.index >= pd.Timestamp(from_date)]
    if len(sub) < 2:
        return None
    return (df['종가'].iloc[-1] / sub['종가'].iloc[0] - 1) * 100

all_data = {}
for code, name in TICKERS.items():
    df = stock.get_market_ohlcv(START, END, code)
    if not df.empty:
        all_data[code] = (name, df)

# 코스피 기준
_, kospi_df = all_data.get('069500', (None, None))
kospi_ytd = ret_from(kospi_df, START) if kospi_df is not None else 0

print('=' * 70)
print(f'  2차전지 섹터 상세 분석  ({START[:4]}-{START[4:6]}-{START[6:]} ~ {END[:4]}-{END[4:6]}-{END[6:]})')
print(f'  KODEX200(코스피 대리) YTD: {kospi_ytd:+.1f}%')
print('=' * 70)

for code, name in TICKERS.items():
    if code == '069500':
        continue
    if code not in all_data:
        continue
    _, df = all_data[code]
    c = df['종가']
    v = df['거래량']

    cur   = c.iloc[-1]
    ma5   = c.rolling(5).mean().iloc[-1]
    ma20  = c.rolling(20).mean().iloc[-1]
    ma60  = c.rolling(60).mean().iloc[-1]
    ma120 = c.rolling(120).mean().iloc[-1]

    r_ytd = ret_from(df, START)
    r_3m  = ret_from(df, '20260228')
    r_1m  = ret_from(df, '20260428')
    r_2w  = ret_from(df, '20260512')
    r_1w  = ret_from(df, '20260520')

    high  = c.max()
    low   = c.min()
    high_d = c.idxmax().strftime('%m/%d')
    low_d  = c.idxmin().strftime('%m/%d')
    vs_h  = (cur / high - 1) * 100
    vs_l  = (cur / low  - 1) * 100

    vol5  = v.iloc[-5:].mean()
    vol20 = v.iloc[-20:].mean()
    vr    = vol5 / vol20

    rs = (r_ytd or 0) - (kospi_ytd or 0)

    # 5일선 기울기 방향
    ma5_now  = c.rolling(5).mean().iloc[-1]
    ma5_prev = c.rolling(5).mean().iloc[-4]
    slope5 = '↑' if ma5_now > ma5_prev else '↓'
    ma20_now  = c.rolling(20).mean().iloc[-1]
    ma20_prev = c.rolling(20).mean().iloc[-5]
    slope20 = '↑' if ma20_now > ma20_prev else '↓'

    print(f'\n{"─"*70}')
    print(f'  ▶ {name} ({code})')
    print(f'{"─"*70}')
    print(f'  현재가  {cur:>9,.0f}원   |   이평선 상태: {ma_state(cur, ma5, ma20, ma60, ma120)}')
    print(f'  이평선  5일 {ma5:>8,.0f}{slope5}  20일 {ma20:>8,.0f}{slope20}  60일 {ma60:>8,.0f}  120일 {ma120:>8,.0f}')
    print(f'  수익률  YTD {r_ytd:>+6.1f}%  |  3M {r_3m:>+6.1f}%  |  1M {r_1m:>+6.1f}%  |  2W {r_2w:>+6.1f}%  |  1W {r_1w:>+6.1f}%')
    print(f'  코스피 대비 RS(YTD): {rs:>+6.1f}%p  |  거래량 5일/20일: {vr:.2f}x  {"🔥 거래량 급증" if vr > 1.5 else ""}')
    print(f'  기간고점  {high:>9,.0f}({high_d})  현재위치 {vs_h:>+5.1f}%  |  기간저점  {low:>8,.0f}({low_d})  {vs_l:>+5.1f}%')
    print(f'  최근 5거래일:')
    for dt, row in df.tail(5).iterrows():
        bar = '█' * int(abs(row['등락률']) * 2) if '등락률' in row.index else ''
        sign = '+' if row.get('등락률', 0) >= 0 else ''
        print(f'    {dt.strftime("%m/%d(%a)")}  {row["종가"]:>8,.0f}원  거래량 {row["거래량"]/10000:>6.1f}만  {sign}{row.get("등락률",0):.2f}%  {bar}')

print(f'\n{"="*70}')
print('  섹터 요약 (코스피 대비 상대강도 순)')
print(f'{"─"*70}')
rs_list = []
for code, name in TICKERS.items():
    if code == '069500' or code not in all_data:
        continue
    _, df = all_data[code]
    r = ret_from(df, START) or 0
    rs_list.append((name, code, r, r - (kospi_ytd or 0)))

rs_list.sort(key=lambda x: x[2], reverse=True)
for name, code, r, rs in rs_list:
    bar = '█' * int(abs(r) / 3)
    sign = '+' if r >= 0 else ''
    print(f'  {name:18s}  YTD {sign}{r:5.1f}%  RS {rs:>+5.1f}%p  {bar}')
print(f'{"="*70}')
