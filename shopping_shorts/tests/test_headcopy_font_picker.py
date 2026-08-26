"""⚡빠른 조절의 폰트 고르기 — '진짜 그 글씨체로' 보이는가를 소스로 잠근다.

2026-08-19 사장님: "해드카피도 썸네일쪽처럼 이쁜폰트로 기본구성 세팅해놔줘".
밋밋한 <select>는 22종이 전부 같은 고딕으로 보여 고를 수가 없었다 —
각 줄을 그 폰트로 그리는 메뉴로 바꿨다.

★여기서 잠그는 계약 3개(하나라도 깨지면 사장님이 다시 "안 이쁘다"를 겪는다):
  1. 메뉴 항목이 자기 폰트(f.css)로 그려진다
  2. 값의 주인은 hcFont 하나 — 빠른조절은 hcQuick()으로만 쓴다(0순위-B)
  3. 안 고르고 빠져나가면 원래 폰트로 되돌아간다(QFONT_BEFORE)
"""
import pathlib
import re

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_quick_font_picker_exists():
    """밋밋한 드롭다운 대신 폰트 미리보기 버튼·메뉴가 있다."""
    assert 'id="hcFontQBtn"' in HTML
    assert 'id="hcFontQMenu"' in HTML


def test_hidden_select_kept_for_wiring():
    """숨은 hcFontQ는 남긴다 — hcQuickSync가 되비추는 자리이고 기존 배선이 이 id를 본다."""
    assert 'id="hcFontQ"' in HTML
    m = re.search(r'<select id="hcFontQ"[^>]*>', HTML)
    assert m and "display:none" in m.group(0), "hcFontQ는 숨겨진 채 남아 있어야 한다"


def test_menu_items_render_in_their_own_font():
    """★각 줄이 자기 폰트로 그려져야 '이쁜 폰트'가 보인다.

    이 줄이 사라지면 22종이 전부 같은 고딕으로 보이는 옛 상태로 되돌아간다.
    """
    body = HTML[HTML.index("function buildQFontMenu"):]
    body = body[:body.index("function syncQFontBtn")]
    assert "qFontItem" in body
    assert "font-family:'${f.css}'" in body, "항목을 f.css 폰트로 그려야 한다"


def test_quick_font_writes_through_hcQuick_only():
    """★값의 주인은 hcFont 하나(0순위-B). 빠른조절이 STATE를 직접 만지면 두 벌이 된다."""
    seg = HTML[HTML.index("var QFONT_BEFORE"):HTML.index("function hcQuickSync")]
    assert "hcQuick('hcFont'" in seg
    assert "STATE.headcopy.font=" not in seg.replace(" ", ""), "빠른조절이 STATE를 직접 쓰면 안 된다"


def test_cancel_restores_previous_font():
    """★안 고르고 나가면 원래대로. 되돌릴 값은 '열 때' 적어둬야 한다 —
    hover가 이미 값을 덮어써서 현재값을 읽으면 되돌리기가 아니라 그대로 두기가 된다."""
    seg = HTML[HTML.index("var QFONT_BEFORE"):HTML.index("function hcQuickSync")]
    # 메뉴를 '열 때' 원본을 적어둔다
    assert "QFONT_BEFORE=(STATE.headcopy&&STATE.headcopy.font)||HC_FONT_COMMITTED" in seg.replace(" ", "")
    # 나갈 때 그 값으로 되돌린다
    assert "if(QFONT_BEFORE) hcQuick('hcFont', QFONT_BEFORE)" in seg, "mouseleave가 원본으로 되돌려야 한다"


def test_pick_survives_mouseleave():
    """고른 뒤에는 되돌아가면 안 된다 — pickQFont가 기준값을 새로 세운다."""
    seg = HTML[HTML.index("function pickQFont"):]
    seg = seg[:seg.index("document.addEventListener")]
    assert "QFONT_BEFORE=file" in seg, "고르면 그게 새 기준이 돼야 mouseleave가 안 되돌린다"


# ── 6단계 UI 확대(2026-08-19 "ui크기도 더 크게 화면채우고 글자도 버튼들 다 크게") ──
def test_step6_enlarge_block_is_scoped():
    """확대는 6단계(data-step=3) 안으로만. 다른 단계로 새면 회귀가 된다."""
    assert '.panel[data-step="3"] #decoTabs .tab' in HTML
    # 확대 규칙이 전부 그 패널 스코프 안에 있는지
    for sel in ('#hcText{font-size:18px', 'summary{font-size:16px'):
        idx = HTML.find(sel)
        assert idx > 0, f"{sel} 규칙이 없다"
        assert '.panel[data-step="3"]' in HTML[max(0, idx - 120):idx]


def test_preview_width_has_single_source():
    """★--pvw의 정의처는 .decoMirror 한 곳. 인라인으로 되돌리면 화면별 확대가 죽는다
    (인라인 커스텀 프로퍼티는 스타일시트가 !important로도 못 이긴다)."""
    assert ".decoMirror{--pvw:" in HTML.replace(" ", "")
    m = re.search(r'<div class="previewSlot decoMirror"[^>]*>', HTML)
    assert m, "미리보기 슬롯에 decoMirror 클래스가 있어야 한다"
    assert "--pvw:" not in m.group(0), "--pvw를 인라인으로 되돌리면 안 된다(CSS가 못 이긴다)"
