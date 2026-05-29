"""
시장 온도계 (Market Heat Monitor)
"매일 냄새 맡기" — 종목 관심도를 3가지 소스로 측정

소스 1. Google Trends  → 검색량 추이 (pytrends, API 키 불필요)
소스 2. 뉴스 언급 빈도  → raw/크롤링 최근 7일 파일에서 종목명 카운트
소스 3. TP 변화 빈도   → raw/매일요약/추정이익변경 파일에서 등장 횟수

사용:
  python scripts/market_heat.py LG이노텍 삼성전기 심텍 이수페타시스
  python scripts/market_heat.py --watchlist                          ← watchlist 주요 종목
  python scripts/market_heat.py LG이노텍 삼성전기 --tg               ← 텔레그램 전송

해석:
  🔴 종합 핫 — 3개 소스 모두 높음
  🟠 주목 필요 — 2개 소스 상승
  🟡 체크 — 1개 소스 신호
  ⚫ 조용함 — 신호 없음
"""
import sys, os, json, re, time, warnings
warnings.filterwarnings('ignore')
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict
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

BOT_TOKEN = env.get('BOT_TOKEN', '')
CHAT_ID   = env.get('CHAT_ID', '')
USE_TG       = '--tg' in sys.argv
USE_WATCHLIST = '--watchlist' in sys.argv


# ─── 종목 목록 ────────────────────────────────────────────────────────────────
def get_keywords():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if args:
        return args
    if USE_WATCHLIST:
        wl = ROOT / 'watchlist.json'
        if wl.exists():
            data = json.loads(wl.read_text(encoding='utf-8'))
            stocks = []
            for sec in data.get('sectors', {}).values():
                for sub in sec.get('subsectors', {}).values():
                    for s in sub.get('stocks', []):
                        if s.get('name'):
                            stocks.append(s['name'])
            return list(dict.fromkeys(stocks))[:20]
    return []


# ─── 소스 1. Google Trends ────────────────────────────────────────────────────
def fetch_google_trends(keywords):
    """Google Trends 최근 3개월 주간 검색량. urllib3 v2 호환 패치 적용."""
    try:
        import requests
        from pytrends.request import TrendReq
        import urllib3

        # urllib3 v2 호환 패치: method_whitelist → allowed_methods
        _orig_init = urllib3.util.retry.Retry.__init__
        def _patched_init(self, *args, **kwargs):
            if 'method_whitelist' in kwargs:
                kwargs['allowed_methods'] = kwargs.pop('method_whitelist')
            _orig_init(self, *args, **kwargs)
        urllib3.util.retry.Retry.__init__ = _patched_init

    except ImportError:
        print('⚠️  pytrends 없음 → pip install pytrends')
        return {}

    results = {}
    try:
        pytrends = TrendReq(hl='ko', tz=540, timeout=(10, 30), retries=2, backoff_factor=0.5)
    except Exception as e:
        print(f'  TrendReq 초기화 실패: {e}')
        return {}

    for i in range(0, len(keywords), 5):
        batch = keywords[i:i+5]
        try:
            pytrends.build_payload(batch, timeframe='today 3-m', geo='KR')
            df = pytrends.interest_over_time()
            if df.empty:
                continue
            for kw in batch:
                if kw in df.columns:
                    vals = df[kw].tolist()
                    results[kw] = vals
            time.sleep(2)
        except Exception as e:
            print(f'  Google Trends 오류 ({batch}): {e}')
            time.sleep(3)

    return results


def analyze_trends(results):
    """마지막 1주 vs 직전 4주 평균 비교"""
    analysis = {}
    for kw, vals in results.items():
        if len(vals) < 2:
            continue
        latest  = vals[-1]
        avg_4w  = sum(vals[-5:-1]) / 4 if len(vals) >= 5 else sum(vals[:-1]) / len(vals[:-1])
        change  = (latest - avg_4w) / avg_4w * 100 if avg_4w > 0 else 0
        peak    = max(vals) if vals else 0
        peak_pct = latest / peak * 100 if peak > 0 else 0

        if change >= 50:
            signal, score = '🔴 급등', 3
        elif change >= 20:
            signal, score = '🟠 상승', 2
        elif change >= 0:
            signal, score = '🟡 보합', 1
        else:
            signal, score = '⚫ 하락', 0

        analysis[kw] = {
            'latest': latest,
            'avg_4w': round(avg_4w, 1),
            'change': round(change, 1),
            'peak_pct': round(peak_pct, 1),
            'trend': vals[-8:],
            'signal': signal,
            'score': score,
        }
    return analysis


# ─── 소스 2. 뉴스 언급 빈도 ──────────────────────────────────────────────────
def count_news_mentions(keywords, days=7):
    """raw/크롤링 최근 N일 파일에서 종목명 카운트"""
    crawl_dir = ROOT / 'raw' / '크롤링 블로그뉴스유튭 요약'
    if not crawl_dir.exists():
        return {kw: 0 for kw in keywords}

    cutoff = date.today() - timedelta(days=days)
    counts = defaultdict(int)

    for f in crawl_dir.glob('*.md'):
        # 파일명에서 날짜 추출 (YYYY-MM-DD_...)
        name = f.name
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', name)
        if date_match:
            try:
                file_date = date.fromisoformat(date_match.group(1))
                if file_date < cutoff:
                    continue
            except:
                pass

        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
            for kw in keywords:
                counts[kw] += text.count(kw)
        except:
            pass

    # 매일요약 폴더도 확인
    for summary_dir in [ROOT / 'raw' / '매일요약', ROOT / 'raw' / 'telegram']:
        if not summary_dir.exists():
            continue
        for f in summary_dir.glob('*.md'):
            name = f.name
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', name) or re.match(r'(\d{8})', name)
            if date_match:
                try:
                    ds = date_match.group(1)
                    if len(ds) == 8:
                        ds = f'{ds[:4]}-{ds[4:6]}-{ds[6:]}'
                    if date.fromisoformat(ds) < cutoff:
                        continue
                except:
                    pass
            try:
                text = f.read_text(encoding='utf-8', errors='ignore')
                for kw in keywords:
                    counts[kw] += text.count(kw)
            except:
                pass

    return dict(counts)


def analyze_news(counts, keywords):
    """언급 횟수 → 신호 등급"""
    analysis = {}
    max_count = max(counts.values()) if counts.values() else 1

    for kw in keywords:
        cnt = counts.get(kw, 0)
        pct = cnt / max_count * 100 if max_count > 0 else 0

        if cnt >= 10:
            signal, score = f'🔴 {cnt}회', 3
        elif cnt >= 5:
            signal, score = f'🟠 {cnt}회', 2
        elif cnt >= 2:
            signal, score = f'🟡 {cnt}회', 1
        else:
            signal, score = f'⚫ {cnt}회', 0

        analysis[kw] = {'count': cnt, 'signal': signal, 'score': score}

    return analysis


# ─── 소스 3. TP 변화 빈도 ────────────────────────────────────────────────────
def count_tp_mentions(keywords, days=7):
    """raw/매일요약 추정이익변경 파일에서 종목 등장 횟수 (최근 N일)"""
    cutoff = date.today() - timedelta(days=days)
    counts = defaultdict(int)

    summary_dir = ROOT / 'raw' / '매일요약'
    if not summary_dir.exists():
        return {kw: 0 for kw in keywords}

    for f in summary_dir.glob('*추정이익변경*.md'):
        name = f.name
        date_match = re.match(r'(\d{8})', name)
        if date_match:
            try:
                ds = date_match.group(1)
                ds = f'{ds[:4]}-{ds[4:6]}-{ds[6:]}'
                if date.fromisoformat(ds) < cutoff:
                    continue
            except:
                pass
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
            for kw in keywords:
                counts[kw] += len(re.findall(kw, text))
        except:
            pass

    return dict(counts)


def analyze_tp(counts, keywords):
    analysis = {}
    for kw in keywords:
        cnt = counts.get(kw, 0)
        if cnt >= 6:
            signal, score = f'🔴 {cnt}건', 3
        elif cnt >= 3:
            signal, score = f'🟠 {cnt}건', 2
        elif cnt >= 1:
            signal, score = f'🟡 {cnt}건', 1
        else:
            signal, score = f'⚫ 0건', 0
        analysis[kw] = {'count': cnt, 'signal': signal, 'score': score}
    return analysis


# ─── 종합 온도계 ─────────────────────────────────────────────────────────────
def build_report(keywords, trends_a, news_a, tp_a):
    today = date.today().strftime('%Y-%m-%d')
    lines = []
    lines.append(f'🌡️ 시장 온도계 ({today})')
    lines.append('=' * 50)
    lines.append('')

    # 종합 점수 계산 후 정렬
    ranked = []
    for kw in keywords:
        t_score = trends_a.get(kw, {}).get('score', 0)
        n_score = news_a.get(kw, {}).get('score', 0)
        p_score = tp_a.get(kw, {}).get('score', 0)
        total   = t_score + n_score + p_score

        if total >= 7:
            heat = '🔴🔴 VERY HOT'
        elif total >= 5:
            heat = '🔴 HOT'
        elif total >= 3:
            heat = '🟠 WARM'
        elif total >= 1:
            heat = '🟡 COOL'
        else:
            heat = '⚫ COLD'

        ranked.append((total, kw, t_score, n_score, p_score, heat))

    ranked.sort(key=lambda x: -x[0])

    # 테이블 헤더
    lines.append(f"{'종목':<12} {'종합':^8} {'검색량':^10} {'뉴스':^8} {'TP변화':^8} {'온도'}")
    lines.append('-' * 60)

    for total, kw, t_score, n_score, p_score, heat in ranked:
        t_sig = trends_a.get(kw, {}).get('signal', '—')
        n_sig = news_a.get(kw, {}).get('signal', '—')
        p_sig = tp_a.get(kw, {}).get('signal', '—')

        # 검색량 상세 (변화율)
        t_change = trends_a.get(kw, {}).get('change', None)
        t_detail = f"{'+' if t_change and t_change >= 0 else ''}{t_change:.0f}%" if t_change is not None else '—'

        lines.append(
            f"{kw:<12} {'★'*total + '☆'*(9-total):^8} "
            f"{t_detail:^10} {n_sig:^8} {p_sig:^8}  {heat}"
        )

    lines.append('')
    lines.append('─' * 60)
    lines.append('검색량: vs 4주 평균 | 뉴스: 최근 7일 언급 | TP: 최근 7일 증권사 목표가 변화')
    lines.append('')

    # HOT 종목 상세
    hot_stocks = [(t, kw, ts, ns, ps, h) for (t, kw, ts, ns, ps, h) in ranked if t >= 5]
    if hot_stocks:
        lines.append('🔥 핫 종목 상세')
        lines.append('')
        for total, kw, t_score, n_score, p_score, heat in hot_stocks:
            t_data = trends_a.get(kw, {})
            n_data = news_a.get(kw, {})
            p_data = tp_a.get(kw, {})

            lines.append(f'■ {kw}  {heat}')
            if t_data:
                change = t_data.get('change', 0)
                peak   = t_data.get('peak_pct', 0)
                lines.append(f'  검색량: 4주평균 대비 {change:+.0f}% | 고점 대비 {peak:.0f}%')
            lines.append(f'  뉴스 언급: {n_data.get("count", 0)}회 (최근 7일)')
            lines.append(f'  TP 변화: {p_data.get("count", 0)}건 (최근 7일)')
            lines.append('')

    return '\n'.join(lines)


# ─── 텔레그램 ─────────────────────────────────────────────────────────────────
def send_telegram(text):
    import requests
    if not BOT_TOKEN or not CHAT_ID:
        return
    # 4096자 제한
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': f'```\n{chunk}\n```', 'parse_mode': 'Markdown'},
            timeout=10
        )


# ─── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    keywords = get_keywords()
    if not keywords:
        print('사용: python scripts/market_heat.py 종목1 종목2 종목3')
        print('     python scripts/market_heat.py --watchlist')
        return

    print(f'📊 시장 온도계 시작 | {len(keywords)}개 종목')
    print(f'   {", ".join(keywords)}')
    print()

    # 소스 1. Google Trends
    print('[1/3] Google Trends 조회 중...')
    raw_trends  = fetch_google_trends(keywords)
    trends_a    = analyze_trends(raw_trends)
    found = len(trends_a)
    print(f'  → {found}/{len(keywords)}개 조회 성공')

    # 소스 2. 뉴스 언급
    print('[2/3] 뉴스 언급 빈도 집계 중...')
    raw_news = count_news_mentions(keywords)
    news_a   = analyze_news(raw_news, keywords)
    top_news = max(raw_news.values()) if raw_news else 0
    print(f'  → 최고 언급: {top_news}회')

    # 소스 3. TP 변화
    print('[3/3] TP 변화 빈도 집계 중...')
    raw_tp = count_tp_mentions(keywords)
    tp_a   = analyze_tp(raw_tp, keywords)
    top_tp = max(raw_tp.values()) if raw_tp else 0
    print(f'  → 최고 TP변화: {top_tp}건')

    print()
    report = build_report(keywords, trends_a, news_a, tp_a)
    print(report)

    if USE_TG:
        send_telegram(report)
        print('✅ 텔레그램 전송 완료')

    # 결과 저장
    out_dir = ROOT / 'raw' / 'market'
    out_dir.mkdir(exist_ok=True)
    today = date.today().strftime('%Y%m%d')
    out_file = out_dir / f'{today}_heat_monitor.md'

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f'# 시장 온도계 {today}\n\n```\n{report}\n```\n')
    print(f'\n💾 저장: {out_file.name}')


if __name__ == '__main__':
    main()
