"""제작소 성우 카드에 튜닝 작업대의 임시 프리셋이 새면 안 된다.

★사장님이 라이브 화면을 보라고 해서 브라우저로 직접 열어보니 카드 목록 맨 아래에
`kr-test`·`kr-snap`이 성우처럼 떠 있었다(2026-07-17 실측). 이름도 설명도 샘플도 없는
껍데기다. 정체는 튜닝 작업대 저장 API(app.py:1526)가 만드는 `origin="tuned"` 행으로,
`prune_voice_presets`가 **의도적으로** 안 지운다(작업대엔 그 행이 필요하다 — 리뷰 S2).
DB에 남는 것 자체는 맞고, **제작소 카드 목록에 나오는 게 틀렸다.**

내가 앞서 이걸 "DB에만 남는 것"으로 보고 넘긴 게 잘못이었다 — 화면을 직접 보니 드러났다.
"""
from fastapi.testclient import TestClient

from shopping_shorts.app import app


def _row(pid, gid, origin, variant="stable", name=None):
    return {"preset_id": pid, "group_id": gid, "variant": variant,
            "name": name or gid, "one_liner": "설명", "lang": "KR", "archetype": "형",
            "base_voice_id": "v1", "voice_settings": {}, "default_speed": 1.5,
            "default_silence_trim": "mid", "sample_file": f"{pid}.mp3",
            "best": gid == "kr-mina", "origin": origin}


def _client(monkeypatch, rows):
    monkeypatch.setattr(
        "shopping_shorts.app.Store",
        lambda *a, **k: type("S", (), {"list_voice_presets": lambda s, lang=None: rows})())
    return TestClient(app)


def test_tuned_presets_do_not_appear_as_voice_cards(monkeypatch):
    """origin='tuned'는 카드에서 빠진다 — 사장님이 고르는 목록에 껍데기가 있으면 안 된다."""
    rows = [_row("kr-mina-stable", "kr-mina", "curated", name="미나"),
            _row("kr-test", "kr-test", "tuned"),
            _row("kr-snap", "kr-snap", "tuned")]
    d = _client(monkeypatch, rows).get("/api/voice-presets?lang=KR").json()
    gids = [g["group_id"] for g in d["groups"]]
    assert gids == ["kr-mina"], f"튜닝 임시 프리셋이 샜다: {gids}"


def test_curated_presets_still_appear(monkeypatch):
    """거르기가 과해서 진짜 성우까지 지우면 안 된다(반대편 봉인)."""
    rows = [_row("kr-mina-stable", "kr-mina", "curated", name="미나"),
            _row("kr-mina-whisper", "kr-mina", "curated", variant="whisper", name="미나"),
            _row("kr-han-stable", "kr-han", "curated", name="한")]
    d = _client(monkeypatch, rows).get("/api/voice-presets?lang=KR").json()
    assert [g["group_id"] for g in d["groups"]] == ["kr-mina", "kr-han"]
    assert set(d["groups"][0]["variants"]) == {"stable", "whisper"}


def test_origin_missing_is_treated_as_curated(monkeypatch):
    """origin이 없는 옛 행(마이그레이션 전)을 조용히 숨기면 성우가 통째로 사라진다.

    거르기의 실패 방향을 '보이는 쪽'으로 잡는다 — 안 보이는 실패는 아무도 못 잡는다.
    """
    r = _row("kr-mina-stable", "kr-mina", "curated", name="미나")
    del r["origin"]
    d = _client(monkeypatch, [r]).get("/api/voice-presets?lang=KR").json()
    assert [g["group_id"] for g in d["groups"]] == ["kr-mina"]
