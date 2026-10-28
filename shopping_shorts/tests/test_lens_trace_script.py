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


def test_주소카드는_프레임을_들고와_대본분석_뒤_검색어를_다시_뽑는다():
    """2026-10-01 사장님 캡처(youtube watch?v=JnqlnQVuFz0): 추적 카드에서 '대본 분석' 뒤 검색어가 사라졌다.
    cn_search_candidates는 image_bytes 없으면 즉시 빈 리스트(video_analysis.py). 추적 카드는 프레임이
    서버에만 있어 화면 frameBlob이 없었다 → 재생성 요청에 frame 0장 → 후보 0개(서버 로그: 1초 내 200).
    서버가 이미 받은 바이트를 frame_b64로 내려주고, 화면은 랭킹 카드와 같은 자리(frameBlob)에 둔다."""
    import inspect
    body_trace = inspect.getsource(a.api_lens_trace_url)
    assert '"frame_b64"' in body_trace, "추적 응답에 프레임 바이트가 없다 — 화면이 검색어를 다시 못 뽑는다"
    idx = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    i = idx.index("async function traceByUrl")
    blk = idx[i:i + 4000]
    assert "d.frame_b64" in blk and "frameBlob:" in blk, "추적 카드 상태에 frameBlob이 없다"


def test_렌즈뭉치_조회는_shortcode로_한다_id가_두벌이라():
    """2026-10-01 사장님 "키워드 검색도 안 들어감"(서버 로그: kw/expand 요청 0건).
    주소 카드(__single__)가 #urlCardBox(706줄)에 #lensRoot·#lensKwInput을 **숨긴 채** 남기고,
    추적 모달(#scriptModal, 727줄)이 같은 id로 또 그린다 → getElementById는 앞쪽(숨은 카드)만 돌려줘
    입력칸 값은 늘 ''이고 data-sc도 '__single__'이라 모달은 응답이 와도 다시 안 그려졌다.
    조회는 _lensRoot(shortcode) 한 곳(data-sc로 찾는다)."""
    idx = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "getElementById('lensRoot')" not in idx, "id로 찾으면 숨은 주소 카드가 먼저 잡힌다"
    assert "getElementById('lensKwInput')" not in idx
    assert "function _lensRoot(" in idx
    i = idx.index("async function lensExpandKeyword")
    assert "_lensRoot(shortcode)" in idx[i:i + 600]
