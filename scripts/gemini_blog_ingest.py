"""
블로그 파일 Gemini 분석 → 위키 인제스트용 요약 생성
"""
import os
import json
from pathlib import Path
from google import genai
from google.genai import types

# API 키
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

BLOG_DIR = Path(r"C:\Users\TheRose\crawling_bot_data\2026-06-09\blog")

PROMPT_TEMPLATE = """
아래는 2026년 6월 9일 수집된 주식 블로그 포스팅입니다.
각 파일을 분석해서 **위키 인제스트용 구조화된 요약**을 만들어주세요.

=== 파일 목록 ===
{files_content}

=== 출력 형식 (JSON 배열) ===
각 파일마다 아래 구조로 출력:
{{
  "filename": "파일명",
  "skip": true/false,  // 와이즈클럽 후기 등 노이즈면 true
  "sector": "반도체|조선|방산|바이오|소비재|전력|로봇|통신|시장전체|개인일기",
  "type": "종목분석|섹터분석|시황|리포트|개인의견",
  "stocks": ["종목명1", "종목명2"],  // 핵심 종목
  "wiki_level": "L5" or "L6",  // 섹터=L5, 종목=L6
  "key_insights": [
    "수치·날짜 포함한 구체적 인사이트 1줄",
    "두 번째 인사이트"
  ],
  "structural_facts": [
    "TP변경·수주계약·실적 등 구조적 사실만"
  ],
  "skip_reason": "노이즈인 경우 이유"
}}

=== 인제스트 제외 기준 ===
- 당일 주가 등락%만 있는 글 → skip: true
- 개인 일기/감성글 → skip: true
- 광고성 후기 (와이즈클럽 등) → skip: true
- 수치 없는 막연한 전망 → skip: true

=== 포함 기준 ===
- TP 변경, 수주/계약, 실적 숫자 포함
- 구조적 섹터 방향성 변화
- 수급 빈집 포착
- 일정·트리거 이벤트

JSON 배열만 출력. 마크다운 코드블록 없이.
"""


def read_blog_files():
    files = sorted(BLOG_DIR.glob("*.md"))
    contents = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except:
            text = f.read_text(encoding="cp949", errors="ignore")
        contents.append({
            "filename": f.name,
            "content": text[:2000]  # 파일당 최대 2000자
        })
    return contents


def call_gemini(files_data):
    import time
    files_content = ""
    for i, fd in enumerate(files_data):
        files_content += f"\n--- 파일 {i+1}: {fd['filename']} ---\n{fd['content']}\n"

    prompt = PROMPT_TEMPLATE.format(files_content=files_content)

    models = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
    for model in models:
        for attempt in range(5):
            try:
                print(f"  시도: {model} (attempt {attempt+1})")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=8192,
                    )
                )
                text = response.text
                print(f"  응답 길이: {len(text) if text else 0}자 | 앞100: {repr(text[:100]) if text else 'None/Empty'}")
                if not text:
                    reason = response.candidates[0].finish_reason if response.candidates else "no_candidates"
                    print(f"  finish_reason: {reason}")
                    continue
                return text
            except Exception as e:
                err = str(e)
                if "503" in err or "UNAVAILABLE" in err:
                    wait = 30 * (attempt + 1)
                    print(f"  503 과부하, {wait}초 대기...")
                    time.sleep(wait)
                elif "429" in err and "limit: 0" in err:
                    print(f"  {model} 쿼터 없음, 다음 모델로...")
                    break
                elif "404" in err or "NOT_FOUND" in err:
                    print(f"  {model} 없음, 다음 모델로...")
                    break
                else:
                    raise
    raise Exception("모든 모델 실패")


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("[LOAD] 블로그 파일 읽는 중...")
    files_data = read_blog_files()
    print(f"  -> {len(files_data)}개 파일 로드")

    # 14개씩 배치 처리
    batch_size = 14
    all_results = []
    out_path = Path(r"C:\Users\TheRose\Desktop\로또의 주식\raw\ingest_blog_2026-06-09_gemini.json")
    for i in range(0, len(files_data), batch_size):
        batch = files_data[i:i+batch_size]
        print(f"[GEMINI] 배치 {i//batch_size+1} ({len(batch)}개) 분석 중...")
        raw = call_gemini(batch)
        try:
            batch_results = json.loads(raw)
        except json.JSONDecodeError:
            import re
            clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
            batch_results = json.loads(clean)
        all_results.extend(batch_results)
        print(f"  -> {len(batch_results)}개 완료")
        # 배치마다 중간 저장
        out_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [저장] 현재까지 {len(all_results)}개 저장 완료")

    results = all_results
    raw = json.dumps(results)  # dummy for compatibility

    # 결과 저장
    out_path = Path(r"C:\Users\TheRose\Desktop\로또의 주식\raw\ingest_blog_2026-06-09_gemini.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 분석 결과 저장: {out_path}")

    # 요약 출력
    total = len(results)
    skip = sum(1 for r in results if r.get("skip"))
    ingest = total - skip

    print(f"\n[결과] 총 {total}개 | 인제스트 대상 {ingest}개 | 스킵 {skip}개\n")

    sectors = {}
    for r in results:
        if not r.get("skip"):
            s = r.get("sector", "기타")
            sectors[s] = sectors.get(s, 0) + 1

    print("섹터별 분포:")
    for s, cnt in sorted(sectors.items(), key=lambda x: -x[1]):
        print(f"  {s}: {cnt}개")

    print("\n--- 인제스트 대상 목록 ---")
    for r in results:
        if not r.get("skip"):
            stocks = ", ".join(r.get("stocks", [])) or "-"
            print(f"\n[{r['sector']}] {r['filename']}")
            print(f"  종목: {stocks}")
            for ins in r.get("key_insights", []):
                print(f"  * {ins}")
            for fact in r.get("structural_facts", []):
                print(f"  # {fact}")

    print("\n--- 스킵 목록 ---")
    for r in results:
        if r.get("skip"):
            print(f"  SKIP: {r['filename']} ({r.get('skip_reason', '')})")

    return results


if __name__ == "__main__":
    main()
