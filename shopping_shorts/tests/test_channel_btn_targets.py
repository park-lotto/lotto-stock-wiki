"""채널수집 버튼이 '어느 화면에서 뜨고, 무엇을 보내는가'(2026-08-18).

버튼 로직은 브라우저 안에서만 도는 코드라 파이썬 테스트로는 못 만진다. 그래서
grab_logic.js에서 판정 함수만 떼어내 node로 **실제 실행**해 확인한다
(test_ranking_render_tdz.py와 같은 방식 — 문법검사로는 못 잡는 층).

같이 지키는 것: 로직을 넣어도 로더 @match·확장 manifest에 그 도메인이 없으면
버튼은 영영 안 뜬다. 쓰레드가 딱 그 상태였다 — 그래서 한 파일이라도 빠지면 깨지게 둔다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

BASE = pathlib.Path(__file__).resolve().parents[1]
LOGIC = BASE / "userscript" / "grab_logic.js"
LOADER = BASE / "userscript" / "grab.user.js"
MANIFEST = BASE / "extension" / "manifest.json"

_FUNCS = ["_chPlat", "_thProfile", "_ytTarget", "_chQuery",
          "_igProfileName", "_ttProfile", "isSinglePost"]


def _fn(src, name):
    """`function name(` 부터 중괄호 균형으로 함수 하나를 통째로 뽑는다."""
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


def _run(cases):
    if not shutil.which("node"):
        pytest.skip("node 없음")
    src = LOGIC.read_text(encoding="utf-8")
    i = src.find("var _IG_RESERVED")
    assert i != -1
    head = src[i:src.index("};", i) + 2]
    body = head + "\n" + "\n".join(_fn(src, n) for n in _FUNCS)
    script = (
        "var location;\n" + body + "\n" +
        "var out = {};\n"
        "for (var href of " + json.dumps(cases) + ") {\n"
        "  var u = new URL(href);\n"
        "  location = { host: u.host, pathname: u.pathname, search: u.search, href: href };\n"
        "  out[href] = _chQuery();\n"
        "}\n"
        "console.log(JSON.stringify(out));\n")
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_유튜브_쇼츠와_채널화면에서_버튼이_뜬다():
    out = _run(["https://www.youtube.com/shorts/AbCdEfGhIjK",
                "https://www.youtube.com/watch?v=AbCdEfGhIjK",
                "https://www.youtube.com/@ssulpulda/shorts",
                "https://www.youtube.com/"])
    assert out["https://www.youtube.com/shorts/AbCdEfGhIjK"].startswith("url=")
    assert out["https://www.youtube.com/watch?v=AbCdEfGhIjK"].startswith("url=")
    assert out["https://www.youtube.com/@ssulpulda/shorts"].startswith("url=")
    assert out["https://www.youtube.com/"] == "", "홈(피드)에선 대상이 모호해 안 뜬다"


def test_쓰레드_게시물과_프로필에서_버튼이_뜬다():
    out = _run(["https://www.threads.com/@shop_lotto/post/DcAbCdEf",
                "https://www.threads.com/@shop_lotto",
                "https://www.threads.com/"])
    assert out["https://www.threads.com/@shop_lotto/post/DcAbCdEf"].startswith("url=")
    assert out["https://www.threads.com/@shop_lotto"].startswith("url=")
    assert out["https://www.threads.com/"] == ""


def test_인스타_틱톡_종전동작이_그대로다():
    out = _run(["https://www.instagram.com/some_user/",
                "https://www.instagram.com/reel/AbCdEfG/",
                "https://www.instagram.com/explore/",
                "https://www.tiktok.com/@handle",
                "https://www.tiktok.com/@handle/video/7412345678901234567"])
    assert out["https://www.instagram.com/some_user/"] == "username=some_user", \
        "인스타 프로필은 종전처럼 username으로 보낸다"
    assert out["https://www.instagram.com/reel/AbCdEfG/"].startswith("url=")
    assert out["https://www.instagram.com/explore/"] == ""
    assert out["https://www.tiktok.com/@handle"].startswith("url=")
    assert out["https://www.tiktok.com/@handle/video/7412345678901234567"].startswith("url=")


@pytest.mark.parametrize("dom", ["threads.com", "threads.net"])
def test_쓰레드가_로더와_확장_양쪽에_등록돼_있다(dom):
    """담기·채널수집 로직이 있어도 여기 빠지면 쓰레드에서 스크립트 자체가 안 돈다."""
    assert "https://*.%s/*" % dom in LOADER.read_text(encoding="utf-8")
    matches = json.loads(MANIFEST.read_text(encoding="utf-8"))["content_scripts"][0]["matches"]
    assert "https://*.%s/*" % dom in matches
