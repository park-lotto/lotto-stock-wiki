# -*- coding: utf-8 -*-
"""내가 클론한 목소리를 성우로 쓴다 (2026-09-02 사장님 "본인이 클론한 음성을 불러다 쓸 수 있나").

★왜 공개 라이브러리로는 안 되나: `/v1/shared-voices`는 **남이 공개한** 목소리만 준다.
  내가 클론한 목소리는 내 계정에만 있어 거기 안 나온다 → 계정을 직접 읽어야 한다.
★담기(add_shared)를 하지 않는다: 이미 내 계정에 있는 것이라 복사할 이유가 없다.
★샘플 4건은 실제 TTS다 — **등록하는 본인 크레딧**으로 굽는다(그 배선이 이 파일의 핵심).
"""
from shopping_shorts import eleven_voices as ev


def test_샘플은_등록하는_사람_크레딧으로_굽는다(monkeypatch):
    """★이걸 놓치면 고객이 등록할 때마다 **사장님 크레딧**이 깎인다."""
    seen = {}

    def _fake_line(text, out, **kw):
        seen["customer_id"] = kw.get("customer_id")
        return "ok"

    import shopping_shorts.mix_pipeline as mp
    monkeypatch.setattr(mp, "synthesize_line", _fake_line)
    ev.bake_sample({"base_voice_id": "v1", "sample_file": "s.mp3",
                    "voice_settings": {}, "default_speed": 1.0}, customer_id=77)
    assert seen["customer_id"] == 77


def test_인자를_안_주면_종전대로_사장님_키(monkeypatch):
    """관리자 등록 경로는 그대로여야 한다(회귀 금지)."""
    seen = {}

    def _fake_line(text, out, **kw):
        seen["customer_id"] = kw.get("customer_id")
        return "ok"

    import shopping_shorts.mix_pipeline as mp
    monkeypatch.setattr(mp, "synthesize_line", _fake_line)
    ev.bake_sample({"base_voice_id": "v1", "sample_file": "s.mp3",
                    "voice_settings": {}, "default_speed": 1.0})
    assert seen["customer_id"] == 0


def test_register가_주인의_크레딧을_쓴다(monkeypatch):
    """register(owner_customer_id=N) → 샘플도 N의 키로. 두 값이 어긋나면 안 된다."""
    got = []
    monkeypatch.setattr(ev, "bake_sample", lambda p, customer_id=0: got.append(customer_id))

    class _S:
        def upsert_voice_preset(self, p):
            pass

    ev.register(_S(), "v9", "내 목소리", owner_customer_id=42)
    assert got and set(got) == {42}, got


def test_계정_목록은_클론도_준다(monkeypatch):
    """/v1/voices는 클론(category=cloned)을 포함해 계정의 모든 목소리를 준다."""
    class _R:
        status_code = 200

        @staticmethod
        def json():
            return {"voices": [
                {"voice_id": "a", "name": "내가 만든 목소리", "category": "cloned"},
                {"voice_id": "b", "name": "기본", "category": "premade"}]}

    monkeypatch.setattr(ev, "requests", type("Q", (), {"get": staticmethod(lambda *a, **k: _R())}))
    from shopping_shorts import tts
    monkeypatch.setattr(tts, "_api_key", lambda cid: "sk_x")
    out = ev.list_account_voices(5)
    assert out["ok"]
    assert [v["category"] for v in out["voices"]] == ["cloned", "premade"]


def test_키가_없으면_조용히_안내(monkeypatch):
    """키 없는 사람에게 예외를 던지지 않는다 — 화면이 안내를 띄운다."""
    from shopping_shorts import tts
    monkeypatch.setattr(tts, "_api_key", lambda cid: "")
    out = ev.list_account_voices(5)
    assert out["ok"] is False and out["voices"] == []
