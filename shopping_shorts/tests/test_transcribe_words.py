"""transcribe_words — Whisper verbose_json 워드 타임스탬프. 키 없으면 None(graceful)."""
import shopping_shorts.asr_check as ac


def test_no_key_returns_none(monkeypatch):
    monkeypatch.setattr(ac.config, "GROQ_API_KEY", "", raising=False)
    assert ac.transcribe_words("x.mp3") is None


def test_parses_word_list(monkeypatch, tmp_path):
    monkeypatch.setattr(ac.config, "GROQ_API_KEY", "k", raising=False)
    mp3 = tmp_path / "a.mp3"; mp3.write_bytes(b"ID3")

    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"words": [{"word": "귤은", "start": 0.0, "end": 0.4},
                              {"word": "손으로", "start": 0.4, "end": 0.9}]}

    monkeypatch.setattr(ac.requests, "post", lambda *a, **k: _Resp())
    out = ac.transcribe_words(str(mp3))
    assert out == [{"word": "귤은", "start": 0.0, "end": 0.4},
                   {"word": "손으로", "start": 0.4, "end": 0.9}]


def test_malformed_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(ac.config, "GROQ_API_KEY", "k", raising=False)
    mp3 = tmp_path / "a.mp3"; mp3.write_bytes(b"ID3")

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"text": "no words here"}   # 워드 없음

    monkeypatch.setattr(ac.requests, "post", lambda *a, **k: _Resp())
    assert ac.transcribe_words(str(mp3)) is None


def test_exception_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(ac.config, "GROQ_API_KEY", "k", raising=False)
    mp3 = tmp_path / "a.mp3"; mp3.write_bytes(b"ID3")
    def _boom(*a, **k): raise RuntimeError("net")
    monkeypatch.setattr(ac.requests, "post", _boom)
    assert ac.transcribe_words(str(mp3)) is None
