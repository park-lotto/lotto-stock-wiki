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


def _collect_fn():
    """수집 엔드포인트 본문만 정확히 떠 온다.

    ★고정 길이(src[i:i+3500])로 자르면 **함수가 길어질 때 조용히 뒷부분을 놓친다**
    (실제로 병렬화 후 load_last_run_platform 검사가 가짜로 실패했다).
    다음 라우트 데코레이터까지를 본문으로 본다.
    """
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    src = p.read_text(encoding="utf-8")
    i = src.index('/api/pinterest/collect')
    j = src.find(chr(10) + "@app.", i + 10)
    return src[i:j if j > 0 else len(src)]


def _code_only(fn):
    """주석·독스트링을 뺀 **실행되는 코드**만 남긴다.

    ★주석에 'as_completed로 바꾸지 마라'라고 적었더니 그 글자를 테스트가 잡아
    가짜로 실패했다 — 금지어 검사는 반드시 코드에서만 해야 한다."""
    out = []
    for line in fn.splitlines():
        t = line.strip()
        if t.startswith("#"):
            continue
        out.append(line.split("  # ")[0])
    return chr(10).join(out)


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


def test_수집은_누적된다():
    """★사장님 지시(2026-08-28): "한번에 다해서 올리는게 아니라 10개씩 하고 올리고 그런식으로".

    익명 수집은 **검색어당 첫 묶음(10~27개)에서 잘린다**(실측: 스크롤 4→15회로 늘려도
    BaseSearchResource가 1회만 호출돼 5개 그대로). 그래서 키워드를 조금씩 여러 번 돌려
    쌓는 방식이 유일한 길인데, 덮어쓰기면 **앞서 모은 게 매번 사라진다**.
    → 기존 것과 합치고 pin_id로 중복 제거한다.
    """
    fn = _collect_fn()
    # 2026-08-29: 읽기~쓰기를 한 트랜잭션으로 묶으면서 병합이 store로 옮겨갔다
    # (동시 수집이 서로를 덮던 문제). 누적한다는 계약 자체는 그대로다.
    assert "merge_last_run_platform" in fn, "기존 수집분을 안 읽는다 — 매번 덮어쓴다"
    assert "reset" in fn, "비우기 수단이 없다 — 쌓이기만 하면 정리를 못 한다"


def test_서버에_수집_엔드포인트가_있고_관리자_전용():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    src = p.read_text(encoding="utf-8")
    i = src.index('/api/pinterest/collect')
    fn = src[i:i + 800]
    assert "_require_admin" in fn, "관리자 권한 검사가 없다"


# ── 병렬 수집 (2026-08-29) ──────────────────────────────────────────────
def test_수집이_병렬로_돈다():
    """★화면 버튼이 순차라 느렸다. 병목은 IP가 아니라 **브라우저 기동+고정 sleep**이다.

    실측(서버 8코어): 키워드마다 chromium.launch()를 새로 열고
    `for _ in range(scrolls): wait_for_timeout(1500)` + 끝에 2000ms
    = 키워드당 약 9.5초가 순수 대기. 12키워드 순차 70.1초 → 병렬 18.1초(결과 손실 0).

    ★프로세스풀이 아니라 **스레드풀**이다 — 웹서버(uvicorn) 안에서 fork하면
    소켓·시그널 핸들러가 상속돼 위험한데, 실측상 속도가 같아(스레드 12.8초 /
    프로세스 12.5초) 위험을 살 이유가 없다.
    """
    fn = _code_only(_collect_fn())
    assert "ThreadPoolExecutor" in fn, "순차 루프다 — 화면 버튼이 느리다"
    assert "ProcessPoolExecutor" not in fn, \
        "웹서버 안에서 fork하면 안 된다(스레드풀로 충분하다 — 실측 속도 동일)"


def test_병렬이어도_순서가_보존된다():
    """★결과 순서가 뒤섞이면 '방금 담은 게 위로' 규칙이 깨진다.
    executor.map은 순서를 보존한다 — as_completed로 바꾸지 마라."""
    fn = _code_only(_collect_fn())
    assert "as_completed" not in fn, "순서가 뒤섞인다 — map을 써라"


def test_키워드_하나가_죽어도_나머지는_산다():
    """★병렬에서 예외 격리가 없으면 키워드 하나가 통째로 수집을 죽인다.
    실측: 'car tool emergency kit'는 정상인데도 0개가 나온다(핀터레스트 사정).
    0개는 괜찮지만 **예외**는 나머지를 죽이면 안 된다."""
    fn = _collect_fn()
    j = fn.index("ThreadPoolExecutor")
    assert "except" in fn[max(0, j - 700):j + 700], "예외 격리가 없다"
# ── pin_video_info: 핀 1개 실조회(렌즈·다운로드 공용, 2026-08-29) ────────────
# 실측 근거: 익명 requests로 핀 상세 페이지가 200으로 열리고, 영상 핀에만
# JSON-LD VideoObject가 있다(영상 2/2 있음 / 이미지 4/4 없음).

_VIDEO_PIN_HTML = """<html><head>
<script type="application/ld+json">{"@type":"SocialMediaPosting","headline":"x"}</script>
<script type="application/ld+json">{"@type":"VideoObject","@context":"http://schema.org/",
 "name":"Stylish Gadgets","description":"desc here",
 "contentUrl":"https://v1.pinimg.com/videos/mc/720p/f2/72/46/aaa.mp4",
 "duration":"PT15S",
 "thumbnailUrl":"https://i.pinimg.com/videos/thumbnails/originals/f2/72/46/aaa.0000000.jpg"}</script>
</head><body></body></html>"""

_IMAGE_PIN_HTML = """<html><head>
<script type="application/ld+json">{"@type":"SocialMediaPosting","headline":"이미지 핀"}</script>
</head><body></body></html>"""


class _PageResp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def test_iso_duration_secs():
    from shopping_shorts import pinterest_crawl as pc
    assert pc.iso_duration_secs("PT15S") == 15.0
    assert pc.iso_duration_secs("PT1M2S") == 62.0
    assert pc.iso_duration_secs("PT1H2M3S") == 3723.0
    # 못 읽으면 None — 0으로 뭉개면 '0초 영상'이 돼 롱폼컷·숏폼 판정이 틀린다
    assert pc.iso_duration_secs("") is None
    assert pc.iso_duration_secs("nope") is None
    assert pc.iso_duration_secs(None) is None


def test_pin_video_info_영상핀은_dict(monkeypatch):
    import requests
    from shopping_shorts import pinterest_crawl as pc
    monkeypatch.setattr(requests, "get", lambda *a, **k: _PageResp(_VIDEO_PIN_HTML))
    info = pc.pin_video_info("https://www.pinterest.com/pin/123456/")
    assert info["video_url"].endswith("aaa.mp4")
    assert info["duration"] == 15.0
    assert info["title"] == "Stylish Gadgets"
    assert "thumbnails" in info["thumbnail"]


def test_pin_video_info_이미지핀은_None(monkeypatch):
    import requests
    from shopping_shorts import pinterest_crawl as pc
    monkeypatch.setattr(requests, "get", lambda *a, **k: _PageResp(_IMAGE_PIN_HTML))
    assert pc.pin_video_info("https://www.pinterest.com/pin/123456/") is None


def test_search_videos_tab이_기본크롤에_전달된다(monkeypatch):
    """tab="videos"(렌즈용 영상탭)가 실제 크롤 URL 선택까지 닿아야 한다.
    ⚠️ 주입 크롤러(_crawler) 계약은 3인자 그대로 — 기존 테스트·수집이 그 모양을 쓴다."""
    from shopping_shorts import pinterest_crawl as pc
    seen = {}

    def fake_crawl(keyword, scrolls, timeout_ms, tab="pins"):
        seen["tab"] = tab
        return []
    monkeypatch.setattr(pc, "_crawl", fake_crawl)
    pc.search_videos("camping table", tab="videos")
    assert seen["tab"] == "videos"
    pc.search_videos("camping table")           # 기본은 종전 그대로 pins
    assert seen["tab"] == "pins"
    # 주입 크롤러는 tab 없이 3인자로 불린다(하위호환)
    calls = []
    pc.search_videos("x", _crawler=lambda k, s, t: calls.append((k, s, t)) or [])
    assert len(calls) == 1


def test_pin_video_info_비200은_예외(monkeypatch):
    """판정불가는 예외로 갈라 준다 — None(이미지 확정)과 섞이면 렌즈가
    멀쩡한 영상 핀을 '이미지'로 잘라버린다(회수율 사고)."""
    import pytest
    import requests
    from shopping_shorts import pinterest_crawl as pc
    monkeypatch.setattr(requests, "get", lambda *a, **k: _PageResp("", status=503))
    with pytest.raises(Exception):
        pc.pin_video_info("https://www.pinterest.com/pin/123456/")


def test_핀_상세요청은_brotli를_광고하지_않는다():
    """★라이브 버그(2026-08-29 실측): 영상핀 8/8이 ContentDecodingError로 죽었다.

    서버에 brotli 1.2.0이 깔려 있어 requests가 `Accept-Encoding: br`을 자동으로
    광고하는데, urllib3 2.0.7과의 조합에서 핀터레스트 응답 디코딩이 깨진다:
      'Received response with content-encoding: br, but failed to decode it'
    → `Accept-Encoding: gzip, deflate`를 **명시**하면 같은 URL이 200으로 열린다(실측).

    ⚠️이 버그는 조용하지 않다 — pin_video_info의 계약상 예외는 '판정불가'라
    렌즈가 자르지 않는다. 그래서 **영상이 사라지진 않지만 보강이 100% 실패**한다.
    """
    from shopping_shorts import pinterest_crawl
    src = __import__("inspect").getsource(pinterest_crawl.pin_video_info)
    assert "Accept-Encoding" in src, \
        "br을 광고한다 — 서버에서 ContentDecodingError로 전부 죽는다"


def test_핀_상세는_HTML을_못_읽어도_조용히_None이_아니다():
    """★None(영상 아님 확정)과 예외(판정불가)를 뭉개면 렌즈가 멀쩡한 영상을 잘라낸다.
    HTTP 200이 아니면 예외여야 한다 — 기존 계약을 지킨다."""
    from shopping_shorts import pinterest_crawl
    src = __import__("inspect").getsource(pinterest_crawl.pin_video_info)
    assert "raise" in src, "비200을 None으로 뭉개면 안 된다"


def test_핀_상세는_주거용_프록시로_간다():
    """★진짜 원인은 brotli가 아니라 **서버 IP**였다(2026-08-29 실측, 표본 10개).

        직접  → None 10/10   (ld+json이 아예 안 내려온다)
        프록시 → dict 10/10   (VideoObject 정상)

    데이터센터 IP엔 핀터레스트가 SEO용 JSON-LD를 안 준다. 헤더를 아무리 사람처럼
    갖춰도 안 되고(브라우저 헤더 시도 실패), **IP만 바꾸면 된다**.

    ⚠️이걸 안 고치면 brotli만 고쳤을 때 **오히려 더 나빠진다**:
      수정 전 = 예외(판정불가 → 렌즈가 안 자름)
      brotli만 고침 = None(**영상 아님 확정 → 렌즈가 잘라낸다**)
    즉 멀쩡한 핀 영상이 통째로 사라진다.

    ★프록시 dict는 reddit_source._proxies()를 **재사용**한다(0순위-B: 같은 판단을
    두 번 적지 않는다). 없으면 None을 주므로 미설정 환경에서도 안 깨진다.
    """
    from shopping_shorts import pinterest_crawl
    src = __import__("inspect").getsource(pinterest_crawl.pin_video_info)
    assert "proxies" in src, "프록시를 안 태운다 — 데이터센터 IP는 JSON-LD를 못 받는다"
    assert "_proxies" in src, "프록시 dict를 새로 짜지 마라 — reddit_source._proxies() 재사용"


def test_동시_수집이_서로를_덮지_않는다():
    """★재현 확인(2026-08-29): 두 수집이 각 50개를 담았는데 **50개만 남았다**.

    엔드포인트가 load(기존) → 파이썬에서 병합 → save(전량) 순서라,
    두 수집이 겹치면 나중 save가 앞 save 결과를 통째로 덮는다.
    사장님이 두 PC에서 동시에 버튼을 누르면 한쪽이 조용히 사라진다
    (오류가 없어서 '덜 담겼네' 정도로만 보인다).

    → 읽기~쓰기를 **한 덩어리로 묶는다**. 같은 함정을 이미 포인트 차감에서 겪었고
      그때 결론도 같았다(메모리 `포인트차감_원자성`).
    """
    fn = _code_only(_collect_fn())
    assert "merge_last_run_platform" in fn, \
        "load→병합→save를 따로 하면 동시 수집이 서로를 덮는다"


def test_병합은_저장쪽에서_원자적으로_한다():
    """★락은 **저장을 담당하는 곳**에 있어야 한다 — 호출부마다 걸면 반드시 빠뜨린다
    (0순위-B: 같은 판단을 두 번 적지 않는다)."""
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "store.py"
    src = p.read_text(encoding="utf-8")
    assert "def merge_last_run_platform" in src, "저장쪽에 병합 함수가 없다"
    i = src.index("def merge_last_run_platform")
    blk = src[i:i + 1800]
    assert "BEGIN IMMEDIATE" in blk or "_conn()" in blk, "한 트랜잭션으로 안 묶인다"
