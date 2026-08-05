"""후보 복제(/api/mix/candidate/clone) — 대본 3개를 3편으로 다 뽑기 위한 경로(2026-07-30).

사장님: "이 화면에 대본이 3개인데 3개 다 만들고 싶다".
같은 job에서 후보만 바꿔 렌더하면 출력이 work/{job_id}/final.mp4 **고정 경로**라
(mix_pipeline.run_render) 다음 렌더가 앞 영상을 덮어쓴다. 그래서 후보별로 job을 갈라
각자 자기 final.mp4를 갖게 한다.

여기서 못 박는 것:
1. 복제본이 **새 job_id**를 갖는다(= final.mp4가 갈라진다. 이게 기능의 존재 이유).
2. 대본을 **다시 생성하지 않는다** — 고른 후보 plan이 그대로 edit_plan이 된다.
3. 소스 mp4가 복제본 work로 따라온다(_resolve_sources가 찾기만 하고 재다운로드를 안 하므로,
   안 따라오면 '소스 영상을 하나도 찾지 못했습니다'로 죽는다).
4. 원본 job이 **그대로 살아 있다**(복제는 이동이 아니다).
5. 유료게이트를 우회하지 않는다(복제도 결국 렌더로 돈이 나간다).
"""
import pathlib

import pytest
from fastapi.testclient import TestClient

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _cand(idx, hook, recommended=False):
    return {"recommended": recommended, "score": 0.5,
            "story": {"hook": hook, "story_person": "나"},
            "plan": {"beats": [{"beat_idx": 0, "narration": hook,
                                "primary": {"video_id": "s0", "start": 0.0, "end": 2.0}}]}}


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    from shopping_shorts.store import Store
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    work_root = tmp_path / "mix_jobs"
    monkeypatch.setattr(app_mod, "_MIX_WORK_DIR", work_root)
    store = Store(tmp_path / "t.db")
    store.create_mix_job("SRC", ["https://x/1", "https://x/2"], 30, "free",
                         given_script="원본 대본", scene_first=True, backbone_main=1)
    store.set_mix_candidates("SRC", [_cand(0, "에이 훅"), _cand(1, "비 훅", recommended=True),
                                     _cand(2, "씨 훅")])
    store.update_mix_job("SRC", status="ready_for_review",
                         extract={"sources": [{"video_id": "s0", "full_text": "원본 분석"}]})
    # 원본 work에 소스 mp4 2개를 깔아둔다(다운로드 완료 상태 재현).
    for i in range(2):
        d = work_root / "SRC" / f"s{i}"
        d.mkdir(parents=True)
        (d / "src.mp4").write_bytes(b"\x00" * 32)
    return TestClient(app_mod.app), store, work_root


def test_clone_makes_new_job_with_chosen_script(ctx):
    client, store, _ = ctx
    d = client.post("/api/mix/candidate/clone", json={"job_id": "SRC", "index": 2}).json()
    assert d["ok"] is True
    new_id = d["job_id"]
    assert new_id != "SRC", "같은 job이면 final.mp4를 그대로 덮어쓴다 — 복제의 의미가 없다"
    job = store.get_mix_job(new_id)
    # 대본 재생성이 아니라 '고른 그 후보'가 그대로 실려야 한다.
    assert job["edit_plan"]["beats"][0]["narration"] == "씨 훅"
    assert job["edit_plan"]["candidate_index"] == 2
    # 매칭을 다시 돌리지 않는다 = 바로 리뷰/렌더로 갈 수 있는 상태.
    assert job["status"] == "ready_for_review"


def test_clone_copies_source_videos(ctx):
    """소스가 안 따라오면 _resolve_sources가 '소스 영상을 하나도 찾지 못했습니다'로 죽는다."""
    client, _, work_root = ctx
    new_id = client.post("/api/mix/candidate/clone",
                         json={"job_id": "SRC", "index": 0}).json()["job_id"]
    for i in range(2):
        assert (work_root / new_id / f"s{i}" / "src.mp4").exists()


def test_clone_does_not_copy_previous_outputs(ctx):
    """옛 final/tts/preview는 안 가져온다 — 가져오면 옛 영상이 새 작업 결과처럼 보인다."""
    client, _, work_root = ctx
    (work_root / "SRC" / "final.mp4").write_bytes(b"old")
    (work_root / "SRC" / "tts").mkdir()
    new_id = client.post("/api/mix/candidate/clone",
                         json={"job_id": "SRC", "index": 0}).json()["job_id"]
    assert not (work_root / new_id / "final.mp4").exists()
    assert not (work_root / new_id / "tts").exists()


def test_clone_keeps_original_job_intact(ctx):
    """복제는 이동이 아니다 — 원본이 살아 있어야 3편을 따로 만들 수 있다."""
    client, store, _ = ctx
    client.post("/api/mix/candidate/clone", json={"job_id": "SRC", "index": 1})
    src = store.get_mix_job("SRC")
    assert src is not None
    assert len(store.get_mix_candidates("SRC")) == 3


def test_clone_carries_candidates_and_settings(ctx):
    """복제본에서도 A/B/C 비교·전환이 되고, 백본·자막제거 등 설정이 이어진다."""
    client, store, _ = ctx
    new_id = client.post("/api/mix/candidate/clone",
                         json={"job_id": "SRC", "index": 0}).json()["job_id"]
    assert len(store.get_mix_candidates(new_id)) == 3
    job = store.get_mix_job(new_id)
    assert job["urls"] == ["https://x/1", "https://x/2"]
    assert job["backbone_main"] == 1
    assert job["given_script"] == "원본 대본"


def test_clone_carries_extract(ctx):
    """★2026-08-03 실사고(job 6c649edecdd8): extract를 안 물려줘 복제본이 원본 분석 없이
    시작했다 — 쿠팡 '화면으로 정확히' 등 extract를 읽는 후속 기능이 빈손이 된다."""
    client, store, _ = ctx
    new_id = client.post("/api/mix/candidate/clone",
                         json={"job_id": "SRC", "index": 1}).json()["job_id"]
    job = store.get_mix_job(new_id)
    assert job["extract"] == {"sources": [{"video_id": "s0", "full_text": "원본 분석"}]}


def test_three_clones_are_three_separate_jobs(ctx):
    """★목적 그 자체: A/B/C를 각각 복제하면 job 3개 = final.mp4 3개."""
    client, store, _ = ctx
    ids = {client.post("/api/mix/candidate/clone",
                       json={"job_id": "SRC", "index": i}).json()["job_id"] for i in (0, 1, 2)}
    assert len(ids) == 3
    narrations = {store.get_mix_job(j)["edit_plan"]["beats"][0]["narration"] for j in ids}
    assert narrations == {"에이 훅", "비 훅", "씨 훅"}


def test_clone_rejects_bad_index(ctx):
    client, _, _ = ctx
    assert client.post("/api/mix/candidate/clone",
                       json={"job_id": "SRC", "index": 9}).status_code == 404
    assert client.post("/api/mix/candidate/clone",
                       json={"job_id": "SRC"}).status_code == 422
    assert client.post("/api/mix/candidate/clone",
                       json={"job_id": "NOPE", "index": 0}).status_code == 404


def test_clone_is_rate_limited_like_render(ctx, monkeypatch):
    """유료게이트 우회 금지 — 복제도 결국 렌더로 돈이 나간다."""
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "check_and_count", lambda cid, kind: False)
    client, _, _ = ctx
    r = client.post("/api/mix/candidate/clone", json={"job_id": "SRC", "index": 0})
    assert r.status_code == 429
    assert r.json()["error_code"] == "daily_limit"


def test_ui_exposes_clone_button():
    """카드마다 '따로 만들기'가 있고, 카드 클릭(고르기)과 겹치지 않는다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "cloneCandidate(" in src
    assert "/api/mix/candidate/clone" in src
    body = src[src.index("async function cloneCandidate(idx){"):src.index("// ─── CANDIDATES-END")]
    assert "event.stopPropagation()" in src, "카드 클릭과 버튼 클릭이 겹친다"
    assert "WORK_ID = null" in body, "새 작업 레코드를 안 만들면 원본이 작업목록에서 사라진다"
    assert "PREVIEW_STATUS=null" in body, "새 job인데 옛 미리보기 게이트를 물고 있으면 유료단계로 샌다"
