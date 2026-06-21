"""포스트형 소스(블로그·유튜브·뉴스) config. 소스 추가 = 여기 한 줄."""

POST_SOURCES = {
    "blog": {
        "source_type": "blog", "dir": "raw/blog",
        "header_label": "출처", "registry": "blog_registry.json",
    },
    "youtube": {
        "source_type": "youtube", "dir": "raw/yt",
        "header_label": "채널", "registry": "youtube_registry.json",
    },
    "news": {
        "source_type": "news", "dir": "raw/news",
        "header_label": ["출처", "키워드"], "registry": "news_registry.json",
    },
}


def source_config(name: str) -> dict:
    return POST_SOURCES[name]
