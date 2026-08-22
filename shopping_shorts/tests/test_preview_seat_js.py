"""3단계 미리보기 '자리'는 하나다 — 주인 판정처가 한 곳인지 강제한다(2026-08-21).

사장님 제보: "미리보기 전체재생 다 하고 믹스확정 누르잖아. 그 미리보기 자리에서
믹스확정이 돌아가게 하면 안 되냐."

실측 원인: 자리를 껐다 켜는 판단이 5곳에 흩어져 startPreview 경로만 구멍이 났다
(_sceneLabPrep이 #mixPreview를 display:none으로 꺼두는데 startPreview가 안 되돌림).
0순위-B(같은 판단 두 번 쓰기 금지) 그대로라 판정처를 _pvShow 하나로 모았다.
"""
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _code():
    """주석을 걷어낸 produce.html 본문 — 주석 속 문구에 정규식이 걸리지 않게."""
    src = _HTML.read_text(encoding="utf-8")
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith("//"))


def test_자리_판정처가_하나다():
    code = _code()
    assert "function _pvShow(" in code, "_pvShow 판정처가 없다"


def test_확정_경로가_판정처를_쓴다():
    """startPreview는 자기가 display를 만지지 말고 **자리 여는 함수**를 불러야 한다.

    ★2026-08-22 단언 조정 — 지우지 말고 읽어라.
    원래 이 단언은 `_pvShow('video')` 문자열 하나만 봤다. 그런데 사장님 지시로
    ("왜 따로 또 자리를 차지하냐고. 저걸 누르면 미리보기 재생했던 곳에서 하라니까")
    로더가 갈 자리가 **부모 좌측 레일 → 장면편집(iframe) 안 확정본 탭**으로 옮겨졌다.
    이제 startPreview는 `_labCall('showConfirmLoading', ...)`을 먼저 부르고, 그게
    실패했을 때만 옛 자리로 `_pvShow('fallback')` 한다.

    이 단언이 지키려는 건 함수 이름이 아니라 **"innerHTML을 쓰기 전에 그 자리를
    먼저 연다"**는 규약이다(안 지키면 2026-08-18의 0×0 재발). 그래서 두 경로를
    **모두** 요구한다 — 어느 한쪽만 남아도 FAIL이다:
      · 주 경로  = _labCall('showConfirmLoading' ...)   ← 이게 빠지면 옛 자리로 회귀
      · 폴백 경로 = _pvShow(...)                        ← 이게 빠지면 iframe 없을 때 0×0
    """
    code = _code()
    body = code.split("async function startPreview()")[1].split("\nasync function")[0]
    assert "_labCall('showConfirmLoading'" in body, \
        "startPreview가 로더를 장면편집 안 자리로 안 넘긴다(2026-08-22 사장님 지시)"
    assert "_pvShow(" in body, "startPreview 폴백이 자리를 안 연다(0×0 재발)"


def test_가조립_경로가_판정처를_쓴다():
    code = _code()
    body = code.split("function _sceneLabPrep(")[1].split("\nfunction ")[0]
    assert "_pvShow('play')" in body, "_sceneLabPrep이 _pvShow('play')를 안 부른다"
    assert "style.display" not in body, "_sceneLabPrep이 아직 display를 직접 만진다"


def test_판정처_밖에서_자리를_직접_안만진다():
    """_pvShow 정의 안을 뺀 나머지에서 #mixPreview의 display를 직접 만지면 안 된다."""
    code = _code()
    head, rest = code.split("function _pvShow(", 1)
    outside = head + rest.split("\n}", 1)[1]
    assert "pv.style.display" not in outside, "_pvShow 밖에서 #mixPreview display를 만진다"


def test_기존_가시성_규약도_그대로다():
    """test_preview_visible.js는 파이썬 래퍼가 없어 게이트에서 안 돌았다 — 여기서 돈다."""
    js = _HTML.parent.parent / "tests" / "test_preview_visible.js"
    out = run_js(js.read_text(encoding="utf-8"))
    assert "FAIL 0" in out, out
