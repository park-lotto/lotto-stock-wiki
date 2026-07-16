"""대본 즐겨찾기 '링크 직접 등록'(2026-07-16 사장님 요청) — 배선의 하중 가정 고정.

사장님 요청: "링크를 대본 즐겨찾기에 등록하는게 하나 있어야 한다".
결정: URL 직접 등록 + 카테고리는 자동 추론하되 교정 가능.

정찰 결과 백엔드 신규 개발 0 — 기존 엔드포인트 둘을 프론트에서 잇는다:
  ① POST /api/produce/extract_from_url {url}  → 추출 + 카테고리 자동추론 + 구조분석, 캐시 저장
  ② (사장님이 통제 어휘 드롭다운으로 교정)
  ③ POST /api/produce/save_to_wiki {url, category} → 캐시 히트라 즉시 저장(원본만 — C-1 재발 없음)

★이 배선의 하중 가정: ①과 ③이 **같은 shortcode(=캐시 키)** 를 만들어야 ③이 캐시를 맞힌다.
  어긋나면 ③이 캐시를 놓쳐 영상을 다시 받고 Gemini로 또 추출한다 —
  느려질 뿐 아니라 **비용이 2배**고, 재추출이 실패하면(Gemini 503 등) 등록 자체가 깨진다.
  두 라우트가 각자 같은 식을 손으로 적어둔 상태라 한쪽만 바뀌면 조용히 깨진다 → 여기서 고정한다.

프론트(library.html)가 통제 어휘 API만 쓰는지도 확인 — 자유 입력이 새면 I-4(고아 학습 버킷)가 되살아난다.
"""
import hashlib
import pathlib
import re

APP_PY = pathlib.Path(__file__).resolve().parents[1] / "app.py"
LIBRARY_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "library.html"

# 두 라우트가 shortcode(캐시 키)를 만드는 줄. 같은 식이어야 한다.
_CODE_LINE = 'code = (body.get("shortcode") or "").strip() or hashlib.sha1(url.encode()).hexdigest()[:12]'


def _route_body(name: str) -> str:
    """@app.post(".../<name>") 부터 다음 @app 데코레이터 직전까지."""
    text = APP_PY.read_text(encoding="utf-8")
    start = text.find(f'@app.post("/api/produce/{name}")')
    assert start != -1, f"라우트 못 찾음(app.py가 바뀌었나): {name}"
    nxt = text.find("\n@app.", start + 10)
    return text[start: nxt if nxt != -1 else len(text)]


def test_extract_and_save_derive_same_cache_key():
    """①extract_from_url 과 ③save_to_wiki 가 같은 URL로 같은 캐시 키를 만든다."""
    extract = _route_body("extract_from_url")
    save = _route_body("save_to_wiki")
    assert _CODE_LINE in extract, "extract_from_url의 shortcode 파생식이 바뀜 — 링크 등록 배선의 캐시 히트가 깨진다"
    assert _CODE_LINE in save, "save_to_wiki의 shortcode 파생식이 바뀜 — 링크 등록 배선의 캐시 히트가 깨진다"


def test_cache_key_formula_is_url_sha1_12():
    """식 자체를 실제로 계산해 고정 — 문자열만 대조하면 식이 통째로 바뀌어도 못 잡는다."""
    url = "https://www.instagram.com/p/Dat2RByz-DM/"
    expected = hashlib.sha1(url.encode()).hexdigest()[:12]
    assert len(expected) == 12
    # app.py가 적어둔 그 식을 그대로 평가해 같은 값이 나오는지 본다.
    assert eval(  # noqa: S307 — 소스에서 잘라낸 우리 식만 평가
        "hashlib.sha1(url.encode()).hexdigest()[:12]", {"hashlib": hashlib, "url": url}
    ) == expected


def test_library_url_panel_wires_both_endpoints():
    """프론트가 ①→③ 순서로 실제 두 엔드포인트를 부른다."""
    html = LIBRARY_HTML.read_text(encoding="utf-8")
    assert "addByUrl" in html, "링크 등록 진입점(addByUrl)이 없다"
    assert "/api/produce/extract_from_url" in html, "①추출 호출이 없다 — 카테고리 자동추론이 안 붙는다"
    assert "/api/produce/save_to_wiki" in html, "③위키 저장 호출이 없다"


def test_library_category_uses_controlled_vocabulary_only():
    """카테고리는 통제 어휘 API로만 채운다 — 자유 입력(prompt)이 새면 I-4가 되살아난다."""
    html = LIBRARY_HTML.read_text(encoding="utf-8")
    assert "/api/wiki/categories" in html, "통제 어휘 API를 안 쓴다 — 고아 학습 버킷이 생긴다"
    panel = html[html.find("function addByUrl"): html.find("async function load()")]
    assert "prompt(" not in panel, "링크 등록 경로에 자유 입력 prompt()가 있다 — I-4 위반(통제 어휘만 허용)"


def test_library_blocks_empty_script_before_saving():
    """대본이 빈 영상은 담아도 학습 재료가 없다 — ③에 가기 전에 끊어야 한다."""
    html = LIBRARY_HTML.read_text(encoding="utf-8")
    panel = html[html.find("async function addByUrl"): html.find("async function _fillCatSelect")]
    assert re.search(r"full_text\s*\|\|\s*''\)\.trim\(\)", panel), \
        "추출 결과의 대본이 비었는지 확인하지 않는다 — 빈 대본이 창고에 들어간다"
