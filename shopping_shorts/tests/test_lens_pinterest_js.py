"""렌즈 핀터레스트 노출 — 프론트 배선(2026-08-29 사장님 "핀터레스트 검색결과도 노출").

서버(lens_discover)가 영상 핀만 보내주므로 프론트 몫은 셋뿐이다:
  ① LENS_PLATFORMS에 pinterest가 있어야 카드 라벨·정렬이 그려진다
     (없으면 라벨이 빈 문자열로 뜨고 정렬은 ??9 폴백 — 조용히 어긋난다)
  ② 정렬 우선순위(_LENS_ORDER)는 배열에서 **자동 생성**돼야 한다(0순위-B)
  ③ 재생은 기존 play_url 경로(/api/video 프록시)를 그대로 탄다 — 새 분기를 만들지 않는다
"""
import json
import pathlib
import shutil

import pytest
from shopping_shorts.tests.js_harness import run_js_proc

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _platforms_slice(src):
    """const LENS_PLATFORMS=[...] ~ _LENS_ORDER=... 까지 — 실제 코드 그대로 잘라 실행한다."""
    i = src.index("const LENS_PLATFORMS=")
    j = src.index("let LENS_STATE", i)
    return src[i:j]


def test_핀터레스트가_플랫폼목록에_있고_정렬은_자동생성(monkeypatch=None):
    if not shutil.which("node"):
        pytest.skip("node 없음")
    src = INDEX.read_text(encoding="utf-8")
    body = (_platforms_slice(src) + "\n"
            "const pin=LENS_PLATFORMS.find(p=>p.k==='pinterest');\n"
            "console.log(JSON.stringify({label: pin&&pin.label,"
            " order:_LENS_ORDER['pinterest'],"
            " n:LENS_PLATFORMS.length,"
            " yt:_LENS_ORDER['youtube'],"
            " nv:_LENS_ORDER['naverclip'],"
            " keys:LENS_PLATFORMS.map(p=>p.k)}));")
    r = run_js_proc(body, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["label"] == "📌 핀터레스트"
    # 배열에서 자동 생성된 정렬 키가 있어야 카드 정렬(??9 폴백)이 안 어긋난다.
    # ★"마지막이어야 한다"고 못박지 않는다(2026-09-08) — 플랫폼이 늘 때마다 깨지고,
    #   이 테스트가 지키려는 건 순서 하나가 아니라 **키가 자동 생성되는가**다.
    assert isinstance(out["order"], int) and 0 <= out["order"] < out["n"]
    # 렌즈가 유튜브를 2건 정도만 주므로 유튜브보다 뒤에 온다(2026-08-16 사장님 정렬).
    assert out["order"] > out["yt"]
    # ★네이버클립도 목록에 있어야 한다(2026-09-08 사장님 "네이버랑 핀터레스트는 안 나오는데?").
    #   kw_search._CHAIN엔 08-30부터 있었는데 이 목록에만 없어서, 결과를 정상으로
    #   가져와도 카드 필터(st.on)가 통째로 잘라내 화면에 안 보였다.
    assert "naverclip" in out["keys"], "네이버클립이 빠지면 결과가 있어도 화면에 안 뜬다"
    assert isinstance(out["nv"], int)


def test_재생은_기존_play_url_경로를_탄다():
    """lensPlayInline의 play_url 분기(랭킹 /api/video 프록시)가 첫 분기로 남아 있어야
    핀터레스트 mp4가 새 코드 없이 재생된다. 이 줄이 사라지면 핀터레스트는
    _lensMediaId가 id를 못 뽑아 전부 '원본 열기' 오버레이로 떨어진다."""
    src = INDEX.read_text(encoding="utf-8")
    assert "if(it.play_url){ img.dataset.vurl='/api/video?url='+encodeURIComponent(it.play_url); return playInline(img); }" in src
