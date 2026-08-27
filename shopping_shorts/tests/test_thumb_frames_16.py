"""썸네일 배경 후보 16장 + [다른 장면 더 뽑기](2026-08-27 사장님).

사장님 제보: 후보 10장 중 고를 만한 건 케이크가 또렷한 몇 장뿐이고 나머지는 흐릿한
배너·빈 벽이었다. "16장으로 하고 새로고침으로 더 나오게" → 기본 16장 + 라운드마다
찍는 지점을 어긋나게 해 새 16장을 준다.

★원본 영상에서 뽑지 않는 이유(사장님 "원본 썸네일쪽 제목없는장면은 캡쳐가 힘드나"):
  원본은 자막이 안 지워져 글자가 남는다. 글자 유무를 자동 판별하려면 OCR이 필요한데
  이 프로젝트엔 없다(sub_region은 원본↔클린 diff라 원본 단독 판정은 못 한다).
  그래서 자막 없는 완성본에서 **더 많이** 뽑는 쪽으로 갔다.
"""
from shopping_shorts import frame_extract
from shopping_shorts.app import _grid_phase


def test_default_is_16():
    """기본 장수는 16 — 화면이 8개씩 2줄로 보여주는 수와 같아야 한다."""
    assert frame_extract.GRID_FRAMES_DEFAULT == 16


def test_phase_first_round_is_center():
    """첫 라운드는 종전과 같은 '구간 중앙' — 기존 동작 회귀 0."""
    assert _grid_phase(0) == 0.5


def test_phase_rounds_never_repeat():
    """★뿌리: 라운드마다 **아직 안 본 지점**이 나와야 한다.

    난수로 하면 같은 자리가 다시 걸려 "눌러도 그대로"가 된다 — 사장님이 겪을 그 증상.
    van der Corput 수열이라 격자가 반씩 어긋난다.
    """
    phases = [_grid_phase(r) for r in range(8)]
    assert len(set(phases)) == 8, f"라운드끼리 지점이 겹친다: {phases}"


def test_phase_stays_inside_safe_range():
    """0초(검은 첫 프레임)·정각(범위 밖 → 추출 실패)을 피한다."""
    for r in range(40):
        assert 0.05 <= _grid_phase(r) <= 0.95


def test_phase_survives_junk():
    """이상한 값이 와도 터지지 않는다 — 여기서 죽으면 썸네일 단계가 통째로 막힌다."""
    for bad in (None, "", "x", -5, 1.5):
        assert 0.05 <= _grid_phase(bad) <= 0.95


def test_rounds_produce_distinct_timestamps():
    """실제 시각으로 환산해도 라운드끼리 안 겹친다(30초·16장 기준 실측)."""
    dur, n = 30.0, frame_extract.GRID_FRAMES_DEFAULT
    seen = set()
    for r in range(4):
        ph = _grid_phase(r)
        ts = {round(dur * (i + ph) / n, 2) for i in range(n)}
        assert not (seen & ts), f"라운드 {r}에서 이전과 같은 시각이 나왔다"
        seen |= ts
    assert len(seen) == n * 4


def test_extract_grid_frames_signature():
    """호출부가 phase를 넘길 수 있어야 한다(안 넘기면 종전대로 중앙)."""
    import inspect
    sig = inspect.signature(frame_extract.extract_grid_frames)
    assert sig.parameters["n"].default == 16
    assert sig.parameters["phase"].default == 0.5
