"""말이 없는 영상도 쓸 수 있어야 한다(무음 제품 영상 = 도우인·틱톡에 흔하다).

2026-08-16 실측 사고: 도우인 다운로드를 뚫었는데 그 다음 관문에서
"전사 결과 없음(음성 없음·자막 불가)"으로 버려졌다. 판정이 `full_text`(말)만
봤기 때문인데, 우리 추출은 **화면만 보고도** 장면을 태깅한다 —
실제로 자막 0자 소스가 세그 10개·label 10개로 성공한 기록이 있다.
즉 되는 것을 게이트가 막고 있었다.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from shopping_shorts.script_extract import has_usable_result


def test_speech_is_usable():
    assert has_usable_result({"full_text": "이 제품은", "segments": []})


def test_screen_only_is_usable():
    """★핵심: 말이 없어도 화면 태깅이 나왔으면 재료다."""
    assert has_usable_result(
        {"full_text": "", "segments": [{"scene_desc": "하트 필터에서 에스프레소가 솟아오른다"}]})


def test_empty_is_not_usable():
    """둘 다 없으면 종전대로 버린다 — 빈 대본이 캐시로 굳으면 영원히 빈값이 나온다."""
    assert not has_usable_result({"full_text": "", "segments": [{"scene_desc": ""}]})
    assert not has_usable_result({"full_text": "  ", "segments": []})
    assert not has_usable_result({})
    assert not has_usable_result(None)


def test_gates_use_the_shared_judgment():
    """★판정은 한 곳에만 둔다 — 자동적재와 예열이 서로 다르게 판단하면
    '어떤 건 되고 어떤 건 안 되네'가 재발한다(0순위-B)."""
    for mod in ("app", "prewarm"):
        src = (pathlib.Path(__file__).resolve().parents[1] / f"{mod}.py").read_text(encoding="utf-8")
        assert "has_usable_result(result)" in src, f"{mod}가 공용 판정을 안 쓴다"
        assert "전사 결과 없음" not in src, f"{mod}에 옛 판정 문구가 남아 있다"
