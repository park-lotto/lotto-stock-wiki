"""파형·무음자르기는 **관리자에게만** 보인다 (2026-09-22 사장님 "관리자에서만 볼수있게").

★왜 테스트로 박나: 고객 화면에 실수로 열리면 사장님이 승인하지 않은 기능이 라이브에
노출된다(0순위-A1c). 화면 요소는 눈에 안 띄게 새는 법이라 사람 눈으로는 못 지킨다.

★왜 `if(window.IS_ADMIN)`로 그리지 않고 CSS로 가리나:
  IS_ADMIN은 `/api/me` 응답 뒤에 켜지는데 renderTtsBeats는 그보다 먼저 돌 수 있다.
  그리는 시점에 판정하면 **관리자에게도 안 보인다**. 요소는 항상 만들고 body 표식으로
  보이기만 제어하면 응답이 언제 오든 맞는다(discover.html이 쓰는 방식과 같다).
"""
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "static" / "produce.html").read_text(encoding="utf-8")


def test_waveform_hidden_by_default():
    """기본은 숨김 — body에 표식이 붙어야만 열린다."""
    assert ".wfAdmin{display:none}" in HTML
    assert "body.is-admin .wfAdmin{display:block}" in HTML
    assert "body.is-admin .wfAdmin.row{display:flex}" in HTML


def test_waveform_row_carries_admin_class():
    """문장별 파형 띠와 상단 일괄 버튼 줄 둘 다 .wfAdmin을 달고 있어야 한다."""
    assert 'class="wfWrap wfAdmin"' in HTML, "문장별 파형에 .wfAdmin이 없다 — 고객에게 보인다"
    assert 'class="wfAdmin row"' in HTML, "상단 일괄 버튼 줄에 .wfAdmin이 없다"


def test_body_gets_admin_mark_on_api_me():
    """/api/me가 cid 0이면 body에 is-admin을 붙인다(이게 없으면 관리자도 못 본다)."""
    assert "document.body.classList.add('is-admin')" in HTML


def test_customer_keeps_old_decorative_wave():
    """고객 줄에서 파형이 통째로 사라지면 안 된다 — 옛 장식 파형이 남아야 한다."""
    assert 'class="wfDeco"' in HTML
    assert "body.is-admin .wfDeco{display:none}" in HTML, "관리자 화면에서 파형 2개가 겹친다"


def test_waveform_not_gated_at_draw_time():
    """★그리는 시점에 IS_ADMIN을 보면 안 된다(타이밍에 따라 관리자도 못 본다).

    _wfHTML/_wfInit/_wfLoad 안에 IS_ADMIN 분기가 들어오면 이 테스트가 잡는다."""
    start = HTML.index("// ─── 실제 파형 + 무음 자르기")
    end = HTML.index("// ─── WAVEFORM-END")
    block = HTML[start:end]
    assert "IS_ADMIN" not in block, \
        "파형 블록이 그릴 때 IS_ADMIN을 본다 — CSS(.wfAdmin)로만 가려야 한다"
