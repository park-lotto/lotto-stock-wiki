# -*- coding: utf-8 -*-
"""영상·소리·그림은 절대 gzip으로 압축하지 않는다 (2026-09-02 고객 제보의 진짜 뿌리).

증상: 미리보기가 검은 화면 / "분명 영상인데 사진처럼 멈춰서 확인이 불가" /
      "돌아가다 다음 클립에서 멈추고 또 돌아가다 멈추고".

★라이브 실측(/api/mix/src/353493f20d31/s0):
  · fetch + Range 요청 → 206, 66ms 정상. Range 응답엔 gzip이 안 붙는다.
  · <video>가 보내는 **Range 없는 첫 GET** → 200 + content-encoding: gzip
    + transfer-encoding: chunked (Content-Length 없음)
    → 8초가 지나도 readyState 0 / networkState 2. 서버 Range·moov·코덱은 전부 정상.
  브라우저 <video>는 Content-Length 없이 압축된 미디어를 다루지 못한다.

GZipMiddleware는 타입을 안 가리고 모든 응답을 압축하므로, 응답 타입을 보고
Content-Encoding: identity를 심어 압축을 비켜가게 한다(Starlette 0.36.3 실측:
GZipResponder는 content-encoding이 이미 있으면 압축하지 않는다).
"""
import gzip as _gz

import pytest
from starlette.applications import Starlette
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from shopping_shorts.app import _NoCompressMedia

BIG = b"x" * 40000


def _app():
    async def mp4(request):
        return Response(BIG, media_type="video/mp4")

    async def js(request):
        return Response(BIG, media_type="application/json")

    async def mp3(request):
        return Response(BIG, media_type="audio/mpeg")

    app = Starlette(routes=[Route("/v", mp4), Route("/j", js), Route("/a", mp3)])
    app.add_middleware(_NoCompressMedia)          # 안쪽
    app.add_middleware(GZipMiddleware, minimum_size=1024)   # 바깥
    return app


@pytest.fixture
def cli():
    return TestClient(_app())


def test_영상은_압축되지_않는다(cli):
    """★이게 깨지면 미리보기가 통째로 검게 죽는다."""
    r = cli.get("/v", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") != "gzip", "mp4가 gzip으로 나갔다"
    assert r.content == BIG


def test_영상은_길이를_알려준다(cli):
    """Content-Length가 없으면 <video>가 시크를 못 한다(chunked가 되는 게 문제였다)."""
    r = cli.get("/v", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-length") == str(len(BIG)), dict(r.headers)


def test_소리도_마찬가지(cli):
    r = cli.get("/a", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") != "gzip"


def test_JSON은_그대로_압축된다(cli):
    """압축을 통째로 끄면 안 된다 — 랭킹 3.34MB 응답이 느려진 게 gzip을 넣은 이유다."""
    r = cli.get("/j", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip", "JSON 압축까지 꺼졌다"
    assert r.content == BIG          # httpx가 풀어서 준다
