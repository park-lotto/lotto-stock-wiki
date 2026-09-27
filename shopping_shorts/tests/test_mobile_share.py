"""폰 [공유] → ⭐나만의 채널 (2026-09-27 사장님 "폰으로 채널 보다가 등록").

여기서 잠그는 계약:
  1. 앱마다 주소를 넣는 칸이 다르다(url/text/title) — _shared_link가 셋을 훑어 첫 주소를 쓴다
  2. 인스타 앱 공유 주소(reel/코드/?igsh=…)는 채널 아이디로 읽히면 안 된다.
     옛 패턴은 igsh 값의 **맨 끝 글자**를 채널로 잡았다(…R4 → '4', …Rx → 'x')
  3. youtu.be 짧은 주소도 유튜브다
"""
import pytest

from shopping_shorts import app as appmod


@pytest.mark.parametrize("url,text,title,want", [
    ("", "https://www.instagram.com/reel/Abc/?igsh=MWx0", "", "https://www.instagram.com/reel/Abc/?igsh=MWx0"),
    ("", "이 영상 봐! https://www.tiktok.com/@a/video/1?_r=1", "", "https://www.tiktok.com/@a/video/1?_r=1"),
    ("https://youtube.com/shorts/X?si=1", "", "요가", "https://youtube.com/shorts/X?si=1"),
    ("", "끝에 마침표 https://youtu.be/X.", "", "https://youtu.be/X"),
    ("", "글자만", "", ""),
])
def test_shared_link_picks_first_url(url, text, title, want):
    assert appmod._shared_link(url, text, title) == want


@pytest.mark.parametrize("url", [
    "https://www.instagram.com/reel/DdujakgzcN2/?igsh=MWx0dGRsbzZtbHR4",
    "https://www.instagram.com/reel/DdujakgzcN2/?igsh=MWx0dGRsbzZtbHRx",   # 옛 패턴 → 'x' 등록
    "https://www.instagram.com/p/DdsAtuzhGc7/?igsh=abc",
    "https://www.instagram.com/reels/DdujakgzcN2/",
])
def test_instagram_post_url_is_not_a_channel(url):
    assert appmod._fav_channel_from_url(url) == (None, None)


@pytest.mark.parametrize("url,want", [
    ("https://www.instagram.com/home.and_joy?igsh=abc", "home.and_joy"),
    ("https://instagram.com/show_gom/", "show_gom"),
    ("https://www.instagram.com/show_gom/reel/DdujakgzcN2/", "show_gom"),
])
def test_instagram_profile_url_is_a_channel(url, want):
    assert appmod._fav_channel_from_url(url) == ("instagram", want)


def test_youtu_be_is_youtube():
    assert appmod._fav_channel_platform("https://youtu.be/OYPzJh5oE24?si=x") == "youtube"
    assert appmod._fav_channel_platform("https://news.naver.com/x") == ""
