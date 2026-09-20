import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "yt_agents"))

import clip_teardown


def test_parse_video_id_supports_common_urls():
    video_id = "abc123DEF45"
    assert clip_teardown.parse_video_id(f"https://youtu.be/{video_id}") == video_id
    assert clip_teardown.parse_video_id(f"https://www.youtube.com/watch?v={video_id}") == video_id
    assert clip_teardown.parse_video_id(f"https://youtube.com/shorts/{video_id}") == video_id
    assert clip_teardown.parse_video_id("https://example.com/video") == ""


def test_teardown_normalizes_ai_result(monkeypatch):
    monkeypatch.setattr(clip_teardown, "_metadata", lambda _video_id: {
        "title": "실제 제목", "channel": "실제 채널", "view_count": 1200,
        "thumbnail": "https://example.com/thumb.jpg", "duration": 60,
    })
    monkeypatch.setattr(clip_teardown.gemini_client, "call_video", lambda *_args, **_kwargs: """{
      "click_device":{"title_formula":"대상+문제"},
      "hook":{"type":"공감","evidence":[{"at":"00:00:02","quote":"근거"}]},
      "story_beats":[],"viewer_needs":[],"visual_grammar":{},"strengths":[],"risks":[]
    }""")
    card = clip_teardown.teardown("abc123DEF45")
    assert card["title"] == "실제 제목"
    assert card["metrics"]["view_count"] == 1200
    assert card["hook"]["evidence"][0]["at"] == "00:00:02"
