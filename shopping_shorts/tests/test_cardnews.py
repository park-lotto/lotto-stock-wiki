"""카드뉴스 제작소(관제 223) — 판단(cardnews.py)·저장 격리·입구 스위치."""
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts import cardnews as cn
from shopping_shorts.store import Store


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


def _slide(role, title, **kw):
    s = {"role": role, "kicker": "", "title": title, "body": kw.pop("body", "")}
    s.update(kw)
    return cn.normalize_slide(s)


def _car(slides, topic="좁은 주방 수납 늘리는 정리 순서"):
    return cn.normalize_carousel({"topic": topic, "source": {"topic": topic}, "slides": slides})


# ── 검사 ──────────────────────────────────────────────────────────────────
def test_check_clean_carousel_has_no_fix():
    car = _car([_slide("cover", "좁은 주방 {수납} 정리"), _slide("list", "있으면 편한 {정리템}", items=["틈새 수납장", "문걸이 선반"]),
                _slide("cta", "저장해 두고 {주말에} 해 보세요")])
    assert [i for i in cn.check_carousel(car, cn.DEFAULT_BRAND) if i["level"] == "fix"] == []


def test_check_flags_invented_date_dup_title_cover_long_and_ban():
    car = _car([_slide("cover", "좁은 주방 {수납} 2배로 늘리는 정리 순서 완벽 정리 가이드"),
                _slide("list", "{정리템}", items=["2026년 3월 1일 출시", "칸막이"]),
                _slide("list", "{정리템}", items=["최고의 선반", "트레이"]),
                _slide("cta", "저장해 두고 {주말에} 해 보세요")])
    codes = {i["code"] for i in cn.check_carousel(car, dict(cn.DEFAULT_BRAND, ban="최고"))}
    assert {"invented", "dup_title", "cover_long", "banned"} <= codes


def test_check_last_slide_must_be_cta_and_count():
    car = _car([_slide("cover", "{제목}"), _slide("list", "{목록}", items=["a", "b"])])
    codes = {i["code"] for i in cn.check_carousel(car, cn.DEFAULT_BRAND)}
    assert "cta" in codes and "count" in codes


def test_check_report_has_12_items_and_dedupes():
    issues = [{"slide": 1, "code": "repeat", "level": "warn", "msg": "같은 말"}] * 3
    rep = cn._check_report(issues, [])
    assert len(rep) == 12
    assert [r for r in rep if r["code"] == "repeat"][0]["msgs"] == ["같은 말"]


def test_normalize_drops_unknown_and_bad_bg_url():
    s = cn.normalize_slide({"role": "hack", "title": "x", "bg": {"kind": "ai", "url": "javascript:alert(1)"}})
    assert s["role"] == "list" and s["bg"]["url"] == ""


def test_asset_path_blocks_traversal(tmp_path):
    assert cn.asset_path(str(tmp_path), 5, "../../reference.db") is None
    assert cn.asset_path(str(tmp_path), 5, "bg_1.png") is None      # 없는 파일


def test_next_run_is_future_on_chosen_day():
    rule = cn.clean_rule({"days": [2], "hour": 9, "topics": ["a"]})       # 수요일 9시
    now = datetime(2026, 10, 17, 10, 0, tzinfo=cn.KST).timestamp()           # 토요일
    nxt = datetime.fromtimestamp(cn.next_run_at(rule, now), cn.KST)
    assert nxt.weekday() == 2 and nxt.hour == 9 and nxt.timestamp() > now


def test_brand_clean_rejects_bad_color_and_logo():
    b = cn.clean_brand({"color": "red", "logo": "https://evil/x.png", "tone": "??"})
    assert b["color"] == cn.DEFAULT_BRAND["color"] and b["logo"] == "" and b["tone"] in cn.TONES


# ── 저장 격리 ──────────────────────────────────────────────────────────────
def test_store_isolates_customers(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    wid = st.cardnews_save(None, 11, {"slides": []}, title="내 것")
    assert st.cardnews_get(wid, 11)["title"] == "내 것"
    assert st.cardnews_get(wid, 22) is None
    assert st.cardnews_save(wid, 22, {"slides": [1]}) is None        # 남의 것 덮어쓰기 불가
    assert st.cardnews_delete(wid, 22) is False
    rid = st.cardnews_rule_save(11, {"topics": ["a"]}, 100)
    assert st.cardnews_rule_save(22, {"topics": ["b"]}, 100, rule_id=rid) is None
    assert st.cardnews_rule_claim(rid, 100, 200, 150) is True
    assert st.cardnews_rule_claim(rid, 100, 300, 150) is False         # 두 번째 프로세스는 못 가져간다


# ── 입구(스위치)와 API ────────────────────────────────────────────────────
@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_CN_DATA", str(tmp_path))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    st = Store(str(tmp_path / "t.db"))
    st.ensure_paywall_schema()
    return st


def _fake_ai(prompt, schema, note=None):
    props = (schema or {}).get("properties", {})
    if "text" in props and len(props) == 1:
        return {"text": "{다시} 쓴 글"}
    if "title" in props and "slides" in props:
        return {"title": "주방 정리", "slides": [{"role": "cover", "line": "표지"}, {"role": "list", "line": "목록"},
                                                {"role": "cta", "line": "마무리"}]}
    return {"slides": [{"role": "cover", "kicker": "꿀팁", "title": "좁은 주방 {정리}", "body": "이것부터"},
                       {"role": "list", "kicker": "", "title": "있으면 편한 {정리템}", "body": "", "items": ["선반", "트레이"]},
                       {"role": "cta", "kicker": "", "title": "저장해 두고 {해 보세요}", "body": "다음 편 예고"}],
            "caption": "본문", "hashtags": ["정리", "#살림"]}


def test_gate_off_blocks_api_and_page(env):
    c = TestClient(appmod.app)
    r = c.get("/api/cardnews/boot", cookies={"dash_auth": _cookie(0)})
    assert r.status_code == 403
    r = c.get("/cardnews", cookies={"dash_auth": _cookie(0)}, follow_redirects=False)
    assert r.status_code == 302


def test_gate_admin_build_save_and_isolation(env, monkeypatch):
    env.set_setting("cardnews_enabled", "admin")
    monkeypatch.setattr(cn, "_ai_json", _fake_ai)
    c = TestClient(appmod.app)
    ck = {"dash_auth": _cookie(0)}
    assert c.get("/api/cardnews/boot", cookies=ck).json()["ok"] is True
    ol = c.post("/api/cardnews/outline", json={"src": {"kind": "topic", "topic": "주방"}, "opts": {}}, cookies=ck).json()
    assert ol["ok"] and len(ol["slides"]) == 3
    b = c.post("/api/cardnews/build", json={"src": {"kind": "topic", "topic": "주방"}, "outline": ol["slides"], "opts": {}},
               cookies=ck).json()
    assert b["ok"] and len(b["carousel"]["slides"]) == 3 and b["carousel"]["hashtags"] == ["정리", "살림"]
    assert len(b["carousel"]["checks"]) == 12
    works = c.get("/api/cardnews/works", cookies=ck).json()["works"]
    assert [w["work_id"] for w in works] == [b["work_id"]]
    # 일반 회원(스위치 admin)은 막힌다
    r = c.get("/api/cardnews/works/" + b["work_id"], cookies={"dash_auth": _cookie(77)})
    assert r.status_code in (402, 403)


def test_ai_failure_is_not_502(env, monkeypatch):
    """502/503/504는 사이드바가 '배포 재시작'으로 읽는다(sidebar.js _ssDown) — AI 실패는 422로."""
    env.set_setting("cardnews_enabled", "admin")
    monkeypatch.setattr(cn, "_ai_json", lambda *a, **k: {})
    c = TestClient(appmod.app)
    r = c.post("/api/cardnews/outline", json={"src": {"kind": "topic", "topic": "주방"}, "opts": {}},
               cookies={"dash_auth": _cookie(0)})
    assert r.status_code == 422 and r.json()["ok"] is False


def test_gen_background_uses_gemini_image_on_global_client(tmp_path, monkeypatch):
    """Imagen 4는 사장님 프로젝트에 없다(2026-10-17 라이브 404) — 기본은 제미니 그림 모델, global 클라이언트."""
    from types import SimpleNamespace as NS
    from shopping_shorts import vertex_route
    calls = {}

    class _Models:
        def generate_content(self, model, contents, config):
            calls["model"] = model
            part = NS(inline_data=NS(data=b"\xff\xd8jpg", mime_type="image/jpeg"))
            return NS(candidates=[NS(content=NS(parts=[part]))])

        def generate_images(self, **kw):
            raise AssertionError("imagen 경로로 가면 안 된다")

    monkeypatch.setattr(cn, "image_allowed", lambda cid: (True, ""))
    monkeypatch.setattr(vertex_route, "client", lambda cid=None, location=None: NS(models=_Models()))
    monkeypatch.setattr(vertex_route, "veo_client", lambda cid: None)
    name, why = cn.gen_background(0, "kitchen", str(tmp_path))
    assert why == "" and name.endswith(".jpg") and calls["model"] == cn.IMAGE_MODEL_DEFAULT
    assert cn.asset_path(str(tmp_path), 0, name)
