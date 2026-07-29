"""수집 진행률이 job에 기록되는지 — "멈춘 건가?"를 없애는 장치.

★2026-07-27 실사고: 사장님이 50분을 기다리다 취소했다. 서버 collect_jobs를 보니
updated_at이 생성 시각에서 한 번도 안 바뀌어 있었다(진행률을 쓰는 코드가 없었음).
"""
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def test_progress_written_to_job_during_collect(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    store = Store(db)
    store.create_collect_job("J1")

    def _fake_collect(platform=None, categories=None, limit_channels=None, on_progress=None):
        on_progress(1, 3, 2, {"ok": 1, "login_wall": 0, "not_found": 0, "error": 0})
        snap = store.get_collect_job("J1")
        assert snap["status"] == "running"
        prog = snap["result"]  # get_collect_job이 result_json을 이미 dict로 파싱해 "result"에 담는다
        assert prog["phase"] == "collecting"
        assert (prog["done"], prog["total"], prog["items_so_far"]) == (1, 3, 2)
        on_progress(3, 3, 5, {"ok": 3, "login_wall": 0, "not_found": 0, "error": 0})
        return []

    monkeypatch.setattr(app_module, "collect", _fake_collect)
    monkeypatch.setattr(app_module, "_attach_vision_tags", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "generate_missing_drafts", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "next_draft_targets", lambda *a, **k: [])
    monkeypatch.setattr(app_module, "_tag_new_items", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "_translate_new_subjects", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "_bank_ingest_collected_bg", lambda *a, **k: None)

    app_module._run_collect_job("J1", "instagram", None, None, 0)
    assert store.get_collect_job("J1")["status"] == "done"


def test_tally_included_in_done_payload(monkeypatch, tmp_path):
    """★차단 비율이 결과에 남아야 부계정(B안) 필요 여부를 숫자로 판단할 수 있다."""
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    store = Store(db)
    store.create_collect_job("J2")

    monkeypatch.setattr(app_module, "collect",
                        lambda **k: [])
    monkeypatch.setattr(app_module.service, "LAST_COLLECT_TALLY",
                        {"ok": 180, "login_wall": 15, "not_found": 3, "error": 2})
    monkeypatch.setattr(app_module, "_attach_vision_tags", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "generate_missing_drafts", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "next_draft_targets", lambda *a, **k: [])
    monkeypatch.setattr(app_module, "_tag_new_items", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "_translate_new_subjects", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "_bank_ingest_collected_bg", lambda *a, **k: None)

    app_module._run_collect_job("J2", "instagram", None, None, 0)
    payload = store.get_collect_job("J2")["result"]
    assert payload["tally"]["login_wall"] == 15
