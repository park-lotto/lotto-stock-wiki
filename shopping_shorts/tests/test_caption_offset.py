from shopping_shorts import video_assemble as va


def _starts(parts):
    """drawtext 필터들에서 between(t,START,END)의 START만 뽑는다(바 제외)."""
    import re
    out = []
    for p in parts:
        if "drawbox" in p:
            continue
        m = re.search(r"between\(t,([\d.]+),", p)
        if m:
            out.append(float(m.group(1)))
    return out


def test_cap_offset_zero_is_byte_identical(tmp_path):
    n = "여러분 오이 절대 냉장고에 그냥 두지 마세요 이 방법은 진짜 좋아요"
    base = va._caption_drawtexts(n, 6.0, tmp_path, 0, t0=2.0)
    same = va._caption_drawtexts(n, 6.0, tmp_path, 0, t0=2.0, cap_offset=0.0)
    assert base == same


def test_cap_offset_shifts_all_caption_starts(tmp_path):
    n = "여러분 오이 절대 냉장고에 그냥 두지 마세요 이 방법은 진짜 좋아요"
    base = _starts(va._caption_drawtexts(n, 6.0, tmp_path, 0, t0=2.0))
    pushed = _starts(va._caption_drawtexts(n, 6.0, tmp_path, 0, t0=2.0, cap_offset=0.3))
    assert len(base) == len(pushed) and len(base) >= 2
    for b, p in zip(base, pushed):
        assert abs((p - b) - 0.3) < 0.01   # 모든 구절이 +0.3초


def test_cap_offset_clamps_start_nonnegative(tmp_path):
    n = "여러분 오이 절대 두지 마세요"
    pulled = _starts(va._caption_drawtexts(n, 6.0, tmp_path, 0, t0=0.0, cap_offset=-5.0))
    assert all(s >= 0.0 for s in pulled)   # 당겨도 음수 시각 없음
