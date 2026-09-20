# -*- coding: utf-8 -*-
"""shortcode로 수집항목 찾기 — **모든 플랫폼 스냅샷**을 본다 (2026-09-06).

★실사고(사장님 제보): 유튜브 카드에서 「🎬 영상 보고 정확히」를 누르면 언제나
  "해당 항목 없음 — 재수집 필요"가 떴다. 영상이 없어서가 아니라 **엉뚱한 서랍을
  뒤졌기 때문**이다.

  - 랭킹 화면이 유튜브 카드를 꺼내는 곳: `load_last_run_platform("youtube")`
    (= settings['last_run::youtube'])                       ← app.py:852
  - 대본추출이 항목을 찾는 곳:          `load_last_run()`
    (= last_run 테이블 id=1, **인스타 전용**)                 ← app.py:2623

  유튜브 수집은 save_last_run을 아예 안 부른다(app.py:423-427) → 원리적으로
  last_run(id=1)엔 절대 없다.

라이브 실측(2026-09-06, 서버 3.35.251.172 reference.db 직접 조회):
  last_run(id=1)            = 134건 (전부 인스타)
  settings['last_run::youtube'] = 8,524건
  ★유튜브 8,524건 중 last_run(id=1)에도 있는 것 = **0건**
  사장님이 누른 그 카드: shortcode=7ONI6JjXvMw, platform=youtube (last_run엔 없음)

  대본캐시 보유율도 갈렸다: 인스타 25/134(19%) vs 유튜브 40/8,524(**0.5%**)

0순위-B: "항목 찾기"를 네 군데가 각자 적고 있었다(2623 대본추출 · 2955 위키저장 ·
3561 영상분석 · 그 밖). 같은 판단을 여러 번 적으면 반드시 어긋난다 → 함수 하나로
뽑아 전부 그것만 부르게 한다.
"""
import pytest

from shopping_shorts.app import _find_collected_item


class _FakeStore:
    """load_last_run / load_last_run_platform만 흉내내는 최소 스토어."""

    def __init__(self, insta=None, platforms=None):
        self._insta = insta or []
        self._platforms = platforms or {}

    def load_last_run(self):
        return list(self._insta), "2026-09-05T00:16:03+00:00"

    def load_last_run_platform(self, platform):
        return list(self._platforms.get(platform, [])), "2026-09-05T04:42:28+00:00"


def test_인스타항목은_종전대로_찾는다():
    """회귀 방지 — 고치기 전에도 되던 경로가 계속 돼야 한다."""
    store = _FakeStore(insta=[{"shortcode": "https://www.instagram.com/p/DcAAA111/"}])
    item = _find_collected_item(store, "https://www.instagram.com/p/DcAAA111/")
    assert item is not None
    assert item["shortcode"] == "https://www.instagram.com/p/DcAAA111/"


def test_인스타는_미디어코드로도_매칭된다():
    """추적파라미터 붙은 URL·reel 형식도 같은 항목으로(2026-07-09 오탐수정 유지)."""
    store = _FakeStore(insta=[{"shortcode": "https://www.instagram.com/p/DcAAA111/"}])
    item = _find_collected_item(store, "https://www.instagram.com/reel/DcAAA111/?igsh=xyz")
    assert item is not None, "미디어코드 매칭이 깨지면 인스타 쪽이 통째로 회귀한다"


def test_유튜브항목을_찾는다_이게_이번_버그():
    """★핵심. 유튜브 카드는 last_run(id=1)에 없고 플랫폼 스냅샷에만 있다.

    고치기 전에는 여기서 None이 나와 404 '해당 항목 없음'이 떴다.
    """
    store = _FakeStore(
        insta=[{"shortcode": "https://www.instagram.com/p/DcAAA111/"}],
        platforms={"youtube": [{"shortcode": "7ONI6JjXvMw",
                                "platform": "youtube",
                                "url": "https://www.youtube.com/watch?v=7ONI6JjXvMw"}]},
    )
    item = _find_collected_item(store, "7ONI6JjXvMw")
    assert item is not None, "유튜브 항목을 못 찾으면 대본추출이 영원히 404다"
    assert item["url"] == "https://www.youtube.com/watch?v=7ONI6JjXvMw"


@pytest.mark.parametrize("platform", ["tiktok", "threads", "naverclip",
                                      "pinterest", "xiaohongshu", "douyin"])
def test_다른_플랫폼도_전부_찾는다(platform):
    """유튜브만 뚫으면 같은 병이 나머지 플랫폼에 그대로 남는다(0순위-B)."""
    store = _FakeStore(platforms={platform: [{"shortcode": f"CODE_{platform}",
                                              "platform": platform}]})
    item = _find_collected_item(store, f"CODE_{platform}")
    assert item is not None, f"{platform} 항목을 못 찾는다"


def test_어디에도_없으면_None():
    """없는 건 없다고 해야 404 안내가 정상 동작한다."""
    store = _FakeStore(insta=[{"shortcode": "AAA"}],
                       platforms={"youtube": [{"shortcode": "BBB"}]})
    assert _find_collected_item(store, "ZZZ") is None


def test_인스타가_우선이다():
    """같은 코드가 양쪽에 있으면 종전 동작(인스타)을 유지 — 회귀 방지."""
    store = _FakeStore(insta=[{"shortcode": "SAME", "which": "insta"}],
                       platforms={"youtube": [{"shortcode": "SAME", "which": "yt"}]})
    assert _find_collected_item(store, "SAME")["which"] == "insta"


def test_스냅샷이_깨져도_안_터진다():
    """플랫폼 스냅샷 하나가 고장나도 나머지를 계속 본다 — 조용한 전멸 금지."""

    class _Broken(_FakeStore):
        def load_last_run_platform(self, platform):
            if platform == "tiktok":
                raise RuntimeError("스냅샷 손상")
            return super().load_last_run_platform(platform)

    store = _Broken(platforms={"youtube": [{"shortcode": "YT1"}]})
    assert _find_collected_item(store, "YT1") is not None


def test_shortcode가_비면_None():
    store = _FakeStore(insta=[{"shortcode": "AAA"}])
    assert _find_collected_item(store, "") is None
    assert _find_collected_item(store, None) is None
