#!/usr/bin/env python3
"""
analyze_blog.py — 블로그 원본 파일 Gemini 요약 + 유형 분류
"""
import sys, os, json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE      = Path(__file__).parent
BLOG_DIR  = Path(r"C:\Users\TheRose\crawling_bot_data\2026-06-05\blog")
OUT_FILE  = BASE / "raw" / "blog" / "2026-06-05_blog_analysis.json"

PROMPT = """\
다음은 투자 관련 블로그 포스팅이다. 아래 JSON 형식으로만 답해라.

---
{content}
---

{{
  "type": "증권사리포트인용|개인분석|테마정리|시황브리핑|기타",
  "broker_cited": "인용한 증권사명 또는 null",
  "ticker_name": "핵심 종목명 또는 null",
  "sector": "반도체|바이오|로봇|전력|조선|방산|엔터|AI소프트웨어|2차전지|통신|소재|자동차|기타",
  "signal": "강세|약세|중립",
  "key_point": "핵심 내용 1~2줄 (수치 포함)",
  "insight_value": "높음|보통|낮음"
}}

판단 기준:
- type: 증권사 리포트를 직접 인용하면 '증권사리포트인용', 개인이 독자적으로 분석하면 '개인분석', 관련주 목록이면 '테마정리'
- insight_value: 증권사 인용+구체적 수치 있으면 '높음', 개인분석이지만 논리적이면 '보통', 단순 정리면 '낮음'
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

def extract_json(raw):
    import re
    raw = raw.strip()
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```', '', raw)
    m = re.search(r'\{[\s\S]*\}', raw)
    return m.group(0) if m else '{}'

def main():
    files = sorted(BLOG_DIR.glob("*.md"))
    print(f"총 {len(files)}개 파일 처리\n")

    client  = get_gemini()
    results = []

    for f in files:
        fname   = f.name
        content = f.read_text(encoding='utf-8', errors='replace')[:3000]
        print(f"  {fname[:50]} ...", end=' ')

        try:
            prompt = PROMPT.replace('{content}', content)
            resp   = client.models.generate_content(model='gemini-3-flash-preview', contents=prompt)
            data   = json.loads(extract_json(resp.text))
            data['file'] = fname
            results.append(data)
            print(f"[{data.get('type','?')}] {data.get('insight_value','?')} — {data.get('ticker_name','')}")
        except Exception as e:
            print(f"오류: {e}")
            results.append({'file': fname, 'type': '오류', 'insight_value': '낮음'})

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n저장: {OUT_FILE}")

    # 유형별 집계
    from collections import Counter
    types  = Counter(r.get('type') for r in results)
    values = Counter(r.get('insight_value') for r in results)
    print("\n[ 유형별 ]")
    for t, c in types.most_common():
        print(f"  {t}: {c}건")
    print("\n[ 인사이트 가치 ]")
    for v, c in values.most_common():
        print(f"  {v}: {c}건")

    print("\n[ 높음 목록 ]")
    for r in results:
        if r.get('insight_value') == '높음':
            print(f"  [{r.get('sector')}] {r.get('ticker_name')} — {r.get('key_point','')[:60]}")

if __name__ == '__main__':
    main()
