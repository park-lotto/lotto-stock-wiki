"""포스트형 소스(블로그·유튜브 등) 내용라우팅 질문지. blog_questionnaire 일반화."""
import json
from pathlib import Path

from google import genai
from google.genai import types

from .atomizer import _load_gemini_key
from .sector_classify import sectors_list

_MODEL = "gemini-3.1-flash-lite"
_DIR = Path(__file__).parent
_REGISTRY_CACHE: dict[str, dict] = {}


def post_trust(registry_file: str, name: str) -> str:
    if registry_file not in _REGISTRY_CACHE:
        path = _DIR / registry_file
        try:
            _REGISTRY_CACHE[registry_file] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _REGISTRY_CACHE[registry_file] = {}
    reg = _REGISTRY_CACHE[registry_file]
    key = (name or "").strip()
    entry = reg.get(key)
    if entry is None:
        # 편집페이지에서 표시명이 바뀐 경우("pokara61 블로그" → 등록명 "포카라님") URL slug로 폴백 매칭
        slug = key.split()[0] if key else ""
        if slug:
            for v in reg.values():
                url = v.get("url", "") if isinstance(v, dict) else ""
                if url and slug in url:
                    entry = v
                    break
    if entry is None:
        entry = "C"
    # registry 값이 {"trust","url"} dict면 trust 필드 추출, 문자열이면 그대로
    if isinstance(entry, dict):
        return entry.get("trust", "C")
    return entry


POST_PROMPT = """너는 투자 컨텐츠(블로그·유튜브 등) 요약본을 '정해진 칸'에 옮겨 적는 사람이다.
판단하지 말고 칸을 채워라. 잡담·인사는 버려라.
철칙: 없으면 null(지어내지 마라) / 종목명·수치·날짜 원문 그대로 /
각 종목에 quote(근거 원문 문장)와 sector를 붙여라. sector는 아래 목록에서 정확히 하나(모르면 "기타"): """ + " / ".join(sectors_list()) + """

## STEP 0 — target_kind 판별 (본문 내용 기준)
- "stock_tips" : 특정 종목 집중 분석
- "sector"     : 단일 섹터/테마 전반
- "market"     : 시황/매크로/시장전략
- "insight"    : 에세이·전략·시장철학

## STEP 1 — target_kind에 맞는 칸만 채워라
[stock_tips] stocks:[{name, signal(bull/bear/neutral), reason, ts(null 허용), quote, sector}], news_items:[{fact, ts, quote}], quote
[sector] sector_name, sector_view(긍정/중립/부정), points(배열), stocks_mentioned:[{name, comment, ts, quote, sector}], events:[{fact, ts, quote}], quote
[market] market_direction, macro_events:[{fact, ts, quote}], sectors_mentioned:[{sector, stance, comment}], quote
[insight] leading_sectors(배열), stance:[{target, view(긍정/중립/부정), ts, quote}], methods:[{rule, quote}], stocks_mentioned:[{name, comment, ts, quote, sector}], quote

## 출력
target_kind + 해당 타입 칸만 채운 JSON 1개. 다른 텍스트 금지."""


def extract_post(md_path: Path) -> dict:
    """포스트 .md를 Gemini로 읽어 채워진 질문지(target_kind+슬롯) 반환. 실패 시 {}."""
    text = md_path.read_text(encoding="utf-8")
    from .atomizer import _get_client, _rotate_key
    for _attempt in range(4):
        try:
            resp = _get_client().models.generate_content(
                model=_MODEL, contents=[text, POST_PROMPT],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(resp.text or "{}")
        except Exception as e:
            _m = str(e)
            if any(c in _m for c in ("429", "RESOURCE_EXHAUSTED")):
                if "PerDay" in _m or "limit: 500" in _m:
                    # 일일 한도 초과 → 다른 프로젝트 키로 rotation
                    if _rotate_key():
                        continue
                else:
                    # 분당 한도(15건/분) → 60초 대기 후 재시도 (키 교체 소용없음)
                    import time
                    time.sleep(62)
                    continue
            print(f"  [WARN] 포스트 추출 실패: {e}")
            return {}
    return {}
