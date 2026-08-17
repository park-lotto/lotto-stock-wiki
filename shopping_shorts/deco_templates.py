"""꾸미기 템플릿 12종의 **유일한 정의처**.

★여기 한 곳에서만 정한다(0순위-B). PNG 생성기(tools/make_deco_templates.py)·
목록 API·렌더가 전부 이 표를 읽는다 — 색이나 이름을 다른 데 또 적으면 언젠가 어긋난다.
"""
import pathlib

# 1080x1920 기준. bar=띠 높이(px), border=테두리 두께(px).
_COLORS = [
    ("코랄", "#FF5A5F"),
    ("민트", "#22C7B8"),
    ("옐로", "#FFC531"),
    ("네이비", "#2B3A67"),
]
_SHAPES = [
    ("top", "상단 띠", {"bar": 190}),
    ("topbottom", "상단+하단 띠", {"bar": 165}),
    ("frame", "테두리", {"border": 26}),
]

TEMPLATES = []
_n = 0
for _shape, _slabel, _geom in _SHAPES:
    for _cname, _hex in _COLORS:
        _n += 1
        _tid = f"tpl_{_n:02d}"
        TEMPLATES.append({
            "id": _tid,
            "name": f"{_slabel} · {_cname}",
            "shape": _shape,
            "color": _hex,
            "geom": _geom,
            "file": _tid + ".png",
        })

_BY_ID = {t["id"]: t for t in TEMPLATES}
_DIR = pathlib.Path(__file__).resolve().parent / "static" / "templates"


def get(tpl_id):
    """없는 id면 None. ★KeyError를 던지지 않는다 — 옛 작업이 지워진 템플릿을 가리킬 수 있다."""
    return _BY_ID.get(tpl_id)


def abs_path(tpl_id):
    """렌더가 쓸 실제 파일 경로. 메타에 없으면 None(파일 존재 여부는 호출부가 확인)."""
    t = get(tpl_id)
    return (_DIR / t["file"]) if t else None
