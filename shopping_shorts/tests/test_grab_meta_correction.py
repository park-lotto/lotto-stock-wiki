"""담기가 보낸 제목·썸네일이 **엉뚱한 영상 것**일 때 서버가 바로잡는가.

왜 필요한가(2026-09-01 실사고, 실측):
  유튜브 쇼츠는 SPA라 세로 스크롤로 다음 영상에 가면 `location.href`는 갱신되지만
  `<meta og:image>`·`<meta og:title>`은 **처음 로드한 영상 것 그대로 남는다**.
  담기 스크립트는 주소를 location.href에서, 제목·썸네일을 og:*에서 따로 읽으므로
  둘이 어긋난다(0순위-B: 같은 판단 "지금 보는 영상"을 두 군데서 따로 내렸다).

  라이브 실측 — customer 205, 2026-08-30 16:14 저장분:
    url       = youtube.com/shorts/L8mYlaYXVFI  → 집코드 "지저분한 수납정리 이걸로 끝"
    name      = "이 서랍 하나로 화장품 정리 전쟁 끝냈어요"  → 홈모아(B_O4a0x_MmU)
    thumbnail = i.ytimg.com/vi/B_O4a0x_MmU/...            → 홈모아
  즉 **주소는 A, 얼굴은 B**인 짜깁기 행. 사장님은 즐겨찾기에서 A를 찾다 못 찾고
  다시 담았고, shortcode는 URL 해시라 "이미 담겨 있어요"만 떴다.

★확장 사용자는 재설치 전엔 옛 로직이 돈다(MV3 원격코드 금지 — 로직이 패키지에 동봉).
  실측 34명 중 32명이 확장 사용자였다. 그래서 **서버가 바로잡아야** 전원이 즉시 산다.
  주소는 항상 정확하므로(location.href는 스크롤 따라 제대로 바뀐다) 서버가 URL로
  다시 조회한 값이 진실이다.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_wrong_meta_is_corrected(tmp_path):
    """브라우저가 보낸 값이 틀렸으면 서버 보강값이 **덮어써야** 한다."""
    s = _store(tmp_path)
    s.mix_basket_add("grab_youtube_ae720c38cf08",
                     url="https://www.youtube.com/shorts/L8mYlaYXVFI",
                     name="이 서랍 하나로 화장품 정리 전쟁 끝냈어요",       # 홈모아 = 틀림
                     thumbnail="https://i.ytimg.com/vi/B_O4a0x_MmU/sardefault.jpg",
                     customer_id=0)
    s.mix_basket_set_meta("grab_youtube_ae720c38cf08", customer_id=0,
                          thumbnail="https://i.ytimg.com/vi/L8mYlaYXVFI/hq2.jpg",
                          name="✨️지저분한 수납정리 이걸로 끝🌈 #정리 #수납템 #살림템",
                          overwrite=True)
    it = s.mix_basket_list(customer_id=0)[0]
    assert it["name"] == "✨️지저분한 수납정리 이걸로 끝🌈 #정리 #수납템 #살림템"
    assert "L8mYlaYXVFI" in it["thumbnail"]
    assert "B_O4a0x_MmU" not in it["thumbnail"]


def test_default_still_does_not_overwrite(tmp_path):
    """★기본 동작은 그대로여야 한다 — overwrite를 안 주면 종전대로 '빈 칸만' 채운다.

    이 보호가 없으면 사용자가 손으로 고친 이름을 백그라운드 보강이 조용히 되돌린다.
    """
    s = _store(tmp_path)
    s.mix_basket_add("k1", url="https://x/y", name="사장님이 고친 이름",
                     thumbnail="https://img/keep.jpg", customer_id=0)
    s.mix_basket_set_meta("k1", customer_id=0,
                          thumbnail="https://img/other.jpg", name="자동으로 뽑은 이름")
    it = s.mix_basket_list(customer_id=0)[0]
    assert it["name"] == "사장님이 고친 이름"
    assert it["thumbnail"] == "https://img/keep.jpg"


def test_overwrite_fills_empty_too(tmp_path):
    """빈 칸이면 overwrite 여부와 무관하게 채워진다(회귀 방지)."""
    s = _store(tmp_path)
    s.mix_basket_add("k2", url="https://x/y", customer_id=0)
    s.mix_basket_set_meta("k2", customer_id=0, thumbnail="https://img/a.jpg",
                          name="제목", overwrite=True)
    it = s.mix_basket_list(customer_id=0)[0]
    assert it["name"] == "제목"
    assert it["thumbnail"] == "https://img/a.jpg"


# ── 서버가 '틀렸다'고 판정하는 지점 ────────────────────────────────────────────
# 판정은 _grab_meta_is_stale 한 곳에서만 한다(0순위-B: 호출부 3곳에 같은 판단을
# 세 번 적으면 반드시 어긋난다).

def test_stale_when_thumbnail_points_to_other_video():
    """유튜브: 썸네일의 영상ID가 URL의 영상ID와 다르면 = og 잔상 = 틀렸다."""
    from shopping_shorts.app import _grab_meta_is_stale
    assert _grab_meta_is_stale(
        "https://www.youtube.com/shorts/L8mYlaYXVFI",
        "https://i.ytimg.com/vi/B_O4a0x_MmU/sardefault.jpg?sqp=-oaym") is True


def test_not_stale_when_ids_match():
    """같은 영상이면 건드리지 않는다 — 정상 담기를 덮어쓰면 안 된다."""
    from shopping_shorts.app import _grab_meta_is_stale
    assert _grab_meta_is_stale(
        "https://www.youtube.com/shorts/L8mYlaYXVFI",
        "https://i.ytimg.com/vi/L8mYlaYXVFI/hq2.jpg") is False


def test_not_stale_when_no_thumbnail():
    """썸네일을 안 보냈으면 비교할 게 없다 → 종전대로 '빈 칸만 채우기'."""
    from shopping_shorts.app import _grab_meta_is_stale
    assert _grab_meta_is_stale("https://www.youtube.com/shorts/L8mYlaYXVFI", "") is False


def test_not_stale_for_other_platforms():
    """★유튜브 밖에는 적용하지 않는다.

    틱톡·인스타 썸네일 URL에는 영상ID가 안 들어 있어 대조 자체가 불가능하다.
    억지로 판정하면 멀쩡한 값을 덮어쓴다(증상 없는 데이터 손상).
    """
    from shopping_shorts.app import _grab_meta_is_stale
    assert _grab_meta_is_stale(
        "https://www.tiktok.com/@a/video/7679696248848321813",
        "https://p16-common-sign.tiktokcdn.com/tos-alisg-p-0037/abc~tplv.jpeg") is False
    assert _grab_meta_is_stale(
        "https://www.instagram.com/reel/DcpEGUbSfYr/",
        "https://scontent.cdninstagram.com/v/t51/xyz.jpg") is False


def test_watch_url_form_also_compared():
    """watch?v= 형식도 같은 판정을 받아야 한다(쇼츠만 있는 게 아니다)."""
    from shopping_shorts.app import _grab_meta_is_stale
    assert _grab_meta_is_stale(
        "https://www.youtube.com/watch?v=kL_1k1vgvMY",
        "https://i.ytimg.com/vi/OTHERvidID1/hq2.jpg") is True
