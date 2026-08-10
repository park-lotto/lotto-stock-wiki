"""태거가 `0/40건`만 찍으며 헛돌던 2차 사고(2026-08-09) 회귀 테스트.

1차 수리(2026-08-07, test_key_pool_false_exhaustion.py)는 **풀이 통째로 잠겼을 때만**
재검증하도록 만들었다. 이번엔 그걸로 부족했다.

## 실측(서버 2026-08-09)

  - 태거가 `0/40건`을 130채널 넘게 연속으로 찍었다. 누적 1,017 → 1,025 (8건/130채널).
  - shorts_gemini_state.json: 태거가 보는 20개 키가 **전부 소진표시**.
  - 그 키로 실제 비전 호출을 하면 **전부 200 OK**(키 0·1·2 실측 — 태깅까지 성공).
  - 로그에는 `소진표시 오탐 해제 — 키 [...] 되살림`이 **수십 번** 반복.
  - 예외 로그(`실패(무시)`)는 **0건** — 조용히 실패하고 있었다.

## 진짜 원인 (가설 하나는 실측으로 기각했다)

기각된 가설: "RPM 429를 PerDay로 오분류해서 잠근다."
  → 실제 429 원문을 받아보니 `limit: 5, model: gemini-3.5-flash / Please retry in
    45.5s` 이고 `is_daily_exhausted_error`는 **False**로 정상 판정했다. 오분류 아님.

실제 원인은 **페이서가 실제 한도보다 3배 빠르게 키를 내주는 것**이다:

  ① `_RPM_PER_KEY` 기본값이 **15**인데 실측 무료등급 한도는 **분당 5건**
     (429 원문 `limit: 5`). 그래서 페이서가 "이 키는 이제 써도 된다"고 판단하는
     간격(60/15=4초)이 실제 필요한 간격(60/5=12초)의 1/3이다.
  ② 결과적으로 호출의 상당수가 429를 맞는다. 429는 키를 잠그진 않지만
     `quota_sleep=8`초만 자고 재시도하는데, 서버는 **45초 뒤에 오라**고 했다.
  ③ `max_retries=3`이라 8초씩 3번 = 24초 만에 시도가 소진되고 `{}`를 반환한다.
     호출부(tag_one)는 `{}`를 "태깅 실패"로 보고 조용히 건너뛴다 → `0/40건`.

즉 키는 멀쩡한데 **너무 빨리 때려서 전부 429**를 맞고 있었다. 잠금·되살림은
증상이었지 원인이 아니었다.

핵심 결론: 한도를 실제 값으로 맞추고, 서버가 알려준 대기시간을 존중한다.
"""
import json

import pytest

from shopping_shorts import comment_gen
from pipeline.atoms import key_vault


class _Err(Exception):
    """실제 google-genai 예외처럼 문자열만 보고 분류되는 가짜 예외."""


# ── ① 페이서 기본 한도가 실측값(분당 5)과 맞아야 한다 ──────────────────────
def test_default_rpm_matches_measured_free_tier_limit():
    """실측 429 원문이 `limit: 5`다 — 15로 두면 3배 빠르게 때려 429를 자초한다.

    서버 실측(2026-08-09): 한 키를 연타하니 8번째 호출에서 429,
    `limit: 5, model: gemini-3.5-flash / Please retry in 45.5s`.
    """
    assert comment_gen._RPM_PER_KEY <= 5, (
        "무료등급 실측 한도는 분당 5건 — 이보다 크면 페이서가 429를 자초한다"
    )
    assert comment_gen._MIN_GAP_S >= 12.0, (
        "분당 5건이면 키당 최소 12초 간격이어야 한다"
    )


# ── ② 429가 알려준 대기시간을 존중한다 ────────────────────────────────────
def test_retry_delay_is_parsed_from_error():
    """서버가 '45.5초 뒤에 오라'고 하면 8초가 아니라 그만큼 기다려야 한다.

    8초만 자고 재시도하면 3번 다 429를 맞고 조용히 {}를 반환한다(= 0/40건).
    """
    err = _Err(
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded "
        "your current quota... limit: 5, model: gemini-3.5-flash\\nPlease retry in "
        "45.527446125s.'}}"
    )

    assert key_vault.retry_delay_seconds(err) == pytest.approx(45.5, abs=1.0), (
        "429 본문의 'Please retry in N s'를 읽어 그만큼 기다려야 한다"
    )


def test_retry_delay_returns_none_when_absent():
    """대기시간을 안 알려주면 None — 호출부가 기존 기본값을 쓰게 둔다."""
    assert key_vault.retry_delay_seconds(_Err("500 internal error")) is None


# ── ③ 분당 429는 키를 잠그지 않는다 (회귀 방지) ───────────────────────────
def test_per_minute_429_never_locks_key():
    """RPM 초과는 잠깐 쉬면 풀린다 — 하루 소진으로 잠그면 살아있는 키를 버린다."""
    rpm = _Err(
        "429 RESOURCE_EXHAUSTED ... limit: 5, model: gemini-3.5-flash. "
        "Please retry in 45.5s."
    )

    assert key_vault.is_quota_error(rpm), "429이므로 쿼터 오류이긴 하다"
    assert not key_vault.is_daily_exhausted_error(rpm), (
        "분당 초과를 하루 소진으로 읽으면 멀쩡한 키를 그날 내내 잠근다"
    )


def test_per_day_429_still_detected():
    """진짜 하루 소진은 그대로 잡아야 한다(과교정 방지)."""
    perday = _Err(
        "429 RESOURCE_EXHAUSTED. quota_id: GenerateRequestsPerDayPerProjectPerModel, "
        "limit: 500"
    )

    assert key_vault.is_daily_exhausted_error(perday)


# ── ④ 일부만 잠겨도 되살린다 (풀 전체가 잠길 때까지 기다리지 않는다) ────────
@pytest.fixture
def state_file(tmp_path, monkeypatch):
    p = tmp_path / "shorts_gemini_state.json"
    monkeypatch.setattr(comment_gen, "_STATE_PATH", p)
    monkeypatch.setattr(comment_gen, "_last_recheck", {"t": 0.0})
    return p


def _write_state(p, exhausted):
    p.write_text(json.dumps({"date": comment_gen._today_str(),
                             "exhausted": exhausted}), encoding="utf-8")


def test_mostly_locked_pool_is_revived_before_full_lockout(state_file, monkeypatch):
    """20개 중 19개가 잠기면 남은 1개에 부하가 몰려 곧 전멸한다 — 그 전에 되살린다.

    종전엔 `if not live`(전멸)일 때만 재검증해서, 19/20이 오탐이어도 살아있는 1개로
    워커 8개가 달려들어 429를 맞고 그것마저 잠긴 뒤에야 재검증이 돌았다.
    """
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [f"k{i}" for i in range(20)])
    _write_state(state_file, list(range(19)))     # 0~18 잠김, 19만 살아있음
    monkeypatch.setattr(comment_gen, "_probe_key_alive", lambda key, timeout=15: True)

    live = comment_gen._live_key_indices()

    assert len(live) == 20, "오탐이 대부분이면 전멸을 기다리지 말고 되살려야 한다"


def test_healthy_pool_does_not_trigger_recheck(state_file, monkeypatch):
    """대부분 살아있으면 재검증하지 않는다 — 재검증 자체가 쿼터를 먹는다."""
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [f"k{i}" for i in range(20)])
    _write_state(state_file, [0, 1])              # 18개 살아있음
    calls = []
    monkeypatch.setattr(comment_gen, "_probe_key_alive",
                        lambda key, timeout=15: calls.append(key) or True)

    live = comment_gen._live_key_indices()

    assert live == [i for i in range(20) if i not in (0, 1)]
    assert calls == [], "여유가 있으면 재검증 호출은 0이어야 한다"
