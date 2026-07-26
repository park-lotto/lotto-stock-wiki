"""담긴 영상 자동 대본적재(/api/produce/autoload) — 무한루프 사고 회귀방지.

배경(2026-07-26 실사고): AI PICK 소스는 script_wiki(도서관) ∩ produce_script_picks(담김)이고
둘 다 customer_id로 스코핑된다(app._load_work_sources). 신규 고객은 도서관이 비어 pick_id가
항상 None → 폴백 화면. 이걸 자동으로 채우려던 첫 구현이 성공/실패를 **클라이언트 메모리와
HANDOFF 객체 필드**에만 남겨, HANDOFF 배열 재대입 때 표시가 증발 → 재추출 무한루프로
AI 크레딧을 태웠다(revert cb8c0fa1d).

그래서 이 테스트가 지키는 계약은 넷이다:
  ① 성공하면 도서관 + 담김에 **둘 다** 들어간다(하나만 넣으면 교집합에서 탈락 → 여전히 폴백)
  ② 전사 결과가 비면(인스타 릴스 다수) 저장하지 않는다 — 빈 대본이 캐시로 굳으면 영구 오작동
  ③ 한 번 실패한 영상은 **다시 추출하지 않는다**(DB 래치) ← 무한루프 차단의 핵심
  ④ 이미 도서관에 있는 영상은 추출 없이 담기만 보장한다
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store

URL = "https://www.instagram.com/reel/AUTOLOAD1/"


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    monkeypatch.setattr(app_module, "analyze_structure", lambda text: None)
    return TestClient(app_module.app), Store(db)


def _stub_extract(monkeypatch, calls, full_text):
    monkeypatch.setattr(app_module, "download_any",
                        lambda url, dest_dir: ("/fake/video.mp4", "캡션"))

    def _fake(video_path, code, caption=""):
        calls.append(code)
        return {"full_text": full_text, "segments": []}
    monkeypatch.setattr(app_module, "extract_script", _fake)


def test_autoload_puts_script_in_both_wiki_and_picks(monkeypatch, tmp_path):
    """①: 성공 시 도서관·담김 양쪽에 들어가 AI PICK 소스 교집합을 통과한다."""
    client, store = _client(monkeypatch, tmp_path)
    calls = []
    _stub_extract(monkeypatch, calls, "정리 꿀팁 원본 대본")

    r = client.post("/api/produce/autoload", json={"items": [{"url": URL, "name": "살림홈"}]})
    assert r.status_code == 200
    d = r.json()
    assert d["added"] == 1 and d["results"][0]["status"] == "added"

    code = d["results"][0]["shortcode"]
    assert any(w["shortcode"] == code for w in store.wiki_list(customer_id=0))
    assert code in store.produce_pick_shortcodes(customer_id=0)
    # 교집합이 실제로 채워졌으니 AI PICK이 소스를 본다.
    assert app_module._load_work_sources("", 0)


def test_autoload_empty_transcript_is_not_saved(monkeypatch, tmp_path):
    """②: 전사 결과가 비면 도서관에도 캐시에도 남기지 않는다."""
    client, store = _client(monkeypatch, tmp_path)
    calls = []
    _stub_extract(monkeypatch, calls, "")   # 인스타 릴스 전사 실패 재현

    d = client.post("/api/produce/autoload", json={"items": [{"url": URL}]}).json()
    assert d["added"] == 0 and d["results"][0]["status"] == "failed_empty"
    assert store.wiki_list(customer_id=0) == []
    assert store.get_extract(d["results"][0]["shortcode"]) is None


def test_autoload_does_not_retry_a_failed_video(monkeypatch, tmp_path):
    """③★무한루프 차단: 같은 영상으로 몇 번을 다시 불러도 추출은 딱 한 번만 돈다."""
    client, store = _client(monkeypatch, tmp_path)
    calls = []
    _stub_extract(monkeypatch, calls, "")

    for _ in range(5):
        client.post("/api/produce/autoload", json={"items": [{"url": URL}]})
    assert len(calls) == 1, f"실패한 영상을 재추출했다(크레딧 소모 루프): {calls}"

    last = client.post("/api/produce/autoload", json={"items": [{"url": URL}]}).json()
    assert last["results"][0]["status"] == "skipped_latched"


def test_autoload_existing_wiki_item_only_gets_picked(monkeypatch, tmp_path):
    """④: 이미 도서관에 있으면 추출 없이 담기만 보장한다(재과금 없음)."""
    client, store = _client(monkeypatch, tmp_path)
    calls = []
    _stub_extract(monkeypatch, calls, "이미 있는 대본")

    first = client.post("/api/produce/autoload", json={"items": [{"url": URL}]}).json()
    code = first["results"][0]["shortcode"]
    store.produce_pick_toggle(code, customer_id=0)          # 담김만 뺀 상태로 되돌린다
    assert code not in store.produce_pick_shortcodes(customer_id=0)

    again = client.post("/api/produce/autoload", json={"items": [{"url": URL}]}).json()
    assert again["results"][0]["status"] == "already"
    assert len(calls) == 1                                   # 추출은 여전히 1회뿐
    assert code in store.produce_pick_shortcodes(customer_id=0)


def test_produce_pick_add_is_idempotent(tmp_path):
    """produce_pick_add는 두 번 불러도 빼지 않는다(toggle을 쓰면 두 번째에 사라진다)."""
    store = Store(tmp_path / "t.db")
    assert store.produce_pick_add("XYZ", customer_id=7) is True
    assert store.produce_pick_add("XYZ", customer_id=7) is False
    assert "XYZ" in store.produce_pick_shortcodes(customer_id=7)
