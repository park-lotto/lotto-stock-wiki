"""렌즈 CN 후보 = '사이트 링크'(무료, Apify 안 씀) — 후보 버튼이 중국어 검색어로
샤오홍슈/도우인 검색 페이지 URL을 올바로(중국어 URL 인코딩) 만드는지 node 슬라이스로 검증.
2026-07-19: Apify 인앱검색 폐기하고 무료 사이트링크로 전환하며 클릭상한 테스트를 이걸로 교체."""
import json, pathlib, shutil, subprocess, pytest

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
    out = subprocess.run([NODE, "-e", driver], capture_output=True, text=True,
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


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_instagram_tag_link_strips_spaces_and_tails():
    """인스타 '#태그' 버튼(2026-08-14 사장님 "계정만 검색된다").

    인스타 키워드 검색은 띄어쓴 여러 단어에 약해 계정·추천만 뜬다. 태그 URL은 공백이
    들어가면 안 되므로 꼬리(만들기 등) 제거 후 한 덩어리로 붙여야 게시물 그리드가 뜬다."""
    driver = _slice() + r"""
    console.log(JSON.stringify({
      tag:  decodeURIComponent(_lensSearchUrl('instagram_tag', '시금치 치아바타')),
      tail: decodeURIComponent(_lensSearchUrl('instagram_tag', '한국식 김밥 만들기')),
      kw:   decodeURIComponent(_lensSearchUrl('instagram', '시금치 치아바타')),
    }));
    """
    out = subprocess.run([NODE, "-e", driver], capture_output=True, text=True,
                         encoding="utf-8", stdin=subprocess.DEVNULL, timeout=20)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["tag"] == "https://www.instagram.com/explore/tags/시금치치아바타/"
    assert r["tail"] == "https://www.instagram.com/explore/tags/한국식김밥/"
    # 키워드 검색은 종전대로 공백 유지(태그와 서로 다른 입구)
    assert r["kw"] == "https://www.instagram.com/explore/search/keyword/?q=시금치 치아바타"
