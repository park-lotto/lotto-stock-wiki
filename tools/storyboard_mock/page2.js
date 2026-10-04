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
function famCard(f){
  const x = job(); const k = String(f.id); const on = picks2().has(k); const sc = (x.styles||[]).find(s => String(s.family) === k);
  const nm = f.names.length > 1 ? f.names[0] + ` <span class="note">외 ${f.names.length-1}</span>` : f.names[0];
  const first = (f.first||[]).slice(0, 2).map(t => `<div class="fq">“${hl(t)}”</div>`).join('');
  const st = OPENF[k] ? `<div class="fstruct">${f.roles.map((r, i) => `<div><b>${i+1}. ${ko(r)}</b> ${(f.chain[i]||'').slice(0,60)}</div>`).join('')}${f.names.length>1?`<div class="note">같은 구조 첫 줄 틀: ${f.names.join(' · ')}</div>`:''}</div>` : '';
  return `<div class="fcard ${on?'on':''}" onclick="tpick('${k}')"><div class="fh"><span class="pf ${f.yt?'yt':'ig'}">${f.yt?'유튜브':'인스타'}</span> <b>${nm}</b>${on?'<span class="ck">✓</span>':''}</div>
    <div class="fit">${(f.fit||[]).slice(0,4).map(c => `<span>${c}</span>`).join('')}</div>
    ${sc ? `<div class="rec">재료 맞음 <div class="bar"><i style="width:${100*sc.filled/Math.max(1,sc.total)}%"></i></div> ${sc.filled}/${sc.total}</div>` : ''}
    <div class="note">${f.yt?'📌 제목 후킹':'🎣 첫 후킹'}</div>${first}
    <span class="more" onclick="event.stopPropagation();OPENF['${k}']=!OPENF['${k}'];render()">${OPENF[k]?'▲ 접기':'▼ 구조·스토리라인 보기'}</span>${st}
    ${BUSY[key()+k]?'<div class="busy">⏳ 만드는 중…</div>':(made()[k]?'<div class="done">✔ 만들어짐</div>':'')}</div>`;
}
function page2(){
  const x = job(); const F = window.FAMS || [];
  const recIds = new Set((x.styles||[]).map(s => String(s.family)));
  const auto = `<div class="fcard auto ${picks2().has('auto')?'on':''}" onclick="tpick('auto')"><div class="fh"><span class="pf ai">AI 자동</span> <b>이 재료에 맞게 자유롭게</b>${picks2().has('auto')?'<span class="ck">✓</span>':''}</div>
    <div class="note">스타일은 참고만 — 우리 S급 히트 대본·승인 부품 말맛으로 창의적으로</div>${BUSY[key()+'auto']?'<div class="busy">⏳ 만드는 중…</div>':(made()['auto']?'<div class="done">✔ 만들어짐</div>':'')}</div>`;
  const rec = F.filter(f => recIds.has(String(f.id))), rest = F.filter(f => !recIds.has(String(f.id)));
  const n = picks2().size, busy = Object.keys(BUSY).some(k => k.startsWith(key()));
  const tabs = Object.keys(made()).map(k => `<button class="btn ${VIEW[key()]===k?'on':''}" onclick="VIEW['${key()}']='${k}';render()">${k==='auto'?'AI 자동':((F.find(f=>String(f.id)===k)||{names:[k]}).names[0])} <span class="note">${made()[k].secs||''}초</span></button>`).join(' ');
  const bd = made()[VIEW[key()]];
  let body = '';
  if (bd){
    const ek = key()+VIEW[key()]; const lines = bd.slots.map((sl, i) => (EDIT[ek] && EDIT[ek][i] != null) ? EDIT[ek][i] : sl.line);
    const mine = new Set(Object.values(asg()).flatMap(s => [...s]));
    const cells = bd.slots.map((sl, i) => { const hs = (sl.ids||[]).some(id => mine.has(id)); const ck = bd.check[i] || {};
      return `<div class="cell ${sl.weak?'weak':''} ${hs?'hasstar':''}"><div class="ch"><b>${i+1}. ${ko(sl.slot)}${hs?' 🎯':''}</b><span>${sl.need||''}</span></div>
        <div class="cth">${(sl.ids||[]).map(id => th(id, 60)).join('')}</div>
        <div class="line" contenteditable="true" oninput="(EDIT['${ek}']=EDIT['${ek}']||{})[${i}]=this.innerText;upd2()">${lines[i]}</div>
        ${sl.weak?`<div class="why">⚠ ${sl.weak}</div>`:''}${sl.line_before?`<div class="meta">✎ 검수: "${sl.line_before}" → 제품 사실 빼고 고침</div>`:''}
        <div class="meta">장면 ${ck.have}초 · 문장 ${ck.need}초</div></div>`; }).join('');
    body = `<div class="sb"><div><div class="note" style="margin:6px 0">${bd.first_line_style||''} · 🎯 = 1단계에서 담은 장면이 들어간 칸 · 문장은 바로 고칠 수 있어요</div><div class="cells">${cells}</div></div>
      <div class="script"><b>📜 대본</b><ol id="scr">${lines.map(l=>'<li>'+l+'</li>').join('')}</ol><button class="btn main" style="width:100%">이 대본으로 확정 → 3단계</button></div></div>`;
  }
  return `<div class="pickbar"><b>대본 스타일 고르기</b> <span class="note">여러 개 골라도 돼요 · 고른 만큼 스토리보드가 따로 나와요 · 스타일 하나에 약 35초(동시에 만듦)</span>
      <span style="margin-left:auto"></span><span id="msg2" class="note"></span>
      <button class="btn main" ${n&&!busy?'':'disabled'} onclick="makeBoards()">${busy?'⏳ 만드는 중…':'선택한 '+n+'개로 스토리보드 만들기'}</button></div>
    <div class="fsec">✨ 추천 — 이 재료에 맞는 스타일</div><div class="fgrid">${auto}${rec.map(famCard).join('')}</div>
    <div class="fsec">전체 스타일 <span class="note">같은 칸 구조는 한 카드로 합침(${F.length}개)</span></div><div class="fgrid">${rest.map(famCard).join('')}</div>
    ${tabs?`<div class="box" style="margin-top:12px"><div class="bh">만든 스토리보드 ${tabs}</div>${body}</div>`:''}`;
}
function upd2(){ const ek = key()+VIEW[key()]; const bd = made()[VIEW[key()]]; if (!bd) return;
  document.getElementById('scr').innerHTML = bd.slots.map((sl,i)=>'<li>'+((EDIT[ek]&&EDIT[ek][i]!=null)?EDIT[ek][i]:sl.line)+'</li>').join(''); }
