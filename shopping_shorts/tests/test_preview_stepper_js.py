from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


# (옛 피팅룸 마크업 시험은 2026-10-01 삭제 — 관제 058 C1, 옛 6단계 HTML 제거)

def test_caption_preview_uses_variable_not_hardcoded():
    # 자막 미리보기 텍스트가 전역 변수를 쓰고, 하드코딩 문자열 직접대입은 사라졌다
    assert "PREVIEW_CAP_TEXT" in HTML
    assert "el.textContent='이렇게 자막이 나와요'" not in HTML


def test_entry_loads_beats_preview():
    # step5 진입 자동완성 근처에서 loadBeatsPreview를 호출한다
    assert "loadBeatsPreview()" in HTML
