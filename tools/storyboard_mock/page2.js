// ── 2단계(2026-10-04 사장님): 대본 스타일 카드(같은 칸 구조는 한 카드) — 처음엔 아무것도 안 고름, 여러 개 고른 뒤 [스토리보드 만들기] → 실제 3.6 생성
let PICK = {}, MADE = {}, BUSY = {}, VIEW = {}, OPENF = {};
function picks2(){ return PICK[key()] = PICK[key()] || new Set(); }
function made(){ return MADE[key()] = MADE[key()] || {}; }
function tpick(k){ const s = picks2(); s.has(k) ? s.delete(k) : s.add(k); render(); }
function hl(t){ return String(t||'').replace(/\{([^}]+)\}/g, '<span class="slotw">$1</span>'); }
function rolesParam(){ return Object.entries(asg()).filter(([r, s]) => s.size).map(([r, s]) => r + '=' + [...s].join(',')).join('|'); }
async function makeBoards(){
  const ks = [...picks2()].filter(k => !made()[k]); if (!ks.length){ VIEW[key()] = [...picks2()][0]; render(); return; }
  ks.forEach(k => BUSY[key()+k] = true); render();
  const t0 = Date.now();
  try {
    const r = await fetch('/gen', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({jid: key(), keys: ks, roles: rolesParam()})});
    const d = await r.json(); Object.entries(d).forEach(([k, v]) => { if (!k.startsWith('_err')) made()[k] = Object.assign(v, {secs: Math.round((Date.now()-t0)/1000)}); });
    const errs = Object.keys(d).filter(k => k.startsWith('_err')); if (errs.length) console.log('[sb] 실패', d);
  } catch(e){ console.log('[sb] 요청 실패', e); alertBox('만들기 실패 — 시험 서버(127.0.0.1:8790)가 켜져 있어야 해요'); }
  ks.forEach(k => delete BUSY[key()+k]); VIEW[key()] = VIEW[key()] && made()[VIEW[key()]] ? VIEW[key()] : ks.find(k => made()[k]); render();
}
function alertBox(m){ const el = document.getElementById('msg2'); if (el) el.textContent = m; }
// 재료 종류와 스타일이 안 맞으면 막지 않고 알려 준다(2026-10-04 전수 검사: 레시피 전용 스타일을 필터 재료에 쓰면 상황이 어긋난다)
const KINDS = ['레시피','홈템','뷰티','생활용품','장비템','가전'];
function fitWarn(f){ const k = job().kind; const fk = (f.fit||[]).filter(c => KINDS.includes(c));
  if (!k || !fk.length || fk.includes(k)) return '';
  return `<div class="fwarn">⚠ ${fk.join('·')}용 스타일 — 이 재료(${k})엔 상황을 옮겨 써요</div>`; }
function famCard(f){
  const x = job(); const k = String(f.id); const on = picks2().has(k); const sc = (x.styles||[]).find(s => String(s.family) === k);
  const nm = f.names.length > 1 ? f.names[0] + ` <span class="note">외 ${f.names.length-1}</span>` : f.names[0];
  const first = (f.first||[]).slice(0, 2).map(t => `<div class="fq">“${hl(t)}”</div>`).join('');
  const st = OPENF[k] ? `<div class="fstruct">${f.roles.map((r, i) => `<div><b>${i+1}. ${ko(r)}</b> ${(f.chain[i]||'').slice(0,60)}</div>`).join('')}${f.names.length>1?`<div class="note">같은 구조 첫 줄 틀: ${f.names.join(' · ')}</div>`:''}</div>` : '';
  return `<div class="fcard ${on?'on':''} ${sc?'isrec':''}" onclick="tpick('${k}')">${sc?`<div class="recb">⭐ 추천 · 재료 ${sc.filled}/${sc.total}칸</div>`:''}<div class="fh"><span class="pf ${f.yt?'yt':'ig'}">${f.yt?'유튜브':'인스타'}</span> <b>${nm}</b>${on?'<span class="ck">✓</span>':''}</div>
    <div class="fit">${(f.fit||[]).slice(0,4).map(c => `<span>${c}</span>`).join('')}</div>
    
    <div class="note">${f.yt?'📌 제목 후킹':'🎣 첫 후킹'}</div>${first}
    <span class="more" onclick="event.stopPropagation();OPENF['${k}']=!OPENF['${k}'];render()">${OPENF[k]?'▲ 접기':'▼ 구조·스토리라인 보기'}</span>${st}
    ${BUSY[key()+k]?'<div class="busy">⏳ 만드는 중…</div>':(made()[k]?'<div class="done">✔ 만들어짐</div>':'')}</div>`;
}
function page2(){
  const x = job(); const F = window.FAMS || [];
  const recIds = new Set((x.styles||[]).map(s => String(s.family)));
  const auto = `<div class="fcard auto ${picks2().has('auto')?'on':''}" onclick="tpick('auto')"><div class="recb ai">⭐ 추천 · 자유 창작</div><div class="fh"><span class="pf ai">AI 자동</span> <b>이 재료에 맞게 자유롭게</b>${picks2().has('auto')?'<span class="ck">✓</span>':''}</div>
    <div class="note">스타일은 참고만 — 우리 S급 히트 대본·승인 부품 말맛으로 창의적으로</div>${BUSY[key()+'auto']?'<div class="busy">⏳ 만드는 중…</div>':(made()['auto']?'<div class="done">✔ 만들어짐</div>':'')}</div>`;
  const rec = F.filter(f => recIds.has(String(f.id))), rest = F.filter(f => !recIds.has(String(f.id)));
  const n = picks2().size, busy = Object.keys(BUSY).some(k => k.startsWith(key()));
  const tabs = Object.keys(made()).map(k => `<button class="btn ${VIEW[key()]===k?'on':''}" onclick="VIEW['${key()}']='${k}';render()">${tabName(k)} <span class="note">${made()[k].secs||''}초</span></button>`).join(' ');
  const bd = made()[VIEW[key()]];
  let body = '';
  if (bd){
    const ek = key()+VIEW[key()]; const lines = bd.slots.map((sl, i) => (EDIT[ek] && EDIT[ek][i] != null) ? EDIT[ek][i] : sl.line);
    const mine = new Set(Object.values(asg()).flatMap(s => [...s]));
    const cells = bd.slots.map((sl, i) => { const hs = (sl.ids||[]).some(id => mine.has(id)); const ck = (bd.check||[])[i] || {};
      const added = (bd.extra||[]).includes(String(sl.slot||'').split('_')[0].toLowerCase()) || sl.added;
      const fixedTxt = sl.line_before ? `<div class="meta">✎ ${sl.fixed_why&&!sl.fixed_why.includes('사실')&&(made()[VIEW[key()]]||{}).mode==='insert'?'이어지게 고침':'검수'}: "${sl.line_before}"${sl.fixed_why?' — '+sl.fixed_why:''}</div>` : '';
      return `<div class="row ${sl.weak?'weak':''} ${hs?'hasstar':''} ${added?'added':''} ${ck.short?'short':''}">
        <div class="rl"><div class="rn">${i+1}</div><div><b>${ko(sl.slot)}${hs?' 🎯':''}</b><div class="rneed">${sl.need||''}</div>
          ${added?'<div class="addb">＋ 끼워 넣은 칸</div>':''}${sl.cta_mark?'<div class="addb" style="background:#ff6fb1">📢 CTA 줄</div>':''}
          <div class="rsec ${ck.short?'bad':''}">문장 ${ck.need||0}초 · 장면 ${ck.have||0}초</div></div></div>
        <div class="rm"><div class="line" contenteditable="true" data-ph="${ko(sl.slot)} — 여기에 쓰세요" oninput="(EDIT['${ek}']=EDIT['${ek}']||{})[${i}]=this.innerText">${lines[i]}</div>
          ${sl.weak?`<div class="why">⚠ ${sl.weak}</div>`:''}${fixedTxt}${(added&&sl.why_scene)?`<div class="meta">🎬 장면 고른 이유: ${sl.why_scene}</div>`:''}
          ${(i===0&&(bd.extra_missing||[]).length)?`<div class="why">⚠ 끼워 넣기에서 빠진 칸: ${bd.extra_missing.map(ko).join(', ')}</div>`:''}
          ${rowActs(i, bd.slots.length, sl)}</div>
        <div class="rs"><div class="cth">${cellCards(ek, i, sl, ck)}</div>${candBox(ek, i, sl, bd)}</div></div>`; }).join('');
    body = `<div class="note" style="margin:6px 0">${bd.first_line_style||''} · 🎯 = 1단계에서 담은 장면이 들어간 칸 · 문장은 바로 고칠 수 있어요 · 한 줄이 곧 대본 한 줄</div>
      <div class="rows">${cells}</div>${xpick(ek, bd)}
      <div style="text-align:right;margin-top:10px"><button class="btn main">이 대본으로 확정 → 3단계</button></div>`;
  }
  return `<div class="pickbar"><b>대본 스타일 고르기</b> <span class="note">여러 개 골라도 돼요 · 고른 만큼 스토리보드가 따로 나와요 · 스타일 하나에 약 35초(동시에 만듦)</span>
      <span style="margin-left:auto"></span><span id="msg2" class="note"></span>
      <button class="btn" title="AI 없이 내 대본을 그대로 — 지금 보고 있는 안의 칸 구성을 따라가요" onclick="mineDraft()">✍ 내가 직접 쓰기</button>
      <button class="btn main" ${n&&!busy?'':'disabled'} onclick="makeBoards()">${busy?'⏳ 만드는 중…':'선택한 '+n+'개로 스토리보드 만들기'}</button></div>
    <div class="fsec">대본 스타일 <span class="note">같은 칸 구조는 한 카드로 합침(${F.length}개) · ⭐ 추천 = 이 재료로 칸이 잘 채워지는 스타일</span></div><div class="fgrid">${auto}${F.map(famCard).join('')}</div>
    ${tabs?`<div class="box" style="margin-top:12px"><div class="bh">만든 스토리보드 ${tabs}</div>${body}</div>`:''}`;
}
// ── 라이브 대본 줄 기능 유지(2026-10-04 사장님 "대본 기능들과 대본 직접 쓰는 것들의 기능도 다 유지"): produce.html 2단계와 같은 버튼
//    [바꾸기](라이브 부품 은행 — 시안에선 자리만) · [📢 CTA](한 줄만) · [🗑 빼기] · [▲▼](칸 이동 — 장면도 같이) · [＋](아래 빈 칸) · [✍ 내가 직접 쓰기]
function bake(ek, bd){      // 손으로 고친 문장·장면 순서를 칸에 굳힌 뒤 구조를 바꾼다(칸 번호로 붙은 기억이 엇갈리지 않게)
  bd.slots.forEach((sl, i) => { sl.ids = ordOf(ek, i, sl).slice(); if (EDIT[ek] && EDIT[ek][i] != null) sl.line = EDIT[ek][i]; });
  [ORD, CAND].forEach(M => Object.keys(M).filter(o => o.startsWith(ek+'#')).forEach(o => delete M[o])); delete EDIT[ek];
}
function tabName(k){ const F = window.FAMS || []; const [base, ...ex] = String(k).split('+');
  const nm = base==='auto'?'AI 자동':base==='mine'?'✍ 내가 직접 쓴 대본':((F.find(f=>String(f.id)===base)||{names:[base]}).names[0]);
  return nm + (ex.length ? ' <span class="addb" style="margin:0">＋' + ex.join('+').split('·')[0].split('+').map(ko).join('·') + '</span>' : ''); }
function curBd(){ const k = VIEW[key()]; return [key()+k, made()[k]]; }
function rowMove(i, d){ const [ek, bd] = curBd(); const t = i + d; if (t < 0 || t >= bd.slots.length) return; bake(ek, bd);
  [bd.slots[i], bd.slots[t]] = [bd.slots[t], bd.slots[i]]; if (bd.check) [bd.check[i], bd.check[t]] = [bd.check[t], bd.check[i]]; render(); }
function rowDel(i){ const [ek, bd] = curBd(); bake(ek, bd); bd.slots.splice(i, 1); if (bd.check) bd.check.splice(i, 1); render(); }
function rowAdd(i){ const [ek, bd] = curBd(); bake(ek, bd); bd.slots.splice(i + 1, 0, {slot: 'free', need: '새 칸', line: '', ids: [], added: true});
  if (bd.check) bd.check.splice(i + 1, 0, {have: 0, need: 0}); render(); }
function rowCta(i){ const [ek, bd] = curBd(); const on = !bd.slots[i].cta_mark; bd.slots.forEach((s, k) => s.cta_mark = on && k === i); render(); }
function rowSwap(i){ alertBox('[바꾸기]는 라이브의 부품 은행(같은 칸의 다른 승인 문장)을 그대로 씁니다 — 시안에선 자리만 보여요'); }
function rowActs(i, n, sl){
  return `<div class="racts"><button class="rb" onclick="rowSwap(${i})">바꾸기</button><button class="rb ${sl.cta_mark?'on':''}" title="이 줄이 CTA — 다시 누르면 해제" onclick="rowCta(${i})">📢 CTA</button>
    <button class="rb" title="이 줄을 대본에서 뺍니다(장면 칸도 같이)" onclick="rowDel(${i})">🗑 빼기</button>
    <span class="rmv"><button ${i===0?'disabled':''} onclick="rowMove(${i},-1)">▲</button><button ${i===n-1?'disabled':''} onclick="rowMove(${i},1)">▼</button><button title="아래에 빈 칸" onclick="rowAdd(${i})">＋</button></span></div>`; }
function mineDraft(){      // ✍ 내가 직접 쓰기 — 지금 보고 있는 안의 칸 구성을 따라간다(없으면 기본 뼈대). AI를 부르지 않는다
  const v = made()[VIEW[key()]]; const roles = v && v.slots ? v.slots.map(s => s.slot) : ['hook', 'problem', 'method', 'proof', 'cta'];
  made()['mine'] = {names: ['내가 직접 쓴 대본'], mine: true, first_line_style: '내가 직접 쓴 대본 — 칸을 채우고, 칸마다 관련 후보에서 장면을 넣으세요',
                    slots: roles.map(r => ({slot: r, need: '', line: '', ids: []})), check: roles.map(() => ({have: 0, need: 0}))};
  VIEW[key()] = 'mine'; render(); }
let ORD = {};
function ordOf(ek, i, sl){ const k = ek + '#' + i; return ORD[k] = ORD[k] || [...(sl.ids||[])]; }
function mv(ek, i, j, d){ const k = ek + '#' + i; const a = ORD[k]; const t = j + d; if (!a || t < 0 || t >= a.length) return; [a[j], a[t]] = [a[t], a[j]]; render(); }
function cellCards(ek, i, sl, ck){
  const ids = ordOf(ek, i, sl); const picked = new Set(sl.picked || []); let acc = 0; const need = Number(ck.need || 0);
  return ids.map((id, j) => { const p = job().pieces[id]; const sec = p ? Number(p.sec) : 0; const show = acc * 1.2 < need - 0.05; acc += sec;
    return `<div class="cc ${show?'':'off'}">${th(id, 60)}<div class="ccb">${picked.has(id)?'<span class="pk">고른 장면</span>':'<span class="aik">AI</span>'}
      <span class="mv" onclick="mv('${ek}',${i},${j},-1)">◀</span><span class="mv" onclick="mv('${ek}',${i},${j},1)">▶</span><span class="mv" title="이 칸에서 빼기" onclick="rmCard('${ek}',${i},${j})">✕</span></div>${show?'':'<div class="offt">안 나옴</div>'}</div>`; }).join(''); }
function upd2(){ const ek = key()+VIEW[key()]; const bd = made()[VIEW[key()]]; if (!bd || !document.getElementById('scr')) return;
  document.getElementById('scr').innerHTML = bd.slots.map((sl,i)=>'<li>'+((EDIT[ek]&&EDIT[ek][i]!=null)?EDIT[ek][i]:sl.line)+'</li>').join(''); }
// ── 칸 후보(2026-10-04 사장님 "한 장짜리 칸에도 관련 카드를 후보로"): 그 칸 장면과 같은 묶음 + AI 쓰임이 맞는 조각 중 아직 어느 칸에도 안 쓰인 것 — 흑백으로 접어 두고, 누르면 그 칸 뒤에 들어간다
const SLOT_TAG = {hook:'훅감',title:'훅감',bait:'훅감',pain:'비포',problem:'비포',limit:'비포',mistake:'비포',regret:'비포',result:'애프터',land:'애프터',twist:'반전',cases:'반전',proof:'반응',react:'반응',witness:'반응',fame:'반응'};
let CAND = {};
function usedAll(ek, bd){ const s = new Set(); bd.slots.forEach((sl, i) => ordOf(ek, i, sl).forEach(id => s.add(id))); return s; }
function candOf(ek, i, sl, bd){
  const x = job(); const used = usedAll(ek, bd); const mine = new Set(ordOf(ek, i, sl)); const a = [];
  x.groups.filter(g => g.ids.some(id => mine.has(id))).forEach(g => g.ids.forEach(id => { if (!used.has(id) && !a.includes(id)) a.push(id); }));
  const tag = SLOT_TAG[String(sl.slot||'').split('_')[0].toLowerCase()];
  if (tag) Object.keys(x.pieces).forEach(id => { if (!used.has(id) && !a.includes(id) && (x.tag_of[id]||[]).includes(tag)) a.push(id); });
  return a.slice(0, 12);
}
function candBox(ek, i, sl, bd){ const cs = candOf(ek, i, sl, bd); if (!cs.length) return ''; const k = ek+'#'+i, open = CAND[k];
  return `<div class="cand"><span class="more" onclick="CAND['${k}']=!${!!open};render()">${open?'▲ 후보 접기':'＋ 관련 후보 '+cs.length+'개 보기'}</span>${open?`<div class="cth">${cs.map(id => `<div class="cc cand1" onclick="addCand('${ek}',${i},'${id}')" title="누르면 이 칸 뒤에 넣어요">${th(id, 52)}<div class="ccb"><span class="ck2">＋ 넣기</span></div></div>`).join('')}</div>`:''}</div>`; }
function addCand(ek, i, id){ const bd = made()[VIEW[key()]]; ordOf(ek, i, bd.slots[i]).push(id); render(); }
function rmCard(ek, i, j){ ORD[ek+'#'+i].splice(j, 1); render(); }
// ── 칸 넣어 다시 쓰기(2026-10-04 사장님 "고조 같은 칸을 고르면 장면과 대본을 추가해서 다시"): 고른 칸을 그 스타일 구조에 끼워 3.6이 장면을 찾고 대본을 처음부터 다시 쓴다
const EXTRA = [['escalation','📈 고조','효능을 한 단계 더 세게'],['twist','🔄 반전','예상 밖 쓰임·충격'],['proof','👥 반응·증거','사람 반응·감탄'],['pain','😩 불편','쓰기 전 답답함'],
  ['how','🔧 사용법','쓰는 과정'],['reveal','💡 정체 공개','제품 첫 등장'],['bait','🪤 미끼','궁금증 한 줄'],['result','🏁 결과','완성·효과 장면']];
let XTRA = {};
function xset(ek){ return XTRA[ek] = XTRA[ek] || new Set(); }
function txtra(ek, r){ const s = xset(ek); s.has(r) ? s.delete(r) : s.add(r); render(); }
function xpick(ek, bd){
  const have = new Set(bd.slots.map(s => String(s.slot||'').split('_')[0].toLowerCase())); const opts = EXTRA.filter(([r]) => !have.has(r));
  if (!opts.length) return ''; const n = xset(ek).size, busy = BUSY[ek];
  return `<div class="xpick"><b>＋ 대본을 더 탄탄하게 — 넣고 싶은 칸을 고르세요</b> <span class="note">지금 대본은 그대로 두고 고른 칸만 끼워요 — 우리 히트 스타일 접속어로 앞 칸에 이어 쓰고, 안 쓴 장면 중 그 문장을 보여 주는 장면을 골라요(약 20초)</span>
    <div class="xopts">${opts.map(([r, nm, d]) => `<span class="xo ${xset(ek).has(r)?'on':''}" onclick="txtra('${ek}','${r}')">${nm} <small>${d}</small></span>`).join('')}</div>
    <button class="btn main" ${n&&!busy?'':'disabled'} onclick="rewrite()">${busy?'⏳ 끼워 넣는 중…':(n?'고른 '+n+'칸 끼워 넣기':'칸을 고르면 끼워 넣어요')}</button></div>`; }
async function rewrite(){
  // 끼워 넣기(2026-10-04 사장님): 대본을 처음부터 다시 쓰지 않는다 — 지금 스토리보드(손으로 고친 문장·장면 순서 포함)를 넘기고 고른 칸만 끼운다
  const k = VIEW[key()], ek = key()+k, bd = made()[k]; if (!bd) return;
  const cur = Object.assign({}, bd, {slots: bd.slots.map((sl, i) => Object.assign({}, sl, {line: (EDIT[ek] && EDIT[ek][i] != null) ? EDIT[ek][i] : sl.line, ids: ordOf(ek, i, sl)}))});
  BUSY[ek] = BUSY[key()+k] = true; render(); const t0 = Date.now();
  try {
    const r = await fetch('/insert', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({jid: key(), board: cur, extra: [...xset(ek)]})});
    const d = await r.json();
    // 원래 탭은 그대로 두고 새 탭으로(2026-10-04 사장님 "추가로 만들어도 미리 만든 탭은 없어지지 않게")
    if (d.slots){ const base = String(k).split('+')[0]; let nk = base + '+' + (d.extra||[]).join('+'); let c = 2; while (made()[nk]) nk = base + '+' + (d.extra||[]).join('+') + '·' + (c++);
      made()[nk] = Object.assign(d, {secs: Math.round((Date.now()-t0)/1000), from: k}); XTRA[ek] = new Set(); VIEW[key()] = nk; }
    else { console.log('[sb] 끼워 넣기 실패', d); alertBox('끼워 넣기 실패 — 다시 눌러 주세요'); }
  } catch(e){ console.log('[sb] 요청 실패', e); alertBox('끼워 넣기 실패 — 시험 서버(127.0.0.1:8790)가 켜져 있어야 해요'); }
  delete BUSY[ek]; delete BUSY[key()+k]; render();
}
