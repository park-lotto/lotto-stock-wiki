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


def test_title_deco_normalize():
    """제목 색·테두리(2026-08-28) — 검사도 normalize 한 곳에서(다른 색 축과 같은 규약)."""
    s = df.normalize({"title_color": "ff0000", "title_ol_c": "#00FF00",
                      "title_ol_w": 99})
    assert s["title_color"] == "#FF0000"      # # 없이 와도 붙여서 받는다
    assert s["title_ol_c"] == "#00FF00"
    assert s["title_ol_w"] == 20              # 상한 20으로 잘린다
    # 이상한 값은 빈값(=자동)으로 — 예외로 죽으면 미리보기가 통째로 안 나온다
    bad = df.normalize({"title_color": "빨강", "title_ol_c": "#12", "title_ol_w": "x"})
    assert bad["title_color"] == "" and bad["title_ol_c"] == ""
    assert bad["title_ol_w"] == 0


def test_title_color_overrides_auto():
    """사장님이 고른 제목색이 자동(흑/백)을 이긴다 — 안 정하면 기존 그림 그대로."""
    base = {"preset": "news_coral", "title": "제목색 테스트", "bar_h": 190}
    # 안 정했으면: 새 키를 빈값으로 보낸 spec == 아예 안 보낸 spec (기존 무변경 계약)
    assert df.cache_key(base) == df.cache_key(
        {**base, "title_color": "", "title_ol_c": "", "title_ol_w": 0})
    im_auto = df.render(base)
    im_red = df.render({**base, "title_color": "#FF0000"})
    assert im_auto.tobytes() != im_red.tobytes()
    # 빨간 픽셀이 실제로 생겼는지 — 제목 블록 영역(띠 아래)에서 찾는다
    found = any(im_red.getpixel((x, y))[:3] == (255, 0, 0)
                for y in range(190, 400, 4) for x in range(300, 780, 4))
    assert found, "title_color를 보냈는데 빨간 글자가 안 그려졌다"


def test_title_outline_draws_only_with_width():
    """테두리는 두께>0일 때만. 색만 정하고 두께 0이면 아무 일도 없다."""
    base = {"preset": "news_coral", "title": "테두리 테스트", "bar_h": 190}
    im_none = df.render(base)
    im_c_only = df.render({**base, "title_ol_c": "#00FF00"})
    assert im_none.tobytes() == im_c_only.tobytes()   # 두께 없으면 무변경
    im_ol = df.render({**base, "title_ol_c": "#00FF00", "title_ol_w": 6})
    assert im_ol.tobytes() != im_none.tobytes()
    found = any(im_ol.getpixel((x, y))[:3] == (0, 255, 0)
                for y in range(190, 400, 4) for x in range(300, 780, 4))
    assert found, "테두리 두께·색을 보냈는데 초록 외곽선이 안 그려졌다"
    # 색을 안 정하고 두께만 밀어도 그려진다(자동 반대색) — 슬라이더만 만져도 동작
    im_w_only = df.render({**base, "title_ol_w": 6})
    assert im_w_only.tobytes() != im_none.tobytes()


def test_bottom_bar_independent_of_top():
    """위·아래 띠는 따로 조절된다. 같은 규칙으로 잘리는지도 함께 잠근다."""
    im = df.render({"preset": "news_coral", "bar_h": 0, "bottom_h": 160})
    assert im.getpixel((540, 5))[3] == 0        # 위는 없음
    assert im.getpixel((540, 1900))[3] == 255   # 아래는 있음
    assert im.getpixel((540, 1200))[3] == 0     # 가운데는 여전히 투명
    assert df.normalize({"bottom_h": 9999})["bottom_h"] == 400
    assert df.normalize({"bottom_h": "abc"})["bottom_h"] == df.DEFAULTS["bottom_h"]
