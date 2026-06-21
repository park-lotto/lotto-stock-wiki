"""블로그 인제스트 — 내용기반 라우팅 + 타입별 질문지 (리포트 라우팅 차용, 텔레 슬롯 호환)."""
import json
from pathlib import Path

from google import genai
from google.genai import types

from .atomizer import _load_gemini_key
from .sector_classify import sectors_list

_MODEL = "gemini-3.1-flash-lite"
_DIR = Path(__file__).parent
_REGISTRY = json.loads((_DIR / "blog_registry.json").read_text(encoding="utf-8"))


def blog_trust(blogger: str) -> str:
    return _REGISTRY.get((blogger or "").strip(), "C")


BLOG_PROMPT = """너는 개인 투자 블로그 포스트를 '정해진 칸'에 옮겨 적는 사람이다.
판단하지 말고 칸을 채워라. 잡담·인사는 버려라.
철칙: 없으면 null(지어내지 마라) / 종목명·수치·날짜 원문 그대로 /
각 종목에 quote(근거 원문 문장)와 sector를 붙여라. sector는 아래 목록에서 정확히 하나(모르면 "기타"): """ + " / ".join(sectors_list()) + """

## STEP 0 — target_kind 판별 (본문 내용 기준)
- "stock_tips" : 특정 종목 집중 분석
- "sector"     : 단일 섹터/테마 전반
- "market"     : 시황/매크로/시장전략
- "insight"    : 에세이·전략·잡생각(매매원칙·시장철학)

## STEP 1 — target_kind에 맞는 칸만 채워라
[stock_tips] stocks:[{name, signal(bull/bear/neutral), reason, ts(null 허용), quote, sector}], news_items:[{fact, ts, quote}], quote
[sector] sector_name, sector_view(긍정/중립/부정), points(배열), stocks_mentioned:[{name, comment, ts, quote, sector}], events:[{fact, ts, quote}], quote
[market] market_direction, macro_events:[{fact, ts, quote}], sectors_mentioned:[{sector, stance, comment}], quote
[insight] leading_sectors(배열), stance:[{target, view(긍정/중립/부정), ts, quote}], methods:[{rule, quote}], stocks_mentioned:[{name, comment, ts, quote, sector}], quote

## 출력
target_kind + 해당 타입 칸만 채운 JSON 1개. 다른 텍스트 금지."""


def extract_blog(md_path: Path) -> dict:
    """블로그 .md를 Gemini로 읽어 채워진 질문지(target_kind+슬롯) 반환. 실패 시 {}."""
    text = md_path.read_text(encoding="utf-8")
    client = genai.Client(api_key=_load_gemini_key())
    try:
        resp = client.models.generate_content(
            model=_MODEL, contents=[text, BLOG_PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(resp.text)
    except Exception as e:
        print(f"  [WARN] 블로그 추출 실패: {e}")
        return {}
