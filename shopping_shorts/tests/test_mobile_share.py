"""폰 [공유] → ⭐나만의 채널 (2026-09-27 사장님 "폰으로 채널 보다가 등록").

여기서 잠그는 계약:
  1. 앱마다 주소를 넣는 칸이 다르다(url/text/title) — _shared_link가 셋을 훑어 첫 주소를 쓴다
  2. 인스타 앱 공유 주소(reel/코드/?igsh=…)는 채널 아이디로 읽히면 안 된다.
     옛 패턴은 igsh 값의 **맨 끝 글자**를 채널로 잡았다(…R4 → '4', …Rx → 'x')
  3. youtu.be 짧은 주소도 유튜브다
  4. 공유 주소의 추적 꼬리(si·igsh·_r…)를 떼 PC 담기와 같은 주소가 된다 — 영상 담기 키가
     주소 해시라 안 떼면 같은 영상이 두 번 담긴다
"""
import pytest

from shopping_shorts import app as appmod


@pytest.mark.parametrize("url,text,title,want", [
    ("", "https://www.instagram.com/reel/Abc/?igsh=MWx0", "", "https://www.instagram.com/reel/Abc/"),
    ("", "이 영상 봐! https://www.tiktok.com/@a/video/1?_r=1", "", "https://www.tiktok.com/@a/video/1"),
    ("https://youtube.com/shorts/X?si=1", "", "요가", "https://www.youtube.com/shorts/X"),
    ("", "https://www.youtube.com/watch?v=OYPzJh5oE24&si=z", "", "https://www.youtube.com/watch?v=OYPzJh5oE24"),
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


def test_youtube_uploader_uses_official_api(monkeypatch):
    """서버 IP의 yt-dlp는 유튜브가 막는다(2026-09-28 폰 공유 실패) → 공식 API로 핸들을 얻는다.
    핸들은 yt-dlp가 주던 모양(@ 뗀 customUrl)과 같아야 이미 담긴 채널과 중복되지 않는다."""
    from shopping_shorts import youtube_client as yc
    calls = []

    def fake_first_ok(url, params):
        calls.append(url)
        if url == yc._VIDEOS_URL:
            return {"items": [{"snippet": {"channelId": "UCabc", "channelTitle": "숏포츠"}}]}, False
        return {"items": [{"snippet": {"customUrl": "@숏포츠-j7j"}}]}, False

    monkeypatch.setattr(yc, "_first_ok", fake_first_ok)
    assert yc.uploader_of_video("https://youtube.com/shorts/oVllezUV5Hs?si=x") == ("숏포츠-j7j", "숏포츠")
    assert calls == [yc._VIDEOS_URL, yc._CHANNELS_URL]
    # _resolve_uploader도 유튜브면 이 길을 탄다(yt-dlp를 부르지 않는다)
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("yt-dlp 호출됨")))
    assert appmod._resolve_uploader("https://youtu.be/oVllezUV5Hs") == ("숏포츠-j7j", "숏포츠")


def test_share_and_pc_grab_same_video_same_key():
    """폰 공유 주소와 PC 브라우저 주소가 같은 영상이면 담기 키(주소)가 같아야 한다."""
    pc = "https://www.youtube.com/shorts/oVllezUV5Hs"
    assert appmod._shared_link("", "https://youtube.com/shorts/oVllezUV5Hs?si=GyDcRuGEqxb2aEpf") == pc
    assert appmod._shared_link("", "https://m.youtube.com/shorts/oVllezUV5Hs?feature=share") == pc


def test_resolve_uploader_survives_empty_youtube_api(monkeypatch):
    """API가 빈 결과(쿼터 소진·키 없음)면 yt-dlp로 내려가야 한다 — 죽으면 안 된다.
    2026-09-28 실측: 함수 안 `import sys`가 위쪽 print(file=sys.stderr)를 UnboundLocalError로 만들어 500."""
    from shopping_shorts import youtube_client as yc
    import subprocess
    monkeypatch.setattr(yc, "_first_ok", lambda url, params: (None, True))

    class R:
        returncode = 0
        stdout = '{"uploader_id": "@aliceyoga5823", "channel": "앨리스 요가", "uploader": "앨리스 요가"}'
        stderr = ""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    assert appmod._resolve_uploader("https://www.youtube.com/shorts/R2MWz58WBpU") == ("aliceyoga5823", "앨리스 요가")
