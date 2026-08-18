"""일레븐랩스 계정 보이스 등록(eleven_voices) 검증.

실TTS·실API는 부르지 않는다 — 순수 계산(build_group)과 DB 왕복(register/delete)만 본다.
샘플 굽기는 bake=False로 끈다(켜면 크레딧을 쓴다)."""
import pytest

from shopping_shorts import eleven_voices as ev
from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_build_group_makes_four_tones_sharing_one_voice():
    rows = ev.build_group("VID123456", "미나", "차분한 여성")
    assert [r["variant"] for r in rows] == ["stable", "natural", "expressive", "whisper"]
    assert len({r["group_id"] for r in rows}) == 1          # 한 성우 = 한 그룹
    assert len({r["preset_id"] for r in rows}) == 4         # 프리셋은 4개로 갈린다
    assert all(r["base_voice_id"] == "VID123456" for r in rows)
    # 톤마다 수치가 실제로 달라야 '톤 바꿔 다시'가 의미가 있다(whisper는 이름이 판정 기준이라 동일).
    assert rows[0]["voice_settings"] != rows[1]["voice_settings"]


def test_origin_is_library_so_startup_seed_does_not_delete_it(store):
    """★prune_voice_presets는 origin='curated'만 지운다. 등록분이 curated면 재기동 때 사라진다."""
    res = ev.register(store, "VID999", "테스트성우", bake=False)
    assert res["count"] == 4
    store.prune_voice_presets(["kr-mina-stable"])            # 큐레이션 seed가 하는 일
    left = [p for p in store.list_voice_presets() if p["group_id"] == res["group_id"]]
    assert len(left) == 4


def test_delete_group_removes_only_library_rows(store):
    res = ev.register(store, "VID777", "지울성우", bake=False)
    store.upsert_voice_preset({"preset_id": "kr-mina-stable", "group_id": "kr-mina",
                               "variant": "stable", "name": "미나", "lang": "KR",
                               "base_voice_id": "M1", "origin": "curated"})
    assert store.delete_voice_group(res["group_id"]) == 4
    ids = {p["preset_id"] for p in store.list_voice_presets()}
    assert ids == {"kr-mina-stable"}                          # 큐레이션은 살아남는다
    # 큐레이션 그룹은 이 경로로 못 지운다(origin 조건이 막는다)
    assert store.delete_voice_group("kr-mina") == 0


def test_list_account_voices_without_key_is_soft_failure(monkeypatch):
    """키가 없으면 예외가 아니라 사유를 돌려준다 — 화면이 빈 목록에 이유를 띄운다."""
    from shopping_shorts import tts
    monkeypatch.setattr(tts, "_api_key", lambda cid=0: "")
    res = ev.list_account_voices(0)
    assert res["ok"] is False and res["voices"] == [] and res["error"]
