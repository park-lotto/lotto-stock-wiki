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
    "renderLens('__single__', 'urlCardMount')",  # 카드 렌더러 재사용 + 전용 자리에 인라인
    'id="urlCardBox"',                  # #cards(grid)에 넣으면 칸이 갈린다
    "lensSearchByUrl(",                 # 숏템파워검색 = 우리 렌즈(traceByUrl)
])
def test_화면에_배선돼_있다(needle):
    assert needle in INDEX.read_text(encoding="utf-8")


def test_검색창_엔터가_렌즈로_직행하지_않는다():
    src = INDEX.read_text(encoding="utf-8")
    i = src.index("function onSearchEnter(")
    line = src[i:src.index("\n", i)]
    assert "traceByUrl" not in line, "링크 엔터가 곧장 유료 렌즈를 태우면 안 된다"


def test_팝업이_아니라_카드_자리에_그린다():
    """사장님 요청: "여기서 그 영상만 나오게" — 모달을 띄우지 않는다."""
    src = INDEX.read_text(encoding="utf-8")
    i = src.index("async function openUrlCard(")
    body = src[i:src.index("\n// 숏템파워검색(주소용)", i)]
    assert "openScript(" not in body, "팝업을 띄우면 랭킹 화면에서 벗어난다"
    assert "getElementById('cards')" in body


def test_숏템파워검색은_기존_렌즈경로를_쓴다():
    """검색을 새로 짜면 렌즈 결과 화면·필터·담기가 두 벌이 된다."""
    src = INDEX.read_text(encoding="utf-8")
    i = src.index("function lensSearchByUrl(")
    assert "traceByUrl(url)" in src[i:i + 200]


def test_유튜브_채널_전부_벤치등록_버튼은_숨겨져_있다():
    """사장님 '이거 숨기고' — 한 번에 15개가 수집목록에 들어가 되돌리기 번거롭다."""
    src = INDEX.read_text(encoding="utf-8")
    assert "유튜브 채널 전부 벤치등록(" not in src.replace(
        "➕ 유튜브 채널 전부 벤치등록 — 2026-08-18", "")


# ── 스킴 없는 주소(2026-08-18 사장님 "엔터가 안 먹는다") ────────────────────────
# 크롬 주소창은 https://를 감춰 보여주고, 그대로 복사하면 스킴이 빠진다.
# 실측 입력: youtube.com/shorts/_6v_D3MktcI?si=... → 종전 판정은 '검색어'로 취급해 무동작.
def _run_js(exprs):
    import json as _json
    import shutil as _sh
    import subprocess as _sp
    if not _sh.which("node"):
        pytest.skip("node 없음")
    src = INDEX.read_text(encoding="utf-8")
    i = src.index("var _URL_HOSTS =")
    j = src.index("function onSearchEnter(")
    body = src[i:j]
    script = body + "\nconsole.log(JSON.stringify([" + ",".join(exprs) + "]));"
    r = _sp.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return _json.loads(r.stdout)


def test_스킴_없는_주소도_링크로_본다():
    out = _run_js([
        "_looksLikeUrl('youtube.com/shorts/_6v_D3MktcI?si=abc')",
        "_looksLikeUrl('https://www.instagram.com/reel/ABC/')",
        "_looksLikeUrl('www.threads.com/@shop/post/ABC')",
        "_looksLikeUrl('채이홈')",
        "_looksLikeUrl('피자 만들기')",
    ])
    assert out[:3] == [True, True, True], "스킴이 빠진 주소도 받아야 한다"
    assert out[3:] == [False, False], "채널명·소재 검색이 링크로 오인되면 안 된다"


def test_스킴을_붙여_보낸다():
    out = _run_js([
        "_normUrl('youtube.com/shorts/ABC')",
        "_normUrl('https://youtu.be/ABC')",
    ])
    assert out[0] == "https://youtube.com/shorts/ABC", \
        "서버는 hostname으로 플랫폼을 가린다 — 스킴이 없으면 422가 난다"
    assert out[1] == "https://youtu.be/ABC"


def test_격자_안에_그리지_않는다():
    """#cards는 display:grid — 머리줄과 렌즈 뭉치를 형제로 넣으면 좌우로 쪼개진다
    (2026-08-18 사장님 캡처가 그 상태였다). 전용 칸에만 그린다."""
    src = INDEX.read_text(encoding="utf-8")
    i = src.index("async function openUrlCard(")
    body = src[i:src.index("\nfunction closeUrlCard(", i)]
    assert "renderLens('__single__', 'cards')" not in body, \
        "카드 격자에 직접 그리면 머리줄과 렌즈 뭉치가 좌우로 쪼개진다"
    assert "renderLens('__single__', 'urlCardMount')" in body


def test_랭킹으로_돌아가기가_목록을_되살린다():
    src = INDEX.read_text(encoding="utf-8")
    i = src.index("function closeUrlCard(")
    body = src[i:i + 500]
    assert "display='none'" in body and "grid.style.display=''" in body, \
        "전용 칸을 감추고 랭킹 격자를 다시 보여야 한다"


def test_카드_안에도_숏템파워검색이_있다():
    """머리줄이 스크롤로 밀리면 못 찾는다 — 눌러야 할 버튼은 카드 옆에 있어야 한다
    (2026-08-18 사장님 "왜 숏템검색이 없어졌나")."""
    src = INDEX.read_text(encoding="utf-8")
    assert "shortcode==='__single__'?" in src and "🔍 숏템파워검색" in src


def test_단일카드에선_렌즈_도구줄을_접는다():
    """'아직 검색어가 없습니다' 같은 안내가 카드 위에 깔리면 버튼이 화면 밖으로 밀린다."""
    src = INDEX.read_text(encoding="utf-8")
    i = src.index("async function openUrlCard(")
    body = src[i:src.index("\n// 주소 카드를 띄운 채로", i)]
    assert "classList.contains('cards')" in body, "카드 격자만 남기고 나머지는 접는다"
