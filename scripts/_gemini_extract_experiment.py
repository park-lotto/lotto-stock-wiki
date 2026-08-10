"""
4개 PDF를 Gemini로 추출 테스트 — 애널리스트 강조 포인트 추출
"""
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

PDFS = [
    ("삼성전기", "C:/Users/TheRose/Downloads/20260610_company_31633000.pdf"),
    ("LG이노텍", "C:/Users/TheRose/Downloads/20260611_company_784094000.pdf"),
    ("일진전기", "C:/Users/TheRose/Downloads/20260611_company_331731000 (1).pdf"),
    ("클로봇",   "C:/Users/TheRose/Downloads/20260610_company_381739000 (1).pdf"),
]

PROMPT = """이 증권사 리포트 PDF를 읽고 아래 형식으로 추출하라.

## 추출 규칙
- 애널리스트가 볼드 처리하거나 반복 언급한 내용을 우선 추출
- 수치·날짜는 원문 그대로 보존 (절대 요약/변환 금지)
- 섹터 시그널(업황 전체에 해당)과 종목 시그널(이 종목만 해당)을 구분
- 중요한 리스크도 반드시 포함

## 출력 형식 (JSON)
{
  "종목명": "",
  "섹터": "",
  "날짜": "",
  "증권사": "",
  "투자의견": "",
  "목표주가": "",
  "핵심주장_1줄": "",
  "섹터_시그널": [
    {"내용": "...", "수치": "..."}
  ],
  "종목_시그널": [
    {"내용": "...", "수치": "..."}
  ],
  "리스크": ["..."]
}

JSON만 반환. 다른 텍스트 금지."""

def test_pdf(name, path):
    print(f"\n{'='*60}")
    print(f"[{name}] 처리 중...")

    pdf_bytes = Path(path).read_bytes()

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            PROMPT
        ]
    )

    raw = response.text.strip()
    # JSON 파싱 시도
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return True
    except json.JSONDecodeError as e:
        print(f"[JSON 파싱 실패] {e}")
        print(f"원본 응답:\n{raw[:1000]}")
        return False

if __name__ == "__main__":
    results = []
    for name, path in PDFS:
        print(f"[{name}] 처리 중...")
        try:
            with open(path, "rb") as fh:
                file_obj = client.files.upload(
                    file=fh,
                    config=types.UploadFileConfig(mime_type="application/pdf"),
                )
            for attempt in range(4):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=[file_obj, PROMPT]
                    )
                    break
                except Exception as e:
                    if attempt < 3 and "503" in str(e):
                        wait = 20 * (attempt + 1)
                        print(f"  503 재시도 {attempt+1}/3 ({wait}s)")
                        time.sleep(wait)
                    else:
                        raise
            try:
                client.files.delete(name=file_obj.name)
            except Exception:
                pass
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            try:
                result = json.loads(raw)
                results.append(result)
                print(f"  OK {result.get('종목명', name)}")
            except json.JSONDecodeError as e:
                results.append({"name": name, "error": str(e), "raw": raw[:500]})
                print(f"  FAIL JSON parse error")
        except Exception as e:
            results.append({"name": name, "error": str(e)[:200]})
            print(f"  SKIP: {str(e)[:100]}")

    out_path = Path("test_gemini_result.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if "error" not in r)
    print(f"saved: {out_path.resolve()} ({ok}/{len(results)})")
