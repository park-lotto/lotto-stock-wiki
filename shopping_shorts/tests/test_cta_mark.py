# -*- coding: utf-8 -*-
"""CTA 표시(관제 45, 2026-09-30 김성현님) — 유튜브용 CTA 잘라내기가 '마무리'·'댓글유도' 칸에서도 되게.

라이브 7일 실측: CTA 문구로 끝나는데 못 자른 작업 34건(마무리 18·댓글유도 5·call_to_action 4 …).
판단 주인: edit_plan.guess_cta_index / apply_cta_mark / _is_cta. 자를 지점: video_assemble.cta_cut_sec.
"""
from shopping_shorts import edit_plan as ep
from shopping_shorts.video_assemble import cta_cut_sec

# 김성현님 eef350b2e52e 마지막 두 칸(라이브 원문)
SUL_LINES = ["손빨래 귀찮아서 저 처럼 모아서 세탁기 돌렸던 분들",
             "댓글에 '손빨래' 남겨주시면 정보 보내드릴게요."]
SUL_ROLES = ["반전", "마무리"]


def _beats(lines, roles):
    return [{"beat_idx": i, "role": r, "narration": t} for i, (t, r) in enumerate(zip(lines, roles))]


def test_role_synonyms_now_cta():
    for r in ("call_to_action", "call-to-action", "댓글유도", "CTA", "cta"):
        assert ep._is_cta({"role": r}), r
    assert not ep._is_cta({"role": "마무리"})


def test_mark_overrides_role():
    assert ep._is_cta({"role": "마무리", "cta_mark": True})
    assert not ep._is_cta({"role": "CTA", "cta_mark": False})


def test_guess_sul_closing_line():
    assert ep.guess_cta_index(SUL_LINES, SUL_ROLES) == 1


def test_guess_quoted_keyword_without_word_comment():
    """김성현님 3b4111969ac4 원문 — '댓글'이란 말 없이 따옴표 키워드만(NBSP 포함)."""
    lines = ["직장인 사이에 난리난 주름 5초컷", "궁금하신 분들은\xa0 '주름'이라고 남겨주세요."]
    assert ep.guess_cta_index(lines, ["반전", "마무리"]) == 1


def test_guess_profile_link():
    assert ep.guess_cta_index(["훅", "긍금하면 프로필 링크에"], ["훅", "마무리"]) == 1


def test_guess_none_when_plain_closing():
    assert ep.guess_cta_index(["훅", "진짜 저만 알기 아까운 요물템!"], ["훅", "마무리"]) is None


def test_guess_mid_comment_not_cta():
    lines = ["훅", "댓글에 '주름' 남겨주세요", "그리고 이렇게 쓰면 끝"]
    assert ep.guess_cta_index(lines, ["훅", "고조", "마무리"]) is None


def test_guess_role_first():
    assert ep.guess_cta_index(["훅", "사세요", "끝 인사"], ["hook", "CTA", "마무리"]) == 1


def test_apply_auto_marks_closing_and_cut_found():
    beats = _beats(SUL_LINES, SUL_ROLES)
    ep.apply_cta_mark(beats, "\n".join(SUL_LINES), {})
    assert [b["cta_mark"] for b in beats] == [False, True]
    tl = [dict(b, t0=float(i) * 3.2) for i, b in enumerate(beats)]
    assert cta_cut_sec(tl) == 3.2


def test_apply_explicit_off():
    beats = _beats(SUL_LINES, SUL_ROLES)
    ep.apply_cta_mark(beats, "\n".join(SUL_LINES), {"cta_line": -1})
    assert not any(ep._is_cta(b) for b in beats)


def test_apply_explicit_line():
    lines = ["훅", "가운데를 CTA로", "끝"]
    beats = _beats(lines, ["hook", "body", "마무리"])
    ep.apply_cta_mark(beats, "\n".join(lines), {"cta_line": 1, "cta_text": "가운데를 CTA로"})
    assert [ep._is_cta(b) for b in beats] == [False, True, False]


def test_apply_by_text_when_counts_differ():
    lines = ["훅", "본문", "댓글에 '주름' 남겨주세요"]
    beats = _beats(["훅", "본문 앞", "본문 뒤", "댓글에 '주름' 남겨주세요"], ["hook", "a", "b", "마무리"])
    ep.apply_cta_mark(beats, "\n".join(lines), {"cta_line": 2, "cta_text": lines[2]})
    assert [ep._is_cta(b) for b in beats] == [False, False, False, True]


def test_apply_noop_without_cta():
    lines = ["훅", "진짜 좋아요"]
    beats = _beats(lines, ["hook", "마무리"])
    ep.apply_cta_mark(beats, "\n".join(lines), None)
    assert all("cta_mark" not in b for b in beats)


def test_existing_cta_role_unchanged():
    lines = ["훅", "소감", "댓글에 '후크' 남겨주시면 정보 보내드릴게요."]
    beats = _beats(lines, ["훅", "소감", "CTA"])
    ep.apply_cta_mark(beats, "\n".join(lines), {})
    assert [ep._is_cta(b) for b in beats] == [False, False, True]


def test_mark_survives_beat_timeline_to_cut():
    """★실제 자르기 경로 — 칸 → _beat_timeline → cta_cut_sec. 표시가 타임라인에서 빠지면 못 자른다
    (2026-09-30 라이브 3b4111969ac4로 발견: cta_cut_sec만 직접 부른 테스트는 통과했었다)."""
    from unittest.mock import patch
    from shopping_shorts.video_assemble import _beat_timeline
    beats = _beats(SUL_LINES, SUL_ROLES)
    ep.apply_cta_mark(beats, "\n".join(SUL_LINES), {})
    with patch("shopping_shorts.video_assemble._probe_duration", side_effect=[4.0, 3.0]):
        tl = _beat_timeline({"beats": beats}, {0: "a.mp3", 1: "b.mp3"})
    assert cta_cut_sec(tl) == 4.0
