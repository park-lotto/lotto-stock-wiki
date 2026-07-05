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

def _key(name):
    return _env.get(name, os.environ.get(name, ''))

# 키 우선순위: 일반풀(GEMINI_API_KEY/_2/_3/_4) 먼저 → 소진되면 나머지 모든 Gemini 키
# (인제스트/임베딩/브리핑 풀)로 최후 폴백. 무료티어 할당량이 자주 바닥나서, YT 기획서
# 생성이 통째로 막히는 것보다 다른 풀 키를 빌려서라도 돌아가게 하는 게 낫다는 판단.
def _gemini_keys() -> list[str]:
    primary_names = ['GEMINI_API_KEY', 'GEMINI_API_KEY_2', 'GEMINI_API_KEY_3', 'GEMINI_API_KEY_4']
    keys = []
    for n in primary_names:
        v = _key(n)
        if v and v not in keys:
            keys.append(v)
    # 나머지 GEMINI_*KEY* 전부 (인제스트/임베딩/브리핑 풀) — 폴백용
    all_names = set()
    all_names.update(_env.keys())
    all_names.update(os.environ.keys())
    for n in sorted(all_names):
        if n.startswith('GEMINI_') and 'KEY' in n and n not in primary_names:
            v = _key(n)
            if v and v not in keys:
                keys.append(v)
    return keys

GEMINI_KEYS = _gemini_keys()
GEMINI_KEY = GEMINI_KEYS[0] if GEMINI_KEYS else ''  # 기존 코드 하위호환용


def _is_quota_error(e: Exception) -> bool:
    msg = str(e)
    return '429' in msg or 'RESOURCE_EXHAUSTED' in msg


def _is_transient_error(e: Exception) -> bool:
    """Gemini 서버측 일시 장애(모델 과부하 등) — 키 문제 아님, 잠깐 뒤 재시도하면 됨."""
    msg = str(e)
    return any(x in msg for x in ('503', 'UNAVAILABLE', '500', 'INTERNAL', 'high demand', 'overloaded'))


def _generate(model: str, contents, config):
    """할당량 초과(429)면 다음 키로, 일시 과부하(503/500)면 짧게 쉬고 재시도.
    18키를 순회하며, 각 키에서 일시장애는 최대 2번까지 백오프 재시도."""
    if not GEMINI_KEYS:
        raise RuntimeError('.env에 GEMINI_API_KEY 없음')

    import time as _t
    from google import genai

    last_err = None
    for key in GEMINI_KEYS:
        client = genai.Client(api_key=key)
        for attempt in range(3):
            try:
                return client.models.generate_content(model=model, contents=contents, config=config)
            except Exception as e:
                last_err = e
                if _is_quota_error(e):
                    break            # 이 키는 소진 → 다음 키로
                if _is_transient_error(e):
                    _t.sleep(2 * (attempt + 1))   # 2s,4s 백오프 후 같은 키 재시도
                    continue
                raise                # 그 외(코드/인증 오류)는 즉시 전파
    raise last_err


def call(prompt: str, system: str = '', model: str = 'gemini-3-flash-preview', temperature: float = 0.7) -> str:
    """Gemini 단일 호출 → 텍스트 반환"""
    from google.genai import types
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    resp = _generate(model, full_prompt, types.GenerateContentConfig(temperature=temperature))
    return resp.text.strip()


def search(query: str, model: str = 'gemini-3-flash-preview') -> str:
    """실제 Google Search grounding — 실시간 웹 검색"""
    from google.genai import types
    resp = _generate(model, query, types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0,
    ))
    return resp.text.strip()


def fetch_url(url: str, prompt: str, model: str = 'gemini-3-flash-preview') -> str:
    """URL을 Gemini가 직접 읽고 분석 — Naver 블로그 등 WebFetch 차단 사이트 우회"""
    from google.genai import types
    resp = _generate(model, f"{prompt}\n\nURL: {url}", types.GenerateContentConfig(
        tools=[types.Tool(url_context=types.UrlContext())],
        temperature=0,
    ))
    return resp.text.strip()


def call_with_grounding(prompt: str, system: str = '', model: str = 'gemini-3-flash-preview', temperature: float = 0.7) -> tuple[str, list]:
    """Google Search grounding 활성화 호출 → (텍스트, 검색출처목록) 반환"""
    from google.genai import types
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    resp = _generate(model, full_prompt, types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=temperature,
    ))

    # 실제 검색 사용 여부 확인
    sources = []
    if hasattr(resp, 'candidates') and resp.candidates:
        for candidate in resp.candidates:
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                meta = candidate.grounding_metadata
                if hasattr(meta, 'grounding_chunks') and meta.grounding_chunks:
                    for chunk in meta.grounding_chunks:
                        if hasattr(chunk, 'web') and chunk.web:
                            sources.append({
                                'title': getattr(chunk.web, 'title', ''),
                                'url': getattr(chunk.web, 'uri', ''),
                            })

    return resp.text.strip(), sources


def call_video(youtube_url: str, prompt: str, model: str = 'gemini-3-flash-preview', temperature: float = 0.4) -> str:
    """유튜브 URL을 Gemini가 직접 시청하고 분석 → 텍스트 반환.
    자막+화면+썸네일을 한 번에 봄. 18키 폴백(할당량 초과 시 다음 키) 그대로 적용.
    2026-07-04: yt-dlp(로컬전용·시각불가) 대신 이걸로 서버단독 해체 가능함을 검증."""
    from google.genai import types
    contents = types.Content(parts=[
        types.Part(file_data=types.FileData(file_uri=youtube_url, mime_type='video/*')),
        types.Part(text=prompt),
    ])
    try:
        resp = _generate(model, contents, types.GenerateContentConfig(temperature=temperature))
    except Exception as e:
        # INVALID_ARGUMENT = Gemini가 이 영상을 가져오지 못함(임베드/지역/연령 제한, 멤버십,
        # 비공개 등 영상 소유자·유튜브 측 제약). 영상 길이·해상도 무관하게 발생 — 모델을 바꿔도
        # 동일. 날것의 400 대신 원인을 알려준다.
        if "INVALID_ARGUMENT" in str(e):
            raise RuntimeError(
                "이 영상은 Gemini가 가져올 수 없습니다 — 임베드/지역/연령 제한, 멤버십·비공개 영상일 수 있어요. "
                "다른 영상으로 해체를 시도해보세요."
            ) from e
        raise
    return resp.text.strip()


def _parse_json_text(text: str) -> dict:
    """```json 블록/잡텍스트 섞인 응답에서 JSON만 뽑아 파싱."""
    import json, re
    text = re.sub(r'```(?:json)?\s*', '', text).strip('`').strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]+\}', text)
        if m:
            return json.loads(m.group())
        raise


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
