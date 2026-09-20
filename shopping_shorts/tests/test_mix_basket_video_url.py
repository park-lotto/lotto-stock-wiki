from shopping_shorts import mix_pipeline
from shopping_shorts.store import Store


def test_mix_uses_basket_direct_video_url_for_customer(tmp_path):
    store = Store(str(tmp_path / "test.db"))
    page = "https://www.rednote.com/discovery/item/abc"
    direct = "https://sns-v28.rednotecdn.com/stream/abc_258.mp4"
    store.mix_basket_add("grab_xiaohongshu_abc", url=page,
                         video_url=direct, customer_id=352)

    assert mix_pipeline._basket_download_urls([page], store, 352) == [direct]


def test_mix_does_not_use_another_customers_video_url(tmp_path):
    store = Store(str(tmp_path / "test.db"))
    page = "https://www.rednote.com/discovery/item/abc"
    direct = "https://sns-v28.rednotecdn.com/stream/abc_258.mp4"
    store.mix_basket_add("grab_xiaohongshu_abc", url=page,
                         video_url=direct, customer_id=352)

    assert mix_pipeline._basket_download_urls([page], store, 999) == [page]


def test_mix_ignores_non_media_basket_url(tmp_path):
    store = Store(str(tmp_path / "test.db"))
    page = "https://www.rednote.com/discovery/item/abc"
    store.mix_basket_add("grab_xiaohongshu_abc", url=page,
                         video_url="https://example.com/not-media", customer_id=352)

    assert mix_pipeline._basket_download_urls([page], store, 352) == [page]
