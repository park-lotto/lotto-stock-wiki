"""즐겨찾기 → 제작소: 어디로 보낼지 고른다(2026-08-18 사장님 제보).

증상: "레퍼런스에서 담아 제작소로 보내면 **작업 중이던 곳에 합쳐진다**."
원인: 제작소가 신규 핸드오프를 **진행 중 작업에 무조건 누적**했다(2026-07-18에
      '두 번 보내면 앞 것이 지워지던' 버그를 막으려고 넣은 규칙). 규칙 자체는 맞지만
      새 묶음을 보낼 때까지 옛 작업에 섞였다.
처방: 즐겨찾기에서 보낼 때 **새 작업(기본) / 이어서 할 작업**을 고르게 하고,
      새 작업은 `?new=1`(직전 작업 복원 안 함), 이어서는 `?work=<id>`로 간다.

여기서 못박는 것:
  ① 합치는 규칙은 _mergeHandoffItems 한 곳에만 있다(0순위-B).
  ② `?work=<id>` 경로가 **보낸 영상을 버리지 않는다** — 전엔 서버 작업으로 통째
     덮어써서 방금 보낸 게 조용히 사라졌다.
  ③ 즐겨찾기 화면이 두 길(new/work)로 보낸다.
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

BASE = pathlib.Path(__file__).resolve().parents[1] / "static"
PRODUCE = BASE / "produce.html"
COLLECTION = BASE / "collection.html"


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


def test_합치는_규칙은_한_곳에만_있다():
    """두 경로(_consumeProduceHandoff·_restoreWork)가 각자 dedupe를 짜면 언젠가 어긋난다.
    (URL 직접 추가는 별개 기능이라 자기 push를 가진다 — 여기서 세지 않는다)"""
    src = PRODUCE.read_text(encoding="utf-8")
    assert "function _mergeHandoffItems(" in src
    for fname in ("_consumeProduceHandoff", "_restoreWork"):
        body = _fn(src, fname)
        assert "HANDOFF.push(" not in body, \
            f"{fname}가 직접 합치고 있다 — _mergeHandoffItems를 쓰게 하라"


def test_기존작업으로_보내도_영상이_버려지지_않는다():
    """_restoreWork가 서버 작업으로 HANDOFF를 덮어쓴 뒤 **합치는지** 확인."""
    if not shutil.which("node"):
        pytest.skip("node 없음")
    src = PRODUCE.read_text(encoding="utf-8")
    body = _fn(src, "_mergeHandoffItems")
    script = (
        "var HANDOFF = [{shortcode:'OLD', useFootage:true}];\n" + body + "\n"
        "var arrived = _mergeHandoffItems("
        "[{shortcode:'NEW', url:'u'}, {shortcode:'OLD', url:'dup'}]);\n"
        "console.log(JSON.stringify({arrived: arrived,"
        " codes: HANDOFF.map(function(h){return h.shortcode;}),"
        " useFootage: HANDOFF[1].useFootage}));\n")
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["arrived"] == 1, "새 영상 1개만 들어가야 한다(중복은 안 쌓는다)"
    assert out["codes"] == ["OLD", "NEW"], "기존 작업 영상을 지우지 않고 뒤에 붙인다"
    assert out["useFootage"] is True, "보낸 영상은 기본으로 화면에 쓴다"


def test_restoreWork가_보낸영상을_합치고_저장한다():
    src = PRODUCE.read_text(encoding="utf-8")
    body = _fn(src, "_restoreWork")
    assert "_mergeHandoffItems(_pendingHandoffItems())" in body, \
        "기존 작업으로 열 때도 방금 보낸 영상을 합쳐야 한다"
    assert "saveWork()" in body, \
        "합친 뒤 저장하지 않으면 새로고침 한 번에 사라진다(스토리지는 이미 비웠다)"


@pytest.mark.parametrize("needle", [
    "_openSendModal(",          # 보내기 전에 어디로 갈지 묻는다
    "'/produce?new=1'",         # 새 작업
    "'/produce?work='",         # 이어서 할 작업
    "새 작업으로 보내기",
])
def test_즐겨찾기가_두_길로_보낸다(needle):
    assert needle in COLLECTION.read_text(encoding="utf-8")


def test_즐겨찾기는_더이상_무조건_제작소로_가지_않는다():
    """`location.href='/produce'`(목적지 없이)가 남아 있으면 옛 합쳐짐이 그대로 재발한다."""
    src = COLLECTION.read_text(encoding="utf-8")
    assert "location.href='/produce'" not in src.replace(" ", "")
