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
