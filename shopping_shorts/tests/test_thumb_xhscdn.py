"""/api/thumb 프록시가 샤오훙슈(rednote) 커버 CDN을 허용하는지(2026-07-19).

제작소 재료 카드는 썸네일을 /api/thumb 프록시로 띄운다. xhscdn.com이 허용목록에 없어
프록시가 400을 내면 lens/grab로 담은 샤오훙슈 영상 썸네일만 안 떴다(실측). 허용목록에
추가했으니 xhscdn URL은 거부되지 않아야 하고, 정상 인스타/틱톡 호스트는 그대로 허용,
비허용 호스트(SSRF/임의)는 계속 거부돼야 한다."""
from shopping_shorts import app as app_module

ALLOWED = app_module._ALLOWED_THUMB_HOSTS


def test_xhscdn_allowed():
    # 실제 저장되는 두 xhscdn 서브도메인(값 형태는 서버 DB 실측)
    for u in (
        "https://sns-na-i11.xhscdn.com/1040g2sg3213mgt8i7ae04a4sb4q8co4m6pkjje0?imageView2/2/w/576/",
        "https://sns-webpic-qc.xhscdn.com/202607191444/e2ef62fa/1040g2sg31v",
    ):
        assert app_module._reject_cdn_proxy(u, ALLOWED) is False, u


def test_other_known_hosts_still_allowed():
    for u in (
        "https://scontent-lax7-1.cdninstagram.com/v/t51/x.jpg",
        "https://p16-common-sign.tiktokcdn.com/tos/x.jpeg",
    ):
        assert app_module._reject_cdn_proxy(u, ALLOWED) is False, u


def test_unknown_or_ssrf_host_still_rejected():
    for u in (
        "http://169.254.169.254/latest/meta-data/",
        "https://evil.example.com/x.jpg",
    ):
        assert app_module._reject_cdn_proxy(u, ALLOWED) is True, u
