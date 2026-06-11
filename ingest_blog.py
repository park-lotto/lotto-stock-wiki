#!/usr/bin/env python3
"""
ingest_blog.py — 블로그 분석 → db/blog_insights.json

블로그는 증권사 TP가 아닌 '왜·다음' 인사이트 중심으로 저장.
기준: 구체적 수치 + 명확한 투자 논리가 있는 것만.

사용:
  python ingest_blog.py                      # 오늘
  python ingest_blog.py --date 2026-06-05    # 특정 날짜
  python ingest_blog.py --dry                # 미리보기
"""

import sys, os, json, re, argparse
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')

BASE      = Path(__file__).parent
DB_FILE   = BASE / "db" / "blog_insights.json"
CRAWL_BOT = Path(r"C:\Users\TheRose\crawling_bot_data")

PROMPT = """\
다음은 투자 블로그 포스팅이다.
구체적 수치와 명확한 투자 논리가 있는 경우에만 JSON으로 추출해라.
단순 종목 소개·뉴스 요약·ETF 가이드는 제외하고 [] 반환.

---
{content}
---

JSON 배열만 출력:
[
  {{
    "sector": "반도체|바이오|로봇|전력|조선|방산|엔터|AI소프트웨어|2차전지|통신|소재|자동차|기타",
    "ticker_name": "핵심 종목명 (없으면 null)",
    "title": "20자 이내 핵심 주제",
    "key_claims": ["핵심 주장 1문장", "핵심 주장 1문장"],
    "data_points": ["구체적 수치나 사실 1개", "구체적 수치나 사실 1개"],
    "implication": "투자 시사점 2~3줄",
    "signal": "강세|약세|중립",
    "time_horizon": "단기|중기|장기"
  }}
]

기준:
- key_claims: 블로거의 독자적 주장 (인과관계·전망 포함)
- data_points: PER·성장률·수주금액 같은 구체적 수치
- 수치 없고 주장만 있으면 제외
- 없으면 []
"""

def get_gemini():
    from google import genai
    env = BASE / '.env'
    cfg = {}
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    api_key = cfg.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
    return genai.Client(api_key=api_key)

def load_db():
    DB_FILE.parent.mkdir(exist_ok=True)
    if not DB_FILE.exists():
        return {"records": []}
    return json.loads(DB_FILE.read_text(encoding='utf-8'))

def save_db(db):
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')

def extract_json(raw):
    raw = re.sub(r'```json\s*', '', raw).strip()
    raw = re.sub(r'```', '', raw).strip()
    m = re.search(r'\[[\s\S]*\]', raw)
    return m.group(0) if m else '[]'

def make_id(date_str, sector, name, existing_ids):
    sector = sector or '기타'
    name   = name or 'blog'
    slug   = re.sub(r'[^\w가-힣]', '', f"{date_str.replace('-','')}blog_{sector[:4]}_{name[:6]}")
    for i in range(1, 200):
        uid = f"{slug}_{i:03d}"
        if uid not in existing_ids:
            return uid
    return f"{slug}_999"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=date.today().strftime('%Y-%m-%d'))
    ap.add_argument('--dry',  action='store_true')
    args = ap.parse_args()

    date_str = args.date
    blog_dir = CRAWL_BOT / date_str / "blog"

    if not blog_dir.exists():
        print(f"블로그 폴더 없음: {blog_dir}")
        return

    files = sorted(blog_dir.glob("*.md"))
    print(f"\n{'='*40}\n ingest_blog — {date_str} ({len(files)}개)\n{'='*40}")

    db           = load_db()
    existing_ids = {r['id'] for r in db.get('records', [])}
    new_records  = []
    client       = get_gemini()

    for f in files:
        content = f.read_text(encoding='utf-8', errors='replace')
        fname   = f.stem[12:] if len(f.stem) > 12 else f.stem  # 날짜+시간 제거
        print(f"  {fname[:45]} ...", end=' ')

        try:
            prompt = PROMPT.replace('{content}', content[:4000])
            resp   = client.models.generate_content(model='gemini-3-flash-preview', contents=prompt)
            items  = json.loads(extract_json(resp.text))
        except Exception as e:
            print(f"오류({e})")
            continue

        if not items:
            print("스킵")
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            uid = make_id(date_str, item.get('sector'), item.get('ticker_name'), existing_ids)
            existing_ids.add(uid)
            new_records.append({
                'id':           uid,
                'date':         date_str,
                'file':         f.name,
                'sector':       item.get('sector') or '기타',
                'ticker_name':  item.get('ticker_name'),
                'title':        item.get('title') or '',
                'key_claims':   item.get('key_claims') or [],
                'data_points':  item.get('data_points') or [],
                'implication':  item.get('implication') or '',
                'signal':       item.get('signal') or '중립',
                'time_horizon': item.get('time_horizon') or '중기',
                'user_comment': ''
            })

        print(f"{len(items)}건")

    if not new_records:
        print("\n추출된 레코드 없음")
        return

    # 정렬: 섹터별, signal 강세 우선
    sig_order = {'강세': 0, '중립': 1, '약세': 2}
    new_records.sort(key=lambda r: (r['sector'], sig_order.get(r['signal'], 1)))

    print(f"\n[ 블로그 인사이트 — {len(new_records)}건 ]\n")
    for r in new_records:
        sig  = {'강세': '🔴', '약세': '🔵', '중립': '⬜'}.get(r['signal'], '  ')
        hor  = {'단기': '⚡', '중기': '📅', '장기': '🔭'}.get(r['time_horizon'], '')
        name = r['ticker_name'] or ''
        print(f"  {sig}{hor} [{r['sector']}] {name} — {r['title']}")
        for c in r['key_claims'][:2]:
            print(f"      • {c}")
        for d in r['data_points'][:2]:
            print(f"      📊 {d}")
        print()

    if args.dry:
        print("--dry 모드: 저장 안 함")
        return

    db.setdefault('records', []).extend(new_records)
    save_db(db)
    print(f"✅ db/blog_insights.json에 {len(new_records)}건 저장")

if __name__ == '__main__':
    main()
