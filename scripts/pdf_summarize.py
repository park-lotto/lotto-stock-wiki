"""
pdf_summarize.py — reports/*.md PDF 링크 → Gemini 요약 → reports_summarized/ 저장 (Pass 1)

원본 파일은 수정하지 않음.
결과: crawling_bot_data/{date}/reports_summarized/{원본파일명}.md
       = 원본 내용 + ## 📄 AI 요약 섹션

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
SUMMARY_PROMPT = """이 증권사 리포트 PDF를 아래 형식으로 한국어로 정리해줘.
반드시 실제 수치, 날짜, 종목명, 퍼센트를 그대로 포함해. 추상적인 표현 금지.

📄 {증권사명}
👤 작성자: {애널리스트 이름 — PDF에서 추출, 없으면 생략}
📅 발행일: {YYYY-MM-DD 형식}
📄 페이지 수: p. {총 페이지 수}

개요
{리포트 전체 핵심을 하나의 문단으로. 핵심 주장 + 주요 근거 수치 + 결론 포함. 3~5문장. 구체적 숫자 필수.}

주요 내용
{PDF의 실제 섹션/챕터 제목을 번호와 함께 그대로 사용. 각 섹션 아래 핵심 데이터 bullet로 정리.
- 수치가 있으면 수치 그대로 기재
- 그래프/표가 있으면 그 내용 해석해서 포함
- 각 섹션 최소 3개 이상 bullet}"""

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

# ── 별도 폴더에 요약 파일 저장 ─────────────────────────────────────────────────
ALREADY_SUMMARIZED = '## 📄 AI 요약'
def save_summarized(md_path: Path, out_dir: Path, summary: str) -> bool:
    """원본 내용 + AI 요약 섹션을 out_dir/{원본파일명}.md 로 저장.
    이미 출력 파일이 있으면 스킵 → False 반환."""
    out_path = out_dir / md_path.name
    if out_path.exists():
        return False
    original = md_path.read_text(encoding='utf-8')
    block = f'\n\n{ALREADY_SUMMARIZED}\n\n{summary}\n'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(original + block, encoding='utf-8')
    return True

# ── 날짜 처리 메인 ─────────────────────────────────────────────────────────────
def process_date(date_str: str, limit: int = 0):
    state       = load_state()
    reports_dir = CRAWL_BASE / date_str / 'reports'
    out_dir     = ROOT / 'raw' / 'report' / date_str

    if not reports_dir.exists():
        print(f'reports 폴더 없음: {reports_dir}')
        return

    md_files = sorted(reports_dir.glob('*.md'))
    print(f'reports/ 파일 {len(md_files)}개 발견  →  저장: raw/report/{date_str}/')

    processed = 0
    for md_path in md_files:
        if limit and processed >= limit:
            print(f'  [LIMIT] {limit}개 처리 완료 → 중단')
            break

        rel_key = f'{date_str}/reports/{md_path.name}'

        # state.json에 이미 기록된 파일 스킵
        if rel_key in state['pdf_summarized']:
            print(f'  [SKIP] {md_path.name}')
            continue

        # 출력 파일이 이미 존재하면 state에만 기록
        if (out_dir / md_path.name).exists():
            state['pdf_summarized'].append(rel_key)
            continue

        # PDF 링크 없으면 완료 처리
        text    = md_path.read_text(encoding='utf-8')
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

        saved = save_summarized(md_path, out_dir, summary)
        if saved:
            print(f'  [✅ OK] raw/report/{date_str}/{md_path.name}')
            state['pdf_summarized'].append(rel_key)
            save_state(state)
            processed += 1

    print(f'\npdf_summarize 완료: {date_str} | {processed}개 신규 처리')

# ── argparse ──────────────────────────────────────────────────────────────────
def process_one(date_str: str, keyword: str):
    """파일명에 keyword가 포함된 파일 1개만 처리."""
    state       = load_state()
    reports_dir = CRAWL_BASE / date_str / 'reports'
    out_dir     = ROOT / 'raw' / 'report' / date_str

    matches = [p for p in reports_dir.glob('*.md') if keyword in p.name]
    if not matches:
        print(f'파일 없음: "{keyword}" 포함된 파일이 reports/에 없음'); return
    if len(matches) > 1:
        print(f'여러 개 매칭됨:')
        for m in matches: print(f'  {m.name}')
        print('더 구체적인 키워드를 사용하세요'); return

    md_path = matches[0]
    rel_key = f'{date_str}/reports/{md_path.name}'
    print(f'대상: {md_path.name}')

    if (out_dir / md_path.name).exists():
        print(f'이미 요약됨: raw/report/{date_str}/{md_path.name}'); return

    text    = md_path.read_text(encoding='utf-8')
    pdf_url = extract_pdf_url(text)
    if not pdf_url:
        print('PDF 링크 없음'); return

    print(f'PDF URL: {pdf_url[:80]}...')
    pdf_bytes = download_pdf(pdf_url)
    if not pdf_bytes: return

    print(f'PDF {len(pdf_bytes)//1024}KB 다운로드 완료')
    summary = summarize_with_gemini(pdf_bytes, md_path.name)
    if not summary: return

    save_summarized(md_path, out_dir, summary)
    state['pdf_summarized'].append(rel_key)
    save_state(state)
    print(f'[✅ OK] raw/report/{date_str}/{md_path.name}')

def main():
    parser = argparse.ArgumentParser(description='reports PDF → Gemini 요약 → raw/report/ 저장')
    parser.add_argument('--date',  default=date.today().strftime('%Y-%m-%d'),
                        help='처리 날짜 (기본: 오늘)')
    parser.add_argument('--limit', type=int, default=0,
                        help='최대 처리 개수 (0=무제한)')
    parser.add_argument('--file',  default=None,
                        help='파일명 키워드로 1개 지정 (예: --file "국내 시총")')
    args = parser.parse_args()

    if args.file:
        process_one(args.date, args.file)
    else:
        process_date(args.date, args.limit)

if __name__ == '__main__':
    main()
