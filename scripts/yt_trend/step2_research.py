import json
import os
import sys
from datetime import datetime
from pathlib import Path
def _load_env(env_path):
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_env(Path(__file__).parent.parent.parent / ".env")

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent.parent.parent / "raw" / "yt_trend"

PROMPT_TEMPLATE = """오늘 날짜: {date}

다음은 오늘 한국 주식 YouTube에서 급상승 중인 영상 제목들이다.

{titles}

⚠️ 중요: 오늘 실제 시장 상황(KOSPI/KOSDAQ 등락률, 주요 급등/급락 섹터, 외인·기관 동향)을
웹 검색으로 먼저 파악한 뒤 아래 분석을 작성하라. 영상 제목만 보고 추론하지 말 것.

분석 요청:
1. 오늘 실제 시장 상황은? (지수 등락, 주도 섹터, 특이 이슈)
2. 위 영상들이 급상승하는 이유는? (시장 상황과 연결해서)
3. 이 트렌드는 며칠이나 지속될 것으로 보이나? 근거는?
4. 투자자들이 지금 가장 궁금해하는 핵심 질문은 무엇인가?

한국어로 1~2페이지 분량으로 작성.
"""


def run(date_str: str):
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("❌ GEMINI_API_KEY 없음")
        sys.exit(1)

    out_dir = BASE_DIR / date_str
    out_file = out_dir / "step2_research.md"
    if out_file.exists():
        print(f"⏭  step2 already done: {out_file}")
        return

    step1_file = out_dir / "step1_videos.json"
    videos = json.loads(step1_file.read_text(encoding="utf-8"))
    titles = "\n".join(f"{i+1}. {v['title']}" for i, v in enumerate(videos[:10]))

    prompt = PROMPT_TEMPLATE.format(date=date_str, titles=titles)

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    result = response.text
    out_file.write_text(result, encoding="utf-8")
    print(f"✅ step2 done → {out_file}")
    print(result[:300] + "...")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = p.parse_args()
    run(args.date)
