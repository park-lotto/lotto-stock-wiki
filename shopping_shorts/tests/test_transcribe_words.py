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


def test_pathlib_path_is_accepted_and_filename_is_str(monkeypatch, tmp_path):
    """★회귀(2026-09-05 서버 실측): Path를 그대로 files의 파일명에 넣으면 requests가
    .translate()를 불러 AttributeError → 전사 0/30. 파일명은 basename str이어야 한다.
    기존 테스트가 전부 str로 넘겨 이 버그를 놓쳤다."""
    monkeypatch.setattr(ac.config, "GROQ_API_KEY", "k", raising=False)
    mp3 = tmp_path / "seg.mp3"; mp3.write_bytes(b"ID3")
    seen = {}

    class _Resp:
        status_code = 200
        def json(self):
            return {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}

    def _post(url, **kw):
        name = kw["files"]["file"][0]
        seen["name"] = name
        name.translate(str.maketrans("", ""))   # requests가 실제로 하는 일
        return _Resp()

    monkeypatch.setattr(ac.requests, "post", _post)
    out = ac.transcribe_words(mp3, language=None)      # ★Path 그대로
    assert out == [{"word": "hi", "start": 0.0, "end": 0.2}]
    assert seen["name"] == "seg.mp3"                   # basename만, str
    assert ac.last_error() == ""
