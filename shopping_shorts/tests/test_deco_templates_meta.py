"""템플릿 메타 — 12종이 빠짐없이·중복 없이 정의돼 있는가."""
import pathlib

from shopping_shorts import deco_templates as dt


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
