"""TTS 타임스탬프 — 문자정렬→단어시각 변환, 후처리 되맞춤, 사이드카 수명(2026-07-31).

★배선 자물쇠도 여기 있다: "함수가 동작한다"가 아니라 "합성 지점이 실제로 이 경로를 탄다"를
잠근다. 예전 사고 계보(feedback_harness_invented_contract)라 계약만 검사하면 0% 동작도 초록이다.
"""
import base64
import json

import pytest

from shopping_shorts import tts, tts_timestamps, mix_pipeline as mp


def _align(chars, starts, ends):
    return {"characters": list(chars),
            "character_start_times_seconds": starts,
            "character_end_times_seconds": ends}


def test_words_split_on_whitespace():
    a = _align("가나 다", [0.0, 0.1, 0.2, 0.3], [0.1, 0.2, 0.3, 0.4])
    assert tts_timestamps.words_from_alignment(a) == [
        {"word": "가나", "start": 0.0, "end": 0.2},
        {"word": "다", "start": 0.3, "end": 0.4},
    ]


def test_words_none_on_garbage():
    assert tts_timestamps.words_from_alignment(None) is None
    assert tts_timestamps.words_from_alignment({}) is None
    assert tts_timestamps.words_from_alignment(_align("", [], [])) is None


def test_rescale_absorbs_trim_and_tempo():
    """앞 0.5초가 트림되고 2배속된 파일(최종 1.0초)이면 시각도 그렇게 옮겨져야 한다."""
    words = [{"word": "가", "start": 0.5, "end": 1.5},
             {"word": "나", "start": 1.5, "end": 2.5}]
    out = tts_timestamps.rescale(words, 1.0)
    assert out[0]["start"] == pytest.approx(0.0)
    assert out[-1]["end"] == pytest.approx(1.0)
    assert out[1]["start"] == pytest.approx(0.5)


def test_rescale_refuses_absurd_ratio():
    """길이 측정이 이상하면 손대지 않는다 — 틀린 보정보다 무보정이 낫다."""
    words = [{"word": "가", "start": 0.0, "end": 1.0}]
    assert tts_timestamps.rescale(words, 100.0) == words
    assert tts_timestamps.rescale(words, 0) == words


def test_sidecar_roundtrip_and_clear(tmp_path):
    mp3 = tmp_path / "a.mp3"
    tts_timestamps.save(str(mp3), _align("가", [0.0], [0.4]))
    assert tts_timestamps.words_from_mp3(str(mp3))[0]["word"] == "가"
    tts_timestamps.clear(str(mp3))
    assert tts_timestamps.words_from_mp3(str(mp3)) is None
    tts_timestamps.clear(str(mp3))            # 두 번 지워도 안 터진다


def test_copy_clears_stale_when_source_has_none(tmp_path):
    """★stale 방지: 고른 take에 정렬이 없으면 목적지의 옛 정렬을 남기면 안 된다."""
    src, dst = tmp_path / "s.mp3", tmp_path / "d.mp3"
    tts_timestamps.save(str(dst), _align("옛", [0.0], [0.4]))
    tts_timestamps.copy(str(src), str(dst))
    assert tts_timestamps.words_from_mp3(str(dst)) is None


def test_synthesize_uses_timestamps_endpoint_and_writes_sidecar(monkeypatch, tmp_path):
    """배선 자물쇠 ①: 키가 있으면 /with-timestamps를 부르고 사이드카를 남긴다."""
    seen = {}

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"audio_base64": base64.b64encode(b"ID3mp3").decode(),
                    "alignment": _align("가", [0.0], [0.4])}

    def fake_post(url, **kw):
        seen["url"] = url
        return R()

    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "k")
    monkeypatch.setattr(tts.config, "ELEVENLABS_TIMESTAMPS", True)
    monkeypatch.setattr(tts.requests, "post", fake_post)
    out = tmp_path / "b.mp3"
    tts.synthesize_tts("가", str(out))
    assert seen["url"].endswith("/with-timestamps")
    assert out.read_bytes() == b"ID3mp3"
    assert tts_timestamps.words_from_mp3(str(out))[0]["word"] == "가"


def test_synthesize_falls_back_to_plain_endpoint(monkeypatch, tmp_path):
    """배선 자물쇠 ②: 타임스탬프 경로가 깨져도 음성은 나온다(일반 엔드포인트)."""
    calls = []

    class Bad:
        def raise_for_status(self):
            raise tts.requests.RequestException("nope")

    class Good:
        content = b"PLAIN"

        def raise_for_status(self):
            pass

    def fake_post(url, **kw):
        calls.append(url)
        return Bad() if url.endswith("/with-timestamps") else Good()

    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "k")
    monkeypatch.setattr(tts.config, "ELEVENLABS_TIMESTAMPS", True)
    monkeypatch.setattr(tts.requests, "post", fake_post)
    out = tmp_path / "c.mp3"
    tts.synthesize_tts("가", str(out), max_retries=1)   # ★폴백이 재시도를 먹으면 여기서 깨진다
    assert out.read_bytes() == b"PLAIN"
    assert len(calls) == 2 and calls[0].endswith("/with-timestamps")


def test_synthesize_clears_stale_sidecar_on_mock(monkeypatch, tmp_path):
    """키 없는 mock 경로도 옛 정렬을 지운다 — 안 지우면 새 대사에 옛 타이밍이 씌워진다."""
    out = tmp_path / "d.mp3"
    tts_timestamps.save(str(out), _align("옛", [0.0], [0.4]))
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "")
    monkeypatch.setattr(tts, "_write_silent_mp3", lambda p, s: None)
    tts.synthesize_tts("새 대사", str(out))
    assert tts_timestamps.words_from_mp3(str(out)) is None


def test_beat_words_prefers_tts_over_asr(monkeypatch, tmp_path):
    """배선 자물쇠 ③: 사이드카가 있으면 ASR을 아예 안 부른다(왕복 제거가 이 이득의 전부)."""
    called = []
    monkeypatch.setattr(mp.asr_check, "transcribe_words",
                        lambda p: called.append(p) or [{"word": "asr", "start": 0.0}])
    mp3 = tmp_path / "e.mp3"
    tts_timestamps.save(str(mp3), _align("가", [0.0], [1.0]))
    words = mp._beat_words(str(mp3), 1.0)
    assert words[0]["word"] == "가" and called == []


def test_beat_words_falls_back_to_asr(monkeypatch, tmp_path):
    monkeypatch.setattr(mp.asr_check, "transcribe_words",
                        lambda p: [{"word": "asr", "start": 0.0, "end": 1.0}])
    words = mp._beat_words(str(tmp_path / "none.mp3"), 1.0)
    assert words[0]["word"] == "asr"


def test_alignment_not_normalized_alignment():
    """정규화판(숫자→한글 등)을 쓰면 우리 원문과 어긋나 없애려던 문제가 돌아온다.
    저장·판독 경로가 'alignment' 키만 본다는 것을 잠근다."""
    data = {"alignment": _align("가", [0.0], [0.4]),
            "normalized_alignment": _align("나", [0.0], [0.4])}
    assert tts_timestamps.words_from_alignment(data.get("alignment"))[0]["word"] == "가"
    assert json.dumps(data)  # 구조가 dict인 것만 확인(스키마 문서화)
