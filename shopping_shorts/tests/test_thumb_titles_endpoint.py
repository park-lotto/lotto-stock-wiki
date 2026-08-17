"""POST /api/produce/thumb/titles — 화면 대본 우선 + 대본↔job 불일치 경고 (2026-07-24).

사고: 바나나 팬케이크 영상인데 며칠 전 '밥솥 식빵' job 대본이 남아 제목이 밥솥으로 나왔다.
job.given_script는 매칭 시점에 고정되므로, 프런트가 보내는 '화면 대본'을 우선 쓴다.
"""
from fastapi.testclient import TestClient

import shopping_shorts.app as app_mod
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    return TestClient(app_mod.app)


def _make_job(tmp_path, job_id, given_script):
    st = Store(str(tmp_path / "t.db"))
    st.create_mix_job(job_id, ["https://x/a"], 30, "free", given_script=given_script)


def test_screen_script_overrides_stale_job_script(monkeypatch, tmp_path):
    """화면 대본이 오면 job의 옛 대본 대신 그걸로 제목을 만들고, 다르면 mismatch=True."""
    seen = {}

    def fake_generate(job, seed=0):      # seed=참고 훅 회전(2026-08-18 추가)
        seen["script"] = job.get("given_script")
        return [{"text": "바나나\n팬케이크", "why": "호기심"}]

    monkeypatch.setattr(app_mod.thumb_title, "generate", fake_generate)
    _make_job(tmp_path, "job1", given_script="아니 식빵 절대 사먹지 마세요 밥솥에서")
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/produce/thumb/titles",
               json={"job_id": "job1", "script": "바나나 팬케이크 진짜 쉬워요"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["titles"]
    assert seen["script"] == "바나나 팬케이크 진짜 쉬워요"   # 화면 대본으로 지었다
    assert d["script_mismatch"] is True                      # 옛 job 대본과 다르다 → 경고


def test_no_screen_script_falls_back_to_job(monkeypatch, tmp_path):
    """화면 대본이 없으면 job 대본을 쓰고, 불일치도 없다(경고 안 뜸)."""
    seen = {}
    monkeypatch.setattr(app_mod.thumb_title, "generate",
                        lambda job, seed=0: (seen.update(script=job.get("given_script")) or
                                             [{"text": "밥솥\n식빵", "why": "반전"}]))
    _make_job(tmp_path, "job2", given_script="밥솥 식빵 대본")
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/produce/thumb/titles", json={"job_id": "job2"})
    assert r.status_code == 200
    assert seen["script"] == "밥솥 식빵 대본"
    assert r.json()["script_mismatch"] is False


def test_empty_both_scripts_returns_422(monkeypatch, tmp_path):
    """job 대본도 화면 대본도 없으면 예시를 베끼지 말고 422로 막는다."""
    monkeypatch.setattr(app_mod.thumb_title, "generate",
                        lambda job: (_ for _ in ()).throw(AssertionError("생성 호출되면 안 됨")))
    _make_job(tmp_path, "job3", given_script=None)
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/produce/thumb/titles", json={"job_id": "job3", "script": "  "})
    assert r.status_code == 422
