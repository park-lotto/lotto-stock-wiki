"""6단계 SEO — 잠근 카드는 「AI로 전체 생성」에도 살아남는다(2026-07-17 리뷰 Major).

리뷰가 잡은 것: 전체 생성이 `SEO = d.seo`로 통째 교체하고 자물쇠 **표시만** 되살렸다.
사장님이 제목을 다듬고 🔒을 눌러도, 태그가 마음에 안 들어 전체 생성을 누르면 잠근 제목이
AI 제목으로 덮였다. 🔒 아이콘은 그대로라 화면이 "잠겨 있다"고 거짓말하고, seoSave()가
즉시 DB에 커밋해 원본은 복구 불가였다.

produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다
(test_produce_preview_gate.py·test_produce_mix_regen.py와 같은 방식 — 재구현이 아니다).

⚠️하네스가 계약을 발명하지 않도록: SEO·MIX_JOB은 페이지가 실제로 쓰는 전역 그대로 두고,
fetch만 가짜 응답을 준다. 하네스가 없는 필드를 지어내면 0% 동작도 초록이 된다(실사고 이력).
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

# SEO_CARD_KEYS = 부분 재생성이 갈아끼울 것 / 전체 생성이 잠금 시 지킬 것의 단일 출처.
_START = "const SEO_CARD_KEYS = {"
_END = "async function seoSave(){"

_HARNESS = r"""
'use strict';
const _els = {};
function _el(){ return { textContent:'', disabled:false, innerHTML:'' }; }
global.document = { getElementById(id){ return (_els[id] = _els[id] || _el()); } };
global.alert = () => {};
global.renderSeo = () => {};
global.seoSave = async () => { global.__saved = JSON.parse(JSON.stringify(global.SEO)); };
global.MIX_JOB = 'job1';
global.HANDOFF = [];
global.fetch = async (url, opts) => {
  global.__sent = JSON.parse(opts.body);
  return { ok: true, json: async () => ({ ok: true, seo: global.__fresh }) };
};
"""

_DRIVER = r"""
(async () => {
  // 사장님이 제목을 손으로 고르고 🔒 잠갔다. 태그·설명은 안 잠갔다.
  global.SEO = {
    title: '내가 고른 제목',
    title_candidates: [{text:'내가 고른 제목', why:'손으로', keywords:['k']}],
    description: '내가 쓴 설명',
    tags: ['옛태그'],
    cta: { youtube: '내 CTA' },
    keyword_stats: [{keyword:'k', verdict:'blue'}],
    locked: { title: true },
  };
  // AI가 전부 새로 뱉었다(제목 포함).
  global.__fresh = {
    title: 'AI가 쓴 제목',
    title_candidates: [{text:'AI가 쓴 제목', why:'ai', keywords:['x']}],
    description: 'AI 설명',
    tags: ['새태그1','새태그2'],
    cta: { youtube: 'AI CTA' },
    keyword_stats: [{keyword:'x', verdict:'red'}],
  };
  await seoGenerate();          // ★전체 생성(only 없음)
  console.log(JSON.stringify({
    title: global.SEO.title,
    title_cand: global.SEO.title_candidates[0].text,
    description: global.SEO.description,
    tags: global.SEO.tags,
    locked: global.SEO.locked,
    sent_locked: global.__sent.locked,
    saved_title: global.__saved && global.__saved.title,
  }));
})();
"""


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i, j = src.index(_START), src.index(_END)
    return src[i:j]


def _run(tmp_path):
    js = tmp_path / "t.js"
    js.write_text(_HARNESS + _slice() + _DRIVER, encoding="utf-8")
    # ★encoding="utf-8" 필수. text=True만 주면 윈도우 로케일(cp949)로 디코딩하다가
    # 한글 출력에서 리더 스레드가 UnicodeDecodeError로 죽는데 **그 예외가 삼켜져서**
    # returncode는 0인데 stdout만 None으로 온다(실측). 다른 JS 테스트들은 출력이
    # 아스키뿐이라 안 걸렸다.
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_full_generate_keeps_locked_title(tmp_path):
    """★잠근 제목이 전체 생성에도 살아남는다 — 이게 리뷰가 잡은 Major의 실물."""
    got = _run(tmp_path)
    assert got["title"] == "내가 고른 제목"          # AI 제목으로 안 덮인다
    assert got["title_cand"] == "내가 고른 제목"     # 딸린 추천 목록도 같이 지킨다
    assert got["saved_title"] == "내가 고른 제목"    # DB에 커밋되는 값도 같다(복구 불가라서)


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_full_generate_replaces_unlocked_cards(tmp_path):
    """안 잠근 건 새로 갈린다 — 안 그러면 전체 생성이 아무것도 안 하는 셈이다."""
    got = _run(tmp_path)
    assert got["description"] == "AI 설명"
    assert got["tags"] == ["새태그1", "새태그2"]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_full_generate_sends_locked_to_server(tmp_path):
    """잠금을 서버에도 보낸다 — 서버가 잠긴 내용을 프롬프트에 실어야 AI가 거기 맞춰 쓴다.
    예전엔 only일 때만 보내서 전체 생성은 잠금을 아예 몰랐다."""
    got = _run(tmp_path)
    assert got["sent_locked"] == {"title": True}


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_full_generate_keeps_lock_flags(tmp_path):
    """자물쇠 표시가 유지된다(표시만 남고 내용이 날아가던 게 원래 결함이다)."""
    got = _run(tmp_path)
    assert got["locked"] == {"title": True}
