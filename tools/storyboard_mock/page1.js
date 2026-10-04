// ── 1단계(2026-10-04 사장님): ① 담은 영상 = 출처·제목 카드, 펼치면 영상별 분석(장면 구성·스토리 줄)
//    ② 역할 상자(우리 스타일 칸에서 뽑은 10개) — 상자를 켜고 카드를 누르면 그 상자에 담김. 담긴 카드의 묶음은 대본에 반영 표시
const ROLES = [["훅","🎣","#c85cff","title·hook"],["미끼·궁금증","🪤","#a17bff","bait·notice·situation"],["문제·불편","😩","#ff8a3d","limit·pain·problem·mistake"],
  ["정체 공개","💡","#ffc23d","reveal·origin·what"],["사용법","🔧","#3a9bff","solve·method·steps·how"],["효과·소구점","✨","#2fbf82","escalation·more·benefit·power"],
  ["반전·의외","🔄","#ff4f7b","twist·cases"],["반응·증거","👥","#24c6d6","fame·proof·witness·react"],["결과","🏁","#7ed957","result·land"],["CTA·가격","💬","#ff6fb1","cta·price·deal"]];
const SUG = {"훅감":"훅","비포":"문제·불편","애프터":"결과","반전":"반전·의외","반응":"반응·증거"};
const PLAT = [["xiaohongshu","샤오홍슈"],["douyin","도우인"],["instagram","인스타"],["tiktok","틱톡"],["youtube","유튜브"],["pinterest","핀터레스트"],["naver","네이버"],["threads","쓰레드"]];
let ROLE = {}, ACTIVE = null, OPENV = {};
function plat(id){ const s = String(id||'').toLowerCase(); const m = PLAT.find(([k]) => s.includes(k)); return m ? m[1] : '직접 올림'; }
function asg(){ return ROLE[key()] = ROLE[key()] || {}; }          // 역할 → Set(조각)
function rolesOf(id){ return Object.entries(asg()).filter(([r, s]) => s.has(id)).map(([r]) => r); }
function setActive(r){ ACTIVE = (ACTIVE === r ? null : r); render(); }
function cardClick(id){ if (!ACTIVE){ return; } const s = asg()[ACTIVE] = asg()[ACTIVE] || new Set(); s.has(id) ? s.delete(id) : s.add(id); render(); }
function roleColor(r){ return (ROLES.find(x => x[0] === r) || [,,'#888'])[2]; }
function card1(id, w){ const p = job().pieces[id]; if (!p) return '';
  const mine = rolesOf(id); const sug = [...new Set((job().tag_of[id]||[]).map(t => SUG[t]).filter(Boolean))];
  return `<div class="pc ${mine.length?'picked':''} ${ACTIVE?'armed':''}" onclick="cardClick('${id}')" title="${(p.desc||'').replace(/"/g,'&quot;')}">
    <div class="th" style="width:${w||76}px;${mine.length?'border-color:'+roleColor(mine[0]):''}"><img src="data:image/jpeg;base64,${p.th}"><span class="sec">${p.sec}초</span>
      <span class="tg">${mine.map(r => `<span style="background:${roleColor(r)}">${(ROLES.find(x=>x[0]===r)||[])[1]} ${r}</span>`).join('')}${!mine.length && sug.length ? `<span class="aisug">AI: ${sug.join('·')}</span>` : ''}</span></div></div>`; }
function vidKey(id){ const m = String(id).match(/^(.*)-\d+$/); return m ? m[1] : id; }
function page1(){
  const x = job();
  const byVid = {}; Object.keys(x.pieces).forEach(id => { (byVid[x.pieces[id].vid] = byVid[x.pieces[id].vid] || []).push(id); });
  const gOf = {}; x.groups.forEach((g, i) => g.ids.forEach(id => gOf[id] = i));
  const strip = x.vids.map((v, i) => { const ids = byVid[v.vid] || []; const open = OPENV[key()+i];
    return `<div class="vcard ${open?'open':''}" onclick="OPENV['${key()}${i}']=!${!!open};render()"><div class="th" style="width:104px"><img src="data:image/jpeg;base64,${v.th}"></div>
      <div class="vcap"><span class="plat">${plat(ids[0])}</span> <b>${v.prod||'영상 '+(i+1)}</b></div><div class="note">${open?'▲ 접기':'▼ 분석 보기'}</div></div>`; }).join('');
  const opened = x.vids.map((v, i) => [v, i]).filter(([v, i]) => OPENV[key()+i]);
  const detail = opened.map(([v, i]) => { const ids = byVid[v.vid] || []; const b = v.brief || {};
    const comp = {}; ids.forEach(id => { const g = x.groups[gOf[id]]; if (g) comp[g.name] = (comp[g.name]||0) + 1; });
    const story = (v.story || []).map(L => `<div class="sline"><div><span class="kind">${L.kind||''}</span> <b>${L.text}</b> <span class="note">${L.point||''}</span></div>
      <div class="sth">${(L.cuts||[]).slice(0,4).map(c => card1(c, 52)).join('')}</div></div>`).join('') || '<div class="note">스토리 없음</div>';
    return `<div class="acard"><div class="ah"><span class="tag">영상 ${i+1}</span> <span class="plat">${plat(ids[0])}</span> <b>${v.prod||''}</b>
        <span class="chip2">🗣 말 있음 ${v.talk||0}자</span><span class="chip2">⏱ ${v.dur||'?'}초</span><span class="chip2">조각 ${ids.length}</span></div>
      <div class="kv"><b>핵심</b> ${b.core||''}</div><div class="kv"><b>흐름</b> ${b.flow||''}</div>
      <div class="kv"><b>장면 구성</b> ${Object.entries(comp).sort((a,b)=>b[1]-a[1]).map(([n,c]) => `<span class="chip2">${n} ${c}</span>`).join('')}</div>
      <div class="kv" style="margin-top:6px"><b>📖 스토리 줄 — 대본에 그대로 들어갈 문장 → 그 장면</b> <span class="note">(${ACTIVE?'켜진 상자: '+ACTIVE+' — 장면을 누르면 담겨요':'위 역할 상자를 켜고 장면을 누르면 담겨요'})</span></div>${story}</div>`; }).join('');
  const boxes = ROLES.map(([r, ic, c, slots]) => { const s = asg()[r] || new Set();
    return `<div class="rbox ${ACTIVE===r?'on':''}" style="--c:${c}" onclick="setActive('${r}')"><div class="rh">${ic} ${r} <b>${s.size||''}</b></div><div class="rs">${slots}</div>
      <div class="rth">${[...s].slice(0,5).map(id => { const p = x.pieces[id]; return p ? `<img src="data:image/jpeg;base64,${p.th}">` : ''; }).join('')}</div></div>`; }).join('');
  const grps = x.groups.map((g, i) => { const all = SHOWALL[key()+i]; const ids = all ? g.ids : g.ids.slice(0, 7);
    const hit = g.ids.filter(id => rolesOf(id).length).length;
    return `<div class="grp ${hit?'star':''}"><div class="gh"><b>${g.name}</b> <span>${g.desc||''} · ${g.ids.length}개</span>${hit?` <span class="hitb">🎯 ${hit}장 담김 — 이 묶음 대본에 반영</span>`:''}</div>
      <div class="gth">${ids.map(id => card1(id)).join('')}</div>${g.ids.length > 7 ? `<span class="more" onclick="SHOWALL['${key()}${i}']=!${!!all};render()">${all?'접기':'나머지 '+(g.ids.length-7)+'개 펼치기'}</span>`:''}</div>`; }).join('');
  return `<div class="box"><div class="bh">① 담은 영상 <small>${x.vids.length}개 · 카드를 누르면 영상별 분석이 펼쳐져요</small></div><div class="strip">${strip}</div>${detail?`<div class="adetail">${detail}</div>`:''}</div>
  <div class="rbar"><div class="bh">🎯 꼭 쓰고 싶은 장면 — 상자를 켜고 카드를 누르세요 <small>${ACTIVE?'지금 켜진 상자: <b>'+ACTIVE+'</b> (다시 누르면 꺼짐)':'다 채울 필요 없어요 — 이 소스를 고른 이유만'}</small></div><div class="rboxes">${boxes}</div></div>
  <div class="box"><div class="bh">② 장면 목록 <small>조각 ${Object.keys(x.pieces).length}개를 ${x.groups.length}묶음으로 — 빠진 조각 없음 · 카드 위 'AI:' = AI가 본 쓰임(참고)</small></div><div class="grps">${grps}</div></div>
  <div class="box"><div class="missing"><b>③ 이 재료에 없는 장면</b><ul>${x.missing.map(m=>'<li>'+m+'</li>').join('')}</ul><button class="btn">＋ 영상 더 담기</button> <span class="note">새 영상 조각만 분석해 위 묶음에 더해요(전체 다시 안 함)</span></div></div>
  <div style="text-align:right"><button class="btn main" onclick="go(2)">2단계 스토리보드로 →</button></div>`;
}
