"""
섹터 트렌드 리포터 (Sector Theme Trend Reporter)
"오늘 시장에서 어떤 테마/섹터가 주도하고 있는가?"

매일 실행 → 오늘의 주도 섹터 순위 + 왜 강한지 이유 자동 태깅
→ 섹터 index.md "일일 분위기 로그" 자동 업데이트

소스:
  1. Google Trends  → 섹터 키워드 검색량 추이 (KR)
  2. 뉴스 언급 빈도  → raw/크롤링 + raw/telegram 최근 1~3일
  3. 이슈 키워드    → 뉴스에서 자주 나오는 단어 자동 추출 (왜 강한지 근거)

사용:
  python scripts/sector_heat.py              ← 전체 섹터 분석 + 위키 반영
  python scripts/sector_heat.py --dry        ← 위키 미반영, 콘솔 출력만
  python scripts/sector_heat.py --tg         ← 텔레그램 전송
  python scripts/sector_heat.py --days 3     ← 뉴스 수집 기간 (기본 2일)
"""
import sys, os, json, re, time, warnings
warnings.filterwarnings('ignore')
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict, Counter
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

DRY_RUN = '--dry' in sys.argv
USE_TG  = '--tg' in sys.argv
DAYS    = 5   # 기본 5일 — 주말·휴일 포함 크롤링 공백 대비
for arg in sys.argv:
    if arg.startswith('--days='):
        DAYS = int(arg.split('=')[1])


# ─── 섹터 × 검색 키워드 매핑 ─────────────────────────────────────────────────
# 각 섹터를 대표하는 검색 키워드 (Google KR 기준)
# 키워드는 실제로 사람들이 검색하는 단어로 설정
SECTOR_KEYWORDS = {
    "로봇·피지컬AI": {
        "keywords":  ["로봇주", "피지컬AI", "현대오토에버", "레인보우로보틱스"],
        "news_tags": ["로봇", "피지컬AI", "현대오토에버", "레인보우", "두산로보틱스", "현대모비스", "LG이노텍", "LG CNS", "젠슨황", "엔비디아"],
        "wiki":      "wiki/L5_섹터/로봇/로봇index.md",
    },
    "반도체·MLCC": {
        "keywords":  ["반도체주", "HBM", "삼성전기", "SK하이닉스"],
        "news_tags": ["HBM", "반도체", "삼성전기", "SK하이닉스", "MLCC", "FC-BGA", "소부장", "LG이노텍"],
        "wiki":      "wiki/L5_섹터/반도체/반도체index.md",
    },
    "조선": {
        "keywords":  ["조선주", "HD현대중공업", "한화오션"],
        "news_tags": ["조선", "HD현대중공업", "한화오션", "수주", "LNG선", "MASGA"],
        "wiki":      "wiki/L5_섹터/조선/조선index.md",
    },
    "방산": {
        "keywords":  ["방산주", "한화에어로스페이스", "K방산"],
        "news_tags": ["방산", "한화에어로스페이스", "한국항공우주", "K9", "수출"],
        "wiki":      "wiki/L5_섹터/방산/방산index.md",
    },
    "전력기기": {
        "keywords":  ["전력주", "LS ELECTRIC", "산일전기"],
        "news_tags": ["전력", "LS ELECTRIC", "산일전기", "변압기", "데이터센터 전력"],
        "wiki":      "wiki/L5_섹터/전력/전력index.md",
    },
    "자동차": {
        "keywords":  ["현대차주", "기아주", "자동차섹터"],
        "news_tags": ["현대차", "기아", "자동차", "SDV", "자율주행"],
        "wiki":      "wiki/L5_섹터/자동차/자동차index.md",
    },
    "바이오": {
        "keywords":  ["바이오주", "알테오젠", "한미약품"],
        "news_tags": ["바이오", "알테오젠", "ADC", "FDA", "임상"],
        "wiki":      "wiki/L5_섹터/바이오/바이오index.md",
    },
    "원전": {
        "keywords":  ["원전주", "두산에너빌리티", "SMR"],
        "news_tags": ["원전", "SMR", "두산에너빌리티", "한전기술", "핵추진"],
        "wiki":      "wiki/L5_섹터/원전/원전index.md",
    },
    "LNG·조선기자재": {
        "keywords":  ["LNG선", "동성화인텍", "한국카본"],
        "news_tags": ["LNG", "동성화인텍", "한국카본", "화물창"],
        "wiki":      "wiki/L5_섹터/LNG/LNGindex.md",
    },
    "이차전지": {
        "keywords":  ["이차전지주", "배터리주", "LG에너지솔루션"],
        "news_tags": ["이차전지", "배터리", "LG에너지솔루션", "ESS", "양극재"],
        "wiki":      "wiki/L5_섹터/이차전지/이차전지index.md",
    },
}


# ─── 소스 1. Google Trends ────────────────────────────────────────────────────
def fetch_trends_by_sector():
    """섹터별 대표 키워드 Google Trends 조회"""
    try:
        import urllib3
        _orig = urllib3.util.retry.Retry.__init__
        def _patch(self, *a, **kw):
            if 'method_whitelist' in kw:
                kw['allowed_methods'] = kw.pop('method_whitelist')
            _orig(self, *a, **kw)
        urllib3.util.retry.Retry.__init__ = _patch
        from pytrends.request import TrendReq
    except ImportError:
        print('⚠️  pytrends 없음')
        return {}

    results = {}
    try:
        pt = TrendReq(hl='ko', tz=540, timeout=(10, 30), retries=2, backoff_factor=0.5)
    except Exception as e:
        print(f'  TrendReq 오류: {e}')
        return {}

    # 섹터별 키워드 배치 수집
    all_kw_map = {}  # keyword → sector
    for sector, cfg in SECTOR_KEYWORDS.items():
        for kw in cfg['keywords']:
            all_kw_map[kw] = sector

    all_keywords = list(all_kw_map.keys())
    sector_scores = defaultdict(list)

    for i in range(0, len(all_keywords), 5):
        batch = all_keywords[i:i+5]
        try:
            pt.build_payload(batch, timeframe='today 1-m', geo='KR')
            df = pt.interest_over_time()
            if not df.empty:
                for kw in batch:
                    if kw in df.columns:
                        vals = df[kw].tolist()
                        if len(vals) >= 2:
                            avg = sum(vals[:-1]) / len(vals[:-1]) if len(vals) > 1 else vals[0]
                            latest = vals[-1]
                            change = (latest - avg) / avg * 100 if avg > 0 else 0
                            sector = all_kw_map[kw]
                            sector_scores[sector].append({
                                'kw': kw, 'latest': latest,
                                'change': change, 'vals': vals
                            })
            time.sleep(2)
        except Exception as e:
            print(f'  Trends 오류 ({batch}): {e}')
            time.sleep(3)

    # 섹터별 평균 점수 계산
    sector_trend = {}
    for sector, scores in sector_scores.items():
        if scores:
            avg_change = sum(s['change'] for s in scores) / len(scores)
            max_change = max(s['change'] for s in scores)
            best_kw    = max(scores, key=lambda x: x['change'])['kw']
            sector_trend[sector] = {
                'avg_change': round(avg_change, 1),
                'max_change': round(max_change, 1),
                'best_kw':    best_kw,
                'details':    scores,
            }

    return sector_trend


# ─── 소스 2. 뉴스 언급 빈도 + 이슈 키워드 추출 ───────────────────────────────
def scan_news_by_sector(days=2):
    """최근 N일 raw 파일에서 섹터별 언급 빈도 + 이슈 키워드 추출"""
    cutoff = date.today() - timedelta(days=days)
    sector_counts  = defaultdict(int)
    sector_context = defaultdict(list)  # 이슈 키워드 수집용

    scan_dirs = [
        ROOT / 'raw' / '크롤링 블로그뉴스유튭 요약',
        ROOT / 'raw' / 'telegram',
        ROOT / 'raw' / 'news',
    ]

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for f in sorted(scan_dir.glob('*.md'), reverse=True)[:50]:
            # 날짜 필터
            name = f.name
            dm = re.match(r'(\d{4}-\d{2}-\d{2})', name)
            if dm:
                try:
                    if date.fromisoformat(dm.group(1)) < cutoff:
                        continue
                except:
                    pass
            try:
                text = f.read_text(encoding='utf-8', errors='ignore')
                for sector, cfg in SECTOR_KEYWORDS.items():
                    for tag in cfg['news_tags']:
                        cnt = text.count(tag)
                        if cnt > 0:
                            sector_counts[sector] += cnt
                            # 해당 태그 주변 문장 수집 (이슈 컨텍스트)
                            sentences = [s.strip() for s in re.split(r'[.!\n]', text) if tag in s]
                            sector_context[sector].extend(sentences[:2])
            except:
                pass

    # 이슈 키워드 추출: 각 섹터 컨텍스트에서 자주 나오는 명사
    sector_issues = {}
    issue_stopwords = {
        '있다','없다','하다','이다','되다','것이','에서','으로','하고','때문','그리고',
        '이번','지난','올해','이후','현재','통해','대한','관련','국내','글로벌',
        '영업일','거래일','마감','시장','주식','투자','분석','전망','예상','수익',
        '종목','섹터','테마','관심','기대','상승','하락','강세','약세','매수','매도',
        '증권사','리포트','목표가','컨센서스','애널리스트','펀드','ETF',
        '미래반도체','코스피','코스닥','지수','유가','환율','금리',
    }
    for sector, contexts in sector_context.items():
        full_text = ' '.join(contexts)
        tokens = re.findall(r'[가-힣A-Z]{2,}', full_text)
        filtered = [t for t in tokens if t not in issue_stopwords and len(t) >= 2]
        counter = Counter(filtered)
        top_issues = [w for w, _ in counter.most_common(5)]
        sector_issues[sector] = top_issues

    return dict(sector_counts), sector_issues


# ─── 소스 3. Gemini 실시간 뉴스 보완 ─────────────────────────────────────────
def fetch_gemini_today_sectors():
    """Gemini Google Search로 오늘 한국 주식시장 주도 섹터 실시간 파악"""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {}

    api_key = env.get('GEMINI_API_KEY', '')
    if not api_key:
        return {}

    today = date.today().strftime('%Y년 %m월 %d일')
    prompt = f"""오늘 {today} 한국 주식시장에서 가장 강세를 보인 섹터/테마 TOP5를 알려줘.

각 섹터마다:
- 섹터명
- 강세 이유 (1줄)
- 대표 종목 (1~2개)

반드시 오늘 날짜 기준 최신 정보로 답해줘. 없으면 모른다고 해.
출력 형식 (다른 설명 없이):
섹터: [섹터명]
이유: [1줄]
종목: [종목1, 종목2]
---"""

    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            )
        )
        text = resp.text

        # 파싱
        results = {}
        blocks = text.split('---')
        for block in blocks:
            sector_m = re.search(r'섹터:\s*(.+)', block)
            reason_m = re.search(r'이유:\s*(.+)', block)
            stock_m  = re.search(r'종목:\s*(.+)', block)
            if sector_m:
                s = sector_m.group(1).strip()
                r = reason_m.group(1).strip() if reason_m else ''
                st = stock_m.group(1).strip() if stock_m else ''
                results[s] = {'reason': r, 'stocks': st}
        return results

    except Exception as e:
        print(f'  Gemini 실시간 조회 오류: {e}')
        return {}


# ─── 종합 섹터 온도계 ────────────────────────────────────────────────────────
def rank_sectors(trend_data, news_counts, sector_issues):
    """섹터별 종합 점수 계산 및 순위 정렬"""
    today = date.today().strftime('%Y-%m-%d')
    ranked = []

    for sector in SECTOR_KEYWORDS:
        t = trend_data.get(sector, {})
        n = news_counts.get(sector, 0)

        # 트렌드 점수 (0~3)
        t_change = t.get('avg_change', 0)
        if t_change >= 50:   t_score = 3
        elif t_change >= 20: t_score = 2
        elif t_change >= 0:  t_score = 1
        else:                t_score = 0

        # 뉴스 점수 (0~3)
        if n >= 30:   n_score = 3
        elif n >= 15: n_score = 2
        elif n >= 5:  n_score = 1
        else:         n_score = 0

        total = t_score + n_score

        if total >= 5:   heat = '🔴🔴 매우 강함'
        elif total >= 4: heat = '🔴 강함'
        elif total >= 2: heat = '🟠 보통'
        elif total >= 1: heat = '🟡 약함'
        else:            heat = '⚫ 조용'

        issues = sector_issues.get(sector, [])

        ranked.append({
            'sector': sector,
            'total': total,
            't_score': t_score,
            'n_score': n_score,
            't_change': t_change,
            'n_count': n,
            'heat': heat,
            'issues': issues,
            'best_kw': t.get('best_kw', ''),
        })

    ranked.sort(key=lambda x: -x['total'])
    return ranked


# ─── 리포트 생성 ─────────────────────────────────────────────────────────────
def build_report(ranked, days, gemini_today=None):
    today = date.today().strftime('%Y-%m-%d')
    lines = []
    lines.append(f'🌡️ 오늘의 주도 섹터 ({today})')
    lines.append(f'   뉴스 수집: 최근 {days}일 | 트렌드: 최근 1개월 대비')
    lines.append('=' * 55)
    lines.append('')

    for i, r in enumerate(ranked[:8], 1):
        if r['total'] == 0:
            break
        issues_str = ' · '.join(r['issues'][:3]) if r['issues'] else ''
        t_str = f"+{r['t_change']:.0f}%" if r['t_change'] >= 0 else f"{r['t_change']:.0f}%"
        lines.append(
            f"{i}위 {r['heat']:12}  {r['sector']}"
        )
        lines.append(
            f"    검색량 {t_str:6} | 뉴스 {r['n_count']:3}건"
            + (f" | 이슈: {issues_str}" if issues_str else '')
        )
        lines.append('')

    # Gemini 실시간 섹터 추가 (보완)
    if gemini_today:
        lines.append('─' * 55)
        lines.append('📡 Gemini 실시간 — 오늘 강세 섹터')
        lines.append('')
        for i, (sector, info) in enumerate(gemini_today.items(), 1):
            lines.append(f'  {i}. {sector}')
            if info.get('reason'):
                lines.append(f'     ↳ {info["reason"]}')
            if info.get('stocks'):
                lines.append(f'     종목: {info["stocks"]}')
        lines.append('')

    # 오늘의 한줄
    lines.append('─' * 55)
    lines.append('📌 오늘의 한줄')
    if gemini_today:
        top_g = list(gemini_today.items())[0]
        lines.append(f'   {top_g[0]} 주도. {top_g[1].get("reason","—")}')
    elif ranked and ranked[0]['total'] >= 2:
        top = ranked[0]
        issues_str = ' · '.join(top['issues'][:2]) if top['issues'] else '—'
        lines.append(f'   {top["sector"]} 주도. 이슈: {issues_str}')
    else:
        lines.append('   오늘 특이 섹터 없음 — 전반적 조용')

    return '\n'.join(lines)


# ─── 위키 섹터 index.md 일일 로그 업데이트 ───────────────────────────────────
def update_wiki_logs(ranked):
    today = date.today().strftime('%Y-%m-%d')
    updated = []

    for r in ranked[:5]:
        if r['total'] < 2:
            continue
        wiki_path = ROOT / r['sector_cfg']['wiki'] if 'sector_cfg' in r else None

        # 섹터 index 파일 경로 찾기
        sector_name = r['sector'].split('·')[0].strip()
        candidates = list(ROOT.glob(f'wiki/L5_섹터/{sector_name}*/*index.md'))
        if not candidates:
            candidates = list(ROOT.glob(f'wiki/L5_섹터/*/{sector_name}*index.md'))
        if not candidates:
            continue

        wiki_file = candidates[0]
        try:
            content = wiki_file.read_text(encoding='utf-8')
        except:
            continue

        issues_str = ' · '.join(r['issues'][:3]) if r['issues'] else '—'
        t_str = f"+{r['t_change']:.0f}%" if r['t_change'] >= 0 else f"{r['t_change']:.0f}%"

        # 오늘의 한줄 업데이트
        new_headline = f'> **{today}**: {r["heat"]} — 검색량 {t_str}, 뉴스 {r["n_count"]}건. 주요 이슈: {issues_str}'

        if '## 오늘의 한줄' in content:
            content = re.sub(
                r'## 오늘의 한줄.*?\n>.*?\n',
                f'## 오늘의 한줄 ({today} 업데이트)\n{new_headline}\n',
                content, flags=re.DOTALL, count=1
            )
        else:
            # 없으면 상단에 추가
            content = f'## 오늘의 한줄 ({today} 업데이트)\n{new_headline}\n\n' + content

        # 일일 분위기 로그에 행 추가
        log_row = (
            f'| {today} | — | — | {issues_str[:30]} '
            f'| {r["heat"]} 검색량{t_str} 뉴스{r["n_count"]}건 '
            f'| {r["heat"][:2]} |'
        )

        if '## 📅 일일 분위기 로그' in content:
            # 헤더 다음 줄에 삽입
            content = re.sub(
                r'(## 📅 일일 분위기 로그.*?\|.*?\n\|[-| ]+\n)',
                lambda m: m.group(0) + log_row + '\n',
                content, flags=re.DOTALL, count=1
            )

            # 7일 초과 행 삭제
            cutoff = date.today() - timedelta(days=7)
            lines = content.split('\n')
            new_lines = []
            in_log = False
            for line in lines:
                if '## 📅 일일 분위기 로그' in line:
                    in_log = True
                if in_log and line.startswith('| 20') and '|' in line:
                    dm = re.search(r'\| (\d{4}-\d{2}-\d{2})', line)
                    if dm:
                        try:
                            if date.fromisoformat(dm.group(1)) < cutoff:
                                continue
                        except:
                            pass
                if line.startswith('## ') and '일일 분위기' not in line:
                    in_log = False
                new_lines.append(line)
            content = '\n'.join(new_lines)

        if not DRY_RUN:
            wiki_file.write_text(content, encoding='utf-8')
            updated.append(wiki_file.name)

    return updated


# ─── 텔레그램 ─────────────────────────────────────────────────────────────────
def send_telegram(text):
    import requests
    if not BOT_TOKEN or not CHAT_ID:
        return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': f'```\n{chunk}\n```', 'parse_mode': 'Markdown'},
            timeout=10
        )


# ─── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    today = date.today().strftime('%Y%m%d')
    print(f'📊 섹터 트렌드 리포터 ({date.today()})')
    print(f'   뉴스 수집: 최근 {DAYS}일 | {"DRY RUN" if DRY_RUN else "위키 반영 ON"}')
    print()

    print('[1/3] Google Trends 섹터별 조회 중...')
    trend_data = fetch_trends_by_sector()
    print(f'  → {len(trend_data)}/{len(SECTOR_KEYWORDS)}개 섹터 조회 성공')

    print(f'[2/3] 뉴스 언급 빈도 + 이슈 키워드 수집 중 (최근 {DAYS}일)...')
    news_counts, sector_issues = scan_news_by_sector(days=DAYS)
    top_sector = max(news_counts, key=lambda k: news_counts[k]) if news_counts else '—'
    print(f'  → 최다 언급: {top_sector} ({news_counts.get(top_sector,0)}건)')

    print('[3/3] Gemini 실시간 뉴스 보완 중...')
    gemini_today = fetch_gemini_today_sectors()
    if gemini_today:
        print(f'  → 오늘 강세 섹터 {len(gemini_today)}개 확인')
    else:
        print('  → Gemini 실시간 없음 (raw 데이터 기반으로만 판단)')

    print('[4/4] 섹터 순위 계산 중...')
    ranked = rank_sectors(trend_data, news_counts, sector_issues)
    print()

    # 리포트 출력
    report = build_report(ranked, DAYS, gemini_today)
    print(report)

    # 위키 업데이트
    if not DRY_RUN:
        print()
        print('📝 위키 섹터 index.md 업데이트 중...')
        updated = update_wiki_logs(ranked)
        for f in updated:
            print(f'  ✅ {f}')

    # 결과 저장
    out_dir = ROOT / 'raw' / 'market'
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f'{today}_sector_heat.md'
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f'# 섹터 트렌드 {today}\n\n```\n{report}\n```\n\n## 전체 순위\n')
        for r in ranked:
            f.write(f"- {r['sector']}: 트렌드{r['t_score']} 뉴스{r['n_score']} = {r['heat']}\n")
    print(f'\n💾 저장: {out_file.name}')

    if USE_TG:
        send_telegram(report)
        print('✅ 텔레그램 전송 완료')

    # log.md 기록
    log_file = ROOT / 'wiki' / 'log.md'
    if not DRY_RUN and log_file.exists():
        log = log_file.read_text(encoding='utf-8')
        top3 = ' > '.join([r['sector'] for r in ranked[:3] if r['total'] >= 2])
        entry = f'- {date.today()} — 섹터 트렌드: {top3}\n'
        log_file.write_text(entry + log, encoding='utf-8')


if __name__ == '__main__':
    main()
