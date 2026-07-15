import tempfile
from pathlib import Path
from shopping_shorts import tts, video_assemble


def test_synthesize_without_key_writes_mock(monkeypatch):
    """ffmpeg 없이도(CI 안전) mock 경로가 올바른 길이로 subprocess를 호출하는지 검증."""
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "")

    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        # 실제 ffmpeg 대신 out_path에 더미 바이트만 써서 "파일 존재"를 재현
        out_path = cmd[-1]
        with open(out_path, "wb") as f:
            f.write(b"fake-mp3-bytes")

        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(tts.subprocess, "run", fake_run)

    out = Path(tempfile.mkdtemp()) / "b.mp3"
    ret = tts.synthesize_tts("안녕하세요", str(out))
    assert ret == str(out)
    assert out.exists() and out.stat().st_size > 0  # mock 무음이라도 파일 존재
    assert "ffmpeg" in calls["cmd"][0]
    assert "anullsrc" in calls["cmd"][calls["cmd"].index("-i") + 1]
    # "안녕하세요" 5글자 / 5자초 = 1.0초 → min clamp(1.0)과 동일
    assert calls["cmd"][calls["cmd"].index("-t") + 1] == "1.00"


def test_synthesize_without_key_real_ffmpeg_produces_probeable_mp3(monkeypatch):
    """실제 ffmpeg로 무음 mock을 만들고 video_assemble._probe_duration으로
    duration>0을 확인한다(핵심 회귀: 예전 16바이트 stub은 ffprobe가 못 읽었음)."""
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "")
    text = "안녕하세요 이것은 테스트 문장입니다"  # 17자 → 17/5=3.4초 추정
    out = Path(tempfile.mkdtemp()) / "real.mp3"
    ret = tts.synthesize_tts(text, str(out))
    assert ret == str(out)
    assert out.exists() and out.stat().st_size > 0

    dur = video_assemble._probe_duration(str(out))
    assert dur > 0
    assert abs(dur - tts._estimate_seconds(text)) < 1.0  # 근사치 허용오차


def test_estimate_seconds_clamped():
    assert tts._estimate_seconds("") == tts._MIN_MOCK_SEC
    assert tts._estimate_seconds("가" * 3) == tts._MIN_MOCK_SEC  # 3/5=0.6 → clamp 1.0
    assert tts._estimate_seconds("가" * 1000) == tts._MAX_MOCK_SEC  # clamp 15.0
    assert tts._estimate_seconds("가" * 25) == 5.0  # 25/5=5.0, 범위 내


def test_synthesize_with_key_calls_api(monkeypatch):
    calls = {}

    class FakeResp:
        status_code = 200
        content = b"ID3fakebytes"
        def raise_for_status(self): pass

    def fake_post(url, **kw):
        calls["url"] = url
        calls["json"] = kw.get("json")
        calls["headers"] = kw.get("headers")
        return FakeResp()

    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.setattr(tts.config, "ELEVENLABS_VOICE_ID", "voiceX")
    monkeypatch.setattr(tts.requests, "post", fake_post)

    out = Path(tempfile.mkdtemp()) / "b.mp3"
    tts.synthesize_tts("테스트 문장", str(out))
    assert "voiceX" in calls["url"]
    assert calls["json"]["text"] == "테스트 문장"
    assert calls["headers"]["xi-api-key"] == "sk-test"
    assert out.read_bytes() == b"ID3fakebytes"


def test_synthesize_sends_voice_settings_and_speed(monkeypatch):
    calls = {}

    class FakeResp:
        content = b"ID3fake"
        def raise_for_status(self): pass

    def fake_post(url, **kw):
        calls["json"] = kw.get("json")
        return FakeResp()

    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.setattr(tts.requests, "post", fake_post)

    import tempfile
    from pathlib import Path
    out = Path(tempfile.mkdtemp()) / "b.mp3"
    tts.synthesize_tts(
        "테스트", str(out), voice_id="vX",
        voice_settings={"stability": 0.65, "similarity_boost": 0.75,
                        "style": 0.0, "use_speaker_boost": True},
        speed=1.1, model_id="eleven_multilingual_v2",
    )
    vs = calls["json"]["voice_settings"]
    assert vs["stability"] == 0.65
    assert vs["style"] == 0.0
    assert vs["use_speaker_boost"] is True
    assert vs["speed"] == 1.1
    assert calls["json"]["model_id"] == "eleven_multilingual_v2"


def test_synthesize_speed_clamped_to_api_range(monkeypatch):
    calls = {}

    class FakeResp:
        content = b"ID3"
        def raise_for_status(self): pass

    def fake_post(url, **kw):
        calls["json"] = kw.get("json")
        return FakeResp()

    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.setattr(tts.requests, "post", fake_post)

    import tempfile
    from pathlib import Path
    out = Path(tempfile.mkdtemp()) / "b.mp3"
    tts.synthesize_tts("x", str(out), voice_id="v", speed=1.5)
    assert calls["json"]["voice_settings"]["speed"] == 1.2


def test_v3_drops_speaker_boost(monkeypatch):
    """v3 모델이면 payload에서 use_speaker_boost 자동 제거."""
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "k")
    captured = {}
    class R:
        content = b"x"
        def raise_for_status(self): pass
    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return R()
    monkeypatch.setattr(tts.requests, "post", fake_post)
    import tempfile; from pathlib import Path
    out = Path(tempfile.mkdtemp()) / "b.mp3"
    tts.synthesize_tts("안녕", str(out), model_id="eleven_v3",
                       voice_settings={"stability": 0.5, "use_speaker_boost": True})
    assert "use_speaker_boost" not in captured["json"]["voice_settings"]

def test_v3_drops_continuity(monkeypatch):
    """v3면 previous_text/next_text를 payload에서 제거한다.

    회귀: v3는 이 필드를 '무시'하는 게 아니라 400을 던진다(2026-07-15 실측) —
    'Providing previous_text or next_text is not yet supported with the eleven_v3 model'.
    호출부(mix_pipeline·작업대)는 늘 인접 비트를 넘기므로 여기서 안 막으면 합성이 통째로 죽는다.
    seed는 v3에서도 지원되므로 남아야 한다."""
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "k")
    captured = {}
    class R:
        content = b"x"
        def raise_for_status(self): pass
    monkeypatch.setattr(tts.requests, "post",
                        lambda url, headers=None, json=None, timeout=None: (captured.update(json=json) or R()))
    import tempfile; from pathlib import Path
    out = Path(tempfile.mkdtemp()) / "v3c.mp3"
    tts.synthesize_tts("안녕", str(out), model_id="eleven_v3", seed=7,
                       previous_text="앞", next_text="뒤")
    assert "previous_text" not in captured["json"]
    assert "next_text" not in captured["json"]
    assert captured["json"]["seed"] == 7


def test_continuity_and_seed_in_payload(monkeypatch):
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "k")
    captured = {}
    class R:
        content = b"x"
        def raise_for_status(self): pass
    monkeypatch.setattr(tts.requests, "post",
                        lambda url, headers=None, json=None, timeout=None: (captured.update(json=json) or R()))
    import tempfile; from pathlib import Path
    out = Path(tempfile.mkdtemp()) / "b.mp3"
    tts.synthesize_tts("안녕", str(out), seed=7, previous_text="앞", next_text="뒤")
    assert captured["json"]["seed"] == 7
    assert captured["json"]["previous_text"] == "앞"
    assert captured["json"]["next_text"] == "뒤"

def test_backward_compat_no_extra_keys(monkeypatch):
    """seed/연속성 미지정 시 payload에 해당 키 없음(회귀)."""
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "k")
    captured = {}
    class R:
        content = b"x"
        def raise_for_status(self): pass
    monkeypatch.setattr(tts.requests, "post",
                        lambda url, headers=None, json=None, timeout=None: (captured.update(json=json) or R()))
    import tempfile; from pathlib import Path
    out = Path(tempfile.mkdtemp()) / "b.mp3"
    tts.synthesize_tts("안녕", str(out))
    for k in ("seed", "previous_text", "next_text"):
        assert k not in captured["json"]


def test_synthesize_best_picks_by_ranker(monkeypatch):
    """N개 합성 후 ranker 점수 최소 take 선택. 각 take는 seed를 달리해 호출."""
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "k")
    seeds_seen = []
    def fake_synth(text, out_path, **kw):
        seeds_seen.append(kw.get("seed"))
        with open(out_path, "wb") as f:
            f.write(b"x")
        return out_path
    monkeypatch.setattr(tts, "synthesize_tts", fake_synth)
    import tempfile; from pathlib import Path
    d = Path(tempfile.mkdtemp())
    # ranker: 경로 끝 숫자가 작을수록 좋음 → take0(_0) 선택
    best = tts.synthesize_best("안녕", str(d / "b.mp3"), n=3, base_seed=10,
                               ranker=lambda path, text: int(path.split("_")[-1].split(".")[0]))
    assert best == str(d / "b.mp3")            # 최종 픽은 out_path로 복사
    assert len(seeds_seen) == 3                # 3회 합성
    assert seeds_seen == [10, 11, 12]          # seed 증분

def test_synthesize_best_n1_single_call(monkeypatch):
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "k")
    calls = {"n": 0}
    def fake_synth(text, out_path, **kw):
        calls["n"] += 1
        with open(out_path, "wb") as f: f.write(b"x")
        return out_path
    monkeypatch.setattr(tts, "synthesize_tts", fake_synth)
    import tempfile; from pathlib import Path
    out = Path(tempfile.mkdtemp()) / "b.mp3"
    tts.synthesize_best("안녕", str(out), n=1)
    assert calls["n"] == 1
