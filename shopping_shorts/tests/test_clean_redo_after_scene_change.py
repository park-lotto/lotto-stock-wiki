# -*- coding: utf-8 -*-
"""장면을 바꾼 뒤 '지금 다시 지우기' + 등급 되돌리기 안내 (2026-09-17 사장님).

사장님 지시 두 가지:
  ① "자막 기본으로 지운 뒤에 별로면 고급으로 다시 할 수 있게"
  ② "지운 뒤에 3단계에서 장면 바꾸고 다시 오니까 이전 장면들로 해야 한다. 수정 가능하게"

★뼈대는 이미 있었다(실측): 등급마다 파일이 따로 남고(_clean_sig에 'p' 접미사),
  장면을 바꾸면 편성 서명이 바뀌어 옛 청소본이 재사용되지 않는다.
  없던 것은 **화면이 그 사실을 알고 행동으로 옮기게 하는 정보**다:
    - 지금 편성으로 만든 게 없는데 **옛 편성으로 만든 건 있다**(=다시 지워야 한다)
    - 다시 지우면 크레딧이 얼마나 나가나(누르기 전에 확인창을 띄우려면 숫자가 필요)
"""
import json

import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts.vmake_client import TIER_BASIC, TIER_PRO


def _plan(vid="s0", secs=3.0):
    return {"beats": [{"beat_idx": 0, "target_seconds": secs,
                       "primary": {"video_id": vid, "start": 0, "end": secs}}]}


def _mk(work, job, tier):
    """그 등급의 청소본 파일을 실제로 만들어 둔다(판정은 파일 존재로 한다)."""
    f = work / ("final_clean_%s.mp4" % mp._clean_sig({**job, "clean_tier": tier}))
    f.write_bytes(b"x" * 2048)
    return f


# ── ① 등급 되돌리기 — 이미 만든 등급은 공짜다 ──────────────────────────────
def test_tiers_ready_marks_only_the_tier_that_exists(tmp_path):
    job = {"edit_plan": _plan(), "clean_tier": TIER_BASIC}
    _mk(tmp_path, job, TIER_BASIC)
    r = mp.clean_tiers_ready(job, tmp_path)
    assert r[TIER_BASIC] is True and r[TIER_PRO] is False


def test_basic_and_pro_are_separate_files_so_switching_recleans(tmp_path):
    """★기본으로 지운 뒤 고급으로 바꾸면 **옛 기본 결과가 재사용되면 안 된다**."""
    job = {"edit_plan": _plan()}
    assert (mp._clean_sig({**job, "clean_tier": TIER_BASIC})
            != mp._clean_sig({**job, "clean_tier": TIER_PRO}))


# ── ② 장면을 바꾼 뒤 — 옛 청소본이 있다는 걸 화면이 알아야 한다 ─────────────
def test_scene_change_invalidates_the_signature(tmp_path):
    """장면(primary.video_id)을 바꾸면 서명이 달라져 재청소가 일어난다."""
    a = mp._clean_sig({"edit_plan": _plan("s0"), "clean_tier": TIER_PRO})
    b = mp._clean_sig({"edit_plan": _plan("s4"), "clean_tier": TIER_PRO})
    assert a != b


def test_redo_state_says_stale_when_only_old_plan_was_cleaned(tmp_path):
    """★핵심: 지금 편성으로는 없고 **옛 편성으로 만든 청소본은 있다** → '다시 지워야 한다'.

    이 상태를 화면이 못 받으면 사장님이 겪은 그대로가 된다 —
    장면을 바꾸고 3단계로 돌아왔는데 옛 장면 결과가 떠 있고, 무엇을 눌러야 할지 모른다.
    """
    old = {"edit_plan": _plan("s0"), "clean_tier": TIER_BASIC}
    _mk(tmp_path, old, TIER_BASIC)                    # 옛 편성으로만 만들어 둔 상태
    now = {"edit_plan": _plan("s4"), "clean_tier": TIER_BASIC}   # 장면을 바꿨다
    st = mp.clean_redo_state(now, tmp_path)
    assert st["stale"] is True                        # 옛 결과가 남아 있다
    assert st["ready"] is False                       # 지금 편성 결과는 없다


def test_redo_state_is_not_stale_on_a_fresh_job(tmp_path):
    """한 번도 안 지운 작업은 stale이 아니다 — 첫 실행에 '다시'라고 하면 거짓말이다."""
    st = mp.clean_redo_state({"edit_plan": _plan(), "clean_tier": TIER_BASIC}, tmp_path)
    assert st["stale"] is False and st["ready"] is False


def test_redo_state_ready_when_current_plan_was_cleaned(tmp_path):
    job = {"edit_plan": _plan(), "clean_tier": TIER_BASIC}
    _mk(tmp_path, job, TIER_BASIC)
    st = mp.clean_redo_state(job, tmp_path)
    assert st["ready"] is True and st["stale"] is False


# ── 확인창에 쓸 크레딧 추정 (사장님: "누르기 전에 확인창") ───────────────────
@pytest.mark.parametrize("secs,tier,want", [
    (30.0, TIER_BASIC, 60),      # 초당 2크레딧
    (30.0, TIER_PRO, 120),       # 초당 4크레딧
    (17.6, TIER_PRO, 72),        # ★초 단위 올림(18초×4) — 실측 job 44112f9a6e64 길이
    (0.1, TIER_BASIC, 2),
])
def test_credit_estimate_matches_the_posted_price(secs, tier, want):
    """화면에 적힌 요금(1초에 2/4크레딧, 초 단위 올림)과 **같은 식**이어야 한다.
    안내 문구와 추정이 어긋나면 그 자체가 거짓 안내다."""
    assert mp.clean_credit_estimate(secs, tier) == want


def test_credit_estimate_unknown_length_returns_none(tmp_path):
    """길이를 못 재면 숫자를 지어내지 않는다 — 확인창은 숫자 없이 뜬다."""
    assert mp.clean_credit_estimate(None, TIER_PRO) is None


# ── 화면 배선 — 서버가 준 값을 화면이 실제로 쓰는가 ─────────────────────────
# ★문자열 검색만으로는 "있다"밖에 못 본다. 배선이 끊기면 값은 서버에 있는데 화면은
#   모르는 조용한 실패가 난다(이 저장소가 여러 번 데인 모양) — 그래서 **부르는 쪽**과
#   **선언**을 함께 확인한다.
import io
import os
import re

_HTML = io.open(os.path.join(os.path.dirname(__file__), "..", "static", "produce.html"),
                encoding="utf-8").read()


def test_no_paid_redo_button_in_the_compare_screen():
    """★비교 화면에 **돈 나가는 버튼**을 두지 않는다(2026-09-20 사장님 "헷갈리니까 없애").

    장면을 바꿔도 고객이 할 일은 없다 — 최종 렌더가 알아서 다시 지운다. 그런데 버튼이
    있으면 '해야 하는 일'로 읽혀 크레딧을 한 번 더 태운다. 함수까지 지워 죽은 코드를
    남기지 않는다(다음 세션이 '왜 안 불리지?'로 헤매지 않게).
    """
    assert "redoCleanForNewScenes" not in _HTML


def test_server_fields_are_read_into_the_page():
    """clean_redo·clean_credit_est를 화면이 실제로 읽어야 한다(배선 누락 방지)."""
    assert "sg.clean_redo" in _HTML
    assert "sg.clean_credit_est" in _HTML


def test_stale_note_is_gone_entirely():
    """★2026-09-20 사장님: "이런건 빼라고 의미없고 / 성공했는지만 표시".

    이 자리는 두 번 줄었다. ①'지금 장면으로 다시 지워야 합니다' + 빨간 재청소 버튼 →
    ②'렌더 때 다시 지웁니다(크레딧)' 한 줄 → ③**없음**. 고객이 **할 일이 없는 일**을
    알리면 '뭘 해야 하나' 하고 멈출 뿐이다. 화면은 성공했는지만 말한다.
    """
    i = _HTML.index("const staleNote")
    block = _HTML[i:i + 400]
    assert "const staleNote = '';" in block
    assert "다시 지워야 합니다" not in block
    assert "크레딧은 그때 나갑니다" not in block


def test_compare_shows_which_side_is_actually_used():
    """★되돌렸는데 그림이 그대로면 '아무 일도 안 일어난' 것으로 보인다(2026-09-20 사장님 제보).

    버튼만 바뀌고 BEFORE/AFTER가 그대로라 '자막 제거됨 ✓'이 살아 있었다. 지금 쓰는 쪽에
    체크와 강조를 두고, 안 쓰는 쪽은 흐려야 한 눈에 갈린다.
    """
    i = _HTML.index("const _useClean = CLEAN_IN_USE")
    block = _HTML[i:i + 1600]
    assert "이걸 씁니다" in block                    # 원본을 쓸 때 그렇게 말한다
    assert "지금은 안 씀" in block                   # 청소본이 놀고 있다는 표시
    assert "grayscale" in block                     # 안 쓰는 쪽을 흐린다


# ── 실패한 뒤 돌아왔을 때 — 옛 결과가 있으면 그 사실을 말해야 한다 ──────────
# ★2026-09-17 실측(이윤정님 job 1556910737b6): clean_status='failed'인데
#   /clean_clips가 stale=False로 답해서, 화면은 "옛 청소본이 있다"는 걸 몰랐다.
#   고객이 보는 건 **아무 설명 없는 빈 비교화면**이다 — 무엇을 눌러야 할지 모른다.
#   ready가 아니어도 옛 청소본이 남아 있으면 stale로 알린다.
def test_clean_clips_reports_stale_when_failed_but_old_clean_exists(tmp_path, monkeypatch):
    import shopping_shorts.app as appmod

    job = {"job_id": "j", "clean_status": "failed",
           "edit_plan": _plan("s4"), "clean_tier": TIER_BASIC}
    work = tmp_path / "j"
    work.mkdir()
    _mk(work, {"edit_plan": _plan("s0")}, TIER_BASIC)   # 옛 편성으로 만든 청소본이 남아 있다

    monkeypatch.setattr(appmod, "_MIX_WORK_DIR", tmp_path)
    monkeypatch.setattr(appmod, "Store", lambda _p: type("S", (), {
        "get_mix_job": staticmethod(lambda _j: job)})())

    r = appmod.api_produce_mix_clean_clips("j")
    assert r["ready"] is False
    assert r["stale"] is True          # ★옛 결과가 있다는 걸 숨기지 않는다


def test_clean_clips_not_stale_on_a_never_cleaned_job(tmp_path, monkeypatch):
    """한 번도 안 지운 작업은 stale이 아니다 — 첫 실행에 '옛 결과'라고 하면 거짓말이다."""
    import shopping_shorts.app as appmod

    job = {"job_id": "j2", "clean_status": None,
           "edit_plan": _plan(), "clean_tier": TIER_BASIC}
    (tmp_path / "j2").mkdir()
    monkeypatch.setattr(appmod, "_MIX_WORK_DIR", tmp_path)
    monkeypatch.setattr(appmod, "Store", lambda _p: type("S", (), {
        "get_mix_job": staticmethod(lambda _j: job)})())

    r = appmod.api_produce_mix_clean_clips("j2")
    assert r["ready"] is False and r["stale"] is False
