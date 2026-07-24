"""run_mix_job의 백본 배선 헬퍼: (1) job.urls로 플랫폼 meta 구성(예전 urls_json 버그 수정)
(2) backbone_main 인덱스 → 추출 소스 video_id 해석."""
from shopping_shorts import mix_pipeline as mp


def _extracts():
    # extracts 키 순서 = 소스(=urls) 순서. run_mix_job의 dict(ex.map(...)) 산출과 동형.
    return {"vidA": {"video_id": "vidA"}, "vidB": {"video_id": "vidB"}}


def test_meta_uses_urls_list_key():
    # get_mix_job은 'urls'(list)로 준다 — platform_of가 실제로 걸려야 한다.
    job = {"urls": ["https://instagram.com/reel/x", "https://xiaohongshu.com/y"]}
    meta = mp._backbone_meta_from_job(job, _extracts())
    assert meta["vidA"]["platform"] == "instagram"
    assert meta["vidB"]["platform"] == "xiaohongshu"


def test_meta_parses_urls_json_fallback():
    # 원시행(urls_json 문자열)이 와도 안전 파싱.
    job = {"urls_json": '["https://youtube.com/shorts/a", "b"]'}
    meta = mp._backbone_meta_from_job(job, _extracts())
    assert meta["vidA"]["platform"] == "youtube"


def test_resolve_backbone_forced_index_to_vid():
    assert mp._resolve_backbone_forced({"backbone_main": 1}, _extracts()) == "vidB"
    assert mp._resolve_backbone_forced({"backbone_main": 0}, _extracts()) == "vidA"


def test_resolve_backbone_forced_none_or_oob():
    assert mp._resolve_backbone_forced({"backbone_main": None}, _extracts()) is None
    assert mp._resolve_backbone_forced({"backbone_main": 9}, _extracts()) is None
    assert mp._resolve_backbone_forced({}, _extracts()) is None


class _FakeStore:
    """수집 캐시(last_run) 흉내 — 백본 참여도(댓글수) 배선 테스트용."""
    def __init__(self, items_by_platform):
        self._items = items_by_platform

    def load_last_run_platform(self, platform):
        return self._items.get(platform, []), None


def test_meta_carries_comments_from_last_run():
    # 사장님: '댓글도 봐야 한다' — url의 shortcode를 수집캐시에서 찾아 comments를 싣는다.
    store = _FakeStore({"instagram": [
        {"shortcode": "AAA111BBB", "comments": 77},
        {"shortcode": "ZZZ999YYY", "comments": 3}]})
    job = {"urls": ["https://www.instagram.com/reel/AAA111BBB/",
                    "https://xiaohongshu.com/discovery/item/x"]}
    meta = mp._backbone_meta_from_job(job, _extracts(), store=store)
    assert meta["vidA"]["comments"] == 77          # 매칭됨
    assert "comments" not in meta["vidB"]          # 캐시에 없으면 미기재(0 지어내지 않음)


def test_meta_without_store_unchanged():
    job = {"urls": ["https://www.instagram.com/reel/AAA111BBB/"]}
    meta = mp._backbone_meta_from_job(job, _extracts())
    assert meta["vidA"] == {"platform": "instagram"}   # store 없으면 기존 동작 그대로
