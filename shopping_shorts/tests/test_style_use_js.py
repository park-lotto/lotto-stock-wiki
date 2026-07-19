from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


<<<<<<< HEAD
def test_style_use_map_and_default_badge():
    # 용도 태그 맵 존재 + 기본/대표 스타일이 매핑돼 있다
    assert "const STYLE_USE=" in HTML
    assert "'임팩트 옐로':'레시피·강한 훅'" in HTML
    # 카드에 ⭐기본 배지와 용도 라벨을 그린다
    assert "⭐기본" in HTML
    assert "const use = STYLE_USE[p.name]" in HTML
    assert "p.name===DEFAULT_STYLE_NAME" in HTML
=======
def test_only_clean_reference_presets():
    # 레퍼런스(HOMEDIRECTOR)와 동일한 깔끔한 흰색 프리셋 3개만 — 크기만 다름, 위치는 동일
    assert "name:'심플 화이트'" in HTML
    assert "name:'심플 화이트(크게)'" in HTML
    assert "name:'심플 화이트(작게)'" in HTML
    assert "const FEATURED = ['심플 화이트','심플 화이트(크게)','심플 화이트(작게)']" in HTML
    assert "const DEFAULT_STYLE_NAME='심플 화이트'" in HTML
    # 요란한 옛 프리셋 + 위치가 다른 하단 변형은 전부 제거됨
    for gone in ("name:'임팩트 옐로'", "name:'네온 글로우", "name:'화이트+민트 투톤'",
                 "name:'심플 화이트(하단)'", "name:'레드 강조'", "name:'옐로 2톤"):
        assert gone not in HTML, f"제거됐어야 할 프리셋 잔존: {gone}"


def test_all_captions_same_position_center_top():
    # 3개 자막 모두 y37(중상단) — 사장님 지적: 자막 위치는 기본과 동일해야 한다
    assert HTML.count("',size:50,y:37,outline:false,shadow:true") == 1  # 보통
    assert HTML.count("',size:58,y:37,outline:false,shadow:true") == 1  # 크게
    assert HTML.count("',size:44,y:37,outline:false,shadow:true") == 1  # 작게
    # y37 이외의 자막 위치(하단 등)는 없다
    assert ",y:82," not in HTML
    assert ",y:84," not in HTML


def test_captions_use_soft_shadow_not_thick_outline():
    # 레퍼런스처럼 은은한 그림자(shadow) — 두꺼운 검은 테두리(outline) 아님
    assert "outline:false,shadow:true" in HTML
    assert "let CAP_SHADOW=false" in HTML
    assert "CAP_SHADOW=!!c.shadow" in HTML
    assert "cs.shadow ?" in HTML  # 프리뷰가 부드러운 그림자를 그린다


def test_default_badge_and_use_map():
    assert "⭐기본" in HTML
    assert "const use = STYLE_USE[p.name]" in HTML
    assert "p.name===DEFAULT_STYLE_NAME" in HTML
    assert "'심플 화이트':'자막 중상단·깔끔'" in HTML
>>>>>>> 76d5b4fe62827fc23ff6b65ecbb40b44d18340dd


def test_no_fabricated_stats_on_cards():
    # 허위 지표(조회/참여 숫자)를 카드에 박지 않는다 — 정직성 잠금
    assert "조회 21만" not in HTML
    assert "참여 5.6%" not in HTML
<<<<<<< HEAD
=======


def test_my_preset_library_surfaced():
    # 내 프리셋 라이브러리가 '직접 다듬기' 접힘 밖으로 나와 항상 보인다(60대 접근성)
    assert "⭐ 내 프리셋 <span" in HTML          # 갤러리 밑 항상 노출되는 라벨
    assert "💾 지금 스타일 저장" in HTML
    assert 'onclick="saveMyPreset()"' in HTML
    assert 'onclick="applyMyPreset(' in HTML     # 클릭 즉시 적용
    # 접혀있던 옛 블록 문구는 제거됨(중복 방지)
    assert "⭐ 내 프리셋 저장 · 불러오기" not in HTML
>>>>>>> 76d5b4fe62827fc23ff6b65ecbb40b44d18340dd
