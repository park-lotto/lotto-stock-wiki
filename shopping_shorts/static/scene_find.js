// ── 3단계 장면 보충 팝업(관제 209, 2026-10-14~15 사장님) ─────────────────────────
// 사장님: "첫 장면은 숏템파워를 동일하게, 대본 분석 없이" / "담기 버튼을 하나 더 만들어야 안 헷갈리지".
// ★팝업 = 숏템파워 화면 그대로(index.html ?kwfind=<제품>&job=<작업>&embed=1 → openKwFind). 화면 두 벌 금지.
//   그 안에서 나라별 검색어·6곳 새 탭·🔎 모아서 보기(이 모드는 유튜브만, 무료)·카드마다 「🎬 3단계에 담기」.
//   사이트에서 📥를 누르면 뜨는 창에도 「🎬 3단계 작업에 담기」가 따로 뜬다(서버 _grab_choice_html).
// ★작업에 더하는 판단 = 서버 _add_extra_source 한 곳. 담긴 영상은 아래 영상 소스에 「영상 N — 담은 영상」으로 뜨고,
//   사람이 🎞 필름에서 구간을 골라 칸에 담는다(그 길이 렌더·캡컷까지 간다).
// 스위치: DATA.scene_find_enabled(서버 scene_find_enabled, 비면 관리자만).

const SF = {beat: null, got: {}, poll: null};

function sceneFindControl(i){
  if (!SL.server || !DATA.scene_find_enabled) return '';
  return `<button title="이 칸에 맞는 장면이 모자랄 때 — 숏템파워로 찾아 🎬 3단계에 담기로 아래 영상 소스에 모읍니다"
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
#sfModal{position:fixed;inset:0;background:#000a;z-index:9999;display:flex;align-items:stretch;justify-content:center;padding:2vh 12px}
#sfModal .sfw{background:#0b0f16;border:1px solid #3a4258;border-radius:14px;width:min(1100px,100%);display:flex;flex-direction:column;overflow:hidden;box-shadow:0 10px 40px #0008}
#sfModal .sfh{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid #2c3242;color:#e8eaf0}
#sfModal .sfh b{font-size:15px}#sfModal .sfh .x{margin-left:auto;cursor:pointer;font-size:18px;background:none;border:0;color:#9aa3b5}
#sfModal .sfgot{font-size:12.5px;color:#a7f3d0;padding:6px 14px;border-bottom:1px solid #1d4f3c;background:#0f2a22}
#sfModal .sfgot:empty{display:none}
#sfModal iframe{flex:1;border:0;width:100%;background:#0b0f16}`;
  document.head.appendChild(st);
  el = document.createElement('div');
  el.id = 'sfModal';
  el.addEventListener('click', e => { if (e.target === el) closeSceneFind(); });
  document.body.appendChild(el);
  window.addEventListener('message', e => {
    if (e.origin === location.origin && e.data && e.data.ss === 'scene_find_added') sfPollOnce();
  });
  return el;
}

function openSceneFind(i){
  SF.beat = i;
  const el = _sfEnsureBox();
  el.style.display = 'flex';
  const need = (typeof beatDur === 'function') ? beatDur(i) : 3;
  const src = '/?' + new URLSearchParams({kwfind: _sfProduct(), job: SL.job, embed: '1'}).toString();
  el.innerHTML = `<div class="sfw">
    <div class="sfh"><b>🔎 ${i + 1}번 칸 장면 찾기</b><span style="color:#9aa3b5;font-size:12.5px">이 칸 ${need.toFixed(1)}초 · 카드의 <b style="color:#a7f3d0">🎬 3단계에 담기</b>나 사이트 📥 창의 <b style="color:#a7f3d0">🎬 3단계 작업에 담기</b>로 담으면 아래 영상 소스에 들어와요</span>
      <button class="x" onclick="closeSceneFind()" title="닫기">✕</button></div>
    <div class="sfgot" id="sfGot"></div>
    <iframe src="${src}" title="숏템파워 장면 찾기"></iframe></div>`;
  _sfRenderGot();
  _sfStartPoll();
}

function closeSceneFind(){
  const el = document.getElementById('sfModal');
  if (el){ el.style.display = 'none'; el.innerHTML = ''; }
  // 폴링은 끄지 않는다 — 다른 탭(사이트)에서 담는 동안 아래 목록이 채워져야 한다(담기 목적지 시간 동안).
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
  const newFail = (d.failed || []).filter(r => !(SF.failed || []).some(x => x.url === r.url));
  SF.failed = d.failed || [];
  if (newFail.length && typeof nsay === 'function') nsay('⚠️ 담은 영상 받기 실패 — ' + (newFail[0].reason || ''));
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
  const fails = (SF.failed || []).map(r => `⚠️ ${_sfEsc(r.platform || '')} 받기 실패 — ${_sfEsc(r.reason || '')}`).join(' · ');
  box.innerHTML = rows.length ? '📥 이 작업에 담긴 영상: ' + rows.map(([vid, s]) =>
    `<b>${s.pending ? '⏳' : '✅'} ${_sfEsc(s.platform || vid)}</b>${s.pending ? ' 받는 중' : ` ${(+s.duration).toFixed(1)}초`}`).join(' · ')
    + ' — 아래 영상 소스의 🎞 필름에서 칸에 담으세요' : '';
  if (fails) box.innerHTML += (box.innerHTML ? '<br>' : '') + `<span style="color:#fca5a5">${fails}</span>`;
}
