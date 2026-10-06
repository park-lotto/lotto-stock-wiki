// 효과음 서랍(관제 143 확장) — 2단계 스토리보드 줄·3단계 칸의 효과음 칸이 함께 쓴다.
// ★고르기(어느 줄에 어느 소리)는 서버(storyboard.sfx_preview·sfx_slots)가 한다. 여기는 보여 주고, 사람이 고른 번호를 돌려줄 뿐.
// 분류 탭 순서 = 서버 /api/sfx/bank 의 cats(storyboard.SFX_CATS) 그대로. 자산이 0개면 '효과음 준비 중'.
(function () {
  if (window.SfxBank) return;
  var S = { data: null, err: "", drawer: null, tab: "", audio: null, loading: null };
  function e(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function load() {
    if (S.data) return Promise.resolve(S.data);
    if (S.loading) return S.loading;
    S.loading = fetch("/api/sfx/bank").then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.ok) { S.err = (d && d.error) || "효과음 목록을 못 읽었어요"; S.data = { cats: [], items: [] }; }
      else S.data = d;
      return S.data;
    }).catch(function () { S.err = "효과음 목록을 못 읽었어요(네트워크)"; S.data = { cats: [], items: [] }; return S.data; });
    return S.loading;
  }
  function item(id) { return ((S.data || {}).items || []).filter(function (x) { return x.id === Number(id); })[0] || null; }
  function total() { return ((S.data || {}).items || []).length; }
  function play(id) {
    try { if (S.audio) S.audio.pause(); S.audio = new Audio("/api/sfx/" + Number(id) + "/media"); S.audio.play(); }
    catch (err) { console.warn("[sfx] 재생 실패", err); }
  }
  // 칸 한 줄 — {id, cat, auto, off, on:{change, remove, add}} → html. 이름은 목록을 불러온 뒤에 보인다(없으면 #번호)
  function cell(o) {
    o = o || {};
    if (!S.data) load().then(function () { if (o.onReady) o.onReady(); });
    if (S.data && !total()) return '<div class="sx-cell">🔊 효과음 준비 중' + (o.cat ? " (" + e(o.cat) + ")" : "") + "</div>";
    if (o.id) {
      var it = item(o.id) || {};
      return '<div class="sx-cell"><button class="mp-btn" title="들어보기" onclick="SfxBank.play(' + Number(o.id) + ')">▶</button>' +
        '<div style="flex:1">🔊 <b>' + e(it.title || ("#" + o.id)) + "</b> · " + e(it.cat || o.cat || "") + (o.auto ? " · 자동" : " · 직접 고름") + "</div>" +
        '<button class="mp-btn" onclick="' + o.change + '">바꾸기</button><button class="mp-btn" onclick="' + o.remove + '">빼기</button></div>';
    }
    return '<div class="sx-cell"><div style="flex:1">🔊 ' + (o.off ? "효과음 뺌" : (o.cat ? "효과음 없음(" + e(o.cat) + " 준비 중)" : "효과음 기본(썰 효과음팩)")) + "</div>" +
      '<button class="mp-btn" onclick="' + o.add + '">＋효과음</button></div>';
  }
  function openDrawer(opts) { S.drawer = opts || {}; S.tab = S.drawer.cat || ""; load().then(function () { if (!S.tab) S.tab = ((S.data.cats || [])[0] || {}).name || ""; render(); }); }
  function closeDrawer() { S.drawer = null; render(); }
  function tab(t) { S.tab = t; render(); }
  function pick(id) { var d = S.drawer; S.drawer = null; render(); if (d && d.onPick) d.onPick(Number(id)); }
  function render() {
    var box = document.getElementById("sfxDrawer");
    if (!S.drawer) { if (box) { box.innerHTML = ""; box.style.display = "none"; } return; }
    if (!box) { box = document.createElement("div"); box.id = "sfxDrawer"; box.className = "mp-drawer"; document.body.appendChild(box); }
    box.style.display = "";
    var d = S.drawer, cats = (S.data || {}).cats || [];
    var list = ((S.data || {}).items || []).filter(function (x) { return x.cat === S.tab; });
    box.innerHTML = '<h3>🔊 ' + e(d.title || "효과음 고르기") + ' <span class="mp-x" onclick="SfxBank.closeDrawer()">닫기</span></h3>' +
      (S.err ? '<div class="mp-err">' + e(S.err) + "</div>" : "") +
      '<div class="mp-tabs">' + cats.map(function (c) { return '<span class="' + (c.name === S.tab ? "on" : "") + '" onclick="SfxBank.tab(\'' + e(c.name) + '\')">' + e(c.name) + " " + c.count + "</span>"; }).join("") + "</div>" +
      (!list.length ? '<div class="mp-note">효과음 준비 중 — 이 분류엔 아직 소리가 없어요</div>' : "") +
      list.map(function (x) {
        return '<div class="sx-row' + (x.id === Number(d.cur) ? " cur" : "") + '"><button class="mp-btn" onclick="SfxBank.play(' + x.id + ')">▶</button>' +
          '<span style="flex:1">' + e(x.title || ("#" + x.id)) + " · " + x.dur + "초</span>" +
          '<button class="mp-btn" onclick="SfxBank.pick(' + x.id + ')">넣기</button></div>';
      }).join("");
  }
  var css = document.createElement("style");
  css.textContent = ".sx-cell{display:flex;gap:8px;align-items:center;margin-top:6px;padding:6px;border:1px solid #2d5a7a;border-radius:8px;background:#0f161c;font-size:12px}" +
    ".sx-row{display:flex;gap:6px;align-items:center;padding:4px;border-bottom:1px solid #222;font-size:12px}.sx-row.cur{background:#2a2410}";
  document.head.appendChild(css);
  window.SfxBank = { load: load, cell: cell, item: item, play: play, openDrawer: openDrawer, closeDrawer: closeDrawer, tab: tab, pick: pick, state: S };
})();
