// 숏템 작업실 탭(관제 291) — 설정 화면(index.html) 위에 [설정·수정 | 진행현황 | 원본 찾기] 탭을 얹는다.
//   이 파일은 회원 PC(local_ui.js /work.js)에서만 받는다 — 서버판(/claude/studio)은 이 파일이 없어 탭이 안 생긴다(따로 판정 안 적음).
//   읽기 = /api/flows·/api/flow(work_view.js), 버튼 = /api/flow/approve·retry(flow_driver 와 같은 함수). 판단 0.
//   디자인: 색·글꼴·버튼은 index.html 토큰이 정본, 탭 알약(9999px·높이 ≥36px)은 linear.app DESIGN.md, 움직임 ease-out 200ms(emil-design).
(() => {
'use strict';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const get = p => fetch(p, { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null);
const post = (p, b) => fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Shortem-UI': '1' }, body: JSON.stringify(b) }).then(r => r.json()).catch(() => null);
const ago = t => { if (!t) return ''; const s = Math.max(0, (Date.now() - t) / 1000); return s < 60 ? '방금' : s < 3600 ? `${Math.floor(s / 60)}분 전` : s < 86400 ? `${Math.floor(s / 3600)}시간 전` : `${Math.floor(s / 86400)}일 전`; };
const NEED = { wait: ['⏳', '만드는 중'], ai: ['🤖', 'AI 판정 중'], approve: ['✍', '사인 기다림'], fail: ['⏸', '멈춤'], done: ['🎬', '완성'] };
const MODE = { lens: '같은 장면 검색', peers: '같은 제품 다른 반응', find: '검색어로 찾기' };
const PLAT = { yt: '유튜브', tiktok: '틱톡', ig: '인스타', instagram: '인스타' };
const TAG = { of_judge: '원본 후보 판정', of_peer: '원본 후보 판정', of_find: '원본 찾을 곳 정하기', of_verify: '원본 실제 장면 확인' };
// 판정 이름 → 화면 말(이름 앞부분만 본다 — 판 이름이 뒤에 붙는다)
const TAG_PRE = [['ref_read', '소재 영상 읽기'], ['research', '제품 자료 조사'], ['product_', '제품 고르기'], ['script_', '대본 쓰기'], ['plan_', '장면 계획'],
  ['shot_', '장면 고르기'], ['thumb_', '표지 만들기'], ['render_fix_', '렌더 검수'], ['final_fix_', '완성본 검수'], ['task_', '작업 확인']];
const tagName = t => TAG[t] || (TAG_PRE.find(([p]) => String(t).startsWith(p)) || [, 'AI 판정'])[1];

const css = `
.wtabs{display:flex;gap:6px;padding:4px;background:var(--panel);border:1px solid var(--line);border-radius:9999px;width:max-content;max-width:100%;overflow:auto}
.wtab{font:inherit;font-weight:700;font-size:13.5px;min-height:38px;padding:0 18px;border-radius:9999px;border:0;background:none;color:var(--mute);cursor:pointer;white-space:nowrap;transition:background .2s ease-out,color .2s ease-out}
.wtab:active{transform:scale(.97)}
.wtab.on{background:linear-gradient(145deg,#7d5cff,#5b3fd8);color:#fff;box-shadow:0 6px 20px rgba(110,80,255,.35)}
.wtab b{display:inline-grid;place-items:center;min-width:18px;height:18px;margin-left:6px;padding:0 5px;border-radius:9px;background:var(--rose);color:#fff;font-size:11px}
.wpane{display:grid;gap:16px;animation:wIn .2s ease-out}
.wpane[hidden]{display:none}
@keyframes wIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.wgrid{display:grid;grid-template-columns:300px minmax(0,1fr);gap:20px;align-items:start}
@media (max-width:920px){.wgrid{grid-template-columns:minmax(0,1fr)}}
.wcard{background:linear-gradient(180deg,var(--panel) 0%,var(--bg2) 100%);border:1px solid var(--line);border-radius:16px;padding:18px;display:grid;gap:14px;min-width:0}
.wcard h2{margin:0;font-size:16px}
.wlist{display:grid;gap:6px}
.witem{font:inherit;text-align:left;color:var(--fg);background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:10px 12px;cursor:pointer;display:grid;gap:3px;transition:border-color .2s ease-out}
.witem.on{border-color:var(--violet2)}.witem small{color:var(--mute);font-size:12px}
.wbar{height:8px;border-radius:9999px;background:var(--panel2);overflow:hidden}.wbar i{display:block;height:100%;background:linear-gradient(90deg,var(--violet),var(--mint));transition:width .3s ease-out}
.wbig{font-size:18px;font-weight:800;display:flex;gap:10px;align-items:center}
.wmsg{color:var(--fg);font-size:14px}.wmute{color:var(--mute);font-size:12.5px}
.wfail{border:1px solid var(--rose);background:rgba(255,107,139,.08);border-radius:12px;padding:12px;display:grid;gap:6px}
.wscript{background:var(--bg2);border:1px solid var(--line);border-radius:12px;padding:12px;white-space:pre-wrap;font-size:13.5px;max-height:320px;overflow:auto}
.wrow{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.wsteps{display:grid;gap:8px}
.wstep{display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px;align-items:start}
.wstep>i{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;font-style:normal;background:var(--panel2);border:1px solid var(--line);font-size:13px}
.wstep.ok>i{background:rgba(63,224,192,.15);border-color:var(--mint)}.wstep.now>i{border-color:var(--violet2);box-shadow:0 0 0 4px rgba(139,108,255,.18)}
.wthumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:8px}
.wthumb{position:relative;border-radius:10px;overflow:hidden;background:var(--bg2);border:1px solid var(--line);animation:wIn .2s ease-out both}
.wthumb img{display:block;width:100%;aspect-ratio:9/12;object-fit:cover}
.wthumb .t{font-size:11px;padding:5px 6px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wthumb .v{position:absolute;top:6px;right:6px;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:900}
.wthumb.yes{border-color:var(--mint)}.wthumb.yes .v{background:var(--mint);color:#04211b}
.wthumb.no{opacity:.45}.wthumb.no .v{background:var(--panel2);color:var(--mute)}
.wseed{display:flex;gap:6px;overflow:auto}.wseed img{height:150px;border-radius:8px;border:1px solid var(--line)}
.wsheet{max-width:100%;border-radius:10px;border:1px solid var(--line)}
.wpill{display:inline-flex;gap:4px;align-items:center;font-size:12px;padding:3px 10px;border-radius:9999px;background:var(--panel2);border:1px solid var(--line)}
.wpill.ok{border-color:var(--mint);color:var(--mint)}.wpill.bad{border-color:var(--rose);color:var(--rose)}
.wempty{color:var(--mute);padding:30px;text-align:center}
`;

const W = { tab: 'set', sid: null, list: [], view: null, busy: false };

function mount() {
  const wrap = document.querySelector('.wrap'), steps = $('steps'), main = document.querySelector('.wrap > .main');
  if (!wrap || !steps || !main) return false;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  const h1 = document.querySelector('.head h1'); if (h1) h1.textContent = '숏템 작업실';
  const tabs = document.createElement('nav'); tabs.className = 'wtabs'; tabs.id = 'wtabs';
  tabs.innerHTML = '<button class="wtab on" data-t="set">⚙ 설정·수정</button><button class="wtab" data-t="run">▶ 진행현황</button><button class="wtab" data-t="of">🔍 원본 찾기</button>';
  wrap.insertBefore(tabs, steps);
  const set = document.createElement('div'); set.id = 'wset'; set.style.display = 'contents';
  wrap.insertBefore(set, steps); set.append(steps, main);
  for (const k of ['run', 'of']) { const p = document.createElement('section'); p.id = 'w' + k; p.className = 'wpane'; p.hidden = true; wrap.appendChild(p); }
  tabs.onclick = e => { const b = e.target.closest('[data-t]'); if (b) go(b.dataset.t); };
  $('wrun').onclick = $('wof').onclick = onClick;
  return true;
}

function go(t) {
  W.tab = t;
  for (const b of $('wtabs').children) b.classList.toggle('on', b.dataset.t === t);
  $('wset').style.display = t === 'set' ? 'contents' : 'none';
  $('wrun').hidden = t !== 'run'; $('wof').hidden = t !== 'of';
  if (t !== 'set') tick();
}

async function onClick(e) {
  const it = e.target.closest('[data-sid]'); if (it) { W.sid = it.dataset.sid; W.view = null; return tick(); }
  const b = e.target.closest('[data-act]'); if (!b || W.busy) return;
  W.busy = true; b.disabled = true;
  const r = await post('api/flow/' + b.dataset.act, { sid: W.sid });
  if (r && r.flow) W.view = r.flow;
  W.busy = false; draw();
}

async function tick() {
  const l = await get('api/flows');
  if (!l) return;
  W.list = l.flows || [];
  if (!W.sid || !W.list.some(f => f.sid === W.sid)) W.sid = W.list[0] && W.list[0].sid;
  W.view = W.sid ? await get('api/flow?sid=' + W.sid) : null;
  const b = $('wtabs').querySelector('[data-t="run"]'), n = W.list.filter(f => f.need === 'approve' || f.need === 'fail').length;
  b.innerHTML = '▶ 진행현황' + (n ? `<b>${n}</b>` : '');
  draw();
}

function listHtml() {
  if (!W.list.length) return '<div class="wempty">아직 만든 영상이 없습니다.<br>Claude 에게 "영상 만들어줘"라고 하면 여기에 진행이 뜹니다.</div>';
  return '<div class="wlist">' + W.list.map(f => {
    const [ic, t] = NEED[f.need] || ['•', f.need];
    return `<button class="witem ${f.sid === W.sid ? 'on' : ''}" data-sid="${f.sid}"><span>${ic} ${esc(f.title || f.stage || t)}</span><small>${esc(t)}${f.step_total ? ` · ${f.step}/${f.step_total}` : ''} · ${ago(f.updated)}</small></button>`;
  }).join('') + '</div>';
}

function runHtml(v) {
  if (!v) return '<div class="wcard"><div class="wempty">고를 작업이 없습니다</div></div>';
  const [ic, t] = NEED[v.need] || ['•', v.need];
  const pct = v.step_total ? Math.round(v.step / v.step_total * 100) : (v.need === 'done' ? 100 : 0);
  let body = `<div class="wbig">${ic} ${esc(v.stage || t)}</div>
    ${v.step_total ? `<div class="wbar"><i style="width:${pct}%"></i></div><div class="wmute">${v.step}/${v.step_total} 단계 · ${esc(t)}</div>` : ''}
    ${v.message && v.message !== v.stage ? `<div class="wmsg">${esc(v.message)}</div>` : ''}`;
  if (v.waiting_ai && v.waiting_ai.length) body += `<div class="wrow">${v.waiting_ai.map(x => `<span class="wpill">🤖 ${esc(tagName(x))} 기다리는 중</span>`).join('')}</div>`;
  if (v.need === 'fail') body += `<div class="wfail"><b>⏸ ${esc(v.fail.why)}</b>${v.fail.fix ? `<span class="wmute">${esc(v.fail.fix)}</span>` : ''}${v.fail.retry_ok ? '<div><button class="btn pri" data-act="retry">👉 다시 시도</button></div>' : ''}</div>`;
  if (v.need === 'approve') body += `<div class="wmute">대본을 확인하고 사인해 주세요. 사인 전에는 목소리 합성·렌더를 하지 않습니다.</div><div class="wscript">${esc(scriptText(v.script))}</div><div><button class="btn pri" data-act="approve">✍ 이 대본으로 만들기</button></div>`;
  if (v.need === 'done' && v.video) body += `<div class="wmute">완성본: ${esc(v.title || '')}</div>`;
  const rv = v.reviews || [];
  if (rv.length) body += '<h2>AI 판정 기록</h2><div class="wsteps">' + rv.slice(-8).map(r => `<div class="wstep ${r.answered ? 'ok' : 'now'}"><i>${r.answered ? '✓' : '…'}</i><div><b>${esc(tagName(r.tag))}</b> <span class="wmute">${ago(r.at)}${r.part ? ' · 소재 ' + esc(r.part.slice(1)) : ''}</span>${r.answer && r.answer.why ? `<div class="wmute">${esc(r.answer.why)}</div>` : ''}</div></div>`).join('') + '</div>';
  return `<div class="wcard">${body}</div>`;
}

function scriptText(s) {
  if (!s) return '';
  if (typeof s === 'string') return s;
  if (Array.isArray(s)) return s.map(x => typeof x === 'string' ? x : (x.text || x.line || JSON.stringify(x))).join('\n');
  return [s.title && '제목: ' + (Array.isArray(s.title) ? s.title.join(' / ') : s.title), ...(s.lines || s.script || []).map(x => typeof x === 'string' ? x : (x.text || ''))].filter(Boolean).join('\n');
}

function ofHtml(v) {
  if (!v) return '<div class="wcard"><div class="wempty">고를 작업이 없습니다</div></div>';
  const parts = v.origin || [];
  if (!parts.length) return `<div class="wcard"><div class="wbig">🔍 원본 찾기</div><div class="wempty">${v.need === 'done' ? '이 편은 원본 찾기 기록이 없습니다' : '아직 원본 찾기 전입니다 — 시작하면 후보가 여기에 하나씩 떠오릅니다'}</div></div>`;
  return parts.map((p, i) => {
    let h = `<div class="wbig">🔍 원본 찾기${parts.length > 1 ? ' · 소재 ' + (i + 1) : ''}</div>`;
    if (p.seeds.length) h += `<div><div class="wmute">① 소재 영상 장면</div><div class="wseed">${p.seeds.map(s => `<img src="${s}" alt="" loading="lazy">`).join('')}</div></div>`;
    p.rounds.forEach((r, k) => {
      const yes = r.cands.filter(c => c.same).length;
      h += `<div><div class="wrow"><b>${k + 2}. ${esc(MODE[r.mode] || r.mode)}</b><span class="wpill">후보 ${r.cands.length}개</span>${r.judged ? `<span class="wpill ${yes ? 'ok' : 'bad'}">AI 판정 · 같음 ${yes}개</span>` : r.legacy ? '<span class="wpill">AI 판정 끝남(이전 판 기록이라 후보 표시 없음)</span>' : '<span class="wpill">🤖 AI 판정 중</span>'}</div>
        ${r.why ? `<div class="wmute" style="margin:6px 0">${esc(r.why)}</div>` : ''}
        ${!r.cands.some(c => c.thumb) && p.sheets.length ? `<div class="wmute" style="margin:6px 0">AI 가 본 후보 판</div>${p.sheets.map(s => `<img class="wsheet" src="${s}" alt="" loading="lazy">`).join('')}` : ''}
        <div class="wthumbs" style="margin-top:8px${r.cands.some(c => c.thumb) ? '' : ';display:none'}">${r.cands.map((c, j) => `<div class="wthumb ${c.same === true ? 'yes' : c.same === false ? 'no' : ''}" style="animation-delay:${Math.min(j, 20) * 30}ms">
          ${c.thumb ? `<img src="${c.thumb}" alt="" loading="lazy">` : '<div style="aspect-ratio:9/12"></div>'}${c.same === null ? '' : `<span class="v">${c.same ? '○' : '✕'}</span>`}
          <div class="t">${esc(PLAT[c.platform] || c.platform || '')}${c.views ? ' · ' + Number(c.views).toLocaleString('ko-KR') : ''}</div></div>`).join('')}</div></div>`;
    });
    p.verify.forEach(r => {
      h += `<div><div class="wrow"><b>실제 장면 확인</b>${r.answered ? r.rows.map(x => `<span class="wpill ${x.ok ? 'ok' : 'bad'}">${x.ok ? '✅ 같은 영상' : '❌ 다른 영상'}</span>`).join('') : '<span class="wpill">🤖 확인 중</span>'}</div>
        ${r.why ? `<div class="wmute" style="margin:6px 0">${esc(r.why)}</div>` : ''}
        <div class="wthumbs" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr));margin-top:8px">${r.images.map(s => `<img class="wsheet" src="${s}" alt="" loading="lazy">`).join('')}</div></div>`;
    });
    return `<div class="wcard">${h}</div>`;
  }).join('');
}

function draw() {
  const pane = W.tab === 'run' ? $('wrun') : W.tab === 'of' ? $('wof') : null;
  if (!pane) return;
  const html = `<div class="wgrid"><div class="wcard"><h2>내 작업</h2>${listHtml()}</div><div style="display:grid;gap:16px;min-width:0">${W.tab === 'run' ? runHtml(W.view) : ofHtml(W.view)}</div></div>`;
  if (pane._html === html) return;     // 바뀐 게 없으면 다시 그리지 않는다(등장 움직임·그림이 2.5초마다 깜빡이지 않게)
  const y = scrollY;
  pane.innerHTML = pane._html = html;
  scrollTo(0, y);
}

if (mount()) setInterval(() => { if (!document.hidden && W.tab !== 'set' && !W.busy) tick(); }, 2500);
})();
