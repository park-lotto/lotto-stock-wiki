"""쓰레드 노드 → 우리 계약 dict (네트워크 없음).

키 이름은 인스타 파서(instagram_parse.parse_reel_node)와 일부러 다르게 둔다 —
쓰레드는 reel이 아니고 reposts가 있다. 랭킹으로 넘길 때 변환한다(Task 5).
"""
from shopping_shorts.threads_parse import parse_post_node

_NODE = {
    "code": "DcIknZjEQVW",
    "taken_at": 1786900000,
    "caption": {"text": "나 지금까지 헛고생함"},
    "like_count": 9,
    "text_post_app_info": {"direct_reply_count": 1, "repost_count": 2},
    "image_versions2": {"candidates": [{"url": "https://cdn/t.jpg", "width": 640}]},
    "video_versions": [{"url": "https://cdn/v.mp4", "width": 720}],
}


def test_영상_게시물을_계약대로_뽑는다():
    p = parse_post_node(_NODE, "petppuri")
    assert p["code"] == "DcIknZjEQVW"
    assert p["username"] == "petppuri"
    assert p["caption"] == "나 지금까지 헛고생함"
    assert p["media_kind"] == "video"
    assert p["video_url"] == "https://cdn/v.mp4"
    assert p["thumb"] == "https://cdn/t.jpg"
    assert p["likes"] == 9
    assert p["comments"] == 1
    assert p["reposts"] == 2
    assert p["url"] == "https://www.threads.com/@petppuri/post/DcIknZjEQVW"


def test_캡션이_문자열로_와도_받는다():
    node = dict(_NODE, caption="그냥 문자열")
    assert parse_post_node(node, "u")["caption"] == "그냥 문자열"


def test_캡션이_None이어도_안_터진다():
    # ★.strip() 전에 타입을 확인하지 않아 라이브 500이 세 번 났다.
    node = dict(_NODE, caption=None)
    assert parse_post_node(node, "u")["caption"] == ""


def test_영상이_없으면_image로_본다():
    node = dict(_NODE)
    node.pop("video_versions")
    p = parse_post_node(node, "u")
    assert p["media_kind"] == "image"
    assert p["video_url"] == ""


def test_코드가_없으면_None():
    assert parse_post_node({"caption": {"text": "x"}}, "u") is None


def test_노드가_dict가_아니면_None():
    assert parse_post_node("문자열", "u") is None


def test_실페이로드에서_노드가_한_개_이상_나온다():
    import json
    import pathlib

    from shopping_shorts.threads_parse import extract_post_nodes, parse_post_node

    raw = json.loads(pathlib.Path(
        "shopping_shorts/tests/fixtures/threads_profile_payload.json"
    ).read_text(encoding="utf-8"))
    nodes = []
    for x in raw:
        nodes += extract_post_nodes(x["body"])
    assert len(nodes) > 0, "실페이로드에서 노드를 하나도 못 뽑았다"

    posts = [p for p in (parse_post_node(n, "jiniggultem") for n in nodes) if p]
    assert posts, "노드는 나왔는데 파싱이 전부 실패했다"
    # 실측: 이 계정 글에는 영상이 붙어 있다(video_versions 19건).
    assert any(p["media_kind"] == "video" for p in posts)
