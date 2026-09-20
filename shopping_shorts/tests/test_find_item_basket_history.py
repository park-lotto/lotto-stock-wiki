# -*- coding: utf-8 -*-
"""shortcode로 항목 찾기 — **담기 바구니·히스토리·아카이브**까지 본다 (2026-09-16).

★실사고(사장님 제보, 화면 캡처): 레퍼런스 카드에서 「📝 대본 분석해서 정확히 찾기」를
  누르면 `⚠️ 대본 분석 실패 — 해당 항목 없음 — 재수집 필요`.

  2026-09-06에 같은 증상을 한 번 고쳤는데(유튜브 스냅샷 추가, test_find_item_all_platforms)
  **서랍이 아직 두 개 더 빠져 있었다.** `_find_collected_item`은 `last_run` 2종만 본다:

      last_run 테이블(인스타) + settings['last_run::<platform>'] 7종

  그런데 화면이 카드를 꺼내는 곳은 `GET /api/reference`(app.py)의 **네 갈래**다:

      archive=1  → channel_archive   (역대 히트작)      ← 안 봤다
      days>0     → reel_history      (이번 주/달)       ← 안 봤다
      인스타 기본 → last_run                             ← 봤다
      그 외      → last_run::<platform>                  ← 봤다

  게다가 렌즈·담기로 들어온 카드(`lens_youtube_…`·`grab_instagram_…`)는 **어느
  스냅샷에도 원리적으로 없다** — mix_basket에만 있고 그 코드는 우리가 지어낸 것이라
  수집이 담을 수가 없다(store.shortcodes_for_url 주석의 그 사정과 같은 뿌리).

라이브 실측 (2026-09-16, 서버 3.35.251.172 reference.db 직접 조회):

    _find_collected_item(store, 'lens_youtube_74oxbh')         -> None
    _find_collected_item(store, 'lens_instagram_f62xyh')       -> None
    _find_collected_item(store, 'grab_youtube_dc4c1ba1bad0')   -> None
    _find_collected_item(store, 'grab_instagram_d7b2e4c9bbad') -> None

    mix_basket 8,710건 중 lens_/grab_ = 7,374건 (전부 url 보유)
    platform_snapshots 유튜브 55,346건 중 last_run::youtube에 없는 것 = 45,143건

  사장님이 누른 그 카드(Godox C100 투명 뷰파인더)도 mix_basket의 lens_/grab_ 무리였다.

0순위-B: 서랍을 늘릴 때 호출부마다 따로 적으면 또 어긋난다 → `_find_collected_item`
  **한 곳**만 고친다. 그러면 /api/extract_script · /api/wiki/save · /api/find/analyze
  세 곳이 같이 살아난다.
"""
import pytest

from shopping_shorts.app import _find_collected_item


class _Store:
    """_find_collected_item이 부르는 것만 흉내내는 최소 스토어.

    ★일부러 **기본값을 전부 빈 값**으로 둔다 — 테스트가 채운 서랍에서만 찾혀야
      "그 서랍을 실제로 봤다"가 증명된다.
    """

    def __init__(self, insta=None, platforms=None, basket=None,
                 reel=None, archive=None):
        self._insta = insta or []
        self._platforms = platforms or {}
        self._basket = basket or []
        self._reel = reel or {}
        self._archive = archive or {}

    def load_last_run(self):
        return list(self._insta), "2026-09-15T00:16:03+00:00"

    def load_last_run_platform(self, platform):
        return list(self._platforms.get(platform, [])), "2026-09-15T04:42:28+00:00"

    def basket_item_any_customer(self, shortcode):
        return next((dict(i) for i in self._basket
                     if i.get("shortcode") == shortcode), None)

    def history_item(self, shortcode):
        r = self._reel.get(shortcode)
        return dict(r) if r else None

    def archive_item(self, shortcode):
        r = self._archive.get(shortcode)
        return dict(r) if r else None


# ── ① 담기·렌즈 카드 (사장님이 실제로 밟은 것) ────────────────────────────

def test_렌즈카드를_찾는다_이게_이번_버그():
    """★핵심. lens_* 코드는 어느 수집 스냅샷에도 없다 — 바구니에만 있다."""
    store = _Store(basket=[{"shortcode": "lens_youtube_74oxbh",
                            "url": "https://www.youtube.com/shorts/2hmDBqk3Dn4",
                            "name": "이게 카메라라고? 투명 뷰파인더의 정체"}])
    item = _find_collected_item(store, "lens_youtube_74oxbh")
    assert item is not None, "바구니를 안 보면 렌즈 카드는 영원히 404다"
    assert item["url"] == "https://www.youtube.com/shorts/2hmDBqk3Dn4"


def test_담기카드를_찾는다():
    store = _Store(basket=[{"shortcode": "grab_instagram_d7b2e4c9bbad",
                            "url": "https://www.instagram.com/reel/DaRg1rUo2nY/"}])
    assert _find_collected_item(store, "grab_instagram_d7b2e4c9bbad") is not None


@pytest.mark.parametrize("code,expected", [
    ("lens_youtube_74oxbh", "youtube"),
    ("grab_instagram_d7b2e4c9bbad", "instagram"),
    ("grab_tiktok_22c3ecbfeff6", "tiktok"),
    ("lens_douyin_abc123", "douyin"),
    ("grab_xiaohongshu_ff00", "xiaohongshu"),
])
def test_접두사로_플랫폼이_채워진다(code, expected):
    """★mix_basket엔 platform 컬럼이 없다(store.py mix_basket_list 참고).

    그런데 `_download_item_video`는 platform을 보고 인스타 릴스 주소를 조립할지
    정한다(2026-09-06에 넣은 가드). platform이 비면 기본값 'instagram'으로 떨어져
    **유튜브 항목에 instagram.com/reel/lens_youtube_74oxbh/ 라는 없는 주소**를
    받으러 간다 — 실패 사유가 "인스타 다운로드 실패"로 뭉개져 추적이 막힌다.

    여기선 url을 못 알아보는 주소로 두어 **접두사 폴백만** 시험한다.
    """
    store = _Store(basket=[{"shortcode": code, "url": "https://example.com/x"}])
    assert _find_collected_item(store, code)["platform"] == expected


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=ylKFpMNzDbU", "youtube"),
    ("https://youtu.be/ylKFpMNzDbU", "youtube"),
    ("https://www.instagram.com/reel/DaRg1rUo2nY/", "instagram"),
    ("https://www.tiktok.com/@a/video/7675547099844316447", "tiktok"),
    ("https://m.naver.com/shorts/abc", "naverclip"),
])
def test_접두사가_없어도_url로_플랫폼을_안다(url, expected):
    """★라이브에서 잡은 구멍(2026-09-16): 담긴 항목이라고 전부 `lens_`/`grab_`가
      붙어 있지는 않다.

      실측 — 담긴 8,710건 중 접두사 없는 것 1,336건, 그중 **인스타가 아닌 것 213건**
      (youtube 209 · naver 4). 접두사만 보면 저 213건이 플랫폼 없이 나가
      인스타로 오인된다. 실제 사례가 `ylKFpMNzDbU`(바구니의 유튜브 영상)였다.
      url은 접두사가 있든 없든 항상 진실을 말한다 → url이 1순위.
    """
    store = _Store(basket=[{"shortcode": "PLAIN123", "url": url}])
    assert _find_collected_item(store, "PLAIN123")["platform"] == expected


def test_url이_접두사를_이긴다():
    """둘이 어긋나면 url을 믿는다 — 접두사는 지어낸 이름이고 url은 실물이다."""
    store = _Store(basket=[{"shortcode": "lens_instagram_zzz",
                            "url": "https://www.youtube.com/watch?v=ABC"}])
    assert _find_collected_item(store, "lens_instagram_zzz")["platform"] == "youtube"


def test_둘_다_모르면_플랫폼을_지어내지_않는다():
    """모르는 건 모른다고 둔다 — 틀린 플랫폼은 없는 주소를 받으러 가게 만든다."""
    store = _Store(basket=[{"shortcode": "AbCdEf123", "url": "https://example.com/y"}])
    item = _find_collected_item(store, "AbCdEf123")
    assert not item.get("platform"), "알 수 없는 항목에 플랫폼을 붙이면 안 된다"


# ── ② 역대 히트작 / 이번 주·달 카드 ───────────────────────────────────────

def test_이번주달_카드를_찾는다_reel_history():
    """days>0 갈래(hits_since=reel_history)로 뜬 카드. 스냅샷엔 없을 수 있다."""
    store = _Store(reel={"RH123": {"url": "https://www.instagram.com/reel/RH123/",
                                   "name": "채널", "thumb": "t.jpg",
                                   "comments": 900, "views": 30000,
                                   "platform": "instagram"}})
    item = _find_collected_item(store, "RH123")
    assert item is not None, "reel_history를 안 보면 '이번 주/달' 카드가 전부 404다"
    assert item["url"] == "https://www.instagram.com/reel/RH123/"


def test_히스토리의_플랫폼을_덮어쓰지_않는다():
    """★reel_history엔 platform 컬럼이 있다(유튜브 행도 있다).

    여기를 'instagram'으로 못박으면 유튜브 항목이 인스타 릴스 주소로 조립돼
    없는 주소를 받으러 간다 — 2026-09-06 가드가 막으려던 바로 그 사고다.
    """
    store = _Store(reel={"YT9": {"url": "https://www.youtube.com/watch?v=YT9",
                                 "platform": "youtube"}})
    assert _find_collected_item(store, "YT9")["platform"] == "youtube"


def test_역대히트작_카드를_찾는다_channel_archive():
    """archive=1 갈래(archive_hits=channel_archive)로 뜬 카드."""
    store = _Store(archive={"AR456": {"url": "https://www.instagram.com/p/AR456/",
                                      "thumbnail": "a.jpg", "views": 900000}})
    item = _find_collected_item(store, "AR456")
    assert item is not None, "channel_archive를 안 보면 '역대 히트작'이 전부 404다"


def test_아카이브항목은_인스타로_친다():
    """channel_archive엔 platform 컬럼이 없다(store.py CREATE TABLE) — 인스타 전용
    테이블이라 인스타로 친다. 비워두면 _download_item_video 기본값과 같지만,
    **명시해야** 나중에 이 테이블에 다른 플랫폼이 섞일 때 여기서 걸린다."""
    store = _Store(archive={"AR456": {"url": "https://www.instagram.com/p/AR456/"}})
    assert _find_collected_item(store, "AR456")["platform"] == "instagram"


# ── ③ 순서·회귀 ───────────────────────────────────────────────────────────

def test_스냅샷이_바구니보다_우선이다():
    """종전에 찾히던 것은 종전 그대로 찾혀야 한다 — 회귀 0(0순위-B).

    수집 스냅샷 항목이 더 풍부하다(카테고리·비전태그·조회수 등 카드 필드 일습).
    """
    store = _Store(platforms={"youtube": [{"shortcode": "SAME", "which": "snapshot"}]},
                   basket=[{"shortcode": "SAME", "which": "basket"}])
    assert _find_collected_item(store, "SAME")["which"] == "snapshot"


def test_바구니가_히스토리보다_우선이다():
    """바구니엔 사용자가 담을 때 확보한 video_url·caption이 있다(더 쓸모 있다)."""
    store = _Store(basket=[{"shortcode": "SAME", "which": "basket"}],
                   reel={"SAME": {"url": "u", "which": "reel"}})
    assert _find_collected_item(store, "SAME")["which"] == "basket"


def test_어디에도_없으면_None():
    """없는 건 없다고 해야 404 안내가 정상 동작한다."""
    store = _Store(insta=[{"shortcode": "AAA"}], basket=[{"shortcode": "BBB"}],
                   reel={"CCC": {"url": "u"}}, archive={"DDD": {"url": "u"}})
    assert _find_collected_item(store, "ZZZ") is None


@pytest.mark.parametrize("broken", ["basket_item_any_customer",
                                    "history_item", "archive_item"])
def test_새서랍이_깨져도_안_터진다(broken):
    """새 서랍 하나가 고장나도 나머지를 계속 본다 — 조용한 전멸 금지.

    ★유튜브 항목을 스냅샷에서 찾는 경로는 새 서랍보다 **앞**이라, 이 테스트는
      '깨진 서랍을 만나도 예외가 밖으로 안 샌다'를 본다.
    """
    store = _Store(basket=[{"shortcode": "LAST", "url": "u"}])
    setattr(store, broken, lambda *a, **k: (_ for _ in ()).throw(RuntimeError("손상")))
    # 깨진 것이 바구니면 None, 아니면 바구니에서 찾힌다 — 어느 쪽이든 **안 터진다**.
    _find_collected_item(store, "LAST")


def test_스토어에_새_메서드가_없어도_안_터진다():
    """옛 Store(메서드 없음)와 섞여도 죽지 않는다 — 배포 중 버전 차이 대비."""

    class _Old:
        def load_last_run(self):
            return [{"shortcode": "AAA"}], None

        def load_last_run_platform(self, platform):
            return [], None

    assert _find_collected_item(_Old(), "AAA") is not None
    assert _find_collected_item(_Old(), "ZZZ") is None


def test_shortcode가_비면_None():
    store = _Store(basket=[{"shortcode": "AAA"}])
    assert _find_collected_item(store, "") is None
    assert _find_collected_item(store, None) is None
