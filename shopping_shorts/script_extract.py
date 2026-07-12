"""Gemini 멀티모달로 영상에서 대본 세그먼트(타임코드+텍스트+장면묘사) 추출.

나레이션 음성과 화면 자막을 구분하지 않고 통합 추출한다(설계 §3-1). 전용 키 풀
(SHORTS_GEMINI_KEYS)만 사용 — comment_gen의 로테이션 재사용, 공유 풀 폴백 금지
(2026-07-09 확정). seg_id는 모델이 아니라 코드가 {video_id}-{n}로 부여해 하류
EDL(edit_plan.py)의 참조 무결성을 보장한다.

(구 transcribe_gemini.py를 대체·흡수 — 그쪽은 공유풀(key_vault.get_client)을 써서
컨벤션 위반이었음. 폐기는 Task 8에서.)
"""
import json
import sys
import time

from google.genai import types

from pipeline.atoms import key_vault
from shopping_shorts import comment_gen
from shopping_shorts.config import SHORTS_GEMINI_KEYS
from shopping_shorts.video_analysis import _MODEL, _wait_until_active

_EMPTY = {"segments": [], "full_text": ""}

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "text": {"type": "string"},
                    "scene_desc": {"type": "string"},
                },
                "required": ["start", "end", "text", "scene_desc"],
            },
        },
        "full_text": {"type": "string"},
    },
    "required": ["segments", "full_text"],
}

_PROMPT = """이 영상을 보고 시간 순서대로 세그먼트로 나눠 대본을 추출해라.

캡션(참고용, 영상 내용이 우선): {caption}

각 세그먼트는 화면이 크게 바뀌거나 말의 주제가 바뀌는 단위로 끊어라. 세그먼트마다:
- start, end: 영상 내 시작/끝 시각(초, 숫자)
- text: 그 구간에서 **실제로 들리는 나레이션**(없으면 화면 자막 문구). **한 단어도 빠짐없이 들리는 그대로 받아써라. 요약·의역·생략 절대 금지.** 말이 빠르거나 뭉개져도 최대한 정확히 받아쓰고, 확실치 않은 부분도 가장 근접한 표기로 채워라(빈칸으로 두지 마라). 화면에 자막이 있으면 자막과 음성을 **교차 확인**해 더 정확한 쪽으로 보정하라.
- scene_desc: 그 구간 화면에 무엇이 보이는지 짧게(제품/행동/구도)

full_text에는 모든 세그먼트의 text를 순서대로 이어붙여라. 한 단어도 빠짐없이 완전히 이어붙이고, 다른 텍스트는 없이 JSON만 출력."""


def _assign_seg_ids(video_id, raw_segments):
    """모델이 준 세그먼트 목록에 seg_id 부여 + 숫자 필드 float 캐스팅(순수함수)."""
    out = []
    for n, seg in enumerate(raw_segments):
        out.append({
            "seg_id": f"{video_id}-{n}",
            "start": float(seg.get("start") or 0.0),
            "end": float(seg.get("end") or 0.0),
            "text": seg.get("text", ""),
            "scene_desc": seg.get("scene_desc", ""),
        })
    return out


def extract_script(video_path, video_id, caption="", max_retries=4, quota_sleep=8):
    """영상 파일 → {"segments": [...seg_id 포함...], "full_text": str}. 실패 시 빈 결과.

    전용 키 풀 로테이션(comment_gen 재사용). 전용 풀 소진 시 빈 결과."""
    if not SHORTS_GEMINI_KEYS:
        raise RuntimeError("script_extract: SHORTS_GEMINI_KEY가 설정되지 않았습니다")
    prompt = _PROMPT.format(caption=caption or "(캡션 없음)")

    for attempt in range(max_retries):
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            return dict(_EMPTY)
        client = comment_gen._client_for_key(key)
        file_obj = None
        try:
            with open(video_path, "rb") as fh:
                file_obj = client.files.upload(file=fh, config=types.UploadFileConfig(mime_type="video/mp4"))
            file_obj = _wait_until_active(client, file_obj)
            resp = client.models.generate_content(
                model=_MODEL,
                contents=[file_obj, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                ),
            )
            data = json.loads(resp.text)
            return {
                "segments": _assign_seg_ids(video_id, data.get("segments", [])),
                "full_text": data.get("full_text", ""),
            }
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                time.sleep(quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            print(f"script_extract: 미분류 오류로 빈 결과 반환 — {e!r}", file=sys.stderr)
            return dict(_EMPTY)
        finally:
            if file_obj is not None:
                try:
                    client.files.delete(name=file_obj.name)
                except Exception:
                    pass
    return dict(_EMPTY)
