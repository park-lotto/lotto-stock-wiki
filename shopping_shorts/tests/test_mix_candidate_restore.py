"""후보 카드 복원(2026-07-30 사장님 "완료까지 갔다 오면 대본 생성된 게 다 리셋된다").

리셋이 아니라 **표시 누락**이었다. 후보는 job_id별로 DB에 그대로 남아 있는데
(mix_pipeline의 set_mix_candidates), 새 매칭 경로(pollMix)만 renderCandidates를 부르고
다른 단계 갔다 돌아오는 복원 경로(_restoreMixContext)엔 그 호출이 빠져 있었다.

여기서 못 박는 것:
1. /api/mix/candidate가 고른 index를 edit_plan에 새긴다(컬럼 추가 없이 복원 가능하게).
2. /api/mix/status가 그 선택(selected_index)과 후보 목록을 함께 내려준다.
3. produce.html의 _restoreMixContext가 status를 읽어 renderCandidates를 부른다(JS 소스 검증).
"""
import pathlib

import pytest
from fastapi.testclient import TestClient

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _cand(idx, hook, recommended=False):
    return {"recommended": recommended, "score": 0.5 + idx / 100,
            "story": {"hook": hook, "story_person": "나"},
            "plan": {"beats": [{"beat_idx": 0, "narration": hook,
                                "primary": {"video_id": "v1", "start": 0.0, "end": 2.0}}]}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    from shopping_shorts.store import Store
    store = Store(tmp_path / "t.db")
    store.create_mix_job("J1", ["https://x/1"], 30, "template")
    store.set_mix_candidates("J1", [_cand(0, "에이 훅"), _cand(1, "비 훅", recommended=True),
                                    _cand(2, "씨 훅")])
    store.update_mix_job("J1", status="ready_for_review")
    return TestClient(app_mod.app)


def test_status_lists_candidates_with_no_selection_yet(client):
    """아직 아무것도 안 골랐으면 selected_index는 None — 프론트가 recommended를 따른다."""
    d = client.get("/api/mix/status/J1").json()
    assert d["ok"] is True
    assert [c["index"] for c in d["candidates"]] == [0, 1, 2]
    assert d["selected_index"] is None


def test_pick_persists_selected_index(client):
    """후보를 고르면 그 index가 job에 남아, 새로고침·단계이동 뒤에도 복원된다."""
    assert client.post("/api/mix/candidate", json={"job_id": "J1", "index": 2}).json()["ok"]
    d = client.get("/api/mix/status/J1").json()
    assert d["selected_index"] == 2
    # 후보 목록 자체는 그대로 — 고른다고 나머지가 지워지지 않는다(사장님이 걱정한 '리셋').
    assert len(d["candidates"]) == 3


def test_candidates_survive_switching_back_and_forth(client):
    """A→C→A로 오가도 후보 3개가 계속 살아 있다(고르기는 edit_plan 교체일 뿐)."""
    for idx in (0, 2, 0):
        assert client.post("/api/mix/candidate", json={"job_id": "J1", "index": idx}).json()["ok"]
        d = client.get("/api/mix/status/J1").json()
        assert len(d["candidates"]) == 3
        assert d["selected_index"] == idx


def test_pick_still_sets_edit_plan_for_render(client, tmp_path):
    """candidate_index를 새기는 게 렌더용 plan(beats)을 망가뜨리지 않는다."""
    client.post("/api/mix/candidate", json={"job_id": "J1", "index": 2})
    from shopping_shorts.store import Store
    plan = Store(tmp_path / "t.db").get_mix_job("J1")["edit_plan"]
    assert plan["candidate_index"] == 2
    assert plan["beats"][0]["narration"] == "씨 훅"


def test_restore_path_redraws_candidate_cards():
    """★뿌리 회귀 못박기: _restoreMixContext가 후보를 다시 그리는가.

    이게 빠져 있어서 사장님 눈엔 '대본이 리셋'으로 보였다. 함수 본문 안에 status 조회와
    renderCandidates 호출이 둘 다 있어야 한다.
    """
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    start = src.index("async function _restoreMixContext(){")
    body = src[start:src.index("function _consumeProduceHandoff(", start)]
    assert "/api/mix/status/" in body, "복원 경로가 후보를 조회하지 않는다"
    assert "renderCandidates(" in body, "복원 경로가 후보 카드를 다시 그리지 않는다"
    assert "selected_index" in body, "복원 경로가 고른 후보를 되살리지 않는다"
