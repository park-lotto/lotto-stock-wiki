/* 공유 좌측 네비게이션 — 모든 페이지 동일 메뉴(단일 소스).
   기존에 페이지마다 <aside class="sidebar">를 손으로 복붙하다 항목이 제각각
   드리프트되고 mix 페이지엔 아예 없던 문제를 하나로 통일(2026-07-13). */
(function () {
  var NAV = [
    { label: "리서치", items: [
      { icon: "📊", text: "레퍼런스 랭킹",   href: "/" },
      { icon: "⭐", text: "영상 즐겨찾기",   href: "/collection" },
      { icon: "📚", text: "대본 즐겨찾기",   href: "/library" },
      { icon: "🔎", text: "신규채널 픽업",   href: "/discover" },
      { icon: "🎞️", text: "장면 라이브러리", href: "/scene_library" },
    ] },
    { label: "제작", items: [
      { icon: "🎬", text: "영상 제작소",     href: "/produce" },
    ] },
    { label: "소통", items: [
      { icon: "💬", text: "인스타 소통공간", href: "/outreach" },
    ] },
  ];

  // 현재 경로 정규화: '/index.html'·'/'→'/', '/mix.html'→'/mix'
  var path = location.pathname.replace(/\.html$/, "");
  if (path === "" || path === "/index") path = "/";
  if (path.length > 1) path = path.replace(/\/$/, "");

  var css =
    "body{display:flex;min-height:100vh;margin:0}" +
    ".ss-nav{width:230px;background:var(--panel,#111722);border-right:1px solid var(--line,#1e2735);" +
      "padding:16px;flex-shrink:0;box-sizing:border-box;font-family:'Malgun Gothic',system-ui,sans-serif}" +
    ".ss-nav h1{font-size:14px;color:var(--sub,#8b98a9);margin:0 0 16px}" +
    ".ss-group{margin-bottom:18px}" +
    ".ss-label{font-size:11px;color:var(--sub,#8b98a9);text-transform:uppercase;margin-bottom:8px}" +
    ".ss-item{padding:8px 12px;border-radius:8px;font-size:13px;color:var(--txt,#e6edf3);cursor:pointer;margin-bottom:2px}" +
    ".ss-item.ss-disabled{cursor:default;opacity:.45}" +
    ".ss-item.active{background:linear-gradient(90deg,#153a6b,#0d2340);color:#7db4ff}" +
    "@media(max-width:760px){body{flex-direction:column}" +
      ".ss-nav{width:100%;border-right:none;border-bottom:1px solid var(--line,#1e2735);display:flex;gap:6px;" +
        "overflow-x:auto;align-items:center;white-space:nowrap;padding:10px 12px}" +
      ".ss-nav h1{margin:0 8px 0 0;flex-shrink:0}" +
      ".ss-group{margin:0;display:flex;gap:6px;align-items:center}" +
      ".ss-label{display:none}" +
      ".ss-item{margin:0;padding:6px 10px;flex-shrink:0;font-size:12px}}";
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  function esc(s) { return String(s).replace(/'/g, "\\'"); }
  var html = "<h1>🛍️ 쇼핑쇼츠</h1>";
  NAV.forEach(function (g) {
    html += '<div class="ss-group"><div class="ss-label">' + g.label + "</div>";
    g.items.forEach(function (it) {
      var active = !!it.href && (it.href === path || (it.href === "/" && path === "/"));
      var cls = "ss-item" + (active ? " active" : "") + (it.href ? "" : " ss-disabled");
      var onclick = it.href && !active ? ' onclick="location.href=\'' + esc(it.href) + "'\"" : "";
      html += '<div class="' + cls + '"' + onclick + ">" + it.icon + " " + it.text + "</div>";
    });
    html += "</div>";
  });

  function mount() {
    // 페이지에 하드코딩된 옛 사이드바가 있으면 제거(중복 방지)
    var old = document.querySelector("aside.sidebar");
    if (old) old.remove();
    if (document.querySelector("aside.ss-nav")) return;
    var aside = document.createElement("aside");
    aside.className = "ss-nav";
    aside.innerHTML = html;
    document.body.insertBefore(aside, document.body.firstChild);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
