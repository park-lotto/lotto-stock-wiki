"""
유튜브 영상 → Gemini API 직접 분석 (샘플 테스트)
- Gemini가 유튜브 URL을 영상으로 직접 읽음 (다운로드 불필요)
- 자막/내용 요약 + 메타데이터를 crawling_bot_data 폴더에 저장

사용:
  python scripts/yt_gemini_fetch.py "https://www.youtube.com/watch?v=XXXX"
  python scripts/yt_gemini_fetch.py "URL" --date 2026-06-21
"""
import sys, os, io, json, argparse
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
ENV = ROOT / '.env'
SAVE_BASE = Path(r"C:\Users\TheRose\crawling_bot_data")

env = {}
if ENV.exists():
    for line in ENV.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

API_KEY = env.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
if not API_KEY:
    print('❌ GEMINI_API_KEY 없음'); sys.exit(1)

PROMPT = """이 유튜브 영상을 분석해서 아래 형식의 JSON으로만 답해줘. 다른 말 없이 JSON만.
{
  "title": "영상 제목(추정)",
  "channel": "채널명(추정, 모르면 빈칸)",
  "summary": "3~5문장 핵심 요약",
  "stocks": ["언급된 종목명들"],
  "sectors": ["언급된 섹터들"],
  "key_points": ["핵심 포인트 5개 이내"],
  "transcript_excerpt": "도입부 자막/발화 200자 발췌"
}
한국 주식 영상이면 종목/섹터를 정확히 뽑아줘."""


def fetch_yt(url: str, model: str = 'gemini-2.5-flash') -> dict:
    import time
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=API_KEY)
    print(f"🎬 Gemini 영상 분석 시작 (모델: {model})")

    contents = types.Content(parts=[
        types.Part(file_data=types.FileData(file_uri=url, mime_type="video/*")),
        types.Part(text=PROMPT),
    ])
    cfg = types.GenerateContentConfig(temperature=0.2)

    resp = None
    for attempt in range(5):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)
            break
        except genai_errors.ServerError as e:
            wait = 10 * (attempt + 1)
            print(f"  ⚠️ 503/서버혼잡 — {wait}초 후 재시도 ({attempt+1}/5)")
            time.sleep(wait)
    if resp is None:
        raise RuntimeError("5회 재시도 후에도 서버 응답 실패")

    text = resp.text.strip()
    # 코드블록 제거
    import re
    text = re.sub(r'```(?:json)?\s*', '', text).strip('`').strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]+\}', text)
        if m:
            return json.loads(m.group())
        return {"raw": text}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('url', help='유튜브 영상 URL')
    p.add_argument('--date', default=date.today().strftime('%Y-%m-%d'))
    args = p.parse_args()

    data = fetch_yt(args.url)
    data['_source_url'] = args.url

    save_dir = SAVE_BASE / args.date / 'yt'
    save_dir.mkdir(parents=True, exist_ok=True)

    # 파일명: 영상ID 추출
    import re
    vid = re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]{11})', args.url)
    vid = vid.group(1) if vid else 'unknown'
    out_path = save_dir / f"yt_{vid}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n✅ 저장 완료: {out_path}")
    print(f"📌 제목: {data.get('title','?')}")
    print(f"📌 종목: {data.get('stocks',[])}")
    print(f"📌 요약: {data.get('summary','')[:120]}")
    return out_path


if __name__ == '__main__':
    main()
