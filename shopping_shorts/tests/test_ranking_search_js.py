"""레퍼런스 랭킹 검색(2026-07-18) — 카테고리+이름+캡션 부분일치."""
import json
import pathlib
import shutil
import subprocess

import pytest

INDEX_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
NODE = shutil.which("node")

_START = "function matchesSearch("
_END = "function setSearch("   # setSearch까지 포함하려면 아래 _END2 사용

# matchesSearch + setSearch 둘 다 자른다.
_END_REAL = "// ── 검색 끝 ──"


def _slice():
    src = INDEX_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END_REAL)]


_DRIVER = r"""
(function(){
  const it = {category:'피자', name:'맛집투어', caption:'집에서 만드는 물총놀이'};
  console.log(JSON.stringify({
    byCategory: matchesSearch(it, '피자'),
    byName: matchesSearch(it, '맛집'),
    byCaption: matchesSearch(it, '물총'),
    caseInsensitive: matchesSearch({category:'IKEA',name:'',caption:''}, 'ikea'),
    trimmed: matchesSearch(it, '  피자  '),
    miss: matchesSearch(it, '이케아'),
    emptyIsAll: matchesSearch(it, ''),
    missingFields: matchesSearch({category:'요리'}, '요리'),
    // 한국어 단어경계(2026-07-18): "가지" 거짓양성 제거
    fpVerb: matchesSearch({caption:'물 한방울도 들어가지 않은 100% 과일즙'}, '가지'),
    fpCounter: matchesSearch({caption:'2가지 재료로 스콘 완성!'}, '가지'),
    fpQualifier: matchesSearch({caption:'여러 가지 재료를 넣어요'}, '가지'),
    realCompound: matchesSearch({caption:'가지볶음 초간단 레시피'}, '가지'),
    realWithJosa: matchesSearch({caption:'오늘은 가지를 볶아봤어요'}, '가지'),
    realCucumber: matchesSearch({caption:'초간단 오이무침'}, '오이'),
  }));
})();
"""


def _run(tmp_path):
    js = tmp_path / "t.js"
    js.write_text(_slice() + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_matches_across_fields(tmp_path):
    got = _run(tmp_path)
    assert got["byCategory"] and got["byName"] and got["byCaption"]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_match_rules(tmp_path):
    got = _run(tmp_path)
    assert got["caseInsensitive"] is True     # 대소문자 무시
    assert got["trimmed"] is True             # 앞뒤 공백 무시
    assert got["miss"] is False               # 없는 단어는 안 맞는다
    assert got["emptyIsAll"] is True          # 빈 검색어는 전체 통과
    assert got["missingFields"] is True       # 캡션 없는 항목도 카테고리로 맞는다


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_korean_word_boundary(tmp_path):
    """'가지' 검색이 동사·수량사에 안 걸리고 진짜 가지영상만 잡는다(2026-07-18)."""
    got = _run(tmp_path)
    assert got["fpVerb"] is False        # 들어'가지' 않은 → 거짓양성 제거
    assert got["fpCounter"] is False     # 2'가지' 재료 → 거짓양성 제거
    assert got["fpQualifier"] is False   # 여러 '가지' → 거짓양성 제거
    assert got["realCompound"] is True   # '가지'볶음 → 진짜 가지
    assert got["realWithJosa"] is True   # '가지'를 → 진짜 가지(조사 붙어도)
    assert got["realCucumber"] is True   # '오이'무침 → 진짜 오이
