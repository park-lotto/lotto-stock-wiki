"""⭐ 레퍼런스 등록 — 영상 1건 + 채널을 한 번에(2026-08-18 사장님 요청).

사장님: "인스타 보다가 좋은 영상을 발견하면 바로 레퍼런스에 반영해서 정렬을 해줄 수 있나?
영상등록 + 채널등록이 되는 걸로."

종전 두 버튼으로는 안 됐다:
  · 📥 담기      → 내 즐겨찾기로만 간다(랭킹엔 안 뜬다)
  · 📌 채널수집  → 다음 수집(09/15/21시)까지 기다려야 그 영상이 잡힌다

여기서 못박는 것:
  ① 항목을 손으로 짓지 않는다 — 수집이 쓰는 build_items를 그대로 태운다.
     손으로 만들면 속도·밀도·가속이 수집분과 달라져 한 화면에 두 잣대가 섞인다(0순위-B).
  ② 오래된 영상도 등록된다(48h 창은 자동수집용이지, 사장님이 고른 영상에 쓸 자가 아니다).
  ③ 같은 영상을 두 번 넣어도 스냅샷에 중복으로 쌓이지 않는다.
  ④ 영상 편입이 실패해도 채널 등록은 살린다(반대도 마찬가지).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from shopping_shorts import app as ap
from shopping_shorts.store import Store


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "t.db")
    Store(path)
    return path


def _meta(hours_ago=3, **kw):
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).timestamp()
    out = {"ts": int(ts), "title": "자석 네일펜", "thumbnail": "t.jpg", "channel": "chaehome",
           "views": 569324, "likes": 4200, "comments": 7217, "followers": 342545,
           "duration": 29}
    out.update(kw)
    return out


def _adopt(db_path, url, meta):
    store = Store(db_path)
    return ap._adopt_into_ranking(store, ap._grab_platform(url), url, meta)


def test_영상이_지금_랭킹에_들어간다(db):
    item = _adopt(db, "https://www.instagram.com/reel/ABC123/", _meta())
    assert item and item["comments"] == 7217
    items, _at = Store(db).load_last_run()
    assert [i["shortcode"] for i in items] == ["ABC123"], "스냅샷 맨 앞에 들어가야 한다"
    assert items[0].get("manual") is True, "직접 등록임을 화면이 구별할 수 있어야 한다"


def test_오래된_영상도_등록된다(db):
    """자동수집은 48시간만 보지만, 사장님이 고른 영상은 그 창으로 자르면 안 된다."""
    item = _adopt(db, "https://www.instagram.com/reel/OLD1/", _meta(hours_ago=24 * 30))
    assert item is not None, "한 달 전 영상도 등록돼야 한다"


def test_같은_영상을_두_번_넣어도_한_줄이다(db):
    _adopt(db, "https://www.instagram.com/reel/ABC123/", _meta())
    _adopt(db, "https://www.instagram.com/reel/ABC123/", _meta(comments=9000))
    items, _at = Store(db).load_last_run()
    assert len(items) == 1 and items[0]["comments"] == 9000, "덮어쓰되 중복은 안 쌓는다"


def test_기존_수집분을_지우지_않는다(db):
    store = Store(db)
    store.save_last_run([{"shortcode": "OLD", "comments": 1}], "2026-08-18T00:00:00+00:00")
    _adopt(db, "https://www.instagram.com/reel/NEW1/", _meta())
    items, _at = store.load_last_run()
    assert [i["shortcode"] for i in items] == ["NEW1", "OLD"]


def test_시각을_못_읽으면_영상은_건너뛴다(db):
    """지표를 못 만들면 랭킹에 못 넣는다 — 조용히 빈 카드를 만드느니 안 넣는 게 낫다."""
    assert _adopt(db, "https://www.instagram.com/reel/ABC/", _meta(ts=None)) is None


def test_쓰레드_유튜브도_각_플랫폼_스냅샷에_들어간다(db):
    _adopt(db, "https://www.threads.com/@shop/post/TH1", _meta())
    _adopt(db, "https://www.youtube.com/shorts/_6v_D3MktcI", _meta())  # 실제 길이(11자)
    st = Store(db)
    assert [i["shortcode"] for i in st.load_last_run_platform("threads")[0]] == ["TH1"]
    assert [i["shortcode"] for i in st.load_last_run_platform("youtube")[0]] == ["_6v_D3MktcI"]
    assert st.load_last_run()[0] == [], "인스타 스냅샷은 건드리지 않는다"


def test_지원안하는_주소는_거절한다(db):
    with patch.object(ap, "DB_PATH", db), patch.object(ap, "_require_admin", lambda r: None):
        html = ap.api_reference_adopt(request=None, url="https://example.com/x")
    assert "지원하지 않는" in html.body.decode("utf-8")


def test_영상편입이_실패해도_채널등록은_한다(db):
    """둘을 한 트랜잭션으로 묶으면 하나가 깨질 때 둘 다 날아간다."""
    called = {}
    with patch.object(ap, "DB_PATH", db), \
         patch.object(ap, "_require_admin", lambda r: None), \
         patch.object(ap, "probe_grab_meta", lambda u, **k: _meta()), \
         patch.object(ap, "_adopt_into_ranking",
                      lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))), \
         patch.object(ap, "api_discover_add_by_url",
                      lambda req, url="", username="": called.setdefault("ch", url) or
                      ap.HTMLResponse("✅ 채널 등록 완료")):
        html = ap.api_reference_adopt(request=None, url="https://www.instagram.com/reel/ABC/")
    assert called.get("ch"), "영상이 깨져도 채널 등록은 시도해야 한다"
    assert "채널만 등록" in html.body.decode("utf-8")


# ── A안: 화면에 떠 있는 숫자를 같이 보낸다(2026-08-18) ────────────────────────────
# 서버는 인스타를 로그인 없이 읽어 조회수·팔로워가 0으로 왔다(실측: 채이홈 항목
# views 0 / followers 0 / 제목 "Video by chae2home"). 그러면 조회수당댓글·팔로워당댓글이
# 계산되지 않아 정렬에서 불리해진다. 사장님 화면엔 그 숫자가 이미 떠 있으니 함께 보낸다.
def _adopt_api(db_path, url, meta, **q):
    with patch.object(ap, "DB_PATH", db_path), \
         patch.object(ap, "_require_admin", lambda r: None), \
         patch.object(ap, "probe_grab_meta", lambda u, **k: dict(meta)), \
         patch.object(ap, "api_discover_add_by_url",
                      lambda req, url="", username="": ap.HTMLResponse("✅ 채널 등록 완료")):
        return ap.api_reference_adopt(request=None, url=url, **q)


def test_화면에서_보낸_숫자로_빈칸을_채운다(db):
    _adopt_api(db, "https://www.instagram.com/reel/ABC123/",
               _meta(views=0, followers=0, likes=0),
               views=569324, followers=342545, likes=4200)
    items, _at = Store(db).load_last_run()
    got = items[0]
    assert got["views"] == 569324 and got["followers"] == 342545, \
        "0으로 비어 있던 칸은 화면 값으로 채워야 정렬 지표가 산다"


def test_서버가_제대로_읽은_값은_덮지_않는다(db):
    """화면 글자 파싱은 근사치다 — 더 정확한 값을 밀어내면 안 된다."""
    _adopt_api(db, "https://www.instagram.com/reel/ABC123/",
               _meta(views=100000), views=7)
    items, _at = Store(db).load_last_run()
    assert items[0]["views"] == 100000


# ─────────────────────────────────────────────────────────────────────────────
# 2026-08-19 — "등록해도 기존 영상들이랑 동일한 포맷으로 저장되고 보이게 해줘"
#
# 실측한 증상(라이브 DB, shortcode DcIrfnOzHre):
#     views 0 / followers 0 / grade None / caption 'Video by chae2home'
# 원인은 adopt가 probe_grab_meta(yt-dlp)만 쓴 것 — yt-dlp는 로그인 없이 인스타를 읽어
# 조회수·팔로워·캡션을 못 가져온다. 화면(index.html)은 값이 있을 때만 줄을 그리므로
# (`${i.views? ...}`) 그 카드만 조회수·조회수당댓글·팔로워당댓글 줄이 통째로 빠졌다.
#
# 못박는 것: 인스타는 **정규 수집이 쓰는 fetch_reels**를 그대로 태워 값을 채운다(0순위-B).
# ─────────────────────────────────────────────────────────────────────────────

def _reel(code="ABC123", **kw):
    """instagram_playwright.fetch_reels가 돌려주는 모양(parse_reel_node 계약)."""
    ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    out = {"shortcode": code, "url": f"https://www.instagram.com/reel/{code}/",
           "timestamp": ts, "caption": "자석 네일펜 진짜 신기함",
           "commentsCount": 9581, "likesCount": 4200, "videoViewCount": 569324,
           "displayUrl": "real.jpg", "videoUrl": "", "duration": 29.0,
           "ownerUsername": "chae2home", "ownerFullName": "채이홈",
           "ownerFollowers": 342545}
    out.update(kw)
    return out


def test_인스타는_수집경로로_지표를_채운다(db):
    """yt-dlp가 0을 줘도 fetch_reels가 준 실제 값이 들어가야 한다.

    이게 이 수정의 핵심 — 조회수·팔로워가 0이면 화면이 그 줄을 아예 안 그린다.
    """
    ytdlp_blank = {"ts": int((datetime.now(timezone.utc) - timedelta(hours=3)).timestamp()),
                   "title": "Video by chae2home",      # yt-dlp 기본 문구
                   "thumbnail": "ytdlp.jpg", "channel": "chae2home",
                   "views": 0, "likes": 3, "comments": 9581, "followers": 0}
    with patch("shopping_shorts.instagram_playwright.fetch_reels", return_value=[_reel()]):
        meta, hit = ap._enrich_instagram_meta(
            "https://www.instagram.com/reels/ABC123/", dict(ytdlp_blank))
    assert hit is not None, "프로필에서 그 영상을 찾았어야 한다"
    assert meta["views"] == 569324, "조회수가 0으로 남으면 화면에 조회수 줄이 안 그려진다"
    assert meta["followers"] == 342545, "팔로워 0이면 팔로워당댓글 줄이 안 그려진다"
    assert meta["title"] == "자석 네일펜 진짜 신기함", "'Video by ...' 기본문구를 실캡션이 밀어내야 한다"
    assert meta["thumbnail"] == "real.jpg"
    assert meta["channel"] == "채이홈", "카드에 뜨는 표시명은 한글 이름"
    assert meta["_ig_username"] == "chae2home", "계정명은 따로 실어야 채널검색이 된다"


def test_수집값이_yt_dlp의_0을_이긴다(db):
    """0은 '값이 없다'는 뜻 — 진짜 값을 덮으면 안 된다(0순위-B: 정본은 한 곳)."""
    with patch("shopping_shorts.instagram_playwright.fetch_reels", return_value=[_reel()]):
        meta, _ = ap._enrich_instagram_meta(
            "https://www.instagram.com/reels/ABC123/",
            {"views": 0, "followers": 0, "channel": "chae2home"})
    assert meta["views"] == 569324 and meta["followers"] == 342545


def test_보강실패해도_등록은_살린다(db):
    """스크레이퍼가 죽어도(계정 차단·세션만료) 등록 자체는 종전대로 돌아야 한다."""
    base = {"views": 0, "channel": "chae2home", "comments": 5}
    with patch("shopping_shorts.instagram_playwright.fetch_reels",
               side_effect=RuntimeError("login wall")):
        meta, hit = ap._enrich_instagram_meta("https://www.instagram.com/reels/ABC123/", dict(base))
    assert hit is None and meta["views"] == 0, "실패하면 meta를 그대로 둔다"


def test_다른영상은_가져오지_않는다(db):
    """프로필엔 릴스가 여러 개 — shortcode가 맞는 것만 써야 한다.

    안 그러면 등록한 영상에 옆 영상의 조회수가 붙는다(메모리: 렌즈썸네일 구글짝지음과 같은 함정).
    """
    others = [_reel(code="ZZZ999", videoViewCount=111), _reel(code="YYY888", videoViewCount=222)]
    with patch("shopping_shorts.instagram_playwright.fetch_reels", return_value=others):
        meta, hit = ap._enrich_instagram_meta(
            "https://www.instagram.com/reels/ABC123/", {"views": 0, "channel": "chae2home"})
    assert hit is None, "그 영상이 없으면 아무것도 안 가져와야 한다"
    assert meta["views"] == 0, "남의 영상 조회수를 붙이면 안 된다"


def test_계정명을_주소에서_뽑는다():
    """프로필 경유 URL이면 주소만으로 계정을 안다 — yt-dlp가 실패해도 열 수 있다."""
    assert ap._ig_username_from_url("https://www.instagram.com/chae2home/reel/ABC/") == "chae2home"
    assert ap._ig_username_from_url("https://www.instagram.com/reel/ABC/") == "", "예약어는 계정이 아니다"
    assert ap._ig_username_from_url("https://www.instagram.com/reels/ABC/") == ""


def test_등급이_스냅샷_전체_기준으로_매겨진다(db):
    """grade가 None이면 카드 채널명 옆이 빈 채로 남는다(실측: 채이홈 항목).

    ★1건만 놓고 정규화하면 자기가 최대라 무조건 최고등급이 된다 —
      합친 뒤에 한 번 매겨야 수집분과 같은 잣대가 된다.
    """
    store = Store(db)
    # 먼저 수집분처럼 '아주 뜨거운' 항목을 스냅샷에 넣어둔다.
    hot = ap._adopt_into_ranking(store, "instagram",
                                 "https://www.instagram.com/reel/HOT1/",
                                 _meta(comments=99999, views=100000))
    assert hot is not None
    # 그 다음 미지근한 항목을 등록한다.
    mild = ap._adopt_into_ranking(store, "instagram",
                                  "https://www.instagram.com/reel/MILD1/",
                                  _meta(comments=1, views=100000))
    assert mild is not None
    items, _at = Store(db).load_last_run()
    by = {i["shortcode"]: i for i in items}
    assert by["HOT1"].get("grade"), "등급이 비면 카드에 등급 자리가 빈 채로 남는다"
    assert by["MILD1"].get("grade"), "등급이 비면 카드에 등급 자리가 빈 채로 남는다"
    assert by["HOT1"]["score"] > by["MILD1"]["score"], \
        "합쳐서 매겨야 뜨거운 쪽이 더 높다(1건씩 매기면 둘 다 만점)"


def test_표시명과_계정명을_따로_담는다(db):
    """카드의 '이 채널 영상만 보기'는 username을 쓴다 — 표시명을 넣으면 0건이 된다."""
    item = ap._adopt_into_ranking(
        Store(db), "instagram", "https://www.instagram.com/reel/NAME1/",
        _meta(channel="채이홈", _ig_username="chae2home"))
    assert item["name"] == "채이홈" and item["username"] == "chae2home"


def test_길이가_바로_카드에_뜬다(db):
    """🎬 길이는 last_run이 아니라 reel_durations 캐시에서 붙는다(_attach_durations).

    등록할 때 값을 들고 있으면 그 캐시에 넣어둬야 등록 직후에도 길이가 뜬다 —
    안 넣으면 durfill 백필(최대 1시간에 1번)을 기다려야 한다.
    """
    store = Store(db)
    ap._adopt_into_ranking(store, "instagram",
                           "https://www.instagram.com/reel/DUR1/", _meta(duration=29))
    assert Store(db).duration_map(["DUR1"]).get("DUR1") == 29.0

    # 화면이 실제로 쓰는 결합 함수까지 태워서 확인한다(캐시에만 있고 안 붙으면 소용없다).
    items = [{"shortcode": "DUR1"}]
    ap._attach_durations(items, Store(db))
    assert items[0]["duration"] == 29.0, "카드에 🎬 길이가 뜨려면 여기서 붙어야 한다"


# ── 2026-08-19 (2차) 실사고: 표시명으로 프로필을 열어 reels=0 ──────────────────
# 라이브 로그 그대로:
#   [adopt] 인스타 보강: 프로필에서 그 영상을 못 찾음 who=채이홈 code=DcF2lTqzeiu reels=0
# 원인: /reels/CODE/ URL엔 계정명이 없어 meta['channel']로 폴백했는데, oEmbed의
# channel은 **표시명**('채이홈')이지 계정('chae2home')이 아니다. 계정명은 제목
# 'Video by chae2home'에 들어 있었다 — 그 문구를 '쓸모없는 기본값'으로만 보고
# 지나쳤던 게 실수였다.

def test_계정명은_제목에서_뽑는다():
    """channel은 표시명이라 프로필 주소에 쓰면 0건이 된다(실사고 재현)."""
    live = {"channel": "채이홈", "title": "Video by chae2home",
            "views": None, "followers": None, "comments": 1729}
    assert ap._ig_username_from_meta(live) == "chae2home"


def test_표시명을_계정으로_오인하지_않는다():
    """한글·공백이 섞이면 계정이 아니다 — 그걸로 프로필을 열면 reels=0."""
    assert ap._ig_username_from_meta({"title": "", "channel": "채이홈"}) == ""
    assert ap._ig_username_from_meta({"title": "", "channel": "채 이홈"}) == ""
    # 영문 계정이 channel에 그대로 온 경우는 종전대로 쓴다.
    assert ap._ig_username_from_meta({"title": "", "channel": "chae2home"}) == "chae2home"
    assert ap._ig_username_from_meta({"title": "", "channel": "@chae2home"}) == "chae2home"


def test_실캡션이면_계정으로_오인하지_않는다():
    """보강이 한 번 성공해 title이 실캡션으로 바뀐 뒤 다시 불려도 안전해야 한다."""
    assert ap._ig_username_from_meta({"title": "자석 네일펜 진짜 신기함",
                                      "channel": "채이홈"}) == ""


def test_reels_URL도_계정을_찾아_보강한다(db):
    """/reels/CODE/ 엔 계정이 없다 — 그래도 제목에서 찾아 프로필을 열어야 한다."""
    seen = {}

    def fake_fetch(usernames, *a, **k):
        seen["who"] = list(usernames)
        return [_reel(code="DcF2lTqzeiu")]

    ytdlp = {"channel": "채이홈", "title": "Video by chae2home",
             "views": 0, "followers": 0, "comments": 1729,
             "ts": int((datetime.now(timezone.utc) - timedelta(hours=3)).timestamp())}
    with patch("shopping_shorts.instagram_playwright.fetch_reels", side_effect=fake_fetch):
        meta, hit = ap._enrich_instagram_meta(
            "https://www.instagram.com/reels/DcF2lTqzeiu/", dict(ytdlp))
    assert seen["who"] == ["chae2home"], f"표시명으로 열면 0건이 된다(실사고): {seen}"
    assert hit is not None and meta["views"] == 569324 and meta["followers"] == 342545


def test_username에_한글표시명이_들어가지_않는다(db):
    """카드의 '이 채널 영상만 보기'는 username을 쓴다 — 표시명이 들어가면 0건."""
    ytdlp = {"channel": "채이홈", "title": "Video by chae2home",
             "views": 0, "followers": 0, "comments": 1729,
             "ts": int((datetime.now(timezone.utc) - timedelta(hours=3)).timestamp())}
    with patch("shopping_shorts.instagram_playwright.fetch_reels",
               return_value=[_reel(code="DcF2lTqzeiu")]):
        meta, _ = ap._enrich_instagram_meta(
            "https://www.instagram.com/reels/DcF2lTqzeiu/", dict(ytdlp))
    item = ap._adopt_into_ranking(Store(db), "instagram",
                                  "https://www.instagram.com/reels/DcF2lTqzeiu/", meta)
    assert item["username"] == "chae2home", "계정명 자리에 표시명이 들어갔다"
    assert item["name"] == "채이홈"
