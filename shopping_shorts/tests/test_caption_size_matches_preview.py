"""꾸미기 자막 크기: 미리보기 = 실제 렌더 (2026-07-30 사장님 제보).

제보: "썸네일에서 자막 비율과 실제 렌더에서 자막 비율이 더 작게 나온다".

뿌리(git 실측): 2026-07-24 f08c18aec가 출력을 720x1280 → 1080x1920으로 올리면서
**내부 기본값은 전부 ×1.5** 했는데(_CAP_FONTSIZE 52→78, size 64→96, outline_w 6→9,
shadow_d 3→5, box_pad 16→24, _BAR_H 300→450) **UI에서 온 값은 환산하지 않았다**.
프론트(produce.html)는 여전히 VIDEO_W=720 기준으로 미리보기를 그리므로, 화면 대비
자막이 정확히 720/1080 = 67% 크기로 렌더됐다.

여기서 못 박는 것:
1. UI가 준 size는 _OUT_W/720배로 환산되어 fontsize에 들어간다(= 미리보기와 같은 비율).
2. 기본값은 환산되지 않는다(이미 1080 기준 — 같이 곱하면 이중 확대).
3. 테두리·그림자·박스여백도 같은 비율로 커진다(폰트만 키우면 상대적으로 얇아진다).
4. 프론트 VIDEO_W와 서버 _UI_REF_W가 같은 값이다(둘이 갈라지면 증상이 재발한다).
"""
import pathlib
import re

import pytest

from shopping_shorts import video_assemble as va

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
RATIO = va._OUT_W / va._UI_REF_W       # 현재 1080/720 = 1.5


def test_ui_value_is_scaled_to_output_resolution():
    """사장님이 슬라이더로 정한 값 → 출력 해상도 비율로 환산."""
    assert va._ui_px(60, 96) == round(60 * RATIO)
    assert va._ui_px(100, 96) == round(100 * RATIO)


def test_default_is_not_scaled():
    """기본값은 1080p 업그레이드 때 이미 ×1.5 됐다 — 또 곱하면 이중 확대."""
    assert va._ui_px(None, 96) == 96
    assert va._ui_px(0, 96) == 96          # 종전 `or` 의미 유지
    assert va._ui_px("", 96) == 96
    assert va._ui_px("헛값", 96) == 96      # 형변환 실패는 조용히 기본값


def test_zero_ok_keeps_explicit_zero():
    """box_pad=0은 '여백 없음'이라는 뜻 — 기본값으로 되돌리면 안 된다."""
    assert va._ui_px(0, 24, zero_ok=True) == 0
    assert va._ui_px(None, 24, zero_ok=True) == 24


def _fontsizes(parts):
    return [int(m.group(1)) for p in parts for m in [re.search(r"fontsize=(\d+)", p)] if m]


def test_caption_fontsize_uses_scaled_ui_size(tmp_path):
    """자막 본문: style.size가 그대로가 아니라 환산되어 나간다(이 테스트가 뿌리 회귀 방지)."""
    parts = va._segmented_drawtext("안녕하세요", {"size": 60}, tmp_path, "k", 50.0, 50.0)
    sizes = _fontsizes(parts)
    assert sizes, "drawtext가 안 만들어졌다"
    assert sizes[0] == round(60 * RATIO)
    assert sizes[0] != 60, "환산이 빠지면 미리보기보다 작게 렌더된다(제보된 증상)"


def test_outline_shadow_box_scale_together(tmp_path):
    """폰트만 키우면 테두리가 상대적으로 얇아진다 — 같이 커져야 미리보기와 같은 룩."""
    style = {"size": 60, "outline": True, "outline_w": 6,
             "box": True, "box_pad": 16, "box_opacity": 80}
    joined = " ".join(va._segmented_drawtext("안녕", style, tmp_path, "k2", 50.0, 50.0))
    assert f"borderw={round(6 * RATIO)}" in joined
    assert f"boxborderw={round(16 * RATIO)}" in joined


def test_fixed_drawtext_headcopy_also_scaled(tmp_path):
    """헤드카피·추가텍스트·워터마크도 같은 UI 기준을 쓴다."""
    out = va._fixed_drawtext({"text": "헤드카피", "size": 80, "outline": True, "outline_w": 6},
                             tmp_path, "hc")
    assert f"fontsize={round(80 * RATIO)}" in out
    assert f"borderw={round(6 * RATIO)}" in out


def test_frontend_and_backend_reference_width_agree():
    """★프론트 VIDEO_W와 서버 _UI_REF_W가 갈라지면 증상이 그대로 재발한다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    m = re.search(r"const\s+PREVIEW_W\s*=\s*\d+\s*,\s*VIDEO_W\s*=\s*(\d+)", src)
    assert m, "produce.html에서 VIDEO_W를 못 찾았다(리팩터링 시 이 테스트도 갱신할 것)"
    assert int(m.group(1)) == va._UI_REF_W, (
        f"프론트 VIDEO_W={m.group(1)} != 서버 _UI_REF_W={va._UI_REF_W} — "
        "미리보기와 렌더 자막 크기가 다시 어긋난다")


def test_thumbnail_card_uses_same_reference():
    """썸네일 카드(92/720 하드코딩)도 같은 기준이어야 한다 — 사장님이 본 그 '썸네일'."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    assert f"/{va._UI_REF_W}" in src, "썸네일 카드 스케일이 UI 기준폭과 다르다"
