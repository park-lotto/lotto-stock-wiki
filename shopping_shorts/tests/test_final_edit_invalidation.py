from pathlib import Path

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _done_job(tmp_path, job_id="j1"):
    db = tmp_path / "test.db"
    store = Store(db)
    store.create_mix_job(job_id, ["https://example.com/video"], 20, "free")
    plan = {
        "beats": [{
            "beat_idx": 0,
            "narration": "같은 대본",
            "target_seconds": 2.0,
            "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
        }]
    }
    store.update_mix_job(
        job_id,
        status="done",
        edit_plan=plan,
        video_path=str(tmp_path / "final.mp4"),
        clean_video_path=str(tmp_path / "final_clean.mp4"),
        fx_status="done",
        fx_path=str(tmp_path / "final_fx.mp4"),
        cta_cut_sec=1.5,
    )
    return store


def test_zoom_after_final_marks_old_video_stale(tmp_path):
    """박세현님 재현: 완성 뒤 장면 확대 저장은 옛 final.mp4를 더는 완성본으로 내주지 않는다."""
    store = _done_job(tmp_path)

    result = app_module._scenezoom_locked(
        store, "j1", {"beat_idx": 0, "zoom": 1.6, "pan_x": 0.1, "pan_y": -0.1}
    )

    assert result["ok"] is True
    saved = store.get_mix_job("j1")
    assert saved["edit_plan"]["beats"][0]["scene_zoom"] == 1.6
    assert saved["status"] == "ready_for_review"
    assert saved["video_path"] is None
    assert saved["clean_video_path"] is None
    assert saved["fx_path"] is None
    assert saved["fx_status"] is None
    assert saved["cta_cut_sec"] is None


def test_same_edit_does_not_discard_valid_final(tmp_path):
    """장면 실험실 자동저장이 같은 값을 다시 보내도 멀쩡한 완성본을 지우지 않는다."""
    store = _done_job(tmp_path)
    plan = store.get_mix_job("j1")["edit_plan"]

    changed = app_module._save_render_inputs(store, "j1", edit_plan=plan)

    saved = store.get_mix_job("j1")
    assert changed is False
    assert saved["status"] == "done"
    assert saved["video_path"].endswith("final.mp4")


def test_caption_and_deco_inputs_invalidate_but_seo_does_not(tmp_path):
    store = _done_job(tmp_path)
    plan = store.get_mix_job("j1")["edit_plan"]
    plan["beats"][0]["cap_xy"] = {"x_pct": 50, "y_pct": 20}
    assert app_module._save_render_inputs(store, "j1", edit_plan=plan) is True
    assert store.get_mix_job("j1")["video_path"] is None

    store = _done_job(tmp_path, "j2")
    assert app_module._save_render_inputs(store, "j2", headcopy={"text": "새 카피"}) is True
    assert store.get_mix_job("j2")["status"] == "ready_for_review"

    store = _done_job(tmp_path, "j3")
    assert app_module._save_render_inputs(store, "j3", seo={"title": "새 제목"}) is False
    assert store.get_mix_job("j3")["status"] == "done"
    assert store.get_mix_job("j3")["video_path"].endswith("final.mp4")


def test_thumbnail_only_invalidates_when_intro_image_changes(tmp_path):
    store = _done_job(tmp_path)
    store.update_mix_job("j1", thumbnail={"intro": False, "results": ["a.png"]})
    assert app_module._save_render_inputs(
        store, "j1", thumbnail={"intro": False, "results": ["a.png", "b.png"]}
    ) is False
    assert store.get_mix_job("j1")["status"] == "done"

    # 인트로 ON + 미선택이면 마지막 결과가 실제 영상에 붙으므로 새 PNG 저장도 렌더 입력 변경이다.
    store.update_mix_job("j1", thumbnail={"intro": True, "results": ["a.png"]})
    assert app_module._save_render_inputs(
        store, "j1", thumbnail={"intro": True, "results": ["a.png", "b.png"]}
    ) is True
    assert store.get_mix_job("j1")["status"] == "ready_for_review"
    assert store.get_mix_job("j1")["video_path"] is None


def test_non_done_job_never_serves_leftover_final_path(tmp_path):
    store = _done_job(tmp_path)
    job = store.get_mix_job("j1")
    job["status"] = "ready_for_review"
    assert "다시" in app_module._video_gone_reason(job)


def test_final_panel_rechecks_server_and_removes_cached_video():
    html = (Path(app_module.__file__).parent / "static" / "produce.html").read_text(encoding="utf-8")
    refresh = html.split("async function refreshFinal(){", 1)[1].split("async function shareVideo", 1)[0]
    idle = html.split("function _finalIdleSlot(){", 1)[1].split("async function renderFinal", 1)[0]

    assert "fv.querySelector('video')" not in refresh
    assert "fetch('/api/mix/status/'" in refresh
    assert "!fv.querySelector('video')" not in idle
