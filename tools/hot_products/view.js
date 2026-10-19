
const D = __DATA__;
const SITES = [["all","전체"],["naver","네이버"],["1688","1688"],["temu","테무"],["amazon","아마존"]];
const PCATS = [["all","전체"],["홈템","🏠 홈템"],["뷰티","💄 뷰티"],["장비템","🔧 장비템"],["차량템","🚗 차량템"],["반려템","🐶 반려템"],["육아템","🧸 육아템"],["디지털템","📱 디지털템"]];
const SORTS = [["total","종합 점수"],["speed","지금 팔리는 속도"],["demand","검색 수요"],["wow","신박함"],["opp","쇼츠 기회"]];
const SN = {naver:"네이버","1688":"1688",temu:"테무",amazon:"아마존"};
const st = {site:"all", pcat:"all", sort:"total"};
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt = n => n == null ? "–" : n >= 10000 ? (n/10000).toFixed(n>=100000?0:1)+"만" : n.toLocaleString();
function render(){
  const inSite = D.filter(r => st.site === "all" || r.site === st.site);
  const ok = inSite.filter(r => r.cat !== "제외");
  const cnt = c => c === "all" ? ok.length : ok.filter(r => r.cat === c).length;
  $("sites").innerHTML = SITES.map(([k,l]) => `<button class="site ${k===st.site?"on":""}" data-site="${k}">${l}<small>${k==="all"?"":D.filter(r=>r.site===k&&r.cat!=="제외").length}</small></button>`).join("");
  $("cats").innerHTML = PCATS.filter(([c]) => c === "all" || cnt(c) > 0).map(([c,l]) => `<button class="cat ${st.pcat===c?"on":""}" data-pcat="${c}">${l}<em>${cnt(c)}</em></button>`).join("")
    + `<button class="cat ex ${st.pcat==="제외"?"on":""}" data-pcat="제외">🚫 제외<em>${inSite.length-ok.length}</em></button>`;
  $("sorts").innerHTML = SORTS.map(([k,l]) => `<button class="chip ${k===st.sort?"on":""}" data-sort="${k}">${l}</button>`).join("");
  let rows = st.pcat === "all" ? ok : inSite.filter(r => r.cat === st.pcat);
  rows = rows.slice().sort((a,b) => (b.sc[st.sort]-a.sc[st.sort]) || (b.sc.total-a.sc.total)).slice(0, 120);
  $("meta").innerHTML = `<b>${st.site==="all"?"전체 사이트":SN[st.site]}</b> · ${st.pcat==="all"?"쇼츠 가능 전체":st.pcat} · ${SORTS.find(s=>s[0]===st.sort)[1]} 순 · 상위 ${rows.length}개`;
  $("grid").innerHTML = rows.map((r,i) => `
    <div class="card ${r.cat==="제외"?"dim":""}">
      <span class="rank ${i<3&&r.cat!=="제외"?"top":""}">${r.cat==="제외"?"–":i+1}</span>
      <span class="site-tag">${SN[r.site]}</span>
      <img class="thumb" src="${esc(r.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.visibility='hidden'">
      <div class="body">
        <div class="title" title="${esc(r.title)}">${esc(r.title)}</div>
        <div class="price">${esc(r.price)}</div>
        ${r.cat==="제외"?`<span class="why">제외: ${esc(r.why||"")}</span>`:`
        <div class="score"><b>${r.sc.total}</b><span class="sbar"><i style="width:${r.sc.total}%"></i></span><span class="wow">${"★".repeat(r.wow||0)}${"☆".repeat(3-(r.wow||0))}</span></div>`}
        <div class="tags">${r.tags.map(c=>`<span class="tag ${/🔥|📈/.test(c)?"hot":""}">${esc(c)}</span>`).join("")}</div>
        ${r.kw?`<div class="dem">🔍 <b>${esc(r.kw)}</b> 월 검색 <b>${fmt(r.search)}</b>${r.trend!=null?` · 4주 추세 <b style="color:${r.trend>0?"#3ee0bf":"#ff8a73"}">${r.trend>0?"+":""}${r.trend}%</b>`:""}<br>▶ 유튜브 상위 20개 조회 합 <b>${fmt(r.yt_sum)}</b></div>`:""}
        <div class="btns">
          ${r.kw?`<a class="go" target="_blank" href="https://shoppingshorts.duckdns.org/?kwfind=${encodeURIComponent(r.kw)}">🔎 숏템파워로 찾기</a>`:""}
          ${r.url?`<a class="src" target="_blank" rel="noreferrer" href="${esc(r.url)}">원문</a>`:""}
        </div>
      </div>
    </div>`).join("") || `<p class="meta">이 조건에 맞는 상품이 없습니다.</p>`;
}
document.addEventListener("click", e => {
  const s = e.target.closest("[data-site]"); if (s) { st.site = s.dataset.site; render(); return; }
  const c = e.target.closest("[data-pcat]"); if (c) { st.pcat = c.dataset.pcat; render(); return; }
  const o = e.target.closest("[data-sort]"); if (o) { st.sort = o.dataset.sort; render(); }
});
render();
