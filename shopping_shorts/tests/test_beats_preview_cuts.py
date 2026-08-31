"""장면 목록은 **컷 단위**여야 한다 (2026-08-31 사장님 "지금 6장이자나, 총 장면을 보여야
자막 안지워진것들 각각 배정할수있으니").

한 비트에 재료가 여럿 섞이면 종전엔 첫 컷만 보였다 → 나머지 컷을 손볼 방법이 없었다.
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts import mix_pipeline
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


def _multi_cut_plan():
    """한 비트가 재료 2개를 나눠 쓰는 계획(나레이션이 길어 alternates까지 화면에 나온다)."""
    return {"beats": [
        {"beat_idx": 0, "narration": "첫 칸", "target_seconds": 6.0,
         "primary": {"video_id": "s0", "start": 0.0, "end": 3.0},
         "alternates": [{"video_id": "s1", "start": 5.0, "end": 8.0}]},
        {"beat_idx": 1, "narration": "둘째 칸", "target_seconds": 2.0,
         "primary": {"video_id": "s0", "start": 10.0, "end": 12.0}},
    ]}


def test_cut_plan_really_splits_the_beat():
    """전제 확인 — final_clip_pairs가 비트 0을 컷 2개로 편다(이게 아니면 아래 테스트는 무의미)."""
    cuts = mix_pipeline.final_clip_pairs(_multi_cut_plan(), {}, {"s0": 30.0, "s1": 30.0})
    assert len([c for c in cuts if c["beat_idx"] == 0]) >= 2


def test_beats_preview_lists_every_cut(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("jc", ["u0"], 20, "free")
    store.update_mix_job("jc", status="ready_for_review", edit_plan=_multi_cut_plan())
    monkeypatch.setattr(app_module, "_final_cuts",
                        lambda job, work: mix_pipeline.final_clip_pairs(
                            job["edit_plan"], {}, {"s0": 30.0, "s1": 30.0}))
    beats = client.get("/api/produce/mix/beats_preview/jc").json()["beats"]
    # 비트는 2개지만 칸은 그보다 많다(비트 0이 컷 2개 이상)
    assert len(beats) > 2
    assert [b["i"] for b in beats] == list(range(len(beats)))
    assert all(b["total"] == len(beats) for b in beats)
    b0 = [b for b in beats if b["beat_idx"] == 0]
    assert len(b0) >= 2
    assert [b["cut"] for b in b0] == list(range(len(b0)))   # 컷 번호가 0,1,…
    assert all(b["cut_of"] == len(b0) for b0_ in [b0] for b in b0_)
    # 같은 비트의 칸들은 자막을 공유한다(자막은 비트 단위)
    assert len({b["caption"] for b in b0}) == 1
    # 컷마다 다른 소스·시각을 가리킨다 = 다른 그림
    assert len({(b["video_id"], b["cut_src"]) for b in b0}) == len(b0)


def test_beats_preview_falls_back_to_beats_when_no_cut_plan(tmp_path, monkeypatch):
    """컷 계획을 못 세우면 종전처럼 비트당 1칸(조용히 깨지지 않게)."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("jf", ["u0"], 20, "free")
    store.update_mix_job("jf", status="ready_for_review", edit_plan=_multi_cut_plan())
    monkeypatch.setattr(app_module, "_final_cuts", lambda job, work: [])
    beats = client.get("/api/produce/mix/beats_preview/jf").json()["beats"]
    assert len(beats) == 2
    assert [b["cut"] for b in beats] == [None, None]
