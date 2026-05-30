"""
핫클립 수집기 — Gemini Google Search grounding
주식 유튜브에서 최근 7일 터진 영상 찾아서 content_bank.md에 저장

사용법:
  .venv\Scripts\python.exe scripts/crawl_hot_clips.py
  .venv\Scripts\python.exe scripts/crawl_hot_clips.py --top 10   # 상위 N개만
"""
import sys, json, re, argparse
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).parent.parent

CONTENT_BANK = ROOT / 'channel' / 'yt' / 'content_bank.md'

# ── Gemini 클라이언트 ────────────────────────────────────────────────
sys.path.insert(0, str(ROOT))
from scripts.yt_agents.gemini_client import search, call_json

# ── 6개 공식 기준 (content_bank 점수 기준) ──────────────────────────
PATTERNS = {
    '숫자_충격':  r'\d+[배만억%천]|[+\-]\d+%|\d+만원|\d+개',
    '시간_압박':  r'지금|오늘|내일|이번주|다음주|6월|7월|임박|마감|긴급|속보',
    '행동_촉구':  r'사세요|모으세요|하세요|보세요|주목|담아|잡아|노려|시작하',
    '대형종목':   r'삼성|하이닉스|카카오|네이버|현대|기아|LG|SK|셀트리온|코스피|코스닥',
    '과장_표현':  r'미친|폭발|대박|미쳤|난리|충격|경악|역대급|사상|압도|깜짝',
    '비밀_공개':  r'기관|외국인|세력|내부|공개|비밀|몰랐던|숨겨진|모르면|알아야',
}

SEARCH_QUERIES = [
    "주식 유튜브 조회수 급상승 최근 2026 site:youtube.com",
    "한국 주식 경제 유튜브 핫클립 최신 조회수 많은",
    "주식 유튜브 바이럴 영상 2026년 5월 6월",
    "코스피 코스닥 유튜브 화제 영상 최신",
    "수급 종목분석 유튜브 인기 최근 조회수",
]

EXTRACT_SYSTEM = """유튜브 영상 정보를 아래 JSON 배열로 추출하세요.
title(제목), url(URL 또는 빈문자열), views(조회수 숫자, 모르면 0), channel(채널명) 추출.
주식·경제·재테크 관련 영상만 포함. 최대 8개.
반드시 JSON 배열만 반환:
[{"title":"...", "url":"...", "views":0, "channel":"..."}]
"""

def score_title(title: str) -> tuple[int, list[str]]:
    """제목으로 6개 공식 점수 계산"""
    matched = []
    for name, pattern in PATTERNS.items():
        if re.search(pattern, title):
            matched.append(name)
    return len(matched), matched

def fetch_hot_clips(top: int = 15) -> list[dict]:
    """Gemini Google Search로 핫클립 수집"""
    all_videos = []
    seen_titles = set()

    for i, query in enumerate(SEARCH_QUERIES):
        print(f"  🔍 검색 {i+1}/{len(SEARCH_QUERIES)}: {query[:40]}...")
        try:
            raw = search(query)
            videos = call_json(
                f"검색 결과:\n{raw[:3000]}\n\n위에서 유튜브 영상 정보를 추출하세요.",
                EXTRACT_SYSTEM
            )
            if isinstance(videos, list):
                for v in videos:
                    title = v.get('title', '').strip()
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        score, patterns = score_title(title)
                        all_videos.append({
                            'title':    title,
                            'url':      v.get('url', ''),
                            'views':    v.get('views', 0),
                            'channel':  v.get('channel', ''),
                            'score':    score,
                            'patterns': patterns,
                        })
        except Exception as e:
            print(f"    ⚠️ 실패: {e}")

    # 점수 → 조회수 순 정렬
    all_videos.sort(key=lambda x: (x['score'], x['views']), reverse=True)
    return all_videos[:top]

def format_entry(v: dict) -> str:
    """content_bank.md 한 줄 포맷"""
    url_part  = f"[{v['title']}]({v['url']})" if v['url'] else v['title']
    views_str = f"{v['views']:,}" if v['views'] else '?'
    pat_str   = ','.join(v['patterns']) if v['patterns'] else ''
    return f"- **[{v['score']}/6]** {url_part}  조회수:{views_str} | 패턴:{pat_str}"

def save_to_bank(videos: list[dict]):
    """content_bank.md 상단에 오늘 수집분 추가"""
    today = datetime.now().strftime('%Y-%m-%d')
    header = f"\n## {today} 신규 소재 발굴\n"
    lines  = [header]
    for v in videos:
        lines.append(format_entry(v))
    lines.append('')

    new_block = '\n'.join(lines)

    existing = CONTENT_BANK.read_text(encoding='utf-8') if CONTENT_BANK.exists() else ''
    # 오늘 날짜 블록이 이미 있으면 교체, 없으면 맨 앞에 추가
    if f"## {today}" in existing:
        existing = re.sub(
            rf'## {today} 신규 소재 발굴\n.*?(?=\n## |\Z)',
            new_block.strip(),
            existing, flags=re.DOTALL
        )
        CONTENT_BANK.write_text(existing, encoding='utf-8')
    else:
        CONTENT_BANK.write_text(new_block + existing, encoding='utf-8')

    print(f"\n✅ content_bank.md 저장 완료 ({len(videos)}개)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top', type=int, default=15, help='수집 영상 수 (기본 15)')
    args = parser.parse_args()

    print("🎬 핫클립 수집 시작...")
    videos = fetch_hot_clips(top=args.top)

    print(f"\n{'─'*60}")
    print(f"  수집 결과 ({len(videos)}개)")
    print(f"{'─'*60}")
    for v in videos:
        print(f"  [{v['score']}/6] {v['title'][:50]}")
        if v['patterns']:
            print(f"         패턴: {', '.join(v['patterns'])}")

    save_to_bank(videos)
    print(f"\n→ {CONTENT_BANK}")

if __name__ == '__main__':
    main()
