# -*- coding: utf-8 -*-
"""로컬 장면교체 실험 페이지 빌더 (v2 — 한 칸에 여러 장 편성).

data.json(서버 실데이터) + thumbs/*.jpg 를 읽어 자립형 index.html을 만든다.
file://에서 fetch가 막히므로 데이터는 HTML 안에 인라인으로 박는다.

v2 변경: 비트를 '장면 목록(list)'으로 다룬다. 첫 항목이 primary, 나머지가 alternates.
사람이 목록에 추가·삭제·순서변경을 직접 한다 — 사장님 손그림(한 칸에 화살표 여러 개).
"""
import json
import sys
from pathlib import Path

# 인자로 잡 폴더를 받는다(fetch.py가 out/<job_id>를 넘긴다). 없으면 이 파일 옆(옛 방식).
BASE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).parent
data = json.loads((BASE / "data.json").read_text(encoding="utf-8"))
# ★사람이 대본을 읽고 직접 고른 배치(선택). picks.json이 있으면 ④번 모드로 노출한다.
#   fetch가 data.json을 덮어써도 이 파일은 남아 배치가 유지된다.
_picks = BASE / "picks.json"
data["picks"] = json.loads(_picks.read_text(encoding="utf-8")) if _picks.exists() else None

html = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>장면교체 실험실 — 숏템메이커</title>
<style>
:root{
  --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --line:#2b3140;
  --ink:#e8ecf4; --dim:#98a2b8; --accent:#4da3ff; --good:#3ecf8e; --warn:#ffb44d; --bad:#ff6b6b;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font-family:"Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif;font-size:14px}
header{padding:12px 18px;border-bottom:1px solid var(--line);display:flex;
       align-items:center;gap:18px;flex-wrap:wrap;background:var(--panel)}
h1{font-size:16px;margin:0;font-weight:700}
.sub{color:var(--dim);font-size:12px}
.modes{display:flex;gap:8px;margin-left:auto;flex-wrap:wrap}
.mode{padding:8px 14px;border:1px solid var(--line);border-radius:8px;background:var(--panel2);
      color:var(--dim);cursor:pointer;font-size:12px;line-height:1.4;text-align:center}
.mode.on{border-color:var(--accent);color:#fff;background:#1b2a3d}
.wrap{display:grid;grid-template-columns:var(--libw,520px) 1fr;height:calc(100vh - 130px)}
.pane{overflow-y:auto;padding:14px}
.pane.left{border-right:1px solid var(--line);background:var(--panel)}
.srcgroup{margin-bottom:18px}
.srchead{font-size:12.5px;color:var(--ink);font-weight:700;margin-bottom:8px;display:flex;justify-content:space-between;gap:8px;position:sticky;top:0;background:var(--panel);padding:6px 4px;border-bottom:1px solid var(--line);z-index:2}
.thumbs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.seg{display:block}
.seg{border:1px solid var(--line);border-radius:8px;overflow:hidden;cursor:pointer;
     background:var(--panel2);position:relative;transition:.12s}
.seg:hover{border-color:var(--accent);transform:translateY(-2px)}
.seg img{width:100%;display:block;aspect-ratio:9/16;object-fit:cover}
.seg .meta{padding:5px 6px;font-size:10.5px;color:var(--ink);line-height:1.4;display:flex;flex-direction:column;gap:2px}
.seg .meta .d{color:var(--dim);font-size:10.5px;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.seg .sid{color:var(--ink);font-weight:600}
.utag{display:inline-block;font-size:9px;padding:1px 5px;border-radius:99px;margin:2px 3px 0 0;border:1px solid var(--line);color:var(--dim)}
.utag.key{border-color:var(--good);color:var(--good)}
.seg .add{position:absolute;left:5px;top:5px;background:var(--accent);color:#fff;font-size:10px;
     padding:2px 6px;border-radius:5px;opacity:0;transition:.12s}
.seg:hover .add{opacity:1}
.seg.inthis{border-color:var(--good);box-shadow:0 0 0 1px var(--good) inset}
/* 소스 영상 길이를 넘어가는 세그먼트 — 렌더하면 검은 화면/정지가 된다(2026-08-14 발각) */
.seg.oor,.item.oor,.cut.oor{border-color:var(--bad)}
.item.oor,.cut.oor{box-shadow:0 0 0 1px var(--bad) inset}
.oorbadge{color:var(--bad);font-size:11px;font-weight:700}
.seg.inthis::after{content:"이 칸에 있음";position:absolute;top:5px;right:5px;background:#000b;
     color:var(--good);font-size:9px;padding:2px 5px;border-radius:4px}
.beat{border:1px solid var(--line);border-radius:10px;margin-bottom:12px;background:var(--panel)}
.beat.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.bhead{display:flex;align-items:center;gap:9px;padding:9px 12px;background:var(--panel2);
       cursor:pointer;flex-wrap:wrap;border-radius:9px 9px 0 0}
.role{font-weight:700;font-size:13px}
.chip{font-size:10px;padding:2px 7px;border-radius:99px;border:1px solid var(--line);color:var(--dim)}
.chip.bad{border-color:var(--bad);color:var(--bad)}
.chip.good{border-color:var(--good);color:var(--good)}
.chip.warn{border-color:var(--warn);color:var(--warn)}
.narr{color:var(--dim);font-size:12px;flex:1 1 100%;line-height:1.5;border:1px dashed transparent;border-radius:5px;padding:3px 5px;outline:none}
.narr:hover{border-color:var(--line)}
.narr:focus{border-color:var(--accent);color:var(--ink);background:#0f1620}
.why{flex:1 1 100%;font-size:11.5px;color:var(--good);line-height:1.5;background:#0f2a20;border:1px solid #1f4d3a;border-radius:6px;padding:5px 8px;margin-top:2px}
.bbody{padding:10px 12px}
.lbl{font-size:11px;color:var(--dim);margin:0 0 6px}
.row{display:flex;gap:16px;flex-wrap:wrap}
.col{flex:1 1 300px;min-width:260px}
.list{display:flex;gap:6px;flex-wrap:wrap}
.item{position:relative;width:132px;border:1px solid var(--line);border-radius:6px;overflow:hidden;
      background:#000}
.item img{width:100%;display:block;aspect-ratio:9/16;object-fit:cover}
.item .n{position:absolute;left:4px;top:4px;background:#000c;color:#fff;font-size:11px;
      padding:1px 4px;border-radius:3px}
.item .ctl{display:flex;justify-content:space-between;padding:2px 3px;background:var(--panel2)}
.item .ctl span{cursor:pointer;font-size:12px;color:var(--dim);padding:0 2px}
.item .ctl span:hover{color:var(--ink)}
.item .ctl .del:hover{color:var(--bad)}
.item.first{border-color:var(--accent)}
/* 담았지만 시간이 모자라 이 칸에서는 안 나오는 장면 — 오해 방지(2026-08-13 사장님 질문) */
.item.unused{opacity:.35;filter:grayscale(1)}
.item.unused::after{content:"안 나옴";position:absolute;left:0;right:0;top:38%;text-align:center;
  font-size:9px;color:var(--warn);background:#000a;padding:2px 0}
.strip{display:flex;gap:3px;overflow-x:auto;padding-bottom:5px}
.cut{flex:0 0 auto;width:88px;border-radius:5px;overflow:hidden;border:1px solid var(--line);background:#000}
.cut img{width:100%;display:block;aspect-ratio:9/16;object-fit:cover}
.cut .t{font-size:11px;text-align:center;color:var(--dim);padding:1px 0}
.cut.mine{border-color:var(--good)}
.cut.mine .t{color:var(--good)}
.cut.long{border-color:var(--warn)}
.cut.long .t{color:var(--warn)}
.empty{color:var(--bad);font-size:11px;padding:6px 0}
footer{border-top:1px solid var(--line);padding:9px 18px;display:flex;gap:20px;
       align-items:center;background:var(--panel);flex-wrap:wrap;font-size:12px}
.kpi b{font-size:17px;color:var(--accent)}
.kpi.warnv b{color:var(--warn)}
.kpi.goodv b{color:var(--good)}
.hint{color:var(--dim);font-size:11px}
button.act{padding:5px 10px;border-radius:7px;border:1px solid var(--line);background:var(--panel2);
      color:var(--ink);cursor:pointer;font-size:11px}
button.act:hover{border-color:var(--accent)}
.ord{display:flex;gap:3px;margin-left:auto}
#player{position:fixed;right:16px;bottom:56px;width:300px;background:var(--panel);
        border:1px solid var(--accent);border-radius:10px;padding:8px;z-index:50;display:none}
#player.on{display:block}
#player #vidbox{position:relative;background:#000;border-radius:6px;overflow:hidden;aspect-ratio:9/16}
#player video{width:100%;height:100%;border-radius:6px;background:#000;display:block;aspect-ratio:9/16;object-fit:contain;position:absolute;inset:0}
.phead{display:flex;justify-content:space-between;align-items:center;font-size:11px;margin-bottom:6px}
.phead .x{cursor:pointer;color:var(--dim)}
.phead .x:hover{color:var(--bad)}
.pinfo{font-size:10px;color:var(--dim);margin-top:5px;line-height:1.4;min-height:26px}
/* 자막 트랙 — 말한 데까지 흰색, 남은 말은 흐리게(카라오케식). 어긋나면 바로 보인다 */
#subbox{margin-top:6px;min-height:42px;font-size:13px;line-height:1.5;font-weight:700;
  background:#000a;border-radius:6px;padding:6px 8px;word-break:keep-all}
#subbox .subtag{font-size:10px;color:var(--accent);font-weight:600;margin-bottom:3px}
#subbox .said{color:#fff}
#subbox .rest{color:#ffffff44}
/* 컷마다 그 시간대 자막 — '이 글자를 말할 때 이 그림' 을 한눈에 */
.cutsub{font-size:10px;color:var(--dim);line-height:1.35;padding:3px 4px;
  background:var(--panel);border-top:1px solid var(--line);min-height:30px;word-break:keep-all}
.play{position:absolute;left:5px;bottom:26px;background:#000b;color:#fff;font-size:11px;
      padding:2px 7px;border-radius:5px;cursor:pointer;z-index:2}
.play:hover{background:var(--accent)}
.item .play{left:4px;bottom:24px;font-size:11px;padding:2px 7px}
.item .cap{padding:4px 5px;font-size:10.5px;color:var(--dim);line-height:1.35;background:var(--panel);border-top:1px solid var(--line)}
.cut{cursor:pointer}
.cut:hover{border-color:var(--accent)}
</style></head><body>

<header>
  <div>
    <h1>장면교체 실험실 <span class="sub">— 로컬 전용 · 서버/라이브에 아무 영향 없음</span></h1>
    <div class="sub" id="jobline"></div>
  </div>
  <div class="modes">
    <div class="mode on" id="m-live" onclick="setMode('live')">① 지금 라이브<br><span class="sub">AI 후보 그대로</span></div>
    <div class="mode" id="m-one" onclick="setMode('one')">② 한 장만<br><span class="sub">후보 다 지움</span></div>
    <div class="mode" id="m-hand" onclick="setMode('hand')">③ 내가 편성<br><span class="sub">칸마다 직접 담기</span></div>
    <div class="mode" id="m-pick" onclick="setMode('pick')" style="display:none">④ 대본에 맞게<br><span class="sub">대사 보고 고른 배치</span></div>
  </div>
</header>

<div class="wrap">
  <div class="pane left">
    <div class="lbl" id="palhint"></div>
    <div class="lbl" id="dropmsg" style="color:var(--bad)"></div>
    <div id="palette"></div>
  </div>
  <div class="pane right">
    <div class="lbl"><button class="act" onclick="playAll(event)" style="margin-right:10px">▶ 전체 재생(칸 이어서)</button><label style="cursor:pointer;margin-right:12px"><input type="checkbox" onchange="toggleOne(this.checked)"> 1장=1컷 · 비례 배분(되돌아옴 없음)</label>아래 <b>“실제 나올 화면”</b>이 렌더 결과입니다(렌더 알고리즘 이식) ·
      <span style="color:var(--warn)">주황 = 2.5초 넘게 안 바뀌는 컷(늘어짐)</span></div>
    <div id="film"></div>
  </div>
</div>

<div id="player">
  <div class="phead"><b>미리보기</b><span class="x" onclick="stopPlay()">닫기 ✕</span></div>
  <div id="vidbox"></div>
  <div id="subbox"></div>
  <audio id="bgaudio"></audio>
  <div class="pinfo" id="pinfo">장면의 ▶ 또는 칸의 “이 칸 재생”을 누르세요<br>
    <span style="opacity:.7">칸 재생 = 화면+음성+자막을 함께 봅니다(렌더 안 함)</span><br>
    <label style="cursor:pointer"><input type="checkbox" id="subcut" checked
      onchange="subPerCut=this.checked"> 지금 컷 번호 표시</label></div>
</div>

<footer>
  <div class="kpi">총 컷 <b id="k-cuts">-</b></div>
  <div class="kpi">평균 컷길이 <b id="k-avg">-</b>초</div>
  <div class="kpi" id="k-long-wrap">늘어진 컷 <b id="k-long">-</b></div>
  <div class="kpi" id="k-own-wrap">내가 고른 화면 <b id="k-own">-</b></div>
  <button class="act" onclick="reset()">처음으로(저장 지움)</button>
  <span id="savedmsg" class="hint" style="color:var(--good)"></span>
  <div class="hint">왼쪽 장면 <b>두 번 클릭</b> = 선택한 칸에 담기 / 칸 안 썸네일은 <b>끌어서 순서 변경</b>, <b>두 번 클릭 = 삭제</b></div>
</footer>

<script>
const DATA = __DATA__;
const MAX_SHOT = 2.2, MIN_CLIP = 0.8, EPS = 1e-3, LONG_CUT = MAX_SHOT + 0.05;   // 상한을 넘긴 컷 = 소재가 모자라 늘린 것

// 소스 영상 길이를 넘는 구간인가 — 실측(job 409f894230c6): s1-10이 100~104초인데
// s1.mp4는 78.5초였다. 렌더하면 그 컷은 실체가 없다. 눈에 보이게 표시한다.
// 최소 컷 길이(0.8초)에 못 미치는 장면 — 담아도 화면에 **안 나온다**(라운드로빈이 건너뛴다).
// 2026-08-14 사장님 "여 씬이 들어가면 뭔가 꼬인다": 0.7초짜리를 담으면 그 장면은 사라지고,
// 남은 소재로 나레이션 길이를 채우느라 다른 컷이 길게 늘어난다. 담기 전에 알려준다.
// ★장면을 결(役)로 묶는다(2026-08-14 사장님 "완성품·조리 이런 식으로 나누고 후킹용·조리용·
//   CTA용 태그"). 새 판단을 만들지 않는다 — 추출이 이미 붙여둔 shot_role/is_key를 그대로 쓴다
//   (완성 / after=결과·증거 / 사용중=조리·사용 / 기타). 실측 분포 9·5·41·1.
const GROUPS = [
  {key:'완성',   title:'🏆 완성품',          hint:'훅·CTA에 좋다'},
  {key:'after',  title:'✅ 결과·증거',       hint:'쪼갠 단면·먹는 반응 — 결과 칸에 좋다'},
  {key:'굽기',   title:'🔥 굽기·완성 직전',  hint:'오븐·가열 — 과정의 절정'},
  {key:'마무리', title:'🍫 마무리·데코',      hint:'초콜릿·토핑 — 완성 직전 한 끗'},
  {key:'재료',   title:'🥣 재료·반죽 준비',  hint:'섞기·짜기 — 해결 칸에 좋다'},
  {key:'기타',   title:'그 밖의 장면',       hint:''},
];
// ★조리(shot_role='사용중')를 '굽기'와 '재료 준비'로 한 겹 더 가른다(2026-08-14 사장님
//   "완성품 조리랑 재료조리는 구분해서 나와야"). 이건 **실험실에서 고르기 쉬우라고 하는
//   화면 분류**일 뿐 배치 로직과 무관하다 — 라이브 판단을 새로 만드는 게 아니다.
const _BAKE = ['오븐', '굽', '예열', '구워', '식힘망'];
// 다 만든 것 위에 하는 작업 — 사장님 지적(Db9O4pqza74-10 '초콜릿 묻은 쿠키 위에 견과류를
// 얹는 작업'이 '재료 준비'로 갔다). 굽기보다 뒤 단계라 따로 세운다.
const _DECO = ['얹', '적시', '묻은', '묻힌', '토핑', '데코', '장식', '뿌리'];
function groupOf(sid){
  const s0 = DATA.segments[sid] || {};
  const r = s0.shot_role || '기타';
  if (r === '사용중'){
    const d = (s0.scene_desc || '') + ' ' + (s0.action || '') + ' ' + (s0.change || '');
    if (_DECO.some(w => d.includes(w))) return '마무리';
    return _BAKE.some(w => d.includes(w)) ? '굽기' : '재료';
  }
  return GROUPS.some(g => g.key === r) ? r : '기타';
}
// 용도 배지 — 위 결에서 바로 파생한 **제안**이다(강제 아님, 담는 건 사장님 판단).
function useTags(sid){
  const s0 = DATA.segments[sid] || {}, r = groupOf(sid), t = [];
  if (r === '완성'){ t.push('후킹용'); t.push('CTA용'); }
  if (r === 'after'){ t.push('후킹용'); t.push('결과용'); }
  if (r === '굽기') t.push('굽기용');
  if (r === '마무리') t.push('마무리용');
  if (r === '재료') t.push('조리용');
  if (s0.is_key) t.push('실증');
  return t;
}
// ★비슷한 장면 묶기(2026-08-14 사장님 "이건 두 개 중복 / 비슷한 거 묶어보고").
//   썸네일을 8x8 흑백으로 줄인 평균해시를 fetch가 실어 온다. 설명·시각이 달라도 **그림이
//   사실상 같은** 컷을 잡는다. 실측(job 409f894230c6): s3-2↔s3-20 거리0, s3-5↔s3-21 거리1,
//   s3-1↔s3-18 거리4(사장님이 지목한 그 쌍).
const DUP_MAX = 8;                 // 해밍거리 이 이하면 '비슷'
let hideDup = true;                // 비슷한 것은 대표 1장만 보이기(기본 켬)
function _hash(sid){ return (DATA.phash || {})[sid] || ''; }
function _dist(a, b){
  if (!a || !b || a.length !== b.length) return 99;
  let n = 0; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) n++;
  return n;
}
// 비슷한 것끼리 묶어 대표(가장 이른 장면)를 정한다. {sid: {rep, mates:[...]}}
let DUPS = null;
function dupMap(){
  if (DUPS) return DUPS;
  DUPS = {};
  const ids = Object.keys(DATA.segments).filter(id => !outOfRange(id) && _hash(id));
  const seen = new Set();
  for (const a of ids){
    if (seen.has(a)) continue;
    const group = [a];
    for (const b of ids){
      if (b === a || seen.has(b)) continue;
      if (_dist(_hash(a), _hash(b)) <= DUP_MAX) group.push(b);
    }
    group.sort((x, y) => DATA.segments[x].start - DATA.segments[y].start);
    const rep = group[0];
    group.forEach(g => { seen.add(g); DUPS[g] = {rep, mates: group.filter(x => x !== g)}; });
  }
  return DUPS;
}
function isDupOf(sid){ const d = dupMap()[sid]; return (d && d.rep !== sid) ? d.rep : null; }
function dupMates(sid){ const d = dupMap()[sid]; return d ? d.mates : []; }
function toggleDup(on){ hideDup = on; render(); }
function tooShort(sid){
  const s0 = DATA.segments[sid]; if (!s0) return false;
  return (s0.end - s0.start) < MIN_CLIP - EPS;
}
function outOfRange(sid){
  const s0 = DATA.segments[sid]; if (!s0) return false;
  const d = (DATA.src_duration || {})[s0.video_id];
  return !!d && s0.end > d + 0.2;
}
function esc(t){ return String(t==null?'':t).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

// ── 자막·음성 트랙(2026-08-14 사장님 "결국 자막이랑 맞아떨어지는 걸 봐야 한다") ──────
// 렌더를 다시 돌리지 않는다. 서버가 이미 만들어 둔 것을 그대로 겹쳐 재생한다:
//   화면 = 소스 mp4의 구간(무음)  /  음성 = tts/beat_N.mp3  /  자막 = DATA.captions
// ★자막 구절·타이밍은 fetch가 **라이브 렌더와 같은 함수**(_caption_segments,
//   _caption_durations)로 계산해 실어 온다. 여기서 다시 나누면 두 벌이 되어 반드시
//   어긋난다(0순위-B). 예전엔 글자 타임스탬프(align.json)를 컷 경계로 잘라 썼는데
//   ①문장이 어절 중간에서 잘리고 ②align은 무음 트림 전 기준(8.16초)이라 실제 mp3
//   (6.10초)보다 느리게 흘렀다 — 사장님이 둘 다 지적했다.
let audioEl = null;
function audio(){ return audioEl || (audioEl = document.getElementById('bgaudio')); }
function capsOf(i){ return (DATA.captions || {})[String(i)] || []; }
// 구간 [a,b)에 걸치는 자막 구절들 — 자르지 않고 구절 통째로 돌려준다.
function capsIn(i, a, b){
  return capsOf(i).filter(c => c.start < b - 1e-3 && c.end > a + 1e-3);
}
function capAt(i, t){
  const cs = capsOf(i);
  return cs.find(c => t >= c.start - 1e-3 && t < c.end) || null;
}

let mode = 'live';
let seqBeat = null;   // 지금 재생 중인 칸(자막·음성 트랙 기준)
let playKey = null;   // 지금 재생 중인 대상 — 같은 것을 다시 누르면 정지(토글)
let seqBounds = [];   // 컷별 [시작,끝) 초 — 자막을 컷 단위로 끊는 기준
let subPerCut = true; // 미리보기에 '컷 n/N' 표시(자막 자체는 라이브와 같은 구절 단위)
let sel = 0;
let lists = [];              // 비트별 장면 seg_id 목록(첫 항목이 primary)
const chosen = new Set();    // 사람이 손으로 담은 seg_id

function baseList(b){
  return [b.primary, ...(b.alternates || [])].filter(Boolean).map(s => s.seg_id);
}
function initLists(){
  lists = DATA.beats.map(b => {
    const all = baseList(b);
    if (mode === 'one') return all.slice(0, 1);
    if (mode === 'hand') return all.slice(0, 1);   // 시작점 1장, 나머지는 사람이 담는다
    if (mode === 'pick'){                          // 대본을 읽고 고른 배치(picks.json)
      const l = ((DATA.picks || {}).lists || [])[b.beat_idx];
      return (l && l.length) ? l.slice() : all;
    }
    return all;
  });
}

// video_assemble._plan_beat_clips 이식(라운드로빈 + shortfall 1순위 근사)
let onePerSeg = false;   // ★1장=1컷(라이브 config.ONE_CLIP_PER_SEGMENT와 같은 규칙)
function toggleOne(on){ onePerSeg = on; render(); }
function planClips(segIds, ttsDur){
  const segments = segIds.map(id => ({...DATA.segments[id], seg_id: id})).filter(s => s.start != null);
  const clips = []; let filled = 0;
  if (!segments.length) return clips;
  if (onePerSeg){
    // 1장=1컷 · 비례 배분(라이브 _plan_beat_clips one_per_seg와 같은 규칙).
    // 나레이션 시간을 담은 장면들에 **길이 비례**로 나눈다 — 남으면 줄이고 모자라면 늘린다.
    // 담은 게 전부·순서대로·한 번씩 나오고, 긴 장면은 길게 짧은 장면은 짧게 비율이 유지된다.
    let usable = segments.filter(g => g.end - g.start > EPS);
    while (usable.length > 1){
      const total = usable.reduce((a,g) => a + (g.end - g.start), 0);
      const scale = total > EPS ? ttsDur / total : 0;
      const small = usable.filter(g => (g.end - g.start) * scale < MIN_CLIP - EPS);
      if (!small.length) break;
      usable = usable.filter(g => !small.includes(g));
    }
    if (usable.length){
      const total = usable.reduce((a,g) => a + (g.end - g.start), 0);
      const scale = total > EPS ? ttsDur / total : 0;
      usable.forEach((seg, k) => {
        let take = (seg.end - seg.start) * scale;
        if (k === usable.length - 1) take = Math.max(0, ttsDur - filled);
        if (take <= EPS) return;
        clips.push({seg_id: seg.seg_id, video_id: seg.video_id, start: seg.start, dur: take});
        filled += take;
      });
    }
    return clips;
  }
  if (segments.length > 1){
    const pos = segments.map(s => s.start);
    let oi = 0, guard = 0;
    while (ttsDur - filled > EPS && guard++ < 2000){
      let i = oi % segments.length; oi++;
      let seg = segments[i];
      const avail = seg.end - pos[i];
      if (avail <= EPS){
        if (segments.every((s,k) => s.end - pos[k] <= EPS)) break;
        continue;
      }
      let take = Math.min(avail, MAX_SHOT, ttsDur - filled);
      if (take < MIN_CLIP - EPS){
        if (ttsDur - filled < MIN_CLIP - EPS) break;
        const j = segments.findIndex((s,k) => s.end - pos[k] >= MIN_CLIP - EPS);
        if (j < 0) break;
        i = j; seg = segments[i];
        take = Math.min(seg.end - pos[i], MAX_SHOT, ttsDur - filled);
      }
      clips.push({seg_id: seg.seg_id, video_id: seg.video_id, start: pos[i], dur: take});
      pos[i] += take; filled += take;
    }
  } else {
    const seg = segments[0];
    const take = Math.min(seg.end - seg.start, ttsDur);
    clips.push({seg_id: seg.seg_id, video_id: seg.video_id, start: seg.start, dur: take});
    filled += take;
  }
  const short = ttsDur - filled;
  if (short > EPS && clips.length) clips[clips.length - 1].dur += short;   // 그 장면이 계속 나온다
  return clips;
}

function render(){
  document.getElementById('jobline').textContent =
    `job ${DATA.job_id} · 칸(멘트) ${DATA.beats.length}개 · 쓸 수 있는 장면 ${Object.keys(DATA.segments).length}개`;
  document.getElementById('palhint').innerHTML = mode === 'hand'
    ? '장면을 클릭하면 <b style="color:var(--accent)">선택한 칸에 담깁니다</b>(여러 장 가능)'
    : '③ 내가 편성 모드에서 담을 수 있습니다';

  // 팔레트
  const byRole = {};
  let dropped = 0, folded = 0;
  for (const [sid, s] of Object.entries(DATA.segments)){
    // ★소스 밖 구간은 아예 빼 놓는다(2026-08-14 사장님 "소스 밖 구간은 빼라").
    //   실체가 없는 화면이라 후보로 보일 이유가 없다. 몇 개 뺐는지는 위에 알린다.
    if (outOfRange(sid)){ dropped++; continue; }
    if (hideDup && isDupOf(sid)){ folded++; continue; }   // 비슷한 것은 대표만 보인다
    (byRole[groupOf(sid)] ||= []).push({sid, ...s});
  }
  const dropMsg = document.getElementById('dropmsg');
  if (dropMsg) dropMsg.innerHTML =
    (dropped ? `⚠ 소스 밖 구간 ${dropped}개 제외(실체 없는 화면)<br>` : '')
    + `<label style="cursor:pointer;color:var(--dim)"><input type="checkbox" ${hideDup?'checked':''}
        onchange="toggleDup(this.checked)"> 비슷한 그림은 대표 1장만 보기`
    + (folded ? ` <b style="color:var(--accent)">(${folded}장 접힘)</b>` : ' (접힌 것 없음)') + `</label>`;
  const cur = new Set(lists[sel] || []);

  // 결 그룹 순서로 묶어 보여준다 — 같은 성격끼리 모여 있어야 고르기 쉽다.
  // 그룹 안에서는 소스별·시간순이라 과정 순서(준비→반죽→굽기)가 자연히 보인다.
  document.getElementById('palette').innerHTML = GROUPS.filter(g => (byRole[g.key]||[]).length).map(g => {
    const segs = byRole[g.key];
    segs.sort((a,b) => a.video_id === b.video_id ? a.start - b.start
                                                 : a.video_id.localeCompare(b.video_id));
    return `<div class="srcgroup"><div class="srchead"><span>${g.title}${g.hint?` <span style="opacity:.65">· ${g.hint}</span>`:''}</span><span>${segs.length}개</span></div>
      <div class="thumbs">${segs.map(s => `
        <div class="seg ${cur.has(s.sid)?'inthis':''} ${(outOfRange(s.sid)||tooShort(s.sid))?'oor':''}" ondblclick="add('${s.sid}')"
             title="${(s.scene_desc||'').replace(/"/g,'')}">
          <img src="thumbs/${s.sid}.jpg" loading="lazy">
          <span class="play" onclick="playSeg('${s.sid}', event)">▶ 보기</span>
          ${!cur.has(s.sid) ? '<span class="add">두 번 눌러 담기</span>' : ''}
          <div class="meta"><span class="sid">${s.sid}</span>
            <span style="color:var(--dim)">${(s.end-s.start).toFixed(1)}초 · ${s.video_id}</span>
            <div>${useTags(s.sid).map(t=>`<span class="utag${t==='실증'?' key':''}">${t}</span>`).join('')}</div>
            ${outOfRange(s.sid)?`<div class="oorbadge">⚠ 소스 밖 구간 — 원본 ${(DATA.src_duration||{})[s.video_id]}초</div>`:''}
            ${tooShort(s.sid)?`<div class="oorbadge">⚠ 0.8초 미만 — 담아도 화면에 안 나옵니다</div>`:''}
            ${dupMates(s.sid).length?`<div class="utag" style="border-color:var(--accent);color:var(--accent)">비슷한 그림 ${dupMates(s.sid).length}장 더 (${esc(dupMates(s.sid).join(', '))})</div>`:''}
            <div class="d">${esc(s.scene_desc||'(설명 없음)')}</div>
            </div>
        </div>`).join('')}</div></div>`;
  }).join('');

  // 필름스트립
  let totCuts = 0, totDur = 0, mineDur = 0, longCuts = 0;
  const _why = (DATA.picks || {}).why || [];
  document.getElementById('film').innerHTML = DATA.beats.map((b, i) => {
    const ids = lists[i] || [];
    const clips = planClips(ids, b.target_seconds || 3);
    totCuts += clips.length;
    const bdur = clips.reduce((a,c) => a + c.dur, 0);
    totDur += bdur;
    mineDur += clips.filter(c => chosen.has(c.seg_id)).reduce((a,c) => a + c.dur, 0);
    const longs = clips.filter(c => c.dur > LONG_CUT).length;
    longCuts += longs;
    // ★늘어짐의 진짜 기준은 '장수'가 아니라 '담은 장면 길이의 합'이다(2026-08-13 실험에서 확인).
    //   장면이 0.9초짜리면 3장을 담아도 2.7초뿐이라 5.8초 멘트를 못 채우고 마지막 컷이 늘어난다.
    // ★0.8초 미만은 어차피 버려지므로 '가진 시간'에서 뺀다(2026-08-14 사장님 "하나를 추가하면
    //   저렇게 된다 부족인데"). 담긴 장수만 세면 왜 계속 부족한지 알 수 없다.
    const okIds = ids.filter(id => DATA.segments[id] && !tooShort(id));
    const have = okIds.reduce((a,id) => a + (DATA.segments[id].end - DATA.segments[id].start), 0);
    const tinyN = ids.length - okIds.length;
    const needSec = b.target_seconds || 3;
    const lack = Math.max(0, needSec - have);
    // 실제로 화면에 나온 장면 = 컷에 등장한 것. 담았어도 시간이 모자라면 안 나온다.
    const used = new Set(clips.map(c => c.seg_id));
    const unused = ids.filter(id => !used.has(id)).length;
    return `<div class="beat ${i===sel?'sel':''}" onclick="selBeat(${i})">
      <div class="bhead">
        <span class="role">${i+1}. ${b.role || '칸'}</span>
        <span class="chip">${(b.target_seconds||0).toFixed(1)}초</span>
        <span class="chip ${lack > 0.1 ? 'bad' : 'good'}">멘트 ${needSec.toFixed(1)}초${
          lack > 0.1 ? ` · <b>${lack.toFixed(1)}초 부족 → 장면 ${Math.ceil(lack / MAX_SHOT)}장 더</b>` : ' · 채움'}</span>
        ${tinyN ? `<span class="chip bad">0.8초 미만 ${tinyN}장은 안 쓰임</span>` : ''}
        <span class="chip ${unused ? 'warn' : ''}">담음 ${ids.length}장 → <b>실제 ${used.size}장</b>${
          unused ? ` · ${unused}장 안 나옴` : ''}</span>
        <span class="chip ${longs?'warn':'good'}">컷 ${clips.length}개${longs?` · 늘어짐 ${longs}`:''}</span>
        <span class="ord">
          ${mode==='hand' ? `<button class="act" onclick="event.stopPropagation();clearBeat(${i})">비우기</button>` : ''}
          <button class="act" onclick="event.stopPropagation();move(${i},-1)">↑</button>
          <button class="act" onclick="event.stopPropagation();move(${i},1)">↓</button>
        </span>
        <div class="narr" contenteditable="true" spellcheck="false"
             data-i="${i}" onblur="editNarr(${i}, this)"
             onclick="event.stopPropagation()"
             title="눌러서 대본을 고칠 수 있습니다">${esc(narrOf(i))}</div>
        ${narrChanged(i) ? `<div class="why" style="color:var(--warn);border-color:#5a4520;background:#2a2113">
             ✏ 대본 수정됨 · 예상 ${estSec(narrOf(i)).toFixed(1)}초(원래 ${(b.target_seconds||0).toFixed(1)}초)
             — 음성·자막은 다시 뽑아야 반영됩니다
             <button class="act" style="margin-left:8px;border-color:var(--good);color:var(--good)"
                     onclick="event.stopPropagation();retts(${i})">🔊 음성·자막 다시 뽑기</button>
             <button class="act" onclick="event.stopPropagation();resetNarr(${i})">되돌리기</button>
             <button class="act" onclick="event.stopPropagation();copyScript()">전체 대본 복사</button></div>` : ''}
        ${(mode==='pick' && _why[i]) ? `<div class="why">🎯 ${esc(_why[i])}</div>` : ''}
      </div>
      <div class="bbody"><div class="row">
        <div class="col">
          <div class="lbl">이 칸에 담은 장면 (첫 장이 대표)</div>
          ${ids.length ? `<div class="list">${ids.map((id, k) => `
            <div class="item ${k===0?'first':''} ${used.has(id)?'':'unused'} ${outOfRange(id)?'oor':''}"
                 draggable="true" ondragstart="dragStart(${i},${k},event)"
                 ondragover="event.preventDefault()" ondrop="dragDrop(${i},${k},event)"
                 ondblclick="delSeg(${i},${k})"
                 title="끌어서 순서 바꾸기 · 두 번 누르면 삭제${used.has(id)?'':' (지금은 시간이 모자라 안 나옵니다)'}">
              <span class="n">${k+1}</span>
              <img src="thumbs/${id}.jpg" loading="lazy">
              <span class="play" onclick="playSeg('${id}', event)">▶</span>
              <div class="ctl">
                <span onclick="event.stopPropagation();moveSeg(${i},${k},-1)">◀</span>
                <span class="del" onclick="event.stopPropagation();delSeg(${i},${k})">✕</span>
                <span onclick="event.stopPropagation();moveSeg(${i},${k},1)">▶</span>
              </div>
              <div class="cap">${outOfRange(id)?'<span class="oorbadge">! 소스 밖 - 화면 없음</span><br>':''}${esc(((DATA.segments[id]||{}).scene_desc||'').slice(0,34))}</div>
            </div>`).join('')}</div>`
            : '<div class="empty">장면이 없습니다 — 왼쪽에서 담아주세요</div>'}
        </div>
        <div class="col">
          <div class="lbl">실제 나올 화면 (${bdur.toFixed(1)}초)
            ${clips.length ? `· <button class="act" onclick="playBeat(${i}, event)">▶ 이 칸 재생</button>` : ''}</div>
          <div class="strip">${(()=>{let off=0; return clips.map(c => {
            const a=off, b=off+c.dur; off=b;
            return `<div class="cut ${chosen.has(c.seg_id)?'mine':''} ${c.dur>LONG_CUT?'long':''} ${outOfRange(c.seg_id)?'oor':''}"
                 onclick="playSeg('${c.seg_id}', event)" title="이 컷 보기">
              <img src="thumbs/${c.seg_id}.jpg" loading="lazy">
              <div class="t">${c.dur.toFixed(1)}s${c.dur>LONG_CUT?' 늘림':''}</div>
              ${(() => { const sg = DATA.segments[c.seg_id];
                 const over = sg ? (c.start + c.dur) - sg.end : 0;
                 return over > 0.15
                   ? `<div class="cutsub" style="color:var(--bad)">⚠ 원본 뒤 ${over.toFixed(1)}초가 더 나옵니다(다른 내용)</div>`
                   : ''; })()}
              <div class="cutsub">${capsIn(i, a, b).map(c=>esc(c.text)).join(' / ') || '&nbsp;'}</div>
            </div>`;}).join('')})()}</div>
        </div>
      </div></div></div>`;
  }).join('');

  document.getElementById('k-cuts').textContent = totCuts;
  document.getElementById('k-avg').textContent = totCuts ? (totDur/totCuts).toFixed(1) : '-';
  document.getElementById('k-long').textContent = longCuts + '개';
  document.getElementById('k-long-wrap').className = 'kpi ' + (longCuts ? 'warnv' : 'goodv');
  const own = totDur ? Math.round(mineDur/totDur*100) : 0;
  document.getElementById('k-own').textContent = chosen.size ? own + '%' : '—';
  document.getElementById('k-own-wrap').className =
    'kpi ' + (!chosen.size ? '' : own >= 80 ? 'goodv' : 'warnv');
  saveWork();          // 무엇을 바꾸든 그리는 순간 저장된다
}

// ── 미리보기 재생 ────────────────────────────────────────────────
// 소스 mp4를 그대로 쓰고 구간만 잘라 재생한다. 여러 컷은 이어서 재생 →
// '실제 나올 화면'을 그대로 눈으로 본다(렌더 돌리지 않고 확인).
let seq = [], seqI = 0, seqTimer = null, seqLabel = '';
// ★칸이 넘어갈 때 검은 화면이 잠깐 생기던 것(2026-08-14 사장님 "훅에서 problem 넘어갈 때
//   중간에 검정화면이 살짝 생긴다"). 원인은 <video> 하나에 src를 갈아끼우느라 파일을 다시
//   여는 공백이었다 — 실제 렌더 영상에는 없는, 미리보기만의 현상이다.
//   처방: 소스마다 <video>를 미리 만들어 두고 **보이기만** 바꾼다(파일은 계속 열려 있다).
//   ★2026-08-14 2차(사장님 "1에서 2로 갈 때 1-2 장면이 살짝 낀다"): 소스별로 재생기를 하나만
//   두면 **같은 소스 안에서 구간이 점프할 때** 시크가 끝나기 전 이전 프레임이 그대로 보인다
//   (실측: 칸1의 컷1 s0@14.1초 → 컷2 s0@4.7초). 이건 전환마다 증상이 다르게 나오는
//   두더지의 뿌리였다 — 재생기가 하나면 '보여주면서 동시에 다음 자리를 찾는' 일이 불가능하다.
//   그래서 소스마다 재생기를 **2개**(A/B) 두고 컷마다 번갈아 쓴다. 다음 컷은 항상 **숨은 쪽**에서
//   미리 자리를 잡아두고, 전환은 보이기만 바꾼다 → 같은 소스든 다른 소스든 프레임 누수 0.
const _vids = {};
function vidFor(videoId, slot){
  const key = videoId + ':' + (slot || 0);
  if (_vids[key]) return _vids[key];
  const box = document.getElementById('vidbox');
  const v = document.createElement('video');
  v.muted = true; v.playsInline = true; v.preload = 'auto';
  v.src = `src/${videoId}.mp4`;
  v.style.display = 'none';
  box.appendChild(v);
  _vids[key] = v;
  return v;
}
// 컷을 숨은 재생기에 미리 앉힌다(시크 완료까지 기다린다). 반환은 그 재생기.
function seat(c){
  const v = vidFor(c.video_id, c._slot);
  if (Math.abs(v.currentTime - c.start) > 0.05) v.currentTime = c.start;
  return v;
}
let curVid = null;
function showVid(v){
  if (curVid === v) return;
  if (curVid){ curVid.pause(); curVid.style.display = 'none'; }
  v.style.display = 'block';
  curVid = v;
}
const vid = () => curVid || document.getElementById('vid');
// 페이지가 열리면 소스들을 미리 열어 둔다(첫 전환도 매끄럽게).
function warmVideos(){
  const ids = new Set(Object.values(DATA.segments).map(s => s.video_id));
  ids.forEach(id => { vidFor(id, 0); vidFor(id, 1); });   // A/B 두 벌
}

function stopPlay(){
  clearTimeout(seqTimer); seqTimer = null; seq = [];
  playKey = null;
  const a0 = audio(); if (a0) a0.onended = null;    // 전체 재생 체인 끊기
  clearInterval(subTimer); seqBeat = null;
  const a = audio(); if (a){ a.pause(); }
  const sb = document.getElementById('subbox'); if (sb) sb.innerHTML = '';
  const v = vid(); if (v) v.pause();
  document.getElementById('player').classList.remove('on');
}
function playSeg(sid, ev){
  if (ev) ev.stopPropagation();
  const s = DATA.segments[sid];
  if (!s) return;
  // ★한 번 누르면 재생, 같은 것을 다시 누르면 정지(2026-08-14 사장님 "정지 버튼이 없다").
  if (playKey === 'seg:' + sid && !vid().paused){ stopPlay(); return; }
  playKey = 'seg:' + sid;
  seqLabel = `장면 ${sid}`;
  clearInterval(subTimer); seqBeat = null;
  const a0 = audio(); if (a0) a0.pause();
  const sb0 = document.getElementById('subbox'); if (sb0) sb0.innerHTML = '';
  startSeq([{seg_id: sid, video_id: s.video_id, start: s.start, dur: s.end - s.start}]);
}
function playBeat(i, ev){
  if (ev) ev.stopPropagation();
  const clips = planClips(lists[i] || [], DATA.beats[i].target_seconds || 3);
  if (!clips.length) return;
  if (playKey === 'beat:' + i && !audio().paused){ stopPlay(); return; }   // 다시 누르면 정지
  playKey = 'beat:' + i;
  seqLabel = `칸 ${i+1} 전체`;
  seqBeat = i;
  startSeq(clips);
  // 음성은 화면과 별개 트랙 — 같이 0초부터 튼다(캡컷의 오디오 트랙과 같은 개념).
  const a = audio();
  a.src = `tts/beat_${i}.mp3`;
  a.currentTime = 0;
  a.play().catch(()=>{});
  tickSub();
}
// 자막은 음성 시각을 따라간다(화면 컷이 몇 개로 쪼개지든 무관).
let subTimer = null;
function tickSub(){
  clearInterval(subTimer);
  const box = document.getElementById('subbox');
  if (seqBeat == null){ box.innerHTML = ''; return; }
  subTimer = setInterval(() => {
    const a = audio(), t = a.currentTime || 0;
    const c = capAt(seqBeat, t);
    const k = seqBounds.findIndex(([a0, b0]) => t >= a0 - 1e-3 && t < b0);
    const tag = (subPerCut && k >= 0) ? `컷 ${k+1}/${seqBounds.length}` : '';
    box.innerHTML = (tag ? `<div class="subtag">${tag}</div>` : '')
      + `<span class="said">${esc(c ? c.text : '')}</span>`;
    if (a.ended || a.paused) clearInterval(subTimer);
  }, 60);
}

// ★전체 재생(2026-08-14 사장님 "지금 된 거 이어서 보여줘봐"): 칸 0부터 끝까지 이어서 돈다.
//   칸이 끝나면(음성 ended) 다음 칸으로 넘어간다 — 렌더 없이 완성 영상 흐름을 그대로 본다.
function playAll(ev){
  if (ev) ev.stopPropagation();
  if (playKey === 'all' && !audio().paused){ stopPlay(); return; }   // 다시 누르면 정지
  playKey = 'all';
  runAllFrom(0);
}
function runAllFrom(i){
  if (playKey !== 'all') return;
  if (i >= DATA.beats.length){ stopPlay(); return; }
  const clips = planClips(lists[i] || [], DATA.beats[i].target_seconds || 3);
  seqBeat = i; sel = i;
  seqLabel = `전체 재생 - 칸 ${i+1}/${DATA.beats.length} (${DATA.beats[i].role || ''})`;
  if (!clips.length){ runAllFrom(i + 1); return; }
  startSeq(clips);
  // 다음 칸의 첫 컷도 지금 미리 앉혀 둔다(칸을 넘을 때도 누수 0).
  const nx = DATA.beats[i + 1];
  if (nx){
    const ncl = planClips(lists[i + 1] || [], nx.target_seconds || 3);
    if (ncl[0]){ ncl[0]._slot = 0; seat(ncl[0]); }
  }
  const a = audio();
  a.onended = () => { if (playKey === 'all') runAllFrom(i + 1); };
  a.src = `tts/beat_${i}.mp3`;
  a.currentTime = 0;
  a.play().catch(()=>{});
  tickSub();
}
function startSeq(clips){
  clearTimeout(seqTimer);
  seq = clips; seqI = 0;
  // 컷 경계 누적(자막을 컷 단위로 끊어 보여주려면 각 컷의 [시작,끝) 초가 필요하다)
  let off = 0;
  seqBounds = clips.map(c => { const a = off; off += c.dur; return [a, off]; });
  clips.forEach((c, k) => { c._slot = k % 2; });   // 이웃한 컷은 다른 재생기 → 미리 앉히기 가능
  if (clips[0]) seat(clips[0]);
  if (clips[1]) seat(clips[1]);
  document.getElementById('player').classList.add('on');
  step();
}
function step(){
  if (seqI >= seq.length){
    document.getElementById('pinfo').textContent = `${seqLabel} — 재생 끝 (${seq.length}컷)`;
    if (curVid) curVid.pause();
    return;
  }
  const c = seq[seqI];
  const v = vidFor(c.video_id, c._slot);
  const go = () => {
    // ★시크가 **끝난 뒤에** 보여준다(2026-08-14 사장님 "3번 솔루션 끝나는 장면 마지막에
    //   2번 첫 장면이 잠깐 보인다"). 칸2와 칸4가 같은 소스(s0)를 쓰는데, 칸4로 넘어갈 때
    //   s0가 칸2에서 멈춰 있던 위치(견과류 얹는 장면)를 한 프레임 노출하고 나서 이동했다.
    const show = () => { showVid(v); v.play().catch(()=>{}); };
    if (Math.abs(v.currentTime - c.start) < 0.05) show();
    else {
      let done = false;
      const once = () => { if (done) return; done = true; v.onseeked = null; show(); };
      v.onseeked = once;
      v.currentTime = c.start;
      setTimeout(once, 200);       // seeked가 안 와도 멈추지 않게(폴백)
    }
    document.getElementById('pinfo').innerHTML =
      `${seqLabel}<br>컷 ${seqI+1}/${seq.length} · ${c.dur.toFixed(1)}초 · 장면 ${c.seg_id}`;
    // 다음 컷을 **숨은 재생기**에 미리 앉힌다 — 전환 순간에 할 일이 남지 않는다.
    if (seq[seqI + 1]) seat(seq[seqI + 1]);
    seqTimer = setTimeout(() => { seqI++; step(); }, c.dur * 1000);
  };
  if (v.readyState >= 1) go();           // 이미 열려 있으면 즉시
  else v.onloadedmetadata = go;
}

// 끌어서 순서 바꾸기(2026-08-14 사장님 "잡고 이동해서 순서변경"). 같은 칸 안에서만 옮긴다
// — 칸을 넘나들면 대사와 화면의 짝이 조용히 어긋난다.
let dragFrom = null;
function dragStart(i, k, ev){
  dragFrom = {i, k};
  if (ev && ev.dataTransfer) ev.dataTransfer.effectAllowed = 'move';
}
function dragDrop(i, k, ev){
  if (ev) ev.preventDefault();
  if (!dragFrom || dragFrom.i !== i || dragFrom.k === k){ dragFrom = null; return; }
  const l = lists[i];
  const [moved] = l.splice(dragFrom.k, 1);
  l.splice(k, 0, moved);
  dragFrom = null; render();
}
// ★내가 조립한 것을 브라우저에 저장한다(2026-08-14 사장님 "방금 조립한 게 없어지고
//   네가 만든 걸로 되어 있어"). 새로고침·페이지 재빌드에도 남는다. 잡별로 따로 저장하므로
//   다른 잡을 열어도 안 섞인다. '처음으로'를 누르면 지운다.
const SAVE_KEY = 'sceneLab:' + (DATA.job_id || 'job');
function saveWork(){
  try{
    localStorage.setItem(SAVE_KEY, JSON.stringify({
      mode, lists, chosen: [...chosen], narr: NARR, at: new Date().toISOString()
    }));
  }catch(e){}
  const el = document.getElementById('savedmsg');
  if (el) el.textContent = '💾 내 편집 저장됨 (새로고침해도 남습니다)';
}
function loadWork(){
  try{
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return false;
    const w = JSON.parse(raw);
    if (!w || !Array.isArray(w.lists) || w.lists.length !== DATA.beats.length) return false;
    mode = w.mode || 'hand';
    lists = w.lists.map(l => Array.isArray(l) ? l.slice() : []);
    chosen.clear(); (w.chosen || []).forEach(x => chosen.add(x));
    Object.keys(NARR).forEach(k => delete NARR[k]);
    Object.assign(NARR, w.narr || {});
    ['live','one','hand','pick'].forEach(x => {
      const b = document.getElementById('m-' + x);
      if (b) b.classList.toggle('on', x === mode);
    });
    const el = document.getElementById('savedmsg');
    if (el) el.textContent = '💾 이어서 편집 중 (저장된 배치를 불러왔습니다)';
    return true;
  }catch(e){ return false; }
}
function clearWork(){ try{ localStorage.removeItem(SAVE_KEY); }catch(e){} }
// ── 대본 편집(2026-08-14 사장님 "여기서 대본까지 수정되게 해줘") ────────────────────
// 로컬에서 음성(TTS)을 새로 만들 수는 없다 — 그래서 **글을 고쳐 저장하고, 길이가 어떻게
// 바뀌는지 라이브와 같은 기준(글자수 ÷ 초당 글자수)으로 보여주는 것**까지가 여기의 몫이다.
// 고친 대본은 '전체 대본 복사'로 가져가 제작소에 넣으면 음성·자막이 새로 만들어진다.
const NARR = {};                       // beat_idx → 고친 대본
function narrOf(i){ return NARR[i] != null ? NARR[i] : (DATA.beats[i].narration || ''); }
function narrChanged(i){ return NARR[i] != null && NARR[i] !== (DATA.beats[i].narration || ''); }
function estSec(t){
  const n = String(t || '').split(' ').join('').length;   // 공백 뺀 글자수
  return Math.max(1.5, n / (DATA.syll_per_sec || 5.7));
}
function editNarr(i, el){
  const t = (el.innerText || '').trim();
  if (t === (DATA.beats[i].narration || '')){ delete NARR[i]; } else { NARR[i] = t; }
  render();
}
function resetNarr(i){ delete NARR[i]; render(); }
// ★음성·자막 다시 뽑기 — 로컬 서버(serve.py)가 SSH로 진짜 서버에 시킨다. 라이브와 같은
//   코드로 만들어 받으므로 자막이 어긋날 수 없다. 끝나면 페이지를 다시 읽어 반영한다.
async function retts(i){
  const msg = document.getElementById('savedmsg');
  const txt = narrOf(i);
  if (msg) msg.textContent = `🔊 칸 ${i+1} 음성·자막 만드는 중… (10~20초)`;
  try{
    const r = await fetch('/retts', {method:'POST', headers:{'Content-Type':'application/json'},
                                    body: JSON.stringify({beat_idx: i, text: txt})});
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || '실패');
    delete NARR[i];                       // 서버 data.json이 새 대본으로 바뀌었다
    saveWork();
    if (msg) msg.textContent = `✅ 칸 ${i+1} 다시 뽑음 — ${j.dur}초 / 자막 ${j.captions.length}구절. 새로고침합니다`;
    setTimeout(() => location.reload(), 900);
  }catch(e){
    if (msg) msg.textContent = '⚠ 다시 뽑기 실패: ' + (e.message || e);
  }
}
function copyScript(){
  // 개행은 코드에 직접 쓰지 않는다 — 이 JS는 파이썬 문자열 안에 들어 있어 이스케이프가 충돌한다.
  const NL = String.fromCharCode(10);
  const txt = DATA.beats.map((b, i) => (i+1) + '. ' + (b.role || '') + NL + narrOf(i)).join(NL + NL);
  navigator.clipboard.writeText(txt).then(
    () => { const el = document.getElementById('savedmsg'); if (el) el.textContent = '📋 대본을 복사했습니다 — 제작소에 붙여넣으면 음성·자막이 새로 만들어집니다'; },
    () => {});
}
function selBeat(i){ sel = i; render(); }
function add(sid){
  // ★담을 때 지금 배치를 절대 초기화하지 않는다(2026-08-14 사장님 "4장면 있었는데 하나
  //   추가하니 2개로 변했다"). 예전엔 setMode('hand')를 불렀는데 그게 initLists()로 전 칸을
  //   되돌려, ④ 배치에 한 장 담는 순간 4장이 1장(첫 장만)으로 줄고 새 것까지 2장이 됐다.
  //   모드 표시만 '내가 편성'으로 바꾸고 리스트·선택은 그대로 둔다.
  if (mode !== 'hand'){
    mode = 'hand';
    ['live','one','hand','pick'].forEach(x =>
      document.getElementById('m-' + x).classList.toggle('on', x === 'hand'));
  }
  const l = lists[sel];
  if (!l) return;
  if (l.includes(sid)) return;          // 중복 금지 — 같은 화면 되풀이 방지
  l.push(sid); chosen.add(sid); render();
}
function delSeg(i, k){ lists[i].splice(k, 1); render(); }
function moveSeg(i, k, d){
  const l = lists[i], j = k + d;
  if (j < 0 || j >= l.length) return;
  [l[k], l[j]] = [l[j], l[k]]; render();
}
function clearBeat(i){ lists[i] = []; sel = i; render(); }
function move(i, d){
  const j = i + d;
  if (j < 0 || j >= DATA.beats.length) return;
  [DATA.beats[i], DATA.beats[j]] = [DATA.beats[j], DATA.beats[i]];
  [lists[i], lists[j]] = [lists[j], lists[i]];
  sel = j; render();
}
function setMode(m){
  mode = m;
  ['live','one','hand','pick'].forEach(x =>
    document.getElementById('m-' + x).classList.toggle('on', x === m));
  initLists(); chosen.clear();
  // ④ 모드는 전부 사람이 고른 화면이므로 '내가 고른 화면 %' 지표가 100%가 되게 표시한다.
  if (m === 'pick') lists.forEach(l => l.forEach(id => chosen.add(id)));
  render();
}
function reset(){
  clearWork();
  const el = document.getElementById('savedmsg'); if (el) el.textContent = '';
  setMode(mode);          // 지금 모드의 기본 배치로 되돌린다(저장본 삭제)
}
if (DATA.picks && (DATA.picks.lists || []).length){
  const el = document.getElementById('m-pick');
  el.style.display = '';
  if (DATA.picks.label) el.firstChild.textContent = DATA.picks.label + ' ';
}
// ★저장된 내 편집이 있으면 그것부터 — 없을 때만 기본 배치로 연다.
warmVideos();
if (loadWork()) render();
else if (DATA.picks && (DATA.picks.lists || []).length) setMode('pick');
else { initLists(); render(); }
</script></body></html>
"""

html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False))
out = BASE / "index.html"
out.write_text(html, encoding="utf-8")
print("wrote", out, len(html), "bytes")
