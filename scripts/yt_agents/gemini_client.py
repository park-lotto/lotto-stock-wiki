"""Gemini API 래퍼 — 기존 scripts와 동일한 방식"""
import sys, os
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
ENV  = ROOT / '.env'

def _load_env():
    env = {}
    if ENV.exists():
        for line in ENV.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env

_env = _load_env()
GEMINI_KEY = _env.get('GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY', ''))

def call(prompt: str, system: str = '', model: str = 'gemini-2.5-flash', temperature: float = 0.7) -> str:
    """Gemini 단일 호출 → 텍스트 반환"""
    if not GEMINI_KEY:
        raise RuntimeError('.env에 GEMINI_API_KEY 없음')

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_KEY)
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    resp = client.models.generate_content(
        model=model,
        contents=full_prompt,
        config=types.GenerateContentConfig(temperature=temperature),
    )
    return resp.text.strip()


def search(query: str, model: str = 'gemini-2.5-flash') -> str:
    """실제 Google Search grounding — 실시간 웹 검색"""
    if not GEMINI_KEY:
        raise RuntimeError('.env에 GEMINI_API_KEY 없음')

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_KEY)

    resp = client.models.generate_content(
        model=model,
        contents=query,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0,
        ),
    )
    return resp.text.strip()


def call_json(prompt: str, system: str = '') -> dict:
    """JSON 응답 파싱"""
    import json, re
    text = call(prompt, system, temperature=0.3)
    # 코드블록 제거
    text = re.sub(r'```(?:json)?\s*', '', text).strip('`').strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSON 부분만 추출 시도
        m = re.search(r'\{[\s\S]+\}', text)
        if m:
            return json.loads(m.group())
        raise
