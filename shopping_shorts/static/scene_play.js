let DATA = null;
let SAVE_KEY = 'sceneLab:job';   // boot()가 job_id로 다시 정한다
const SL = {
  server: false, job: '',
  thumb: sid => SL.server ? `/api/mix/seg_thumb/${SL.job}/${encodeURIComponent(sid)}` : `thumbs/${sid}.jpg`,
  src:   vid => SL.server ? `/api/mix/src/${SL.job}/${encodeURIComponent(vid)}` : `src/${vid}.mp4`,
  tts:   i   => SL.server ? `/api/mix/tts/${SL.job}/${i}` : `tts/beat_${i}.mp3`,
  applyUrl: () => SL.server ? `/api/mix/scene_lab/${SL.job}/apply` : '/apply',
};
const MAX_SHOT = 2.2, MIN_CLIP = 0.8, EPS = 1e-3, LONG_CUT = MAX_SHOT + 0.05;   // 상한을 넘긴 컷 = 소재가 모자라 늘린 것

// 소스 영상 길이를 넘는 구간인가 — 실측(job 409f894230c6): s1-10이 100~104초인데
// s1.mp4는 78.5초였다. 렌더하면 그 컷은 실체가 없다. 눈에 보이게 표시한다.
// 최소 컷 길이(0.8초)에 못 미치는 장면 — 담아도 화면에 **안 나온다**(라운드로빈이 건너뛴다).
// 2026-08-14 사장님 "여 씬이 들어가면 뭔가 꼬인다": 0.7초짜리를 담으면 그 장면은 사라지고,
// 남은 소재로 나레이션 길이를 채우느라 다른 컷이 길게 늘어난다. 담기 전에 알려준다.
// ★장면을 결(役)로 묶는다(2026-08-14 사장님 "완성품·조리 이런 식으로 나누고 후킹용·조리용·
//   CTA용 태그"). 새 판단을 만들지 않는다 — 추출이 이미 붙여둔 shot_role/is_key를 그대로 쓴다
//   (완성 / after=결과·증거 / 사용중=조리·사용 / 기타). 실측 분포 9·5·41·1.

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


let seqBeat = null;   // 지금 재생 중인 칸(자막·음성 트랙 기준)
let playKey = null;   // 지금 재생 중인 대상 — 같은 것을 다시 누르면 정지(토글)
let seqBounds = [];   // 컷별 [시작,끝) 초 — 자막을 컷 단위로 끊는 기준
let subPerCut = true; // 미리보기에 '컷 n/N' 표시(자막 자체는 라이브와 같은 구절 단위)
let sel = 0;
let lists = [];              // 비트별 장면 seg_id 목록(첫 항목이 primary)
const chosen = new Set();    // 사람이 손으로 담은 seg_id


const TRIMS = {};                  // sid → [a, b] (장면 시작 기준 초)
let trimA = null, trimSid = null;  // 첫 번째 체크 지점 / 지금 트림바가 보는 장면
function trimPieces(id){
  const s = DATA.segments[id]; if (!s) return [];
  const t = TRIMS[id];
  if (!t) return [s];
  const p = [];
  if (t[0] > EPS) p.push({...s, end: s.start + t[0]});                 // 앞토막 [0 ~ a]
  if (s.end - (s.start + t[1]) > EPS) p.push({...s, start: s.start + t[1]});  // 뒤토막 [b ~ 끝]
  return p.length ? p : [s];       // 전부 잘려 나가면 트림 무시(원본)
}
// '가진 시간'용 실제 가용 길이 — 0.8초 미만 토막은 어차피 안 나오므로 뺀다.
function effLen(id){
  return trimPieces(id).filter(p => p.end - p.start >= MIN_CLIP - EPS)
                       .reduce((x, p) => x + (p.end - p.start), 0);
}
function trimBarSid(){ return (playKey && playKey.indexOf('seg:') === 0) ? playKey.slice(4) : null; }
function updateTrimBar(){
  const bar = document.getElementById('trimbar');
  if (!bar) return;
  const sid = trimBarSid();
  if (sid !== trimSid){ trimSid = sid; trimA = null; }   // 다른 장면으로 넘어가면 체크 초기화
  if (!sid){ bar.style.display = 'none'; return; }
  bar.style.display = 'flex';
  const t = TRIMS[sid];
  if (t){
    bar.innerHTML = `<span class="hint">✂ ${t[0].toFixed(1)}~${t[1].toFixed(1)}초 뺐음 · 여기 재생은 원본 전체</span>
      <button class="act" onclick="event.stopPropagation();unTrim('${sid}')">되돌리기</button>`;
  } else if (trimA != null){
    bar.innerHTML = `<button class="act" onclick="trimMark(event)">✂ 여기까지</button>
      <span class="hint">시작 ${trimA.toFixed(1)}초 — 끝 지점에서 다시 누르세요</span>`;
  } else {
    bar.innerHTML = `<button class="act" onclick="trimMark(event)">✂ 여기부터 자르기</button>
      <span class="hint">진행바로 지점을 찾아 누르세요</span>`;
  }
}
function trimMark(ev){
  if (ev) ev.stopPropagation();
  const sid = trimBarSid(); if (!sid || !seq.length) return;
  const t = Math.min(seqTotal(), Math.max(0, curT()));
  if (trimA == null){ trimA = t; updateTrimBar(); return; }
  const a = Math.min(trimA, t), b = Math.max(trimA, t);
  trimA = null;
  if (b - a < 0.05){ updateTrimBar(); return; }          // 같은 자리 두 번 = 취소
  TRIMS[sid] = [Math.round(a * 100) / 100, Math.round(b * 100) / 100];
  (typeof render === 'function' && render());                                              // saveWork까지 — 새로고침에도 남는다
  updateTrimBar();
}
function unTrim(sid){ delete TRIMS[sid]; trimA = null; (typeof render === 'function' && render()); updateTrimBar(); }

// video_assemble._plan_beat_clips 이식(라운드로빈 + shortfall 1순위 근사)
let onePerSeg = false;   
const STRETCH = {};                 // beat_idx → true(늘려 채우기 켬)
function toggleStretch(i, on){ if (on) STRETCH[i] = true; else delete STRETCH[i]; (typeof render === 'function' && render()); }
function planClips(segIds, ttsDur, spread){
  // ✂ 트림된 장면은 '구멍 뺀 두 토막'으로 갈라서 넣는다 — 아래 분배 규칙은 그대로다.
  const segments = segIds.flatMap(id => trimPieces(id).map(p => ({...p, seg_id: id})))
                         .filter(s => s.start != null);
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
  if (short > EPS && clips.length){
    // spread(늘려 채우기 토글 ON): 부족분을 마지막 컷에 몰지 않고 전 컷에 비례로 나눈다.
    // 컷마다 조금씩 길어질 뿐 라운드로빈 결과(컷 수·순서·시작점)는 그대로다.
    if (spread && filled > EPS) clips.forEach(c => { c.dur *= ttsDur / filled; });
    else clips[clips.length - 1].dur += short;   // 그 장면이 계속 나온다
  }
  return clips;
}

// 타임프레임 한 줄 — 실제 컷을 시간 순서대로. 계산은 planClips 하나만 쓴다(아래 필름과 동일).


// ── 미리보기 재생 엔진 (공용)
// ※ render()는 장면 편집 화면에만 있다 — 제작소에서 돌 때를 위해 있을 때만 부른다. ────────────────────────────────────────────────
// 2026-08-15 분리: 사장님 "미리보기를 렌더 썸네일 자리에서 재생해 달라".
// 장면 편집(scene_lab.html)은 제작소 안에 iframe으로 들어가 있어, 브라우저 보안상
// **안쪽 화면을 바깥 페이지 자리에 그릴 수 없다**. 그래서 재생 코드를 이 파일로 빼서
// 제작소(produce.html)와 장면 편집이 **같은 한 벌**을 쓰게 한다.
// ★복사해서 두 벌로 만들지 않는다 — 한쪽만 고쳐져 어긋나는 사고를 막는다(CLAUDE.md 0순위-B).
//
// 이 파일이 기대하는 전역(쓰는 쪽이 준비한다):
//   DATA(잡 데이터) · lists(칸별 담긴 seg_id) · STRETCH(칸별 늘려채우기)
//   planClips() · capAt() · SL(주소 어댑터) · playKey/seqBeat 등 재생 상태
// 화면 요소 id: #player #vidbox #seek #subbox #bgaudio #pinfo #trimbar

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
  v.src = SL.src(videoId);
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
  playKey = null; seqPaused = false;
  const a0 = audio(); if (a0) a0.onended = null;    // 전체 재생 체인 끊기
  clearInterval(subTimer); seqBeat = null;
  const a = audio(); if (a){ a.pause(); }
  const sb = document.getElementById('subbox'); if (sb) sb.innerHTML = '';
  const v = vid(); if (v) v.pause();
  clearInterval(posTimer);
  const sk = document.getElementById('seek'); if (sk) sk.value = 0;
  document.querySelectorAll('.item.playing').forEach(el => el.classList.remove('playing'));
  updatePlayBtns();
  document.getElementById('player').classList.remove('on');
  if (typeof sceneLabPlayClosed === 'function') sceneLabPlayClosed();
}
function playSeg(sid, ev){
  if (ev) ev.stopPropagation();
  const s = DATA.segments[sid];
  if (!s) return;
  // ★한 번 누르면 재생, 같은 것을 다시 누르면 정지(2026-08-14 사장님 "정지 버튼이 없다").
  if (playKey === 'seg:' + sid && !vid().paused){ stopPlay(); return; }
  playKey = 'seg:' + sid;
  seqLabel = '장면 미리보기';
  clearInterval(subTimer); seqBeat = null;
  const a0 = audio(); if (a0) a0.pause();
  const sb0 = document.getElementById('subbox'); if (sb0) sb0.innerHTML = '';
  startSeq([{seg_id: sid, video_id: s.video_id, start: s.start, dur: s.end - s.start}]);
}
function playBeat(i, ev){
  if (ev) ev.stopPropagation();
  const clips = planClips(lists[i] || [], DATA.beats[i].target_seconds || 3, STRETCH[i]);
  if (!clips.length) return;
  // ★재생 버튼을 다시 누르면 **일시정지/재개** 토글(2026-08-15 사장님 "누르면 일시정지").
  //   완전 정지는 미리보기 창의 닫기 ✕. 끝까지 다 돈 뒤에 누르면 처음부터 다시.
  if (playKey === 'beat:' + i && seqI < seq.length){ togglePause(); return; }
  playKey = 'beat:' + i;
  seqLabel = `칸 ${i+1} 전체`;
  seqBeat = i;
  startSeq(clips);
  // 음성은 화면과 별개 트랙 — 같이 0초부터 튼다(캡컷의 오디오 트랙과 같은 개념).
  const a = audio();
  a.src = SL.tts(i);
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
  if (playKey === 'all'){ togglePause(); return; }   // 다시 누르면 일시정지/재개
  playKey = 'all';
  runAllFrom(0);
}
function runAllFrom(i){
  if (playKey !== 'all') return;
  if (i >= DATA.beats.length){ stopPlay(); return; }
  const clips = planClips(lists[i] || [], DATA.beats[i].target_seconds || 3, STRETCH[i]);
  seqBeat = i; sel = i;
  seqLabel = `전체 재생 - 칸 ${i+1}/${DATA.beats.length} (${DATA.beats[i].role || ''})`;
  if (!clips.length){ runAllFrom(i + 1); return; }
  startSeq(clips);
  // 다음 칸의 첫 컷도 지금 미리 앉혀 둔다(칸을 넘을 때도 누수 0).
  const nx = DATA.beats[i + 1];
  if (nx){
    const ncl = planClips(lists[i + 1] || [], nx.target_seconds || 3, STRETCH[i + 1]);
    if (ncl[0]){ ncl[0]._slot = 0; seat(ncl[0]); }
  }
  const a = audio();
  a.onended = () => { if (playKey === 'all') runAllFrom(i + 1); };
  a.src = SL.tts(i);
  a.currentTime = 0;
  a.play().catch(()=>{});
  tickSub();
}
function startSeq(clips){
  clearTimeout(seqTimer);
  seq = clips; seqI = 0; seqPaused = false;
  // 컷 경계 누적(자막을 컷 단위로 끊어 보여주려면 각 컷의 [시작,끝) 초가 필요하다)
  let off = 0;
  seqBounds = clips.map(c => { const a = off; off += c.dur; return [a, off]; });
  clips.forEach((c, k) => { c._slot = k % 2; });   // 이웃한 컷은 다른 재생기 → 미리 앉히기 가능
  if (clips[0]) seat(clips[0]);
  if (clips[1]) seat(clips[1]);
  document.getElementById('player').classList.add('on');
  // 진행바 갱신 — 끌고 있는 동안(seekDrag)은 안 덮어쓴다.
  clearInterval(posTimer);
  posTimer = setInterval(() => {
    if (seekDrag) return;
    const el = document.getElementById('seek'), tot = seqTotal();
    if (el && tot) el.value = Math.round(Math.min(1, curT() / tot) * 1000);
  }, 120);
  updatePlayBtns();
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
    paintCut();
    // 다음 컷을 **숨은 재생기**에 미리 앉힌다 — 전환 순간에 할 일이 남지 않는다.
    if (seq[seqI + 1]) seat(seq[seqI + 1]);
    schedStep(c.dur * 1000);
  };
  if (v.readyState >= 1) go();           // 이미 열려 있으면 즉시
  else v.onloadedmetadata = go;
}

// ── 컷 표시 한 곳(2026-08-15 사장님 "왼쪽은 3개인데 컷이 4/4" 혼란) ─────────────────
// "컷 4/4"의 4번째는 새 장면이 아니라 **앞 장면이 또 나오는 것**(planClips가 멘트를 못
// 채우면 되풀이·연장으로 채운다). 그래서 컷이 바뀔 때마다 ①지금 나오는 장면의 카드를
// 필름에서 강조하고 ②되풀이면 pinfo에 'N번 장면이 또 나와요'를 밝힌다 — 계산 불변, 표시만.
function paintCut(){
  const c = seq[seqI]; if (!c) return;
  const segIdx = seqBeat != null ? (lists[seqBeat] || []).indexOf(c.seg_id) : -1;
  // ✂ 바로 앞 컷이 같은 장면이면 '또 나옴'이 아니라 **이어짐**(트림 두 토막·연장)이다 —
  //   다른 장면을 거쳐 돌아왔을 때만 '또 나와요'로 알린다.
  const again = seq.slice(0, seqI).some(x => x.seg_id === c.seg_id)
             && !(seqI > 0 && seq[seqI - 1].seg_id === c.seg_id);
  document.getElementById('pinfo').innerHTML =
    `${seqLabel}<br>컷 ${seqI+1}/${seq.length} · ${c.dur.toFixed(1)}초` +
    ((again && segIdx >= 0) ? ` · <b style="color:var(--warn)">${segIdx+1}번 장면이 또 나와요</b>` : '');
  document.querySelectorAll('.item.playing').forEach(el => el.classList.remove('playing'));
  if (seqBeat != null && segIdx >= 0){
    const be = document.querySelectorAll('#film .beat')[seqBeat];
    const card = be && be.querySelectorAll('.item')[segIdx];
    if (card) card.classList.add('playing');
  }
}
// 재생 버튼 표시(▶ ↔ ⏸) — 상태가 바뀌는 모든 곳에서 부른다.
function updatePlayBtns(){
  const playing = k => playKey === k && !seqPaused && seqI < seq.length;
  (DATA.beats || []).forEach((b, i) => {
    const el = document.getElementById('pb-' + i);
    if (el) el.textContent = playing('beat:' + i) ? '⏸ 일시정지' : '▶️ 재생';
  });
  const a = document.getElementById('pball');
  if (a) a.textContent = playing('all') ? '⏸ 일시정지' : '▶️ 전체 재생';
  updateTrimBar();   // ✂ 트림바는 장면 미리보기(seg:)일 때만 보인다 — 상태 전환마다 갱신
}

// ── 구간 이동(2026-08-15 사장님 "미리보기 켜질 때 구간이동될 수 있게") ────────────────
// ★칸·전체 재생은 여러 컷을 seqTimer로 **순차로 잇는다** — video.currentTime만 옮기면
//   컷 진행(seqI·타이머)과 어긋난다. 그래서 이동은 반드시 여기로: 목표 초가 속한 컷을
//   seqBounds에서 찾아 seqI를 옮기고, 그 컷 안 오프셋으로 영상·음성을 맞춘 뒤 타이머를
//   남은 시간으로 다시 건다. 자막(tickSub)은 음성 시각을 따르므로 저절로 맞는다.
let seekDrag = false, posTimer = null;
function seqTotal(){ return seqBounds.length ? seqBounds[seqBounds.length - 1][1] : 0; }
function curT(){
  if (!seq.length) return 0;
  if (seqBeat != null) return audio().currentTime || 0;   // 음성이 시계(자막과 같은 기준)
  if (seqI >= seq.length) return seqTotal();
  const c = seq[seqI];
  return seqBounds[seqI][0] + Math.max(0, (curVid ? curVid.currentTime : c.start) - c.start);
}
function seekInput(val){
  const tot = seqTotal(); if (!tot) return;
  seekTo(Math.min(tot - 0.05, Math.max(0, tot * val / 1000)));
}
function seekTo(t){
  if (!seq.length) return;
  clearTimeout(seqTimer);
  const a = audio();
  if (seqBeat != null && a.src){
    a.currentTime = t;
    // ★브라우저가 아직 버퍼 안 된 구간 시크를 조용히 당겨 앉힌다(첫 재생 직후 실측:
    //   6.5초 요청 → 5.7초 안착). 음성이 시계이므로 **실제 앉은 지점**을 다시 읽어
    //   그 시각 기준으로 컷·영상을 맞춘다 — 안 그러면 화면과 음성·자막이 어긋난다.
    if (Math.abs(a.currentTime - t) > 0.05) t = a.currentTime;
  }
  let k = seqBounds.findIndex(([x, y]) => t >= x && t < y);
  if (k < 0) k = seq.length - 1;
  seqI = k;
  const c = seq[k];
  const v = vidFor(c.video_id, c._slot);
  v.currentTime = c.start + (t - seqBounds[k][0]);
  showVid(v);
  const remain = Math.max(50, (seqBounds[k][1] - t) * 1000);
  if (seqPaused){
    seqRemain = remain;                          // 멈춘 채로 자리만 옮김 — 재개하면 여기부터
  } else {
    v.play().catch(()=>{});
    if (seqBeat != null && a.src && !a.ended) a.play().catch(()=>{});
    schedStep(remain);
    if (seqBeat != null) tickSub();
  }
  if (seq[k + 1]) seat(seq[k + 1]);              // 다음 컷 미리 앉히기(step과 동일)
  paintCut();
}

// ── 미리보기 정지/재생·창 옮기기(2026-08-15 사장님 "화면 누르면 정지 재생 / 화면 이동") ──
// ★칸·전체 재생은 seqTimer(컷 순차 타이머)가 진행을 쥔다 — video.pause()만 하면 타이머가
//   계속 돌아 다음 컷으로 넘어간다. 그래서 정지는 타이머 남은 시간을 기억하고 멈추고,
//   재생은 딱 그 시간부터 다시 건다. 컷 순서·길이 계산은 그대로다(조작만 추가).
let seqPaused = false, seqNextAt = 0, seqRemain = 0;
function schedStep(ms){
  seqNextAt = Date.now() + ms;
  seqTimer = setTimeout(() => { seqI++; step(); }, ms);
}
function togglePause(ev){
  if (ev) ev.stopPropagation();
  if (!seq.length) return;                       // 재생 중이 아니면 무시
  if (!seqPaused){
    seqPaused = true;
    seqRemain = Math.max(50, seqNextAt - Date.now());   // 이 컷의 남은 시간
    clearTimeout(seqTimer);
    if (curVid) curVid.pause();
    const a = audio(); if (a && !a.paused) a.pause();
    clearInterval(subTimer);
    document.getElementById('pinfo').innerHTML = `${seqLabel}<br>⏸ 일시정지 — 누르면 이어서 재생`;
  } else {
    seqPaused = false;
    if (curVid) curVid.play().catch(()=>{});
    const a = audio();
    if (a && a.src && seqBeat != null && !a.ended) a.play().catch(()=>{});
    if (seqI < seq.length){
      schedStep(seqRemain);                      // 멈춘 지점부터 이어서(다음 컷으로 안 건너뜀)
      paintCut();
    }
    if (seqBeat != null) tickSub();
  }
  updatePlayBtns();
}
