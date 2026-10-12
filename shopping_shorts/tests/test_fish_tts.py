"""Fish Audio TTS 엔진(2026-10-05, 관제 123) — 판정·본문·키 정책·기본 성우·엔진 분기."""
import pytest

from shopping_shorts import config, fish_tts, keyroute, tts, voice_presets


class _Store:
    """keys_for/has_own_key가 쓰는 최소 스텁 — {(cid, svc): [keys]}."""
    def __init__(self, own=None):
        self.own = own or {}

    def get_customer_keys_plain(self, cid, svc):
        return list(self.own.get((cid, svc), []))


@pytest.fixture
def store(monkeypatch):
    st = _Store()
    monkeypatch.setattr("shopping_shorts.store.Store", lambda *a, **k: st)
    monkeypatch.setattr(config, "FISH_API_KEY", "OWNER-KEY")
    monkeypatch.setattr(config, "FISH_ENABLED", True)
    return st


def test_is_fish_판정():
    assert fish_tts.is_fish("fish-s2.1-pro-free")
    assert fish_tts.is_fish("FISH-s1")
    assert not fish_tts.is_fish("ssfm-v30")
    assert not fish_tts.is_fish("eleven_v3")
    assert not fish_tts.is_fish(None)
    assert fish_tts.api_model("fish-s2.1-pro-free") == "s2.1-pro-free"
    assert voice_presets.engine_of("fish-s2.1-pro-free") == "fish"
    assert voice_presets.engine_of("ssfm-v30") == "typecast"
    assert voice_presets.engine_of("eleven_v3") == "elevenlabs"


def test_build_payload():
    b = fish_tts.build_payload("[curious] 안녕하세요", "abc")
    assert b == {"text": "안녕하세요", "reference_id": "abc", "format": "mp3"}
    assert "prosody" not in fish_tts.build_payload("x", "a", speed=1.0)
    assert fish_tts.build_payload("x", "a", speed=3)["prosody"] == {"speed": 2.0}
    h = fish_tts.headers("K", "fish-s2.1-pro-free")
    assert h["Authorization"] == "Bearer K" and h["model"] == "s2.1-pro-free"


def test_회원은_사장님키로_폴백하지_않는다(store):
    assert fish_tts.api_key(999) == ""                       # 회원 키 없음 → 빈 값(폴백 없음)
    store.own[(999, keyroute.SVC_FISH)] = ["MEMBER"]
    assert fish_tts.api_key(999) == "MEMBER"
    assert fish_tts.api_key(0) == "OWNER-KEY"                # 사장님은 회사 키


def test_키없는_회원은_안내문으로_실패(store, monkeypatch):
    called = []
    monkeypatch.setattr(fish_tts.requests, "post", lambda *a, **k: called.append(1))
    with pytest.raises(RuntimeError) as e:
        tts.synthesize_tts("문장", "x.mp3", voice_id="v", model_id="fish-s2.1-pro-free", customer_id=999)
    assert "Fish 무료 키" in str(e.value) and "키를 등록해야" in str(e.value)
    assert not called


def test_tts_block_reason_fish(store):
    assert keyroute.tts_block_reason(store, 999, "fish-s2.1-pro-free")[0] == "need_own_key"
    store.own[(999, keyroute.SVC_FISH)] = ["K"]
    assert keyroute.tts_block_reason(store, 999, "fish-s2.1-pro-free") is None
    assert keyroute.tts_block_reason(store, 999, None) is None   # Fish 키만 있어도 음성 통과


def test_TTS키_없는_회원_기본성우는_Fish(store):
    assert fish_tts.use_fish_default("eleven_v3", 999)
    assert fish_tts.use_fish_default(None, 999)
    assert not fish_tts.use_fish_default("fish-s2.1-pro-free", 999)   # 이미 Fish
    assert not fish_tts.use_fish_default(None, 0)                      # 사장님
    store.own[(999, keyroute.SVC_ELEVENLABS)] = ["E"]
    assert not fish_tts.use_fish_default("eleven_v3", 999)             # 키 등록 회원은 종전대로


def test_FISH_ENABLED_0이면_일레븐으로_대체(store, monkeypatch):
    monkeypatch.setattr(config, "FISH_ENABLED", False)
    assert fish_tts.use_fallback("fish-s2.1-pro-free")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        raise fish_tts.requests.RequestException("stop")
    monkeypatch.setattr(tts, "_api_key", lambda cid=0: "ELEVEN")
    monkeypatch.setattr(tts.requests, "post", fake_post)
    monkeypatch.setattr(tts.time, "sleep", lambda s: None)
    monkeypatch.setattr(tts, "_record_tts_event", lambda *a, **k: None)
    with pytest.raises(Exception):
        tts.synthesize_tts("문장", "x.mp3", voice_id="v", model_id="fish-s2.1-pro-free", max_retries=1)
    assert "elevenlabs" in seen["url"]


def test_엔진분기_fish로_나간다(store, monkeypatch, tmp_path):
    seen = {}

    class R:
        status_code = 200
        content = b"ID3fakemp3"
        text = ""

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json)
        return R()
    monkeypatch.setattr(fish_tts.requests, "post", fake_post)
    monkeypatch.setattr(tts, "_record_tts_event", lambda *a, **k: None)
    out = tmp_path / "a.mp3"
    tts.synthesize_tts("안녕", str(out), voice_id="abc", model_id="fish-s2.1-pro-free", customer_id=0)
    assert seen["url"] == "https://api.fish.audio/v1/tts"
    assert seen["headers"]["model"] == "s2.1-pro-free"
    assert seen["json"]["reference_id"] == "abc"
    assert out.read_bytes() == b"ID3fakemp3"


def test_프리셋_8명_샘플_있음():
    rows = [r for r in voice_presets.load_presets_file() if fish_tts.is_fish(r.get("model_id"))]
    assert [r["name"] for r in rows] == ["하늘", "소연", "다인", "정숙", "태호", "민준", "도윤", "지성"]
    for r in rows:
        assert (voice_presets.SAMPLES_DIR / r["sample_file"]).exists()
    assert fish_tts.FISH_DEFAULT_VOICE["voice_id"] == rows[0]["base_voice_id"]
