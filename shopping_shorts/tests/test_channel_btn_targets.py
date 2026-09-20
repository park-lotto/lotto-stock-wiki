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
from shopping_shorts.tests.js_harness import run_js_proc

BASE = pathlib.Path(__file__).resolve().parents[1]
LOGIC = BASE / "userscript" / "grab_logic.js"
LOADER = BASE / "userscript" / "grab.user.js"
MANIFEST = BASE / "extension" / "manifest.json"

_FUNCS = ["_chPlat", "_thProfile", "_ytTarget", "_chQuery",
          "_igProfileName", "_ttProfile", "isSinglePost", "_igAuthor"]

# _igAuthor는 화면(DOM)을 읽는다 — 기본 스텁은 '아무것도 못 읽음'이라 종전과 답이 같다.
_DOC_EMPTY = ("var document = { querySelectorAll: function () { return []; },"
              " body: { innerHTML: '' } };\n")


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


def _run(cases, doc=None):
    if not shutil.which("node"):
        pytest.skip("node 없음")
    src = LOGIC.read_text(encoding="utf-8")
    i = src.find("var _IG_RESERVED")
    assert i != -1
    head = src[i:src.index("};", i) + 2]
    body = head + "\n" + "\n".join(_fn(src, n) for n in _FUNCS)
    script = (
        "var location;\n" + (doc or _DOC_EMPTY) + body + "\n" +
        "var out = {};\n"
        "for (var href of " + json.dumps(cases) + ") {\n"
        "  var u = new URL(href);\n"
        "  location = { host: u.host, pathname: u.pathname, search: u.search, href: href };\n"
        "  out[href] = _chQuery();\n"
        "}\n"
        "console.log(JSON.stringify(out));\n")
    r = run_js_proc(script, capture_output=True, text=True, timeout=60)
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


def test_레퍼런스_등록_버튼이_영상_페이지에서만_뜬다():
    """⭐ 레퍼런스 등록(2026-08-18) — 피드·프로필에선 '어느 영상'인지 정해지지 않는다."""
    if not shutil.which("node"):
        pytest.skip("node 없음")
    src = LOGIC.read_text(encoding="utf-8")
    body = _fn(src, "_isVideoPage")
    cases = ["https://www.instagram.com/reel/ABC/",
             "https://www.instagram.com/",
             "https://www.instagram.com/some_user/",
             "https://www.youtube.com/shorts/_6v_D3MktcI",
             "https://www.youtube.com/",
             "https://www.threads.com/@shop/post/TH1",
             "https://www.threads.com/@shop",
             "https://www.tiktok.com/@h/video/7412345678901234567"]
    script = ("var location;\n" + body + "\nvar out={};\n"
              "for (var href of " + json.dumps(cases) + "){\n"
              "  var u=new URL(href);\n"
              "  location={host:u.host, pathname:u.pathname, search:u.search, href:href};\n"
              "  out[href]=_isVideoPage();\n}\n"
              "console.log(JSON.stringify(out));")
    r = run_js_proc(script, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["https://www.instagram.com/reel/ABC/"] is True
    assert out["https://www.youtube.com/shorts/_6v_D3MktcI"] is True
    assert out["https://www.threads.com/@shop/post/TH1"] is True
    assert out["https://www.tiktok.com/@h/video/7412345678901234567"] is True
    assert out["https://www.instagram.com/"] is False
    assert out["https://www.instagram.com/some_user/"] is False, "프로필엔 등록할 영상이 없다"
    assert out["https://www.youtube.com/"] is False
    assert out["https://www.threads.com/@shop"] is False


def test_레퍼런스_등록_버튼이_같은_팝업_방식을_쓴다():
    src = LOGIC.read_text(encoding="utf-8")
    assert '"/api/reference/adopt?url="' in src.replace("'", '"'), \
        "담기·채널수집과 같은 popup GET(세션 쿠키가 실린다)이어야 한다"
    assert "ss-adopt-btn" in src


def test_화면_숫자를_읽어_붙인다():
    """A안(2026-08-18): 서버가 못 읽는 조회수·팔로워를 화면 글자에서 읽어 같이 보낸다.
    '1.2만'·'22.1만' 같은 한국식 단위를 못 풀면 0이 되어 아무 소용이 없다."""
    if not shutil.which("node"):
        pytest.skip("node 없음")
    src = LOGIC.read_text(encoding="utf-8")
    body = "\n".join(_fn(src, n) for n in ("_num", "_pageStats", "_pageStatsQuery"))
    page = "좋아요 207개 댓글 1,202개 조회수 1.2만회 팔로워 22.1만"
    script = ("var document={body:{innerText:" + json.dumps(page) + "}};\n" + body +
              "\nconsole.log(JSON.stringify([_pageStats(), _num('195만'), _num('6.3천'), _num('')]));")
    r = run_js_proc(script, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    stats, man, chun, empty = json.loads(r.stdout)
    assert stats == {"views": 12000, "likes": 207, "comments": 1202, "followers": 221000}
    assert man == 1950000 and chun == 6300
    assert empty == 0, "못 읽으면 0 — 서버는 0을 안 쓰고 종전 값을 유지한다"


def test_릴스에서_작성자를_화면에서_읽어_보낸다():
    """서버 yt-dlp가 인스타를 못 읽어 '채널을 못 찾았어요'가 뜨던 것(2026-09-02 사장님 제보).
    화면에 이미 떠 있는 계정명을 읽어 username으로 함께 보낸다."""
    rect = "function () { return { width: 400, height: 700 }; }"
    doc = ("var _a = { getAttribute: function () { return '/sua_play/'; } };\n"
           "var _box = { querySelectorAll: function () { return [_a]; },"
           " parentElement: null, getBoundingClientRect: " + rect + " };\n"
           "var _v = { parentElement: _box, getBoundingClientRect: " + rect + " };\n"
           "var document = { querySelectorAll: function (s) {"
           " return s === 'video' ? [_v] : []; }, body: { innerHTML: '' } };\n")
    url = "https://www.instagram.com/reels/Dcvn_VGS497/"
    out = _run([url], doc=doc)
    assert out[url].startswith("url="), "URL도 함께 보내야 한다"
    assert "username=sua_play" in out[url], out[url]
