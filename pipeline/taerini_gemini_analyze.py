"""
태린이아빠 텔레그램 파일 → Gemini Flash 이미지+텍스트 통합 분석
Usage: python pipeline/taerini_gemini_analyze.py --date 2026-06-04
"""
import argparse
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import google.genai as genai
from google.genai import types

TELEGRAM_DIR = Path("c:/Users/TheRose/Desktop/로또의 주식/raw/telegram")
IMAGES_BASE  = Path("c:/Users/TheRose/crawling_bot_data")

PROMPT = """
당신은 주식 투자 전문가의 텔레그램 채널 메시지(텍스트+차트 이미지)를 분석합니다.

아래는 태린이아빠의 하루치 텔레그램 메시지입니다.
텍스트 코멘트와 첨부 이미지(차트, 데이터 화면)를 함께 보고 다음을 분석하세요:

## 분석 항목

### 1. 매매 결정 타임라인
시간대별로 어떤 결정을 내렸는지 표로 정리. (시간 | 결정 내용 | 근거)

### 2. 차트에서 읽은 신호
이미지 차트에서 어떤 패턴/지표를 보고 어떤 판단을 내렸는지 구체적으로.

### 3. 오실레이터 활용법
피어스그리드 오실레이터를 언제 어떻게 사용했는지. 수치나 구간이 보이면 명시.

### 4. 섹터/종목 선별 기준
어떤 필터로 종목을 골랐는지. 52주 신고가, 거래대금, 섹터 조건 등.

### 5. 리스크 관리 원칙
손절/현금화 기준. 언제 팔았고 왜 팔았는지.

### 6. 핵심 통찰 3개
이날 가장 중요한 인사이트. 미래 투자에 써먹을 수 있는 것.

텍스트가 깨진 부분(한글 인코딩 깨짐)은 문맥으로 유추해서 해석하세요.
한국어로 답하세요.
"""

def load_md_with_images(date_str: str):
    """MD 파일 읽고 이미지 경로 목록 추출"""
    md_path = TELEGRAM_DIR / f"{date_str}_태린이아빠 주식투자.md"
    if not md_path.exists():
        print(f"[ERROR] 파일 없음: {md_path}")
        sys.exit(1)

    text = md_path.read_text(encoding="utf-8", errors="replace")

    # images/20260603_210458_20465.jpg 형태 추출
    img_refs = re.findall(r"images/([\w.]+\.jpg)", text)

    # 날짜에서 crawling_bot_data 경로 계산
    # 파일명에 날짜 20260603_... 형태 → 봇 데이터 폴더 날짜와 다를 수 있음
    # crawling_bot_data/{date}/telegram/images/ 에서 찾기
    img_dir = IMAGES_BASE / date_str / "telegram" / "images"

    images_found = []
    for ref in img_refs:
        p = img_dir / ref
        if p.exists():
            images_found.append(p)

    return text, images_found


def analyze(date_str: str, max_images: int = 40):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY 없음")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print(f"[INFO] {date_str} 파일 로딩 중...")
    text, images = load_md_with_images(date_str)

    # 이미지 max_images개로 제한 (토큰 관리)
    images = images[:max_images]
    print(f"[INFO] 텍스트 {len(text):,}자, 이미지 {len(images)}개 로드")

    # 콘텐츠 구성
    parts = [f"=== {date_str} 태린이아빠 텔레그램 ===\n\n{text}\n\n=== 이미지 {len(images)}장 첨부 ==="]

    for i, img_path in enumerate(images):
        try:
            img_bytes = img_path.read_bytes()
            parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
            if (i+1) % 10 == 0:
                print(f"  이미지 {i+1}/{len(images)} 로드...")
        except Exception as e:
            print(f"  [WARN] {img_path.name} 스킵: {e}")

    parts.append(PROMPT)

    print(f"[INFO] Gemini Flash에 전송 중...")
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=parts,
        )
        return response.text
    except Exception as e:
        print(f"[ERROR] API 호출 실패: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-06-04", help="분석 날짜 YYYY-MM-DD")
    parser.add_argument("--max-images", type=int, default=40, help="최대 이미지 수")
    parser.add_argument("--output", help="결과 저장 경로 (없으면 출력만)")
    args = parser.parse_args()

    result = analyze(args.date, args.max_images)

    print("\n" + "="*60)
    print(result)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"\n[저장] {args.output}")
    else:
        out_path = Path(f"c:/Users/TheRose/Desktop/로또의 주식/out/taerini_analysis_{args.date}.md")
        out_path.write_text(result, encoding="utf-8")
        print(f"\n[저장] {out_path}")


if __name__ == "__main__":
    main()
