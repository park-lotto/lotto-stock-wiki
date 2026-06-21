"""리포트 질문지 추출 — Gemini가 PDF를 고정 슬롯에 옮긴다."""
import json
from pathlib import Path

from google import genai
from google.genai import types

from .atomizer import _load_gemini_key

_MODEL = "gemini-3.1-flash-lite"

QUESTIONNAIRE_PROMPT = """너는 증권사 리포트를 '정해진 질문지'에 옮겨 적는 사람이다.
무엇이 중요한지 판단하지 마라. 칸을 채우는 것이 전부다.

## 철칙
1. 칸에 해당하는 내용이 리포트에 없으면 그 값은 null. 절대 지어내지 마라.
2. 모든 수치·날짜·종목명은 원문 그대로(축자). 반올림·재서술 금지.
3. 핵심 슬롯에는 "quote"(근거가 된 원문 문장 그대로)를 짝으로 붙여라.
4. 면책조항·독립성 고지·보유율(1% 미만 등)·법적 경고 문구는 완전히 무시하라.
   설령 그것이 요약의 전부처럼 보여도, 본문에서 실제 분석 내용을 찾아 채워라.
5. 증권사명·애널리스트명은 PDF 표지/머리글/꼬리글에서 찾아라. (파일명엔 없을 수 있음)

## STEP 0 — target_kind 판별
- "stock"  : 특정 종목에 목표주가가 제시됨
- "sector" : 단일 업종/테마 전반의 전망 (개별 목표가 없이 업종을 논함)
- "market" : 시장 전체/매크로/전략, 또는 2개 이상 섹터를 묶은 데일리·위클리
판별 근거는 네이버 카테고리나 제목이 아니라 본문 내용이다.

## STEP 1 — 공통 헤더
broker(증권사), analyst(애널리스트), report_date

## STEP 2 — target_kind별 질문지

[stock] 각 종목별로 stocks 배열:
  name, code(PDF에 6자리 있으면, 없으면 null),
  rating, rating_changed,
  tp_new, tp_prev, tp_direction(up/down/flat/null),
  earnings_outlook(이번·차기 분기 실적·판매량·매출·영익 전망. 컨센/YoY/QoQ 수치가
    하나라도 있으면 반드시 채워라. 빈칸으로 넘기지 마라),
  estimate_revision, next_catalyst,
  thesis(최대 3개 배열), valuation_basis, risk, supply_comment, quote

[sector]
  sector_name, sector_view(비중확대/중립/축소),
  thesis(배열), timeline(배열),
  top_picks: [{name, reason, tp}]
    — 본문에 매수·선호·수혜·주목·탑픽·1선/2선으로 종목명이 거론된 곳을 빠짐없이.
      단 하나의 종목명도 없을 때만 null.
  risk, quote

[market]
  market_direction, macro_vars(배열),
  recommended_sectors: [{sector, stance, reason}],
  style, event_calendar: [{date, event}],
  top_picks(거론 종목 배열 또는 null), risk, quote

## 출력
질문지 1장을 JSON 객체 하나로. target_kind에 해당하는 칸만 채우고 나머지는 생략.
다른 텍스트 절대 금지."""


def extract_questionnaire(pdf_path: Path) -> dict:
    """PDF를 Gemini로 읽어 채워진 질문지 dict 반환. 실패 시 {}."""
    client = genai.Client(api_key=_load_gemini_key())
    try:
        with open(pdf_path, "rb") as fh:
            fobj = client.files.upload(
                file=fh, config=types.UploadFileConfig(mime_type="application/pdf")
            )
    except Exception as e:
        print(f"  [WARN] 업로드 실패: {e}")
        return {}
    try:
        resp = client.models.generate_content(
            model=_MODEL,
            contents=[fobj, QUESTIONNAIRE_PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(resp.text)
    except Exception as e:
        print(f"  [WARN] 추출 실패: {e}")
        return {}
    finally:
        try:
            client.files.delete(name=fobj.name)
        except Exception:
            pass
