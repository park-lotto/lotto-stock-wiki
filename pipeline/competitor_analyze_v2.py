"""
경쟁 채널 분석 v2 - 10~15편 - Gemini 2.5 Flash
Usage: python pipeline/competitor_analyze_v2.py
"""
import os, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import google.genai as genai

PROMPT = """당신은 유튜브 채널 전략 전문가이자 주식 투자 콘텐츠 분석가입니다.

위의 자료는 월 수익 4천만원을 달성한 "부코드" 유튜브 채널의 영상 10편~15편 전체 자막입니다.

참고: 이전 분석(1~9편)에서 파악한 핵심 구조:
- 채널 전략: AI 도구(GPT/Gemini/퍼플렉시티/노트북LM) 활용법 교육 → 카카오 단톡방 → 강의/시스템 판매
- 포지셔닝: 실전 트레이더가 아닌 AI 활용 전도사
- 퍼널: 1~8편(신뢰+필요성) → 9편(판매)

아래 항목을 심층 분석해주세요:

## 1. 10~15편의 콘텐츠 진화
- 9편 이후 채널이 어떤 방향으로 발전했는가
- 새로 등장한 AI 도구나 전략이 있는가 (Gemini, 퍼플렉시티, 노트북LM 등)
- 시청자 타겟이 변화했는가 (초보 → 중급 등)

## 2. 수익화 전략 업그레이드
- 9편 이후 CTA나 판매 방식이 변화했는가
- 단톡방, 강의 외 새로운 수익원이 등장했는가
- 구독 유도 방식의 변화

## 3. 후킹 및 콘텐츠 패턴 업데이트
- 10~15편에서 새로 등장한 후킹 방식
- 기존 공포형/기회형/호기심형 대비 변화
- 가장 강력했던 훅 TOP 3 (실제 문장 인용)

## 4. 경쟁 채널 대비 공격 포인트 추가 발굴
- 10~15편에서 드러난 새로운 약점
- 1~9편 분석에서 놓친 공격 포인트가 있는가

## 5. "로또의 주식인사이트" 대응 전략 업데이트
- 10~15편 분석을 반영한 추가 차별화 포인트
- 이 영상들에서 배울 수 있는 콘텐츠 아이디어 (우리에게 적용 가능한 것)
- 부코드가 다루지 않는 영역 중 우리가 선점할 수 있는 주제

배경:
- 나는 20년 경력 실전 트레이더
- 보유 시스템: 오실레이터(calc_oscillator.py), 섹터RS랭킹, daily_scenario.py, Gemini이미지분석
- 실시간 리딩 안 함. 잘 만든 서비스 판매 목표

한국어로 구체적이고 실행 가능한 수준으로 작성해주세요."""


def main():
    data_path = Path("C:/Users/TheRose/Desktop/tmp_v10_15.json")
    data = json.loads(data_path.read_text(encoding="utf-8"))

    full_text = "=== 경쟁 채널: 부코드 | 영상 10편~15편 전체 자막 ===\n\n"
    for key, val in data.items():
        title = val.get("title", "")
        transcript = val.get("transcript", "")
        full_text += f"[{key}] 제목: {title}\n자막:\n{transcript}\n\n{'='*60}\n\n"

    print(f"[전송] 총 {len(full_text):,}자 -> Gemini 2.5 Flash")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[full_text, PROMPT],
    )

    out = Path("C:/Users/TheRose/Desktop/로또의 주식/out/competitor_analysis_부코드_v2.md")
    out.write_text(response.text, encoding="utf-8")
    print(f"[완료] {out}")
    print(f"[크기] {len(response.text):,}자")
    print("\n" + "=" * 60)
    print(response.text[:2000])


if __name__ == "__main__":
    main()
