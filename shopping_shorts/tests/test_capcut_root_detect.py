r"""캡컷 폴더의 절대경로는 **가정하지 않고 알아낸다** (2026-09-02).

사장님: "다들 캡컷 내보내기가 계속 안 된다는데" / "캡컷 가면 폴더만 있고 빈 통이래"

실측으로 갈렸다 — 서버 로그의 capcut_asset 요청은 **전부 200 OK**였다. 재료는 다 갔다.
문제는 draft가 미디어를 참조하는 **절대경로**였다:

    C:/capcutproject/CapCut Drafts/<프로젝트>/src_cc0.mp4

이 경로를 종전엔 표준값(CAPCUT_DEFAULT_PATH)으로 **가정**했다. 고객이 폴더 선택창에서
캡컷 기본 폴더(AppData\Local\CapCut\User Data\Projects\com.lveditor.draft)를 고르면
파일은 거기 정상적으로 쓰이지만 draft는 C:/capcutproject/...를 가리켜 캡컷이 미디어를
하나도 못 찾는다 → 프로젝트 폴더는 보이는데 내용이 빈 통.

해결: 캡컷이 만든 프로젝트마다 draft_meta_info.json에 draft_root_path(그 드래프트 폴더의
절대경로)가 들어 있다. 고른 폴더 안을 훑어 그 값을 읽으면 추측 없이 실제 경로를 안다.
실측(2026-09-02, 로컬 두 폴더):
  C:\capcutproject\CapCut Drafts                       → 8:2 다수결로 정확히 탐지
  ...\CapCut\User Data\Projects\com.lveditor.draft   → 9/9 정확히 탐지
"""
import pathlib
import re

_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _src():
    return _HTML.read_text(encoding="utf-8")


def test_탐지함수가_있다():
    src = _src()
    assert "async function _ccDetectRoot(" in src, "폴더 실경로 탐지 함수가 사라졌다"
    assert "draft_meta_info.json" in src, "draft_meta_info.json을 읽지 않는다"
    assert "draft_root_path" in src, "draft_root_path를 읽지 않는다"


def test_보내기가_탐지결과를_먼저_쓴다():
    """표준 경로는 **탐지 실패 시의 폴백**이어야 한다 — 먼저 쓰면 예전 버그 그대로다."""
    src = _src()
    i = src.index("async function sendToCapCut(")
    body = src[i:i + 6000]
    det = body.find("_ccDetectRoot(")
    fallback = body.find("CAPCUT_DEFAULT_PATH")
    assert det > 0, "sendToCapCut이 _ccDetectRoot를 부르지 않는다"
    assert fallback > det, (
        "표준 경로(CAPCUT_DEFAULT_PATH)를 탐지보다 먼저 쓴다 — 고객이 다른 폴더를 고르면\n"
        "draft가 엉뚱한 경로를 가리켜 '폴더만 있고 빈 통'이 재발한다"
    )


def test_탐지_실패를_조용히_넘기지_않는다():
    src = _src()
    assert "캡컷 프로젝트가 하나도 없습니다" in src,         "탐지 실패를 사용자에게 알리지 않는다 — 조용히 표준 경로로 넘어가면 원인이 안 보인다"
    # 자동설정 .bat은 폴더를 먼저 만들고 캡컷 설정을 나중에 바꾼다. 캡컷이 켜져 있거나
    # 캡컷에 로그인이 안 돼 있으면 **폴더만 만들고 중단**한다 — 빈 폴더가 남고 캡컷은
    # 원래 폴더를 계속 본다. "폴더만 있고 빈 통"의 가장 유력한 경로다.
    assert "캡컷을 완전히 끄고" in src,         "자동설정을 캡컷 끈 채 다시 돌리라는 안내가 없다 — 고객이 무엇을 해야 할지 모른다"
