"""[완성본 만들기]가 **밀린 편집을 먼저 저장한 뒤** 렌더하는지.

2026-09-02 사장님 제보:
  "구간편집 체크 해제 후, 각 섹션마다 1초 단위로 컷편집을 조정한 뒤에
   완성본 미리보기를 클릭해서 확인하면 해당 컷 편집이 적용되어 있지 않음."

라이브 실측으로 순서가 **정확히 거꾸로**인 것을 확인했다:
    0ms  렌더시작(POST /api/produce/mix/preview)
  901ms  편집저장(POST /api/mix/scene_lab/<job>/apply)
autoApply가 1.2초 디바운스라, 컷을 조정하고 그 안에 탭을 누르면
서버는 **옛 편성으로** 렌더를 시작한다. 데이터·배선은 멀쩡했고 순서만 틀렸다.

고침: _askRender가 flushApply()를 await 한 뒤 부모의 startPreview()를 부른다.
      디바운스는 그대로 둔다(연속 편집마다 POST가 나가면 안 된다) — "지금 비우기"만 추가.
"""
import pathlib
import re

SCENE_LAB = pathlib.Path(__file__).resolve().parents[1] / "static" / "scene_lab.html"


def _src() -> str:
    return SCENE_LAB.read_text(encoding="utf-8")


def _body(src: str, head: str) -> str:
    i = src.index(head)
    return src[i:src.index("\n}", i) + 2]


def test_ask_render_flushes_before_rendering():
    """렌더 요청 전에 저장을 기다려야 한다 — 순서가 곧 이 버그의 전부다."""
    src = _src()
    body = _body(src, "async function _askRender()")
    assert "flushApply" in body, (
        "렌더 전에 밀린 편집을 안 비운다 — 컷 편집이 빠진 채로 만들어진다")
    fi = body.index("flushApply")
    si = body.index("startPreview")
    assert fi < si, f"flushApply가 startPreview보다 뒤에 있다(순서가 거꾸로): {body[:200]!r}"
    assert re.search(r"await\s+flushApply\(\)", body), (
        "await 없이 부르면 안 기다린다 — 지금 버그와 똑같아진다")


def test_ask_render_is_async():
    """await를 쓰려면 async여야 한다(아니면 문법 오류로 탭이 통째로 죽는다)."""
    assert "async function _askRender()" in _src()


def test_flush_waits_for_inflight_save():
    """보내는 중이면 applyServer가 즉시 return하므로, 재전송까지 기다려야 한다."""
    body = _body(_src(), "async function flushApply()")
    assert "_autoApplyBusy" in body and "_autoApplyAgain" in body, (
        "전송 중·재전송 예약 상태를 안 본다 — 마지막 편집이 빠질 수 있다")
    assert "clearTimeout" in body, "예약된 디바운스를 안 끄면 저장이 두 번 나간다"


def test_debounce_kept_for_normal_edits():
    """평소 편집은 그대로 디바운스 — 슬라이더마다 POST가 나가면 안 된다(저장 폭주 방지)."""
    body = _body(_src(), "function autoApply()")
    assert "1200" in body and "clearTimeout" in body, "디바운스가 사라졌다"


def test_render_failure_does_not_block():
    """저장이 실패해도 렌더는 계속돼야 한다 — 막으면 아무것도 못 만든다."""
    body = _body(_src(), "async function _askRender()")
    assert "catch" in body, "flushApply 실패가 렌더를 통째로 막는다"
