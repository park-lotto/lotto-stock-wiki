# crawl_ingest 파이프라인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `C:\Users\TheRose\crawling_bot_data\YYYY-MM-DD\` 에 매일 쌓이는 크롤링 데이터를 wiki에 자동 ingest하는 2-pass 파이프라인 구축

**Architecture:**
- Pass 1 (`pdf_summarize.py`): reports/*.md 파일의 PDF 링크 감지 → Gemini 2.0 Flash로 요약 → .md 파일에 주입
- Pass 2 (`ingest_crawl.py`): 시간대 필터(`--from`/`--to`) + `crawl_ingest_state.json` 중복 방지 + 폴더별 wiki 라우팅
- 둘 다 독립 실행 가능. 보통 순서: `pdf_summarize.py` → `ingest_crawl.py`

**Tech Stack:** Python 3.12, `google.genai` (기존 코드베이스 패턴), `requests`, `pathlib`, `argparse`, `json`, `re`

**소스 경로:** `C:\Users\TheRose\crawling_bot_data\YYYY-MM-DD\{blog,market,news,reports,telegram,youtube}\`

**wiki 라우팅 규칙:**
| 폴더 | 대상 wiki 파일 |
|------|--------------|
| market/ | `wiki/L3_한국시장/market_한국증시_{date}.md` |
| news/ | `wiki/L5_섹터/{섹터}/피드_{섹터}.md` |
| reports/ | `wiki/L5_섹터/{섹터}/피드_{섹터}.md` |
| telegram/태린이아빠 | `wiki/L6_수급/수급index.md` |
| blog/ | `wiki/L5_섹터/{섹터}/stock/{종목명}.md` |
| youtube/ | wiki 갱신 없음 (raw 저장만) |

---

## 파일 구조

```
pipeline/
└── crawl_ingest_state.json     # 처리완료 파일 기록 (신규)

scripts/
├── pdf_summarize.py            # Pass 1: PDF → Gemini → .md 주입 (신규)
└── ingest_crawl.py             # Pass 2: 라우팅 + wiki 업데이트 (신규)
```

---

## Task 1: `pipeline/crawl_ingest_state.json` 초기 구조 생성

**Files:**
- Create: `pipeline/crawl_ingest_state.json`

- [ ] **Step 1: state.json 파일 생성**

```json
{
  "pdf_summarized": [],
  "ingested": [],
  "last_run": null
}
```

`pdf_summarized`: pdf_summarize.py가 처리 완료한 파일 경로 목록 (형식: `"2026-06-04/reports/파일명.md"`)
`ingested`: ingest_crawl.py가 wiki에 기록 완료한 파일 경로 목록
`last_run`: 마지막 실행 ISO timestamp

- [ ] **Step 2: 파일 존재 확인**

```bash
python -c "import json; d=json.load(open('pipeline/crawl_ingest_state.json')); print(d)"
```
Expected: `{'pdf_summarized': [], 'ingested': [], 'last_run': None}`

- [ ] **Step 3: Commit**

```bash
git add pipeline/crawl_ingest_state.json
git commit -m "feat: crawl_ingest_state.json 초기 구조 생성"
```

---

## Task 2: `scripts/pdf_summarize.py` 구현

**Files:**
- Create: `scripts/pdf_summarize.py`

reports/*.md 파일에서 PDF 링크를 감지하고 Gemini 2.0 Flash로 요약 후 .md 파일에 `## 📄 AI 요약` 섹션을 주입한다.

- [ ] **Step 1: 스크립트 생성**

```python
"""
pdf_summarize.py — reports/*.md PDF 링크 → Gemini 2.0 Flash 요약 → .md 주입 (Pass 1)

사용:
  python scripts/pdf_summarize.py --date 2026-06-04
  python scripts/pdf_summarize.py  # 오늘 날짜 자동
"""
import sys, io, re, json, argparse, requests
from datetime import date
from pathlib import Path
from google import genai
from google.genai import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
ENV  = ROOT / '.env'
STATE_PATH = ROOT / 'pipeline' / 'crawl_ingest_state.json'
CRAWL_BASE = Path(r'C:\Users\TheRose\crawling_bot_data')

# ── 환경 변수 로드 ─────────────────────────────────────────────────────────────
env = {}
for line in ENV.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

API_KEY = env.get('GEMINI_API_KEY', '')
if not API_KEY:
    print('GEMINI_API_KEY 없음'); sys.exit(1)

client = genai.Client(api_key=API_KEY)

# ── state.json ────────────────────────────────────────────────────────────────
def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    return {'pdf_summarized': [], 'ingested': [], 'last_run': None}

def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

# ── PDF 링크 추출 ──────────────────────────────────────────────────────────────
PDF_RE = re.compile(r'\[다운로드\]\((https?://[^\)]+\.pdf[^\)]*)\)', re.IGNORECASE)

def extract_pdf_url(md_text: str) -> str | None:
    m = PDF_RE.search(md_text)
    return m.group(1) if m else None

# ── PDF 다운로드 ───────────────────────────────────────────────────────────────
def download_pdf(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f'  PDF 다운로드 실패: {e}')
        return None

# ── Gemini 요약 ────────────────────────────────────────────────────────────────
SUMMARY_PROMPT = """이 증권사 리포트를 아래 형식으로 요약해줘. 반드시 한국어로.

**핵심 주장 (1줄)**: 
**주요 내용 (3줄 이내)**:
- 
**언급 종목/섹터**: 
**투자 시사점**: """

def summarize_with_gemini(pdf_bytes: bytes, filename: str) -> str | None:
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'),
                SUMMARY_PROMPT
            ]
        )
        return response.text.strip()
    except Exception as e:
        print(f'  Gemini 요약 실패 ({filename}): {e}')
        return None

# ── .md 파일에 요약 주입 ────────────────────────────────────────────────────────
ALREADY_SUMMARIZED = '## 📄 AI 요약'

def inject_summary(md_path: Path, summary: str) -> bool:
    """기존 파일에 AI 요약 섹션 추가. 이미 있으면 스킵."""
    text = md_path.read_text(encoding='utf-8')
    if ALREADY_SUMMARIZED in text:
        return False  # 이미 처리됨
    block = f'\n\n## 📄 AI 요약\n\n{summary}\n'
    md_path.write_text(text + block, encoding='utf-8')
    return True

# ── 날짜 처리 메인 ─────────────────────────────────────────────────────────────
def process_date(date_str: str):
    state = load_state()
    reports_dir = CRAWL_BASE / date_str / 'reports'
    if not reports_dir.exists():
        print(f'  reports 폴더 없음: {reports_dir}')
        return

    md_files = sorted(reports_dir.glob('*.md'))
    print(f'reports/ 파일 {len(md_files)}개 발견')

    for md_path in md_files:
        rel_key = f'{date_str}/reports/{md_path.name}'
        if rel_key in state['pdf_summarized']:
            print(f'  [SKIP] {md_path.name}')
            continue

        text = md_path.read_text(encoding='utf-8')
        if ALREADY_SUMMARIZED in text:
            state['pdf_summarized'].append(rel_key)
            continue

        pdf_url = extract_pdf_url(text)
        if not pdf_url:
            print(f'  [NO PDF] {md_path.name}')
            state['pdf_summarized'].append(rel_key)  # PDF 없는 파일도 완료 표시
            continue

        print(f'  [PDF] {md_path.name}')
        pdf_bytes = download_pdf(pdf_url)
        if not pdf_bytes:
            continue

        summary = summarize_with_gemini(pdf_bytes, md_path.name)
        if not summary:
            continue

        injected = inject_summary(md_path, summary)
        if injected:
            print(f'  [OK] 요약 주입 완료: {md_path.name}')
            state['pdf_summarized'].append(rel_key)
            save_state(state)

    print(f'pdf_summarize 완료: {date_str}')

# ── argparse ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='reports PDF → Gemini 요약 → .md 주입')
    parser.add_argument('--date', default=date.today().strftime('%Y-%m-%d'),
                        help='처리 날짜 (기본: 오늘)')
    args = parser.parse_args()
    process_date(args.date)

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 동작 테스트 (오늘 날짜 1개 파일)**

```bash
python scripts/pdf_summarize.py --date 2026-06-04
```

Expected 출력:
```
reports/ 파일 N개 발견
  [PDF] 2026-06-04_1359_(Macro Snapshot) 반도체 호황...md
  [OK] 요약 주입 완료: ...
pdf_summarize 완료: 2026-06-04
```

파일 확인:
```bash
python -c "
from pathlib import Path
f = Path(r'C:\Users\TheRose\crawling_bot_data\2026-06-04\reports')
files = list(f.glob('*.md'))
for p in files[:2]:
    t = p.read_text(encoding='utf-8')
    print(p.name, '→', '✅ 요약있음' if '## 📄 AI 요약' in t else '❌ 요약없음')
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/pdf_summarize.py pipeline/crawl_ingest_state.json
git commit -m "feat: pdf_summarize.py — reports PDF Gemini 요약 주입 (Pass 1)"
```

---

## Task 3: `ingest_crawl.py` — 뼈대 + state + 파일 스캔 + 시간 필터

**Files:**
- Create: `scripts/ingest_crawl.py`

- [ ] **Step 1: 뼈대 구조 생성**

```python
"""
ingest_crawl.py — crawling_bot_data → wiki 자동 라우팅 파이프라인 (Pass 2)

사용:
  python scripts/ingest_crawl.py --date 2026-06-04
  python scripts/ingest_crawl.py --date 2026-06-04 --from 0800 --to 1400
  python scripts/ingest_crawl.py --date 2026-06-04 --folder news
"""
import sys, io, re, json, argparse
from datetime import date, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT       = Path(__file__).parent.parent
STATE_PATH = ROOT / 'pipeline' / 'crawl_ingest_state.json'
CRAWL_BASE = Path(r'C:\Users\TheRose\crawling_bot_data')
WIKI       = ROOT / 'wiki'

# ── SECTOR MAP (키워드 → 섹터 폴더명) ──────────────────────────────────────────
SECTOR_MAP = {
    '반도체': ['반도체', 'HBM', 'NAND', 'DRAM', '메모리', '파운드리', '시스템반도체',
               '실트론', 'SK하이닉스', '삼성전자', '마이크론', '엔비디아'],
    '방산':   ['방산', '우주', '잠수함', '전투기', '레이더', '한화', 'LIG', '현대로템',
               '스페이스X', '위성'],
    '로봇':   ['로봇', '자동화', '액추에이터', '감속기', '협동로봇', '두산로보틱스'],
    '바이오': ['바이오', '제약', '의약', '신약', '임상', '올릭스', '한미약품', '셀트리온',
               '유한양행', '로레알', '피부'],
    '2차전지ESS': ['2차전지', '배터리', 'ESS', '양극재', '음극재', '전해질', '전고체',
                   '엘앤에프', '에코프로', '포스코퓨처엠', 'LG에너지'],
    'AI소프트웨어': ['AI소프트웨어', '클라우드', 'SaaS', '플랫폼SW', '솔루션'],
    'LNG':    ['LNG', '조선', '해운', '현대중공업', '삼성중공업', 'HD현대'],
    '미용':   ['화장품', '뷰티', '미용', 'K뷰티', '아모레', 'LG생활건강'],
    '소비내수': ['소비', '내수', '유통', '음식', '식품', '백화점', '현대백화점'],
}

SECTOR_FOLDERS = list(SECTOR_MAP.keys())

# ── state.json ────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    return {'pdf_summarized': [], 'ingested': [], 'last_run': None}

def save_state(state: dict):
    state['last_run'] = datetime.now().isoformat()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

# ── 시간 필터 ─────────────────────────────────────────────────────────────────
HHMM_RE = re.compile(r'^\d{4}-\d{2}-\d{2}_(\d{4})_')

def parse_hhmm(filename: str) -> int | None:
    """파일명에서 HHMM 추출 → 정수. 없으면 None (텔레그램 등 날짜만 있는 파일)."""
    m = HHMM_RE.match(filename)
    return int(m.group(1)) if m else None

def in_time_range(hhmm: int | None, from_hhmm: int, to_hhmm: int) -> bool:
    """HHMM이 없으면 항상 포함 (텔레그램 등). 있으면 범위 체크."""
    if hhmm is None:
        return True
    return from_hhmm <= hhmm <= to_hhmm

# ── 섹터 감지 ─────────────────────────────────────────────────────────────────
def keyword_to_sector(text: str) -> str | None:
    """텍스트에서 섹터 키워드 매칭 → 섹터명 반환. 없으면 None."""
    for sector, keywords in SECTOR_MAP.items():
        for kw in keywords:
            if kw in text:
                return sector
    return None

# ── wiki 파일 append ──────────────────────────────────────────────────────────
def append_to_wiki(target_path: Path, block: str):
    """target_path 파일 끝에 block 추가. 파일 없으면 생성."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open('a', encoding='utf-8') as f:
        f.write(block)

# ── 라우터 플레이스홀더 (Task 4~8에서 구현) ────────────────────────────────────
def route_market(md_path: Path, date_str: str, state: dict): pass
def route_news(md_path: Path, date_str: str, state: dict): pass
def route_reports(md_path: Path, date_str: str, state: dict): pass
def route_telegram(md_path: Path, date_str: str, state: dict): pass
def route_blog(md_path: Path, date_str: str, state: dict): pass

FOLDER_ROUTERS = {
    'market':   route_market,
    'news':     route_news,
    'reports':  route_reports,
    'telegram': route_telegram,
    'blog':     route_blog,
    'youtube':  None,  # raw 저장만, wiki 갱신 없음
}

# ── 메인 실행 ─────────────────────────────────────────────────────────────────
def process_folder(folder_name: str, folder_path: Path, date_str: str,
                   from_hhmm: int, to_hhmm: int, state: dict):
    router = FOLDER_ROUTERS.get(folder_name)
    if router is None:
        print(f'  [{folder_name}] 라우터 없음 — 스킵')
        return

    md_files = sorted(folder_path.glob('*.md'))
    print(f'[{folder_name}] {len(md_files)}개 파일')

    for md_path in md_files:
        rel_key = f'{date_str}/{folder_name}/{md_path.name}'
        if rel_key in state['ingested']:
            print(f'  [SKIP] {md_path.name}')
            continue

        hhmm = parse_hhmm(md_path.name)
        if not in_time_range(hhmm, from_hhmm, to_hhmm):
            print(f'  [시간제외] {md_path.name}')
            continue

        router(md_path, date_str, state)

def main():
    parser = argparse.ArgumentParser(description='crawling_bot_data → wiki 자동 ingest')
    parser.add_argument('--date',   default=date.today().strftime('%Y-%m-%d'))
    parser.add_argument('--from',   dest='from_hhmm', default='0000')
    parser.add_argument('--to',     dest='to_hhmm',   default='2359')
    parser.add_argument('--folder', default=None, help='특정 폴더만 처리')
    args = parser.parse_args()

    from_hhmm = int(args.from_hhmm)
    to_hhmm   = int(args.to_hhmm)
    date_str  = args.date
    base_dir  = CRAWL_BASE / date_str

    if not base_dir.exists():
        print(f'날짜 폴더 없음: {base_dir}'); return

    state = load_state()
    folders = [args.folder] if args.folder else list(FOLDER_ROUTERS.keys())

    for folder_name in folders:
        folder_path = base_dir / folder_name
        if not folder_path.exists():
            continue
        process_folder(folder_name, folder_path, date_str, from_hhmm, to_hhmm, state)

    save_state(state)
    print(f'\n✅ ingest_crawl 완료: {date_str}')

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 뼈대 동작 확인 (라우터 비어 있어도 실행 확인)**

```bash
python scripts/ingest_crawl.py --date 2026-06-04
```

Expected 출력:
```
[market] 1개 파일
[news] N개 파일
[reports] N개 파일
[telegram] N개 파일
[blog] N개 파일
[youtube] 라우터 없음 — 스킵

✅ ingest_crawl 완료: 2026-06-04
```
(아직 라우터 미구현이므로 실제 wiki 업데이트 없음)

- [ ] **Step 3: Commit**

```bash
git add scripts/ingest_crawl.py
git commit -m "feat: ingest_crawl.py — 뼈대 + 파일 스캔 + 시간 필터"
```

---

## Task 4: `ingest_crawl.py` — market 라우터

**Files:**
- Modify: `scripts/ingest_crawl.py` (route_market 구현)
- Target wiki: `wiki/L3_한국시장/market_한국증시_{date}.md`

market/*.md 파일은 증시 스냅샷(코스피/코스닥 지수 + 거래량 순위). 날짜별 파일에 append.

- [ ] **Step 1: route_market 구현 — 기존 placeholder 교체**

```python
def route_market(md_path: Path, date_str: str, state: dict):
    target = WIKI / 'L3_한국시장' / f'market_한국증시_{date_str.replace("-","")}.md'
    text   = md_path.read_text(encoding='utf-8')

    # 파일 없으면 신규 생성 (기존 포맷 유지)
    if not target.exists():
        header = f'# 한국 증시 — {date_str}\n\n'
        append_to_wiki(target, header)

    # 이미 같은 날 데이터 있으면 스킵
    if target.exists() and md_path.stem in target.read_text(encoding='utf-8'):
        state['ingested'].append(f'{date_str}/market/{md_path.name}')
        return

    block = f'\n---\n\n{text}\n\n> 출처: `crawling_bot_data/{date_str}/market/{md_path.name}`\n'
    append_to_wiki(target, block)
    state['ingested'].append(f'{date_str}/market/{md_path.name}')
    save_state(state)
    print(f'  [OK] market → {target.name}')
```

- [ ] **Step 2: 테스트**

```bash
python scripts/ingest_crawl.py --date 2026-06-04 --folder market
```

확인:
```bash
python -c "
from pathlib import Path
p = Path('wiki/L3_한국시장/market_한국증시_20260604.md')
print(p.read_text(encoding='utf-8')[:300])
"
```

Expected: `# 한국 증시 — 2026-06-04` 헤더 + 코스피/코스닥 지수 포함

- [ ] **Step 3: Commit**

```bash
git add scripts/ingest_crawl.py
git commit -m "feat: ingest_crawl — market 라우터 구현 (L3_한국시장)"
```

---

## Task 5: `ingest_crawl.py` — news 라우터

**Files:**
- Modify: `scripts/ingest_crawl.py` (route_news 구현)
- Target wiki: `wiki/L5_섹터/{섹터}/피드_{섹터}.md`

news/*.md 파일은 `키워드: 방산` 등 frontmatter가 있음. 키워드로 섹터 매핑.

- [ ] **Step 1: route_news 구현**

```python
# ingest_crawl.py 최상단 근처에 헬퍼 추가
def get_sector_feed_path(sector: str) -> Path:
    """섹터 피드 파일 경로 반환. 없으면 생성."""
    path = WIKI / 'L5_섹터' / sector / f'피드_{sector}.md'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'# {sector} — 뉴스·리포트 피드\n\n'
            '> crawling_bot_data 자동 수집. 최신순 누적.\n\n',
            encoding='utf-8'
        )
    return path

def extract_frontmatter_value(text: str, key: str) -> str | None:
    """- **key**: value 형식에서 값 추출."""
    m = re.search(rf'-\s*\*\*{re.escape(key)}\*\*\s*:\s*(.+)', text)
    return m.group(1).strip() if m else None

def route_news(md_path: Path, date_str: str, state: dict):
    text    = md_path.read_text(encoding='utf-8')
    rel_key = f'{date_str}/news/{md_path.name}'

    # frontmatter 키워드 우선, 없으면 제목+본문에서 감지
    keyword = extract_frontmatter_value(text, '키워드')
    sector  = keyword_to_sector(keyword or '') or keyword_to_sector(text[:500])

    if not sector:
        print(f'  [미분류] {md_path.name}')
        state['ingested'].append(rel_key)
        return

    # 본문에서 종합 요약 추출 (## 종합 요약 섹션)
    summary_m = re.search(r'## 종합 요약\s*\n+([\s\S]+?)(?=\n##|\Z)', text)
    summary   = summary_m.group(1).strip()[:300] if summary_m else text[:200]

    # 제목 추출 (# 이후 첫 줄)
    title_m = re.search(r'^#\s+(.+)', text, re.MULTILINE)
    title   = title_m.group(1).strip() if title_m else md_path.stem

    block = (
        f'\n---\n\n'
        f'### {date_str} — {title}\n\n'
        f'> {summary}\n\n'
        f'**섹터**: {sector} | **출처**: `crawling_bot_data/{date_str}/news/{md_path.name}`\n'
    )

    target = get_sector_feed_path(sector)
    append_to_wiki(target, block)
    state['ingested'].append(rel_key)
    save_state(state)
    print(f'  [OK] news/{md_path.name} → L5/{sector}/피드_{sector}.md')
```

- [ ] **Step 2: 테스트**

```bash
python scripts/ingest_crawl.py --date 2026-06-04 --folder news
```

확인:
```bash
python -c "
from pathlib import Path
p = Path('wiki/L5_섹터/방산/피드_방산.md')
if p.exists(): print(p.read_text(encoding='utf-8')[:500])
else: print('파일 없음')
"
```

Expected: `### 2026-06-04 — [방산] 오늘의 주요 뉴스 묶음` 섹션 포함

- [ ] **Step 3: Commit**

```bash
git add scripts/ingest_crawl.py wiki/L5_섹터/
git commit -m "feat: ingest_crawl — news 라우터 + 섹터 피드 파일 생성 (L5)"
```

---

## Task 6: `ingest_crawl.py` — reports 라우터

**Files:**
- Modify: `scripts/ingest_crawl.py` (route_reports 구현)
- Target wiki: `wiki/L5_섹터/{섹터}/피드_{섹터}.md`

reports/*.md 파일은 `증권사`, `카테고리` 필드 + PDF AI 요약 섹션 포함 가능.

- [ ] **Step 1: route_reports 구현**

```python
def route_reports(md_path: Path, date_str: str, state: dict):
    text    = md_path.read_text(encoding='utf-8')
    rel_key = f'{date_str}/reports/{md_path.name}'

    # 섹터 감지: 제목 + 본문 첫 500자
    title_m  = re.search(r'^#\s+(.+)', text, re.MULTILINE)
    title    = title_m.group(1).strip() if title_m else md_path.stem
    brokerage = extract_frontmatter_value(text, '증권사') or '증권사 미상'
    sector   = keyword_to_sector(title) or keyword_to_sector(text[:500])

    if not sector:
        print(f'  [미분류] {md_path.name}')
        state['ingested'].append(rel_key)
        return

    # AI 요약 섹션 추출 (pdf_summarize.py가 주입한 섹션)
    ai_summary_m = re.search(r'## 📄 AI 요약\s*\n+([\s\S]+?)(?=\n##|\Z)', text)
    if ai_summary_m:
        summary = ai_summary_m.group(1).strip()[:400]
        summary_label = '📄 AI요약'
    else:
        # AI 요약 없으면 파일 내용 첫 200자
        summary = text[:200].strip()
        summary_label = '원문발췌'

    block = (
        f'\n---\n\n'
        f'### {date_str} — [{brokerage}] {title}\n\n'
        f'> {summary_label}: {summary}\n\n'
        f'**섹터**: {sector} | **출처**: `crawling_bot_data/{date_str}/reports/{md_path.name}`\n'
    )

    target = get_sector_feed_path(sector)
    append_to_wiki(target, block)
    state['ingested'].append(rel_key)
    save_state(state)
    print(f'  [OK] reports/{md_path.name} → L5/{sector}/피드_{sector}.md')
```

- [ ] **Step 2: 테스트 (pdf_summarize 먼저 실행 후)**

```bash
python scripts/pdf_summarize.py --date 2026-06-04
python scripts/ingest_crawl.py --date 2026-06-04 --folder reports
```

확인:
```bash
python -c "
from pathlib import Path
for p in Path('wiki/L5_섹터').rglob('피드_*.md'):
    lines = p.read_text(encoding='utf-8').count('### ')
    print(f'{p.relative_to(\"wiki\")} → {lines}개 항목')
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/ingest_crawl.py
git commit -m "feat: ingest_crawl — reports 라우터 (AI요약 통합, L5 섹터 피드)"
```

---

## Task 7: `ingest_crawl.py` — telegram 라우터

**Files:**
- Modify: `scripts/ingest_crawl.py` (route_telegram 구현)
- Target wiki: `wiki/L6_수급/수급index.md`

telegram/*.md는 채널별 파일 (태린이아빠, 신한리서치 등). 태린이아빠만 L6_수급에 중요 메시지 발췌.

- [ ] **Step 1: route_telegram 구현**

```python
TELEGRAM_ROUTES = {
    '태린이아빠': WIKI / 'L6_수급' / '수급index.md',
}

def route_telegram(md_path: Path, date_str: str, state: dict):
    rel_key = f'{date_str}/telegram/{md_path.name}'
    text    = md_path.read_text(encoding='utf-8')

    # 채널명 감지 (파일명 패턴: YYYY-MM-DD_{채널명}.md)
    channel = md_path.stem.replace(f'{date_str}_', '', 1)
    target  = TELEGRAM_ROUTES.get(channel)

    if target is None:
        print(f'  [미지정채널] {channel} — 스킵')
        state['ingested'].append(rel_key)
        return

    # 시간대별 메시지에서 이미지가 아닌 텍스트만 추출 (최대 3개)
    msg_blocks = re.findall(r'\*\*\d{2}:\d{2}\*\*\s*\n+((?:(?!\*\*\d{2}:\d{2}\*\*|!\[)[\s\S])*)', text)
    msgs = [m.strip() for m in msg_blocks if m.strip() and len(m.strip()) > 10][:3]

    if not msgs:
        print(f'  [텍스트없음] {md_path.name}')
        state['ingested'].append(rel_key)
        return

    excerpts = '\n'.join(f'> {m[:150]}' for m in msgs)
    block = (
        f'\n---\n\n'
        f'### {date_str} — {channel} 핵심 메시지\n\n'
        f'{excerpts}\n\n'
        f'**원본**: `crawling_bot_data/{date_str}/telegram/{md_path.name}`\n'
    )

    append_to_wiki(target, block)
    state['ingested'].append(rel_key)
    save_state(state)
    print(f'  [OK] telegram/{md_path.name} → L6_수급/수급index.md')
```

- [ ] **Step 2: 테스트**

```bash
python scripts/ingest_crawl.py --date 2026-06-04 --folder telegram
```

확인:
```bash
python -c "
from pathlib import Path
p = Path('wiki/L6_수급/수급index.md')
t = p.read_text(encoding='utf-8')
idx = t.find('2026-06-04')
print(t[idx:idx+400] if idx >= 0 else '날짜 항목 없음')
"
```

Expected: `### 2026-06-04 — 태린이아빠 핵심 메시지` 섹션 포함

- [ ] **Step 3: Commit**

```bash
git add scripts/ingest_crawl.py
git commit -m "feat: ingest_crawl — telegram 라우터 (태린이아빠 → L6_수급)"
```

---

## Task 8: `ingest_crawl.py` — blog 라우터

**Files:**
- Modify: `scripts/ingest_crawl.py` (route_blog 구현)
- Target wiki: `wiki/L5_섹터/{섹터}/stock/{종목명}.md`

blog/*.md는 종목 분석 블로그 포스트. 제목에서 종목명 추출 → 섹터 매핑 → stock 파일 업데이트.

- [ ] **Step 1: route_blog 구현**

```python
# 종목명 추출용 패턴 (파일명: YYYY-MM-DD_HHMM_{종목명} {내용}.md)
STOCK_NAME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{4}_([^_\s]+(?:\s+[^_\s]+)?)')

def extract_stock_name_from_filename(filename: str) -> str | None:
    """파일명 앞부분에서 종목명 추출 (날짜_HHMM_ 이후 첫 1~2 단어)."""
    m = STOCK_NAME_RE.match(filename)
    if not m:
        return None
    candidate = m.group(1).strip()
    # 한국어 포함이면 종목명으로 인정
    if re.search(r'[가-힣]', candidate):
        return candidate
    return None

def get_or_create_stock_page(sector: str, stock_name: str) -> Path:
    """stock 페이지 경로 반환. 없으면 기본 구조로 생성."""
    # 종목명에서 파일명 안전 변환 (공백 → 언더스코어)
    safe_name = re.sub(r'[\s/\\:*?"<>|]', '_', stock_name)
    path = WIKI / 'L5_섹터' / sector / 'stock' / f'{safe_name}.md'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'# {stock_name}\n\n'
            f'**섹터**: {sector}\n\n'
            '---\n\n',
            encoding='utf-8'
        )
        print(f'  [NEW] stock 페이지 생성: {path.relative_to(WIKI)}')
    return path

def route_blog(md_path: Path, date_str: str, state: dict):
    text    = md_path.read_text(encoding='utf-8')
    rel_key = f'{date_str}/blog/{md_path.name}'

    # 종목명: 파일명 우선, 없으면 제목에서 추출
    stock_name = extract_stock_name_from_filename(md_path.name)
    if not stock_name:
        title_m    = re.search(r'^#\s+(.+)', text, re.MULTILINE)
        stock_name = title_m.group(1).split()[0] if title_m else None

    if not stock_name:
        print(f'  [종목명미상] {md_path.name}')
        state['ingested'].append(rel_key)
        return

    # 섹터 감지
    sector = keyword_to_sector(stock_name) or keyword_to_sector(text[:500])
    if not sector:
        print(f'  [섹터미상] {stock_name} in {md_path.name}')
        state['ingested'].append(rel_key)
        return

    # 핵심 내용 추출 (파일 첫 200자)
    content_preview = text[:300].strip()

    block = (
        f'\n---\n\n'
        f'### {date_str} — 블로그 분석\n\n'
        f'> {content_preview[:250]}\n\n'
        f'**출처**: `crawling_bot_data/{date_str}/blog/{md_path.name}`\n'
    )

    target = get_or_create_stock_page(sector, stock_name)
    append_to_wiki(target, block)
    state['ingested'].append(rel_key)
    save_state(state)
    print(f'  [OK] blog/{md_path.name} → L5/{sector}/stock/{stock_name}.md')
```

- [ ] **Step 2: 테스트**

```bash
python scripts/ingest_crawl.py --date 2026-06-04 --folder blog
```

확인:
```bash
python -c "
from pathlib import Path
for p in Path('wiki/L5_섹터').rglob('stock/*.md'):
    t = p.read_text(encoding='utf-8')
    if '2026-06-04' in t:
        print(p.relative_to('wiki'), '→ 업데이트됨')
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/ingest_crawl.py wiki/L5_섹터/
git commit -m "feat: ingest_crawl — blog 라우터 (종목명 추출 → stock 페이지 업데이트)"
```

---

## Task 9: log.md 연동 + 전체 통합 실행

**Files:**
- Modify: `scripts/ingest_crawl.py` (main()에 log.md 업데이트 추가)

- [ ] **Step 1: main() 끝에 log.md 업데이트 추가**

```python
# ingest_crawl.py — main() 함수 내 save_state(state) 직후에 추가

LOG_PATH = ROOT / 'wiki' / 'log.md'

def update_log(date_str: str, state: dict, new_ingested_count: int):
    """wiki/log.md에 오늘 ingest 결과 1줄 기록."""
    if not LOG_PATH.exists():
        return
    log_text  = LOG_PATH.read_text(encoding='utf-8')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry     = f'- {timestamp} | crawl_ingest | {date_str} | 신규 {new_ingested_count}개 처리\n'

    # 기존 같은 날짜 항목이 있으면 업데이트, 없으면 맨 위에 추가
    if f'crawl_ingest | {date_str}' in log_text:
        log_text = re.sub(
            rf'.+ crawl_ingest \| {re.escape(date_str)} \| .+\n',
            entry, log_text
        )
    else:
        # 첫 번째 `- ` 항목 앞에 삽입
        log_text = re.sub(r'^(- )', entry + r'\1', log_text, count=1, flags=re.MULTILINE)

    LOG_PATH.write_text(log_text, encoding='utf-8')
```

그리고 `main()` 마지막 부분을 아래로 교체:

```python
# main() 끝부분
    ingested_before = len(state['ingested'])
    
    for folder_name in folders:
        folder_path = base_dir / folder_name
        if not folder_path.exists():
            continue
        process_folder(folder_name, folder_path, date_str, from_hhmm, to_hhmm, state)

    new_count = len(state['ingested']) - ingested_before
    save_state(state)
    update_log(date_str, state, new_count)
    print(f'\n✅ ingest_crawl 완료: {date_str} | 신규 {new_count}개 처리')
```

- [ ] **Step 2: 전체 파이프라인 통합 실행**

```bash
# Pass 1
python scripts/pdf_summarize.py --date 2026-06-04

# Pass 2 전체
python scripts/ingest_crawl.py --date 2026-06-04
```

Expected 최종 출력:
```
[market] 1개 파일
  [OK] market → market_한국증시_20260604.md
[news] N개 파일
  [OK] news/... → L5/방산/피드_방산.md
[reports] N개 파일
  ...
[telegram] N개 파일
  [OK] telegram/... → L6_수급/수급index.md
[blog] N개 파일
  ...
[youtube] 라우터 없음 — 스킵

✅ ingest_crawl 완료: 2026-06-04 | 신규 XX개 처리
```

log.md 확인:
```bash
python -c "
from pathlib import Path
log = Path('wiki/log.md').read_text(encoding='utf-8')
for line in log.splitlines()[:5]:
    print(line)
"
```

- [ ] **Step 3: 최종 Commit + Push**

```bash
git add scripts/ingest_crawl.py wiki/
git commit -m "feat: ingest_crawl 파이프라인 완성 — market/news/reports/telegram/blog 라우터 + log.md 연동"
git push
```

---

## 실행 참조

### 일반 사용
```bash
# 오늘 전체
python scripts/pdf_summarize.py && python scripts/ingest_crawl.py

# 특정 날짜
python scripts/pdf_summarize.py --date 2026-06-03
python scripts/ingest_crawl.py --date 2026-06-03

# 오전 데이터만 (00:00~12:00)
python scripts/ingest_crawl.py --date 2026-06-04 --from 0000 --to 1200

# news만 처리
python scripts/ingest_crawl.py --date 2026-06-04 --folder news
```

### state.json 리셋 (재처리)
```bash
python -c "
import json
from pathlib import Path
p = Path('pipeline/crawl_ingest_state.json')
d = json.loads(p.read_text())
d['ingested'] = []  # 또는 d['pdf_summarized'] = []
p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print('리셋 완료')
"
```
