// ── 3단계 장면 보충 팝업(관제 209, 2026-10-14 사장님) ─────────────────────────
// 장면이 모자란 칸에서 키워드로 영상을 찾아 → 고르면 그 job 원본에 '영상 N'으로 더하고
// → 가운데 필름에 펴서 그 칸 길이만큼 노란 박스를 올리고 → 그 칸에 담는다.
// ★검색은 숏템파워 검색 패널과 같은 API(/api/lens/kw/expand · /api/lens/kw/search)를 부른다 — 두 벌 금지.
// ★원본에 더하는 판단은 서버 /api/mix/scene_lab/{job}/add_source(→ mix_pipeline.extra_source_paths) 한 곳.
// ★박스·담기는 사람이 ＋ 구간으로 할 때와 같은 길(filmroll addBox · commitRoll)을 탄다 — 렌더·캡컷이 그대로 따라온다.
// 스위치: DATA.scene_find_enabled(서버 scene_find_enabled, 비면 관리자만).

const SF = {beat: null, items: [], busy: false, cands: []};

function sceneFindControl(i){
  if (!SL.server || !DATA.scene_find_enabled) return '';
  return `<button title="이 칸에 맞는 장면이 모자랄 때 — 키워드로 영상을 찾아 필름에 넣고 이 칸에 담습니다"
      onclick="openSceneFind(${i})">🔎 장면 찾기</button>`;
}

function _sfProduct(){
  const b = DATA.src_brief || {};
  for (const k of Object.keys(b)){ const p = ((b[k] || {}).product || '').trim(); if (p) return p; }
  return '';
}

function _sfEsc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function _sfEnsureBox(){
  let el = document.getElementById('sfModal');
  if (el) return el;
  const st = document.createElement('style');
  st.textContent = `
#sfModal{position:fixed;inset:0;background:#000a;z-index:9999;display:flex;align-items:flex-start;justify-content:center;padding:4vh 12px;overflow:auto}
#sfModal .sfw{background:#12151d;border:1px solid #3a4258;border-radius:14px;width:min(980px,100%);color:#e8eaf0;box-shadow:0 10px 40px #0008}
#sfModal .sfh{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #2c3242}
#sfModal .sfh b{font-size:16px}#sfModal .sfh .x{margin-left:auto;cursor:pointer;font-size:18px;background:none;border:0;color:#9aa3b5}
#sfModal .sfb{padding:14px 16px}
#sfModal .sfctx{background:#1f2330;border-radius:9px;padding:8px 12px;font-size:13px;margin-bottom:10px}
#sfModal .sfrow{display:flex;gap:8px;align-items:center}
#sfModal input.sfkw{flex:1;background:#0b0d13;border:1px solid #2c3242;color:#e8eaf0;border-radius:8px;padding:9px 10px;font-size:15px}
#sfModal .sfbtn{padding:8px 13px;border-radius:8px;border:1px solid #2c3242;background:#1f2330;color:#e8eaf0;font-weight:700;cursor:pointer;font-size:13px;white-space:nowrap}
#sfModal .sfbtn.acc{background:#2fe0b0;border-color:#2fe0b0;color:#04201c}
#sfModal .sfbtn.mk{border-color:#2fe0b0;color:#2fe0b0}
#sfModal .sfbtn:disabled{opacity:.5;cursor:wait}
#sfModal .sfk{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #222838}
#sfModal .sfk .t{flex:1;min-width:0}#sfModal .sfk .t b{display:block}#sfModal .sfk .t span{font-size:12px;color:#9aa3b5}
#sfModal .sfres{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:12px}
#sfModal .sfit{background:#1a1e2a;border:1px solid #2c3242;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
#sfModal .sfit .im{aspect-ratio:9/16;background:#0b0d13 center/cover no-repeat;position:relative}
#sfModal .sfit .im span{position:absolute;left:4px;top:4px;font-size:11px;background:#000b;padding:0 6px;border-radius:5px}
#sfModal .sfit .ti{font-size:12px;padding:6px 7px;color:#c9cfdb;height:34px;overflow:hidden}
#sfModal .sfit .ac{display:flex;gap:4px;padding:0 6px 7px}
#sfModal .sfit .ac .sfbtn{flex:1;padding:6px 4px;font-size:12px}
#sfModal .sfmsg{font-size:13px;color:#9aa3b5;margin-top:8px;min-height:18px}`;
  document.head.appendChild(st);
  el = document.createElement('div');
  el.id = 'sfModal';
  el.addEventListener('click', e => { if (e.target === el) closeSceneFind(); });
  document.body.appendChild(el);
  return el;
}

function openSceneFind(i){
  SF.beat = i; SF.items = []; SF.cands = [];
  const el = _sfEnsureBox();
  el.style.display = 'flex';
  const need = (typeof beatDur === 'function') ? beatDur(i) : 3;
  const narr = ((DATA.beats || [])[i] || {}).narration || ((DATA.beats || [])[i] || {}).text || '';
  el.innerHTML = `<div class="sfw">
    <div class="sfh"><b>🔎 ${i + 1}번 칸 장면 찾기</b><span style="color:#9aa3b5;font-size:13px">이 칸 ${need.toFixed(1)}초</span>
      <button class="x" onclick="closeSceneFind()" title="닫기">✕</button></div>
    <div class="sfb">
      ${narr ? `<div class="sfctx">대사: <b>${_sfEsc(narr)}</b></div>` : ''}
      <div class="sfrow"><input class="sfkw" id="sfKw" placeholder="찾을 제품을 직접 입력 (예: 와플메이커)" value="${_sfEsc(_sfProduct())}">
        <button class="sfbtn mk" id="sfExp" onclick="sfExpand()">✨ 검색어 만들기</button>
        <button class="sfbtn acc" onclick="sfSearch(document.getElementById('sfKw').value)">🔎 바로 찾기</button></div>
      <div id="sfCands"></div>
      <div class="sfmsg" id="sfMsg"></div>
      <div class="sfres" id="sfRes"></div>
    </div></div>`;
  const kw = document.getElementById('sfKw');
  kw.addEventListener('keydown', e => { if (e.key === 'Enter') sfSearch(kw.value); });
}

function closeSceneFind(){
  const el = document.getElementById('sfModal');
  if (el){ el.style.display = 'none'; el.innerHTML = ''; }
}

function _sfMsg(t){ const m = document.getElementById('sfMsg'); if (m) m.textContent = t || ''; }

async function sfExpand(){
  const kw = (document.getElementById('sfKw').value || '').trim();
  if (!kw){ _sfMsg('찾을 제품을 먼저 넣어 주세요'); return; }
  const btn = document.getElementById('sfExp');
  btn.disabled = true; btn.textContent = '⏳ 만드는 중…';
  try{
    const fd = new FormData(); fd.append('keyword', kw); fd.append('n', '6');
    const d = await (await fetch('/api/lens/kw/expand', {method: 'POST', body: fd})).json();
    SF.cands = (d && d.candidates) || [];
    const box = document.getElementById('sfCands');
    box.innerHTML = SF.cands.length ? SF.cands.map((c, k) => {
      const ko = c.ko || c.keyword || '';
      const sub = [c.en, c.zh, c.ja].filter(Boolean).join(' · ');
      return `<div class="sfk"><div class="t"><b>${_sfEsc(ko)}</b><span>${_sfEsc(sub)}</span></div>
        <button class="sfbtn acc" onclick="sfSearch(SF.cands[${k}].ko || SF.cands[${k}].keyword)">🔎 아래로 모아서 보기</button></div>`;
    }).join('') : '';
    _sfMsg(SF.cands.length ? '검색어를 눌러 영상을 모으세요' : '검색어를 못 만들었어요 — 바로 찾기를 눌러 보세요');
  }catch(e){ _sfMsg('검색어 만들기 실패: ' + e); }
  btn.disabled = false; btn.textContent = '✨ 검색어 만들기';
}

async function sfSearch(kw){
  kw = (kw || '').trim();
  if (!kw){ _sfMsg('검색어가 비었어요'); return; }
  if (SF.busy) return;
  SF.busy = true; _sfMsg(`⏳ "${kw}" 찾는 중… (유튜브·인스타·틱톡)`);
  try{
    const fd = new FormData(); fd.append('keyword', kw); fd.append('max_results', '12');
    const r = await fetch('/api/lens/kw/search', {method: 'POST', body: fd});
    const d = await r.json();
    if (!r.ok || !d.ok){ _sfMsg(d.error || ('찾기 실패 ' + r.status)); SF.busy = false; return; }
    const seen = new Set(SF.items.map(x => x.url));
    for (const it of (d.items || [])) if (it && it.url && !seen.has(it.url)){ SF.items.push(it); seen.add(it.url); }
    _sfRender();
    _sfMsg(`"${kw}" ${(d.items || []).length}개 — 마음에 드는 영상의 [이 칸에 쓰기]를 누르세요`);
  }catch(e){ _sfMsg('찾기 실패: ' + e); }
  SF.busy = false;
}

function _sfRender(){
  const box = document.getElementById('sfRes');
  if (!box) return;
  box.innerHTML = SF.items.map((it, k) => `<div class="sfit">
    <div class="im" style="background-image:url('${_sfEsc(it.thumbnail || '')}')"><span>${_sfEsc(it.platform || '')}</span></div>
    <div class="ti">${_sfEsc(it.title || '')}</div>
    <div class="ac"><a class="sfbtn" href="${_sfEsc(it.url)}" target="_blank" rel="noopener" title="원본을 새 탭으로">▶</a>
      <button class="sfbtn acc" id="sfUse${k}" onclick="sfUse(${k})">이 칸에 쓰기</button></div></div>`).join('');
}

async function sfUse(k){
  const it = SF.items[k], i = SF.beat;
  if (!it || i == null) return;
  const btn = document.getElementById('sfUse' + k);
  if (btn){ btn.disabled = true; btn.textContent = '⏳ 받는 중…'; }
  _sfMsg('영상을 받아 필름에 넣는 중… (10~40초)');
  try{
    const r = await fetch(`/api/mix/scene_lab/${SL.job}/add_source`, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: it.url, thumbnail: it.thumbnail || '', platform: it.platform || '', beat_idx: i})});
    const d = await r.json();
    if (!r.ok || !d.ok){ throw new Error(d.error || ('실패 ' + r.status)); }
    sfPlace(i, d.video_id, +d.duration || 0);
    closeSceneFind();
  }catch(e){
    _sfMsg('넣지 못했어요: ' + (e.message || e));
    if (btn){ btn.disabled = false; btn.textContent = '이 칸에 쓰기'; }
  }
}

// 받아 온 영상을 필름에 펴고 그 칸 길이만큼 노란 박스 → 그 칸에 담기(사람이 ＋ 구간·담기를 누른 것과 같은 길).
function sfPlace(i, vid, dur){
  if (!vid || !(dur > 0.1)){ nsay('영상 길이를 몰라 담지 못했어요'); return; }
  DATA.src_duration = DATA.src_duration || {};
  DATA.src_duration[vid] = dur;
  // '영상 N' 번호 — 기존 번호 다음(srcNo2가 읽는 표)
  if (typeof srcNo === 'function'){ const k0 = Object.keys(DATA.segments || {})[0]; if (k0) srcNo(k0); }
  if (typeof _SRC_NO !== 'undefined'){
    if (_SRC_NO === null) _SRC_NO = {};
    if (_SRC_NO[vid] === undefined) _SRC_NO[vid] = 1 + Math.max(0, ...Object.values(_SRC_NO));
  }
  const need = Math.min(dur, (typeof beatDur === 'function') ? beatDur(i) : 3);
  if (ROLL.key) closeRoll(ROLL);
  toggleRoll('src', vid);
  try{ if (ROLL.inst && ROLL.inst.addBox) ROLL.inst.addBox(0, need); }catch(e){ console.warn('[장면 찾기] 박스 실패', e); }
  commitRoll('src', vid, vid, [{s: 0, e: need}], i);
  nsay(`${i + 1}번 칸에 새 영상(영상 ${srcNo2(vid)}) ${need.toFixed(1)}초를 담았어요 — 노란 박스를 끌어 구간을 옮길 수 있어요`);
}
