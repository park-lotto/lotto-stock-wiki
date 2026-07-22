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
