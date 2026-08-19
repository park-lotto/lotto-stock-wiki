# -*- coding: utf-8 -*-
"""미리보기(9:16) 크기가 '고치면 자꾸 틀어지고 커지던' 것 (2026-08-20 사장님 제보).

★근본 원인(코드 실측) — 같은 미리보기의 크기를 **여러 곳이 각자** 정하고 있었다
(CLAUDE.md 0순위-B). 실측 9곳:
    produce.html : ①레일 340px ②vidbox aspect+max-height:520px 클램프 ③#player video
                   ④렌더 결과 video max-height:520px ⑤자리표시 div ⑥로더 frame
    scene_lab.html: ⑦#playerhost 440px ⑧#vidbox ⑨#player video
  게다가 재생 위치 자체가 상태에 따라 바뀐다(_outerPlayer: 레일이 열려 있으면 제작소
  340px 레일에서, 닫혀 있으면 장면편집 안 440px에서) → 작업할 때마다 미리보기가
  다른 크기(340 vs 440)·다른 비율(max-height 클램프 → 좌우 레터박스)로 나왔다.

계약: 숫자의 정의처는 scene_play.js PV_W/PV_AR **한 곳**(두 화면이 다 읽는 파일).
      CSS는 var(--shorts-pv-w / --shorts-pv-ar)로 받고, var() 폴백은 그 값과 같아야
      한다(이 테스트가 짝을 강제한다). 크기를 바꾸려면 PV_W/PV_AR 두 줄만 고친다.
"""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"
PLAY = (STATIC / "scene_play.js").read_text(encoding="utf-8")
PROD = (STATIC / "produce.html").read_text(encoding="utf-8")
LAB = (STATIC / "scene_lab.html").read_text(encoding="utf-8")


def _const(name):
    m = re.search(r"const\s+" + name + r"\s*=\s*'([^']+)'", PLAY)
    assert m, f"scene_play.js에 {name} 상수가 없다 — 크기 정의처 실종"
    return m.group(1)


def test_정의처는_scene_play_한_곳이다():
    w, ar = _const("PV_W"), _const("PV_AR")
    assert re.search(r"setProperty\('--shorts-pv-w',\s*PV_W\)", PLAY), "--shorts-pv-w 주입이 없다"
    assert re.search(r"setProperty\('--shorts-pv-ar',\s*PV_AR\)", PLAY), "--shorts-pv-ar 주입이 없다"
    # 정의는 한 번만 — 두 번 적히면 그게 바로 이 사고다.
    assert PLAY.count("const PV_W") == 1 and PLAY.count("const PV_AR") == 1


def test_var_폴백은_정의값과_같다():
    """폴백이 다르면 '스크립트 로드 전/실패 시'와 이후가 다른 크기가 된다."""
    w, ar = _const("PV_W"), _const("PV_AR")
    for src, name in ((PROD, "produce.html"), (LAB, "scene_lab.html")):
        for fb in re.findall(r"var\(--shorts-pv-w\s*,\s*([^)]+)\)", src):
            assert fb.strip() == w, f"{name}: --shorts-pv-w 폴백 {fb} ≠ PV_W {w}"
        for fb in re.findall(r"var\(--shorts-pv-ar\s*,\s*([^)]+)\)", src):
            assert fb.strip() == ar, f"{name}: --shorts-pv-ar 폴백 {fb} ≠ PV_AR {ar}"


def test_레일과_playerhost가_같은_변수를_쓴다():
    """두 재생 위치가 각자 숫자를 적으면(340 vs 440) 상태 따라 크기가 널뛴다 — 그 사고다."""
    m = re.search(r'<div id="mixPreviewRail"[^>]*>', PROD)
    assert m, "mixPreviewRail을 못 찾았다"
    tag = m.group(0)
    assert "--shorts-pv-w" in tag, "레일 폭이 변수를 안 쓴다"
    assert "340px" not in tag, "레일에 340px 리터럴이 되살아났다"
    m = re.search(r"#playerhost\{[^}]*\}", LAB, re.S)
    assert m, "#playerhost를 못 찾았다"
    body = m.group(0)
    assert "--shorts-pv-w" in body, "#playerhost 폭이 변수를 안 쓴다"
    assert not re.search(r"flex:0 0 \d", body), "#playerhost에 폭 리터럴이 되살아났다"


def test_vidbox에_max_height_클램프가_없다():
    """max-height가 aspect-ratio를 누르면 비율이 깨져 '틀어져' 보인다(실측: 340×520)."""
    m = re.search(r'<div id="vidbox"[^>]*>', PROD)
    assert m, "produce vidbox를 못 찾았다"
    tag = m.group(0)
    assert "max-height" not in tag, f"vidbox에 max-height 클램프가 되살아났다: {tag}"
    assert "--shorts-pv-ar" in tag, "vidbox 비율이 변수를 안 쓴다"


def test_미리보기_비율_리터럴이_되살아나지_않았다():
    """레일 안(#mixPreview 계열)과 재생기 CSS에서 9/16을 손으로 적으면 또 갈라진다."""
    # produce: #player video CSS · 렌더결과 video · 자리표시 · 로더 frame
    for pat, name in (
        (r"#player video\{[^}]*\}", "produce #player video"),
        (r"_renderPreviewVideo[\s\S]{0,400}?<video[^>]*>", "렌더 결과 video"),
        (r"pvLoadFrame[^>]*>", "로더 frame"),
    ):
        m = re.search(pat, PROD, re.S)
        assert m, f"{name}을 못 찾았다"
        seg = m.group(0)
        assert "--shorts-pv-ar" in seg, f"{name}이 비율 변수를 안 쓴다"
        assert not re.search(r"aspect-ratio:\s*9/16\s*[;\"']", seg), f"{name}에 9/16 리터럴"
        assert "max-height:520px" not in seg, f"{name}에 520px 클램프가 되살아났다"
    # scene_lab: #vidbox · #player video
    for pat, name in (
        (r"#player #vidbox\{[^}]*\}", "scene_lab #vidbox"),
        (r"#player video\{[^}]*\}", "scene_lab #player video"),
    ):
        m = re.search(pat, LAB, re.S)
        assert m, f"{name}을 못 찾았다"
        seg = m.group(0)
        assert "--shorts-pv-ar" in seg, f"{name}이 비율 변수를 안 쓴다"
        assert not re.search(r"aspect-ratio:\s*9/16\s*[;}\"']", seg), f"{name}에 9/16 리터럴"
