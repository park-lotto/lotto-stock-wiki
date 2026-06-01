"""한투 API 연결 테스트 — 토큰 발급 + 삼성전자 현재가 + 외인·기관 순매수"""
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')
import urllib.request, urllib.parse
from pathlib import Path

BASE = Path(__file__).parent.parent
env = {}
for line in (BASE / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

APP_KEY    = env['KIS_APP_KEY']
APP_SECRET = env['KIS_APP_SECRET']
BASE_URL   = 'https://openapi.koreainvestment.com:9443'

# ── 1. 토큰 발급 ───────────────────────────────────────────────
print('1. 토큰 발급 중...')
body = json.dumps({
    'grant_type': 'client_credentials',
    'appkey':     APP_KEY,
    'appsecret':  APP_SECRET,
}).encode()
req = urllib.request.Request(
    f'{BASE_URL}/oauth2/tokenP',
    data=body,
    headers={'content-type': 'application/json'},
)
with urllib.request.urlopen(req, timeout=10) as r:
    token_data = json.loads(r.read())

if 'access_token' not in token_data:
    print(f'❌ 토큰 발급 실패: {token_data}')
    sys.exit(1)

TOKEN = token_data['access_token']
print(f'✅ 토큰 발급 완료 (만료: {token_data.get("access_token_token_expired", "?")})')

def kis_get(path, params, tr_id):
    url = f'{BASE_URL}{path}?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'content-type':  'application/json',
        'authorization': f'Bearer {TOKEN}',
        'appkey':        APP_KEY,
        'appsecret':     APP_SECRET,
        'tr_id':         tr_id,
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# ── 2. 삼성전자 현재가 + 거래대금 ──────────────────────────────
print('\n2. 삼성전자 현재가...')
res = kis_get(
    '/uapi/domestic-stock/v1/quotations/inquire-price',
    {'fid_cond_mrkt_div_code': 'J', 'fid_input_iscd': '005930'},
    'FHKST01010100'
)
if res.get('rt_cd') == '0':
    o = res['output']
    print(f'  현재가:  {int(o["stck_prpr"]):,}원')
    print(f'  거래대금: {int(o["acml_tr_pbmn"])//100000000}억원')
    print(f'  시가총액: {int(o.get("hts_avls","0"))//100000000}억원')
else:
    print(f'  ❌ {res}')

# ── 3. 삼성전자 투자자별 일별 순매수 (과거 5일) ────────────────
print('\n3. 삼성전자 투자자별 일별 순매수...')
res2 = kis_get(
    '/uapi/domestic-stock/v1/quotations/inquire-daily-trade-volume',
    {
        'fid_cond_mrkt_div_code': 'J',
        'fid_input_iscd': '005930',
        'fid_begin_date': '20260520',
        'fid_end_date':   '20260601',
        'fid_period_div_code': 'D',
        'fid_input_iscd2': '005930',
    },
    'FHKST03010400'
)
print(f'  rt_cd: {res2.get("rt_cd")}  msg: {res2.get("msg1","")[:50]}')
if res2.get('rt_cd') == '0':
    for row in (res2.get('output2') or [])[:5]:
        print(f'  {row}')
else:
    # 응답 키 출력해서 구조 파악
    print(f'  keys: {list(res2.keys())}')

# ── 3-2. 다른 방법: 주식 체결 통보 (투자자 단위)  ───────────────
print('\n3-2. 투자자별 매수매도 현황...')
res2b = kis_get(
    '/uapi/domestic-stock/v1/quotations/inquire-investor',
    {
        'fid_cond_mrkt_div_code': 'J',
        'fid_input_iscd': '005930',
        'fid_input_date_1': '20260601',
        'fid_input_date_2': '20260601',
        'fid_period_div_code': 'D',
        'fid_div_cls_code': '0',
    },
    'FHKST01010900'
)
print(f'  rt_cd: {res2b.get("rt_cd")}  msg: {res2b.get("msg1","")[:80]}')
if res2b.get('rt_cd') == '0':
    items = res2b.get('output2') or [res2b.get('output', {})]
    for row in items[:3]:
        print(f'  {row}')
else:
    print(f'  keys: {list(res2b.keys())}')

# ── 4. 일봉 데이터 확인 (최근 5일) ────────────────────────────
print('\n4. 삼성전자 일봉 (최근 5일)...')
res3 = kis_get(
    '/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice',
    {
        'fid_cond_mrkt_div_code': 'J',
        'fid_input_iscd': '005930',
        'fid_input_date_1': '20260501',
        'fid_input_date_2': '20260601',
        'fid_period_div_code': 'D',
        'fid_org_adj_prc': '0',
    },
    'FHKST03010100'
)
if res3.get('rt_cd') == '0':
    for row in res3.get('output2', [])[:5]:
        print(f"  {row['stck_bsop_date']}  종가:{int(row['stck_clpr']):,}  거래량:{int(row['acml_vol']):,}")
else:
    print(f'  ❌ {res3}')

print('\n✅ 테스트 완료')
