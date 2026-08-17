# -*- coding: utf-8 -*-
"""/api/wiki/generate **스타일 경로가 끝까지 200으로 돈다**(2026-08-17).

## 왜 이 테스트가 생겼나 — 라이브 500 사고

재료 조립을 `_materials_for_generate`로 뽑아내면서 `_scene_block` 지역변수가 함수 안으로
들어갔는데, **응답을 만드는 줄(`materials.scene_points`)이 아직 그 변수를 쓰고 있었다.**
→ 라이브에서 `NameError: name '_scene_block' is not defined` → 500 →
화면엔 **"네트워크 오류"** 만 떴다(사장님 제보).

★못 잡은 이유가 핵심이다: 기존 테스트·내 HTTP 점검은 전부 **422/404에서 끝났다.**
  이 줄은 `style_ids`가 유효하고 생성까지 성공해야 **비로소 실행되는 마지막 줄**이라
  실패 케이스만 두드려서는 영원히 안 걸린다. **성공 경로를 끝까지 타는 테스트**가 답이다.

(같은 유형의 과거 사고: `work_id`에 dict가 와서 500 → 화면엔 '네트워크 오류'만.
 화면이 원인을 못 보여주는 오류는 서버 로그를 봐야만 정체가 드러난다.)
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts import script_generate
from shopping_shorts.store import Store


STYLE = {
    "id": 52, "name": "가족갈등 반전형", "status": "approved",
    "beat_roles": ["hook", "cta"], "beat_chain": ["미끼", "약속"],
    "templates": {"hook": ["이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요"]},
    "chars_per_30s": 300, "fit_categories": [],
}


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(Store, "list_style_spines",
                        lambda self, category=None, status="approved": [dict(STYLE)])
    monkeypatch.setattr(
        script_generate, "generate_by_styles",
        lambda sources, styles, **kw: [{
            "style_id": 52, "style_name": "가족갈등 반전형",
            "beats": [{"role": "hook", "text": "훅"}, {"role": "cta", "text": "댓글 남겨주세요"}],
            "script": "훅\n댓글 남겨주세요", "hook": "훅",
            "checks": [{"name": "구간 순서", "ok": True}], "passed": True, "tries": [{}],
        }])
    return TestClient(app_mod.app)


def test_스타일_경로가_200으로_끝까지_돈다(monkeypatch, tmp_path):
    """★라이브 500 회귀 — 응답 조립까지 도달해야 `_scene_block` 같은 누락이 잡힌다."""
    client = _client(monkeypatch, tmp_path)
    r = client.post("/api/wiki/generate?shortcode=X",
                    json={"base_script": "원본 대본", "category": "홈템", "style_ids": [52]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True and d["mode"] == "style"
    assert len(d["drafts"]) == 1


def test_materials가_응답에_실린다(monkeypatch, tmp_path):
    """화면이 '무슨 재료를 썼는지' 보여주는 블록 — 여기가 500의 진원지였다."""
    client = _client(monkeypatch, tmp_path)
    r = client.post("/api/wiki/generate?shortcode=X",
                    json={"base_script": "원본 대본", "category": "홈템", "style_ids": [52]})
    assert r.status_code == 200, r.text
    m = r.json()["materials"]
    assert m["styles"] == ["가족갈등 반전형"]
    assert isinstance(m["scene_points"], int)      # ★NameError로 죽던 자리
    assert isinstance(m["product_facts"], bool)
    assert m["sources"] and m["sources"][0]["chars"] > 0


def test_auto_style도_같은_경로를_탄다(monkeypatch, tmp_path):
    """'AI에게 맡김' — style_ids 없이 auto_style만 와도 스타일 경로로 가야 한다."""
    client = _client(monkeypatch, tmp_path)
    r = client.post("/api/wiki/generate?shortcode=X",
                    json={"base_script": "원본 대본", "category": "홈템", "auto_style": True})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "style"


def test_job_id가_dict여도_500이_아니다(monkeypatch, tmp_path):
    """★타입을 믿지 마라 — 클라이언트 값이라 문자열이 아닐 수 있다(과거 실사고)."""
    client = _client(monkeypatch, tmp_path)
    r = client.post("/api/wiki/generate?shortcode=X",
                    json={"base_script": "원본", "category": "홈템", "style_ids": [52],
                          "job_id": {"a": 1}, "work_id": [1]})
    assert r.status_code == 200, r.text
