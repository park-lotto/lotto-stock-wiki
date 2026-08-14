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
.narr{color:var(--dim);font-size:12px;flex:1 1 100%;line-height:1.5}
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
#player video{width:100%;border-radius:6px;background:#000;display:block;aspect-ratio:9/16;object-fit:contain}
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
    <div id="palette"></div>
  </div>
  <div class="pane right">
    <div class="lbl"><button class="act" onclick="playAll(event)" style="margin-right:10px">▶ 전체 재생(칸 이어서)</button>아래 <b>“실제 나올 화면”</b>이 렌더 결과입니다(렌더 알고리즘 이식) ·
      <span style="color:var(--warn)">주황 = 2.5초 넘게 안 바뀌는 컷(늘어짐)</span></div>
    <div id="film"></div>
  </div>
</div>

<div id="player">
  <div class="phead"><b>미리보기</b><span class="x" onclick="stopPlay()">닫기 ✕</span></div>
  <video id="vid" muted playsinline></video>
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
  {key:'완성',   title:'🏆 완성품',        hint:'훅·CTA에 좋다'},
  {key:'after',  title:'✅ 결과·증거',     hint:'쪼갠 단면·먹는 반응 — 결과 칸에 좋다'},
  {key:'사용중', title:'🍳 조리·사용 과정', hint:'해결·과정 칸에 좋다'},
  {key:'기타',   title:'그 밖의 장면',     hint:''},
];
function groupOf(sid){
  const r = (DATA.segments[sid] || {}).shot_role || '기타';
  return GROUPS.some(g => g.key === r) ? r : '기타';
}
// 용도 배지 — 위 결에서 바로 파생한 **제안**이다(강제 아님, 담는 건 사장님 판단).
function useTags(sid){
  const s0 = DATA.segments[sid] || {}, r = groupOf(sid), t = [];
  if (r === '완성'){ t.push('후킹용'); t.push('CTA용'); }
  if (r === 'after'){ t.push('후킹용'); t.push('결과용'); }
  if (r === '사용중') t.push('조리용');
  if (s0.is_key) t.push('실증');
  return t;
}
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
function planClips(segIds, ttsDur){
  const segments = segIds.map(id => ({...DATA.segments[id], seg_id: id})).filter(s => s.start != null);
  const clips = []; let filled = 0;
  if (!segments.length) return clips;
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
  for (const [sid, s] of Object.entries(DATA.segments))
    (byRole[groupOf(sid)] ||= []).push({sid, ...s});
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
    const have = ids.reduce((a,id) => a + (DATA.segments[id] ? DATA.segments[id].end - DATA.segments[id].start : 0), 0);
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
          lack > 0.1 ? ` · <b>${lack.toFixed(1)}초 부족</b>` : ' · 채움'}</span>
        <span class="chip ${unused ? 'warn' : ''}">담음 ${ids.length}장 → <b>실제 ${used.size}장</b>${
          unused ? ` · ${unused}장 안 나옴` : ''}</span>
        <span class="chip ${longs?'warn':'good'}">컷 ${clips.length}개${longs?` · 늘어짐 ${longs}`:''}</span>
        <span class="ord">
          ${mode==='hand' ? `<button class="act" onclick="event.stopPropagation();clearBeat(${i})">비우기</button>` : ''}
          <button class="act" onclick="event.stopPropagation();move(${i},-1)">↑</button>
          <button class="act" onclick="event.stopPropagation();move(${i},1)">↓</button>
        </span>
        <div class="narr">${b.narration || ''}</div>
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
const vid = () => document.getElementById('vid');

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
  document.getElementById('player').classList.add('on');
  step();
}
function step(){
  const v = vid();
  if (seqI >= seq.length){
    document.getElementById('pinfo').textContent = `${seqLabel} — 재생 끝 (${seq.length}컷)`;
    v.pause(); return;
  }
  const c = seq[seqI];
  const src = `src/${c.video_id}.mp4`;
  const go = () => {
    v.currentTime = c.start;
    v.play().catch(()=>{});
    document.getElementById('pinfo').innerHTML =
      `${seqLabel}<br>컷 ${seqI+1}/${seq.length} · ${c.dur.toFixed(1)}초 · 장면 ${c.seg_id.split('-').pop()}`;
    seqTimer = setTimeout(() => { seqI++; step(); }, c.dur * 1000);
  };
  if (!v.src.endsWith(src)){
    v.src = src;
    v.onloadedmetadata = go;                 // 소스가 바뀌면 메타데이터를 기다렸다 시크
  } else go();
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
      mode, lists, chosen: [...chosen], at: new Date().toISOString()
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
if (loadWork()) render();
else if (DATA.picks && (DATA.picks.lists || []).length) setMode('pick');
else { initLists(); render(); }
</script></body></html>
"""

html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False))
out = BASE / "index.html"
out.write_text(html, encoding="utf-8")
print("wrote", out, len(html), "bytes")
