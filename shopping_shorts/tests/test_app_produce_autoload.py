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
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store

URL = "https://www.instagram.com/reel/AUTOLOAD1/"


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    monkeypatch.setattr(app_module, "analyze_structure", lambda text: None)
    monkeypatch.setattr(app_module, "_WIKI_MEDIA_DIR", tmp_path / "media")
    return TestClient(app_module.app), Store(db)


def _stub_extract(monkeypatch, calls, full_text):
    def _fake_download(url, dest_dir):
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        p = Path(dest_dir) / "video.mp4"
        p.write_bytes(b"fake-mp4-bytes")
        return str(p), "캡션"
    monkeypatch.setattr(app_module, "download_any", _fake_download)

    def _fake(video_path, code, caption=""):
        calls.append(code)
        return {"full_text": full_text, "segments": []}
    monkeypatch.setattr(app_module, "extract_auto", _fake)


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


def test_autoload_saves_video_permanently(monkeypatch, tmp_path):
    """2026-07-26 실사고 회귀방지: autoload로 담긴 영상은 /api/wiki/video가 서빙할 수 있게
    _WIKI_MEDIA_DIR에 mp4가 영구보관돼야 한다(누락 시 대본만 저장돼 도서관에서
    "원본 영상 없음"으로 뜬다 — DB엔 있는데 파일만 없는 상태)."""
    client, store = _client(monkeypatch, tmp_path)
    calls = []
    _stub_extract(monkeypatch, calls, "정리 꿀팁 원본 대본")

    d = client.post("/api/produce/autoload", json={"items": [{"url": URL}]}).json()
    code = d["results"][0]["shortcode"]

    hashed = hashlib.sha1(code.encode()).hexdigest()[:16]
    media_file = (tmp_path / "media") / f"{hashed}.mp4"
    assert media_file.exists(), "autoload가 도서관 DB엔 저장했지만 원본 mp4를 영구보관하지 않았다"

    r = client.get(f"/api/wiki/video?shortcode={code}")
    assert r.status_code == 200


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


def test_pick_remove_takes_video_out_of_aipick_sources(monkeypatch, tmp_path):
    """✕(dropFootage)로 뺀 영상은 AI PICK 후보에서 즉시 빠진다.
    2026-07-26 사장님 제보: 자동적재 이후 담김이 서버에도 쌓이는데 ✕가 클라만 고쳐서
    뺀 영상이 계속 카드에 남았다. remove는 멱등이어야 한다(toggle이면 두 번째에 되살아난다)."""
    client, store = _client(monkeypatch, tmp_path)
    calls = []
    _stub_extract(monkeypatch, calls, "정리 꿀팁 원본 대본")

    code = client.post("/api/produce/autoload",
                       json={"items": [{"url": URL}]}).json()["results"][0]["shortcode"]
    assert app_module._load_work_sources("", 0)          # 담긴 상태 = 후보 있음

    for _ in range(2):                                    # 두 번 눌러도 되살아나지 않는다
        assert client.post("/api/produce/picks/remove", json={"shortcode": code}).status_code == 200
        assert code not in store.produce_pick_shortcodes(customer_id=0)
    assert app_module._load_work_sources("", 0) == []     # AI PICK 후보에서 사라졌다


def test_produce_pick_add_is_idempotent(tmp_path):
    """produce_pick_add는 두 번 불러도 빼지 않는다(toggle을 쓰면 두 번째에 사라진다)."""
    store = Store(tmp_path / "t.db")
    assert store.produce_pick_add("XYZ", customer_id=7) is True
    assert store.produce_pick_add("XYZ", customer_id=7) is False
    assert "XYZ" in store.produce_pick_shortcodes(customer_id=7)


def test_aipick_includes_handoff_video_not_in_library(monkeypatch, tmp_path):
    """회귀(2026-07-27 실측 사고): '넘어온 영상(handoff)'이 도서관(script_wiki)에 저장 안
    됐어도 script_extracts에 추출본이 있으면 AI PICK 후보에 남아야 한다.

    예전엔 `items = wiki_list(cid) ∩ handoff`로 좁혀, 도서관에 없는 영상(실측: '홈스텐다드')이
    통째로 탈락하고 도서관 즐겨찾기(금손여신·살림홈)만 뽑혀 "도서관 것만 AI PICK"이 됐다.
    이제 도서관에 없으면 script_extracts+reel_history에서 끌어와 후보로 넣는다."""
    _, store = _client(monkeypatch, tmp_path)
    # 도서관에 저장된 영상(즐겨찾기)
    store.save_to_wiki({"shortcode": "LIB1", "name": "살림홈", "category": "홈템"},
                       {"full_text": "도서관 대본", "segments": []}, {}, customer_id=0)
    # 도서관엔 없지만 추출본만 있는 '넘어온 영상'
    store.save_script("NEW1", {"full_text": "새로 넘어온 영상 대본", "segments": []}, category="홈템")
    # 두 영상을 담은 작업(handoff = 넘어온 영상 목록)
    wid = store.upsert_produce_work(
        None, {"handoff": [{"shortcode": "NEW1"}, {"shortcode": "LIB1"}]}, customer_id=0)

    ids = {s["video_id"] for s in app_module._load_work_sources(wid, 0)}
    assert "NEW1" in ids   # ★핵심: 도서관에 없어도 후보에 남는다
    assert "LIB1" in ids
