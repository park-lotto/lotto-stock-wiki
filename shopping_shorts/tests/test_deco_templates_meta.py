"""템플릿 메타 — 12종이 빠짐없이·중복 없이 정의돼 있는가."""
import pathlib
import sys

from shopping_shorts import deco_templates as dt

# tools/make_deco_templates.py는 패키지가 아니라 스크립트라 sys.path에 tools/를 넣어야 import된다.
_TOOLS_DIR = pathlib.Path(__file__).resolve().parents[2] / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
import make_deco_templates as gen  # noqa: E402


def test_twelve_templates():
    assert len(dt.TEMPLATES) == 12


def test_ids_unique_and_stable():
    ids = [t["id"] for t in dt.TEMPLATES]
    assert len(set(ids)) == 12, "id 중복 — 고른 템플릿이 엉뚱하게 바뀐다"
    assert ids[0] == "tpl_01" and ids[-1] == "tpl_12"


def test_every_template_has_name_and_file():
    for t in dt.TEMPLATES:
        assert t["name"], f"{t['id']} 이름 없음 — 카드에 빈칸이 뜬다"
        assert t["file"] == t["id"] + ".png"
        assert t["shape"] in ("top", "topbottom", "frame")


def test_get_returns_none_for_unknown():
    assert dt.get("tpl_99") is None, "없는 id에 None을 안 주면 호출부가 KeyError로 죽는다"
    assert dt.get("tpl_01")["id"] == "tpl_01"


def test_abs_path_points_into_static():
    p = dt.abs_path("tpl_01")
    assert p is not None and p.name == "tpl_01.png"
    assert p.parent.name == "templates"


def test_geom_not_shared_between_siblings():
    """같은 shape의 4색이 geom dict 하나를 공유하면 한 템플릿 수정이 나머지도 바꾼다(별칭 버그)."""
    top_group = [t for t in dt.TEMPLATES if t["shape"] == "top"]
    assert len(top_group) == 4
    ids_before = {id(t["geom"]) for t in top_group}
    assert len(ids_before) == 4, "geom dict가 같은 shape 형제들 사이에 공유되고 있다"


def _opaque_run(im, x, from_top=True):
    """x열을 위(또는 아래)에서부터 훑어 alpha==255가 연속으로 몇 px인지 센다."""
    w, h = im.size
    n = 0
    ys = range(h) if from_top else range(h - 1, -1, -1)
    for y in ys:
        if im.getpixel((x, y))[3] == 255:
            n += 1
        else:
            break
    return n


def _by_shape(shape):
    return next(t for t in dt.TEMPLATES if t["shape"] == shape)


def test_draw_top_matches_declared_geom_exactly():
    """Fix2 회귀 감지: bar 선언값과 실제로 칠해진 px 수가 정확히 같아야 한다."""
    t = _by_shape("top")
    im = gen.draw(t)
    assert im.mode == "RGBA" and im.size == (1080, 1920)
    measured = _opaque_run(im, 540, from_top=True)
    assert measured == t["geom"]["bar"], (
        f"선언 bar={t['geom']['bar']}인데 실제로 칠해진 건 {measured}px — off-by-one 회귀"
    )
    # 중앙은 투명해야 한다(띠 밖은 배경).
    assert im.getpixel((540, 960))[3] == 0


def test_draw_topbottom_matches_declared_geom_exactly():
    t = _by_shape("topbottom")
    im = gen.draw(t)
    top_measured = _opaque_run(im, 540, from_top=True)
    bot_measured = _opaque_run(im, 540, from_top=False)
    assert top_measured == t["geom"]["bar"]
    assert bot_measured == t["geom"]["bar"]
    assert im.getpixel((540, 960))[3] == 0


def test_draw_frame_matches_declared_geom_exactly():
    t = _by_shape("frame")
    im = gen.draw(t)
    top_measured = _opaque_run(im, 540, from_top=True)
    assert top_measured == t["geom"]["border"]
    # 좌우 테두리도 같은 두께여야 한다.
    left_measured = 0
    w, h = im.size
    for x in range(w):
        if im.getpixel((x, 960))[3] == 255:
            left_measured += 1
        else:
            break
    assert left_measured == t["geom"]["border"]
    # 중앙은 투명해야 한다(테두리 안쪽은 빈 프레임).
    assert im.getpixel((540, 960))[3] == 0


def test_committed_pngs_match_generator_bytes():
    """드리프트 가드: _COLORS/_SHAPES를 고치고 재생성을 깜빡하면 커밋된 PNG가 낡은 채로 남는다."""
    for t in dt.TEMPLATES:
        p = dt.abs_path(t["id"])
        assert p.exists(), f"{t['id']} PNG 파일이 없다 — py tools/make_deco_templates.py 실행 필요"
        committed = p.read_bytes()
        fresh = gen.draw(t)
        import io
        buf = io.BytesIO()
        fresh.save(buf, "PNG")
        assert committed == buf.getvalue(), (
            f"{t['id']}.png이 현재 메타로 재생성한 결과와 다르다 — "
            "py tools/make_deco_templates.py 로 다시 만들고 커밋할 것"
        )
