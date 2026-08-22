"""확정 영상은 장면편집 안 재생 자리에서 본다(2026-08-22 사장님).

"왜 따로 또 자리를 차지하냐고. 저걸 누르면 미리보기 재생했던 곳에서 하라니까"

부모(produce.html) 좌측 레일에 새 칸을 여는 대신, iframe(scene_lab) 안
[가조립 | 확정본] 탭으로 같은 자리를 나눠 쓴다. 부모→iframe은 contentWindow
직접 호출(postMessage는 2026-08-15에 조용히 실패해 버린 경로다).
"""
import pathlib

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"


def _code(name):
    src = (_STATIC / name).read_text(encoding="utf-8")
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith("//"))


def test_확정본_패널이_있다():
    lab = _code("scene_lab.html")
    assert 'id="confirmPane"' in lab, "확정본 패널이 없다"
    assert 'id="pvTabs"' in lab, "탭이 없다"


def test_부모가_부를_함수가_있다():
    lab = _code("scene_lab.html")
    for fn in ("showConfirmLoading", "showConfirmVideo", "clearConfirm"):
        assert f"function {fn}(" in lab, f"{fn}이 없다"
        assert f"window.{fn}" in lab, f"{fn}이 window에 안 붙었다(부모가 못 부른다)"


def test_부모가_iframe으로_넘긴다():
    """부모는 자기 칸에 그리지 말고 iframe 함수를 불러야 한다."""
    pro = _code("produce.html")
    body = pro.split("function _renderPreviewVideo(")[1].split("\nfunction ")[0]
    assert "_labCall(" in body, "_renderPreviewVideo가 iframe으로 안 넘긴다"


def test_통로는_contentWindow다():
    """postMessage는 2026-08-15에 조용히 실패해 버린 경로 — 되살리지 마라."""
    pro = _code("produce.html")
    body = pro.split("function _labCall(")[1].split("\nfunction ")[0]
    assert "contentWindow" in body, "_labCall이 contentWindow를 안 쓴다"
    assert "postMessage" not in body, "postMessage를 쓰면 안 된다"


def test_좌측레일은_감춘다():
    """레일이 살아 있으면 자리가 또 둘이 된다 — 사장님 지적의 원인."""
    pro = _code("produce.html")
    assert "_RAIL_OFF" in pro, "레일 감춤 스위치가 없다"
