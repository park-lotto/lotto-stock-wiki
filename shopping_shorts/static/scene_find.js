// ── 3단계 장면 보충 팝업(관제 209, 2026-10-14~15 사장님) ─────────────────────────
// 장면이 모자랄 때: 나라별 검색어(5개 언어) → 6곳(샤오홍슈·도우인·틱톡·인스타·핀터레스트·유튜브)을 새 탭으로 열고
// 사이트에서 📥 담기를 누르면 **이 작업의 아래 영상 소스**로 들어온다. 팝업 안 썸네일은 유튜브만(무료 쿼터).
// 사장님: "완전 무료로 / 여러 개일 수 있으니 아래쪽 소스 추가 부분에 담기게 / 썸네일은 유튜브만".
// ★6곳 주소·나라별 검색어 고르기 = lens_open.js(숏템파워와 같은 파일) — 두 벌 금지.
// ★작업에 더하는 판단 = 서버 _add_extra_source 한 곳(3단계 [담기]·사이트 📥 담기가 같이 부른다).
// ★필름에 놓는 건 사람이 아래 영상 소스의 🎞 필름에서 한다 — 그 길(filmroll · commitRoll)이 렌더·캡컷까지 간다.
// 스위치: DATA.scene_find_enabled(서버 scene_find_enabled, 비면 관리자만).

const SF = {beat: null, items: [], busy: false, cands: [], lang: 'auto', seen: null, poll: null};
const _SF_LANGS = [['auto', '🌍 해외 원본'], ['ko', '🇰🇷 한국어'], ['zh', '🇨🇳 중국어'], ['en', '🇺🇸 영어'], ['ja', '🇯🇵 일본어'], ['ru', '🇷🇺 러시아어']];

function sceneFindControl(i){
  if (!SL.server || !DATA.scene_find_enabled) return '';
  return `<button title="이 칸에 맞는 장면이 모자랄 때 — 나라별 검색어로 6곳을 열고 📥 담기로 아래 영상 소스에 모읍니다"
      onclick="openSceneFind(${i})">🔎 장면 찾기</button>`;
}

function _sfProduct(){
  const b = DATA.src_brief || {};
  for (const k of Object.keys(b)){ const p = ((b[k] || {}).product || '').trim(); if (p && !p.startsWith('담은 영상')) return p; }
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
#sfModal .sfrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
#sfModal input.sfkw{flex:1;min-width:200px;background:#0b0d13;border:1px solid #2c3242;color:#e8eaf0;border-radius:8px;padding:9px 10px;font-size:15px}
#sfModal .sfbtn{padding:8px 13px;border-radius:8px;border:1px solid #2c3242;background:#1f2330;color:#e8eaf0;font-weight:700;cursor:pointer;font-size:13px;white-space:nowrap}
#sfModal .sfbtn.acc{background:#2fe0b0;border-color:#2fe0b0;color:#04201c}
#sfModal .sfbtn.mk{border-color:#2fe0b0;color:#2fe0b0}
#sfModal .sfbtn.yt{border-color:#ff4e45;color:#ff8a84}
#sfModal .sfbtn:disabled{opacity:.5;cursor:wait}
#sfModal .sflang{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 4px}
#sfModal .sflang button{padding:5px 10px;border-radius:99px;border:1px solid #2c3242;background:#171b25;color:#c9cfdb;font-size:12.5px;cursor:pointer}
#sfModal .sflang button.on{background:#2fe0b0;border-color:#2fe0b0;color:#04201c;font-weight:700}
#sfModal .sfk{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #222838;flex-wrap:wrap}
#sfModal .sfk .t{flex:1;min-width:180px}#sfModal .sfk .t b{display:block}#sfModal .sfk .t span{font-size:12px;color:#9aa3b5}
#sfModal .sfgot{background:#0f2a22;border:1px solid #1d5c49;border-radius:9px;padding:8px 12px;margin-top:10px;font-size:13px}
#sfModal .sfgot:empty{display:none}
#sfModal .sfres{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:12px}
#sfModal .sfit{background:#1a1e2a;border:1px solid #2c3242;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
#sfModal .sfit .im{aspect-ratio:9/16;background:#0b0d13 center/cover no-repeat}
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
      <div class="sfrow"><input class="sfkw" id="sfKw" placeholder="찾을 제품을 입력 (예: 와플메이커)" value="${_sfEsc(_sfProduct())}">
        <button class="sfbtn mk" id="sfExp" onclick="sfExpand()">✨ 나라별 검색어 만들기</button></div>
      <div class="sflang" id="sfLang"></div>
      <div id="sfCands"></div>
      <div class="sfgot" id="sfGot"></div>
      <div class="sfmsg" id="sfMsg">✨ 검색어를 만들면 나라별로 <b>↗ 6곳 열기</b>(사이트에서 📥 담기) · <b>▶ 유튜브 보기</b>(여기서 바로 담기)를 쓸 수 있어요</div>
      <div class="sfres" id="sfRes"></div>
    </div></div>`;
  const kw = document.getElementById('sfKw');
  kw.addEventListener('keydown', e => { if (e.key === 'Enter') sfExpand(); });
  _sfRenderLang();
  _sfRenderGot();
  _sfStartPoll();
}

function closeSceneFind(){
  const el = document.getElementById('sfModal');
  if (el){ el.style.display = 'none'; el.innerHTML = ''; }
  // 폴링은 끄지 않는다 — 사장님이 다른 탭에서 📥 담기를 누르는 동안 아래 목록이 채워져야 한다(담기 목적지 시간 동안).
}

function _sfMsg(t){ const m = document.getElementById('sfMsg'); if (m) m.innerHTML = t || ''; }

function _sfRenderLang(){
  const box = document.getElementById('sfLang'); if (!box) return;
  box.innerHTML = _SF_LANGS.map(([k, l]) => `<button class="${SF.lang === k ? 'on' : ''}" onclick="sfSetLang('${k}')">${l}</button>`).join('');
}
function sfSetLang(k){ SF.lang = k; _sfRenderLang(); _sfRenderCands(); }

async function sfExpand(){
  const kw = (document.getElementById('sfKw').value || '').trim();
  if (!kw){ _sfMsg('찾을 제품을 먼저 넣어 주세요'); return; }
  const btn = document.getElementById('sfExp');
  btn.disabled = true; btn.textContent = '⏳ 만드는 중…';
  try{
    const fd = new FormData(); fd.append('keyword', kw); fd.append('n', '6');
    const d = await (await fetch('/api/lens/kw/expand', {method: 'POST', body: fd})).json();
    SF.cands = ((d && d.candidates) || []).filter(c => c && (c.ko || c.zh || c.en));
    const made = SF.cands.length;
    if (!made) SF.cands = [{ko: kw}];
    _sfRenderCands();
    _sfMsg(made ? '나라를 고르고 <b>↗ 6곳 열기</b>로 사이트에서 📥 담기를 누르면 아래 영상 소스로 들어와요'
                : '⚠️ 나라별 검색어를 못 만들었어요 — 입력한 검색어(한국어)로 열 수 있어요');
  }catch(e){ SF.cands = [{ko: kw}]; _sfRenderCands(); _sfMsg('검색어 만들기 실패 — 입력한 검색어로 찾을 수 있어요: ' + _sfEsc(e)); }
  btn.disabled = false; btn.textContent = '✨ 나라별 검색어 만들기';
}

function _sfRenderCands(){
  const box = document.getElementById('sfCands'); if (!box) return;
  box.innerHTML = SF.cands.map((c, k) => {
    const shown = _lensKwFor(c, 'youtube', SF.lang) || c.ko || '';
    const sub = ['ko', 'zh', 'en', 'ja', 'ru'].map(L => c[L]).filter(Boolean).join(' · ');
    return `<div class="sfk"><div class="t"><b>${_sfEsc(shown)}</b><span>${_sfEsc(sub)}</span></div>
      <button class="sfbtn acc" onclick="sfOpenSix(${k})" title="이 검색어로 6곳을 새 탭으로 엽니다 — 사이트에서 📥 담기를 누르면 이 작업 영상 소스로 들어와요">↗ 6곳 열기</button>
      <button class="sfbtn yt" onclick="sfYoutube(${k})" title="유튜브 결과를 여기 썸네일로 봅니다(무료)">▶ 유튜브 보기</button></div>`;
  }).join('');
}

async function _sfGrabTarget(){
  try{
    const r = await fetch(`/api/mix/scene_lab/${SL.job}/grab_target`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({on: true})});
    const d = await r.json();
    return !!(r.ok && d.ok);
  }catch(e){ return false; }
}

async function sfOpenSix(k){
  const c = SF.cands[k]; if (!c) return;
  // 고른 나라 검색어가 없으면(검색어 만들기 실패·입력한 말만 있을 때) 한국어로 연다 — 아무것도 안 열리는 것보다 낫다
  let targets = lensOpenTargets(c, SF.lang);
  if (!targets.length) targets = lensOpenTargets(c, 'ko');
  if (!targets.length){ _sfMsg('검색어가 비었어요'); return; }
  // 탭부터 연다(클릭 직후여야 팝업 차단을 덜 받는다) — 담기 목적지는 그다음에 켠다
  let opened = 0;
  targets.forEach(t => { try { const w = window.open(t.url, '_blank'); if (w){ try{ w.opener = null; }catch(_){} opened++; } } catch(e){} });
  const ok = await _sfGrabTarget();
  _sfStartPoll();
  const block = opened < targets.length
    ? ` · <b style="color:#ffb454">${opened}/${targets.length}곳만 열렸어요 — 주소창 오른쪽 🚫 팝업 차단에서 '항상 허용'을 눌러 주세요</b>` : '';
  _sfMsg((ok ? '✅ 지금부터 1시간 동안 사이트에서 📥 담기를 누른 영상이 <b>이 작업 영상 소스</b>로 들어와요' : '⚠️ 담기 연결 실패 — 다시 눌러 주세요') + block);
}

async function sfYoutube(k){
  const c = SF.cands[k]; if (!c || SF.busy) return;
  const kw = _lensKwFor(c, 'youtube', SF.lang) || c.ko || '';
  if (!kw) return;
  SF.busy = true; _sfMsg(`⏳ 유튜브에서 "${_sfEsc(kw)}" 찾는 중…`);
  try{
    const r = await fetch(`/api/mix/scene_lab/${SL.job}/yt_search`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({keyword: kw})});
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || ('실패 ' + r.status));
    const seen = new Set(SF.items.map(x => x.url));
    for (const it of (d.items || [])) if (it && it.url && !seen.has(it.url)){ SF.items.push(it); seen.add(it.url); }
    _sfRender();
    _sfMsg(`유튜브 "${_sfEsc(kw)}" ${(d.items || []).length}개 — 마음에 드는 영상의 <b>📥 담기</b>를 누르면 아래 영상 소스로 들어가요`);
  }catch(e){ _sfMsg('유튜브 찾기 실패: ' + _sfEsc(e.message || e)); }
  SF.busy = false;
}

function _sfRender(){
  const box = document.getElementById('sfRes'); if (!box) return;
  box.innerHTML = SF.items.map((it, k) => `<div class="sfit">
    <div class="im" style="background-image:url('${_sfEsc(it.thumbnail || '')}')"></div>
    <div class="ti">${_sfEsc(it.title || '')}</div>
    <div class="ac"><a class="sfbtn" href="${_sfEsc(it.url)}" target="_blank" rel="noopener" title="원본을 새 탭으로">▶</a>
      <button class="sfbtn acc" id="sfUse${k}" onclick="sfUse(${k})">📥 담기</button></div></div>`).join('');
}

async function sfUse(k){
  const it = SF.items[k]; if (!it) return;
  const btn = document.getElementById('sfUse' + k);
  if (btn){ btn.disabled = true; btn.textContent = '⏳ 받는 중…'; }
  try{
    const r = await fetch(`/api/mix/scene_lab/${SL.job}/add_source`, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: it.url, thumbnail: it.thumbnail || '', platform: it.platform || 'youtube', title: it.title || ''})});
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || ('실패 ' + r.status));
    if (btn) btn.textContent = '✅ 담김';
    await sfPollOnce();
  }catch(e){
    _sfMsg('담지 못했어요: ' + _sfEsc(e.message || e));
    if (btn){ btn.disabled = false; btn.textContent = '📥 담기'; }
  }
}

// ── 담긴 영상 → 아래 영상 소스 목록(서버 /extra_sources 를 몇 초마다 본다) ──
function _sfStartPoll(){
  if (SF.poll) return;
  SF.poll = setInterval(sfPollOnce, 4000);
  sfPollOnce();
}

async function sfPollOnce(){
  let d;
  try{ d = await (await fetch(`/api/mix/scene_lab/${SL.job}/extra_sources`)).json(); }catch(e){ return; }
  if (!d || !d.ok) return;
  SF.got = d.sources || {};
  let added = [];
  for (const [vid, s] of Object.entries(SF.got)){
    if (s.pending || !(s.duration > 0.1)) continue;
    if ((DATA.src_duration || {})[vid]) continue;
    _sfAddSource(vid, s); added.push(vid);
  }
  if (added.length){
    if (typeof render === 'function') render();
    nsay(`영상 소스에 새 영상 ${added.length}개가 들어왔어요 — 아래 🎞 필름에서 구간을 골라 칸에 담으세요`);
  }
  _sfRenderGot();
  const anyPending = Object.values(SF.got).some(s => s.pending);
  const modalOpen = !!(document.getElementById('sfModal') || {}).innerHTML;
  if (!d.grab_target && !anyPending && !modalOpen){ clearInterval(SF.poll); SF.poll = null; }
}

function _sfAddSource(vid, s){
  DATA.src_duration = DATA.src_duration || {};
  DATA.src_duration[vid] = s.duration;
  DATA.src_brief = DATA.src_brief || {};
  if (!DATA.src_brief[vid]) DATA.src_brief[vid] = {product: '담은 영상' + (s.platform ? ' · ' + s.platform : ''), role: String(s.title || '').slice(0, 40)};
  const sid = `film_${vid}_0.00_${(+s.duration).toFixed(2)}`;
  DATA.segments = DATA.segments || {};
  if (!DATA.segments[sid]) DATA.segments[sid] = {video_id: vid, start: 0, end: +s.duration, scene_desc: s.title || '', text: '',
    label: '영상 통째', shot_role: '기타', is_key: false, benefits: [], auto_ok: false};
  if (typeof _SRC_NO !== 'undefined' && _SRC_NO && _SRC_NO[vid] === undefined)
    _SRC_NO[vid] = 1 + Math.max(0, ...Object.values(_SRC_NO));
}

function _sfRenderGot(){
  const box = document.getElementById('sfGot'); if (!box) return;
  const rows = Object.entries(SF.got || {});
  box.innerHTML = rows.length ? '📥 이 작업에 담긴 영상: ' + rows.map(([vid, s]) =>
    `<b>${s.pending ? '⏳' : '✅'} ${_sfEsc(s.platform || vid)}</b>${s.pending ? ' 받는 중' : ` ${(+s.duration).toFixed(1)}초`}`).join(' · ')
    + ' — 아래 영상 소스의 🎞 필름에서 칸에 담으세요' : '';
}
