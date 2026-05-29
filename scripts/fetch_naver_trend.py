"""
네이버 데이터랩 검색량 추이 — 종목 관심도 측정
"매일 냄새 맡기": 개인 투자자 관심이 올라오기 전 선행 신호 포착

사용:
  python scripts/fetch_naver_trend.py LG이노텍 삼성전기 심텍
  python scripts/fetch_naver_trend.py --watchlist         ← watchlist.json 전체 종목
  python scripts/fetch_naver_trend.py LG이노텍 --tg       ← 텔레그램 전송

해석 기준:
  검색량 급등 (전주 대비 +50%↑) → 개인 관심 유입 직전 신호
  검색량 감소 → 관심 식어가는 신호
  검색량 꾸준히 증가 → 모멘텀 지속 확인
"""
import sys, os, json, requests
from datetime import date, timedelta
from pathlib import Path
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
ENV  = ROOT / '.env'

env = {}
for line in ENV.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

# 네이버 데이터랩 API — 클라이언트 등록 필요
# https://developers.naver.com/apps/#/register
# CLIENT_ID, CLIENT_SECRET을 .env에 추가:
# NAVER_CLIENT_ID=xxx
# NAVER_CLIENT_SECRET=xxx
CLIENT_ID     = env.get('NAVER_CLIENT_ID', '')
CLIENT_SECRET = env.get('NAVER_CLIENT_SECRET', '')

BOT_TOKEN = env.get('BOT_TOKEN', '')
CHAT_ID   = env.get('CHAT_ID', '')

USE_TG = '--tg' in sys.argv
USE_WATCHLIST = '--watchlist' in sys.argv


def get_keywords():
    """CLI 인자 또는 watchlist에서 종목명 추출"""
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if args:
        return args

    if USE_WATCHLIST:
        wl_path = ROOT / 'watchlist.json'
        if wl_path.exists():
            wl = json.loads(wl_path.read_text(encoding='utf-8'))
            stocks = []
            for sector in wl.get('sectors', {}).values():
                for sub in sector.get('subsectors', {}).values():
                    for s in sub.get('stocks', []):
                        name = s.get('name', '')
                        if name:
                            stocks.append(name)
            return list(dict.fromkeys(stocks))[:20]  # 중복 제거, 최대 20개
    return []


def fetch_trend(keywords, period_weeks=4):
    """네이버 데이터랩 API로 검색량 추이 조회"""
    if not CLIENT_ID or not CLIENT_SECRET:
        print('⚠️  NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 없음')
        print('   https://developers.naver.com/apps/#/register 에서 발급 후 .env에 추가')
        print('   NAVER_CLIENT_ID=xxx')
        print('   NAVER_CLIENT_SECRET=xxx')
        return fallback_mock(keywords)

    today = date.today()
    start = (today - timedelta(weeks=period_weeks)).strftime('%Y-%m-%d')
    end   = today.strftime('%Y-%m-%d')

    # 5개씩 묶어서 요청 (API 제한)
    results = {}
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i+5]
        body = {
            "startDate": start,
            "endDate": end,
            "timeUnit": "week",
            "keywordGroups": [
                {"groupName": kw, "keywords": [kw]}
                for kw in batch
            ]
        }
        try:
            resp = requests.post(
                'https://openapi.naver.com/v1/datalab/search',
                headers={
                    'X-Naver-Client-Id': CLIENT_ID,
                    'X-Naver-Client-Secret': CLIENT_SECRET,
                    'Content-Type': 'application/json'
                },
                json=body,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get('results', []):
                    kw = item['title']
                    ratios = [p['ratio'] for p in item['data']]
                    results[kw] = ratios
            else:
                print(f'  API 오류 {resp.status_code}: {resp.text[:100]}')
        except Exception as e:
            print(f'  요청 실패: {e}')

    return results


def fallback_mock(keywords):
    """API 키 없을 때 — 구조만 반환"""
    print('\n[Mock 모드] API 키 없음. 실제 데이터 조회 불가.')
    print('검색량 추이 측정 체계 구조:\n')
    for kw in keywords:
        print(f'  {kw}: [API 키 필요]')
    return {}


def analyze(results):
    """검색량 변화 분석 — 마지막 주 vs 직전 주 비교"""
    analysis = []
    for kw, ratios in results.items():
        if len(ratios) < 2:
            continue
        latest = ratios[-1]
        prev   = ratios[-2]
        if prev == 0:
            change = 0
        else:
            change = (latest - prev) / prev * 100

        if change >= 50:
            signal = '🔴 급등 — 개인 관심 유입 직전'
        elif change >= 20:
            signal = '🟠 상승 — 관심 증가 중'
        elif change >= 0:
            signal = '🟡 보합 — 유지'
        elif change >= -20:
            signal = '⚫ 하락 — 관심 식어가는 중'
        else:
            signal = '❌ 급락 — 모멘텀 소멸'

        analysis.append({
            'keyword': kw,
            'latest': latest,
            'prev': prev,
            'change': change,
            'signal': signal,
            'trend': ratios
        })

    # 변화율 큰 순 정렬
    analysis.sort(key=lambda x: x['change'], reverse=True)
    return analysis


def build_message(analysis, period_weeks):
    today = date.today().strftime('%Y-%m-%d')
    lines = [
        f'📊 종목 검색량 트렌드 ({today})',
        f'   기간: 최근 {period_weeks}주',
        '',
        '| 종목 | 최근 | 전주 | 변화 | 신호 |',
        '|------|------|------|------|------|',
    ]
    for a in analysis:
        trend_str = '→'.join([str(round(r, 1)) for r in a['trend'][-4:]])
        lines.append(
            f"| {a['keyword']} | {a['latest']:.1f} | {a['prev']:.1f} | "
            f"{'+' if a['change']>=0 else ''}{a['change']:.0f}% | {a['signal']} |"
        )
    lines.append('')
    lines.append('> 100 = 기간 내 최고 검색량. 급등 = 개인 관심 유입 전 선행 신호.')
    return '\n'.join(lines)


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    requests.post(url, json={
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown'
    }, timeout=10)


# ── 실행 ──────────────────────────────────────────────────────
keywords = get_keywords()
if not keywords:
    print('사용: python scripts/fetch_naver_trend.py 종목1 종목2 ...')
    print('     python scripts/fetch_naver_trend.py --watchlist')
    sys.exit(0)

print(f'검색 종목 ({len(keywords)}개): {", ".join(keywords)}')
print('네이버 데이터랩 조회 중...\n')

results = fetch_trend(keywords)
if not results:
    sys.exit(0)

analysis = analyze(results)
message  = build_message(analysis, period_weeks=4)

print(message)

if USE_TG:
    send_telegram(message)
    print('\n✅ 텔레그램 전송 완료')
