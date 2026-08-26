"""꾸미기 템플릿 12종의 **유일한 정의처**.

★여기 한 곳에서만 정한다(0순위-B). PNG 생성기(tools/make_deco_templates.py)·
목록 API·렌더가 전부 이 표를 읽는다 — 색이나 이름을 다른 데 또 적으면 언젠가 어긋난다.
"""
import pathlib

# 1080x1920 기준. bar=띠 높이(px), border=테두리 두께(px).
# ★id는 (shape, color) 순서에서 나온 위치값(tpl_01..tpl_12) — 사용자 저장작업이 id를
#   그대로 들고 있으므로 두 리스트 다 **뒤에만 추가**한다. 중간 삽입·순서변경 금지
#   (예: _COLORS에 5번째 색을 앞에 끼우면 tpl_02가 딴 색으로 바뀐다 = 저장된 선택이 조용히 뒤바뀜).
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
            "geom": dict(_geom),   # ★복사본. 원본을 그대로 넣으면 같은 shape의 4색이 dict 하나를 공유해
            "file": _tid + ".png",  #   한 템플릿의 geom 수정이 나머지 3개도 조용히 바꾼다(별칭 버그).
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
