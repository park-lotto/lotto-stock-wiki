/* 감정짤 밈팩(관제 143, 2026-10-06) — 밈팩 페이지·2단계 스토리보드·3단계 칸이 함께 쓰는 한 벌.
   시안 tools/storyboard_mock/pages_tpl.html 의 memeDrawer/MFAV 를 옮김.
   ★서버가 정본: 팩 목록 /api/meme/pack · 우선 짤 /api/meme/prefs(회원별) · 짤 길이·자리는 서버(storyboard.meme_head/meme_slots).
   ★이 파일이 그리는 자리는 서랍(#memeDrawer) 하나 — 그리는 함수는 renderDrawer 하나뿐이다.
   스위치 meme_enabled 가 꺼진 계정은 /api/meme/pack 이 403 → 아무것도 안 그린다(화면 불변). */
(function () {
  if (window.MemePack) return;
  var S = { data: null, loading: null, err: "", drawer: null, tab: "" };
  function e(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function clip(id) { id = Number(id); return ((S.data && S.data.clips) || []).find(function (c) { return c.id === id; }) || null; }
  function prefs() { return (S.data && S.data.prefs) || []; }
  // 감정 안 우선순위(1부터) — 없으면 0
  function rankOf(id) { id = Number(id); var p = prefs().find(function (x) { return x.asset_id === id; }); return p ? p.rank : 0; }
  function favIds(emo) {
    return prefs().filter(function (p) { return !emo || p.emotion === emo; })
      .sort(function (a, b) { return a.emotion === b.emotion ? a.rank - b.rank : (a.emotion > b.emotion ? 1 : -1); })
      .map(function (p) { return p.asset_id; });
  }
  function load(force) {
    if (S.data && !force) return Promise.resolve(S.data);
    if (S.loading && !force) return S.loading;
    S.loading = fetch("/api/meme/pack").then(function (r) {
      return r.json().catch(function () { return null; }).then(function (d) {
        if (!r.ok || !d || !d.ok) { S.err = (d && d.error) || ("밈팩을 못 읽었어요(" + r.status + ")"); S.data = null; return null; }
        S.err = ""; S.data = d; return d;
      });
    }).catch(function (x) { console.warn("[meme] 밈팩 읽기 실패", x); S.err = "밈팩을 못 읽었어요 — 잠시 뒤 다시"; return null; })
      .then(function (d) { S.loading = null; return d; });
    return S.loading;
  }
  // ☆ 토글 — 누른 순서가 우선순위(그 감정의 맨 뒤에 붙는다). 저장은 서버(회원별)
  function toggleFav(id) {
    id = Number(id); var c = clip(id); if (!c || !S.data) return Promise.resolve(false);
    var cur = prefs().slice();
    var has = cur.some(function (p) { return p.asset_id === id; });
    if (has) cur = cur.filter(function (p) { return p.asset_id !== id; });
    else cur.push({ asset_id: id, emotion: c.emotion, rank: 1 + Math.max.apply(null, [0].concat(cur.filter(function (p) { return p.emotion === c.emotion; }).map(function (p) { return p.rank; }))) });
    // 감정별 순서를 1부터 다시 매겨 보낸다
    var by = {};
    cur.sort(function (a, b) { return a.rank - b.rank; }).forEach(function (p) { (by[p.emotion] = by[p.emotion] || []).push(p); });
    var out = [];
    Object.keys(by).forEach(function (k) { by[k].forEach(function (p, i) { out.push({ asset_id: p.asset_id, emotion: k, rank: i + 1 }); }); });
    S.data.prefs = out; changed();
    return fetch("/api/meme/prefs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prefs: out }) })
      .then(function (r) { return r.json().then(function (d) { if (r.ok && d && d.ok) { S.data.prefs = d.prefs; changed(); return true; } throw new Error((d && d.error) || r.status); }); })
      .catch(function (x) { console.warn("[meme] 우선 짤 저장 실패", x); alert("우선 짤 저장 실패 — 다시 눌러 주세요"); return load(true).then(function () { changed(); return false; }); });
  }
  var listeners = [];
  function onChange(fn) { listeners.push(fn); }
  function changed() { renderDrawer(); listeners.forEach(function (fn) { try { fn(); } catch (x) { console.warn("[meme] 화면 갱신 실패", x); } }); }
  function poster(id) { return "/api/meme/" + Number(id) + "/poster"; }
  function media(id) { return "/api/meme/" + Number(id) + "/media"; }
  // 짤 표지 + 마우스 올리면 재생(preload none — 1,283개를 한꺼번에 받지 않는다). 표지는 video poster 라 img lazy 아님
  function video(id, cls) {
    return '<video class="' + (cls || "") + '" src="' + media(id) + '" poster="' + poster(id) + '" muted loop playsinline preload="none"' +
      ' onmouseenter="this.play().catch(function(){})" onmouseleave="this.pause()"></video>';
  }
  function star(id, emo) {
    var r = rankOf(id);
    return '<span class="mp-st" title="이 감정의 우선 짤로(먼저 누른 순서대로 자동 배치에 먼저 쓰여요)" onclick="event.stopPropagation();MemePack.toggleFav(' + Number(id) + ')">' + (r ? "⭐" + r : "☆") + "</span>";
  }
  // 카드 하나 — 밈팩 페이지·서랍이 같이 쓴다
  function card(c, opts) {
    opts = opts || {};
    return '<div class="mp-card' + (opts.cur ? " cur" : "") + '" title="' + e(c.title || "") + '"' + (opts.onclick ? ' onclick="' + opts.onclick + '"' : "") + ">" +
      video(c.id) + star(c.id, c.emotion) + '<span class="mp-em">' + e(c.emotion) + " · " + e(c.dur) + "초</span></div>";
  }
  function tabs(cur, onTab) {
    var d = S.data || { emotions: [] };
    var nf = prefs().length;
    return '<div class="mp-tabs"><span class="' + (cur === "⭐" ? "on" : "") + '" onclick="' + onTab + "('⭐')\">⭐ 우선 짤 " + nf + "</span>" +
      d.emotions.map(function (x) {
        var k = prefs().filter(function (p) { return p.emotion === x.name; }).length;
        return '<span class="' + (cur === x.name ? "on" : "") + '" onclick="' + onTab + "('" + e(x.name) + "')\">" + e(x.name) + " " + x.count + (k ? " · ⭐" + k : "") + "</span>";
      }).join("") + "</div>";
  }
  function listOf(tab) {
    if (!S.data) return [];
    if (tab === "⭐") return favIds().map(clip).filter(Boolean);
    return S.data.clips.filter(function (c) { return c.emotion === tab; });
  }
  // ── 서랍: opts = {title, emotion(처음 탭), cur(지금 짤 id), onPick(id)} ──
  function openDrawer(opts) {
    S.drawer = opts || {};
    S.tab = S.drawer.emotion || (prefs().length ? "⭐" : ((S.data && S.data.emotions[0] || {}).name || "⭐"));
    load().then(renderDrawer);
  }
  function closeDrawer() { S.drawer = null; renderDrawer(); }
  function drawerTab(t) { S.tab = t; renderDrawer(); }
  function pick(id) { var d = S.drawer; S.drawer = null; renderDrawer(); if (d && d.onPick) d.onPick(Number(id)); }
  function renderDrawer() {
    var box = document.getElementById("memeDrawer");
    if (!S.drawer) { if (box) { box.innerHTML = ""; box.style.display = "none"; } return; }
    if (!box) { box = document.createElement("div"); box.id = "memeDrawer"; box.className = "mp-drawer"; document.body.appendChild(box); }
    box.style.display = "";
    var d = S.drawer, list = listOf(S.tab);
    box.innerHTML = '<h3>🎭 ' + e(d.title || "짤 고르기") + ' <span class="mp-x" onclick="MemePack.closeDrawer()">닫기</span></h3>' +
      '<div class="mp-note">눌러서 넣기 · ☆ = 이 감정의 우선 짤(먼저 누른 순서대로 자동 배치에 먼저 쓰여요)</div>' +
      (S.err ? '<div class="mp-err">' + e(S.err) + "</div>" : "") +
      (S.data ? tabs(S.tab, "MemePack.drawerTab") : '<div class="mp-note">불러오는 중…</div>') +
      (S.data && !list.length ? '<div class="mp-note">' + (S.tab === "⭐" ? "아직 비었어요 — 감정 탭에서 ☆를 눌러 담으세요" : "이 감정엔 짤이 없어요") + "</div>" : "") +
      '<div class="mp-grid">' + list.slice(0, 160).map(function (c) { return card(c, { cur: c.id === Number(d.cur), onclick: "MemePack.pick(" + c.id + ")" }); }).join("") + "</div>";
  }
  // 스타일 한 벌(페이지마다 따로 적지 않게)
  var css = document.createElement("style");
  css.textContent = ".mp-drawer{position:fixed;right:0;top:0;bottom:0;width:440px;max-width:100vw;background:#12101c;border-left:2px solid #6b2d7a;z-index:9000;overflow:auto;padding:12px;color:#eee;font-size:13px}" +
    ".mp-drawer h3{margin:0 0 6px;font-size:15px}.mp-x{float:right;cursor:pointer;border:1px solid #555;border-radius:8px;padding:1px 10px;font-size:12px}" +
    ".mp-note{font-size:12px;opacity:.75;margin:4px 0}.mp-err{color:#ff7a7a;font-size:12px}" +
    ".mp-tabs{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0}.mp-tabs span{font-size:12px;cursor:pointer;border:1px solid #444;border-radius:12px;padding:2px 9px}" +
    ".mp-tabs span.on{background:#c85cff;border-color:#c85cff;color:#fff}" +
    ".mp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:6px}" +
    ".mp-card{position:relative;cursor:pointer;border-radius:7px;overflow:hidden;border:2px solid transparent;background:#000}.mp-card.cur{border-color:#ffd24a}" +
    ".mp-card video{width:100%;aspect-ratio:9/16;object-fit:cover;display:block;background:#000}" +
    ".mp-st{position:absolute;right:3px;top:2px;font-size:15px;text-shadow:0 0 3px #000;cursor:pointer}" +
    ".mp-em{position:absolute;left:3px;bottom:3px;font-size:10px;background:#000b;color:#fff;border-radius:5px;padding:0 4px}" +
    ".mp-cell{display:flex;gap:8px;align-items:center;margin-top:6px;padding:6px;border:1px solid #6b2d7a;border-radius:8px;background:#160f1c;font-size:12px}" +
    ".mp-cell video{width:44px;height:78px;object-fit:cover;border-radius:4px;background:#000}" +
    ".mp-btn{cursor:pointer;border:1px solid #6b2d7a;border-radius:8px;padding:2px 9px;font-size:12px;background:transparent;color:inherit}" +
    ".mp-add{display:inline-block;margin-top:6px}";
  document.head.appendChild(css);
  window.MemePack = { load: load, toggleFav: toggleFav, onChange: onChange, clip: clip, rankOf: rankOf, favIds: favIds,
    video: video, card: card, tabs: tabs, listOf: listOf, openDrawer: openDrawer, closeDrawer: closeDrawer,
    drawerTab: drawerTab, pick: pick, poster: poster, media: media, state: S, esc: e };
})();
