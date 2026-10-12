"""렌즈 CN 후보 = '사이트 링크'(무료, Apify 안 씀) — 후보 버튼이 중국어 검색어로
샤오홍슈/도우인 검색 페이지 URL을 올바로(중국어 URL 인코딩) 만드는지 node 슬라이스로 검증.
2026-07-19: Apify 인앱검색 폐기하고 무료 사이트링크로 전환하며 클릭상한 테스트를 이걸로 교체."""
import json, pathlib, shutil, subprocess, pytest
from shopping_shorts.tests.js_harness import run_js_proc

INDEX_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
NODE = shutil.which("node")
_START = "function _lensSearchUrl("
_END = "function renderLens("


def _slice():
    src = INDEX_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_cn_candidate_site_links():
    driver = _slice() + r"""
    console.log(JSON.stringify({
      xhs: _lensSearchUrl('xiaohongshu', '空气炸锅土豆片'),
      dy:  _lensSearchUrl('douyin', '气泡土豆'),
      tk:  _lensSearchUrl('tiktok', '공기튀김 감자칩'),
      ig:  _lensSearchUrl('instagram', '공기튀김 감자칩'),
    }));
    """
    # stdin=DEVNULL: pytest가 stdin 핸들을 캡처/교체한 상태에서 node -e 가 그 핸들을
    # 건드려 Windows WinError 6(invalid handle)로 간헐 실패하던 것을 막는다(2026-07-19 실측).
    out = run_js_proc(driver, capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, timeout=20)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    # 중국어가 URL 인코딩돼 그 사이트 검색으로 열려야 한다(무료 경로의 핵심)
    assert r["xhs"] == "https://www.xiaohongshu.com/search_result?keyword=" \
        + "%E7%A9%BA%E6%B0%94%E7%82%B8%E9%94%85%E5%9C%9F%E8%B1%86%E7%89%87"
    assert r["dy"].startswith("https://www.douyin.com/search/")
    assert "%E6%B0%94%E6%B3%A1%E5%9C%9F%E8%B1%86" in r["dy"]   # 气泡土豆 인코딩
    # 틱톡/인스타는 한국어(c.ko)로 검색 — 중국앱은 중국어, 글로벌앱은 한국어(플랫폼별 언어)
    assert r["tk"].startswith("https://www.tiktok.com/search?q=")
    assert r["ig"].startswith("https://www.instagram.com/explore/search/keyword/?q=")
    assert "%EA%B3%B5%EA%B8%B0" in r["tk"]   # '공기...' 한국어 인코딩


# ── 인스타 검색어 다듬기 — 라이브 인스타 실측(2026-08-16)을 그대로 고정한다 ──
# 사장님 제보 "인스타는 10에 8이 결과없음". 원인은 길이가 아니라 **지어낸 조합**이었다.
# 아래 기대값 옆 숫자는 그날 라이브 인스타에서 직접 센 결과 건수다.
@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_ig_keyword_trim_measured_cases():
    driver = _slice() + r"""
    const cases=['고독스 아동용 카메라','고독스 토이 카메라','아이 장난감 카메라',
                 '어린이 사진 촬영','키즈 카메라 추천','고독스 카메라 언박싱',
                 '고독스 픽스플레이 사용법','고독스 카메라'];
    console.log(JSON.stringify(cases.map(c=>[c,_igKw(c),_igShortKw(c)])));
    """
    # encoding 명시 필수 — 한글이 오가는데 윈도우 기본 cp949로 읽으면 깨진다
    # (형제 테스트는 URL 퍼센트인코딩이라 ASCII뿐이어서 문제가 안 났다).
    out = run_js_proc(driver, capture_output=True, text=True,
                         encoding="utf-8", stdin=subprocess.DEVNULL)
    assert out.returncode == 0, out.stderr
    got = {c: (trim, short) for c, trim, short in json.loads(out.stdout)}
    # 3어절 → 첫+마지막 (실측: 0건 → 18/15/18건)
    assert got["고독스 아동용 카메라"][0] == "고독스 카메라"
    assert got["고독스 토이 카메라"][0] == "고독스 카메라"
    assert got["아이 장난감 카메라"][0] == "아이 카메라"
    assert got["어린이 사진 촬영"][0] == "어린이 촬영"
    # 꼬리말 제거 (추천/언박싱/사용법)
    assert got["키즈 카메라 추천"][0] == "키즈 카메라"
    assert got["고독스 카메라 언박싱"][0] == "고독스 카메라"
    assert got["고독스 픽스플레이 사용법"][0] == "고독스 픽스플레이"
    # 이미 짧은 건 안 건드린다
    assert got["고독스 카메라"][0] == "고독스 카메라"
    # 안전망: 2어절이면 마지막 한 단어(실측 '픽스플레이' 13건)
    assert got["고독스 픽스플레이 사용법"][1] == "픽스플레이"
    assert got["고독스 카메라"][1] == "카메라"


# ── 영어(한글 없음) 검색어 — 2026-09-14 라이브 인스타 실측 ──
# 'Mario phone case'(3)·'Super Mario phone case'(4) 결과 있음 / 5단어 이상 전부 0건.
# 한국어식 '첫+끝'을 영어에 쓰면 'Mario phone case'가 'Mario case'로 망가졌다.
@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_ig_keyword_english_keeps_up_to_4_words():
    driver = _slice() + r"""
    const cases=['Mario phone case','Super Mario phone case','Mario phone case with stand',
                 'Super Mario 3D stand phone case'];
    console.log(JSON.stringify(cases.map(c=>[c,_igKw(c)])));
    """
    out = run_js_proc(driver, capture_output=True, text=True,
                      encoding="utf-8", stdin=subprocess.DEVNULL)
    assert out.returncode == 0, out.stderr
    got = dict(json.loads(out.stdout))
    assert got["Mario phone case"] == "Mario phone case"
    assert got["Super Mario phone case"] == "Super Mario phone case"
    assert got["Mario phone case with stand"] == "Mario phone case stand"
    assert len(got["Super Mario 3D stand phone case"].split()) <= 4


# ── 핀터레스트 검색어 줄이기 — 2026-09-26 앱 크롤러(pinterest_crawl, 영상탭)로 센 건수 ──
# 사장님 "베이스어스 이어폰이 정확한데 핀터는 길어서 안 나온다".
@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_pinterest_keyword_trim_measured_cases():
    driver = _slice() + r"""
    const cases=['Baseus open ear headphones','earbuds that don\'t fall out while running',
                 'comfortable open ear headphones for running','affordable sports earbuds review',
                 'running earbuds','super mario phone case','Super Mario phone case',
                 'Godox kids digital camera','Dyson cordless hair dryer','Baseus オープンイヤー型イヤホン'];
    console.log(JSON.stringify(cases.map(c=>[c,_pinKw(c)])));
    console.log(_lensSearchUrl('pinterest','Baseus open ear headphones'));
    """
    out = run_js_proc(driver, capture_output=True, text=True,
                      encoding="utf-8", stdin=subprocess.DEVNULL)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.strip().splitlines()
    got = dict(json.loads(lines[0]))
    assert got["Baseus open ear headphones"] == "Baseus headphones"          # 3건 → 22건
    assert got["earbuds that don't fall out while running"] == "earbuds"     # 1건 → 25건
    assert got["comfortable open ear headphones for running"] == "open ear headphones"  # 0 → 25
    assert got["affordable sports earbuds review"] == "affordable sports earbuds"
    assert got["running earbuds"] == "running earbuds"                       # 짧은 건 그대로(25)
    # 브랜드 없는 4단어는 뒤 3단어 — 'super case'(뜻 망가짐)가 되면 안 된다
    assert got["super mario phone case"] == "mario phone case"
    assert got["Super Mario phone case"] == "Super Mario case"               # 두 단어 브랜드 유지
    assert got["Godox kids digital camera"] == "Godox camera"               # 0건 → 25건
    assert got["Dyson cordless hair dryer"] == "Dyson dryer"                # 7건 → 25건
    assert got["Baseus オープンイヤー型イヤホン"] == "Baseus オープンイヤー型イヤホン"   # 영어 아닌 건 안 건드림
    assert lines[1] == "https://www.pinterest.com/search/videos/?q=Baseus%20headphones"
