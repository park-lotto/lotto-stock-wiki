"""끝 자막 겹침(2026-07-25) — headcopy가 enable 없으면 영상 전체에 깔려 마지막 비트 CTA
자막과 두 줄로 충돌한다(job 57ec653ba579: 상단 '댓글에 바나나라고' + 하단 CTA). 기본 enable을
마지막 비트 시작 전까지로 제한해 끝에서 headcopy가 사라지게 한다."""
from shopping_shorts import video_assemble as va


def test_headcopy_default_enable_stops_before_last_beat():
    timeline = [
        {"t0": 0.0, "dur": 4.0}, {"t0": 4.0, "dur": 4.0}, {"t0": 8.0, "dur": 3.0},
    ]
    enable = va._default_headcopy_enable(timeline)
    assert enable is not None
    # 마지막 비트 시작(8.00)이 상한으로 들어가야 함 (그 뒤엔 headcopy 안 뜸)
    assert "8.00" in enable
    assert enable.startswith("lte(t,")


def test_headcopy_none_when_single_beat():
    assert va._default_headcopy_enable([{"t0": 0.0, "dur": 5.0}]) is None


def test_headcopy_none_when_empty():
    assert va._default_headcopy_enable([]) is None
