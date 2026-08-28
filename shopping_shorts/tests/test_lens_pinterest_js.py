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
            " last:LENS_PLATFORMS[LENS_PLATFORMS.length-1].k}));")
    r = run_js_proc(body, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["label"] == "📌 핀터레스트"
    # 배열에서 자동 생성된 정렬 키가 있어야 카드 정렬(??9 폴백)이 안 어긋난다
    assert out["order"] == out["n"] - 1 and out["last"] == "pinterest"


def test_재생은_기존_play_url_경로를_탄다():
    """lensPlayInline의 play_url 분기(랭킹 /api/video 프록시)가 첫 분기로 남아 있어야
    핀터레스트 mp4가 새 코드 없이 재생된다. 이 줄이 사라지면 핀터레스트는
    _lensMediaId가 id를 못 뽑아 전부 '원본 열기' 오버레이로 떨어진다."""
    src = INDEX.read_text(encoding="utf-8")
    assert "if(it.play_url){ img.dataset.vurl='/api/video?url='+encodeURIComponent(it.play_url); return playInline(img); }" in src
