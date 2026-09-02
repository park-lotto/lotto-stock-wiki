"""6단계 꾸미기에서 **출력을 바꾸는 조작은 전부 저장돼야 한다**.

2026-09-02 실사용 QA에서 같은 병을 네 번 찾았다(자막11 · 헤드카피14 · 그리고 아래 4개):
화면·STATE는 바뀌는데 저장(saveHeadcopy → POST /api/produce/mix/settings)을 안 불러
**새로고침하면 원복**되고 최종 렌더에도 안 실린다. 사장님 제보
"바꾼 게 적용은 되는데 렌더에 반영이 안 된다"의 실체다.

이 테스트는 **호출 사슬을 따라가며** 저장 여부를 본다(직접 부르든, 부르는 함수를 통하든 OK).
새 조작을 추가할 때 저장을 빠뜨리면 여기서 잡힌다.
"""
import pathlib
import re

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"

# STATE.deco / headcopy / captionStyle 을 바꾸므로 **반드시 저장돼야 하는** 조작들.
# (라이브에서 실제로 안 되던 것 4개 + 되던 것 몇 개를 함께 넣어 회귀도 본다)
MUST_SAVE = [
    "hcWordSetColor",   # 낱말 강조 색 — 안 됐다
    "hcWordClear",      # 낱말 강조 해제 — 안 됐다
    "clearOverlay",     # 이미지 오버레이 제거 — 안 됐다(넣기는 저장했다)
    "clearHeadcopy",    # 헤드카피 문구 비우기 — 안 됐다
    "frUpdate",         # 틀 설정
    "frSwapHeadcopy",   # 틀↔헤드카피 교체
    "mkAdd",            # 가림 추가
    "pickMotionPack",   # 모션팩
    "capTouched",       # 자막 컨트롤 공용 입구
    "hcTouched",        # 헤드카피 컨트롤 공용 입구
]

_SAVERS = re.compile(r"saveHeadcopy\(|_capSaveSoon\(|_hcSaveSoon\(|saveWork\(")
_SKIP_CALLEES = {"if", "for", "while", "switch", "function", "return", "catch",
                 "typeof", "parseInt", "parseFloat", "Number", "String", "Math"}


def _src() -> str:
    return PRODUCE_HTML.read_text(encoding="utf-8")


def _body_of(src: str, fn: str):
    """함수 본문을 중괄호 균형으로 잘라낸다(정규식만으론 중첩을 못 센다)."""
    m = re.search(r"function\s+" + re.escape(fn) + r"\s*\([^)]*\)\s*\{", src)
    if not m:
        return None
    depth = 0
    for k in range(m.end() - 1, min(len(src), m.end() + 9000)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[m.end():k]
    return None


def _saves(src: str, fn: str, seen=None, depth=0) -> bool:
    """직접 저장하거나, 저장하는 함수를 부르면 True(사슬 3단까지)."""
    if seen is None:
        seen = set()
    if fn in seen or depth > 3:
        return False
    seen.add(fn)
    body = _body_of(src, fn)
    if body is None:
        return False
    if _SAVERS.search(body):
        return True
    for callee in set(re.findall(r"\b([a-zA-Z_$][\w$]*)\s*\(", body)):
        if callee in _SKIP_CALLEES:
            continue
        if _saves(src, callee, seen, depth + 1):
            return True
    return False


@pytest.mark.parametrize("fn", MUST_SAVE)
def test_handler_persists(fn):
    src = _src()
    assert _body_of(src, fn) is not None, f"{fn} 정의를 못 찾음(이름이 바뀌었나)"
    assert _saves(src, fn), (
        f"{fn}()이 저장을 안 한다 — 화면·STATE만 바뀌고 새로고침하면 원복된다. "
        f"최종 렌더에도 안 실린다(사장님 제보 '반영 안 됨'의 실체)")
