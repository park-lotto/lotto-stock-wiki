# -*- coding: utf-8 -*-
"""영상을 바꾸면 3단계가 다시 매칭한다 — 소스 지문 `_sources_hash` (2026-09-21).

★왜 생겼나(회원 제보 2026-09-21):
  "재봉틀 영상을 잘못 넣어서 빼고 다른 영상 2개를 넣었는데, 수정을 해도 영상대본믹스에서는
   계속 미니 재봉틀 영상이 나옵니다."
  3단계는 들어올 때마다 **대본 지문만** 대조해 다시 매칭했다(_remixIfScriptChanged).
  영상을 바꿔도 대본이 그대로면 옛 job이 그대로 남아, 뺀 영상의 장면이 계속 나왔다.

★짝으로 움직이는 값(0순위-B): 서버 `_sources_hash`(app.py)와 화면 `_sourcesHash`
  (produce.html)가 어긋나면 **항상 '바뀐 것'으로 보여 무한 재매칭 = 요금**이다.
  그래서 여기서 node로 화면 함수를 **실제로 돌려** 서버 값과 대조한다.
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

from shopping_shorts.app import _sources_hash

HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"

_CASES = [
    ["https://www.instagram.com/reel/AAA/", "https://www.instagram.com/reel/BBB/"],
    ["https://www.instagram.com/reel/BBB/", "https://www.instagram.com/reel/AAA/"],   # 순서만 다름
    ["https://a.com/1", "https://a.com/1", " https://b.com/2 "],                        # 중복·공백
    ["https://www.douyin.com/video/한글?x=1&y=2"],
    [],
]


def _fn(src, name):
    """produce.html에서 `async function name(...){...}` 한 덩이를 중괄호 짝으로 잘라낸다."""
    m = re.search(r"(async\s+)?function\s+" + re.escape(name) + r"\s*\(", src)
    assert m, name + " 가 produce.html에 없다"
    i = src.index("{", m.end())
    depth, j = 0, i
    while True:
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return src[m.start():j + 1]


def _node(script):
    node = shutil.which("node")
    if not node:
        pytest.skip("node 없음")
    r = subprocess.run([node, "-e", script], capture_output=True, text=True,
                       encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_order_and_duplicates_do_not_change_hash():
    """담긴 순서·중복·앞뒤 공백은 같은 재료다 — 그걸로 다시 매칭(과금)하면 안 된다."""
    assert _sources_hash(_CASES[0]) == _sources_hash(_CASES[1])
    assert _sources_hash(_CASES[2]) == _sources_hash(["https://b.com/2", "https://a.com/1"])


def test_swapping_a_video_changes_hash():
    """영상 하나를 다른 것으로 바꾸면 반드시 달라져야 한다(제보의 핵심)."""
    a = _sources_hash(["https://x/marker1", "https://x/sewing"])
    b = _sources_hash(["https://x/marker1", "https://x/marker2", "https://x/marker3"])
    assert a and b and a != b


def test_empty_is_empty_string():
    for empty in ([], None, ["", "  "]):
        assert _sources_hash(empty) == ""


def test_frontend_hash_matches_server():
    """화면 `_sourcesHash`를 node로 실제 실행해 서버 값과 대조한다."""
    src = HTML.read_text(encoding="utf-8")
    js = (_fn(src, "_scriptHash") + "\n" + _fn(src, "_sourcesHash") + "\n"
          + "const crypto=require('crypto').webcrypto;\n"
          + "(async()=>{const cs=" + json.dumps(_CASES, ensure_ascii=False) + ";"
          + "const o=[];for(const c of cs)o.push(await _sourcesHash(c));"
          + "console.log(JSON.stringify(o));})();")
    got = _node(js)
    assert got == [_sources_hash(c) for c in _CASES]


def _run_remix(status, urls, script="대본"):
    """_remixIfChanged를 가짜 fetch로 돌려 startProduceMix가 몇 번 불렸나 센다."""
    src = HTML.read_text(encoding="utf-8")
    js = ("const crypto=require('crypto').webcrypto;\n"
          + _fn(src, "_scriptHash") + "\n" + _fn(src, "_sourcesHash") + "\n"
          + _fn(src, "_remixIfChanged") + "\n"
          + "let MIX_JOB='job1', calls=0, msgs=[];\n"
          + "const STATE={script:" + json.dumps(script, ensure_ascii=False) + "};\n"
          + "function collectMixUrls(){return " + json.dumps(urls) + ";}\n"
          + "function drawMixStatus(t){msgs.push(t);}\n"
          + "async function startProduceMix(){calls++;}\n"
          + "async function fetch(){return {json:async()=>(" + json.dumps(status, ensure_ascii=False) + ")};}\n"
          + "(async()=>{await _remixIfChanged();console.log(JSON.stringify({calls,msgs}));})();")
    return _node(js)


def test_remix_when_sources_changed_but_script_same():
    """★제보 재현: 대본은 그대로, 영상만 바뀜 → 다시 매칭해야 한다."""
    from shopping_shorts.app import _script_hash
    st = {"ok": True, "status": "ready_for_review", "script_hash": _script_hash("대본"),
          "sources_hash": _sources_hash(["https://x/marker1", "https://x/sewing"])}
    r = _run_remix(st, ["https://x/marker1", "https://x/marker2", "https://x/marker3"])
    assert r["calls"] == 1
    assert "영상" in r["msgs"][0]


def test_no_remix_when_nothing_changed():
    from shopping_shorts.app import _script_hash
    urls = ["https://x/marker1", "https://x/marker2"]
    st = {"ok": True, "status": "done", "script_hash": _script_hash("대본"),
          "sources_hash": _sources_hash(list(reversed(urls)))}
    assert _run_remix(st, urls)["calls"] == 0


def test_no_remix_for_old_job_without_sources_hash_or_empty_pool():
    """옛 job(지문 없음)·영상풀이 빈 화면(복원 전)에선 돈이 나가는 재매칭을 걸지 않는다."""
    from shopping_shorts.app import _script_hash
    base = {"ok": True, "status": "done", "script_hash": _script_hash("대본")}
    assert _run_remix(dict(base), ["https://x/new"])["calls"] == 0
    st = dict(base, sources_hash=_sources_hash(["https://x/old"]))
    assert _run_remix(st, [])["calls"] == 0


def test_no_remix_while_running():
    st = {"ok": True, "status": "planning", "script_hash": "zzz", "sources_hash": "yyy"}
    assert _run_remix(st, ["https://x/new"])["calls"] == 0
