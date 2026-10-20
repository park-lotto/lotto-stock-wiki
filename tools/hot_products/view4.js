const DATA = __DATA__;
const R = DATA.rows;
const POWER = "https://shoppingshorts.duckdns.org/?kwfind=";
// 탭 = 검증된 신호 하나씩(lecture/catalog_tx.md). 기본 정렬도 탭이 정한다.
const TABS = [
  {id:"hot", label:"🔥 지금 터지는 중", f:r=>r.n_hits>0 && r.hit_days!=null && r.hit_days<=14, sort:"hit_last",
   d:"최근 14일 안에 이 상품으로 <b>쇼츠가 실제로 터진</b> 상품. 같은 상품은 보통 1~4일 안에 다른 계정에서 또 터집니다."},
  {id:"season", label:"📅 곧 뜰 시즌템", f:r=>r.season_up!=null && r.season_up>=20, sort:"season_up",
   d:"작년 이맘때부터 8주 동안 검색이 <b>20% 이상</b> 오른 상품. 피크 2~3달 전에 만들어 두세요."},
  {id:"rising", label:"📈 검색 급상승", f:r=>(r.trend!=null && r.trend>=50) || (r.yoy!=null && r.yoy>=2), sort:"trend",
   d:"최근 4주 검색 <b>+50% 이상</b> 또는 작년 같은 때의 <b>2배 이상</b>."},
  {id:"news", label:"📰 뉴스 화제", f:r=>r.news.length>0, sort:"n_news",
   d:"품절·완판·판매 N배처럼 <b>수요가 움직인 근거</b>가 있는 기사에 나온 상품(행사·증정 기사는 뺌)."},
  {id:"kids", label:"🧒 아이·10대", f:r=>r.kids!=null && r.kids>=1.5, sort:"kids",
   d:"네이버 검색이 <b>0~18세</b>에 전체보다 1.5배 이상 몰린 상품."},
  {id:"senior", label:"👵 5060", f:r=>r.senior!=null && r.senior>=1.5, sort:"senior",
   d:"네이버 검색이 <b>50세 이상</b>에 전체보다 1.5배 이상 몰린 상품."},
  {id:"best", label:"🛒 사이트 베스트", f:r=>r.src.includes("best"), sort:"search",
   d:"네이버·1688·테무·아마존 베스트 중 <b>쇼츠로 만들 수 있는</b> 상품(식품·소모품·옷·광고 제외)."},
  {id:"fav", label:"★ 즐겨찾기", f:r=>favs.has(r.kw), sort:"search", d:"별을 누른 상품. 이 브라우저에만 저장됩니다."},
];
const COLS = [
  {id:"rk", label:"순위", always:true},
  {id:"prod", label:"상품", always:true},
  {id:"badges", label:"신호"},
  {id:"ser", label:"1년 추이"},
  {id:"search", label:"월 검색", sort:true},
  {id:"trend", label:"4주 추세", sort:true},
  {id:"yoy", label:"작년 대비", sort:true},
  {id:"season_up", label:"곧 뜰 시즌", sort:true},
  {id:"age", label:"연령 쏠림"},
  {id:"hits", label:"터진 쇼츠", sort:"hit_max"},
  {id:"comp", label:"광고 경쟁"},
  {id:"price", label:"가격"},
  {id:"act", label:"", always:true},
];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt = n => n == null ? "–" : n >= 10000 ? (n/10000).toFixed(n>=100000?0:1)+"만" : Number(n).toLocaleString();
const pct = n => n == null ? "–" : `<span class="${n>0?"pos":n<0?"neg":""}">${n>0?"+":""}${n}%</span>`;
function store(k, v){ try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch(e) { return null; } }
let favs = new Set(JSON.parse(store("hp_favs") || "[]"));
let hidden = new Set(JSON.parse(store("hp_cols") || "[]"));
const st = {tab: store("hp_tab") || "hot", sort: null, dir: -1, q: "", cat: "all"};
R.forEach(r => { r.n_news = r.news.length; });

function badges(r){
  const b = [];
  if (r.hit_days != null && r.hit_days <= 14) b.push(`<span class="bd hot">🔥 방금 터짐 ${r.hit_days}일 전</span>`);
  if (r.trend != null && r.trend >= 50) b.push(`<span class="bd up">📈 검색 +${r.trend}%</span>`);
  if (r.yoy != null && r.yoy >= 2) b.push(`<span class="bd up">🆕 작년의 ${r.yoy}배</span>`);
  if (r.season_up != null && r.season_up >= 20) b.push(`<span class="bd sea">📅 곧 시즌 +${r.season_up}%</span>`);
  if (r.kids != null && r.kids >= 1.5) b.push(`<span class="bd age">🧒 아이 ${r.kids}배</span>`);
  if (r.senior != null && r.senior >= 1.5) b.push(`<span class="bd age">👵 5060 ${r.senior}배</span>`);
  if (r.news.length) b.push(`<span class="bd news">📰 수요 뉴스</span>`);
  return b.join("");
}
function spark(s, w=110, h=30){
  if (!s || s.length < 4) return `<span style="color:var(--sub);font-size:11px">자료 없음</span>`;
  const mx = Math.max(...s, 1), step = w / (s.length - 1);
  const pts = s.map((v,i) => `${(i*step).toFixed(1)},${(h - 2 - v/mx*(h-4)).toFixed(1)}`).join(" ");
  const last4 = s.slice(-4).reduce((a,b)=>a+b,0)/4, prev = s.slice(-12,-4).reduce((a,b)=>a+b,0)/8;
  const col = last4 >= prev ? "#3ee0bf" : "#ff8a73";
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke="${col}" stroke-width="1.8" points="${pts}"/></svg>`;
}
function grade(c){ return c==="낮음" ? `<span class="grade g-good">좋음</span>` : c==="중간" ? `<span class="grade g-mid">보통</span>` : c==="높음" ? `<span class="grade g-bad">나쁨</span>` : "–"; }
function cell(id, r, i){
  switch(id){
    case "rk": return `<td class="rk ${i<3?"top":""}">${i+1}</td>`;
    case "prod": return `<td><div class="prod">${r.img?`<img src="${esc(r.img)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'ph',textContent:'📦'}))">`:`<div class="ph">📦</div>`}<div><b>${esc(r.kw)}</b><small>${esc(r.cat||"")}${r.price?" · "+esc(r.price):""}</small></div></div></td>`;
    case "badges": return `<td data-c="신호"><div class="badges">${badges(r)||`<span class="bd">–</span>`}</div></td>`;
    case "ser": return `<td data-c="1년 추이">${spark(r.ser)}</td>`;
    case "search": return `<td class="num" data-c="월 검색">${fmt(r.search)}</td>`;
    case "trend": return `<td class="num" data-c="4주 추세">${pct(r.trend)}</td>`;
    case "yoy": return `<td class="num" data-c="작년 대비">${r.yoy==null?"–":r.yoy+"배"}</td>`;
    case "season_up": return `<td class="num" data-c="곧 뜰 시즌">${pct(r.season_up)}${r.peak_ly?`<br><small style="color:var(--sub)">작년 피크 ${r.peak_ly.slice(5)}</small>`:""}</td>`;
    case "age": return `<td class="num" data-c="연령 쏠림">${r.kids==null&&r.senior==null?"–":`🧒${r.kids??"–"} · 👵${r.senior??"–"}`}</td>`;
    case "hits": return `<td class="num" data-c="터진 쇼츠">${r.n_hits?`${r.n_hits}개 · 최고 ${fmt(r.hit_max)}`:"–"}</td>`;
    case "comp": return `<td data-c="광고 경쟁">${grade(r.comp)}</td>`;
    case "price": return `<td class="num" data-c="가격">${esc(r.price||"–")}</td>`;
    case "act": return `<td style="white-space:nowrap"><button class="star ${favs.has(r.kw)?"on":""}" data-fav="${esc(r.kw)}" title="즐겨찾기">★</button> <a class="go" target="_blank" href="${POWER+encodeURIComponent(r.kw)}" onclick="event.stopPropagation()">숏템파워로 찾기</a></td>`;
  }
}
function current(){
  const t = TABS.find(x => x.id === st.tab) || TABS[0];
  let rows = R.filter(t.f);
  if (st.cat !== "all") rows = rows.filter(r => r.cat === st.cat);
  if (st.q) rows = rows.filter(r => r.kw.includes(st.q) || (r.sites||[]).some(s => (s.title||"").includes(st.q)));
  const key = st.sort || t.sort, dir = st.sort ? st.dir : -1;
  const v = r => key === "hit_last" ? (r.hit_last || "") : (r[key] ?? -1e9);
  rows.sort((a,b) => { const x = v(a), y = v(b); return (x > y ? 1 : x < y ? -1 : 0) * dir || (b.hit_max - a.hit_max); });
  return {t, rows: rows.slice(0, 200), key};
}
function render(){
  const {t, rows, key} = current();
  $("tabs").innerHTML = TABS.map(x => `<button class="tab ${x.id===st.tab?"on":""}" data-tab="${x.id}">${x.label}<em>${R.filter(x.f).length}</em></button>`).join("");
  $("tabdesc").innerHTML = t.d;
  const cats = [...new Set(R.filter(t.f).map(r => r.cat).filter(Boolean))];
  $("cats").innerHTML = cats.length > 1 ? ["all", ...cats].map(c => `<button class="chip ${st.cat===c?"on":""}" data-cat="${c}">${c==="all"?"전체":esc(c)}</button>`).join(" ") : "";
  $("asof").textContent = `${DATA.built} 기준`;
  const cols = COLS.filter(c => c.always || !hidden.has(c.id));
  $("cols").innerHTML = COLS.filter(c => !c.always).map(c => `<label><input type="checkbox" data-col="${c.id}" ${hidden.has(c.id)?"":"checked"}> ${c.label}</label>`).join("");
  $("head").innerHTML = cols.map(c => { const sk = c.sort === true ? c.id : c.sort; return `<th ${sk?`data-sort="${sk}"`:""} class="${sk&&sk===key?"sorted":""}">${c.label}${sk&&sk===key?(st.sort&&st.dir>0?" ▲":" ▼"):""}</th>`; }).join("");
  $("body").innerHTML = rows.map((r,i) => `<tr class="r" data-kw="${esc(r.kw)}">${cols.map(c => cell(c.id, r, i)).join("")}</tr>`).join("")
    || `<tr><td colspan="${cols.length}" class="empty">이 조건에 맞는 상품이 없습니다.</td></tr>`;
}
function bigChart(s){
  if (!s || s.length < 4) return `<p class="why">검색 추이 자료가 없습니다.</p>`;
  const w = 500, h = 120, mx = Math.max(...s, 1), step = w / (s.length - 1);
  const pts = s.map((v,i) => `${(i*step).toFixed(1)},${(h - 14 - v/mx*(h-24)).toFixed(1)}`).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" width="100%"><polyline fill="none" stroke="#3ee0bf" stroke-width="2" points="${pts}"/><text x="0" y="${h-2}" fill="#8b97ad" font-size="11">52주 전</text><text x="${w}" y="${h-2}" fill="#8b97ad" font-size="11" text-anchor="end">지난주</text></svg>`;
}
function openDrawer(kw){
  const r = R.find(x => x.kw === kw); if (!r) return;
  const age = (n, v) => `<div class="agebar"><span>${n}</span>${v==null?`<span style="color:var(--sub)">자료 없음</span>`:`<i style="width:${Math.min(100, v*40)}%"></i><span>${v}배</span>`}</div>`;
  $("drawer").innerHTML = `
    <div class="dh">${r.img?`<img src="${esc(r.img)}" referrerpolicy="no-referrer">`:""}<div><h2>${esc(r.kw)}</h2><small style="color:var(--sub)">${esc(r.cat||"")} ${esc(r.price||"")}</small></div><button class="x" data-close>×</button></div>
    <div class="badges" style="max-width:none;margin-bottom:10px">${badges(r)}</div>
    <a class="go" style="display:block;text-align:center;margin-bottom:12px;padding:11px" target="_blank" href="${POWER+encodeURIComponent(r.kw)}">🔎 숏템파워로 「${esc(r.kw)}」 영상 찾기</a>
    <div class="blk"><h3>핵심 숫자</h3><div class="kv">
      <div><small>월 검색(네이버)</small><b>${fmt(r.search)}</b></div><div><small>4주 추세</small><b>${pct(r.trend)}</b></div><div><small>작년 대비</small><b>${r.yoy==null?"–":r.yoy+"배"}</b></div>
      <div><small>곧 뜰 시즌(8주)</small><b>${pct(r.season_up)}</b></div><div><small>작년 피크</small><b>${esc(r.peak_ly||"–")}</b></div><div><small>광고 경쟁</small><b>${grade(r.comp)}</b></div></div></div>
    <div class="blk"><h3>1년 검색 추이 (네이버 데이터랩, 주간)</h3>${bigChart(r.ser)}</div>
    <div class="blk"><h3>연령 쏠림 (전체 대비, 1.5배↑면 그 연령 상품)</h3>${age("0~18세", r.kids)}${age("50세+", r.senior)}</div>
    <div class="blk"><h3>이 상품으로 터진 쇼츠 (레퍼런스랭킹)</h3>${r.hits.length ? r.hits.map(h => `<div class="li"><span>${esc(h.date)}</span><span>조회 <b>${fmt(h.views)}</b></span><small>${esc(h.user||h.platform||"")}</small>${h.url?`<a target="_blank" rel="noreferrer" href="${esc(h.url)}">보기</a>`:""}</div>`).join("") : `<p class="why">아직 터진 쇼츠가 없습니다 — 먼저 올릴 기회일 수 있습니다.</p>`}</div>
    ${r.news.length ? `<div class="blk"><h3>뉴스 근거</h3>${r.news.map(n => `<div class="li"><small>${esc(n.d)}</small><a target="_blank" rel="noreferrer" href="${esc(n.u)}">${esc(n.t)}</a></div>`).join("")}${r.news[0].ev?`<p class="why">근거: ${esc(r.news[0].ev)}</p>`:""}</div>` : ""}
    ${r.sites.length ? `<div class="blk"><h3>판매처 베스트 순위</h3>${r.sites.map(s => `<div class="li"><span>${esc(s.site)} ${esc(s.list||"")} <b>${s.rank??""}위</b></span>${s.url?`<a target="_blank" rel="noreferrer" href="${esc(s.url)}">원문</a>`:""}</div>`).join("")}</div>` : ""}`;
  $("drawer").classList.add("open"); $("dim").classList.add("open");
}
function closeDrawer(){ $("drawer").classList.remove("open"); $("dim").classList.remove("open"); }
function csv(){
  const {rows} = current();
  const head = ["키워드","분류","월검색","4주추세%","작년대비배","곧뜰시즌%","작년피크","아이쏠림","5060쏠림","터진쇼츠수","터진최고조회","광고경쟁","가격"];
  const lines = [head].concat(rows.map(r => [r.kw,r.cat,r.search,r.trend,r.yoy,r.season_up,r.peak_ly,r.kids,r.senior,r.n_hits,r.hit_max,r.comp,r.price]))
    .map(a => a.map(v => `"${String(v ?? "").replace(/"/g,'""')}"`).join(","));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\n")], {type:"text/csv"}));
  a.download = `인기상품_${st.tab}_${DATA.built.slice(0,10)}.csv`; a.click();
}
document.addEventListener("click", e => {
  const g = e.target.closest.bind(e.target);
  if (g("[data-close]") || e.target.id === "dim") return closeDrawer();
  const fav = g("[data-fav]"); if (fav) { e.stopPropagation(); const k = fav.dataset.fav; favs.has(k) ? favs.delete(k) : favs.add(k); store("hp_favs", JSON.stringify([...favs])); return render(); }
  const tb = g("[data-tab]"); if (tb) { st.tab = tb.dataset.tab; st.sort = null; st.cat = "all"; store("hp_tab", st.tab); return render(); }
  const ct = g("[data-cat]"); if (ct) { st.cat = ct.dataset.cat; return render(); }
  const th = g("th[data-sort]"); if (th) { const k = th.dataset.sort; st.dir = st.sort === k ? -st.dir : -1; st.sort = k; return render(); }
  if (e.target.id === "colbtn") return $("cols").classList.toggle("open");
  if (e.target.id === "csv") return csv();
  const tr = g("tr.r"); if (tr) openDrawer(tr.dataset.kw);
});
document.addEventListener("change", e => { const c = e.target.dataset.col; if (!c) return; e.target.checked ? hidden.delete(c) : hidden.add(c); store("hp_cols", JSON.stringify([...hidden])); render(); });
$("q").addEventListener("input", e => { st.q = e.target.value.trim(); render(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });
if (!TABS.find(x => x.id === st.tab)) st.tab = "hot";
render();
