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


def test_redo_button_is_wired_to_the_confirming_function():
    """stale일 때 나오는 버튼이 **확인창을 거치는** 함수를 불러야 한다.
    startCleanPreview를 직접 부르면 확인 없이 크레딧이 나간다."""
    assert "onclick=\"redoCleanForNewScenes()\"" in _HTML
    assert "function redoCleanForNewScenes()" in _HTML
    body = _HTML[_HTML.index("function redoCleanForNewScenes()"):]
    body = body[:body.index("\n}\n")]
    assert "confirm(" in body                      # 누르기 전에 묻는다
    assert "startCleanPreview()" in body            # 확인하면 실제로 돈다


def test_server_fields_are_read_into_the_page():
    """clean_redo·clean_credit_est를 화면이 실제로 읽어야 한다(배선 누락 방지)."""
    assert "sg.clean_redo" in _HTML
    assert "sg.clean_credit_est" in _HTML


def test_stale_note_tells_what_to_do_not_just_that_it_is_stale():
    """★경고만 있고 지시가 없으면 고객은 무엇을 눌러야 할지 모른다(사장님 제보의 본체)."""
    i = _HTML.index("const staleNote")
    block = _HTML[i:i + 1200]
    assert "다시 지우기" in block                  # 행동을 준다
    assert "장면을 바꾸기 전" in block              # 왜 그런지 말한다
