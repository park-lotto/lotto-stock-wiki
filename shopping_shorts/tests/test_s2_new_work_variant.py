"""한 재료로 여러 편 — "＋ 이 안으로 새 작업"(2026-08-18 사장님 요청).

사장님: "다채널이라 같은 주제로 두 개 이상 만들려는데, 여기서 복사해서 내 작업에
붙여넣는 것 말고 좋은 방법 없나? 대본 여러 개로 하고 싶어."

종전엔 A안·B안 중 하나만 확정하면 나머지는 버려졌다. 손으로 복사·붙여넣기는
소스·장면이 안 따라와서 반쪽이다 → 작업을 통째로 복제하고 대본만 그 안으로 넣는다.

여기서 못박는 것:
  ① 지금 작업을 **안 건드린다**(확정하지 않는다) — A안은 여기, B안은 새 작업.
  ② work_id를 안 보낸다 = 새 작업. 보내면 지금 작업을 덮어써 A안이 사라진다.
  ③ job_id를 물려주지 않는다 — 믹스 결과는 작업마다 따로다(남의 렌더가 붙으면 안 된다).
  ④ 탭 보기에서도 버튼이 보인다(.s2-dfoot는 탭 모드에서 숨겨진다).
"""
import pathlib
import re

import pytest

PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _fn(src, name):
    i = src.find("function %s(" % name)
    assert i != -1, "%s 를 못 찾음(구조 변경?)" % name
    start = src.index("{", i)
    depth = 0
    for j in range(start, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    pytest.fail("%s 끝을 못 찾음" % name)


def test_새작업으로_보낼때_work_id를_안_보낸다():
    body = _fn(PRODUCE.read_text(encoding="utf-8"), "s2ConfirmToNewWork")
    assert "'/api/produce/works'" in body
    assert "work_id" not in body.split("JSON.stringify(")[1].split(")")[0], \
        "work_id를 실으면 지금 작업을 덮어써 다른 안이 사라진다"


def test_믹스결과를_물려주지_않는다():
    body = _fn(PRODUCE.read_text(encoding="utf-8"), "s2ConfirmToNewWork")
    payload = body.split("JSON.stringify(")[1].split(")")[0]   # 주석이 아니라 실제 전송값만
    assert "job_id" not in payload, "job_id를 물려주면 새 작업에 남의 렌더 결과가 붙는다"


def test_지금_작업을_확정하지_않는다():
    """STATE.script을 건드리면 지금 작업까지 이 안으로 바뀐다 — 그러면 2편이 아니다."""
    body = _fn(PRODUCE.read_text(encoding="utf-8"), "s2ConfirmToNewWork")
    assert "STATE.script=" not in body.replace(" ", "")
    assert "st.script=script" in body.replace(" ", ""), "복제본에만 대본을 넣는다"


def test_지금_작업을_먼저_저장한다():
    """디바운스를 기다리다 페이지가 넘어가면 방금 뽑은 초안이 통째로 날아간다."""
    body = _fn(PRODUCE.read_text(encoding="utf-8"), "s2ConfirmToNewWork")
    assert "_pushWorkNow()" in body


def test_만든_작업으로_이동한다():
    body = _fn(PRODUCE.read_text(encoding="utf-8"), "s2ConfirmToNewWork")
    assert "'/produce?work='" in body


@pytest.mark.parametrize("needle", [
    'id="s2NewWorkBtn"',              # 탭 보기(확정 바)에도 있다
    "s2ConfirmToNewWork(${i})",       # 좌우 보기(카드 밑)에도 있다
])
def test_두_보기_모두에_버튼이_있다(needle):
    assert needle in PRODUCE.read_text(encoding="utf-8")


def test_카드밑_버튼은_탭보기에서_숨겨진_채로_둔다():
    """.s2-dfoot{display:none}을 인라인 style로 깨면 탭 보기 레이아웃이 무너진다."""
    src = PRODUCE.read_text(encoding="utf-8")
    m = re.search(r'<div class="s2-dfoot"[^>]*>', src)
    assert m and "display:" not in m.group(0), \
        "s2-dfoot에 인라인 display를 주면 CSS의 탭/좌우 분기가 무력화된다"
