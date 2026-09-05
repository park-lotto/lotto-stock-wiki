"""⭐ 내 프리셋 · 🧰 재료 탭 · 🖼 인트로 체크 기억 (2026-09-01 사장님 3건).

서버(설정 저장)와 화면(JS)을 각각 실제로 돌려 확인한다 — 문자열 검사만으로는
"저장은 되는데 적용이 안 된다"를 못 잡는다.
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"

pytestmark = requires_node


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index("// ── 6단계 썸네일"):src.index("// ── 썸네일 끝")]


# ⭐ 글자스타일 '내 프리셋'(2026-09-01)은 **없앴다**(2026-09-05 사장님 "산만하다").
# 같은 이름의 물건이 화면에 두 개(id=myThumbPresets가 중복)라 어느 쪽이 도는지 알 수 없었고,
# 실제로 병합 뒤 MY_THUMB_PRESETS가 두 번 선언돼 스크립트가 통째로 죽는 자리였다.
# 남은 것은 '🖼 내 프리셋 — 구성 전체'(서버 thumb_presets) 하나뿐이다.

def test_재료탭은_한_번에_하나만_보인다():
    out = run_js(_slice() + """
var panes = {sticker:{hidden:false}, shape:{hidden:false}, badge:{hidden:false}};
var document = { getElementById: function(id){
  var m = /^thKit_(\w+)$/.exec(id); if (m) return panes[m[1]];
  return null;   // 탭 버튼은 없다(하네스) — 그래도 죽지 않아야 한다
}};
showThumbKit('badge');
console.log(JSON.stringify({s:panes.sticker.hidden, h:panes.shape.hidden, b:panes.badge.hidden}));
""")
    r = json.loads(out)
    assert r == {"s": True, "h": True, "b": False}


def test_모르는_탭_이름은_무시한다():
    out = run_js(_slice() + """
var panes = {sticker:{hidden:false}, shape:{hidden:true}, badge:{hidden:true}};
var document = { getElementById: function(id){
  var m = /^thKit_(\w+)$/.exec(id); return m ? panes[m[1]] : null; }};
showThumbKit('없는탭');
console.log(JSON.stringify({s:panes.sticker.hidden}));
""")
    assert json.loads(out)["s"] is False       # 아무것도 안 건드린다


# ── 서버: 개인 기본값·내 프리셋 저장 ────────────────────────────────────────
def test_설정_키는_고객마다_다르다():
    from shopping_shorts import app as A
    assert A._thumb_presets_key(7) != A._thumb_presets_key(8)
    assert A._thumb_intro_key(7) != A._thumb_intro_key(8)


def test_깨진_값이_와도_빈_목록으로_넘어간다(monkeypatch):
    """설정값이 깨져도 편집 화면이 통째로 막히면 안 된다."""
    from shopping_shorts import app as A

    class _S:
        def get_setting(self, k, d=None):
            return "{이건 JSON이 아니다"

    monkeypatch.setattr(A, "Store", lambda *_a, **_k: _S())
    assert A._load_my_thumb_presets(1) == []
