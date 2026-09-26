# -*- coding: utf-8 -*-
"""주소로 가져온 카드(__trace__/__single__)의 '대본 분석 후 찾기'(2026-09-26 사장님 "왕혜원 영상 결과 없음").

서버 로그: POST /api/extract_script?shortcode=__trace__ → 404 ×7. 가짜 ID는 스냅샷에 없다 → 주소로 추출한다.
저장 코드는 검색어 생성이 대본을 찾는 열쇠(_lens_script_code)와 같아야 한다."""
from pathlib import Path
import shopping_shorts.app as a

ROOT = Path(__file__).resolve().parents[1]


def test_주소카드_응답에_대본코드가_실린다():
    src = a.__dict__  # 함수 본문을 소스로 확인(엔드포인트는 네트워크·과금이 붙어 직접 못 돈다)
    import inspect
    body_trace = inspect.getsource(a.api_lens_trace_url)
    body_single = inspect.getsource(a.api_lens_single)
    assert '"script_code": _lens_script_code(url, "")' in body_trace
    assert '"script_code": _lens_script_code(url, "")' in body_single
    assert a._lens_script_code("https://www.youtube.com/shorts/9OslEZJs_is", "") == "9OslEZJs_is"
    assert a._lens_script_code("https://www.youtube.com/shorts/9OslEZJs_is", "__trace__") == "__trace__",         "shortcode가 오면 그게 이긴다 — 그래서 화면이 가짜 ID를 보내면 안 된다"


def test_화면_가짜ID는_주소로_추출한다():
    idx = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    i = idx.index("async function lensExtractThenSearch")
    blk = idx[i:i + 1800]
    assert "'/api/produce/extract_from_url'" in blk and "st.srcUrl" in blk and "shortcode:(st.srcCode||undefined)" in blk
    assert "shortcode==='__trace__' || shortcode==='__single__'" in blk
    assert "srcUrl:url, srcCode:(d.script_code||'')" in idx and "srcCode:(d.script_code||it.shortcode||'')" in idx
    j = idx.index("async function fetchLensCnKeywords")
    fk = idx[j:j + 1400]
    assert "st0.srcUrl" in fk and "st0.srcCode" in fk
    assert "if(shortcode && shortcode!=='__single__') fd.append('source_shortcode', shortcode);" not in fk, "가짜 ID를 대본 열쇠로 보내던 줄"
