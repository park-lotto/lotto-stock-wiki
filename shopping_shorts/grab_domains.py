"""담기·받기가 알아보는 플랫폼 주소 목록 — **한 곳**(관제 234 5판에서 app.py 에서 떼어냄).
app(담기·렌즈)·media_download(받기)가 같이 쓴다. 회원 PC 엔진 묶음에는 app.py 가 없어 media_download 가 app 을
부르면 틱톡·유튜브 받기까지 통째로 막혔다(10-19 실측: "import of shopping_shorts.app halted") — 그래서 목록만 여기로.
"""
import urllib.parse

_GRAB_DOMAINS = [
    ("youtube", ("youtube.com", "youtu.be")),
    ("tiktok", ("tiktok.com",)),
    ("instagram", ("instagram.com",)),
    ("xiaohongshu", ("xiaohongshu.com", "xhslink.com", "rednote.com")),
    ("douyin", ("douyin.com", "iesdouyin.com")),
    ("threads", ("threads.com", "threads.net")),
    # 핀터레스트(2026-09-11 고객 "담기 버튼이 없다") — 다운로드는 media_download._download_pinterest
    # ★2026-09-24 고객 "담기가 안 된다": `pinterest.com`만 알아봐서 **앱 공유 링크(pin.it)**와
    #   나라별 주소(pinterest.co.kr·.jp 등)가 통째로 막혔다. 휴대폰 공유 버튼이 주는 기본 주소가 pin.it이다.
    ("pinterest", ("pinterest.com", "pin.it", "pinterest.co.kr", "pinterest.co.uk",
                   "pinterest.jp", "pinterest.ca", "pinterest.de", "pinterest.fr",
                   "pinterest.es", "pinterest.it", "pinterest.ph", "pinterest.at",
                   "pinterest.ch", "pinterest.cl", "pinterest.dk", "pinterest.ie",
                   "pinterest.nz", "pinterest.pt", "pinterest.se", "pinterest.ru")),
]


def _grab_platform(url):
    host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    for name, doms in _GRAB_DOMAINS:
        if any(host == d or host.endswith("." + d) for d in doms):
            return name
    return ""
