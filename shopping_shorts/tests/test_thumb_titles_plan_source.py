"""썸네일 제목은 '영상이 실제로 말하는 대본'(고른 후보 = edit_plan 나레이션)에서 뽑아야 한다.

사고(2026-07-26): 장면 우선 대본 모드에서 후보를 고르면 edit_plan만 세탁으로 바뀌고
given_script/화면 대본(STATE.script)은 1단계 원본(네일)으로 남는다. 예전 api/produce/thumb/titles는
그 원본(네일)을 읽어, 세탁 영상에 네일·큐티클 제목이 나왔다(사장님 실측). 제목의 진실은 edit_plan이다.
"""
import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts import thumb_title
from shopping_shorts.store import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    return TestClient(app_module.app)


def _capture_generate(monkeypatch):
    """thumb_title.generate가 실제로 받은 대본을 잡아 돌려준다."""
    captured = {}

    def fake_generate(job, seed=0):      # seed=참고 훅 회전(2026-08-18 추가)
        captured["script"] = job.get("given_script")
        return [{"text": "하얀\n비밀", "why": "호기심"}]

    monkeypatch.setattr(thumb_title, "generate", fake_generate)
    return captured


def test_titles_use_chosen_candidate_narration_not_stale_original(client, tmp_path, monkeypatch):
    """given_script(네일)·화면 대본(네일)이 옛 원본으로 남아도, 제목은 edit_plan(세탁)으로 만든다."""
    s = Store(tmp_path / "t.db")
    # 1단계 원본 = 네일(장면 우선 모드에선 후보가 소스영상에서 나와 이 값과 무관해진다)
    s.create_mix_job("j1", ["https://x/1"], 30, "free",
                     given_script="다이소 큐티클 제거 꿀템, 네일샵 원장이 쓰는 것", scene_first=True)
    # 고른 후보(edit_plan) = 영상이 실제로 말하는 대본 = 세탁/흰옷 표백
    s.update_mix_job("j1", edit_plan={"beats": [
        {"narration": "흰 빨래가 누렇게 변한 옷 고민이었죠"},
        {"narration": "세제 한 스푼 넣고 조물조물하면 하얗게 돌아와요"},
    ]})
    captured = _capture_generate(monkeypatch)

    # 화면 대본(STATE.script)도 옛 네일이 그대로 넘어오는 최악 경우를 재현
    r = client.post("/api/produce/thumb/titles",
                    json={"job_id": "j1", "script": "다이소 큐티클 제거 꿀템"})
    assert r.status_code == 200, r.text

    used = captured["script"] or ""
    assert ("빨래" in used or "세제" in used), f"영상 대본(세탁)을 써야 한다: {used!r}"
    assert ("큐티클" not in used and "네일" not in used), f"옛 원본(네일)을 쓰면 안 된다: {used!r}"


def test_titles_fallback_to_script_when_no_edit_plan(client, tmp_path, monkeypatch):
    """edit_plan이 아직 없으면(구 흐름) 예전대로 화면/원본 대본으로 폴백한다 — 회귀 방지."""
    s = Store(tmp_path / "t.db")
    s.create_mix_job("j2", ["https://x/1"], 30, "free", given_script="원본 대본")
    captured = _capture_generate(monkeypatch)

    r = client.post("/api/produce/thumb/titles",
                    json={"job_id": "j2", "script": "화면에서 고친 대본"})
    assert r.status_code == 200, r.text
    assert captured["script"] == "화면에서 고친 대본"


def test_titles_no_mismatch_warning_when_plan_used(client, tmp_path, monkeypatch):
    """edit_plan을 진실로 쓰면 제목은 이미 영상과 일치 → 오해를 부르는 mismatch 경고를 켜지 않는다."""
    s = Store(tmp_path / "t.db")
    s.create_mix_job("j3", ["https://x/1"], 30, "free",
                     given_script="네일 원본", scene_first=True)
    s.update_mix_job("j3", edit_plan={"beats": [{"narration": "세탁 대본입니다"}]})
    _capture_generate(monkeypatch)

    r = client.post("/api/produce/thumb/titles",
                    json={"job_id": "j3", "script": "네일 원본"})
    assert r.status_code == 200, r.text
    assert r.json().get("script_mismatch") is False
