"""사람이 고른 낱말 색이 **틀(템플릿) 자동 규칙보다 먼저**인지 — 화면·서버 둘 다.

2026-09-02 사장님 제보(실재현 완료):
  "헤드카피 설정 후, 템플릿 적용하고, 다시 헤드카피로 돌아가 기존에 적용되어 있던
   글자별 색을 클릭하여 색 바꿈을 시도하면 기존 색이 바뀌지 않음."

뿌리: 템플릿을 고르면 `applyHeadcopySet`이 **2줄째 통째**를 키워드로 규칙 하나를 넣는다
      ({keyword:"바닥 세정제 추천", color:색2, _fromFrame:true}).
      그런데 색칠 로직(hlSegments / _build_segments)이 **긴 키워드 먼저** 정렬하고
      `marks[i]==null`일 때만 칠하므로, 9자짜리 틀 규칙이 2자짜리 사람 규칙을 통째로 덮었다.
      → 데이터(highlight_rules)는 새 색으로 바뀌는데 **화면·렌더만 안 바뀐다**.
      실측: 내 규칙 #2EE6C5인데 세그먼트는 전부 #000000 한 덩어리.

고침: 정렬을 (사람규칙 먼저, 그 안에서 긴 것 먼저)로. 길이 우선은 같은 등급 안에서만 유지
      (짧은 규칙이 긴 규칙을 조각내는 원래 문제는 그대로 막는다).

★화면과 서버가 **같은 규칙**이어야 미리보기와 최종 렌더가 안 어긋난다(0순위-B) → 둘 다 검사.
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

from shopping_shorts.video_assemble import _build_segments

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRODUCE_HTML = ROOT / "static" / "produce.html"
NODE = shutil.which("node")

# 사장님 재현 그대로: 사람이 '바닥'을 칠해둔 뒤 템플릿이 2줄째 전체를 검정으로 덮는다.
_LINE = "바닥 세정제 추천"
_RULES = [
    {"keyword": "바닥", "color": "#2EE6C5"},
    {"keyword": "바닥 세정제 추천", "color": "#000000", "_fromFrame": True},
]


def test_server_user_rule_wins():
    """서버(_build_segments): '바닥'은 내 색, 나머지는 틀 색."""
    segs = _build_segments(_LINE, "#FFFFFF", _RULES)
    got = [(t, c) for (t, c, _b, _bc) in segs]
    assert got[0] == ("바닥", "#2EE6C5"), (
        f"사람이 고른 낱말이 틀 규칙에 덮였다 — 색을 바꿔도 안 바뀐다: {got}")
    assert any(c == "#000000" for _t, c in got[1:]), f"틀 색이 사라졌다: {got}"


def test_server_longest_first_still_holds_within_same_kind():
    """같은 등급 안에선 여전히 긴 것 먼저 — 짧은 규칙이 긴 규칙을 조각내면 안 된다."""
    rules = [{"keyword": "꿀", "color": "#FF0000"},
             {"keyword": "꿀템", "color": "#00FF00"}]
    segs = _build_segments("이거 꿀템 추천", "#FFFFFF", rules)
    got = [(t, c) for (t, c, _b, _bc) in segs]
    assert ("꿀템", "#00FF00") in got, f"긴 규칙이 조각났다: {got}"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_frontend_matches_server(tmp_path):
    """화면(hlSegments)이 서버와 **같은 결과**를 내는지 — 어긋나면 미리보기가 거짓말한다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    start = src.index("function hlSegments(line, rules, baseColor){")
    frag = src[start:src.index("\n}", start) + 2]
    js = tmp_path / "t.js"
    js.write_text(
        frag + "\nconsole.log(JSON.stringify(hlSegments(" + json.dumps(_LINE)
        + "," + json.dumps(_RULES) + ",'#FFFFFF').map(s=>[s.text,s.color])));",
        encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    front = [tuple(x) for x in json.loads(out.stdout.strip().splitlines()[-1])]
    server = [(t, c) for (t, c, _b, _bc) in _build_segments(_LINE, "#FFFFFF", _RULES)]
    assert front == server, f"화면과 서버가 다르다\n화면 {front}\n서버 {server}"
    assert front[0] == ("바닥", "#2EE6C5"), front


def test_both_sides_sort_by_user_rule_first():
    """정렬 규칙이 양쪽에 다 들어갔는지(한쪽만 고치면 미리보기≠렌더)."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    py = (ROOT / "video_assemble.py").read_text(encoding="utf-8")
    hl = html[html.index("function hlSegments("):][:1600]
    assert "_fromFrame" in hl, "화면 정렬에 사람규칙 우선이 없다"
    assert re.search(r"_fromFrame.*-len\(r\[.keyword.\]\)", py, re.S), \
        "서버 정렬에 사람규칙 우선이 없다"
