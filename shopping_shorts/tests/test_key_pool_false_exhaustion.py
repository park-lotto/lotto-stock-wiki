"""키 소진 '오탐'으로 대본추출이 조용히 죽던 사고(2026-08-07) 회귀 테스트.

증상: 하루 전 담아둔 영상을 제작소로 보내면 "담긴 영상의 대본을 아직 분석하지
못했어요"만 뜬다. 가끔만 그런다.

실측 원인(서버):
  - shorts_gemini_state.json 에 소진표시 20개 / 살아있는 키 3개
  - 그런데 그 20개를 직접 호출하니 **전부 HTTP 200** = 표시만 죽어 있었다
  - 아침 크론(태거 965건·백필)이 풀을 훑고 잠그면 그날 하루 아무도 안 풀어준다
  - extract_script는 키가 없으면 예외 없이 빈 결과를 반환 → 호출부가 "음성 없는
    영상"으로 오해 → 재시도 래치(attempts)만 깎여 3회 후 영구 제외

세 가지를 고쳤고 각각을 여기서 검증한다.
"""
import json
import pytest

from shopping_shorts import comment_gen


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    p = tmp_path / "shorts_gemini_state.json"
    monkeypatch.setattr(comment_gen, "_STATE_PATH", p)
    monkeypatch.setattr(comment_gen, "_last_recheck", {"t": 0.0})
    return p


def _write_state(p, exhausted):
    p.write_text(json.dumps({"date": comment_gen._today_str(),
                             "exhausted": exhausted}), encoding="utf-8")


# ── 고침 ①: 전 키 소진 판정 시 실제로 찔러보고 오탐이면 해제 ──────────────
def test_all_keys_locked_but_alive_are_revived(state_file, monkeypatch):
    """20개가 소진표시인데 실제로는 살아있으면 → 되살려서 서비스가 계속 돈다."""
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [f"k{i}" for i in range(3)])
    _write_state(state_file, [0, 1, 2])          # 전부 잠김
    monkeypatch.setattr(comment_gen, "_probe_key_alive", lambda key, timeout=15: True)

    live = comment_gen._live_key_indices()

    assert live == [0, 1, 2], "실호출 200인 키는 표시를 해제해야 한다"
    assert json.loads(state_file.read_text(encoding="utf-8"))["exhausted"] == [], \
        "되살린 키는 상태파일에서도 빠져야 한다(다음 호출이 또 재검증하면 낭비)"


def test_genuinely_dead_keys_stay_locked(state_file, monkeypatch):
    """진짜 소진(재검증도 실패)이면 되살리지 않는다 — 죽은 키를 계속 때리면 안 된다."""
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [f"k{i}" for i in range(3)])
    _write_state(state_file, [0, 1, 2])
    monkeypatch.setattr(comment_gen, "_probe_key_alive", lambda key, timeout=15: False)

    assert comment_gen._live_key_indices() == []
    assert json.loads(state_file.read_text(encoding="utf-8"))["exhausted"] == [0, 1, 2]


def test_recheck_skipped_while_pool_has_headroom(state_file, monkeypatch):
    """풀에 여유가 있으면 재검증을 안 한다(불필요한 호출로 한도를 먹지 않게).

    ⚠️ 2026-08-09 수정: 종전엔 '하나라도 살아있으면 안 한다'(전멸일 때만)였는데,
    그러면 20개 중 19개가 오탐이어도 남은 1개로 워커가 몰려 429를 맞고 그것마저
    잠긴 뒤에야 재검증이 돌았다 — 그 사이 태깅은 계속 0건이었다. 지금은 살아있는
    키가 풀의 20% 이하로 줄면 '거의 전멸'로 보고 재검증한다. 그래서 여유 있음을
    검증하려면 키를 넉넉히 두고 소수만 잠근다.
    """
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [f"k{i}" for i in range(10)])
    _write_state(state_file, [0, 1])             # 8개 살아있음 = 여유 충분
    calls = []
    monkeypatch.setattr(comment_gen, "_probe_key_alive",
                        lambda key, timeout=15: calls.append(key) or True)

    assert comment_gen._live_key_indices() == [2, 3, 4, 5, 6, 7, 8, 9]
    assert calls == [], "여유가 있으면 재검증 호출은 0이어야 한다"


def test_recheck_is_rate_limited(state_file, monkeypatch):
    """재검증 자체가 쿼터를 먹으므로 쿨다운 안에서는 두 번 돌지 않는다."""
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k0"])
    _write_state(state_file, [0])
    calls = []
    monkeypatch.setattr(comment_gen, "_probe_key_alive",
                        lambda key, timeout=15: calls.append(key) or False)

    comment_gen._live_key_indices()
    comment_gen._live_key_indices()

    assert len(calls) == 1, "쿨다운 안의 2번째 호출은 재검증을 건너뛰어야 한다"


# ── 고침 ②: 키가 없으면 조용한 빈 결과가 아니라 명시적 예외 ────────────────
def test_extract_raises_instead_of_silent_empty(monkeypatch):
    """키 풀이 잠기면 KeyPoolExhausted를 올린다 — 빈 결과로 위장하면 안 된다.

    이게 사고의 핵심이었다: 호출부가 '키 없음'과 '음성 없는 영상'을 구분 못 했다.
    """
    from shopping_shorts import script_extract

    monkeypatch.setattr(script_extract, "SHORTS_GEMINI_KEYS", ["k0"])
    monkeypatch.setattr(script_extract.comment_gen, "_current_key_and_idx",
                        lambda: (None, None))
    monkeypatch.setattr(script_extract, "_boundary_hint",
                        lambda p: ("", [], 30.0))
    monkeypatch.setattr(script_extract, "_video_duration", lambda p: 20.0)

    with pytest.raises(script_extract.KeyPoolExhausted):
        script_extract.extract_script("/tmp/nonexistent.mp4", "TESTCODE")


# ── 고침 ③: 키 소진 실패는 재시도 래치를 깎지 않는다 ──────────────────────
def test_rollback_restores_retry_budget(tmp_path):
    """영상 탓이 아닌 실패는 attempts를 되돌려야 자동추출에서 영구 제외되지 않는다."""
    from shopping_shorts.store import Store

    store = Store(str(tmp_path / "t.db"))
    code = "ABC123"
    for _ in range(3):
        store.autoload_mark_attempt(code)
    assert store.autoload_attempts([code])[code] == 3, "3회면 latched 상태"

    store.autoload_rollback_attempt(code, "예열 보류: 키 풀 소진")

    assert store.autoload_attempts([code])[code] == 2, \
        "키 소진 실패는 시도 횟수를 돌려줘야 한다"


def test_rollback_never_goes_negative(tmp_path):
    from shopping_shorts.store import Store

    store = Store(str(tmp_path / "t2.db"))
    store.autoload_mark_attempt("X")
    store.autoload_rollback_attempt("X")
    store.autoload_rollback_attempt("X")

    assert store.autoload_attempts(["X"]).get("X", 0) == 0
