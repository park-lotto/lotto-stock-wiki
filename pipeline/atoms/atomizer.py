import os
import json
import hashlib
from pathlib import Path
from google import genai
from google.genai import types

_GEMINI_MODEL = "gemini-3.1-flash-lite"


def _load_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                    key = line.split("=", 1)[1].strip()
                    break
    return key


_client = genai.Client(api_key=_load_gemini_key())

_PROMPT = """다음 텍스트를 주식 시장 정보 '원자' 단위로 분해하라.

원자 정의: 하나의 명확한 주제(자산/이벤트)에 대한 최소 의미 단위. 3~7문장.
핵심 규칙: 원문을 요약하지 마라. 원문의 해당 부분을 그대로 담아라.

각 원자에 아래 메타데이터를 부여하라:
- sector: 반도체/조선/로봇/방산/바이오/전력/2차전지/자동차/통신/AI소프트웨어/우주/소비내수/기타
- asset: 종목명 또는 섹터명 또는 지표명
- asset_level: stock/sector/market/macro/theme
- signal: bullish/bearish/neutral/risk/catalyst/conflict/data
- event_type: earnings/policy/supply/demand/consensus/momentum/macro/news/report/event
- magnitude: major/minor
- content_type: fact/data/analysis/opinion
- validity_type: permanent/date/event
- validity_until: 만료일 YYYY-MM-DD 형식 또는 null

JSON 배열만 반환하라. 다른 텍스트 없이.

텍스트:
{text}"""


def _sanitize(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


def atomize_text(
    text: str,
    source_type: str,
    source_name: str,
    source_trust: str,
    raw_file: str,
    date: str,
    layer: str = "L5",
) -> list[dict]:
    text = _sanitize(text)
    try:
        response = _client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=_PROMPT.format(text=text),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        raw_atoms: list[dict] = json.loads(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nResponse: {getattr(response, 'text', 'no response')[:200]}")
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}")

    atoms = []
    for i, a in enumerate(raw_atoms):
        content = a.get("content", "")
        if not content:
            continue
        atoms.append(
            {
                "id": _make_id(date, source_name, i),
                "date": date,
                "source_type": source_type,
                "source_name": source_name,
                "source_trust": source_trust,
                "raw_file": raw_file,
                "layer": layer,
                "sector": a.get("sector", "기타"),
                "asset": a.get("asset", ""),
                "asset_level": a.get("asset_level", "sector"),
                "signal": a.get("signal", "neutral"),
                "event_type": a.get("event_type", "news"),
                "magnitude": a.get("magnitude", "minor"),
                "content_type": a.get("content_type", "fact"),
                "strength_score": _calc_strength(a, source_trust),
                "validity_type": a.get("validity_type", "permanent"),
                "validity_until": a.get("validity_until"),
                "is_active": 1,
                "content": content,
                "relations": [],
            }
        )
    return atoms


def _make_id(date: str, source_name: str, index: int) -> str:
    raw = f"{date}_{source_name}_{index}"
    return "atom_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _calc_strength(atom: dict, source_trust: str) -> int:
    score = 1
    score += {"A": 2, "B": 1}.get(source_trust, 0)
    if atom.get("magnitude") == "major":
        score += 1
    return min(score, 5)
