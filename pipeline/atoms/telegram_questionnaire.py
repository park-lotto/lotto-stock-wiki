"""텔레그램 타입별 질문지 프롬프트 + Gemini 추출."""
import json
from pathlib import Path

from google import genai
from google.genai import types

from .atomizer import _load_gemini_key

_MODEL = "gemini-3.1-flash-lite"

_COMMON = """너는 텔레그램 주식 채널의 하루치 메시지를 '정해진 칸'에 옮겨 적는 사람이다.
판단하지 말고 칸을 채워라. 잡담·인사·이미지설명·외부링크는 버려라.
철칙: 없으면 null(지어내지 마라) / 수치·종목명·날짜는 원문 그대로 /
각 항목에 ts(원문 메시지 시각 HH:MM)와 quote(근거 원문 문장 그대로)를 짝으로 붙여라 /
comment·reason은 재서술 허용하되 quote는 반드시 원문 축자.
출력: 해당 칸만 채운 JSON 1개. 다른 텍스트 금지.
"""

QUESTIONNAIRES = {
    "sector": _COMMON + """
이 채널 타입: sector
칸: sector_name, sector_view(긍정/중립/부정), points(코멘트 배열),
stocks_mentioned:[{name, comment, ts, quote}],
events:[{fact, ts, quote}], quote(핵심 한 문장)""",

    "market": _COMMON + """
이 채널 타입: market
칸: market_direction, macro_events:[{fact, ts, quote}],
sectors_mentioned:[{sector, stance, comment}], quote""",

    "stock_tips": _COMMON + """
이 채널 타입: stock_tips
칸: stocks:[{name, signal(bull/bear/neutral), reason, ts, quote}],
news_items:[{fact, ts, quote}], quote""",

    "insight": _COMMON + """
이 채널 타입: insight (잡담 많음 — 투자 인사이트만 추려라)
칸: leading_sectors(배열),
stance:[{target(종목 또는 섹터), view(긍정/중립/부정), ts, quote}],
methods:[{rule, quote}]  (종목 무관 매매규칙),
stocks_mentioned:[{name, comment, ts, quote}],
noise_ratio(0~1 추정), quote(가장 통찰력 있는 한 문장)""",

    "report_relay": _COMMON + """
이 채널 타입: report_relay (증권사 리포트 중계)
칸: reports:[{broker, stock, rating, tp, ts, quote}], quote""",
}


def extract_telegram(md_path: Path, ctype: str) -> dict:
    """채널 .md를 Gemini로 읽어 채워진 질문지 반환. 실패 시 {}."""
    prompt = QUESTIONNAIRES.get(ctype)
    if not prompt:
        return {}
    text = md_path.read_text(encoding="utf-8")
    client = genai.Client(api_key=_load_gemini_key())
    try:
        resp = client.models.generate_content(
            model=_MODEL, contents=[text, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(resp.text)
    except Exception as e:
        print(f"  [WARN] 추출 실패({ctype}): {e}")
        return {}
