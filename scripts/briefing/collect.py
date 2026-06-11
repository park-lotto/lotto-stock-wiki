"""
collect.py — wiki L5_섹터에서 오늘 핵심 이슈 3~5개 추출

사용:
  python scripts/briefing/collect.py
  python scripts/briefing/collect.py --date 2026-06-06
"""
import sys, io, json, argparse
from datetime import date
from pathlib import Path
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT       = Path(__file__).parent.parent.parent
WIKI_L5    = ROOT / 'wiki' / 'L5_섹터'
STATE_PATH = ROOT / 'pipeline' / 'briefing_state.json'

# ── env ───────────────────────────────────────────────────────────────────────
env = {}
for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

client = genai.Client(api_key=env['GEMINI_API_KEY'])

def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding='utf-8'))

def save_state(s: dict):
    STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')

def _find_sector_index(sector_dir: Path) -> Path | None:
    """섹터 디렉터리에서 인덱스 파일 탐색.
    우선순위: sector_{name}.md → {name}index.md → *index.md → sector_*.md
    """
    # 1순위: sector_{name}.md
    primary = sector_dir / f'sector_{sector_dir.name}.md'
    if primary.exists():
        return primary
    # 2순위: {name}index.md
    index_md = sector_dir / f'{sector_dir.name}index.md'
    if index_md.exists():
        return index_md
    # 3순위: *index.md 패턴
    for p in sector_dir.glob('*index.md'):
        return p
    # 4순위: sector_*.md
    for p in sector_dir.glob('sector_*.md'):
        return p
    return None

def gather_recent_wiki(target_date: str) -> str:
    """오늘 날짜가 포함된 섹터 index 파일들의 최근 내용 수집"""
    chunks = []
    for sector_dir in sorted(WIKI_L5.iterdir()):
        if not sector_dir.is_dir():
            continue
        idx = _find_sector_index(sector_dir)
        if idx is None:
            continue
        lines = idx.read_text(encoding='utf-8').splitlines()
        relevant = []
        for i, line in enumerate(lines):
            if target_date in line:
                start = max(0, i - 2)
                end = min(len(lines), i + 50)
                relevant.extend(lines[start:end])
                break
        if relevant:
            chunks.append(f"### {sector_dir.name}\n" + '\n'.join(relevant[:80]))
    return '\n\n'.join(chunks[:8])

def extract_issues(wiki_text: str, target_date: str) -> list[dict]:
    """Gemini Flash로 오늘 핵심 이슈 3~5개 추출"""
    prompt = f"""아래는 {target_date} 기준 주식 섹터 위키 내용이다.

{wiki_text}

위 내용에서 오늘({target_date}) 가장 중요한 핵심 이슈 3~5개를 추출하라.
각 이슈는 반드시 JSON 배열로 반환하라:
[
  {{
    "sector": "반도체",
    "headline": "브로드컴 쇼크 여파 + 피에스케이 상한가",
    "story": "어젯밤 브로드컴이 네트워크 부문 부진으로 -11.8% 급락했어요. 근데 AI 가이던스는 오히려 올렸고, 피에스케이는 상한가를 쳤어요. 시장이 엇갈린 신호를 보내고 있어요.",
    "numbers": "브로드컴 -11.8% / AI가이던스 +8% / 피에스케이 +29.9%",
    "pivot_a": "일시 조정 — AI 방향은 살아있다",
    "pivot_b": "추세 전환 — 네트워크 부진이 구조적"
  }}
]
- headline: 이슈 핵심 1줄 (30자 이내)
- story: 운영자가 읽고 판단할 수 있도록 맥락을 2~3줄 구어체로 설명. "~했어요" 말투.
- numbers: 핵심 수치 3개 이내, "종목 수치% / 종목 수치%" 형식. 없으면 빈 문자열.
- pivot_a: 강세/낙관 판단 시나리오 (15자 이내)
- pivot_b: 약세/주의 판단 시나리오 (15자 이내)
JSON만 반환, 다른 텍스트 없이."""

    resp = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt,
    )
    text = resp.text.strip()
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
    return json.loads(text.strip())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=str(date.today()))
    args = parser.parse_args()
    target_date = args.date

    print(f"[collect] {target_date} 이슈 추출 시작")
    wiki_text = gather_recent_wiki(target_date)
    if not wiki_text:
        print("[collect] 오늘 데이터 없음 — ingest 먼저 실행 필요")
        sys.exit(1)

    issues = extract_issues(wiki_text, target_date)
    print(f"[collect] 추출된 이슈 {len(issues)}개: {[i['sector'] for i in issues]}")

    state = load_state()
    state['date'] = target_date
    state['issues'] = issues
    state['stage'] = 'collected'
    save_state(state)
    print(f"[collect] 상태 저장 완료 → {STATE_PATH}")

if __name__ == '__main__':
    main()
