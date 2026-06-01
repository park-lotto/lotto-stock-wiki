"""
투자경고 해제 공식 검증기

목적:
  KIND에서 확인된 실제 해제 종목들을 역산해서
  "해제 전날 3조건이 충족됐는가" 검증

검증 방법:
  해제일 전날 종가로 롤링 T-5 / T-15 조건 계산 → 맞으면 공식 확정

사용법:
  python 투경_검증.py          # 오늘 해제 6종목 자동 검증
  python 투경_검증.py --all    # 저장된 전체 이력 검증
"""

import sys
from datetime import date, datetime, timedelta
from pykrx import stock as pyk

sys.stdout.reconfigure(encoding='utf-8')

TODAY_DT = date.today()

# ── 검증 데이터셋: 실제 해제된 종목들 (KIND에서 직접 확인) ──────────────
# 형식: (종목명, 코드, 지정일, 실제해제일, 지정유형)
# 유형: 'surge' = 급등형(160/200%), 'unfair' = 불건전형(145/175%)
VERIFIED_RELEASES = [
    # 2026-06-01 해제 확인 (5/15 지정, 12영업일)
    ('TPC로보틱스',   '048770', '2026-05-15', '2026-06-01', 'unknown'),
    ('네오티스',      '085910', '2026-05-15', '2026-06-01', 'unknown'),
    ('미래반도체',    '254490', '2026-05-15', '2026-06-01', 'unknown'),
    ('민테크',        '452200', '2026-05-15', '2026-06-01', 'unknown'),
    ('성문전자',      '014910', '2026-05-15', '2026-06-01', 'unknown'),
    ('코스텍시스템',  '169670', '2026-05-15', '2026-06-01', 'unknown'),
]

THRESH = {
    'surge':   (1.60, 2.00),   # 급등형: T-5×160%, T-15×200%
    'unfair':  (1.45, 1.75),   # 불건전형: T-5×145%, T-15×175%
    'unknown': None,            # 둘 다 계산
}


def get_prices(code: str, ref_date: date, n: int = 20):
    """ref_date 포함 이전 n영업일 종가 (newest-first)."""
    start = (ref_date - timedelta(days=90)).strftime('%Y%m%d')
    end   = ref_date.strftime('%Y%m%d')
    try:
        df = pyk.get_market_ohlcv(start, end, code)
        if df is None or df.empty:
            return []
        result = []
        for idx in df.index[::-1]:
            close = int(df.loc[idx, '종가'])
            if close == 0:
                continue
            result.append((idx.strftime('%Y-%m-%d'), close))
            if len(result) >= n:
                break
        return result
    except Exception as e:
        return []


def prev_biz_day(d: date) -> date:
    """d 이전의 가장 가까운 영업일."""
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def check_conditions(code: str, check_date: date, t5_mult: float, t15_mult: float):
    """check_date 장마감 기준 3조건 확인."""
    prices = get_prices(code, check_date, 20)
    if len(prices) < 16:
        return None, f'데이터 부족({len(prices)}건)'

    today_close = prices[0][1]
    today_date  = prices[0][0]
    t5_close    = prices[5][1]
    t5_date     = prices[5][0]
    t15_close   = prices[15][1]
    t15_date    = prices[15][0]

    tp5  = int(t5_close  * t5_mult)
    tp15 = int(t15_close * t15_mult)

    high15      = max(p[1] for p in prices[:15])
    high15_date = max(prices[:15], key=lambda x: x[1])[0]

    c1 = today_close < tp5
    c2 = today_close < tp15
    c3 = today_close != high15
    ok = c1 and c2 and c3

    return ok, {
        'check_date': today_date,
        'close':      today_close,
        't5':   (t5_date,  t5_close,  tp5,  c1, round(today_close/t5_close*100,1)),
        't15':  (t15_date, t15_close, tp15, c2, round(today_close/t15_close*100,1)),
        'high15': (high15_date, high15, c3),
        'all_ok': ok,
    }


def verify_one(name, code, des_date_str, release_date_str, typ):
    """단일 종목 검증."""
    release_dt = datetime.strptime(release_date_str, '%Y-%m-%d').date()
    check_dt   = prev_biz_day(release_dt)   # 해제 전날 (조건 충족 확인일)

    print(f'\n{"━"*60}')
    print(f'  {name} ({code})  지정:{des_date_str} → 해제:{release_date_str}')
    print(f'  검증기준일: {check_dt} (해제 전날 장마감)')

    thresholds = []
    if typ == 'unknown':
        thresholds = [('급등형(160/200)',  1.60, 2.00),
                      ('불건전형(145/175)', 1.45, 1.75)]
    elif typ == 'surge':
        thresholds = [('급등형(160/200)',  1.60, 2.00)]
    else:
        thresholds = [('불건전형(145/175)', 1.45, 1.75)]

    for label, t5m, t15m in thresholds:
        ok, detail = check_conditions(code, check_dt, t5m, t15m)
        if ok is None:
            print(f'  [{label}] ⚠️  {detail}')
            continue

        d = detail
        c1d = '✅' if d['t5'][3]  else '❌'
        c2d = '✅' if d['t15'][3] else '❌'
        c3d = '✅' if d['high15'][2] else '❌'
        verdict = '🟢 3조건 충족 → 해제 예측 맞음' if d['all_ok'] else '🔴 조건 미충족 → 해제 예측 틀림'

        print(f'\n  [{label}]')
        print(f'  종가 {d["close"]:,}원  ({d["check_date"]})')
        print(f'  {c1d} ① T-5  {d["t5"][1]:,}원({d["t5"][0]}) × {int(t5m*100)}% = {d["t5"][2]:,}  ({d["t5"][4]}%)')
        print(f'  {c2d} ② T-15 {d["t15"][1]:,}원({d["t15"][0]}) × {int(t15m*100)}% = {d["t15"][2]:,}  ({d["t15"][4]}%)')
        print(f'  {c3d} ③ 15일최고 {d["high15"][1]:,}원({d["high15"][0]})')
        print(f'  → {verdict}')


def main():
    print(f'투자경고 해제 공식 검증  ({TODAY_DT})')
    print(f'검증 종목: {len(VERIFIED_RELEASES)}건')

    results = {'surge_ok': 0, 'surge_fail': 0,
               'unfair_ok': 0, 'unfair_fail': 0,
               'unknown': 0}

    for name, code, des, rel, typ in VERIFIED_RELEASES:
        verify_one(name, code, des, rel, typ)

    print(f'\n\n{"═"*60}')
    print('검증 완료.')
    print()
    print('※ 두 유형 모두 ✅이면 → 어느 유형이든 해당 종목은 통과')
    print('※ 한 유형만 ✅이면  → 그 유형이 실제 지정유형')
    print('※ 둘 다 ❌이면      → 공식 자체가 틀렸거나 데이터 문제')


if __name__ == '__main__':
    main()
