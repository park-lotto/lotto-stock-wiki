"""
텔레그램 + 리포트 파일 Gemini 분석 → 위키 인제스트용 JSON 생성
Usage: python scripts/gemini_tele_report_ingest.py [--date YYYY-MM-DD]
"""
import os, sys, json, re, time, argparse
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).parent.parent / ".env")

from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODELS = ["gemini-3-flash-preview", "gemini-3.1-flash-lite"]

PROMPT_TEMPLATE = """
아래는 {source_type} 파일들입니다. 각 파일을 분석해서 위키 인제스트용 구조화 요약을 만들어주세요.

=== 파일 목록 ===
{files_content}

=== 출력 형식 (JSON 배열) ===
[
  {{
    "filename": "파일명",
    "skip": true/false,
    "sector": "반도체|조선|방산|바이오|화장품|로봇|전력|자동차|통신|시장전체|매크로|기타",
    "type": "종목분석|섹터분석|시황|리포트|매크로",
    "stocks": ["종목명"],
    "wiki_level": "L5 또는 L6",
    "key_insights": ["수치·날짜 포함 구체적 인사이트"],
    "structural_facts": ["TP변경·수주·실적·수급 등 구조적 사실만"],
    "skip_reason": ""
  }}
]

=== skip 기준 ===
- 당일 등락%만 있는 글 → skip
- 개인 감성글·일기 → skip
- 수치 없는 막연한 전망 → skip
- 중복 내용 (같은 내용 여러 파일) → 첫 번째만 keep, 나머지 skip

=== keep 기준 ===
- TP 변경, 수주/계약 공시, 실적 숫자
- 구조적 섹터 방향성 변화
- 수급 신호 (기관/외국인 대규모 순매수)
- 일정·트리거 이벤트 (FOMC·CPI·상장일 등)
- 증권사 리서치 핵심 수치

JSON 배열만 출력. 마크다운 코드블록 없이.
"""


def read_files(folder: Path, max_chars=2000):
    files = sorted(folder.glob("*.md"))
    result = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            text = f.read_text(encoding="cp949", errors="ignore")
        result.append({"filename": f.name, "content": text[:max_chars]})
    return result


def call_gemini(files_data, source_type="텔레그램/리포트"):
    files_content = ""
    for i, fd in enumerate(files_data):
        files_content += f"\n--- 파일 {i+1}: {fd['filename']} ---\n{fd['content']}\n"

    prompt = PROMPT_TEMPLATE.format(source_type=source_type, files_content=files_content)

    for model in MODELS:
        for attempt in range(5):
            try:
                print(f"  [{model}] attempt {attempt+1}")
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=8192),
                )
                text = resp.text
                if not text:
                    reason = resp.candidates[0].finish_reason if resp.candidates else "no_candidates"
                    print(f"  빈 응답 finish_reason={reason}, 재시도...")
                    continue
                print(f"  응답 {len(text)}자")
                return text
            except Exception as e:
                err = str(e)
                if "503" in err or "UNAVAILABLE" in err:
                    wait = 30 * (attempt + 1)
                    print(f"  503 과부하, {wait}초 대기...")
                    time.sleep(wait)
                elif "429" in err:
                    if "limit: 0" in err:
                        print(f"  {model} 쿼터 없음, 다음 모델...")
                        break
                    else:
                        wait = 60
                        print(f"  429 쿼터초과, {wait}초 대기...")
                        time.sleep(wait)
                elif "404" in err or "NOT_FOUND" in err:
                    print(f"  {model} 없음, 다음 모델...")
                    break
                else:
                    raise
    raise Exception("모든 모델 실패")


def parse_json(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
        return json.loads(clean)


def process_folder(folder: Path, source_type: str, batch_size: int, out_path: Path, existing=[]):
    files_data = read_files(folder)
    print(f"\n[{source_type}] {len(files_data)}개 파일 로드")

    all_results = list(existing)
    for i in range(0, len(files_data), batch_size):
        batch = files_data[i:i + batch_size]
        print(f"  배치 {i // batch_size + 1} ({len(batch)}개)...")
        raw = call_gemini(batch, source_type)
        batch_results = parse_json(raw)
        all_results.extend(batch_results)
        out_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> 누적 {len(all_results)}개 저장")

    return all_results


def print_summary(results):
    total = len(results)
    skip = sum(1 for r in results if r.get("skip"))
    keep = total - skip
    print(f"\n{'='*60}")
    print(f"총 {total}개 | 인제스트 대상 {keep}개 | 스킵 {skip}개")

    sectors = {}
    for r in results:
        if not r.get("skip"):
            s = r.get("sector", "기타")
            sectors[s] = sectors.get(s, 0) + 1
    print("\n섹터별:")
    for s, cnt in sorted(sectors.items(), key=lambda x: -x[1]):
        print(f"  {s}: {cnt}개")

    print("\n--- 인제스트 대상 ---")
    for r in results:
        if not r.get("skip"):
            stocks = ", ".join(r.get("stocks", [])) or "-"
            print(f"\n[{r.get('sector','')}] {r['filename']}")
            print(f"  종목: {stocks}")
            for ins in r.get("key_insights", [])[:3]:
                print(f"  * {ins}")
            for fact in r.get("structural_facts", [])[:3]:
                print(f"  # {fact}")

    print("\n--- 스킵 ---")
    for r in results:
        if r.get("skip"):
            print(f"  SKIP: {r['filename']} ({r.get('skip_reason', '')})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-06-09")
    parser.add_argument("--source", choices=["telegram", "reports", "both"], default="both")
    parser.add_argument("--batch", type=int, default=10)
    args = parser.parse_args()

    base = Path(r"C:\Users\TheRose\crawling_bot_data") / args.date
    out_dir = Path(r"C:\Users\TheRose\Desktop\로또의 주식\raw")

    all_results = []

    if args.source in ("telegram", "both"):
        out_path = out_dir / f"ingest_telegram_{args.date}_gemini.json"
        tele_folder = base / "telegram"
        if tele_folder.exists():
            results = process_folder(tele_folder, "텔레그램", args.batch, out_path)
            all_results.extend(results)
            print(f"\n[저장] {out_path}")
        else:
            print(f"폴더 없음: {tele_folder}")

    if args.source in ("reports", "both"):
        out_path = out_dir / f"ingest_reports_{args.date}_gemini.json"
        rep_folder = base / "reports"
        if rep_folder.exists():
            results = process_folder(rep_folder, "리포트", args.batch, out_path)
            all_results.extend(results)
            print(f"\n[저장] {out_path}")
        else:
            print(f"폴더 없음: {rep_folder}")

    if args.source == "both":
        combined_path = out_dir / f"ingest_combined_{args.date}_gemini.json"
        combined_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[통합 저장] {combined_path}")

    print_summary(all_results)


if __name__ == "__main__":
    main()
