"""원샷링크딸깍 자막 조각 — 화면 글자(공백·부호 포함) ≤ 프리셋 caption_max_chars(preset_make A9 와 같은 값)."""
from tools.calcopy.oneshot import to_work as T


def test_caption_max_from_manifest():
    assert T.caption_max("잇썸홈") == 13 and T.caption_max("재미썸홈") == 13


def test_pieces_fit_a9_and_no_tiny_tail():
    # 10-18 실측: chunk_sentence(공백 뺀 기준)만 쓰니 17자 조각이 A9 에 걸렸다
    for t in ["출장 갈 때 축축한 칫솔 챙기기 불편했던 직장인이 통 안에 살균기를 쏙 숨겨버렸대요.",
              "양치하고 혀로 쓸어보면 스케일링 받은 것처럼 매끈해요.",
              "진짜 핵심은 이건데, 그때 분당 3만 1천 번이던 진동을 분당 4만 번까지 올렸다고 하더라고요."]:
        ps = T.pieces_of(t, 13)
        assert all(len(p) <= 13 for p in ps), ps
        assert all(len(p) >= 4 for p in ps), ps
        assert "".join(ps).replace(" ", "") == t.replace(" ", "").replace(".", "").replace(",", "")


def test_no_break_inside_number():
    ps = T.pieces_of("진짜 핵심은 이건데, 그때 분당 3만 1천 번이던 진동을 분당 4만 번까지 올렸다고 하더라고요.", 13)
    assert not any(p.endswith("3만") for p in ps), ps
