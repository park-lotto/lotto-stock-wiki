"""체험판 개방(2026-08-20) — 랭킹·즐겨찾기·렌즈는 열고 제작소 API는 계속 막는다."""
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return s


def test_favorites_and_lens_open_for_ranking_only():
    """즐겨찾기 담기·목록과 과금검사 있는 렌즈 2개는 열린다."""
    assert appmod._ranking_only_blocked("/api/mix/basket", "GET") is False
    assert appmod._ranking_only_blocked("/api/mix/basket/toggle", "POST") is False
    assert appmod._ranking_only_blocked("/collection", "GET") is False
    assert appmod._ranking_only_blocked("/api/lens/search", "POST") is False
    assert appmod._ranking_only_blocked("/api/lens/trace_url", "POST") is False


def test_unmetered_lens_and_produce_api_still_blocked():
    """★과금검사 없는 렌즈는 계속 막는다 — prefix로 열면 Apify 유료가 샌다."""
    assert appmod._ranking_only_blocked("/api/lens/kw/search", "POST") is True
    assert appmod._ranking_only_blocked("/api/lens/cn/search", "POST") is True
    assert appmod._ranking_only_blocked("/api/lens/yt", "POST") is True
    assert appmod._ranking_only_blocked("/api/lens/single", "GET") is True
    # 제작소 API는 HTML을 열어도 계속 막힌다(과금 기능 유출 방지)
    assert appmod._ranking_only_blocked("/api/produce/mix/clean", "POST") is True
    assert appmod._ranking_only_blocked("/api/produce/script/mix", "POST") is True
    # 담기 파생 경로도 열지 않았다
    assert appmod._ranking_only_blocked("/api/mix/basket/reprobe", "POST") is True


def test_free_user_can_toggle_basket(tmp_path, monkeypatch):
    """실제 요청으로 담기가 200을 받는다(402가 아니다)."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("trial1", "pw12")
    s.set_plan(cid, "free", full_access_until=0)      # ranking_only
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert c.get("/api/mix/basket").status_code == 200
    r = c.post("/api/mix/basket/toggle", json={"shortcode": "ABC123", "url": ""})
    assert r.status_code == 200
    assert r.json()["in"] is True


def test_free_basket_skips_paid_side_effects(tmp_path, monkeypatch):
    """무료 등급이 담아도 인스타 크롤·Gemini 예열이 돌지 않는다."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("trial2", "pw12")
    s.set_plan(cid, "free", full_access_until=0)      # ranking_only
    calls = []
    monkeypatch.setattr(appmod, "_enqueue_prewarm",
                        lambda *a, **k: calls.append("prewarm"))
    monkeypatch.setattr(appmod, "_enrich_grab",
                        lambda *a, **k: calls.append("grab"))
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = c.post("/api/mix/basket/toggle", json={
        "shortcode": "SC_FREE", "url": "https://www.instagram.com/reel/SC_FREE/"})
    assert r.status_code == 200
    assert r.json()["in"] is True          # 담기 자체는 정상 동작
    assert calls == []                     # ★유료 부작용은 하나도 안 돈다


def test_paid_basket_still_runs_side_effects(tmp_path, monkeypatch):
    """★회귀 방지 — pro(full) 등급은 종전과 완전히 같이 동작한다."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pro1", "pw12")
    s.set_plan(cid, "pro")                            # full
    calls = []
    monkeypatch.setattr(appmod, "_enqueue_prewarm",
                        lambda *a, **k: calls.append("prewarm"))
    monkeypatch.setattr(appmod, "_enrich_grab",
                        lambda *a, **k: calls.append("grab"))
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = c.post("/api/mix/basket/toggle", json={
        "shortcode": "SC_PRO", "url": "https://www.instagram.com/reel/SC_PRO/"})
    assert r.status_code == 200
    assert "prewarm" in calls              # 예열은 돈다(종전 동작 보존)


def _produce_body(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} → {r.status_code}"
    return r.text


def test_produce_shows_intro_for_free_user(tmp_path, monkeypatch):
    """무료 등급은 /produce·/produce.html 모두 소개 페이지를 받는다(402 JSON 아님)."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("trial3", "pw12")
    s.set_plan(cid, "free", full_access_until=0)      # ranking_only
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    for path in ("/produce", "/produce.html"):
        body = _produce_body(c, path)
        # ★판정 기준(2026-08-20 변경): 미리보기는 **진짜 화면을 얼린 복사본**이라
        #   마크업이 원본과 같다. 그래서 'mixScriptPick 유무'로는 못 가른다
        #   (예전 기준. 얼린 페이지에도 그 문자열이 그대로 들어 있다).
        #   진짜로 지켜야 할 성질은 **미리보기 배너가 있고 실행 코드가 없다**는 것.
        assert "ss-bar" in body                       # 미리보기 배너
        assert "미리보기입니다" in body


def test_frozen_preview_cannot_call_any_api(tmp_path, monkeypatch):
    """★핵심 안전장치 — 미리보기 페이지는 API를 부를 '코드 자체'가 없어야 한다.

    버튼을 하나씩 잠그는 방식이면 221개 중 하나만 빠뜨려도 과금이 샌다.
    그래서 <script>를 통째로 걷어내는 방식을 썼고, 그게 유지되는지 여기서 지킨다."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("trial4", "pw12")
    s.set_plan(cid, "free", full_access_until=0)      # ranking_only
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    body = _produce_body(c, "/produce")
    assert body.count("<script") == 1                 # 얼린 스크립트 1개만
    assert "fetch(" not in body
    assert "XMLHttpRequest" not in body
    assert "onclick=" not in body
    assert "/api/produce" not in body                 # 제작 API 주소가 아예 없다
    assert body.count('class="panel') >= 9            # 9단계는 그대로 둘러볼 수 있다


def test_produce_unchanged_for_paid_user(tmp_path, monkeypatch):
    """★회귀 방지 — pro는 진짜 제작소 화면(살아 있는 것)을 그대로 받는다."""
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pro2", "pw12")
    s.set_plan(cid, "pro")                            # full
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    body = _produce_body(c, "/produce")
    assert "mixScriptPick" in body                    # 진짜 제작소 화면
    assert "ss-bar" not in body                       # 미리보기 배너가 없다
    assert body.count("<script") > 1                  # 스크립트가 살아 있다(얼린 게 아니다)
