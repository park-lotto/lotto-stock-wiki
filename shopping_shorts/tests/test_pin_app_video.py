"""핀 페이지에 JSON-LD가 없을 때(프록시 없는 서버 IP) 앱 데이터로 영상 핀을 알아본다 — 관제 151, 2026-10-07.

실측: 프록시가 끊긴 뒤 렌즈가 영상 핀 3/3을 '영상 아님'으로 잘라 핀터레스트가 사라졌다.
서버 IP로 받은 페이지의 앱 데이터: 영상 핀 9/9 duration·영상 주소 있음, 사진 핀 8/8 없음.
"""
from shopping_shorts import pinterest_crawl as pc

VIDEO_PAGE = (
    '<html><head><title>Six-Speed Gear Shift Keychain [Video] | Car accessories</title></head><body>'
    '<script>{"title":"Six-Speed Gear Shift Keychain","videos":{"videoList":{"__typename":"VideoList",'
    '"vHLSV3MOBILE":{"thumbnail":"https://i.pinimg.com/videos/thumbnails/originals/59/06/aa.0000000.jpg",'
    '"url":"https://v1.pinimg.com/videos/iht/hls/59/06/aa.m3u8","duration":4500},'
    '"v720P":{"__typename":"VideoDetail","thumbnail":"https://i.pinimg.com/videos/thumbnails/originals/59/06/aa.0000000.jpg",'
    '"width":1080,"height":1920,"url":"https://v1.pinimg.com/videos/iht/expMp4/59/06/aa_720w.mp4","duration":4500}}}}'
    '</script></body></html>')
HLS_ONLY_PAGE = ('<title>Story [Video] | x</title>'
                 '{"url":"https://v1.pinimg.com/videos/iht/hls/1d/3d/bb.m3u8","duration":11733}')
PHOTO_PAGE = ('<html><head><title>Kitchen organization ideas | Pantry</title></head>'
              '<body><script>{"images":{"736x":{"url":"https://i.pinimg.com/736x/aa.jpg"}}}</script></body></html>')


def test_video_pin_from_app_data():
    it = pc._ld_video_block(VIDEO_PAGE)
    assert it["contentUrl"].endswith("_720w.mp4")
    assert pc.iso_duration_secs(it["duration"]) == 4.5
    assert it["name"] == "Six-Speed Gear Shift Keychain"
    assert it["thumbnailUrl"].startswith("https://i.pinimg.com/videos/thumbnails/")


def test_hls_only_pin_still_counts_as_video():
    it = pc._ld_video_block(HLS_ONLY_PAGE)
    assert it["contentUrl"].endswith(".m3u8")
    assert round(pc.iso_duration_secs(it["duration"]), 3) == 11.733


def test_photo_pin_is_not_video():
    assert pc._ld_video_block(PHOTO_PAGE) is None


def test_json_ld_still_wins():
    page = ('<script type="application/ld+json">{"@type":"VideoObject","contentUrl":"https://v1.pinimg.com/videos/ld.mp4",'
            '"duration":"PT9S","name":"LD"}</script>') + VIDEO_PAGE
    it = pc._ld_video_block(page)
    assert it["contentUrl"].endswith("/ld.mp4") and it["name"] == "LD"


def test_lens_knows_country_pinterest_domains():
    """렌즈도 담기와 같은 핀터레스트 주소 목록을 쓴다 — pinterest.co.kr 핀이 '모르는 사이트'로 버려지던 것."""
    from shopping_shorts import lens_discover as ld
    assert ld._platform_of("https://www.pinterest.co.kr/pin/123456789/") == "pinterest"
    assert ld._platform_of("https://kr.pinterest.com/pin/123456789/") == "pinterest"
    assert ld._platform_of("https://www.pinterest.jp/pin/1/") == "pinterest"
    assert ld._platform_of("https://store.shopping.yahoo.co.jp/x") is None
    assert ld._platform_of("https://www.instagram.com/reel/abc/") == "instagram"
