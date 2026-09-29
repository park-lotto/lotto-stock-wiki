"""Higgsfield API의 최소 안전 어댑터.

첫 파일럿은 Seedance 2.0 image-to-video 한 경로만 연다. 모델·해상도·길이를
화면 입력으로 그대로 받지 않는 이유는 관리자 시험 중에도 API 비용이 실제로 나가기
때문이다. 자격증명은 서버 환경변수에서만 읽고 응답에는 절대 싣지 않는다.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


BASE_URL = "https://api.higgsfield.ai"
MODEL_ID = "bytedance/seedance-2.0/image-to-video"
MODEL_URL = f"{BASE_URL}/{MODEL_ID}"
DURATION = 5
RESOLUTION = "720p"
GENERATE_AUDIO = False
ESTIMATED_USD_PER_SECOND = 0.0985


class HiggsfieldError(RuntimeError):
    """사용자에게 비밀값 없이 보여줄 수 있는 공급자 오류."""


def _credentials(credentials=None):
    if credentials:
        text = str(credentials).strip()
        if ":" not in text:
            return "", ""
        return tuple(part.strip() for part in text.split(":", 1))
    key_id = (os.getenv("HIGGSFIELD_API_KEY_ID") or os.getenv("HF_API_KEY_ID") or "").strip()
    secret = (os.getenv("HIGGSFIELD_API_KEY_SECRET") or os.getenv("HF_API_KEY_SECRET") or "").strip()
    return key_id, secret


def configured(credentials=None):
    key_id, secret = _credentials(credentials)
    return bool(key_id and secret)


def estimated_usd():
    return round(ESTIMATED_USD_PER_SECOND * DURATION, 4)


def _headers(credentials=None):
    key_id, secret = _credentials(credentials)
    if not key_id or not secret:
        raise HiggsfieldError(
            "Higgsfield API 키가 없습니다. 서버에 HIGGSFIELD_API_KEY_ID와 "
            "HIGGSFIELD_API_KEY_SECRET를 등록하세요."
        )
    return {
        "Authorization": f"Key {key_id}:{secret}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def validate_public_https_url(value, *, provider_only=False):
    """비밀 자격증명·내부 주소가 외부로 새지 않도록 URL을 제한한다."""
    value = (value or "").strip()
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise HiggsfieldError("주소 형식이 올바르지 않습니다.") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HiggsfieldError("공개 HTTPS 주소만 사용할 수 있습니다.")
    host = parsed.hostname.lower().rstrip(".")
    if provider_only and host != "api.higgsfield.ai":
        raise HiggsfieldError("Higgsfield 공식 상태 주소가 아닙니다.")
    if host == "localhost" or host.endswith(".local"):
        raise HiggsfieldError("내부망 주소는 사용할 수 없습니다.")
    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            candidates = {
                ipaddress.ip_address(info[4][0])
                for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError) as exc:
            raise HiggsfieldError("주소를 확인할 수 없습니다.") from exc
    if any(not ip.is_global for ip in candidates):
        raise HiggsfieldError("내부망 주소는 사용할 수 없습니다.")
    return value


def _json_response(response):
    try:
        data = response.json()
    except ValueError as exc:
        raise HiggsfieldError("Higgsfield가 JSON이 아닌 응답을 보냈습니다.") from exc
    if response.status_code >= 400:
        message = ""
        if isinstance(data, dict):
            message = str(data.get("message") or data.get("error") or data.get("detail") or "")
        suffix = f": {message[:300]}" if message else ""
        raise HiggsfieldError(f"Higgsfield 요청 실패({response.status_code}){suffix}")
    if not isinstance(data, dict):
        raise HiggsfieldError("Higgsfield 응답 형식이 올바르지 않습니다.")
    return data


def _find_video_url(data):
    """SDK/REST 응답 모양이 달라도 video URL 한 값을 찾는다."""
    if not isinstance(data, dict):
        return None
    video = data.get("video")
    if isinstance(video, str) and video.startswith("https://"):
        return video
    if isinstance(video, dict):
        url = video.get("url")
        if isinstance(url, str) and url.startswith("https://"):
            return url
    for key in ("result", "output", "data", "response"):
        found = _find_video_url(data.get(key))
        if found:
            return found
    for key in ("video_url", "output_url", "url"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith("https://"):
            return value
    return None


def _normalise(data, request_id=None, status_url=None):
    rid = str(data.get("request_id") or data.get("id") or request_id or "").strip()
    raw_status = str(data.get("status") or data.get("state") or "").lower().strip()
    video_url = _find_video_url(data)
    if video_url:
        state = "done"
    elif raw_status in {"completed", "complete", "succeeded", "success", "done", "ready"}:
        state = "done"
    elif raw_status in {"failed", "error", "cancelled", "canceled"}:
        state = "failed"
    else:
        state = "running"
    supplied_status = data.get("status_url") or data.get("statusUrl") or status_url
    if supplied_status:
        supplied_status = validate_public_https_url(str(supplied_status), provider_only=True)
    elif rid:
        supplied_status = f"{BASE_URL}/requests/{rid}/status"
    error = data.get("error") or data.get("failure_message") or data.get("message")
    if isinstance(error, dict):
        error = error.get("message") or str(error)
    return {
        "request_id": rid,
        "status_url": supplied_status,
        "state": state,
        "video_url": video_url,
        "error": str(error or "")[:500],
        "raw": data,
    }


def submit_image_to_video(image_url, prompt="", *, credentials=None, post=requests.post):
    image_url = validate_public_https_url(image_url)
    payload = {
        "image_url": image_url,
        "prompt": (prompt or "").strip(),
        "duration": DURATION,
        "resolution": RESOLUTION,
        "generate_audio": GENERATE_AUDIO,
    }
    response = post(MODEL_URL, headers=_headers(credentials), json=payload, timeout=45)
    result = _normalise(_json_response(response))
    if result["state"] != "done" and not result["request_id"]:
        raise HiggsfieldError("Higgsfield 응답에 작업번호가 없습니다.")
    return result


def wait_for_result(submission, *, credentials=None, get=requests.get, sleep=time.sleep,
                    timeout_seconds=900, poll_seconds=5):
    """비동기 요청을 완료까지 기다린다. 최종 응답에 URL이 없으면 result를 한 번 조회."""
    current = dict(submission)
    if current.get("state") == "done" and current.get("video_url"):
        return current
    deadline = time.monotonic() + timeout_seconds
    status_url = current.get("status_url")
    request_id = current.get("request_id")
    if not status_url:
        raise HiggsfieldError("Higgsfield 상태 확인 주소가 없습니다.")
    validate_public_https_url(status_url, provider_only=True)
    while time.monotonic() < deadline:
        response = get(status_url, headers=_headers(credentials), timeout=30)
        current = _normalise(_json_response(response), request_id=request_id,
                             status_url=status_url)
        if current["state"] == "failed":
            raise HiggsfieldError(current["error"] or "Higgsfield 영상 생성이 실패했습니다.")
        if current["state"] == "done":
            if current.get("video_url"):
                return current
            result_url = f"{BASE_URL}/requests/{request_id}/result"
            response = get(result_url, headers=_headers(credentials), timeout=30)
            current = _normalise(_json_response(response), request_id=request_id,
                                 status_url=status_url)
            if current.get("video_url"):
                return current
            raise HiggsfieldError("완료 응답에 영상 주소가 없습니다.")
        sleep(poll_seconds)
    raise HiggsfieldError("Higgsfield 생성이 15분 안에 끝나지 않았습니다.")


def download_video(video_url, destination, *, get=requests.get, max_bytes=300 * 1024 * 1024):
    """공급자 임시 URL을 우리 저장소로 옮긴다. 부분 파일은 성공 전까지 노출하지 않는다."""
    video_url = validate_public_https_url(video_url)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    total = 0
    try:
        with get(video_url, stream=True, timeout=(20, 180)) as response:
            if response.status_code >= 400:
                raise HiggsfieldError(f"완성 영상 다운로드 실패({response.status_code})")
            with partial.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise HiggsfieldError("완성 영상이 300MB 제한을 넘었습니다.")
                    fh.write(chunk)
        if total == 0:
            raise HiggsfieldError("완성 영상 파일이 비어 있습니다.")
        partial.replace(destination)
    finally:
        if partial.exists():
            partial.unlink()
    return destination
