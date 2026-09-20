"""EvoLink 비동기 영상 생성 API 어댑터.

API 키는 서버 환경변수/.env에서만 읽고 프론트엔드로 보내지 않는다.
공식 흐름: 생성 요청 -> task id -> 상태 조회 -> 완료 URL 즉시 로컬 저장.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests


BASE_URL = os.environ.get("EVOLINK_BASE_URL", "https://api.evolink.ai").rstrip("/")
DEFAULT_MODEL = "wan2.7-text-to-video"
MODELS = (
    {"id": "wan2.7-text-to-video", "name": "Wan 2.7 · 균형형"},
    {"id": "seedance-2.0-text-to-video", "name": "Seedance 2.0 · 영화형"},
)
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{6,160}$")
_ALLOWED_QUALITY = {"720p", "1080p"}
_ALLOWED_RATIO = {"16:9", "9:16", "1:1", "4:3", "3:4"}


class EvoLinkError(RuntimeError):
    """사용자에게 안전하게 보여줄 수 있는 EvoLink 호출 오류."""


def _headers(api_key: str) -> dict[str, str]:
    key = str(api_key or "").strip()
    if not key:
        raise EvoLinkError("에보링크 API 키가 없습니다. .env에 EVOLINK_API_KEY를 등록하세요.")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        data = {}
    message = data.get("message") or data.get("error") or response.text
    if isinstance(message, dict):
        message = message.get("message") or message.get("code") or ""
    message = str(message or "").strip()[:300]
    if response.status_code in (401, 403):
        return "에보링크 API 키가 올바르지 않거나 권한이 없습니다."
    if response.status_code == 402:
        return "에보링크 잔액이 부족합니다."
    if response.status_code == 429:
        return "에보링크 요청 한도에 도달했습니다. 잠시 후 다시 시도하세요."
    return f"에보링크 요청 실패(HTTP {response.status_code})" + (f": {message}" if message else "")


def _request(method: str, path: str, api_key: str, **kwargs) -> dict:
    try:
        response = requests.request(
            method, f"{BASE_URL}{path}", headers=_headers(api_key), timeout=30, **kwargs
        )
    except requests.RequestException as exc:
        raise EvoLinkError(f"에보링크 서버에 연결하지 못했습니다: {exc}") from exc
    if not response.ok:
        raise EvoLinkError(_error_message(response))
    try:
        data = response.json()
    except ValueError as exc:
        raise EvoLinkError("에보링크 응답이 JSON 형식이 아닙니다.") from exc
    if not isinstance(data, dict):
        raise EvoLinkError("에보링크 응답 형식이 올바르지 않습니다.")
    return data


def create_video(
    *, api_key: str, prompt: str, model: str = DEFAULT_MODEL, duration: int = 5,
    quality: str = "720p", aspect_ratio: str = "16:9", generate_audio: bool = False,
) -> dict:
    prompt = str(prompt or "").strip()
    if not prompt:
        raise EvoLinkError("AI 영상에 사용할 장면 설명이 필요합니다.")
    if len(prompt) > 5000:
        raise EvoLinkError("장면 설명은 5,000자 이하만 가능합니다.")
    model_ids = {row["id"] for row in MODELS}
    if model not in model_ids:
        raise EvoLinkError("지원하지 않는 에보링크 영상 모델입니다.")
    if quality not in _ALLOWED_QUALITY:
        raise EvoLinkError("화질은 720p 또는 1080p만 가능합니다.")
    if aspect_ratio not in _ALLOWED_RATIO:
        raise EvoLinkError("지원하지 않는 화면 비율입니다.")
    if not 2 <= int(duration) <= 15:
        raise EvoLinkError("영상 길이는 2~15초만 가능합니다.")

    payload = {
        "model": model,
        "prompt": prompt,
        "duration": int(duration),
        "quality": quality,
        "aspect_ratio": aspect_ratio,
        "prompt_extend": False,
    }
    if model.startswith("seedance-"):
        payload["generate_audio"] = bool(generate_audio)
    task = _request("POST", "/v1/videos/generations", api_key, json=payload)
    if not task.get("id"):
        raise EvoLinkError("에보링크가 작업 ID를 반환하지 않았습니다.")
    return task


def get_task(*, api_key: str, task_id: str) -> dict:
    task_id = str(task_id or "").strip()
    if not _TASK_ID_RE.fullmatch(task_id):
        raise EvoLinkError("잘못된 에보링크 작업 ID입니다.")
    return _request("GET", f"/v1/tasks/{task_id}", api_key)


def download_result(url: str, destination: str | os.PathLike, max_bytes: int = 500 * 1024 * 1024) -> int:
    """EvoLink가 반환한 결과 URL을 원자적으로 저장한다."""
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise EvoLinkError("에보링크 결과 URL이 올바르지 않습니다.")
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(dest.suffix + ".part")
    size = 0
    try:
        with requests.get(url, stream=True, timeout=(15, 120)) as response:
            if not response.ok:
                raise EvoLinkError(f"완성 영상 다운로드 실패(HTTP {response.status_code})")
            with temp.open("wb") as out:
                for chunk in response.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise EvoLinkError("완성 영상이 500MB 제한을 넘었습니다.")
                    out.write(chunk)
        os.replace(temp, dest)
        return size
    except requests.RequestException as exc:
        raise EvoLinkError(f"완성 영상을 저장하지 못했습니다: {exc}") from exc
    finally:
        if temp.exists():
            temp.unlink()
