"""Gemini에 영상 파일 자체를 입력해 제품/장면 키워드 추출 — 캡션 텍스트만 보는
tubefactory와의 차별화 핵심(설계문서 §1 참고). 전용 키 풀(comment_gen.py와 동일 패턴)."""
import json
import time
from google import genai
from google.genai import types
from shopping_shorts.config import SHORTS_GEMINI_KEYS

_MODEL = "gemini-3-flash"  # 비디오 입력 지원 모델
_EMPTY = {"keywords": {"ko": [], "en": [], "zh": []}, "category": ""}

_PROMPT = """이 영상을 보고 어떤 제품/장면을 다루는지 파악해라.

캡션(참고용, 영상 내용이 우선): {caption}

다음 JSON으로만 출력해라:
{{
  "keywords": {{
    "ko": ["핵심 키워드 3~5개, 한국어"],
    "en": ["같은 키워드의 영어 번역"],
    "zh": ["같은 키워드의 중국어(간체) 번역"]
  }},
  "category": "제품 카테고리 (예: 생활용품/홈케어, 뷰티, 주방가전 등)"
}}

키워드는 영상 속 실제 제품·행동·특징을 반영해야 한다(캡션 문구를 그대로 베끼지 말고
영상에서 실제로 보이는 것 기준). 다른 텍스트 없이 JSON만 출력."""

_client_cache = {}


def _client_for_key(key):
    if key not in _client_cache:
        _client_cache[key] = genai.Client(api_key=key)
    return _client_cache[key]


def _wait_until_active(client, file_obj, max_wait_s=60, poll_interval=2):
    waited = 0
    state = file_obj.state.name
    while state == "PROCESSING" and waited < max_wait_s:
        time.sleep(poll_interval)
        waited += poll_interval
        file_obj = client.files.get(name=file_obj.name)
        state = file_obj.state.name
    if state != "ACTIVE":
        raise RuntimeError(f"video_analysis: 파일 처리 실패(state={state})")
    return file_obj


def analyze_video(video_path, caption):
    """영상 파일 → {"keywords": {...}, "category": "..."}. 실패 시 빈 결과."""
    if not SHORTS_GEMINI_KEYS:
        raise RuntimeError("video_analysis: SHORTS_GEMINI_KEY가 설정되지 않았습니다")
    client = _client_for_key(SHORTS_GEMINI_KEYS[0])
    file_obj = None
    try:
        with open(video_path, "rb") as fh:
            file_obj = client.files.upload(file=fh, config=types.UploadFileConfig(mime_type="video/mp4"))
        file_obj = _wait_until_active(client, file_obj)
        prompt = _PROMPT.format(caption=caption or "(캡션 없음)")
        resp = client.models.generate_content(
            model=_MODEL,
            contents=[file_obj, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        data = json.loads(resp.text)
        return {
            "keywords": {
                "ko": data.get("keywords", {}).get("ko", []),
                "en": data.get("keywords", {}).get("en", []),
                "zh": data.get("keywords", {}).get("zh", []),
            },
            "category": data.get("category", ""),
        }
    except Exception:
        return dict(_EMPTY)
    finally:
        if file_obj is not None:
            try:
                client.files.delete(name=file_obj.name)
            except Exception:
                pass
