"""2차전지 서브섹터별 상세 분석 — 위키 매핑 기준"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pykrx import stock
import pandas as pd

START = '20260101'
END   = '20260527'

# 위키 서브섹터 매핑 그대로
SUBSECTORS = [
    ('1. 배터리셀(EV)',  'EV 판매량·CATL 경쟁·IRA',   'TSLA·CATL',
     [('373220','LG에너지솔루션'), ('006400','삼성SDI'), ('096770','SK이노베이션')]),

    ('2. 배터리셀(ESS)', '미국 ESS 발주·전력망',        'FLNC·ENPH',
     [('006400','삼성SDI'), ('373220','LG에너지솔루션')]),

    ('3. 양극재',        '리튬·니켈 판가·NCMA 채택률',  '—',
     [('247540','에코프로비엠'), ('066970','엘앤에프'), ('003670','포스코퓨처엠')]),

    ('4. 음극재',        '탈중국 흑연·실리콘 음극재',    '—',
     [('003670','포스코퓨처엠'), ('078600','대주전자재료'), ('036830','솔브레인홀딩스')]),

    ('5. 분리막',        '건식/습식 전환·EV 수요',       '—',
     [('361610','SKIET'), ('393890','더블유씨피')]),

    ('6. 전해질',        '전해질가격·LFP vs NCM',        '—',
     [('025900','동화기업'), ('348370','엔켐'), ('357780','솔브레인')]),

    ('7. 동박',          '동 가격·배터리 두께 축소',      '—',
     [('020150','일진머티리얼즈')]),

    ('8. 알루미늄박',    '양극 집전체·ESS 확대',          '—',
     [('018540','동일알루미늄')]),

    ('9. 배터리재활용',  'EU 배터리법·리튬 리사이클링',  'LI·LICY',
     [('365340','성일하이텍'), ('086520','에코프로')]),

    ('10. 전고체(차세대)','삼성SDI 2027 양산 로드맵',    'QuantumScape',
     [('006400','삼성SDI'), ('003670','포스코퓨처엠')]),

    ('11. 충전인프라',   'EV 보급률·급속충전',           'CHPT·BLNK',
     [('019800','스타코')]),
]

# 전체 유니크 종목 사전 로딩
all_codes = list({c for ss in SUBSECTORS for c, _ in ss[3]})
cache = {}
print('데이터 로딩 중...')
for code in all_codes:
    df = stock.get_market_ohlcv(START, END, code)
    if not df.empty:
        cache[code] = df

# KODEX200 기준
kodex = stock.get_market_ohlcv(START, END, '069500')
kospi_ytd = (kodex['종가'].iloc[-1] / kodex['종가'].iloc[0] - 1) * 100 if not kodex.empty else 0

def get_stats(code):
    if code not in cache:
        return None
    df = cache[code]
    c, v = df['종가'], df['거래량']
    cur   = c.iloc[-1]
    ma5   = c.rolling(5).mean().iloc[-1]
    ma20  = c.rolling(20).mean().iloc[-1]
    ma60  = c.rolling(60).mean().iloc[-1]

    def ret(d):
        s = df[df.index >= pd.Timestamp(d)]
        return (cur / s['종가'].iloc[0] - 1) * 100 if len(s) >= 2 else None

    r_ytd = ret('20260101')
    r_1m  = ret('20260428')
    r_2w  = ret('20260512')
    r_1w  = ret('20260520')
    high  = c.max()
    high_d = c.idxmax().strftime('%m/%d')
    vs_h  = (cur / high - 1) * 100

    vol5  = v.iloc[-5:].mean()
    vol20 = v.iloc[-20:].mean()
    vr    = vol5 / vol20

    # 이평선 상태 (1줄)
    if cur > ma5 > ma20 > ma60:
        st = '✅정배열'
    elif cur > ma20 > ma60:
        st = '🟡5선이탈'
    elif cur > ma60:
        st = '🟠20선이탈'
    else:
        st = '❌역배열'

    # 5일선 방향
    slope = '↑' if c.rolling(5).mean().iloc[-1] > c.rolling(5).mean().iloc[-4] else '↓'

    rs = (r_ytd or 0) - kospi_ytd

    return dict(cur=cur, ma5=ma5, ma20=ma20, ma60=ma60,
                r_ytd=r_ytd, r_1m=r_1m, r_2w=r_2w, r_1w=r_1w,
                high=high, high_d=high_d, vs_h=vs_h,
                vr=vr, st=st, slope=slope, rs=rs)

# 출력
print()
print('=' * 72)
print(f'  2차전지 서브섹터 분석  ({START[:4]}.{START[4:6]}.{START[6:]} ~ {END[:4]}.{END[4:6]}.{END[6:]})')
print(f'  KODEX200 YTD 기준선: {kospi_ytd:+.1f}%')
print('=' * 72)

for ss_name, driver, us_peer, stocks in SUBSECTORS:
    # 서브섹터 평균 YTD
    ytds = []
    for code, _ in stocks:
        s = get_stats(code)
        if s and s['r_ytd'] is not None:
            ytds.append(s['r_ytd'])
    avg_ytd = sum(ytds) / len(ytds) if ytds else 0
    avg_rs  = avg_ytd - kospi_ytd

    if avg_rs >= 10:
        ss_sig = '🔴'
    elif avg_rs >= -30:
        ss_sig = '🟠'
    elif avg_rs >= -70:
        ss_sig = '🟡'
    else:
        ss_sig = '⚫'

    print(f'\n{ss_sig} [{ss_name}]  드라이버: {driver}  |  미국페어: {us_peer}')
    print(f'   서브섹터 평균 YTD: {avg_ytd:+.1f}%  |  코스피 대비 RS: {avg_rs:+.1f}%p')
    print(f'   {"종목":<14}  {"현재가":>8}  {"YTD":>7}  {"1M":>7}  {"2W":>7}  {"1W":>7}  {"이평선":>9}  {"5선":>2}  {"고점비":>7}  {"RS":>7}  {"거래량비":>5}')
    print(f'   {"─"*14}  {"─"*8}  {"─"*7}  {"─"*7}  {"─"*7}  {"─"*7}  {"─"*9}  {"─"*2}  {"─"*7}  {"─"*7}  {"─"*5}')

    for code, name in stocks:
        s = get_stats(code)
        if s is None:
            print(f'   {name:<14}  데이터 없음')
            continue
        r_ytd = f'{s["r_ytd"]:>+.1f}%' if s['r_ytd'] is not None else '  —  '
        r_1m  = f'{s["r_1m"]:>+.1f}%'  if s['r_1m']  is not None else '  —  '
        r_2w  = f'{s["r_2w"]:>+.1f}%'  if s['r_2w']  is not None else '  —  '
        r_1w  = f'{s["r_1w"]:>+.1f}%'  if s['r_1w']  is not None else '  —  '
        print(f'   {name:<14}  {s["cur"]:>8,.0f}  {r_ytd:>7}  {r_1m:>7}  {r_2w:>7}  {r_1w:>7}  {s["st"]:>9}  {s["slope"]:>2}  {s["vs_h"]:>+6.1f}%  {s["rs"]:>+6.1f}%p  {s["vr"]:.2f}x')

print()
print('=' * 72)
print('  서브섹터 종합 신호 (코스피 대비 RS 기준)')
print('─' * 72)
summary = []
for ss_name, _, _, stocks in SUBSECTORS:
    ytds = [get_stats(c)['r_ytd'] for c, _ in stocks if get_stats(c) and get_stats(c)['r_ytd']]
    if ytds:
        avg = sum(ytds) / len(ytds)
        rs  = avg - kospi_ytd
        summary.append((ss_name, avg, rs))

summary.sort(key=lambda x: x[2], reverse=True)
for name, avg, rs in summary:
    sig = '🔴' if rs >= 10 else ('🟠' if rs >= -30 else ('🟡' if rs >= -70 else '⚫'))
    bar = '█' * max(0, int((avg + 20) / 8))
    print(f'  {sig} {name:<20}  YTD {avg:>+6.1f}%  RS {rs:>+7.1f}%p  {bar}')
print('=' * 72)
