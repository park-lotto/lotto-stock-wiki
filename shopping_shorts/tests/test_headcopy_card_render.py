"""헤드카피 후보 카드를 **실제로 그려본다**(정적 검사로는 못 잡는 것).

★node --check는 문법만 본다 — 런타임 오류(TDZ·undefined 참조)는 통과시킨다
  (reference_render죽으면_전화면공백). 그래서 조각을 떼어 진짜 실행한다.

⚠️ 이 파일에서 테스트 데이터를 파이썬 문자열로 조립하지 마라 — 이스케이프가 무너져
   하네스가 죽는다(2026-08-24에 두 번 밟았다). 반드시 json.dumps로 넣는다.
⚠️ node는 이 PC에서 파일을 cp949로 읽는다 → 하네스는 utf-8-sig(BOM)로 쓴다.
"""
import json
import pathlib
import shutil
import subprocess
import tempfile

import pytest

HTML_PATH = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
HTML = HTML_PATH.read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")


def _render(list_data):
    i = HTML.index("    box.innerHTML=list.map((c,i)=>{")
    j = HTML.index("    if(msg) msg.textContent='';", i)
    frag = HTML[i:j]
    esc_fn = ('function esc(s){ return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")'
              '.replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }')
    harness = (
        esc_fn + "\n"
        + 'const document = { getElementById: id => (id==="hcColor" ? {value:"#FFD400"} : null) };\n'
        + 'const box = {innerHTML:""};\n'
        + "const list = " + json.dumps(list_data, ensure_ascii=False) + ";\n"
        + frag + "\n"
        + "console.log(JSON.stringify(box.innerHTML));\n"
    )
    f = pathlib.Path(tempfile.gettempdir()) / "hc_card_harness_test.js"
    f.write_text(harness, encoding="utf-8-sig")
    r = subprocess.run(["node", str(f)], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[:800]
    return json.loads(r.stdout.decode("utf-8", "replace").strip())


def test_two_line_text_becomes_br():
    """★두 줄로 뽑힌 문구가 카드에서도 두 줄이어야 한다(썸네일 카드와 같은 계약)."""
    html = _render([{"label": "반전형", "text": "축 처진 머리\n이제 안 해요", "why": "이유"}])
    assert "축 처진 머리<br>이제 안 해요" in html


def test_why_is_rendered():
    html = _render([{"label": "x", "text": "한 줄", "why": "궁금증을 유발했습니다"}])
    assert "궁금증을 유발했습니다" in html


def test_missing_why_renders_without_crash():
    """옛 캐시엔 why가 없다 — 죽지도, 빈 칸을 그리지도 않는다."""
    html = _render([{"label": "훅형", "text": "why 없는 옛 응답"}])
    assert "why 없는 옛 응답" in html
    assert "opacity:.7;margin-top:2px" not in html   # 이유문 자리는 아예 안 그린다


def test_color_input_seeded_from_hcColor():
    """색 고르개는 지금 글자색을 보여준다 — 딴 값으로 시작하면 사장님이 오해한다."""
    html = _render([{"label": "x", "text": "문구", "why": "이유"}])
    assert 'value="#FFD400"' in html


def test_color_input_stops_propagation():
    """★색을 고를 때 카드까지 눌리면 문구가 멋대로 바뀐다."""
    html = _render([{"label": "x", "text": "문구", "why": "이유"}])
    assert "event.stopPropagation()" in html
    assert "useHeadcopyColor(0,this.value)" in html


def test_html_is_escaped():
    """대본에서 온 문자열이 그대로 태그가 되면 안 된다."""
    html = _render([{"label": "x", "text": "<script>bad</script>", "why": "<b>w</b>"}])
    assert "<script>bad" not in html
    assert "&lt;script&gt;" in html
