"""렌즈 '원본 열기' 링크 도메인 치환 순수 헬퍼 _openUrl(2026-07-19) — node 슬라이스.

샤오훙슈 글 링크는 한국(로그아웃) 방문자를 /login으로 튕긴다(저장 url은 깨끗한데 샤오훙슈
서버가 튕기는 것 — 서버DB·브라우저 실측). 해외판 rednote.com은 같은 xsec_token으로 로그인
벽 없이 열린다. _openUrl은 '원본 열기'에서만 xiaohongshu.com→rednote.com로 바꾸고, 그 외
도메인·저장/다운로드용 url은 건드리지 않는다."""
import json, pathlib, shutil, subprocess, pytest

INDEX_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
NODE = shutil.which("node")
_START = "function _openUrl("


def _slice():
    src = INDEX_HTML.read_text(encoding="utf-8")
    i = src.index(_START)
    return src[i:src.index("\n", i)]


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_open_url_rewrites_only_xiaohongshu():
    driver = _slice() + r"""
    console.log(JSON.stringify({
      // 샤오훙슈 글 링크(xsec_token 포함) → rednote로, 경로·쿼리 보존
      item:   _openUrl("https://www.xiaohongshu.com/discovery/item/abc?xsec_token=T=&xsec_source=app_share"),
      // www 없는 형태도 치환
      nowww:  _openUrl("https://xiaohongshu.com/discovery/item/x"),
      // 후보 검색 링크(로그인벽)도 rednote로 — 쿼리 보존
      search: _openUrl("https://www.xiaohongshu.com/search_result?keyword=%E5%8F%91%E5%85%89"),
      // 다른 플랫폼은 그대로
      douyin: _openUrl("https://www.douyin.com/video/123"),
      // 이미 rednote면 그대로
      already:_openUrl("https://www.rednote.com/explore/xyz"),
      // 빈값 안전
      empty:  _openUrl(""),
      nullv:  _openUrl(null),
    }));
    """
    # stdin=DEVNULL: pytest가 stdin 핸들을 캡처한 상태에서 node -e 가 그 핸들을 건드려
    # Windows WinError 6(invalid handle)로 간헐 실패하던 것을 막는다(2026-07-19 실측).
    out = subprocess.run([NODE, "-e", driver], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, timeout=20)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["item"] == "https://www.rednote.com/discovery/item/abc?xsec_token=T=&xsec_source=app_share"
    assert r["nowww"] == "https://www.rednote.com/discovery/item/x"
    assert r["search"] == "https://www.rednote.com/search_result?keyword=%E5%8F%91%E5%85%89"
    assert r["douyin"] == "https://www.douyin.com/video/123"
    assert r["already"] == "https://www.rednote.com/explore/xyz"
    assert r["empty"] == ""
    assert r["nullv"] == ""
