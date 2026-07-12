"""VMake(vmake.ai) 자막제거 API 어댑터.

이 파일이 VMake API의 불확실한 부분(엔드포인트·서명·폴링 스펙)을 전부 가둔다.
나머지 코드는 remove_subtitles(video_path, api_key) -> clean_path 만 본다.

⚠️ 실제 엔드포인트/서명 알고리즘/폴링 스펙은 개발자 문서(로그인 뒤)로 확정 예정.
현재는 조사 기반 추정값. 문서 확보 시 _API_BASE / _sign / submit·poll만 교체하면 된다.
"""
import hashlib
import hmac

_API_BASE = "https://open.vmake.ai/api/v1"   # ⚠️ 추정 — 문서로 확정


def _sign(app_key, secret, timestamp, nonce):
    """서명 문자열 생성(결정적). ⚠️ 실제 알고리즘은 문서로 확정 — 지금은
    HMAC-SHA256(secret, app_key+timestamp+nonce)로 가정."""
    msg = f"{app_key}{timestamp}{nonce}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def _auth_headers(app_key, secret, timestamp, nonce):
    """VMake 서명 인증 헤더 4종."""
    return {
        "X-App-Key": app_key,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Sign": _sign(app_key, secret, timestamp, nonce),
    }


import time
import urllib.request


def _split_key(api_key):
    """대시보드 등록 키는 'app_key:secret' 형식으로 저장(VMake 발급 형태 추정).
    콜론 없으면 app_key=secret=키 전체로 폴백."""
    if ":" in api_key:
        app, secret = api_key.split(":", 1)
        return app, secret
    return api_key, api_key


def _request(method, path, api_key, **kw):
    """VMake REST 호출(서명 헤더 부착) → JSON dict. ⚠️ 실패 시 응답 본문을
    예외 메시지에 담아 원인을 삼키지 않는다(지난 exit255 교훈)."""
    import secrets as _secrets
    import requests
    app, secret = _split_key(api_key)
    ts = str(int(time.time()))
    nonce = _secrets.token_hex(8)
    headers = _auth_headers(app, secret, ts, nonce)
    resp = requests.request(method, f"{_API_BASE}{path}", headers=headers, timeout=60, **kw)
    if resp.status_code >= 400:
        raise RuntimeError(f"VMake API {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def _submit(video_path, api_key):
    """영상 업로드+자막제거 job 제출 → job_id. ⚠️ 엔드포인트/필드 문서로 확정."""
    with open(video_path, "rb") as f:
        data = _request("POST", "/video/remove-subtitles", api_key, files={"file": f})
    return data.get("job_id") or data.get("id")


def _poll(job_id, api_key, timeout):
    """완료까지 상태 폴링 → 결과 URL. timeout(초) 초과 시 TimeoutError."""
    deadline = time.time() + timeout
    while True:
        data = _request("GET", f"/video/jobs/{job_id}", api_key)
        status = data.get("status")
        if status in ("done", "success", "completed"):
            return data.get("result_url") or data.get("output_url")
        if status in ("failed", "error"):
            raise RuntimeError(f"VMake job 실패: {data}")
        if time.time() >= deadline:
            raise TimeoutError(f"VMake job {job_id} {timeout}s 내 미완료(마지막: {status})")
        time.sleep(10)


def _download(url, dest):
    """결과 영상 다운로드 → dest 경로."""
    urllib.request.urlretrieve(url, dest)
    return str(dest)


def remove_subtitles(video_path, api_key, out_path, poll_timeout=1200):
    """video_path의 하드섭을 VMake로 제거 → out_path에 저장하고 그 경로 반환.
    api_key 없으면 ValueError. 처리 실패/타임아웃은 상위로 raise."""
    if not api_key:
        raise ValueError("VMake API 키가 등록되지 않았습니다")
    job_id = _submit(video_path, api_key)
    result_url = _poll(job_id, api_key, poll_timeout)
    return _download(result_url, out_path)
