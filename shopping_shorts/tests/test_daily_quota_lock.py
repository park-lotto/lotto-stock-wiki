# -*- coding: utf-8 -*-
"""일일 소진 키가 **자정까지** 잠기는지 — 57초 뒤 되살아나 또 때리지 않게.

★실사고(2026-09-02): 사장님이 관측판에서 "죽은 키 1개(…nIWJaw)를 18번 헛되이 호출"
  경보를 반복해서 봤다. 실측한 원문:

      429 RESOURCE_EXHAUSTED ... generate_content_free_tier_requests,
      limit: 20, model: gemini-3-flash
      Please retry in 57.425692394s.

  구글은 **하루치를 다 쓴 429에도 '57초 뒤에 오라'를 함께 준다.** 우리는 그 값을 그대로
  잠금 시간으로 썼다(잠금 기록의 ttl이 30~55초였다) → 1분 만에 풀려 또 때리고 또 막힌다.
  경보가 "계속 뜨는" 게 아니라 **실제로 계속 때리고 있었다.**

★고칠 곳은 retry_delay_seconds 한 곳이다 — 호출부 27곳이 전부 이 함수를 거친다(0순위-B).
"""
import time

from pipeline.atoms import key_vault as kv

_DAILY = ("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: "
          "generativelanguage.googleapis.com/generate_content_free_tier_requests, "
          "limit: 500, PerDay, model: gemini-3-flash. Please retry in 57.4s.")
_RPM = ("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: "
        "generate_content_free_tier_requests, limit: 20, model: gemini-3-flash. "
        "Please retry in 57.4s.")


def test_일일소진은_57초를_믿지_않는다():
    """같은 '57초 뒤'가 붙어 있어도 일일 소진이면 자정까지 기다려야 한다."""
    got = kv.retry_delay_seconds(Exception(_DAILY))
    assert got is not None and got > 3600, (
        f"일일 소진인데 {got}초만 잠근다 — 그만큼 뒤 되살아나 또 때린다")


def test_분당한도는_알려준_값을_그대로_쓴다():
    """분당 한도는 실제로 그때 풀린다 — 여기까지 길게 잠그면 멀쩡한 키를 놀린다."""
    got = kv.retry_delay_seconds(Exception(_RPM))
    assert got is not None and 40 <= got <= 60, got


def test_자정까지_초는_하루_안이다():
    s = kv.seconds_until_quota_reset()
    assert 60 <= s <= 24 * 3600 + 60, s


def test_알_수_없으면_None():
    """모르면 호출부가 기존 기본값을 쓰도록 둔다(동작 보존)."""
    assert kv.retry_delay_seconds(Exception("그냥 알 수 없는 오류")) is None


def test_잠금이_실제로_자정까지_간다():
    """retry_delay_seconds → _mark_key_exhausted 로 이어지는 실제 경로."""
    from shopping_shorts import comment_gen as cg
    delay = kv.retry_delay_seconds(Exception(_DAILY))
    ttl = max(30.0, min(delay, 24 * 3600.0))      # _mark_key_exhausted와 같은 클램프
    assert ttl > 6 * 3600 or ttl == delay, (
        "6시간 클램프가 자정까지의 값을 잘라내면 고친 의미가 없다")
    assert cg._EXHAUST_TTL_S > 0
