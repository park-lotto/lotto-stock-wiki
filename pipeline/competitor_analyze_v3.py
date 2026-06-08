"""
경쟁 채널 분석 v3 - 16~21편 (마지막) - Gemini 2.5 Flash
Usage: python pipeline/competitor_analyze_v3.py
"""
import os, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import google.genai as genai

PROMPT = """당신은 유튜브 채널 전략 전문가이자 주식 투자 콘텐츠 분석가입니다.

위의 자료는 월 수익 4천만원을 달성한 "부코드" 유튜브 채널의 영상 16편~21편 전체 자막입니다.

이전 분석 결과 요약:
- 1~9편: GPT 활용법 교육 → 카카오 단톡방 → 강의/시스템 판매 퍼널 구축
- 10~15편: Gemini/퍼플렉시티/노트북LM으로 도구 다변화, 리드 마그넷 도입
- 핵심 약점: 실전 트레이더 근거 없음, 수익 증거 없음, 도구 교육 ≠ 투자 교육

아래 항목을 심층 분석해주세요:

## 1. 16~21편 콘텐츠 진화 및 최종 전략
- 채널이 마지막 단계에서 어떤 방향으로 수렴했는가
- 새로운 훅/포맷/전략이 등장했는가
- 전체 21편을 통해 완성된 채널 아이덴티티는 무엇인가

## 2. 최종 수익화 구조 완성도
- 16~21편에서의 CTA 변화 및 강도
- 리드 마그넷, 단톡방, 강의 이외 새로운 수익 채널이 등장했는가
- 최종적으로 이 채널이 월 4천만원을 버는 구조의 완성된 그림

## 3. 가장 강력한 훅 TOP 3 (실제 문장 인용)
- 16~21편에서 가장 강력한 훅 3개, 왜 강력한지 분석

## 4. 21편 전체를 관통하는 핵심 전략 3가지
- 1편부터 21편까지 전체를 관통하는 채널 성공의 핵심 원리

## 5. "로또의 주식인사이트" 최종 대응 전략
배경:
- 20년 경력 실전 트레이더
- 보유 시스템: calc_oscillator.py(오실레이터), 섹터RS랭킹 자동화, daily_scenario.py(아침브리핑), Gemini이미지+텍스트 분석
- 실시간 리딩 안 함. 잘 만든 서비스 판매 목표
- 채널명: 로또의 주식인사이트

분석 요청:
- 21편 분석 완료 기준, 부코드를 이길 수 있는 최종 전략 한 문단 (핵심만)
- 첫 번째 영상에서 쓸 수 있는 최강의 후킹 문구 3개 (부코드 약점을 직접 겨냥)
- 지금 당장 실행 가능한 콘텐츠 우선순위 TOP 5

한국어로 구체적이고 실행 가능한 수준으로 작성해주세요."""


def main():
    data_path = Path("C:/Users/TheRose/Desktop/tmp_v16_21.json")
    data = json.loads(data_path.read_text(encoding="utf-8"))

    full_text = "=== 경쟁 채널: 부코드 | 영상 16편~21편 전체 자막 ===\n\n"
    for key, val in data.items():
        title = val.get("title", "")
        transcript = val.get("transcript", "")
        full_text += f"[{key}] 제목: {title}\n자막:\n{transcript}\n\n{'='*60}\n\n"

    print(f"[전송] 총 {len(full_text):,}자 -> Gemini 2.5 Flash")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[full_text, PROMPT],
    )

    out = Path("C:/Users/TheRose/Desktop/로또의 주식/out/competitor_analysis_부코드_v3.md")
    out.write_text(response.text, encoding="utf-8")
    print(f"[완료] {out}")
    print(f"[크기] {len(response.text):,}자")


if __name__ == "__main__":
    main()
