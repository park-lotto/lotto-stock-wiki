"""Task9 실렌더가 잡은 결함 2건의 회귀 테스트 — 시간축.

두 결함 다 "필터 문자열은 그럴듯한데 실제 영상이 틀린" 종류였다. 그래서 실렌더로
픽셀 증명을 따로 했고(2026-07-16, 수정전/후 같은 조건 렌더 비교), 이 파일은
**되돌림 방지용 자물쇠**다. 이것만으로 '검증했다'고 하면 안 된다 — 그게 Phase1이
'육안검증 통과'라 적어놓고 실은 정지 프레임을 보고 통과시킨 이유다.

실렌더 증거(2026-07-16, 합성 자산·gray 베이스):
- 결함① 수정전 흰사각형 y=[767,767,767](정지) → 수정후 y=[162,383,629](재생)
- 결함② 비트0 자막 최대밝기 수정전 12/255 → 수정후 255/255 (어제 실자산 실측 9/255와 일치)
  마지막 비트는 수정 전후 모두 255/255 = 회귀 없음
"""
from shopping_shorts.video_assemble import _caption_drawtexts, _motion_layer_filters


# ── 결함① start>0 레이어가 정지 잔상이 되던 것 (setpts) ──────────

def test_layer_with_start_shifts_its_own_pts():
    """enable=은 '언제 그릴지'만 정하고 소스 PTS는 벽시계를 따라간다. setpts로 레이어
    자신의 시간을 밀지 않으면 enable 창이 열릴 때 자산은 이미 끝나 정지 프레임만 깔린다."""
    _, fc, _, _ = _motion_layer_filters(
        [{"_abspath": "/x/swipe.mov", "start": 3.0, "dur": 1.0}], 1, "v0")
    chain = fc[0]
    assert "setpts=PTS-STARTPTS+3.000/TB" in chain, \
        "★start>0인데 setpts가 없다 — 정지 잔상으로 되돌아갔다"
    assert chain.index("setpts") < chain.index("format=rgba"), \
        "setpts는 포맷 변환보다 앞이어야 한다"


def test_layer_without_start_has_no_setpts():
    """start=0은 원점이라 이동이 no-op — 필터를 불필요하게 늘리지 않는다(기존 산출물 호환)."""
    _, fc, _, _ = _motion_layer_filters(
        [{"_abspath": "/x/swipe.mov", "start": 0, "dur": 1.0}], 1, "v0")
    assert "setpts" not in fc[0]


def test_layer_enable_window_matches_start_and_dur():
    _, fc, _, _ = _motion_layer_filters(
        [{"_abspath": "/x/swipe.mov", "start": 2.5, "dur": 1.5}], 1, "v0")
    assert "enable='between(t,2.500,4.000)'" in fc[1]


# ── 결함② 자막 바가 비트마다 누적돼 앞 비트를 덮던 것 (drawbox enable) ──

def _bar_part(parts):
    return next((p for p in parts if p.startswith("drawbox=")), None)


def test_caption_bar_is_gated_to_its_own_beat(tmp_path):
    """바에 enable이 없으면 영상 전체에 그려진다. _burn_captions가 비트마다 이 함수를
    호출해 체인에 이어붙이므로, 바 N개가 겹쳐 **먼저 그려진 비트의 자막을 덮는다**
    (0.82 불투명 바 2겹 = 3% → 실측 9~12/255). 마지막 비트만 멀쩡해 보여 놓치기 쉽다."""
    parts = _caption_drawtexts("첫 비트 자막", 3.0, tmp_path, 0, t0=0.0,
                               style={"bar": True})
    bar = _bar_part(parts)
    assert bar, "바가 없다 — bar=True인데(show_bar = bar and not box)"
    assert "enable=" in bar, "★바에 enable이 없다 — 앞 비트 자막이 다시 묻힌다"
    assert "between(t,0.00,3.50)" in bar, f"바 창이 이 비트와 안 맞는다: {bar}"


def test_caption_bar_window_follows_beat_offset(tmp_path):
    """t0가 있는 뒤쪽 비트의 바는 그 비트 구간에만 있어야 한다."""
    parts = _caption_drawtexts("두 번째 비트", 2.0, tmp_path, 1, t0=3.0,
                               style={"bar": True})
    bar = _bar_part(parts)
    assert "between(t,3.00,5.50)" in bar, f"t0 오프셋이 바에 반영 안 됨: {bar}"


def test_caption_bars_of_two_beats_do_not_overlap(tmp_path):
    """★핵심 불변식: 서로 다른 비트의 바 창이 겹치면 누적 덮임이 되살아난다."""
    p0 = _caption_drawtexts("비트0", 3.0, tmp_path, 0, t0=0.0, style={"bar": True})
    p1 = _caption_drawtexts("비트1", 3.0, tmp_path, 1, t0=3.0, style={"bar": True})
    import re

    def win(parts):
        m = re.search(r"between\(t,([\d.]+),([\d.]+)\)", _bar_part(parts))
        return float(m.group(1)), float(m.group(2))

    a0, b0 = win(p0)
    a1, b1 = win(p1)
    # 자막은 세그먼트 종료 후 0.5초 여유를 두므로 경계에서 소폭 겹칠 수 있다.
    # 허용치를 넘어 '통째로' 겹치면(=enable 없음과 사실상 동일) 결함이다.
    assert b0 - a1 <= 0.5, f"비트0 바가 비트1 구간을 0.5초 넘게 침범한다: {(a0, b0)} vs {(a1, b1)}"
    assert a1 < b1 and a0 < b0
