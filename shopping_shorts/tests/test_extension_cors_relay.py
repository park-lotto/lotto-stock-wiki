"""확장이 서버 요청을 **백그라운드로 대행**한다(2026-08-18 실사고).

증상: 인스타 화면의 🔍렌즈가 "❌ 서버 연결 실패". 랭킹 화면(같은 도메인)에서는 정상.
실측(서버 로그): `"OPTIONS /api/lens/trace_url" 401 Unauthorized` — 브라우저가 보낸
**사전확인(preflight)**을 우리 로그인 가드가 막아 본 요청이 아예 안 나갔다.
원인: MV3에서 콘텐츠 스크립트의 fetch는 **그 페이지(instagram.com)의 CORS 규칙**을 받는다.
처방: host_permissions로 CORS를 안 타는 **서비스워커**가 대신 보낸다.
      (서버에서 instagram.com에 credentialed CORS를 열어주는 길도 있지만, 그러면 인스타의
       아무 스크립트나 사장님 쿠키로 우리 API를 부를 수 있게 된다 — 택하지 않았다.)
"""
import json
import pathlib

import pytest

EXT = pathlib.Path(__file__).resolve().parents[1] / "extension"
CONTENT = EXT / "content.js"
BACKGROUND = EXT / "background.js"
MANIFEST = EXT / "manifest.json"


def test_콘텐츠_스크립트가_직접_fetch하지_않는다():
    src = CONTENT.read_text(encoding="utf-8")
    body = src[src.index("__ssGmFetch"):]
    assert "fetch(d.url" not in body, \
        "콘텐츠 스크립트에서 직접 보내면 페이지 CORS에 걸려 preflight가 401로 막힌다"
    assert "chrome.runtime.sendMessage" in body


def test_백그라운드가_대행하고_비동기_응답을_연다():
    src = BACKGROUND.read_text(encoding="utf-8")
    assert "__ssRelay" in src and "chrome.runtime.onMessage.addListener" in src
    assert "return true;" in src, \
        "true를 안 돌려주면 sendResponse가 무시돼 화면은 '서버 연결 실패'로 보인다"
    assert 'credentials: "include"' in src, "로그인 쿠키가 실려야 가드를 통과한다"


def test_우리_서버로만_대행한다():
    """아무 도메인이나 열면 페이지 스크립트가 사용자 쿠키로 임의 요청을 쏘는 통로가 된다."""
    src = BACKGROUND.read_text(encoding="utf-8")
    assert 'SS_BASE = "https://shoppingshorts.duckdns.org/"' in src
    assert "indexOf(SS_BASE) !== 0" in src


def test_확장_버전이_올라갔다():
    """압축해제 확장은 자동업데이트가 없다 — 버전이 올라야 사장님이 갈아끼운 걸 확인할 수 있다."""
    ver = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    assert tuple(int(x) for x in ver.split(".")) >= (1, 3, 0)
