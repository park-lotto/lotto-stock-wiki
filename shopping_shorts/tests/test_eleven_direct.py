# -*- coding: utf-8 -*-
"""회원 PC 미나 = 회원 일레븐랩스 키로 직접(narr_align.eleven_direct, 사장님 10-21) — 요청 꼴이 서버 서비스(shopping_shorts/tts.py)와 같은가."""
import base64
import io
import json
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import narr_align as N  # noqa: E402


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_request_shape_and_alignment(tmp_path, monkeypatch):
    seen = {}

    def fake(req, timeout=0):
        seen["url"], seen["key"], seen["body"] = req.full_url, req.get_header("Xi-api-key"), json.loads(req.data)
        return _Resp(json.dumps({"audio_base64": base64.b64encode(b"ID3fake").decode(), "alignment": {"characters": ["가"]}}).encode())
    monkeypatch.setattr("urllib.request.urlopen", fake)
    out = tmp_path / "a.mp3"
    al = N.eleven_direct("안녕하세요.", "kr-mina-expressive", out, "sk_test")
    assert seen["url"] == "https://api.elevenlabs.io/v1/text-to-speech/aiUUgjHa4mpHf6UenZuf/with-timestamps"
    assert seen["key"] == "sk_test" and seen["body"]["model_id"] == "eleven_v3" and "use_speaker_boost" not in seen["body"].get("voice_settings", {})
    assert out.read_bytes() == b"ID3fake" and al == {"characters": ["가"]}


def test_errors_are_korean(tmp_path, monkeypatch):
    def fake(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 401, "x", {}, None)
    monkeypatch.setattr("urllib.request.urlopen", fake)
    try:
        N.eleven_direct("가.", "kr-mina-expressive", tmp_path / "a.mp3", "bad")
    except RuntimeError as e:
        assert "키가 맞지 않습니다" in str(e)
    else:
        raise AssertionError("401 이 올라오지 않았다")


def test_customer_without_key_stops_with_fix(tmp_path, monkeypatch):
    monkeypatch.setenv("CALCOPY_CUSTOMER_MODE", "1")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    try:
        N._synth_eleven("가.", "kr-mina-expressive", 1.35, tmp_path / "a.mp3", "k", "m", print)
    except RuntimeError as e:
        assert "일레븐랩스 키가 필요합니다" in str(e)
    else:
        raise AssertionError("키 없이 넘어갔다")


def _raise_with(status, message, code=401):
    def fake(req, timeout=0):
        body = io.BytesIO(json.dumps({"detail": {"status": status, "message": message}}).encode())
        raise urllib.error.HTTPError(req.full_url, code, "x", {}, body)
    return fake


def _why(tmp_path, monkeypatch, status, message):
    monkeypatch.setattr("urllib.request.urlopen", _raise_with(status, message))
    try:
        N.eleven_direct("가.", "kr-mina-expressive", tmp_path / "a.mp3", "sk_x")
    except RuntimeError as e:
        return str(e)
    raise AssertionError("오류가 안 올라왔다")


def test_401_은_일레븐_상태로_갈라_말한다(tmp_path, monkeypatch):
    """11-04 김미화 #4038 payment_issue · 11-03 박준영 #3698 missing_permissions — 키는 맞는데 '키가 맞지 않습니다'로 시작해 엉뚱한 곳을 보게 했다."""
    w = _why(tmp_path, monkeypatch, "payment_issue", "Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.")
    assert not w.startswith("일레븐랩스 키가 맞지 않습니다") and "결제" in w and "payment_issue" in w
    w = _why(tmp_path, monkeypatch, "missing_permissions", "The API key you used is missing the permission text_to_speech to execute this operation.")
    assert not w.startswith("일레븐랩스 키가 맞지 않습니다") and "권한" in w and "missing_permissions" in w
    w = _why(tmp_path, monkeypatch, "detected_unusual_activity", "Unusual activity detected. Free Tier usage disabled.")
    assert not w.startswith("일레븐랩스 키가 맞지 않습니다") and "유료" in w
    w = _why(tmp_path, monkeypatch, "invalid_api_key", "Invalid API key")
    assert w.startswith("일레븐랩스 키가 맞지 않습니다")
