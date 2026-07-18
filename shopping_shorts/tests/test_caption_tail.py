import re
from shopping_shorts import video_assemble as va


def _ends(parts):
    """enable='between(t,START,END)'의 END만 뽑는다(바 포함)."""
    out = []
    for p in parts:
        m = re.search(r"between\(t,[\d.]+,([\d.]+)\)", p)
        if m:
            out.append(float(m.group(1)))
    return out


def _starts(parts):
    out = []
    for p in parts:
        m = re.search(r"between\(t,([\d.]+),", p)
        if m:
            out.append(float(m.group(1)))
    return out


def test_tail_zero_no_caption_past_beat_end(tmp_path):
    # 중간 비트(tail=0.0): 어떤 자막/바도 비트 끝(t0+dur)을 넘지 않는다 → 다음 비트와 안 겹침.
    n = "여러분 오이 절대 냉장고에 그냥 두지 마세요 이 방법은 진짜"
    parts = va._caption_drawtexts(n, 6.0, tmp_path, 0, t0=2.0, tail=0.0)
    assert _ends(parts), "enable 절이 있어야"
    assert max(_ends(parts)) <= 2.0 + 6.0 + 1e-6   # t0+dur


def test_tail_default_still_lingers_half_second(tmp_path):
    # 기본(tail=0.5, 마지막 비트용): 마지막 자막·바는 t0+dur+0.5까지 유지(기존 동작 보존).
    n = "여러분 오이 절대 냉장고에 그냥 두지 마세요 이 방법은 진짜"
    parts = va._caption_drawtexts(n, 6.0, tmp_path, 0, t0=2.0)   # 기본 tail
    assert abs(max(_ends(parts)) - (2.0 + 6.0 + 0.5)) < 1e-6


def test_consecutive_beats_no_caption_overlap(tmp_path):
    # _burn_captions가 하는 것 그대로: 중간 비트 tail=0.0, 마지막 비트 tail=0.5.
    # 비트0의 마지막 자막 끝이 비트1 첫 자막 시작을 넘지 않아야 전환 겹침이 없다.
    # (수정 전 tail=0.5였다면 비트0 끝=3.5 > 비트1 시작=3.0 → 겹쳐 실패)
    p0 = va._caption_drawtexts("가나 다라 마바", 3.0, tmp_path, 0, t0=0.0, tail=0.0)
    p1 = va._caption_drawtexts("사아 자차 카타", 2.0, tmp_path, 1, t0=3.0, tail=0.5)
    assert _ends(p0) and _starts(p1)
    assert max(_ends(p0)) <= min(_starts(p1)) + 1e-6
