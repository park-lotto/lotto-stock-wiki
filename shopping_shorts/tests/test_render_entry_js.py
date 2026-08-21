"""렌더 입구는 '자막+음성 완성본' 탭 하나다(2026-08-22 사장님).

"이거 2개는 삭제하고 자막+음성 완성본 이 자리에 … 이걸 누르면 랜더되는걸로"

확정 버튼(#mixPreviewCta)과 매칭 진행바(#mixStatus 파이프)는 탭과 역할이 겹쳐
지웠다. 탭을 누르면 렌더가 시작된다(부모 startPreview를 iframe이 호출).

⚠️ 이 파일은 **문자열 검사**다 — 실제로 눌러서 렌더가 도는지는 못 본다.
   레이아웃·동작은 브라우저 실측(계획서 Task 4)이 진짜 판정이다.
"""
import pathlib
import re

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"


def _code(name):
    src = (_STATIC / name).read_text(encoding="utf-8")
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith("//"))


def test_확정버튼이_없다():
    pro = _code("produce.html")
    assert "대본×영상믹스 확정" not in pro, "확정 버튼이 아직 있다"


def test_진행바를_안그린다():
    """매칭 파이프(다운로드~완료)는 자리만 먹는다 — 상태는 한 줄 글자로 충분."""
    pro = _code("produce.html")
    assert "MIX_STAGE_ORDER" not in pro, "매칭 진행바가 아직 있다"


def test_상태글자는_남는다():
    """진행바만 뺀다 — '매칭 완료' 한 줄까지 지우면 사용자가 상태를 못 본다."""
    pro = _code("produce.html")
    assert "MIX_LABEL" in pro, "상태 글자표까지 지웠다"
    assert "ready_for_review:'매칭 완료'" in pro, "'매칭 완료' 문구가 사라졌다"


def test_탭이_렌더입구다():
    lab = _code("scene_lab.html")
    body = lab.split("function pvTab(")[1].split("\nfunction ")[0]
    assert "_askRender" in body, "확정본 탭이 렌더를 부르지 않는다"


def test_탭은_비었을때만_렌더한다():
    """이미 만들어졌으면 다시 안 만든다 — 서버 렌더는 20초+ 유료다."""
    lab = _code("scene_lab.html")
    body = lab.split("function _askRender(")[1].split("\nfunction ")[0]
    assert "confirmBody" in body, "이미 있는지 안 본다"
    assert "startPreview" in body, "부모 렌더를 안 부른다"


def test_확정본탭이_잠겨있지_않다():
    """이제 '눌러서 만드는' 버튼이다 — disabled면 렌더 입구가 막힌다.

    마크업의 초기 disabled와, clearConfirm이 다시 잠그던 것 둘 다 떼야 한다.
    """
    lab = _code("scene_lab.html")
    tab = re.search(r'<button[^>]*data-pane="confirm"[^>]*>', lab)
    assert tab, "확정본 탭 버튼을 못 찾았다"
    assert "disabled" not in tab.group(0), "확정본 탭이 아직 disabled로 시작한다"
    body = lab.split("function clearConfirm(")[1].split("\nfunction ")[0]
    assert "disabled = true" not in body and "disabled=true" not in body, \
        "clearConfirm이 아직 탭을 잠근다"
    assert "innerHTML = ''" in body, "clearConfirm이 내용을 안 비운다(옛 영상이 남는다)"


def test_아래카드가_위카드와_같은비율():
    """아래 소스 카드가 9:16이면 세로로 길어 스크롤이 끝없다(2026-08-22 사장님
    "썸네일 크기를 위쪽 내 영상 전체 크기랑 동일하게").

    위(.seg img)는 2026-08-16에 이미 4/5로 줄였는데 아래(.item img)만 9/16으로
    남아 있었다 — 같은 판단이 두 곳에 다르게 적힌 것(0순위-B).
    """
    lab = _code("scene_lab.html")
    seg = re.search(r"\.seg img\{[^}]*aspect-ratio:([^;}]+)", lab)
    item = re.search(r"\.item img\{[^}]*aspect-ratio:([^;}]+)", lab)
    assert seg and item, "카드 비율 정의를 못 찾았다"
    assert seg.group(1).strip() == item.group(1).strip(), \
        f"위={seg.group(1)} 아래={item.group(1)} — 달라서 아래만 세로로 길어진다"


def test_iframe높이가_화면안이다():
    """150vh/1100px은 화면보다 커서 **바깥 페이지**가 먼저 길어졌다(스크롤 두 겹).

    calc(100vh - N)이면 안쪽이 스크롤한다 — 사장님 "스크롤 너무 내리지않고 최소화".
    """
    pro = _code("produce.html")
    h = re.search(r"_SL_FRAME_H\s*=\s*'([^']+)'", pro)
    assert h, "_SL_FRAME_H를 못 찾았다"
    assert "100vh" in h.group(1) and "calc(" in h.group(1), \
        f"iframe 높이가 아직 화면 밖이다: {h.group(1)}"
