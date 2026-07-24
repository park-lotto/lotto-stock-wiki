"""썸네일 제목 추천기(thumb_title) — 대본→짧은 제목 후보.

네트워크·키풀은 건드리지 않는다. 프롬프트가 대본을 싣는지, 무키일 때 None으로
빠지는지(호출부가 502로 돌려주는 계약)만 잠근다.
"""
from shopping_shorts import thumb_title


def test_prompt_carries_script_and_is_thumbnail_flavored():
    job = {"given_script": "밥솥으로 만든 빵 진짜 미쳤다",
           "script_structure": {"tone": "반말"},
           "headcopy": {"text": "밥솥 빵"}}
    p = thumb_title._build_prompt(job)
    assert "밥솥으로 만든 빵 진짜 미쳤다" in p        # 대본이 실렸다
    assert "썸네일 제목" in p                          # SEO가 아니라 썸네일용 규격
    assert "검색용 긴 문장 금지" in p                  # 짧게 강제


def test_generate_returns_none_without_keys(monkeypatch):
    monkeypatch.setattr(thumb_title.key_vault, "get_live_keys_cascade", lambda g: [])
    assert thumb_title.generate({"given_script": "x"}) is None
