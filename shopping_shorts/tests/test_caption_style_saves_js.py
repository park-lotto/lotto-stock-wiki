"""6단계 자막 다듬기가 **저장까지** 되는지 — 미리보기만 바뀌면 안 된다.

2026-09-02 라이브 실측(사장님 지적 유형: "바꾼 게 렌더에 반영 안 된다"):
  6단계에서 자막 색을 #ff00cc로 바꾸면 미리보기는 즉시 마젠타가 되는데,
  새로고침하면 #ffffff로 되돌아갔다(서버 caption_style도 흰색).
  자막 컨트롤 11개가 전부 oninput="updateCaption()"만 불렀고,
  updateCaption은 STATE만 채우고 **saveHeadcopy를 안 불렀다**.
  (템플릿·프레임·모션팩 경로는 18곳에서 saveHeadcopy를 부른다 = 같은 화면에서
   어떤 조작은 저장되고 어떤 조작은 안 되던 상태)

이 테스트가 지키는 것 둘:
  ① 사람이 만지면 저장된다
  ② 복원·초기 렌더에서는 저장하지 않는다 — 그때 DOM이 기본값이면 저장된 스타일을
     덮어쓴다(이 파일이 이미 겪은 사고: "색이 #ffe100→#ff8800으로 죽었다")
"""
import pathlib
import re

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"

# 라이브에서 실제로 안 저장되던 컨트롤들
_CAP_INPUTS = ["capFont", "capColor", "capSize", "capY", "capOutline", "capOutColor",
               "capOutW", "capBox", "capBoxColor", "capBoxPad", "capBoxOpacity"]


def _src() -> str:
    return PRODUCE_HTML.read_text(encoding="utf-8")


def test_every_caption_control_goes_through_touched():
    """자막 컨트롤이 하나라도 updateCaption() 직행이면 그 항목만 조용히 안 저장된다."""
    src = _src()
    missed = []
    for cid in _CAP_INPUTS:
        m = re.search(r'id="%s"[^>]*?(?:oninput|onchange)="([^"]*)"' % cid, src)
        assert m, f"{cid} 컨트롤을 못 찾음(마크업이 바뀌었나)"
        handler = m.group(1)
        if "capTouched()" not in handler:
            missed.append((cid, handler))
    assert not missed, (
        "이 컨트롤들은 저장 경로를 안 탄다 — 화면만 바뀌고 렌더엔 안 반영된다: %r" % missed)


def test_update_caption_saves():
    """updateCaption 끝에 저장 호출이 있어야 한다(값을 만드는 한 곳에서 저장까지)."""
    src = _src()
    body = src[src.index("function updateCaption(){"):src.index("function renderSparkles(")]
    assert "_capSaveSoon()" in body, "updateCaption이 저장을 안 부른다"


def test_restore_path_does_not_overwrite():
    """★복원·초기 렌더에서는 저장하면 안 된다 — 저장된 스타일을 기본값으로 덮는다."""
    src = _src()
    guard = src[src.index("function _capSaveSoon()"):]
    guard = guard[:400]
    assert "_CAP_USER_EDIT" in guard, (
        "사람이 만졌는지 가리는 가드가 없다 — 패널에 들어오기만 해도 저장돼 "
        "저장된 자막 스타일이 기본값으로 덮인다")
    # capTouched만 그 플래그를 세워야 한다(내부 호출은 안 된다)
    assert re.search(r"function capTouched\(\)\{\s*_CAP_USER_EDIT\s*=\s*true", src), \
        "capTouched가 사용자 편집 표시를 안 한다"


def test_debounced_not_per_pixel():
    """슬라이더 드래그로 초당 수십 번 POST가 나가면 안 된다(디바운스)."""
    src = _src()
    body = src[src.index("function _capSaveSoon()"):][:500]
    assert "setTimeout" in body and "clearTimeout" in body, "디바운스가 없다"


# ── 헤드카피도 **똑같은 병**이었다(2026-09-02 실측: #00ff88 → 새로고침 후 #ffffff) ──
_HC_INPUTS = ["hcText", "hcFont", "hcColor", "hcWeight", "hcSize", "hcX", "hcY",
              "hcOutline", "hcOutColor", "hcOutW", "hcBox", "hcBoxColor",
              "hcBoxPad", "hcBoxOpacity"]


def test_every_headcopy_control_goes_through_touched():
    """헤드카피 컨트롤도 저장 경로를 타야 한다 — 자막과 같은 뿌리, 같은 증상."""
    src = _src()
    missed = []
    for cid in _HC_INPUTS:
        m = re.search(r'id="%s"[^>]*?(?:oninput|onchange)="([^"]*)"' % cid, src)
        assert m, f"{cid} 컨트롤을 못 찾음(마크업이 바뀌었나)"
        if "hcTouched()" not in m.group(1):
            missed.append((cid, m.group(1)))
    assert not missed, (
        "이 헤드카피 컨트롤들은 저장 경로를 안 탄다 — 화면만 바뀐다: %r" % missed)


def test_update_hc_saves_and_guards_restore():
    """updateHC도 저장하되, 복원·초기 렌더에서는 저장하지 않아야 한다."""
    src = _src()
    assert "_hcSaveSoon()" in src, "updateHC가 저장을 안 부른다"
    guard = src[src.index("function _hcSaveSoon()"):][:400]
    assert "_HC_USER_EDIT" in guard, (
        "사람이 만졌는지 가리는 가드가 없다 — 패널 진입만으로 저장돼 스타일이 덮인다")
    assert "setTimeout" in guard and "clearTimeout" in guard, "디바운스가 없다"
