"""'내용물 있는 틀' 고정 테스트.

여기서 지키려는 것은 그림의 예쁨이 아니라 **미리보기와 렌더가 같은 그림을 쓴다**는 계약이다.
그게 깨지면 "미리보기랑 다르게 나왔다"가 다시 시작된다.
"""
from shopping_shorts import deco_frame as df
from shopping_shorts import mix_pipeline as mp


def test_normalize_defaults_and_clamp():
    s = df.normalize({})
    assert s["preset"] in df.PRESETS
    assert s["bar_h"] == df.DEFAULTS["bar_h"]
    # 범위를 넘기면 잘린다 — 화면이 아니라 여기서 자른다(정의처 한 곳)
    assert df.normalize({"bar_h": 9999})["bar_h"] == 400
    assert df.normalize({"bar_h": -50})["bar_h"] == 0
    assert df.normalize({"bar_h": "abc"})["bar_h"] == df.DEFAULTS["bar_h"]
    # 모르는 preset은 조용히 기본값으로 (옛 작업이 지워진 preset을 가리킬 수 있다)
    assert df.normalize({"preset": "없는것"})["preset"] == df.DEFAULTS["preset"]


def test_cache_key_same_spec_same_key():
    a = {"preset": "news_coral", "channel": "가", "bar_h": 190}
    b = {"bar_h": 190, "channel": "가", "preset": "news_coral"}   # 순서만 다름
    assert df.cache_key(a) == df.cache_key(b)
    assert df.cache_key(a) != df.cache_key({**a, "bar_h": 100})


def test_render_size_and_transparent_middle():
    im = df.render({"preset": "news_coral", "channel": "테스트", "bar_h": 190})
    assert im.size == (1080, 1920)
    assert im.mode == "RGBA"
    # 가운데는 비어 있어야 한다 — 안 그러면 영상을 가린다
    assert im.getpixel((540, 1400))[3] == 0
    # 띠 안은 칠해져 있다
    assert im.getpixel((540, 90))[3] == 255


def test_bar_zero_draws_nothing_on_top():
    im = df.render({"preset": "news_coral", "bar_h": 0})
    assert im.getpixel((540, 5))[3] == 0


def test_pipeline_uses_same_file_as_preview():
    """렌더가 집는 경로 == deco_frame이 정한 캐시 경로. 두 곳이 갈리면 이 테스트가 깨진다."""
    spec = {"preset": "news_lime", "channel": "쇼핑 치트키", "title": "제목", "bar_h": 150}
    layer = mp._template_layer({"frame": spec})
    assert layer is not None
    assert layer["_abspath"] == str(df.cache_path(spec))
    assert layer["id"].startswith("frame:")


def test_legacy_color_bar_templates_still_work():
    """옛 12종(빈 색띠)은 건드리지 않았다 — 저장된 작업이 계속 돌아야 한다."""
    layer = mp._template_layer({"id": "tpl_01", "span": "first"}, 3.5)
    assert layer is not None
    assert layer["id"] == "tpl_01"
    assert layer["dur"] == 3.5
    assert mp._template_layer({}) is None
