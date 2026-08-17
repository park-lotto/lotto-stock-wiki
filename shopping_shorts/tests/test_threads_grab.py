"""쓰레드 담기 배선.

★틱톡에서 캐시 키 접두사가 어긋나 태깅이 통째로 불발한 전례가 있다. 여기서는
  기존 sc 조립식(grab_<platform>_<sha1>)을 그대로 쓰므로 손으로 접두사를 붙이지 않는다.
"""
from shopping_shorts.app import _grab_platform, _is_grabbable_media


def test_쓰레드_URL이_threads로_갈린다():
    assert _grab_platform("https://www.threads.com/@u/post/DcAbc") == "threads"
    assert _grab_platform("https://threads.net/@u/post/DcAbc") == "threads"


def test_다른_플랫폼은_그대로다():
    assert _grab_platform("https://www.instagram.com/reel/x/") == "instagram"
    assert _grab_platform("https://www.tiktok.com/@u/video/1") == "tiktok"


def test_모르는_주소는_빈값():
    assert _grab_platform("https://example.com/a") == ""


def test_쓰레드_영상_CDN이_허용된다():
    # ★없으면 영상 주소가 조용히 버려진다. 쓰레드 mp4는 인스타와 같은 CDN이다.
    assert _is_grabbable_media(
        "https://scontent-ssn1-1.cdninstagram.com/o1/v/t16/f2/m84/AQOp9.mp4") is True


def test_임의_도메인은_여전히_막힌다():
    assert _is_grabbable_media("https://evil.example.com/a.mp4") is False
    assert _is_grabbable_media("http://scontent.cdninstagram.com/a.mp4") is False
