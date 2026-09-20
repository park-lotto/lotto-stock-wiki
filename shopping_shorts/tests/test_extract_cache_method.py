# -*- coding: utf-8 -*-
"""추출 캐시가 **방식(기존 vs B1 프레임)을 구분**하는지 — 2026-09-05.

왜: 캐시 키가 shortcode 하나뿐이라 어느 방식으로 뽑았는지 몰랐다. 그래서
  · frame_extract_enabled를 **켜도** 이미 본 영상은 옛 결과가 그대로 나오고
  · **꺼도** 새 방식 결과가 계속 나온다
켜기 판단(서버 30편 재측정)이 바로 이 캐시에 막힌다 — 켰는데 옛 결과가 나오면
"효과가 없다"고 잘못 읽는다.

계약: save_script(..., method=) 로 방식을 같이 저장하고, get_extract(code, method=)
      에 방식을 주면 **다른 방식으로 뽑힌 캐시는 안 준다**(None → 재추출).
      method를 안 주면 종전과 완전히 같다(회귀 0).
"""
import json
import pytest

from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _script(txt="가"):
    return {"full_text": txt, "segments": [{"seg_id": "s0-0", "text": txt}]}


def test_방식을_안_주면_종전과_같다(store):
    store.save_script("abc", _script("옛방식"))
    got = store.get_extract("abc")
    assert got and got["full_text"] == "옛방식"


def test_같은_방식이면_캐시를_준다(store):
    store.save_script("abc", _script("B1결과"), method="frames")
    assert store.get_extract("abc", method="frames")["full_text"] == "B1결과"


def test_다른_방식이면_캐시를_안_준다(store):
    """켜기 전에 옛 방식으로 뽑힌 캐시가 있어도, 켠 뒤엔 다시 뽑아야 한다."""
    store.save_script("abc", _script("옛방식"), method="classic")
    assert store.get_extract("abc", method="frames") is None, "옛 방식 캐시가 새 방식으로 샜다"
    assert store.get_extract("abc", method="classic")["full_text"] == "옛방식"


def test_끄면_새방식_캐시가_안_샌다(store):
    """반대 방향도 막아야 한다 — 껐는데 B1 결과가 계속 나오면 되돌릴 수가 없다."""
    store.save_script("abc", _script("B1결과"), method="frames")
    assert store.get_extract("abc", method="classic") is None


def test_방식_모르는_옛행은_기존방식으로_친다(store):
    """이미 쌓인 캐시는 method가 비어 있다 — 전부 버리면 라이브에서 재추출 폭풍이 난다.
    옛 행은 기존 방식(classic)으로 간주해 그대로 쓰고, B1일 때만 다시 뽑는다."""
    store.save_script("abc", _script("옛날행"))          # method 없이 저장(종전 코드)
    assert store.get_extract("abc", method="classic")["full_text"] == "옛날행"
    assert store.get_extract("abc", method="frames") is None


def test_방식은_덮어쓴다(store):
    store.save_script("abc", _script("옛방식"), method="classic")
    store.save_script("abc", _script("새방식"), method="frames")
    assert store.get_extract("abc", method="frames")["full_text"] == "새방식"
    assert store.get_extract("abc", method="classic") is None


# ─── 배선 (저장소만 고치고 화면이 안 쓰면 아무 효과가 없다) ──────────────────
# 메모리 '배선은 층마다': 서버·호출부를 고쳐도 위층이 안 부르면 도착조차 안 한다.

def test_current_method가_설정을_따른다():
    from shopping_shorts import script_extract as SE
    assert SE.current_method(True) == SE.METHOD_FRAMES
    assert SE.current_method(False) == SE.METHOD_CLASSIC


def test_재추출을_결정하는_캐시조회는_전부_method를_넘긴다():
    """추출 캐시를 **다시 뽑을지 판단하는** 조회·저장이 method= 없이 남아 있으면 이 컬럼은
    채워지지도 읽히지도 않는다(조용한 무효화 — 메모리 '배선은 층마다').

    ⚠️읽기 전용 소비처(AI PICK 후보·쿠팡 근거·믹스 조회·제품명)에는 붙이면 **안 된다** —
      붙이면 멀쩡히 저장된 대본을 방식이 다르다는 이유로 못 읽는다. 그래서 개수가 아니라
      **어느 함수 안에 있는 호출인지**로 가른다."""
    import ast
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    # 재추출을 결정하는(=캐시 미스면 다시 뽑는) 함수들. 여기 안의 조회·저장은 방식을 봐야 한다.
    MUST = {
        "app.py": {"_enqueue_prewarm", "api_extract_script", "api_produce_extract_from_url",
                   "api_wiki_save", "api_produce_save_to_wiki", "api_produce_autoload"},
        "prewarm.py": {"run_prewarm"},
    }
    bare = []
    for fname, funcs in MUST.items():
        tree = ast.parse((root / fname).read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name not in funcs:
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ("get_extract", "save_script")
                        and not any(k.arg == "method" for k in node.keywords)):
                    bare.append(f"{fname}:{node.lineno} {fn.name}() {node.func.attr}")
    assert not bare, "method= 없이 남은 재추출 캐시 호출: " + ", ".join(bare)


def test_읽기전용_소비처엔_method를_안_붙인다():
    """방식을 붙이면 저장된 대본을 못 읽어 기능이 조용히 죽는다(쿠팡 근거가 사라지는 식)."""
    import ast
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name not in ("_extract_as_source_item", "_coupang_evidence",
                           "_enrich_job_extract", "api_product_prefetch_retry"):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get_extract"):
                assert not any(k.arg == "method" for k in node.keywords), (
                    f"{fn.name}()는 읽기 전용인데 method=가 붙었다 (line {node.lineno})")
