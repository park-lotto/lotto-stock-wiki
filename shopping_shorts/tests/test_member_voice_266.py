"""관제 266 — 회원 목소리 넓히기(사장님 10-26): 추천 성우(일레븐·피쉬)·세 엔진 검색 성우·타입캐스트 감정. 필재 금지 유지.
판단 주인 = tools/calcopy/engine/voices.check_tts(저장 관문 preview_request.check · 제작기 preset_make.voice_spec 이 부른다)
캐시 키 주인 = preset_make.tts_key(타입캐스트 무감정은 옛 키 그대로). 실제 유료 합성은 하지 않는다 — 합성 함수·요청은 전부 가짜."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy import preview_request as P  # noqa: E402
from tools.calcopy.engine import preset_make as PM  # noqa: E402
from tools.calcopy.engine import voices as VO  # noqa: E402

TC = "tc_6059dad0b83880769a50502f"          # 박창수
PILJAE = "tc_68257f68bc6e3c161ab5078d"
EL_RAW = "aiUUgjHa4mpHf6UenZuf"             # 일레븐 검색 성우 id 꼴(20자)
FISH_RAW = "4e118bfbb83e401c84699c09b5f08257"


# ── ① 저장 관문(check) ────────────────────────────────────────────────
@pytest.mark.parametrize("tts", [
    {"provider": "typecast", "voice_id": TC, "name": "박창수", "tempo": 1.25},
    {"provider": "typecast", "voice_id": "tc_61c2f7741330d213c238cba6", "name": "김건"},     # 명단 밖 타입캐스트(검색 성우) — 옛 판은 거절
    {"provider": "typecast", "voice_id": TC, "emotion": "angry"},
    {"provider": "typecast", "voice_id": TC, "emotion": "whisper"},
    {"provider": "elevenlabs", "voice_id": "kr-hanna-stable", "name": "한나"},               # 숏템 추천 일레븐
    {"provider": "elevenlabs", "voice_id": EL_RAW, "name": "검색 성우"},
    {"provider": "fish", "voice_id": "fs-taeho-stable", "name": "태호"},                     # 숏템 추천 피쉬
    {"provider": "fish", "voice_id": FISH_RAW, "name": "검색 성우"},
    {"provider": "typecast", "voice_id": TC, "emotion": None},                               # null = 감정 없음(설정 화면 확정 10-26)
    {"provider": "elevenlabs", "voice_id": EL_RAW, "emotion": None},                         # 타입캐스트 외 엔진도 null 은 통과
    {"provider": "fish", "voice_id": FISH_RAW, "emotion": None},
    {"voice_id": TC},                                                                        # 옛 팩(provider 없음)
    {"voice_id": "kr-mina-expressive", "name": "미나"},
])
def test_check_accepts(tts):
    assert VO.check_tts(tts) == []
    assert not [e for e in P.check({"tts": tts}, cat=_cat()) if "목소리" in e or "감정" in e]


@pytest.mark.parametrize("tts,word", [
    ({"provider": "typecast", "voice_id": PILJAE, "name": "필재"}, "쓸 수 없는"),
    ({"provider": "typecast", "voice_id": TC, "name": "필재"}, "쓸 수 없는"),                # 이름으로도
    ({"provider": "typecast", "voice_id": TC, "preset_id": "tc-piljae-natural"}, "쓸 수 없는"),
    ({"provider": "fish", "voice_id": FISH_RAW, "name": "필재"}, "쓸 수 없는"),              # 어느 provider 든
    ({"provider": "typecast", "voice_id": TC, "alternates": [{"voice_id": PILJAE}]}, "쓸 수 없는"),
    ({"provider": "elevenlabs", "voice_id": EL_RAW, "emotion": "angry"}, "타입캐스트 목소리에만"),
    ({"provider": "fish", "voice_id": FISH_RAW, "emotion": "normal"}, "타입캐스트 목소리에만"),
    ({"provider": "typecast", "voice_id": TC, "emotion": "joy"}, "모르는 감정"),
    ({"provider": "openai", "voice_id": TC}, "모르는 목소리 엔진"),
    ({"provider": "typecast", "voice_id": "kr-mina-expressive"}, "형식"),
    ({"provider": "elevenlabs", "voice_id": TC}, "형식"),
    ({"provider": "fish", "voice_id": "xyz"}, "형식"),
    ({"provider": "elevenlabs", "voice_id": "kr-nobody-stable"}, "모르는 추천 성우"),
])
def test_check_rejects(tts, word):
    errs = P.check({"tts": tts}, cat=_cat())
    assert any(word in e for e in errs), errs


def test_check_emotion_is_editable_field():
    assert "모르는 칸" not in " ".join(P.check({"tts": {"provider": "typecast", "voice_id": TC, "emotion": "sad"}}, cat=_cat()))


def _cat():
    return {"fonts": [], "caption_enter": [], "emphasis": [], "caption_mode": ["accumulate", "replace"], "voices": [], "bgm": [], "templates": []}


# ── ② 캐시 키 — 옛 키 = 새 키(타입캐스트 무감정) ─────────────────────────
def test_cache_key_compat():
    old = PM.sha(["v1", 1.25, "글"])                                   # 관제 266 전 tts()·chunk_line_starts·voice_gate 의 키
    assert PM.tts_key({"voice": "v1"}, 1.25, "글") == old
    assert PM.tts_key({"voice": "v1", "tts_provider": "typecast", "tts_emotion": None}, 1.25, "글") == old
    prov, emo = PM.voice_spec({"voice_id": TC, "emotion": "normal"}, {}, TC)       # normal = 감정 없음
    assert PM.tts_key({"voice": TC, "tts_provider": prov, "tts_emotion": emo}, 1.25, "글") == PM.sha([TC, 1.25, "글"])
    keys = {PM.tts_key({"voice": "v1", "tts_provider": p, "tts_emotion": e}, t, "글")
            for p, e, t in (("typecast", None, 1.25), ("typecast", "angry", 1.25), ("typecast", "sad", 1.25),
                            ("elevenlabs", None, 1.25), ("fish", None, 1.25), ("typecast", None, 1.3))}
    assert len(keys) == 6                                               # provider·감정·속도가 바뀌면 다른 캐시


def test_voice_spec_reads_work_voice_then_preset():
    assert PM.voice_spec({"voice_id": TC}, {}, TC) == ("typecast", None)
    assert PM.voice_spec({"voice_id": TC, "emotion": "toneup"}, {}, TC) == ("typecast", "toneup")
    assert PM.voice_spec({}, {"tts_provider": "fish"}, FISH_RAW) == ("fish", None)
    assert PM.voice_spec({"provider": "fish", "emotion": None}, {}, FISH_RAW) == ("fish", None)          # null = 감정 없음
    assert PM.voice_spec({"provider": "elevenlabs", "emotion": None}, {}, EL_RAW) == ("elevenlabs", None)
    assert PM.voice_spec({"emotion": None}, {"tts_emotion": "sad"}, TC) == ("typecast", None)          # 작품 칸 null 이 우선(감정 없음)
    assert PM.voice_spec({"voice_id": PILJAE}, {}, PILJAE) == ("typecast", None)    # 옛 작품은 제작기에서 막지 않는다(관문이 막는다)
    with pytest.raises(SystemExit):
        PM.voice_spec({"provider": "elevenlabs", "emotion": "angry"}, {}, EL_RAW)


# ── ③ provider 분기(가짜 합성) ──────────────────────────────────────────
def test_make_synth_branches(monkeypatch, tmp_path):
    calls = []
    from shopping_shorts.channelkit import providers
    from tools.calcopy.engine import narr_align as NA
    import requests

    def fake_tc(voice, tempo=None, key_file=None, **k):
        def s(text, out, role="NARR", emotion=None, intensity=None):
            calls.append(("typecast", voice, tempo, emotion, text)); Path(out).write_bytes(b"ID3")
        return s
    monkeypatch.setattr(providers, "typecast_synth", fake_tc)
    monkeypatch.setattr(NA, "eleven_direct", lambda text, vid, out, key: calls.append(("elevenlabs", vid, key, text)) or Path(out).write_bytes(b"ID3"))

    class R:
        status_code, content, text = 200, b"ID3", ""
    monkeypatch.setattr(requests, "post", lambda url, headers=None, json=None, timeout=None: calls.append(("fish", url, headers["Authorization"], json)) or R())
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-fake")
    monkeypatch.setenv("FISH_API_KEY", "fish-fake")

    PM.make_synth("typecast", TC, 1.25, "angry")("가", str(tmp_path / "a.mp3"))
    PM.make_synth("typecast", TC, 1.25, None)("나", str(tmp_path / "b.mp3"))
    PM.make_synth("elevenlabs", "kr-hanna-stable", 1.25, None)("다", str(tmp_path / "c.mp3"))
    PM.make_synth("fish", "fs-taeho-stable", 1.25, None)("라", str(tmp_path / "d.mp3"))
    assert calls[0] == ("typecast", TC, 1.25, "angry", "가")
    assert calls[1] == ("typecast", TC, 1.25, None, "나")
    assert calls[2] == ("elevenlabs", "kr-hanna-stable", "el-fake", "다")
    f = calls[3]
    assert f[1] == "https://api.fish.audio/v1/tts" and f[2] == "Bearer fish-fake"
    assert f[3]["reference_id"] == "29da56534ac84ccd81092be4359a1639" and f[3]["text"] == "라"   # fs- 프리셋 → reference_id
    with pytest.raises(ValueError):
        PM.make_synth("openai", TC, 1.0, None)


def test_make_synth_no_member_key_stops(monkeypatch, tmp_path):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("FISH_API_KEY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for p in ("elevenlabs", "fish"):
        with pytest.raises(RuntimeError, match="키가 없습니다"):
            PM.make_synth(p, EL_RAW if p == "elevenlabs" else FISH_RAW, 1.0, None)


def test_eleven_direct_accepts_search_voice(monkeypatch, tmp_path):
    """일레븐 검색 성우 id(추천 프리셋 밖) → base_voice_id 그대로 · 모델 eleven_multilingual_v2 로 요청(가짜 응답)."""
    import base64
    import urllib.request
    from tools.calcopy.engine import narr_align as NA
    seen = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"audio_base64": base64.b64encode(b"ID3").decode()}).encode()

    def fake_open(req, timeout=None):
        seen["url"], seen["body"] = req.full_url, json.loads(req.data.decode())
        return Resp()
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    NA.eleven_direct("안녕", EL_RAW, tmp_path / "x.mp3", "k")
    assert EL_RAW in seen["url"] and seen["body"]["model_id"] == "eleven_multilingual_v2"
    assert (tmp_path / "x.mp3").read_bytes() == b"ID3"


def test_tts_routes_provider_and_emotion(monkeypatch, tmp_path):
    """preset_make.tts → make_synth 에 작품의 provider·감정이 그대로 간다. 덩어리 캐시 파일 이름 = tts_key."""
    got = []

    def fake_make(prov, voice, tempo, emo):
        def s(text, out):
            got.append((prov, voice, tempo, emo, text)); Path(out).write_bytes(b"ID3")
        return s
    monkeypatch.setattr(PM, "make_synth", fake_make)
    monkeypatch.setattr(PM, "run", lambda cmd: Path(cmd[-1]).write_bytes(b"RIFF"))
    for prov, emo in (("typecast", "sad"), ("elevenlabs", None), ("fish", None)):
        w = {"voice": "v", "tts_provider": prov, "tts_emotion": emo, "lines": [{"tts": "오늘은 좋은 날."}]}
        log = {}
        PM.tts(w, {"tts_split": None, "tts_tempo": 1.2}, tmp_path / prov, None, True, log)
        assert got[-1] == (prov, "v", 1.2, emo, "오늘은 좋은 날.")
        assert (tmp_path / prov / "tts" / "chunk" / f"{PM.tts_key(w, 1.2, '오늘은 좋은 날.')}.mp3").exists()
    # 옛 캐시(타입캐스트 무감정, 옛 키 이름)가 있으면 다시 부르지 않는다
    old = tmp_path / "old" / "tts" / "chunk" / f"{PM.sha(['v', 1.2, '오늘은 좋은 날.'])}.mp3"
    old.parent.mkdir(parents=True); old.write_bytes(b"ID3")
    n = len(got)
    log = {}
    PM.tts({"voice": "v", "tts_provider": "typecast", "tts_emotion": None, "lines": [{"tts": "오늘은 좋은 날."}]},
           {"tts_split": None, "tts_tempo": 1.2}, tmp_path / "old", None, False, log)
    assert len(got) == n and log["tts"]["calls"] == 0
