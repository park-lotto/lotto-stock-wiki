# -*- coding: utf-8 -*-
"""★배선 테스트 — 컷 개수 규칙이 렌더·화면 양쪽에서 실제로 불리는가.

함수만 만들고 호출부에 안 붙이는 사고가 이 코드베이스에서 반복됐다.
문자열 검색은 주석에도 걸리므로 AST(파이썬)와 호출 패턴(JS)으로 검사한다.
"""
import ast
import io
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VA = ROOT / "video_assemble.py"
JS = ROOT / "static" / "scene_play.js"


def _calls_in(tree, fname):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fname:
            return {c.func.id for c in ast.walk(n)
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    return None


def test_렌더가_컷개수규칙을_부른다():
    tree = ast.parse(io.open(VA, encoding="utf-8").read())
    # 구절 맞춤 계획 함수를 이름으로 찾지 말고, 실제로 부르는 함수를 전부 뒤진다
    hit = [n.name for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and (_calls_in(tree, n.name) or set()) >= {"pick_split_bounds", "cuts_for_beat"}]
    assert hit, "pick_split_bounds/cuts_for_beat를 함께 부르는 함수가 없다 — 배선 누락"


def test_화면도_같은_규칙을_부른다():
    """★planClips **안에서** 불려야 한다 — 파일 어딘가에 이름이 있는 것만으로는
    배선이 아니다(선언부의 자기 이름에 걸려 사보타주를 못 잡았던 가짜 단언 수정)."""
    js = io.open(JS, encoding="utf-8").read()
    code = "\n".join(re.sub(r"//.*$", "", ln) for ln in js.splitlines())
    start = code.index("function planClips")
    body = code[start:code.index("\nfunction ", start + 10)]
    assert re.search(r"\bpickSplitBounds\s*\(", body), "planClips가 pickSplitBounds를 안 부른다"
    assert re.search(r"\bcutsForBeat\s*\(", body), "planClips가 cutsForBeat를 안 부른다"


def test_두_규칙의_상수가_같다():
    """서버와 화면이 다른 값을 쓰면 미리보기와 결과물이 어긋난다(0순위-B)."""
    from shopping_shorts.video_assemble import _BEAT_1CUT_UNDER, _BEAT_3CUT_OVER
    js = io.open(JS, encoding="utf-8").read()
    m = re.search(r"BEAT_1CUT_UNDER\s*=\s*([\d.]+)\s*,\s*BEAT_3CUT_OVER\s*=\s*([\d.]+)", js)
    assert m, "화면 상수를 못 찾았다"
    assert float(m.group(1)) == _BEAT_1CUT_UNDER
    assert float(m.group(2)) == _BEAT_3CUT_OVER


def test_수동하한이_자동하한과_분리돼있다():
    """✋ 수동 지정은 MIN_CLIP(0.8)이 아니라 MANUAL_MIN을 쓴다."""
    js = io.open(JS, encoding="utf-8").read()
    m = re.search(r"const\s+MANUAL_MIN\s*=\s*([\d.]+)", js)
    assert m, "MANUAL_MIN이 없다"
    assert float(m.group(1)) < 0.8, "수동 하한이 자동 하한보다 낮아야 한다"
    body = js[js.index("function applyFixedLens"):]
    body = body[:body.index("\n}")]
    # ★주석은 걷어내고 본다 — 내 설명 주석이 MIN_CLIP을 언급해 빨개졌었다(가짜 실패).
    code = "\n".join(re.sub(r"//.*$", "", ln) for ln in body.splitlines())
    assert "MIN_CLIP" not in code.replace("MANUAL_MIN", ""), \
        "applyFixedLens가 아직 MIN_CLIP으로 수동값을 누르고 있다"


def test_대본프롬프트가_한문장을_지시한다():
    src = io.open(ROOT / "bank_assemble.py", encoding="utf-8").read()
    assert "2~3문장씩 써라" not in src, "옛 지시(2~3문장)가 남아 있다"
    assert "한 칸은 한 문장으로" in src
