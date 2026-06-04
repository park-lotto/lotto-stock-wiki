"""
ingest_crawl.py — raw/report/{date}/ → wiki 섹터/종목 코멘트 누적 (Pass 2)

흐름:
  1. Gemini 분류: sector / stock / skip
  2. sector → wiki/L5_섹터/{섹터}/sector_{섹터}.md 에 [날짜] 코멘트 append
  3. stock  → wiki/L5_섹터/{섹터}/stock/stock_{종목}.md 에 [날짜] 코멘트 append

사용:
  python scripts/ingest_crawl.py --date 2026-06-04
  python scripts/ingest_crawl.py             # 오늘 날짜 자동
  python scripts/ingest_crawl.py --dry-run   # 분류만, wiki 수정 없음
  python scripts/ingest_crawl.py --file 완성차  # 특정 파일만
"""
import sys, io, re, json, argparse
from datetime import date
from pathlib import Path
from google import genai
from google.genai import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT            = Path(__file__).parent.parent
STATE_PATH      = ROOT / 'pipeline' / 'crawl_ingest_state.json'
REGISTRY_PATH   = ROOT / 'pipeline' / 'channel_registry.json'
WIKI_L5         = ROOT / 'wiki' / 'L5_섹터'
WIKI_INSIGHTS   = ROOT / 'wiki' / 'insights'
LOG_PATH        = ROOT / 'wiki' / 'log.md'

WIKI_INSIGHTS.mkdir(parents=True, exist_ok=True)

# ── env ───────────────────────────────────────────────────────────────────────
env = {}
for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k.strip()] = v.strip()

client = genai.Client(api_key=env['GEMINI_API_KEY'])
L5_SECTORS = sorted(d.name for d in WIKI_L5.iterdir() if d.is_dir())

# ── 채널 레지스트리 로드 ──────────────────────────────────────────────────────
def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        data = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        return {k: v for k, v in data.items() if not k.startswith('_')}
    return {}

CHANNEL_REGISTRY = load_registry()

TELEGRAM_PROMPT = """\
아래 텔레그램 채널 요약에서 섹터/종목 관련 코멘트를 모두 추출해줘.
하나의 파일에서 여러 섹터·종목이 나와도 각각 별도 항목으로 추출.

분류 기준:
- "sector": 산업/섹터 전반 언급
- "stock": 한국 상장 종목 1개 언급
- "coupling": 해외(외국) 기업 언급 → 연관 한국 섹터에 커플링 신호로 기록
- 시황 전체·금리·환율·지수만 언급된 건 skip

섹터명은 아래 목록에서만:
{sectors}

코멘트 규칙:
- 1~2줄, 핵심 수치/이슈 포함, 한국어
- broker 필드에 채널명 그대로 기입
- coupling: foreign_stock(해외기업명), sector(연관 한국 섹터명) 필수

JSON 배열만 반환:
[
  {{"file":"파일명","type":"sector","sector":"반도체","broker":"채널명","comment":"코멘트"}},
  {{"file":"파일명","type":"stock","sector":"바이오","stock":"오스코텍","code":"039200","broker":"채널명","comment":"코멘트"}},
  {{"file":"파일명","type":"coupling","sector":"반도체","foreign_stock":"낸야테크놀로지","broker":"채널명","comment":"코멘트"}}
]

채널 요약:
{reports}
"""

def classify_telegram(reports: list) -> list:
    reports_text = ''
    for r in reports:
        reports_text += f'파일: {r["file"]}\n채널: {r["broker"]}\n---내용---\n{r["summary"]}\n===\n'

    prompt = TELEGRAM_PROMPT.format(sectors=', '.join(L5_SECTORS), reports=reports_text)
    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[types.Content(role='user', parts=[types.Part(text=prompt)])]
    )
    raw = re.sub(r'^```[\w]*\n?', '', resp.text.strip())
    raw = re.sub(r'\n?```$', '', raw)
    return json.loads(raw)

INSIGHTS_PROMPT = """\
아래 발언에서 이 사람의 사고방식과 인사이트를 추출해줘.
팩트(수치·이벤트)는 제외하고, 생각의 구조와 판단 방식만 뽑아줘.

추출 항목:
1. frameworks: 반복 등장하는 분석 공식·원칙 (없으면 빈 배열)
2. signals: "A를 보면 B를 판단" 같은 시그널 패턴 (없으면 빈 배열)
3. calls: 실제 언급한 관심/매수/매도 (없으면 빈 배열)
4. summary: 오늘 핵심 주장 1~2줄

JSON만 반환:
{{
  "frameworks": ["공식1", "공식2"],
  "signals": ["TEL 강세 → 당일 국내 장비주 진입 타이밍"],
  "calls": [{{"type":"관심","target":"주성엔지니어링","reason":"TEL 팔로잉"}}],
  "summary": "핵심 주장"
}}

발언:
{content}
"""

def extract_insights(channel: str, content: str) -> dict:
    prompt = INSIGHTS_PROMPT.format(content=content)
    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[types.Content(role='user', parts=[types.Part(text=prompt)])]
    )
    raw = re.sub(r'^```[\w]*\n?', '', resp.text.strip())
    raw = re.sub(r'\n?```$', '', raw)
    return json.loads(raw)

def append_insight(channel: str, date_str: str, data: dict):
    insight_file = WIKI_INSIGHTS / f'{channel}.md'

    if not insight_file.exists():
        reg = CHANNEL_REGISTRY.get(channel, {})
        type_label = {'A':'증권사 공식','B':'고급 큐레이션','C':'섹터 전문가','D':'인사이트·흐름형'}.get(reg.get('type',''), '')
        specialty = ', '.join(reg.get('specialty', []))
        insight_file.write_text(
            f'# {channel} — 인사이트 누적\n'
            f'> 타입: {type_label} | 전문: {specialty}\n\n'
            f'## 반복 공식\n\n'
            f'## 콜 히스토리\n'
            f'| 날짜 | 타입 | 대상 | 이유 |\n'
            f'|------|------|------|------|\n\n'
            f'## 일별 로그\n',
            encoding='utf-8'
        )

    content = insight_file.read_text(encoding='utf-8')

    # 콜 히스토리 테이블에 추가
    calls = data.get('calls', [])
    call_lines = ''
    for c in calls:
        call_lines += f'| {date_str} | {c.get("type","")} | {c.get("target","")} | {c.get("reason","")} |\n'

    # 일별 로그에 추가
    fw = ' / '.join(data.get('frameworks', []))
    sg = ' / '.join(data.get('signals', []))
    summary = data.get('summary', '')
    log_entry = f'\n[{date_str}] {summary}'
    if fw:  log_entry += f'\n- 공식: {fw}'
    if sg:  log_entry += f'\n- 시그널: {sg}'

    # 테이블 뒤에 콜 삽입
    if call_lines:
        content = content.replace(
            '| 날짜 | 타입 | 대상 | 이유 |\n|------|------|------|------|\n',
            f'| 날짜 | 타입 | 대상 | 이유 |\n|------|------|------|------|\n{call_lines}'
        )

    content += log_entry + '\n'
    insight_file.write_text(content, encoding='utf-8')
    return True

# ── state ─────────────────────────────────────────────────────────────────────
def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8-sig'))
    return {'pdf_summarized': [], 'ingested': [], 'last_run': None}

def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

# ── 파일 메타 + 요약 전문 로드 ────────────────────────────────────────────────
def load_report(md_path: Path) -> dict:
    text  = md_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    title  = next((l.lstrip('# ').strip() for l in lines if l.startswith('#')), md_path.stem)
    broker = next((l.split('**증권사**:')[-1].strip() for l in lines if '**증권사**:' in l), '')
    # AI 요약 전문 (## 📄 AI 요약 이후)
    ai_idx  = text.find('## 📄 AI 요약')
    summary = text[ai_idx:].strip() if ai_idx >= 0 else text[:2000]
    return {'file': md_path.name, 'title': title, 'broker': broker, 'summary': summary}

# ── Gemini: 배치 분류 + 코멘트 추출 ──────────────────────────────────────────
PROMPT = """\
아래 증권사 리포트들을 분류하고, sector/stock 리포트는 핵심 코멘트를 추출해줘.

분류 기준:
- "sector": 산업/섹터 전반 분석 (월간동향, 산업전망 등)
- "stock": 특정 종목 1개 분석 (투자의견·TP·실적·이슈)
- "skip": 시황 Daily, 매크로(환율·금리), 아침브리핑, 채권, ETF, 펀드플로우 등

섹터명은 아래 목록에서만:
{sectors}

코멘트 규칙:
- 1~2줄, 핵심 수치/이슈 포함, 한국어
- sector 예: "5월 완성차 판매 전년비 -3%. 하반기 로봇·자율주행 모멘텀으로 시장 재평가 중."
- stock 예: "교보증권 TP 70만 유지. 릴리와 최대 1조2600억 기술이전 계약, 글로벌 빅파마 납품 본격화."

JSON 배열만 반환:
[
  {{"file":"파일명","type":"sector","sector":"자동차","broker":"하나증권","comment":"코멘트"}},
  {{"file":"파일명","type":"stock","sector":"바이오","stock":"한미약품","code":"128940","broker":"교보증권","comment":"코멘트"}},
  {{"file":"파일명","type":"skip"}}
]

리포트 목록:
{reports}
"""

def classify_and_extract(reports: list) -> list:
    reports_text = ''
    for r in reports:
        reports_text += f'파일: {r["file"]}\n제목: {r["title"]}\n증권사: {r["broker"]}\n---요약---\n{r["summary"][:600]}\n===\n'

    prompt = PROMPT.format(sectors=', '.join(L5_SECTORS), reports=reports_text)

    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[types.Content(role='user', parts=[types.Part(text=prompt)])]
    )
    raw = re.sub(r'^```[\w]*\n?', '', resp.text.strip())
    raw = re.sub(r'\n?```$', '', raw)
    return json.loads(raw)

# ── wiki append ───────────────────────────────────────────────────────────────
def append_sector_comment(sector: str, date_str: str, comment: str) -> bool:
    sector_dir  = WIKI_L5 / sector
    sector_file = sector_dir / f'sector_{sector}.md'

    if not sector_dir.exists():
        print(f'    ⚠️ 섹터 폴더 없음: {sector}')
        return False

    if not sector_file.exists():
        sector_file.write_text(f'# {sector} 섹터 코멘트\n\n', encoding='utf-8')

    content = sector_file.read_text(encoding='utf-8')
    new_line = f'\n\n[{date_str}] {comment}'
    sector_file.write_text(content + new_line, encoding='utf-8')
    return True


def append_stock_comment(sector: str, stock: str, code: str,
                         date_str: str, broker: str, comment: str) -> bool:
    stock_dir = WIKI_L5 / sector / 'stock'
    stock_dir.mkdir(parents=True, exist_ok=True)

    # 기존 파일 탐색
    candidates = list(stock_dir.glob(f'*{stock}*.md'))
    if not candidates and code:
        candidates = list(stock_dir.glob(f'*{code}*.md'))

    if candidates:
        stock_file = candidates[0]
    else:
        # 신규 생성
        stock_file = stock_dir / f'stock_{stock}.md'
        display = f'{stock}({code})' if code else stock
        stock_file.write_text(f'# {display}\n> 섹터: {sector}\n\n', encoding='utf-8')

    content  = stock_file.read_text(encoding='utf-8')
    new_line = f'\n[{date_str}] [{broker}] {comment}'
    stock_file.write_text(content + new_line, encoding='utf-8')
    return True

# ── 메인 ─────────────────────────────────────────────────────────────────────
def load_telegram(md_path: Path) -> dict:
    text  = md_path.read_text(encoding='utf-8')
    # 채널명: 파일명에서 추출 (예: 신한리서치_요약.md → 신한리서치)
    channel = md_path.stem.replace('_요약', '')
    return {'file': md_path.name, 'title': channel, 'broker': channel, 'summary': text}

def process(date_str: str, dry_run=False, limit=0, file_kw=None, source='report'):
    state = load_state()

    if source == 'telegram':
        raw_dir   = ROOT / 'raw' / 'telegram' / date_str
        state_key = 'ingested_tg'
        label     = f'raw/telegram/{date_str}/'
        loader    = load_telegram
    else:
        raw_dir   = ROOT / 'raw' / 'report' / date_str
        state_key = 'ingested'
        label     = f'raw/report/{date_str}/'
        loader    = load_report

    if not raw_dir.exists():
        print(f'{label} 없음'); return

    all_files    = sorted(raw_dir.glob('*.md'))
    ingested_set = set(state.get(state_key, []))
    todo = [f for f in all_files if f.name not in ingested_set]
    if file_kw:
        todo = [f for f in todo if file_kw in f.name]
    if limit:
        todo = todo[:limit]

    print(f'{label} → {len(todo)}개 처리 예정')
    if not todo: print('모두 처리됨'); return

    reports = [loader(f) for f in todo]
    print(f'  Gemini 분류+코멘트 추출 중... ({len(reports)}개)')
    classified = classify_telegram(reports) if source == 'telegram' else classify_and_extract(reports)

    s = sum(1 for c in classified if c['type']=='sector')
    st = sum(1 for c in classified if c['type']=='stock')
    cp = sum(1 for c in classified if c['type']=='coupling')
    sk = sum(1 for c in classified if c['type']=='skip')
    print(f'  결과: sector={s}, stock={st}, coupling={cp}, skip={sk}')

    if dry_run:
        print('\n[DRY-RUN]')
        for c in classified:
            if c['type'] == 'skip': continue
            if c['type'] == 'coupling':
                tag = f'{c.get("sector","")}/(커플링){c.get("foreign_stock","")}'
            else:
                tag = f'{c.get("sector","")}' + (f'/{c.get("stock","")}' if c['type']=='stock' else '')
            print(f'  [{c["type"]:8}] {tag:30} → {c.get("comment","")[:60]}')
        return

    # ── Pass 2: 인사이트 채널별 처리 ──────────────────────────────────────────
    if source == 'telegram':
        for r in reports:
            channel = r['broker']
            reg = CHANNEL_REGISTRY.get(channel, {})
            if reg.get('pass2', False):
                print(f'  [인사이트] {channel} Pass 2 추출 중...')
                try:
                    data = extract_insights(channel, r['summary'])
                    append_insight(channel, date_str, data)
                    calls_cnt = len(data.get('calls', []))
                    print(f'  [인사이트✅] {channel} → {data.get("summary","")[:60]} (콜 {calls_cnt}개)')
                except Exception as e:
                    print(f'  [인사이트⚠️] {channel} 실패: {e}')

    newly_done = []
    for c in classified:
        fname = c['file']
        if c['type'] == 'skip':
            newly_done.append(fname); continue

        comment = c.get('comment', '')
        broker  = c.get('broker', '')

        if c['type'] == 'sector':
            ok = append_sector_comment(c['sector'], date_str, comment)
            if ok:
                print(f'  [섹터✅] {c["sector"]:12} → {comment[:60]}')
                newly_done.append(fname)

        elif c['type'] == 'stock':
            ok = append_stock_comment(c['sector'], c.get('stock',''), c.get('code',''),
                                      date_str, broker, comment)
            if ok:
                print(f'  [종목✅] {c["sector"]}/{c.get("stock",""):12} → {comment[:50]}')
                newly_done.append(fname)

        elif c['type'] == 'coupling':
            foreign = c.get('foreign_stock', '')
            coupling_comment = f'[커플링: {foreign}] {comment}'
            ok = append_sector_comment(c['sector'], date_str, coupling_comment)
            if ok:
                print(f'  [커플링✅] {c["sector"]}/{foreign:12} → {comment[:50]}')
                newly_done.append(fname)

    state.setdefault(state_key, [])
    state[state_key].extend(newly_done)
    state['last_run'] = date_str
    save_state(state)

    log_line = f'- {date_str} ingest_crawl({source}): sector {s}개, stock {st}개 코멘트 추가\n'
    if LOG_PATH.exists():
        LOG_PATH.write_text(LOG_PATH.read_text(encoding='utf-8') + log_line, encoding='utf-8')

    print(f'\n✅ 완료 | sector {s}개, stock {st}개 코멘트 누적')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--date',    default=date.today().strftime('%Y-%m-%d'))
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--limit',   type=int, default=0)
    p.add_argument('--file',    default=None)
    p.add_argument('--source',  default='report', choices=['report', 'telegram'])
    a = p.parse_args()
    process(a.date, a.dry_run, a.limit, a.file, a.source)

if __name__ == '__main__':
    main()
