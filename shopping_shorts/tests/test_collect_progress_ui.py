"""수집 진행률이 화면에 붙어 있는지(정적 검사).

★2026-07-27 실사고: 50분간 화면에 아무 변화가 없어 사장님이 취소했다.
서버가 진행률을 보내도 화면이 안 읽으면 같은 일이 반복된다.
"""
import pathlib

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def test_ui_reads_collecting_phase():
    assert "collecting" in HTML, "진행률 phase를 화면이 안 읽는다"


def test_ui_shows_done_over_total():
    # 브리프 원안은 "d.total"을 찾았지만 실제 응답 접근 경로는 d.result.total이라
    # "result.total"로 맞췄다(검증 의도=진행 카운트 렌더링은 그대로 유지).
    assert "items_so_far" in HTML and "result.total" in HTML, \
        "진행 카운트(37/200 · N건)를 화면에 안 그린다"


def test_progress_does_not_overwrite_collect_progress_container():
    """★2026-07-28 회귀: #collectProgress는 cpSpin/cpMsg/cpSub/cpRetry 자식 4개를 가진
    컨테이너다. textContent/innerHTML을 여기 직접 대입하면 자식이 전부 삭제돼
    이후 _cpDone/_cpFail이 e.spin.style.display에서 null 참조로 죽는다.
    진행률은 반드시 자식(cpMsg 등)에 써야 한다.
    """
    import re
    for bad in (
        r"getElementById\(['\"]collectProgress['\"]\)\s*\.\s*textContent\s*=",
        r"getElementById\(['\"]collectProgress['\"]\)\s*\.\s*innerHTML\s*=",
    ):
        assert not re.search(bad, HTML), f"collectProgress 컨테이너에 직접 대입: {bad}"
