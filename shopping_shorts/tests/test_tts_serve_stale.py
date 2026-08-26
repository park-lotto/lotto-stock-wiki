"""미리보기는 **대본과 어긋난 음성을 주지 않는다**(2026-08-19 사장님 제보).

렌더 경로는 `_synthesize_beats(skip_existing=True)`가 현재 대본의 해시 경로로
스킵을 판정해 자동으로 다시 뽑는다(test_tts_drift_resynth). 그런데 미리보기
`/api/mix/tts/{job}/{beat}`는 `beat["tts_path"]`를 **그대로** 내보내서, 대본이
갈린 비트는 옛 소리가 그대로 들렸다 — 사장님이 "tts가 우리 대본을 읽고 딴소리한다"고
본 것이 이 경로다.

조용히 틀어주면 렌더까지 가서야 알게 되므로 409로 드러낸다.
"""
from fastapi.testclient import TestClient

import shopping_shorts.app as app_mod
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    return TestClient(app_mod.app), Store(tmp_path / "t.db")


def _mp3(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"ID3fake")
    return p


def test_대본과_맞는_음성은_정상_재생(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j1", ["u"], 20, "free")
    # 해시는 _beat_tts_path 규칙 그대로 — 판단처가 하나이므로 여기서 계산해 쓴다
    import shopping_shorts.mix_pipeline as mp
    beat = {"beat_idx": 0, "narration": "정상적인 대본입니다"}
    beat["tts_path"] = mp._beat_tts_path(tmp_path, beat)
    _mp3(tmp_path, __import__("pathlib").Path(beat["tts_path"]).name)
    store.update_mix_job("j1", edit_plan={"beats": [beat]})
    r = client.get("/api/mix/tts/j1/0")
    assert r.status_code == 200, "정상 비트인데 막혔다"


def test_대본이_갈린_비트는_409로_막는다(tmp_path, monkeypatch):
    """★핵심 회귀 방어 — 여기가 깨지면 옛 소리가 다시 조용히 흘러나온다."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j1", ["u"], 20, "free")
    import shopping_shorts.mix_pipeline as mp
    from pathlib import Path
    beat = {"beat_idx": 0, "narration": "원래 대본"}
    beat["tts_path"] = mp._beat_tts_path(tmp_path, beat)
    _mp3(tmp_path, Path(beat["tts_path"]).name)
    beat["narration"] = "리라이터가 갈아치운 새 대본"     # 재합성 없이 대본만 변경
    store.update_mix_job("j1", edit_plan={"beats": [beat]})
    r = client.get("/api/mix/tts/j1/0")
    assert r.status_code == 409, "대본과 다른 음성을 그대로 내줬다"
    assert r.json().get("stale") is True


def test_옛_비해시_잡은_그대로_재생된다(tmp_path, monkeypatch):
    """2026-07-27 이전 잡(beat_0.mp3)은 판정 불가 → 막으면 옛 작업이 통째로 죽는다."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j1", ["u"], 20, "free")
    p = _mp3(tmp_path, "beat_0.mp3")
    store.update_mix_job("j1", edit_plan={"beats": [
        {"beat_idx": 0, "narration": "옛 잡 대본", "tts_path": str(p)}]})
    assert client.get("/api/mix/tts/j1/0").status_code == 200
