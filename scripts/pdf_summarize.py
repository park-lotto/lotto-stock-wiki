"""
pdf_summarize.py — reports/*.md PDF 링크 → Gemini 2.0 Flash 요약 → .md 주입 (Pass 1)

사용:
  python scripts/pdf_summarize.py --date 2026-06-04
  python scripts/pdf_summarize.py             # 오늘 날짜 자동
  python scripts/pdf_summarize.py --limit 3   # 최대 3개만 처리 (테스트용)
"""
import sys, io, re, json, argparse, requests
from datetime import date
from pathlib import Path
from google import genai
from google.genai import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT       = Path(__file__).parent.parent
ENV        = ROOT / '.env'
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
def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    return {'pdf_summarized': [], 'ingested': [], 'last_run': None}

def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

# ── PDF 링크 추출 ──────────────────────────────────────────────────────────────
PDF_RE = re.compile(r'\[다운로드\]\((https?://[^\)]+\.pdf[^\)]*)\)', re.IGNORECASE)

def extract_pdf_url(md_text: str) -> str | None:
    m = PDF_RE.search(md_text)
    return m.group(1) if m else None

# ── PDF 다운로드 ───────────────────────────────────────────────────────────────
def download_pdf(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        r.raise_for_status()
        if len(r.content) < 1000:
            print(f'  PDF 너무 작음 ({len(r.content)}bytes) — 다운로드 실패 가능성')
            return None
        return r.content
    except Exception as e:
        print(f'  PDF 다운로드 실패: {e}')
        return None

# ── Gemini 요약 ────────────────────────────────────────────────────────────────
SUMMARY_PROMPT = """이 증권사 리포트 PDF를 아래 형식으로 한국어로 요약해줘.

**핵심 주장 (1줄)**:
**주요 내용 (3줄 이내)**:
-
**언급 종목/섹터**:
**투자 시사점**: """

def summarize_with_gemini(pdf_bytes: bytes, filename: str) -> str | None:
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Content(role='user', parts=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'),
                    types.Part(text=SUMMARY_PROMPT)
                ])
            ]
        )
        return response.text.strip()
    except Exception as e:
        print(f'  Gemini 요약 실패 ({filename}): {e}')
        return None

# ── .md 파일에 요약 주입 ────────────────────────────────────────────────────────
ALREADY_SUMMARIZED = '## 📄 AI 요약'

def inject_summary(md_path: Path, summary: str) -> bool:
    """기존 .md 파일 끝에 AI 요약 섹션 추가. 이미 있으면 스킵 → False 반환."""
    text = md_path.read_text(encoding='utf-8')
    if ALREADY_SUMMARIZED in text:
        return False
    block = f'\n\n{ALREADY_SUMMARIZED}\n\n{summary}\n'
    md_path.write_text(text + block, encoding='utf-8')
    return True

# ── 날짜 처리 메인 ─────────────────────────────────────────────────────────────
def process_date(date_str: str, limit: int = 0):
    state      = load_state()
    reports_dir = CRAWL_BASE / date_str / 'reports'

    if not reports_dir.exists():
        print(f'reports 폴더 없음: {reports_dir}')
        return

    md_files = sorted(reports_dir.glob('*.md'))
    print(f'reports/ 파일 {len(md_files)}개 발견')

    processed = 0
    for md_path in md_files:
        if limit and processed >= limit:
            print(f'  [LIMIT] {limit}개 처리 완료 → 중단')
            break

        rel_key = f'{date_str}/reports/{md_path.name}'

        # 이미 처리된 파일 스킵
        if rel_key in state['pdf_summarized']:
            print(f'  [SKIP] {md_path.name}')
            continue

        text = md_path.read_text(encoding='utf-8')

        # 이미 요약 섹션 있으면 state에만 기록
        if ALREADY_SUMMARIZED in text:
            state['pdf_summarized'].append(rel_key)
            continue

        # PDF 링크 없으면 완료 처리
        pdf_url = extract_pdf_url(text)
        if not pdf_url:
            print(f'  [NO PDF] {md_path.name}')
            state['pdf_summarized'].append(rel_key)
            continue

        print(f'  [처리중] {md_path.name}')
        print(f'    URL: {pdf_url[:80]}...')

        pdf_bytes = download_pdf(pdf_url)
        if not pdf_bytes:
            continue

        print(f'    PDF {len(pdf_bytes)//1024}KB 다운로드 완료')

        summary = summarize_with_gemini(pdf_bytes, md_path.name)
        if not summary:
            continue

        injected = inject_summary(md_path, summary)
        if injected:
            print(f'  [✅ OK] 요약 주입 완료: {md_path.name}')
            state['pdf_summarized'].append(rel_key)
            save_state(state)
            processed += 1

    print(f'\npdf_summarize 완료: {date_str} | {processed}개 신규 처리')

# ── argparse ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='reports PDF → Gemini 요약 → .md 주입')
    parser.add_argument('--date',  default=date.today().strftime('%Y-%m-%d'),
                        help='처리 날짜 (기본: 오늘)')
    parser.add_argument('--limit', type=int, default=0,
                        help='최대 처리 개수 (0=무제한, 테스트용)')
    args = parser.parse_args()
    process_date(args.date, args.limit)

if __name__ == '__main__':
    main()
