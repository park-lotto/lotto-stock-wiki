"""픽업 생성도 담긴 재료 전체와 공통 소재 출구 검사를 거친다(2026-09-14)."""
import sqlite3
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts import script_generate as sg
from shopping_shorts.store import Store


SOURCES = [
    {"full_text": "여행용 가방은 백팩과 숄더백으로 바꿔 멜 수 있습니다.",
     "product": "3-way 여행용 가방"},
    {"full_text": "가방을 펼치면 수납칸이 넓어지고 캐리어에도 걸 수 있습니다."},
]


def test_guarded_pickup_retries_wrong_subject_and_uses_all_sources(monkeypatch):
    calls = []

    def fake_generate(_structure, full_text, *_args, **_kwargs):
        calls.append(full_text)
        if len(calls) == 1:
            return [{"hook": "주방", "script": "기름때 닦는 행주라 주방 청소가 쉬워집니다."}]
        return [{"hook": "여행", "script": "이 여행용 가방은 백팩과 숄더백으로 바꿔 멜 수 있어요."}]

    monkeypatch.setattr(sg, "generate_variations", fake_generate)
    reasons = []
    out = sg.generate_guarded_variations({}, SOURCES, {}, {}, n=1,
                                         rejection_reasons=reasons)

    assert len(calls) == 2, "첫 소재 이탈 결과 뒤에 새 생성이 실행되지 않았다"
    assert all(s["full_text"] in calls[0] for s in SOURCES), "씨앗 한 편만 생성기에 들어갔다"
    assert out[0]["hook"] == "여행"
    assert reasons == [{"reason": "소재이탈", "detail": "소재 일치"}]


def test_guarded_pickup_never_returns_wrong_subject_after_retries(monkeypatch):
    calls = []

    def always_wrong(*_args, **_kwargs):
        calls.append(1)
        return [{"hook": "주방", "script": "기름때와 설거지용 행주를 소개합니다."}]

    monkeypatch.setattr(sg, "generate_variations", always_wrong)
    reasons = []
    out = sg.generate_guarded_variations({}, SOURCES, {}, {}, n=1,
                                         rejection_reasons=reasons)

    assert len(out) == 1 and out[0]["made_by"] == "장면근거"
    assert "3-way 여행용 가방" in out[0]["script"]
    assert "기름때" not in out[0]["script"] and "행주" not in out[0]["script"]
    assert len(calls) == sg.PICKUP_MATERIAL_REWRITES + 1
    assert len(reasons) == len(calls)


def test_pickup_api_passes_shared_material_bundle_to_guarded_generator(tmp_path, monkeypatch):
    db = tmp_path / "pickup.db"
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    store = Store(db)
    store.save_to_wiki(
        {"shortcode": "seed", "name": "여행가방", "category": "홈템"},
        {"full_text": "씨앗 한 편", "segments": []}, {"hook": "훅"}, customer_id=0)
    monkeypatch.setattr(app_mod, "_materials_for_generate",
                        lambda *a, **k: (SOURCES, "", {}, "", ""))
    captured = {}

    def fake_guarded(structure, sources, *args, **kwargs):
        captured["sources"] = sources
        return [{"hook": "여행", "script": "여행용 가방을 백팩으로 멜 수 있어요."}]

    monkeypatch.setattr(app_mod.script_generate, "generate_guarded_variations", fake_guarded)
    r = TestClient(app_mod.app).post("/api/wiki/generate?shortcode=seed", json={"n": 1})

    assert r.status_code == 200, r.text
    assert captured["sources"] == SOURCES
    assert len(r.json()["materials"]["sources"]) == 2


def test_pickup_api_recovers_grounded_draft_instead_of_saving_subject_leak(tmp_path, monkeypatch):
    db = tmp_path / "pickup.db"
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    Store(db).save_to_wiki(
        {"shortcode": "seed", "name": "여행가방", "category": "홈템"},
        {"full_text": "씨앗 한 편", "segments": []}, {"hook": "훅"}, customer_id=0)
    monkeypatch.setattr(app_mod, "_materials_for_generate",
                        lambda *a, **k: (SOURCES, "", {}, "", ""))

    def reject_all(*args, **kwargs):
        kwargs["rejection_reasons"].append({"reason": "소재이탈", "detail": "소재 일치"})
        return []

    monkeypatch.setattr(app_mod.script_generate, "generate_guarded_variations", reject_all)
    r = TestClient(app_mod.app).post("/api/wiki/generate?shortcode=seed", json={"n": 1})

    assert r.status_code == 200, r.text
    drafts = r.json()["drafts"]
    assert len(drafts) == 1 and drafts[0]["made_by"] == "장면근거"
    assert "3-way 여행용 가방" in drafts[0]["script"]
    assert "기름때" not in drafts[0]["script"] and "행주" not in drafts[0]["script"]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM script_drafts").fetchone()[0] == 1
