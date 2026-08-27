"""핀터레스트 수집 — 2026-08-28 사장님 "깨끗한 영상들이 많아서 / 나만보게 비공개탭".

## 왜 (실측)
핀터레스트 영상은 **자막·워터마크가 없는 원본**이 많다. 실측으로 받아본 결과:
  · 720x1280 세로 9:16 — 우리 쇼츠 규격 그대로
  · pv1(9.0초): 자막·워터마크·로고 **0개** — 완전히 깨끗
  · pv2(9.6초): 하단 'Gadgets World' 워터마크 있음 — **전부 깨끗하진 않다**
→ 깨끗한 건 자막제거(VMake) 비용이 **0원**이 된다. 지금 크레딧 소진으로 고객 신고까지
  났던 그 비용을 통째로 아낄 수 있다.

## 어떻게 긁나 (실측으로 확정)
★검색 페이지 HTML엔 핀이 **0개**다(껍데기). `__PWS_DATA__`에도 설정값만 82KB.
  콘텐츠는 **`BaseSearchResource/get` 응답**에 있다 — 이걸 가로채면 나온다.
★**로그인이 필요 없다**(익명 브라우저로 핀 38개·영상 3개 확보).
★영상은 `curl`로 직접 받힌다(yt-dlp도 불필요, Referer만 있으면 200).

## 사장님 결정 (2026-08-28)
  ① 워터마크 있는 것도 **다 담고** 눈으로 고른다(자동 필터 안 함)
  ② 랭킹에 핀터레스트 탭 신설 — **관리자만** 보이게(비공개)
  ③ 키워드는 **영어 먼저**
"""
import json


def test_모듈이_있다():
    from shopping_shorts import pinterest_crawl
    assert hasattr(pinterest_crawl, "search_videos")


def test_응답에서_영상핀만_뽑는다():
    """★핀터레스트 응답은 이미지 핀·광고가 섞여 온다. videos.video_list가 있는 것만 영상이다."""
    from shopping_shorts.pinterest_crawl import parse_pins
    body = {"resource_response": {"data": {"results": [
        {"id": "111", "grid_title": "이미지핀"},                       # 영상 아님
        {"id": "222", "grid_title": "영상핀",
         "videos": {"duration": 9000, "video_list": {
             "V_720P": {"url": "https://v1.pinimg.com/a.mp4", "width": 720, "height": 1280}}}},
    ]}}}
    out = parse_pins(body)
    assert len(out) == 1, "영상 핀만 뽑아야 한다"
    assert out[0]["pin_id"] == "222"
    assert out[0]["video_url"].endswith(".mp4")
    assert out[0]["duration"] == 9.0, "ms→초 변환이 안 됐다"


def test_가장_큰_화질을_고른다():
    """여러 화질이 오면 제일 큰 것 — 우리 렌더가 세로 고화질을 쓴다."""
    from shopping_shorts.pinterest_crawl import parse_pins
    body = {"x": [{"id": "1", "videos": {"duration": 5000, "video_list": {
        "V_480P": {"url": "https://v1.pinimg.com/s.mp4", "width": 480, "height": 854},
        "V_720P": {"url": "https://v1.pinimg.com/b.mp4", "width": 720, "height": 1280}}}}]}
    out = parse_pins(body)
    assert out[0]["width"] == 720 and out[0]["video_url"].endswith("b.mp4")


def test_구조가_달라도_재귀로_찾는다():
    """★응답 구조는 플랫폼 사정으로 바뀐다(인스타 통로가 1~2달마다 폐지된 전례).
    고정 경로로 파면 그때 통째로 0건이 된다 — 재귀로 훑는다."""
    from shopping_shorts.pinterest_crawl import parse_pins
    deep = {"a": {"b": [{"c": {"id": "9", "videos": {"duration": 3000, "video_list": {
        "V": {"url": "https://v1.pinimg.com/d.mp4", "width": 640, "height": 1136}}}}}]}}
    assert len(parse_pins(deep)) == 1


def test_빈_응답도_안_터진다():
    from shopping_shorts.pinterest_crawl import parse_pins
    assert parse_pins({}) == []
    assert parse_pins(None) == []
    assert parse_pins({"resource_response": {"data": None}}) == []


def test_중복_핀은_한_번만():
    from shopping_shorts.pinterest_crawl import parse_pins
    v = {"duration": 4000, "video_list": {"V": {"url": "https://v1.pinimg.com/x.mp4",
                                                "width": 720, "height": 1280}}}
    body = {"r": [{"id": "5", "videos": v}, {"id": "5", "videos": v}]}
    assert len(parse_pins(body)) == 1


def test_영어_키워드가_기본이다():
    """사장님 확정: 영어 먼저(핀터레스트는 영어권이 압도적)."""
    from shopping_shorts import pinterest_crawl
    kws = pinterest_crawl.DEFAULT_KEYWORDS
    assert kws, "기본 키워드가 없다"
    for k in kws:
        assert k.isascii(), f"영어가 아닌 키워드: {k}"


def test_워터마크를_자동으로_거르지_않는다():
    """★사장님 결정 ①: 다 담고 눈으로 고른다.
    자동 필터를 넣으면 '왜 안 담기지'가 되고, 판정 근거도 없다(화면을 봐야 안다)."""
    from shopping_shorts import pinterest_crawl
    src = __import__("inspect").getsource(pinterest_crawl)
    assert "watermark_filter" not in src


# ── 화면 ────────────────────────────────────────────────────────────────
def _index_html():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
    return p.read_text(encoding="utf-8")


def test_랭킹에_핀터레스트_탭이_있다():
    src = _index_html()
    assert 'data-platform="pinterest"' in src, "플랫폼 탭이 없다"


def test_탭은_관리자만_보인다():
    """★사장님 결정 ②: 비공개. 고객 화면엔 아예 안 보여야 한다.
    기존 관리자 전용 방식(body.is-admin CSS)을 그대로 쓴다 — 두 벌로 만들지 않는다."""
    src = _index_html()
    i = src.index('data-platform="pinterest"')
    tab = src[max(0, i - 300):i + 200]
    assert "admin-only" in tab or "is-admin" in tab, \
        "관리자 전용 표시가 없다 — 고객에게 보인다"


def test_썸네일_영상_호스트가_허용목록에_있다():
    """★없으면 카드가 통째로 **검게** 뜬다(실측). 같은 사고가 xhscdn·douyinpic·gstatic로
    이미 3번 반복됐다 — 메모리 `썸네일화이트리스트_누락`."""
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    src = p.read_text(encoding="utf-8")
    i = src.index("_ALLOWED_THUMB_HOSTS")
    j = src.index("_ALLOWED_VIDEO_HOSTS")
    assert "pinimg.com" in src[i:j], "썸네일 허용목록에 pinimg가 없다 — 카드가 검게 뜬다"
    assert "pinimg.com" in src[j:j + 900], "영상 허용목록에 pinimg가 없다 — 인라인 재생이 막힌다"


def test_핀마다_username이_달라야_한다():
    """★화면의 '채널당 2개' 상한(PER_CHANNEL_MAX)은 **username**으로 묶는다.
    전부 같은 값이면 11건 중 2건만 보인다(실측으로 겪었다).
    핀터레스트 검색 응답엔 게시자가 아예 없으므로(키: id·images·videos뿐)
    지어내지 않고 검색어+핀id로 갈라 준다."""
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    src = p.read_text(encoding="utf-8")
    i = src.index('"platform": "pinterest"')
    blk = src[i:i + 600]
    assert '"username": (' in blk or 'pin_id' in blk, "username이 핀마다 갈리지 않는다"


def test_서버에_수집_엔드포인트가_있고_관리자_전용():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    src = p.read_text(encoding="utf-8")
    i = src.index('/api/pinterest/collect')
    fn = src[i:i + 800]
    assert "_require_admin" in fn, "관리자 권한 검사가 없다"
