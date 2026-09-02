# -*- coding: utf-8 -*-
"""🎙 마지막 성우 기억 = TTS 이중 차감 차단 (2026-09-02 사장님 지시).

사장님: "처음부터 본인 TTS를 선택하게 하고 두번 차감이 안되도록 …
        마지막 본인이 세팅한 TTS를 기반으로 다음작업에도 기억될수있게"

★무엇이 문제였나 (실측 코드 경로):
  job.voice가 비면 mix_pipeline._voice_params가 _DEFAULT_VOICE(미나)로 폴백한다.
  create_mix_job은 voice를 아예 안 넣었으므로 **3단계 매칭의 1차 TTS가 항상 미나**였다.
  고객이 4단계에서 자기 성우로 바꾸면 /api/mix/voice → resynth_tts_job이 도는데
  이건 skip_existing이 **없어** 전 비트를 다시 합성한다 → 편당 TTS 2회.
  (다른 합성 3곳 mix_pipeline:2754·2861·2989는 전부 skip_existing=True라 재과금 0.)

★그래서 여기서 무엇을 지키나:
  "기억한 성우가 새 job의 voice로 실제로 들어간다"가 이 기능의 전부다.
  그게 되면 1차 TTS부터 본인 성우 → 4단계를 누를 이유가 없음 → 1회로 끝난다.
  문자열 검색이 아니라 **실제 Store를 돌려** 확인한다.
"""
import pytest
from cryptography.fernet import Fernet

from shopping_shorts import mix_pipeline
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    return Store(str(tmp_path / "t.db"))


VOICE = {"preset_id": "kr-sena-natural", "voice_id": "VID_SENA",
         "settings": {"stability": 0.4}, "speed": 1.4,
         "silence_trim": "mid", "pace_mode": True, "model_id": "eleven_v3"}


def _cid(store):
    return store.create_customer("u1", "pw")


def test_저장하고_그대로_돌려준다(store):
    cid = _cid(store)
    assert store.get_last_voice(cid) is None       # 신규 고객은 기억 없음
    store.set_last_voice(cid, VOICE)
    assert store.get_last_voice(cid) == VOICE


def test_새_job이_기억한_성우로_생성된다(store):
    """★이 테스트가 이 기능의 핵심이다 — 여기가 깨지면 이중 차감이 되살아난다."""
    cid = _cid(store)
    store.set_last_voice(cid, VOICE)
    store.create_mix_job("job_new", ["u"], 25, "free", customer_id=cid)
    assert store.get_mix_job("job_new")["voice"] == VOICE


def test_기억이_없으면_종전대로_비어있다(store):
    """신규 고객은 voice=None → _voice_params가 미나로 폴백(동작 불변)."""
    cid = _cid(store)
    store.create_mix_job("job_first", ["u"], 25, "free", customer_id=cid)
    assert store.get_mix_job("job_first")["voice"] is None


def test_기억한_성우가_실제_합성_파라미터까지_닿는다(store):
    """job.voice가 채워지는 것만으로는 부족하다 — 그 값이 TTS 파라미터로 풀려야
    1차 합성이 본인 성우로 나간다. 미나 기본값과 **다름**을 함께 확인한다."""
    cid = _cid(store)
    store.set_last_voice(cid, VOICE)
    store.create_mix_job("job_p", ["u"], 25, "free", customer_id=cid)
    voice = store.get_mix_job("job_p")["voice"]
    got = mix_pipeline._voice_params(voice)
    assert got[0] == "VID_SENA"                     # voice_id
    assert got[2] == 1.4                            # speed
    default = mix_pipeline._voice_params(None)
    assert default[0] == mix_pipeline._DEFAULT_VOICE["voice_id"]
    assert got[0] != default[0], "기억이 미나 폴백을 실제로 대체해야 한다"


def test_다시_바꾸면_최신값을_기억한다(store):
    cid = _cid(store)
    store.set_last_voice(cid, VOICE)
    v2 = dict(VOICE, preset_id="kr-mina-whisper", voice_id="VID_MINA", speed=1.0)
    store.set_last_voice(cid, v2)
    assert store.get_last_voice(cid)["voice_id"] == "VID_MINA"


def test_고객끼리_안_섞인다(store):
    a, b = store.create_customer("a", "pw"), store.create_customer("b", "pw")
    store.set_last_voice(a, VOICE)
    assert store.get_last_voice(b) is None
    store.create_mix_job("job_b", ["u"], 25, "free", customer_id=b)
    assert store.get_mix_job("job_b")["voice"] is None


def test_깨진값은_조용히_무시한다(store):
    """깨진 기억이 영상제작을 막으면 안 된다 — None으로 폴백(미나)."""
    cid = _cid(store)
    with store._conn() as c:
        c.execute("UPDATE customers SET last_voice_json=? WHERE id=?", ("{깨짐", cid))
    assert store.get_last_voice(cid) is None
    store.create_mix_job("job_bad", ["u"], 25, "free", customer_id=cid)
    assert store.get_mix_job("job_bad")["voice"] is None


def test_voice_id_없는_스냅샷은_저장하지_않는다(store):
    """voice_id가 없으면 합성이 못 도는 값이다. 저장해봐야 폴백만 늦춘다."""
    cid = _cid(store)
    store.set_last_voice(cid, {"preset_id": "x", "speed": 1.2})
    assert store.get_last_voice(cid) is None


def test_None이면_기억을_지운다(store):
    cid = _cid(store)
    store.set_last_voice(cid, VOICE)
    store.set_last_voice(cid, None)
    assert store.get_last_voice(cid) is None


def test_비로그인_cid0은_기억하지_않는다(store):
    """cid=0(레거시·비로그인)에 저장하면 전원이 한 성우를 공유하게 된다."""
    store.set_last_voice(0, VOICE)
    assert store.get_last_voice(0) is None


# ── 엔드포인트 배선 (2026-09-02) ────────────────────────────────────────────
# ★모듈 import만으로는 "라우트가 실제로 기억을 쓰는지"를 못 본다(과거 사고:
#   테스트 146개 통과 + 라이브 사용 0건). 여기서는 진짜 HTTP로 왕복시킨다.
from fastapi.testclient import TestClient          # noqa: E402
from shopping_shorts import app as appmod          # noqa: E402


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(appmod, "DB_PATH", db)
    return TestClient(appmod.app), Store(db)


def _preset(store, pid="kr-sena-natural", vid="VID_SENA"):
    store.upsert_voice_preset({
        "preset_id": pid, "name": "세나", "lang": "KR", "base_voice_id": vid,
        "voice_settings": {"stability": 0.4}, "model_id": "eleven_v3",
        "naturalize_profile": None,
    })


def test_성우적용_라우트가_기억을_남긴다(monkeypatch, tmp_path):
    """/api/mix/voice가 job.voice 저장과 **함께** 고객 기억도 남겨야 한다.
    이게 없으면 다음 작업이 또 미나로 시작해 이중 차감이 그대로다."""
    client, store = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(appmod, "resynth_tts_job", lambda *a, **k: None)  # 실합성 차단
    _preset(store)
    cid = store.create_customer("u1", "pw")
    # ★음성 키 게이트를 통과시킨다(2026-09-02). 이 테스트가 만들어질 땐 키 필수 차단이
    #   없어서 맨 고객으로 /api/mix/voice가 200이었다. 지금은 키가 없으면 402로 막는 게
    #   **정상**(사장님 확정 "v메이크랑 tts는 없으면 못하게 막아") — 이 테스트가 보려는 건
    #   게이트가 아니라 '성우 기억이 남는가'라, 통과한 상태에서 확인한다.
    #   실키 등록(add_customer_key)은 BYOK_MASTER_KEY가 있어야 해서 테스트에선 못 쓴다.
    monkeypatch.setattr(appmod.keyroute, "tts_block_reason", lambda *a, **k: None)
    store.create_mix_job("j1", ["u0"], 20, "free", customer_id=cid)
    store.update_mix_job("j1", edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
         "primary": {}, "alternates": [], "effect": "cut"}], "plagiarism_flags": []})

    r = client.post("/api/mix/voice", json={"job_id": "j1",
                                            "preset_id": "kr-sena-natural", "speed": 1.4})
    assert r.status_code == 200
    remembered = store.get_last_voice(cid)
    assert remembered and remembered["voice_id"] == "VID_SENA"
    assert remembered["speed"] == 1.4


def test_다음_작업이_그_성우로_시작한다(monkeypatch, tmp_path):
    """★전체 흐름 한 번에: 성우 적용 → 새 작업 → 1차 TTS가 이미 본인 성우.
    = 4단계를 누를 이유가 없다 = 편당 TTS 1회."""
    client, store = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(appmod, "resynth_tts_job", lambda *a, **k: None)
    _preset(store)
    cid = store.create_customer("u1", "pw")
    # ★음성 키 게이트를 통과시킨다(2026-09-02). 이 테스트가 만들어질 땐 키 필수 차단이
    #   없어서 맨 고객으로 /api/mix/voice가 200이었다. 지금은 키가 없으면 402로 막는 게
    #   **정상**(사장님 확정 "v메이크랑 tts는 없으면 못하게 막아") — 이 테스트가 보려는 건
    #   게이트가 아니라 '성우 기억이 남는가'라, 통과한 상태에서 확인한다.
    #   실키 등록(add_customer_key)은 BYOK_MASTER_KEY가 있어야 해서 테스트에선 못 쓴다.
    monkeypatch.setattr(appmod.keyroute, "tts_block_reason", lambda *a, **k: None)
    store.create_mix_job("j1", ["u0"], 20, "free", customer_id=cid)
    store.update_mix_job("j1", edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
         "primary": {}, "alternates": [], "effect": "cut"}], "plagiarism_flags": []})
    client.post("/api/mix/voice", json={"job_id": "j1", "preset_id": "kr-sena-natural"})

    store.create_mix_job("j2", ["u9"], 20, "free", customer_id=cid)   # 다음 작업
    v2 = store.get_mix_job("j2")["voice"]
    assert v2 and v2["voice_id"] == "VID_SENA"
    assert mix_pipeline._voice_params(v2)[0] != mix_pipeline._DEFAULT_VOICE["voice_id"]


def test_프리셋목록이_기억을_내려준다(monkeypatch, tmp_path):
    """화면이 성우를 미리 골라두려면 이 값이 필요하다. 없으면 자막제거 경고가
    헛나가고 고객이 4단계를 눌러 **재합성 비용**을 낸다(목적과 정반대)."""
    client, store = _client(monkeypatch, tmp_path)
    _preset(store)
    d = client.get("/api/voice-presets?lang=KR").json()
    assert "last_voice" in d, "화면 복원용 last_voice가 응답에 있어야 한다"
