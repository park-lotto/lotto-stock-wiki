"""
경쟁 채널 분석 - Gemini 2.5 Flash
Usage: python pipeline/competitor_analyze.py
"""
import os, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import google.genai as genai

TITLES = {
    "1번": "chat GPT로 주식투자? 종목 찾는 시간 10배 단축!",
    "2번": "챗GPT를 투자에 활용하는 방법",
    "3번": "챗GPT 신기능! 주식 뉴스 매일 자동으로 받기!",
    "4번": "이걸 깨닫는 순간, 뉴스 분석하는 시간 절반으로 줄었습니다",
    "5번": "챗GPT로 주식 투자하면 수익률이 얼마나 될까?",
    "6번": "챗GPT 주식 분석, 이 질문 하나로 완전 달라집니다",
    "7번": "실제로 해보고 알게된 챗GPT 8배 잘 쓰는법",
    "8번": "증권사 직원처럼 주식 분석 속도 10배 올리는 AI 활용법",
    "9번": "챗GPT로 종목분석 10초 완성, 증권사 망하게 하는 AI 주식활용법",
}

PROMPT = """당신은 유튜브 채널 전략 전문가이자 주식 투자 콘텐츠 분석가입니다.

위의 자료는 월 수익 4천만원을 달성한 "부코드" 유튜브 채널의 영상 1편~9편 전체 자막입니다.

아래 항목을 심층 분석해주세요:

## 1. 채널 성장 전략 분석
- 1편→9편으로 콘텐츠가 어떻게 진화했는가 (단계별 설명)
- 시청자를 어떻게 단계적으로 끌어올렸는가
- 알고리즘 타겟 키워드 전략 (각 영상별 핵심 키워드 추출)

## 2. 수익화 구조 해부
- 유튜브 광고 외 수익원 (카카오 단톡방, 강의, 시스템 판매)
- 1~8편이 9편 판매를 위한 퍼널이었음을 구조적으로 설명
- 9편에서 드러난 실제 상품 구조와 가격 전략 추정

## 3. 콘텐츠 패턴 분석
- 후킹 방식 유형화 (공포형/기회형/호기심형 등)
- 매 영상 감정 흐름 구조 (불안 → 해결 → 기대)
- CTA 방식 변화 추이 (1편 vs 9편 비교)

## 4. 핵심 약점 3가지 (공격 포인트)
- 신뢰도: 실전 트레이더 근거 없음
- 콘텐츠: 복제 가능성, 지속 가능성
- 상품: 백테스트 75% 주장의 허점

## 5. 경쟁자 전략 제안
배경 정보:
- 나는 20년 경력 실전 트레이더
- 이미 보유한 시스템: 오실레이터 계산기(calc_oscillator.py), 섹터 RS 랭킹 자동화, 아침 브리핑 자동화(daily_scenario.py), Gemini 이미지+텍스트 분석
- 실시간 리딩 안 함. "잘 만든 서비스 판매"가 목표
- 채널명: 로또의 주식인사이트

분석 요청:
- 부코드와 명확히 다른 포지셔닝 한 문장
- 9편짜리 콘텐츠 퍼널 설계 (편당 제목 컨셉 + 핵심 장면)
- 부코드가 절대 만들 수 없는 콘텐츠 유형 3가지 (이유 포함)
- 수익화 모델: 유튜브→카카오→구독서비스 단계별 전환 설계
- 첫 영상 스크립트 초안 (훅 30초 + 본문 구조)

한국어로 답하세요. 구체적이고 실행 가능한 수준으로 작성해주세요."""


def load_transcripts():
    desktop = Path("C:/Users/TheRose/Desktop")
    data = {}
    file_map = {
        "tmp_transcripts.json": None,
        "tmp_v4.json": "4번",
        "tmp_v5v6.json": None,
        "tmp_v789.json": None,
    }
    for fname, single_key in file_map.items():
        p = desktop / fname
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if single_key:
            if "transcript" in d:
                data[single_key] = d["transcript"]
        else:
            for k, v in d.items():
                if isinstance(v, dict):
                    data[k] = v.get("transcript", v.get("error", ""))
                else:
                    data[k] = v
    return data


def main():
    transcripts = load_transcripts()

    full_text = "=== 경쟁 채널: 부코드 (AI 활용해서 투자하기) | 9편 전체 자막 ===\n\n"
    for k, title in TITLES.items():
        t = transcripts.get(k, "")
        if t and not t.startswith("ERROR"):
            full_text += f"[{k}] 제목: {title}\n자막:\n{t}\n\n{'='*60}\n\n"
        else:
            full_text += f"[{k}] 제목: {title}\n[자막 없음]\n\n{'='*60}\n\n"

    print(f"[전송] 총 {len(full_text):,}자 → Gemini 2.5 Flash")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[full_text, PROMPT],
    )

    out = Path("C:/Users/TheRose/Desktop/로또의 주식/out/competitor_analysis_부코드.md")
    out.write_text(response.text, encoding="utf-8")
    print(f"[완료] {out}")
    print(f"[크기] {len(response.text):,}자")
    print("\n" + "="*60)
    print(response.text[:3000])


if __name__ == "__main__":
    main()
