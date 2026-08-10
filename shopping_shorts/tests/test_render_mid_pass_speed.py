"""렌더 단축 — 중간 패스는 빠르게, 최종 1회만 품질(2026-07-31).

같은 화면을 2~3번 인코딩하는데(서브클립 → 비트클립 → 자막 번인) 전부 최종 품질
(CRF 16·medium)로 돌고 있었다. 화질을 정하는 건 마지막 패스라, 중간에 들인 시간은
그대로 버려진다.
"""
import re

from shopping_shorts import video_assemble as va


def _cmd_text(src, func_name):
    """소스에서 함수 하나의 본문 텍스트를 대충 잘라온다(어느 preset을 쓰는지 확인용)."""
    m = re.search(rf"def {func_name}\(.*?(?=\ndef )", src, re.S)
    return m.group(0) if m else ""


def test_mid_pass_is_fast_and_final_keeps_quality():
    src = (va.__file__ and open(va.__file__, encoding="utf-8").read())
    # 중간 산출물(서브클립·켄번스·컷어웨이 비트)은 mid 프리셋
    assert src.count("_mid_preset()") >= 3, "중간 패스가 여전히 최종 품질로 인코딩된다"
    # 자막 번인 등 최종 패스는 기존 품질 유지 — 여기까지 바꾸면 화질이 떨어진다
    assert '"-preset", _preset()' in src, "최종 패스가 mid로 바뀌었다(화질 저하)"


def test_defaults_are_fast_but_high_quality():
    assert va._MID_PRESET == "veryfast"
    assert int(va._MID_CRF) <= 16, "중간 CRF가 최종(16)보다 나쁘면 세대손실이 보인다"


def test_preview_mode_overrides_win(monkeypatch):
    """미리보기(저품질 빠른 모드)가 걸려 있으면 중간 패스도 그걸 따라야 한다 —
    미리보기인데 중간만 veryfast/CRF14로 더 좋게 뽑으면 오히려 느려진다."""
    monkeypatch.setattr(va._preset_local, "value", "ultrafast", raising=False)
    monkeypatch.setattr(va._preset_local, "crf", "30", raising=False)
    try:
        assert va._mid_preset() == "ultrafast"
        assert va._mid_crf() == "30"
    finally:
        monkeypatch.setattr(va._preset_local, "value", None, raising=False)
        monkeypatch.setattr(va._preset_local, "crf", None, raising=False)
