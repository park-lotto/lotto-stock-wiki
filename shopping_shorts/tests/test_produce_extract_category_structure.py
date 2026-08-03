"""제작소(영상제작소) 대본뽑기 모달의 I-1(category 전파)·I-2(structure 반환) 배선 수정
검증(2026-07-15, Task 6).

라이브 실측: PM_CATEGORY=""·PM_BASE_STRUCT=null → 드롭다운 옵션 0개("학습된 카테고리
아직 없음")로 무력화. 원인은 /api/produce/extract_from_url이 store.get_script()(category·
structure 없음)만 쓰고 있었기 때문. store.get_extract()로 교체 + categorize() 유추로 해결."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "reference.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


def test_extract_returns_category_and_structure_from_cache(monkeypatch, tmp_path):
    """이미 추출·구조분석된 영상은 캐시에서 category·structure를 그대로 실어 보낸다."""
    client, st = _client(monkeypatch, tmp_path)
    st.save_script("ABC", {"full_text": "감자전 레시피", "segments": []}, category="레시피")
    st.save_extract_structure("ABC", {"hook": "훅", "characters": "언니"})

    r = client.post("/api/produce/extract_from_url",
                     json={"url": "https://x/reel/ABC", "shortcode": "ABC"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["cached"] is True
    assert d["category"] == "레시피"
    assert d["structure"]["characters"] == "언니"


def test_extract_infers_category_from_name_caption(monkeypatch, tmp_path):
    """category가 없으면 랭킹과 같은 categorize(name, caption)로 유추한다(I-1 핵심).
    즐겨찾기 핸드오프엔 category가 없고 name·caption만 있기 때문.
    categorize.py의 KEYWORDS/NAME_KEYWORDS 실측: caption "감자 레시피 간단한 요리"가
    레시피 키워드("레시피","감자")에 2건 매칭(가중 x3=6) + name "하랑쿠킹"이
    NAME_KEYWORDS 레시피의 "쿠킹"에 매칭(가중 x1=1) → 합계 7점으로 최고점 → "레시피"."""
    client, st = _client(monkeypatch, tmp_path)
    # category 없이 저장된 캐시
    st.save_script("ZZZ", {"full_text": "본문", "segments": []}, category=None)

    r = client.post("/api/produce/extract_from_url",
                     json={"url": "https://x/reel/ZZZ", "shortcode": "ZZZ",
                           "name": "하랑쿠킹", "caption": "감자 레시피 간단한 요리"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["category"] == "레시피"

    # 다음 클릭부터 안정되도록 DB에도 채워 넣어야 한다(브리프 Step3-3).
    saved = st.get_extract("ZZZ")
    assert saved["category"] == "레시피"


def test_extract_does_not_overwrite_existing_category(monkeypatch, tmp_path):
    """이미 category가 있으면 categorize() 추론으로 덮어쓰지 않는다."""
    client, st = _client(monkeypatch, tmp_path)
    st.save_script("KEEP", {"full_text": "본문", "segments": []}, category="가전")

    r = client.post("/api/produce/extract_from_url",
                     json={"url": "https://x/reel/KEEP", "shortcode": "KEEP",
                           "name": "하랑쿠킹", "caption": "감자 레시피 간단한 요리"})
    assert r.status_code == 200, r.text
    assert r.json()["category"] == "가전"
    assert st.get_extract("KEEP")["category"] == "가전"


def test_extract_new_video_infers_category_and_saves_structure(monkeypatch, tmp_path):
    """캐시에 없는 새 영상도 다운로드·추출 후 category를 유추해 저장하고,
    structure는 analyze_structure() 결과가 있으면 저장한다."""
    client, st = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "download_any", lambda url, d: ("/tmp/x.mp4", "캡션"))
    monkeypatch.setattr(app_module, "extract_auto",
                         lambda path, code, caption="": {"full_text": "감자 레시피 대본", "segments": []})
    monkeypatch.setattr(app_module, "analyze_structure",
                         lambda full_text, max_key_tries=3: {"hook": "질문형"})

    r = client.post("/api/produce/extract_from_url",
                     json={"url": "https://insta/p/NEW", "shortcode": "NEW1",
                           "name": "하랑쿠킹", "caption": "감자 레시피 간단한 요리"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["cached"] is False
    assert d["category"] == "레시피"
    assert d["structure"] == {"hook": "질문형"}
    saved = st.get_extract("NEW1")
    assert saved["category"] == "레시피"
    assert saved["structure"] == {"hook": "질문형"}


def test_extract_structure_analysis_failure_does_not_break_response(monkeypatch, tmp_path):
    """analyze_structure는 Gemini 호출이라 실패할 수 있다 — 실패해도 대본 추출 응답
    자체는 성공해야 한다(structure=None으로). 대본을 잃는 게 최악이라는 요구사항 검증.
    (실제 analyze_structure는 내부에서 이미 예외를 삼키고 {}를 반환하지만, 여기선
    엔드포인트가 예외를 던지는 최악의 경우까지 방어하는지 확인한다.)"""
    client, st = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "download_any", lambda url, d: ("/tmp/x.mp4", ""))
    monkeypatch.setattr(app_module, "extract_auto",
                         lambda path, code, caption="": {"full_text": "본문", "segments": []})

    def _boom(full_text, max_key_tries=3):
        raise RuntimeError("Gemini API down")
    monkeypatch.setattr(app_module, "analyze_structure", _boom)

    r = client.post("/api/produce/extract_from_url",
                     json={"url": "https://insta/p/FAIL", "shortcode": "FAIL1"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["full_text"] == "본문"
    assert d["structure"] is None
