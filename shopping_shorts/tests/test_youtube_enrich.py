from shopping_shorts.youtube_client import video_id_from_url

def test_video_id_from_url_forms():
    assert video_id_from_url("https://www.youtube.com/watch?v=abc123DEF45") == "abc123DEF45"
    assert video_id_from_url("https://youtu.be/abc123DEF45") == "abc123DEF45"
    assert video_id_from_url("https://www.youtube.com/shorts/abc123DEF45") == "abc123DEF45"
    assert video_id_from_url("https://www.youtube.com/watch?v=abc123DEF45&t=10s") == "abc123DEF45"
    assert video_id_from_url("https://www.tiktok.com/@x/video/123") is None
    assert video_id_from_url("") is None
