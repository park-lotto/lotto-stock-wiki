"""비전 주제태그 배선 전체 검증(2026-07-19) — Gemini 호출만 스텁하고
수집훅(_tag_new_items)→저장→캐시→읽기결합(_attach_vision_tags)까지 통합 확인.
실 Gemini 태깅은 서버(systemd 키)에서만 가능 — 로컬은 배선만 검증."""
import shopping_shorts.app as appmod
from shopping_shorts import video_analysis
from shopping_shorts.store import Store


def test_tag_pipeline_wiring(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda url, timeout=15: b"fakeimg")
    monkeypatch.setattr(video_analysis, "subject_tags_vision",
                        lambda img, caption, **kw: {"subject": "오이무침", "keywords": ["오이", "다이어트반찬"]})

    items = [
        {"shortcode": "p1", "thumbnail": "http://x/a.jpg", "caption": "여름 다이어트 반찬"},
        {"shortcode": "p2", "thumbnail": "", "caption": "썸네일 없음"},   # 썸네일 없어 스킵
    ]
    appmod._tag_new_items(items)

    st = Store(db)
    assert st.get_vision_tags("p1")["subject"] == "오이무침"   # 태깅·저장됨
    assert st.get_vision_tags("p2") is None                    # 썸네일 없어 스킵

    # 읽기 결합: 저장된 태그가 아이템에 실린다
    out = appmod._attach_vision_tags([{"shortcode": "p1"}, {"shortcode": "p2"}], st)
    assert out[0]["vision_keywords"] == ["오이", "다이어트반찬"]
    assert "vision_keywords" not in out[1]

    # 캐시: 이미 태그 있으면 재호출 안 함(스텁을 예외로 바꿔도 p1 안 건드림)
    def _boom(*a, **k):
        raise AssertionError("이미 태그 있는데 재태깅하면 안 됨")
    monkeypatch.setattr(video_analysis, "subject_tags_vision", _boom)
    appmod._tag_new_items(items)   # 예외 안 나면 캐시가 동작한 것


def test_tag_cap_defers_overflow(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_VISION_TAG_CAP", 2)          # 상한 2로 낮춰 테스트
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda url, timeout=15: b"x")
    calls = []
    monkeypatch.setattr(video_analysis, "subject_tags_vision",
                        lambda img, caption, **kw: (calls.append(1), {"subject": "s", "keywords": ["k"]})[1])
    items = [{"shortcode": f"p{i}", "thumbnail": "http://x", "caption": ""} for i in range(5)]
    appmod._tag_new_items(items)
    assert len(calls) == 2                                     # 상한만큼만 태깅
    assert Store(db).get_vision_tags("p0") is not None
    assert Store(db).get_vision_tags("p4") is None             # 초과분은 다음 수집으로
