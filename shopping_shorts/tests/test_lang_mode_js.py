"""2단계 대본 영어·일본어모드 화면(2026-10-21 관제 248) — produce.html 의 진짜 함수를 잘라 node 로 돌린다.

잠그는 계약:
  · langOfText 는 서버 script_translate.lang_of 와 같은 판정(한글→ko · 가나/한자→ja · 영어 단어 3+→en)
  · s2ToggleLang(i,'ja') 는 /api/script/translate 에 lang:'ja' 를 실어 보내고 dr.lang='ja'·dr.cps_x 를 저장, 원문은 text_ko
  · s2ToggleLang(i,'ko') 는 원문으로 되돌리고 cps_x·cps_en 을 지운다
  · s2ToggleLang(i,'en') 은 종전처럼 cps_en 도 남긴다(옛 저장본 호환)
  · 외국어 카드의 예상 초는 cps_x 로 센다
"""
import json
import pathlib

from shopping_shorts import script_translate
from shopping_shorts.tests.js_harness import requires_node, run_js

PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
pytestmark = requires_node


def _slice(s, a, b):
    i = s.index(a)
    return s[i:s.index(b, i)]


def _src():
    s = PRODUCE.read_text(encoding="utf-8")
    return "\n".join([
        _slice(s, "const EN_CHARS_PER_SEC", "// ★2026-07-17 병합 해결"),
        _slice(s, "function s2SecOf(text, dr){", "function s2SecTag("),
        _slice(s, "const S2_LANG_NAME=", "// [이대로 쓰기]"),
    ])


def _run(tail, reply):
    return run_js(f"""
var SYLLABLES_PER_SEC = 5.7;
var toast = function(m){{ LOG.toast = m; }}, saveWork = function(){{}}, s2RenderDrafts = function(){{}};
var LOG = {{}};
var document = {{ getElementById: function(){{ return null; }} }};
function s2Beats(dr){{ return dr.beats; }}
function s2Cps(){{ return 7.41; }}
var fetch = async function(url, opt){{ LOG.url = url; LOG.body = JSON.parse(opt.body);
  return {{ ok: true, json: async function(){{ return {json.dumps(reply, ensure_ascii=False)}; }} }}; }};
var S2 = {{ materials: {{ topic_product: '' }}, drafts: [{{ lang: 'ko', beats: [{{text:'가격도 착한데'}}, {{text:'지금 확인해 보세요'}}] }}] }};
{_src()}
(async function(){{ {tail} }})();
""")


def test_langOfText_matches_server():
    samples = ["여러분 다이소 가시면", "If you go to Daiso, grab this.", "ダイソーに行ったら", "1980円", "AI", "", "漢字"]
    code = "console.log(JSON.stringify(%s.map(langOfText)));" % json.dumps(samples, ensure_ascii=False)
    out = run_js(_src() + "\n" + code)
    assert json.loads(out) == [script_translate.lang_of(x) for x in samples]


def test_toggle_ja_sends_lang_and_keeps_original():
    out = _run("await s2ToggleLang(0,'ja'); const dr=S2.drafts[0];"
               "console.log(JSON.stringify({body:LOG.body, lang:dr.lang, cps_x:dr.cps_x, cps_en:dr.cps_en||null,"
               " texts:dr.beats.map(b=>b.text), ko:dr.beats.map(b=>b.text_ko), sec:s2SecOf('値段も安い', dr)}));",
               {"ok": True, "lines": ["値段も安いのに", "今すぐチェック"], "lang": "ja", "cps": 6.8})
    d = json.loads(out)
    assert d["body"]["lang"] == "ja"
    assert d["lang"] == "ja" and d["cps_x"] == 6.8 and d["cps_en"] is None
    assert d["texts"] == ["値段も安いのに", "今すぐチェック"] and d["ko"] == ["가격도 착한데", "지금 확인해 보세요"]
    assert d["sec"] == round(5 / 6.8, 1)


def test_toggle_back_to_korean():
    out = _run("await s2ToggleLang(0,'ja'); s2ToggleLang(0,'ko'); const dr=S2.drafts[0];"
               "console.log(JSON.stringify({lang:dr.lang, cps_x:dr.cps_x===undefined, texts:dr.beats.map(b=>b.text)}));",
               {"ok": True, "lines": ["値段も安いのに", "今すぐチェック"], "lang": "ja", "cps": 6.8})
    d = json.loads(out)
    assert d == {"lang": "ko", "cps_x": True, "texts": ["가격도 착한데", "지금 확인해 보세요"]}


def test_toggle_en_keeps_cps_en():
    out = _run("await s2ToggleLang(0,'en'); const dr=S2.drafts[0];"
               "console.log(JSON.stringify({body:LOG.body, lang:dr.lang, cps_en:dr.cps_en, cps_x:dr.cps_x}));",
               {"ok": True, "lines": ["It is cheap", "Check it now"], "lang": "en", "cps": 14.9, "cps_en": 14.9})
    d = json.loads(out)
    assert d["body"]["lang"] == "en" and d["lang"] == "en" and d["cps_en"] == 14.9 and d["cps_x"] == 14.9


def test_card_shows_three_states():
    s = PRODUCE.read_text(encoding="utf-8")
    assert "onclick=\"s2ToggleLang(${i},'en')\"" in s
    assert "onclick=\"s2ToggleLang(${i},'ja')\"" in s
    assert "onclick=\"s2ToggleLang(${i},'ko')\"" in s
    assert "onclick=\"sbToggleLang('ja')\"" in s and "onclick=\"sbToggleLang('ko')\"" in s
    assert "s2ToggleLang(${i})\"" not in s and "sbToggleLang()\"" not in s
