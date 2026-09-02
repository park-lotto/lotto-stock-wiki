# -*- coding: utf-8 -*-
"""TTS 관측이 **분모**를 갖는지, 그리고 상대가 말한 사유를 남기는지.

★왜(2026-09-02 실사고): tts.py가 실패만 기록해서 api_events에 성공이 한 건도 없었다.
  경보는 실패/(실패+성공)으로 실패율을 내는데 분모가 실패뿐이라 **항상 100%**가 됐다.
  사장님이 "elevenlabs 최근 1시간 실패율 100% (14/14건)" 경보를 보고 사고로 판단했지만,
  실제로는 그 시간의 완성 mp3가 mean_volume -15~-18dB로 **소리가 정상**이었다
  (409가 나도 재시도로 넘어갔다). 거짓 경보는 진짜 사고를 가린다.

★그리고 실패에 응답 본문이 없어 "409 Client Error: Conflict"만 남았다 —
  일레븐랩스가 왜 거절했는지 알 길이 없으니 처방도 정할 수 없었다.
"""
import io
import os
import re

_SRC = os.path.join(os.path.dirname(__file__), "..", "tts.py")


def _src():
    return io.open(_SRC, encoding="utf-8").read()


def test_성공도_기록한다_분모가_있어야_실패율이_참이다():
    s = _src()
    assert "ok=True" in s, "성공을 안 남기면 실패율이 항상 100%가 된다"
    # 두 엔진 모두 — 한쪽만 세면 분모가 또 어긋난다
    assert s.count("ok=True") >= 3, (
        "일레븐랩스(타임스탬프/일반)와 타입캐스트 성공 지점이 모두 기록돼야 한다")
    for engine in ('"elevenlabs", None, ok=True', '"typecast", None, ok=True'):
        assert engine in s, f"{engine} 경로가 성공을 안 남긴다"


def test_실패에_응답본문을_담는다():
    s = _src()
    i = s.index("def _record_tts_event(")
    body = s[i:i + 2600]
    assert "resp.text" in body, "상대가 말한 사유(응답 본문)를 안 남기면 원인을 못 정한다"
    assert "[:200]" in body, "본문은 잘라 담아야 원장이 부풀지 않는다"
    assert "detail=detail" in body, "모아둔 detail을 실제로 넘겨야 기록에 남는다"


def test_관측이_본작업을_죽이지_않는다():
    """기록은 어디까지나 곁다리다 — 실패해도 음성 합성은 계속돼야 한다."""
    s = _src()
    i = s.index("def _record_tts_event(")
    body = s[i:i + 2600]
    assert body.count("except Exception") >= 2, "본문 읽기·기록 둘 다 감싸야 한다"
    assert "pass" in body


def test_무음폴백_기록은_그대로_남아있다():
    """키가 없어 무음 mp3로 내려앉는 건 여전히 사각의 핵심이다 — 지우지 마라."""
    s = _src()
    assert "OUT_SILENT" in s and "silent=True" in s
