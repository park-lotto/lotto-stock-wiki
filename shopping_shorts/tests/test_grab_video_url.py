"""담기가 보낸 '영상 파일 직접 주소'(video_url)가 저장·전달되는지.

왜 필요한가(2026-08-17 실측): 도우인은 yt-dlp가 쿠키를 요구해 페이지 URL로는
서버가 영상을 못 받는다 — 서버(AWS)와 사장님 PC(가정용 IP) 양쪽에서 똑같이 실패해
IP 문제가 아님을 확인했고, 헤드리스 브라우저로 쿠키 20개를 얻어 넘겨도 안 됐다.
유일하게 확실한 길은 **브라우저에 이미 떠 있는 CDN 주소를 담을 때 함께 받는 것**이다.
그 값이 한 군데라도 끊기면 다시 조용히 '분석 대기'로 돌아간다.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_basket_keeps_video_url(tmp_path):
    s = _store(tmp_path)
    u = "https://v3-dy-o.zjcdn.com/abc/def?sig=xyz"
    s.mix_basket_add("grab_douyin_1", url="https://www.douyin.com/video/1",
                     video_url=u, customer_id=0)
    got = {i["shortcode"]: i.get("video_url") for i in s.mix_basket_list(customer_id=0)}
    assert got["grab_douyin_1"] == u


def test_basket_without_video_url_is_unchanged(tmp_path):
    """옛 방식(영상 주소 없이 담기)은 그대로 — 회귀 0."""
    s = _store(tmp_path)
    s.mix_basket_add("grab_old", url="https://x/y", customer_id=0)
    item = s.mix_basket_list(customer_id=0)[0]
    assert item["shortcode"] == "grab_old"
    assert not item.get("video_url")


def test_toggle_still_works(tmp_path):
    """★담기 토글은 video_url을 받지 않는다 — 여기에 그 변수를 끼워 넣었다가
    호출만 하면 터지는 상태를 만든 적이 있다(같은 테이블에 INSERT가 두 곳)."""
    s = _store(tmp_path)
    assert s.mix_basket_toggle("tog1", url="https://z/1", customer_id=0) is True
    assert s.mix_basket_toggle("tog1", url="https://z/1", customer_id=0) is False


def test_grabbable_media_guard_is_host_based():
    """서버가 그 주소를 그대로 내려받으므로 임의 도메인을 받아선 안 된다."""
    from shopping_shorts.app import _is_grabbable_media
    assert _is_grabbable_media("https://v3-dy-o.zjcdn.com/a?b=1")
    assert _is_grabbable_media("https://sns-video.xhscdn.com/y")
    assert not _is_grabbable_media("https://evil.example.com/a.mp4")   # 확장자만으론 안 된다
    assert not _is_grabbable_media("https://zjcdn.com.evil.com/a")     # 접미 위장
    assert not _is_grabbable_media("blob:https://www.douyin.com/x")    # 브라우저 안에서만 유효
    assert not _is_grabbable_media("http://v3-dy-o.zjcdn.com/a")       # https만


def test_regrab_fills_missing_video_url(tmp_path):
    """★이미 담긴 영상을 다시 담으면 영상 주소가 **채워져야** 한다.

    shortcode는 URL 해시라 같은 영상을 다시 담으면 '이미 있음'으로 떨어진다.
    거기서 그냥 return하면 사장님이 아무리 다시 담아도 주소가 영영 안 들어와
    도우인은 계속 못 받는다 — 다시 담기가 유일한 구제 수단인데 그게 막힌다.
    """
    s = _store(tmp_path)
    s.mix_basket_add("grab_douyin_1", url="https://www.douyin.com/video/1", customer_id=0)
    assert not s.mix_basket_list(customer_id=0)[0].get("video_url")
    u = "https://v3-dy-o.zjcdn.com/abc?sig=1"
    s.mix_basket_add("grab_douyin_1", url="https://www.douyin.com/video/1",
                     video_url=u, customer_id=0)
    assert s.mix_basket_list(customer_id=0)[0]["video_url"] == u


def test_regrab_does_not_overwrite_existing_video_url(tmp_path):
    """이미 주소가 있으면 덮어쓰지 않는다(서명 만료된 새 값으로 멀쩡한 값을 밀어내지 않게)."""
    s = _store(tmp_path)
    first = "https://v3-dy-o.zjcdn.com/first?sig=1"
    s.mix_basket_add("grab_d", url="https://www.douyin.com/video/2",
                     video_url=first, customer_id=0)
    s.mix_basket_add("grab_d", url="https://www.douyin.com/video/2",
                     video_url="https://v3-dy-o.zjcdn.com/second?sig=2", customer_id=0)
    assert s.mix_basket_list(customer_id=0)[0]["video_url"] == first


def test_hopeless_errors_are_reported_at_once():
    """로그인벽·비공개는 몇 번을 더 해도 결과가 같다 — 3회를 기다리지 말고 바로 알린다.

    사장님 지적('대본 만들기를 눌러야 분석이 된다고?')의 뿌리: 이미 막힌 영상이
    시도 1~2회 동안 '분석 대기'로 보여, 오지 않을 결과를 기다리게 했다.
    """
    from shopping_shorts.app import _is_hopeless_error
    assert _is_hopeless_error("ERROR: [Douyin] Fresh cookies (not necessarily logged in) are needed")
    assert _is_hopeless_error("Video unavailable")
    assert not _is_hopeless_error("Connection reset by peer")   # 일시적 — 더 해보면 될 수 있다
    assert not _is_hopeless_error("")
