import json
import os
import sys
from datetime import datetime
from pathlib import Path

import google.generativeai as genai

sys.stdout.reconfigure(encoding="utf-8")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
BASE_DIR = Path(__file__).parent.parent.parent / "raw" / "yt_trend"

CHANNEL_NAME = "로또의 스탁브레인"


def run(date_str: str):
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)

    out_dir = BASE_DIR / date_str
    step2_file = out_dir / "step2_research.md"
    step3_file = out_dir / "step3_analysis.json"
    out_file = out_dir / "step4_ideas.json"

    if out_file.exists():
        print(f"⏭  step4 already done: {out_file}")
        return

    missing = [str(f) for f in [step2_file, step3_file] if not f.exists()]
    if missing:
        print(f"❌ 누락 파일: {missing}")
        sys.exit(1)

    research = step2_file.read_text(encoding="utf-8")
    analysis = json.loads(step3_file.read_text(encoding="utf-8"))
    analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2)

    prompt = f"""채널명: {CHANNEL_NAME}
채널 원칙: 70/20/10 (70% 순수정보, 20% 간접노출 방법론, 10% CTA는 S8 씬에만)

[시장 배경 리서치]
{research}

[경쟁 영상 분석 결과]
{analysis_str}

위 데이터를 기반으로 우리 채널에서 만들 영상 소재 3개를 추출해줘.
조건:
- 경쟁 영상과 각도가 다른 신선한 접근
- 주식 투자자에게 실질적 도움이 되는 정보
- 지금 트렌드에 올라탈 수 있는 타이밍

아래 JSON 배열로만 응답해줘 (마크다운 코드블록 없이):
[
  {{
    "rank": 1,
    "title_hook": "제목 방향 (훅 포함, 30자 이내)",
    "angle": "우리 채널만의 각도 (2줄 이내)",
    "key_points": ["핵심 포인트1", "핵심 포인트2", "핵심 포인트3"],
    "why_viral": "왜 터질 것 같은가 (1줄)"
  }},
  ...
]"""

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content(prompt)

    text = resp.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        ideas = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"❌ Gemini 응답 파싱 실패: {e}\n원문:\n{resp.text[:500]}")
        sys.exit(1)

    out_file.write_text(json.dumps(ideas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ step4 done: {len(ideas)}개 소재 → {out_file}")
    for idea in ideas:
        print(f"  {idea['rank']}. {idea['title_hook']} — {idea['why_viral']}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = p.parse_args()
    run(args.date)
