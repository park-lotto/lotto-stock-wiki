/* 공유 좌측 네비게이션 — 모든 페이지 동일 메뉴(단일 소스).
   기존에 페이지마다 <aside class="sidebar">를 손으로 복붙하다 항목이 제각각
   드리프트되고 mix 페이지엔 아예 없던 문제를 하나로 통일(2026-07-13). */
(function () {
  var NAV = [
    { label: "리서치", items: [
      { icon: "📊", text: "레퍼런스 랭킹",   href: "/", free: true },
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
    ".ss-work{padding:5px 8px 5px 30px;border-radius:6px;font-size:12px;color:var(--sub,#8b98a9);" +
      "cursor:pointer;margin-bottom:1px;display:flex;align-items:center;gap:4px}" +
    ".ss-work:hover{color:var(--txt,#e6edf3)}" +
    ".ss-work.ss-work-current{color:#7db4ff;background:rgba(21,58,107,.35)}" +
    ".ss-work-open{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".ss-work-del{flex-shrink:0;cursor:pointer;color:var(--sub,#8b98a9);opacity:0;padding:0 4px;font-size:13px}" +
    ".ss-work:hover .ss-work-del{opacity:.65}" +
    ".ss-work-del:hover{opacity:1;color:#ff6b6b}" +
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
  // esc()는 작은따옴표만 JS-문자열 이스케이프한다 — onclick="location.href='...'"처럼
  // 작은따옴표로 감싼 JS 문자열 안에 넣을 값(it.href·w.work_id, 코드가 만든 불투명 값) 전용이다.
  // title="..." 속성(큰따옴표로 감쌈)이나 텍스트 콘텐츠 자리엔 부적합 — 그건 HTML 엔티티
  // 이스케이프가 필요하다(index.html:420·library.html:183과 동일 관례). 사용자가 타이핑한
  // 대본 앞 20자(store.py의 title)처럼 신뢰 못 할 값은 반드시 이걸로.
  function escHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  var html = "<h1>🛍️ 쇼핑쇼츠</h1>";
  NAV.forEach(function (g) {
    html += '<div class="ss-group"><div class="ss-label">' + g.label + "</div>";
    g.items.forEach(function (it) {
      var active = !!it.href && (it.href === path || (it.href === "/" && path === "/"));
      var cls = "ss-item" + (active ? " active" : "") + (it.href ? "" : " ss-disabled");
      var onclick = it.href && !active ? ' onclick="location.href=\'' + esc(it.href) + "'\"" : "";
      var payAttr = (it.href ? ' data-ss-href="' + esc(it.href) + '"' : "") + (it.free ? ' data-ss-free="1"' : "");
      html += '<div class="' + cls + '"' + payAttr + onclick + ">" + it.icon + " " + it.text + "</div>";
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
  // 작업 삭제(2026-07-19) — 사이드바 ✕. 백엔드 /api/produce/works/{id}/delete는 이미 있다.
  // 현재 열린 작업을 지우면 화면이 그 작업을 붙들고 있으니 새 작업으로 보낸다. 아니면 행만 제거.
  window.__ssDelWork = function (ev, wid) {
    if (ev && ev.stopPropagation) ev.stopPropagation();
    if (!window.confirm("이 작업을 삭제할까요? 되돌릴 수 없습니다.")) return;
    fetch("/api/produce/works/" + encodeURIComponent(wid) + "/delete", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) { window.alert("삭제 실패"); return; }
        var open = null;
        try { open = new URLSearchParams(location.search).get("work"); } catch (e) {}
        if (open === wid) { location.href = "/produce?new=1"; return; }
        var node = document.querySelector('.ss-work[data-wid="' + wid + '"]');
        if (node) node.remove();
      })
      .catch(function () { window.alert("삭제 실패"); });
  };
  // 제작소 작업파일 목록(2026-07-17) — 사장님 제보 "내일 다시 들어와도 기록남고 그대로".
  // NAV는 로드 시 동기로 그려지는 정적 배열이라 하위 항목 개념이 없다 → 마운트 뒤에 주입한다.
  // NAV 구조 자체는 안 건드린다 — 페이지 6개가 이 파일을 공유한다.
  function mountWorks() {
    if (path !== "/produce") return;   // 다른 페이지에서 제작소 작업을 부를 이유가 없다
    var nav = document.querySelector(".ss-nav");
    if (!nav) return;
    var open = null;
    try { open = new URLSearchParams(location.search).get("work"); } catch (e) {}
    fetch("/api/produce/works").then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.ok || !d.works) return;
      var h = "";
      d.works.forEach(function (w) {
        var cur = open && w.work_id === open;
        var name = escHtml(w.title || "(제목 없음)");
        // 열기(제목)와 삭제(✕)를 각각 클릭 가능하게 분리한다. ✕는 행 onclick으로 전파되면
        // 삭제 직후 그 작업을 또 열어버리므로 __ssDelWork가 stopPropagation한다.
        h += '<div class="ss-work' + (cur ? " ss-work-current" : "") + '" data-wid="' + escHtml(w.work_id) + '">' +
             '<span class="ss-work-open"' +
             " onclick=\"location.href='/produce?work=" + esc(w.work_id) + "'\"" +
             ' title="' + name + '">· ' + name + " · " + (w.step + 1) + "단계</span>" +
             '<span class="ss-work-del" title="이 작업 삭제"' +
             " onclick=\"window.__ssDelWork(event,'" + esc(w.work_id) + "')\">✕</span>" +
             "</div>";
      });
      // ★?new=1이 없으면 produce.html이 이걸 새로고침과 구분 못 해 직전 작업을 덮어쓴다(C-1).
      h += '<div class="ss-work" onclick="location.href=\'/produce?new=1\'">+ 새 작업</div>';
      // nav.innerHTML = nav.innerHTML + h (통째 재할당) 금지 — nav의 기존 자식 전체를 파괴하고
      // 문자열에서 재파싱한다. 이 함수는 fetch().then() 안에서 비동기로 돈다 — nav가 이미
      // 라이브 DOM에 들어간 뒤에 재파싱되면, 모바일(@media max-width:760px, .ss-nav는
      // overflow-x:auto로 가로스크롤)에서 사용자가 nav를 옆으로 스크롤해둔 상태의
      // scrollLeft가 0으로 리셋된다. 컨테이너 하나만 만들어 appendChild하면 기존 자식·스크롤
      // 위치를 안 건드리고 노드 하나만 끝에 붙는다.
      var wrap = document.createElement("div");
      wrap.innerHTML = h;
      nav.appendChild(wrap);
    }).catch(function () {});   // 서버가 죽어도 네비게이션은 살아 있어야 한다
  }

  // ── 유료게이트(2026-07-19): /api/me 등급으로 UI를 잠근다. sidebar.js는 6개 페이지 공유라
  //    여기 한 곳이면 전 페이지에 체험배너·🔒메뉴·만료안내가 걸린다. ──
  var _pw = { level: "full", contact: {} };
  function _pwModal() {
    var ex = document.getElementById("ss-pw-modal");
    if (ex) { ex.style.display = "flex"; return; }
    var k = _pw.contact.kakao || "", ph = _pw.contact.phone || "";
    var m = document.createElement("div");
    m.id = "ss-pw-modal";
    m.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.72);display:flex;align-items:center;justify-content:center;font-family:'Malgun Gothic',system-ui,sans-serif";
    m.innerHTML = '<div style="background:#16161c;border:1px solid #2a2a30;border-radius:16px;padding:28px 26px;max-width:340px;text-align:center;color:#e8e8ea">' +
      '<div style="font-size:40px">🔒</div>' +
      '<div style="font-size:18px;font-weight:800;margin:10px 0 6px">무료 체험이 끝났어요</div>' +
      '<div style="font-size:14px;color:#b8b8c0;line-height:1.6">이 기능은 결제하시면 계속 쓸 수 있어요.<br>담아둔 영상·자료는 <b>그대로 보존</b>돼요.</div>' +
      (k || ph ? '<div style="margin-top:14px;font-size:14px;color:#7db4ff">' + (k ? "카톡: " + escHtml(k) + "<br>" : "") + (ph ? "전화: " + escHtml(ph) : "") + "</div>" : "") +
      '<div style="margin-top:18px"><button id="ss-pw-close" style="background:#4f9dfa;color:#111;border:0;border-radius:8px;padding:10px 22px;font-weight:800;font-size:14px;cursor:pointer">닫기</button></div>' +
      "</div>";
    document.body.appendChild(m);
    document.getElementById("ss-pw-close").onclick = function () { m.style.display = "none"; };
  }
  window.__ssShowPaywall = _pwModal;
  function _pwBanner(daysLeft) {
    if (document.getElementById("ss-pw-banner")) return;
    var b = document.createElement("div");
    b.id = "ss-pw-banner";
    b.style.cssText = "position:sticky;top:0;z-index:9999;background:linear-gradient(90deg,#153a6b,#0d2340);color:#cfe4ff;padding:8px 14px;font-size:13px;text-align:center;font-family:system-ui,sans-serif";
    b.innerHTML = "🎁 무료 체험 <b style='font-size:15px'>D-" + daysLeft + "</b> · 결제하면 계속 쓸 수 있어요";
    var nav = document.querySelector(".ss-nav");
    if (nav && nav.nextSibling) document.body.insertBefore(b, nav.nextSibling);
    else document.body.appendChild(b);
  }
  function _pwLockSidebar() {
    document.querySelectorAll(".ss-item[data-ss-href]:not([data-ss-free])").forEach(function (el) {
      if (el.querySelector(".ss-lock")) return;
      el.setAttribute("onclick", "window.__ssShowPaywall()");
      el.style.opacity = ".6";
      el.innerHTML = el.innerHTML + ' <span class="ss-lock">🔒</span>';
    });
  }
  function initPaywall() {
    fetch("/api/me").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d) return;
      _pw.level = d.level; _pw.contact = d.contact || {};
      if (d.level === "ranking_only") _pwLockSidebar();
      else if (typeof d.days_left === "number" && d.days_left >= 0 && d.plan !== "pro") _pwBanner(d.days_left);
    }).catch(function () {});
  }
  // 유료 API가 402(등급부족)를 주면 만료 안내 모달 — 페이지 내 어떤 유료버튼이든 공통 처리.
  var _origFetch = window.fetch;
  window.fetch = function () {
    return _origFetch.apply(this, arguments).then(function (resp) {
      if (resp && resp.status === 402) { try { _pwModal(); } catch (e) {} }
      return resp;
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
    document.addEventListener("DOMContentLoaded", mountWorks);
    document.addEventListener("DOMContentLoaded", initPaywall);
  } else {
    mount();
    mountWorks();
    initPaywall();
  }
})();
