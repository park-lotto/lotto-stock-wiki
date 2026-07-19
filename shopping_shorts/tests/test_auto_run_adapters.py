"""기본 단계 어댑터 — 실 엔진을 올바른 인자로 부르는지(트랙4 Task4). 엔진은 monkeypatch."""
import pytest
from shopping_shorts import auto_run
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_s1_picks_highest_score(monkeypatch, store, tmp_path):
    items = [{"shortcode": "a", "score": 0.3, "video_url": "u_a", "caption": "", "structure": {}, "full_text": "ta"},
             {"shortcode": "b", "score": 0.9, "video_url": "u_b", "caption": "", "structure": {}, "full_text": "tb"},
             {"shortcode": "c", "score": 0.5, "video_url": "u_c", "caption": "", "structure": {}, "full_text": "tc"}]
    monkeypatch.setattr(auto_run.service, "collect", lambda *a, **k: items)
    stages = auto_run.default_stages(tmp_path / "t.db", tmp_path / "work")
    ctx = {"job_id": "J1", "store": store, "results": {}, "job": {}}
    res = stages["S1"](ctx)
    assert res.output_ref == "b"                    # 최고 점수
    assert res.metrics["pick"]["shortcode"] == "b"
    assert res.metrics["cost_krw"] > 0
    assert len(res.candidates) <= 5


def test_s2_calls_generator_and_takes_first(monkeypatch, store, tmp_path):
    seen = {}

    def fake_gen(structure, full_text, *a, **k):
        seen["full_text"] = full_text
        return [{"hook": "훅1", "script": "대본1"}, {"hook": "훅2", "script": "대본2"}]
    monkeypatch.setattr(auto_run.script_generate, "generate_variations", fake_gen)
    stages = auto_run.default_stages(tmp_path / "t.db", tmp_path / "work")
    ctx = {"job_id": "J1", "store": store,
           "results": {"S1": {"metrics": {"pick": {"full_text": "원본대본", "structure": {}, "video_url": "u"}}}},
           "job": {}}
    res = stages["S2"](ctx)
    assert res.output_ref == "대본1"
    assert seen["full_text"] == "원본대본"
    assert len(res.candidates) == 2


def test_s3_creates_job_runs_mix_and_render(monkeypatch, store, tmp_path):
    calls = []
    monkeypatch.setattr(auto_run.mix_pipeline, "run_mix_job",
                        lambda jid, db, wr: calls.append(("mix", jid)))

    def fake_render(jid, db, wr):
        calls.append(("render", jid))
        store.update_mix_job(jid, status="done", video_path="/out/final.mp4")
    monkeypatch.setattr(auto_run.mix_pipeline, "run_render", fake_render)
    store.create_auto_job("J1")
    stages = auto_run.default_stages(store.db_path, tmp_path / "work")
    ctx = {"job_id": "J1", "store": store,
           "results": {"S1": {"metrics": {"pick": {"video_url": "u1"}}},
                       "S2": {"output_ref": "확정대본"}},
           "job": {}}
    res = stages["S3"](ctx)
    assert ("mix", res.metrics["mix_job_id"]) in calls
    assert ("render", res.metrics["mix_job_id"]) in calls
    assert res.output_ref == "/out/final.mp4"       # video_path
    assert store.get_auto_job("J1")["mix_job_id"] == res.metrics["mix_job_id"]
    # 실제 mix_jobs 행이 생겼다
    assert store.get_mix_job(res.metrics["mix_job_id"]) is not None
