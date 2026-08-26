#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""체험판 제작소 '얼린 샘플 페이지' 생성기 (2026-08-20)

사장님 지시(3차, 스크린샷과 함께 — 앞서 두 번 잘못 알아들었다):
  "내가 보고 있는 페이지랑 동일한데 목업처럼 만들어서 **클릭 안 되고 API 안 나가는**
   샘플 페이지를 html로. **9단계까지 이동되는데 내가 만들어놓은 게 채워져 있게.**
   그 위에 네가 주석 설명 달고."

→ 화면을 **다시 그리지 않는다**(그게 앞선 실패였다). 진짜 `produce.html`을 **그대로 복사**해서
  ①모든 JS를 걷어내고 ②패널 전환만 하는 작은 스크립트를 새로 넣고 ③실제 작업 데이터를
  HTML에 박아 ④주석을 얹는다. 그래서 사이드바·레이아웃·색이 전부 실물과 같다.

동작 원리
  - `produce.html` 원본을 읽어 `<script>` 블록을 **전부 제거**한다(외부 src 포함).
    → fetch/onclick 배선이 통째로 사라지므로 **API가 나갈 수 없다**.
  - `onclick=` 등 인라인 핸들러를 **속성째 제거**한다(눌러도 아무 일이 없다).
  - 그 자리에 `_FREEZE_JS`(순수 패널 전환 + 주석 배치)만 넣는다. 네트워크 호출 0.
  - 오브↔패널 매핑은 원본과 **같은 값**을 쓴다(ORB_TO_PANEL=[0,8,7,1,2,3,4,5,6]).
    원본이 바뀌면 여기 상수도 같이 고쳐야 한다 — 아래 _ORB_TO_PANEL 주석 참조.

★왜 진짜 페이지를 서빙하지 않고 구워서 박나
  진짜 페이지는 열리자마자 `/api/produce/*`를 여러 개 부르는데 체험 등급엔 전부 402다.
  버튼을 하나하나 잠그는 방식은 **빠뜨린 버튼 하나가 곧 과금**이라 위험하다.
  스크립트를 통째로 걷어내면 "부를 코드 자체가 없다" → 구조적으로 안전하다.

쓰는 법:
    py tools/build_produce_intro.py --json <sample.json>
  sample.json은 produce_works.state_json에서 뽑은 것. 없으면 내장 기본값으로 굽는다.
"""
import argparse
import html
import json
import pathlib
import re
import sys
from urllib.parse import quote

HERE = pathlib.Path(__file__).resolve().parent.parent
SRC = HERE / "shopping_shorts" / "static" / "produce.html"
OUT = HERE / "shopping_shorts" / "static" / "produce_intro.html"

# ★원본 produce.html의 값과 **같아야 한다**(0순위-B). 원본이 순서를 바꾸면 여기도 바꾼다.
#   빌드 시 원본에서 실제로 읽어 대조하므로, 어긋나면 빌드가 멈춘다(아래 _check_mapping).
_ORB_TO_PANEL = [0, 8, 7, 1, 2, 3, 4, 5, 6]
_STEP_LABELS = ["영상추출/분석", "대본생성", "영상대본MIX", "고품질 자막제거", "TTS음성",
                "자막꾸미기", "썸네일", "SEO해시테크", "최종렌더"]

# 단계마다 얹을 주석(사장님이 요청한 "네가 다는 설명"). 오브 번호(0-based) → 문구.
_NOTES = {
    0: ("담은 영상을 <b>전부 받아적고</b> 화면에 뭐가 나오는지까지 읽습니다. "
        "카드마다 <b>말 있음 284자</b>처럼 받아적은 분량이 보이고, "
        "<b>자막이 아예 없는 영상도</b> 화면만 보고 알아냅니다(외국어도 그대로). "
        "왼쪽 첫 칸 <b>AI PICK</b>이 대표로 뽑힌 영상이에요. 여기서 모인 게 대본의 재료가 됩니다."),
    1: ("잘 터진 채널들의 <b>말하는 방식</b>을 학습해둔 틀 중에서 고릅니다. "
        "같은 제품이라도 틀을 바꾸면 완전히 다른 영상이 나와요. "
        "결과 대본은 <b>미끼·찔림·반전·증거·약속</b> 다섯 토막으로 나뉘고 토막마다 길이(초)가 정해집니다. "
        "마음에 안 드는 곳은 <b>그 줄만</b> 다시 뽑아요 — 전체를 새로 쓸 필요가 없습니다."),
    2: ("대사에 맞는 <b>장면을 붙이는</b> 단계입니다. 담은 영상에서 쓸 만한 장면을 찾아두고 "
        "\"주사기처럼 생겨서\"라고 말할 때 <b>실제로 그 장면이 나오게</b> 맞춥니다."),
    3: ("남의 영상에 박혀 있던 <b>자막을 지웁니다.</b> 지운 자리를 주변 화면으로 메워서 "
        "티가 안 나게 만들어요. 여기가 깔끔해야 내 자막을 새로 얹을 수 있습니다."),
    4: ("대본을 <b>성우 목소리로</b> 읽습니다. 목소리와 속도를 골라 미리 들어볼 수 있어요."),
    5: ("자막의 <b>글씨체·색·위치</b>를 꾸밉니다. 채널 분위기에 맞춰 한 번 정해두면 계속 씁니다."),
    6: ("영상 속 한 장면을 골라 <b>썸네일</b>을 만듭니다. 글자와 스티커를 얹을 수 있어요."),
    7: ("<b>제목·해시태그</b>를 만듭니다. 검색으로 들어오는 사람을 늘리는 자리예요."),
    8: ("여기까지가 <b>한 편</b>입니다. 완성 영상을 내려받거나 카톡으로 바로 보낼 수 있어요. "
        "사람이 하는 건 '어떤 영상을 담을지' 고르기와 '마음에 안 드는 곳 바꾸기' 둘뿐입니다."),
}

_SAMPLE = {"product": "다이소 자석 네일펜", "sources_thumbs": []}

# 얼린 페이지 전용 스크립트 — 네트워크 호출이 하나도 없다.
_FREEZE_JS = """
<script>
/* ★얼린 샘플 페이지(2026-08-20) — 원본 produce.html의 JS는 전부 걷어냈고,
   이 스크립트만 남는다. 하는 일은 **패널 전환과 주석 배치뿐**이며
   fetch/XHR을 일절 쓰지 않는다(체험 등급은 제작 API가 전부 402라서). */
(function(){
  var ORB_TO_PANEL = %(orb_to_panel)s;
  var STEP_LABELS  = %(step_labels)s;
  var NOTES        = %(notes)s;
  var cur = 0;

  function panels(){ return document.querySelectorAll('.panel'); }

  function showPanel(orb){
    cur = orb;
    var want = ORB_TO_PANEL[orb];
    panels().forEach(function(p){
      p.classList.toggle('show', String(p.dataset.step) === String(want));
    });
    renderOrbs();
    placeNote(orb);
    var top = document.getElementById('ssTop');
    if(top) top.scrollIntoView({behavior:'smooth', block:'start'});
  }

  function renderOrbs(){
    var bar = document.getElementById('ssOrbs');
    if(!bar) return;
    var pct = Math.round(cur / (STEP_LABELS.length - 1) * 100);
    var h = '<div class="orbline"><div class="orbfill" style="width:'+pct+'%%"></div></div>';
    STEP_LABELS.forEach(function(name, i){
      var cls = i < cur ? 'orb done' : (i === cur ? 'orb cur' : 'orb');
      h += '<div class="'+cls+'" data-orb="'+i+'"><div class="ball">'+(i<cur?'✓':(i+1))+
           '</div><div class="lb">'+name+'</div></div>';
    });
    bar.innerHTML = h;
    bar.querySelectorAll('.orb').forEach(function(o){
      o.addEventListener('click', function(){ showPanel(+o.dataset.orb); });
    });
  }

  /* 주석은 현재 패널 맨 위에 끼워 넣는다 — 단계를 옮기면 그 단계 설명으로 바뀐다. */
  function placeNote(orb){
    var old = document.getElementById('ssNote');
    if(old) old.remove();
    var want = ORB_TO_PANEL[orb];
    var p = document.querySelector('.panel[data-step="'+want+'"]');
    if(!p || !NOTES[orb]) return;
    var d = document.createElement('div');
    d.id = 'ssNote';
    d.className = 'ss-note';
    d.innerHTML = '<span class="ss-note-pin">💬</span><div><b>이 단계는 이런 걸 합니다</b><br>' +
                  NOTES[orb] + '</div>';
    p.insertBefore(d, p.firstChild);
  }

  /* 눌러도 아무 일 없게 — 남아 있는 링크·폼도 죽인다(스크립트는 이미 제거됨). */
  function deaden(){
    document.querySelectorAll('a[href]').forEach(function(a){
      var h = a.getAttribute('href') || '';
      if(h.indexOf('/pricing') === 0 || h === '/') return;   // 안내 링크 2개만 살린다
      a.removeAttribute('href');
      a.style.cursor = 'default';
    });
    document.addEventListener('submit', function(e){ e.preventDefault(); }, true);
    /* 오브 말고 다른 버튼은 눌러도 무시 */
    document.addEventListener('click', function(e){
      var t = e.target.closest('button, .btn, input[type=submit]');
      if(!t) return;
      if(t.closest('#ssOrbs') || t.closest('.ss-bar')) return;
      e.preventDefault(); e.stopPropagation();
      var tip = document.getElementById('ssTip');
      if(tip){ tip.classList.add('on'); clearTimeout(window.__tipT);
               window.__tipT = setTimeout(function(){ tip.classList.remove('on'); }, 1800); }
    }, true);
  }

  document.addEventListener('DOMContentLoaded', function(){
    deaden();
    showPanel(0);
  });
})();
</script>
"""

_FREEZE_CSS = """
<style>
/* 얼린 샘플 전용 — 원본 스타일은 손대지 않고 위에 얹기만 한다. */
  .ss-bar{position:sticky;top:0;z-index:60;background:linear-gradient(90deg,rgba(62,224,191,.16),rgba(62,224,191,.04));
    border-bottom:1px solid rgba(62,224,191,.45);padding:10px 16px;font-size:14px;color:#dff5ef}
  .ss-bar b{color:#3ee0bf}
  .ss-note{display:flex;gap:10px;background:rgba(62,224,191,.10);border:1px solid rgba(62,224,191,.35);
    border-left:4px solid #3ee0bf;border-radius:0 10px 10px 0;padding:12px 15px;margin:0 0 16px;
    font-size:14px;line-height:1.65;color:#d5e8e3}
  .ss-note b{color:#fff}
  .ss-note-pin{flex:0 0 auto;font-size:16px}
  #ssTip{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(14px);
    background:#111a27;border:1px solid #3ee0bf66;color:#dff5ef;padding:10px 18px;border-radius:10px;
    font-size:13.5px;opacity:0;pointer-events:none;transition:.22s;z-index:200}
  #ssTip.on{opacity:1;transform:translateX(-50%) translateY(0)}
  /* 얼린 페이지에서 의미 없는 조작 버튼은 눌리지 않는 느낌으로 */
  .panel button,.panel .btn{cursor:default!important}
</style>
"""


# 사이드바는 원래 sidebar.js가 그리는데 그 스크립트를 걷어냈으므로(=거기 있던 API 호출도
# 함께 사라진다), 같은 메뉴를 **정적 마크업**으로 다시 넣는다. 관리자 전용 항목
# (역대 히트작·레퍼런스 채널 관리)은 체험 사용자에게 보일 이유가 없어 뺐다.
# 링크는 실제로 쓸 수 있는 두 곳(랭킹·즐겨찾기)만 살리고 나머지는 🔒 표시만 한다.
_SIDEBAR = """
<style>
  .ss-side{position:fixed;left:0;top:0;bottom:0;width:196px;background:#0d1220;
    border-right:1px solid #1e2635;padding:16px 12px;overflow-y:auto;z-index:50}
  .ss-side .brand{font-size:16px;font-weight:800;color:#3ee0bf;margin:0 0 12px;padding:0 4px}
  .ss-side .grp{font-size:11px;color:#5f6a7d;font-weight:800;margin:14px 4px 6px}
  .ss-side a,.ss-side span.it{display:flex;align-items:center;gap:8px;padding:8px 10px;
    border-radius:8px;font-size:13.5px;color:#c3ccdb;text-decoration:none;margin-bottom:2px}
  .ss-side a:hover{background:#151d2c}
  .ss-side .on{background:#12352e;color:#3ee0bf;font-weight:800}
  .ss-side .lock{margin-left:auto;font-size:10px;color:#5f6a7d}
  .ss-acct{border:1px solid #1e2635;border-radius:10px;padding:9px 11px;margin-bottom:4px}
  .ss-acct b{font-size:13px}
  .ss-acct .tag{display:inline-block;background:#3ee0bf22;color:#3ee0bf;font-size:10px;
    font-weight:800;padding:1px 7px;border-radius:20px;margin-left:5px}
  .ss-acct .sub{font-size:11px;color:#6f7a8d;margin-top:3px}
  body{padding-left:196px}
  @media(max-width:900px){ .ss-side{display:none} body{padding-left:0} }
</style>
<aside class="ss-side">
  <p class="brand">&#128736; 숏템메이커</p>
  <div class="ss-acct"><b>체험 중</b><span class="tag">미리보기</span>
    <div class="sub">랭킹 · 즐겨찾기 이용 가능</div></div>
  <div class="grp">리서치</div>
  <a href="/">&#128202; 레퍼런스 랭킹</a>
  <a href="/">&#11088; 영상 즐겨찾기</a>
  <span class="it">&#128270; 신규채널 픽업<span class="lock">&#128274;</span></span>
  <span class="it">&#127902; 장면 라이브러리<span class="lock">&#128274;</span></span>
  <div class="grp">제작</div>
  <span class="it on">&#127916; 숏템 제작소</span>
  <div class="grp">소통</div>
  <span class="it">&#128172; 인스타 소통공간<span class="lock">&#128274;</span></span>
</aside>
"""


def _thumb(url):
    return ("/api/thumb?url=" + quote(url, safe="")) if url else ""


def _check_mapping(src_text):
    """원본의 ORB_TO_PANEL·STEP_LABELS와 이 파일의 상수가 같은지 대조한다.
    어긋나면 단계가 엉뚱한 패널을 열게 되므로 **빌드를 멈춘다**(조용한 오작동 방지)."""
    m = re.search(r"const ORB_TO_PANEL\s*=\s*\[([^\]]+)\]", src_text)
    if m:
        got = [int(x) for x in re.findall(r"\d+", m.group(1))]
        if got != _ORB_TO_PANEL:
            raise SystemExit(f"★ORB_TO_PANEL이 원본과 다르다: 원본={got} / 여기={_ORB_TO_PANEL}\n"
                             f"  tools/build_produce_intro.py의 _ORB_TO_PANEL을 원본에 맞춰라.")
    m = re.search(r'const STEP_LABELS\s*=\s*\[([^\]]+)\]', src_text)
    if m:
        got = re.findall(r'"([^"]+)"', m.group(1))
        if got and got != _STEP_LABELS:
            raise SystemExit(f"★STEP_LABELS가 원본과 다르다: 원본={got}\n  _STEP_LABELS를 맞춰라.")


def _strip_scripts(t):
    """<script>…</script>를 전부 제거(외부 src 포함). 이게 API 차단의 핵심이다."""
    t = re.sub(r"<script\b[^>]*>.*?</script>", "", t, flags=re.S | re.I)
    t = re.sub(r"<script\b[^>]*/?>", "", t, flags=re.I)
    return t


def _strip_handlers(t):
    """인라인 이벤트 핸들러(onclick/onchange/…)를 속성째 제거."""
    return re.sub(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", t, flags=re.I)


def _strip_comments(t):
    """HTML 주석 제거. 두 가지 이유가 있다:
      ① 원본 주석엔 내부 설계 메모·엔드포인트 이름(GET /api/produce/works 등)이 적혀 있다 —
         체험 사용자에게 보일 이유가 없다.
      ② 그 문자열 때문에 '이 페이지에 /api/produce가 없다'는 자가검증이 오탐한다.
         (주석은 실행되지 않으니 위험은 아니지만, 검증을 무디게 만드는 게 더 나쁘다)"""
    return re.sub(r"<!--.*?-->", "", t, flags=re.S)


def _fill_sources(t, sample):
    """1단계 '담은 영상' 칸에 실제 썸네일을 채운다(빈 화면이면 설명이 안 되니까)."""
    thumbs = [x for x in (sample.get("sources_thumbs") or []) if x]
    if not thumbs:
        return t
    cards = []
    for i, u in enumerate(thumbs[:5]):
        badge = ('<span class="ss-pick">AI PICK</span>' if i == 0
                 else '<span class="ss-chk">✓</span>')
        cards.append(
            f'<div class="ss-vcard">{badge}'
            f'<img src="{html.escape(_thumb(u))}" loading="lazy" alt="담은 영상 {i+1}">'
            f'<span class="ss-play">▶</span></div>')
    block = (
        '<style>'
        '.ss-vwrap{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 4px}'
        '.ss-vcard{position:relative;width:118px;height:157px;border-radius:10px;overflow:hidden;'
        'background:#141b2a;border:1px solid #1e2635;flex:0 0 auto}'
        '.ss-vcard img{width:100%;height:100%;object-fit:cover;display:block}'
        '.ss-play{position:absolute;inset:0;margin:auto;width:32px;height:32px;background:rgba(0,0,0,.5);'
        'border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px}'
        '.ss-pick{position:absolute;top:6px;left:6px;z-index:2;background:#f5b53f;color:#3a2800;'
        'font-size:9.5px;font-weight:800;padding:2px 6px;border-radius:4px}'
        '.ss-chk{position:absolute;top:6px;right:6px;z-index:2;background:#3ee0bf;color:#063;'
        'width:17px;height:17px;border-radius:50%;font-size:10px;font-weight:800;display:flex;'
        'align-items:center;justify-content:center}'
        '</style>'
        f'<div class="ss-vwrap">{"".join(cards)}</div>'
        '<div style="font-size:12px;color:#8b95a8;margin-bottom:6px">🎞 담은 영상 '
        f'{len(thumbs)}개 · 화면 {len(thumbs)}개 담김 (믹스)</div>')
    # 1단계 패널(data-step="0") 안쪽 맨 앞에 끼워 넣는다.
    return t.replace('<section class="panel" data-step="0">',
                     '<section class="panel" data-step="0">' + block, 1)


def build(src_text, sample):
    _check_mapping(src_text)
    t = _strip_scripts(src_text)
    t = _strip_handlers(t)
    t = _strip_comments(t)
    t = _fill_sources(t, sample)

    # 오브 바를 우리 것으로 갈아끼운다(원본은 JS가 그렸는데 그 JS를 걷어냈으므로).
    t = re.sub(r'<div[^>]*id="steps"[^>]*>.*?</div>',
               '<div id="ssTop"></div><div class="orbbar" id="ssOrbs"></div>',
               t, count=1, flags=re.S)
    if 'id="ssOrbs"' not in t:      # id="steps"를 못 찾았을 때의 안전망
        t = t.replace('<section class="panel"',
                      '<div id="ssTop"></div><div class="orbbar" id="ssOrbs"></div>'
                      '<section class="panel"', 1)

    banner = (
        '<div class="ss-bar">👀 <b>미리보기입니다.</b> 실제로 만들어진 영상 한 편이 '
        '어떻게 만들어졌는지 <b>화면 그대로</b> 보여드립니다. '
        '위 <b>단계를 눌러</b> 1~9단계를 둘러보세요 — <b>고치거나 새로 만들 수는 없습니다.</b> '
        '<a href="/pricing" style="color:#3ee0bf;font-weight:800">이용권 보기 →</a></div>')
    tip = '<div id="ssTip">🔒 미리보기라 눌러도 동작하지 않아요. 이용권을 시작하면 열립니다.</div>'

    t = t.replace("</head>", _FREEZE_CSS + "</head>", 1) if "</head>" in t else _FREEZE_CSS + t
    js = _FREEZE_JS % {
        "orb_to_panel": json.dumps(_ORB_TO_PANEL),
        "step_labels": json.dumps(_STEP_LABELS, ensure_ascii=False),
        "notes": json.dumps(_NOTES, ensure_ascii=False),
    }
    if "<body" in t:
        t = re.sub(r"(<body[^>]*>)",
                   lambda m: m.group(1) + _SIDEBAR + banner, t, count=1)
    else:
        t = _SIDEBAR + banner + t
    t = t.replace("</body>", tip + js + "</body>", 1) if "</body>" in t else t + tip + js
    t = t.replace("<title>", "<title>미리보기 · ", 1)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="produce_works에서 뽑은 샘플 JSON")
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    sample = dict(_SAMPLE)
    if a.json:
        raw = json.loads(pathlib.Path(a.json).read_text(encoding="utf-8"))
        sample["sources_thumbs"] = [h.get("thumbnail") for h in (raw.get("handoff") or [])
                                    if h.get("thumbnail")]

    src_text = pathlib.Path(a.src).read_text(encoding="utf-8")
    out = pathlib.Path(a.out)
    out.write_text(build(src_text, sample), encoding="utf-8")
    body = out.read_text(encoding="utf-8")

    # ── 자가검증: 이 페이지는 API를 부를 수 '없어야' 한다 ──
    scripts = re.findall(r"<script\b[^>]*>", body, flags=re.I)
    assert len(scripts) == 1, f"★<script>가 {len(scripts)}개다 — 얼린 스크립트 1개만 남아야 한다"
    for bad in ("fetch(", "XMLHttpRequest", "onclick=", "onchange=", "/api/produce"):
        assert bad not in body, f"★{bad} 가 남아 있다 — API가 나갈 수 있다"
    assert 'id="ssOrbs"' in body, "★오브 바가 없다 — 단계 이동이 안 된다"
    assert body.count('class="panel') >= 9, "★패널이 9개 미만이다"
    print(f"생성 완료: {out} ({out.stat().st_size:,} bytes)")
    print("자가검증 통과: script 1 (frozen only) / fetch,onclick,api 0 / "
          f"panels {body.count(chr(34) + 'class=' + chr(34))and body.count('class=' + chr(34) + 'panel')} / notes {len(_NOTES)}")


if __name__ == "__main__":
    sys.exit(main())
