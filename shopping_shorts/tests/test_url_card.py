"""🔗 주소로 가져오기 — 주소 하나 → 그 영상 카드 1장(2026-08-18 사장님 요청).

사장님: "영상 주소를 넣고 이런 식으로 다운된 다음 숏템파워로 찾고 영상을 만드는 과정."
종전엔 랭킹 검색창에 링크를 넣으면 **곧바로 렌즈(유사 영상 찾기)**로 갔다 — 정작 넣은
그 영상의 카드는 안 나왔고, 볼 때마다 유료 렌즈(SerpApi 월 100회)를 태웠다.

여기서 못박는 것:
  ① 카드 1장은 **렌즈를 안 탄다**(무료). 유사 찾기는 팝업 안 버튼으로 그때만.
  ② 지표는 probe_grab_meta 한 곳에서만 읽는다 — 담기·카드와 숫자가 갈리면 안 된다.
  ③ 지원 안 하는 주소는 422로 분명히 거절한다(조용히 빈 카드 금지).
  ④ 메타를 못 읽어도 카드는 준다(로그인벽 등) — 담기·숏템파워검색은 여전히 써야 한다.
"""
import pathlib
from unittest.mock import patch

import pytest

from shopping_shorts import app as ap

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _call(url, meta):
    with patch.object(ap, "probe_grab_meta", lambda u, **k: meta):
        return ap.api_lens_single(request=None, url=url)


def test_지원하는_주소면_카드_한_장을_준다():
    out = _call("https://www.instagram.com/reel/ABC/",
                {"title": "자석 네일펜", "thumbnail": "t.jpg", "views": 569324, "comments": 7217})
    it = out["item"]
    assert out["ok"] and it["platform"] == "instagram"
    assert it["views"] == 569324 and it["comments"] == 7217
    assert it["url"] == "https://www.instagram.com/reel/ABC/"


def test_쓰레드_주소도_된다():
    out = _call("https://www.threads.com/@shop/post/ABC", {"title": "t"})
    assert out["item"]["platform"] == "threads"


def test_지원안하는_주소는_거절한다():
    out = _call("https://example.com/x", {})
    assert getattr(out, "status_code", None) == 422


def test_메타를_못_읽어도_카드는_준다():
    out = _call("https://www.instagram.com/reel/ABC/", {})
    assert out["ok"] and out["item"]["meta_ok"] is False, \
        "로그인벽 등으로 지표만 못 읽는 경우에도 담기·숏템파워검색은 쓸 수 있어야 한다"


def test_렌즈를_타지_않는다():
    """유료 렌즈를 부르면 카드 한 장 볼 때마다 월 100회 예산이 깎인다."""
    src = pathlib.Path(ap.__file__).read_text(encoding="utf-8")
    i = src.index("def api_lens_single(")
    body = src[i:src.index("\n@app.", i)]
    body = body.split('"""')[0] + "".join(body.split('"""')[2:])   # 설명문(주석) 제외
    assert "serpapi" not in body.lower() and "trace_url" not in body


@pytest.mark.parametrize("needle", [
    "function openUrlCard(",            # 팝업 여는 함수
    "openUrlCard((v||'').trim())",      # 검색창 엔터가 이리로 온다(옛 렌즈 직행 아님)
    "openUrlCard()",                    # 검색창 옆 버튼
    "'/api/lens/single?url='",          # 무료 단일조회
    "renderLens('__single__')",         # 카드 렌더러 재사용(새로 그리지 않는다)
    "🔍 비슷한 영상도 찾기",             # 유사 찾기는 눌러야만
])
def test_화면에_배선돼_있다(needle):
    assert needle in INDEX.read_text(encoding="utf-8")


def test_검색창_엔터가_렌즈로_직행하지_않는다():
    src = INDEX.read_text(encoding="utf-8")
    i = src.index("function onSearchEnter(")
    line = src[i:src.index("\n", i)]
    assert "traceByUrl" not in line, "링크 엔터가 곧장 유료 렌즈를 태우면 안 된다"
