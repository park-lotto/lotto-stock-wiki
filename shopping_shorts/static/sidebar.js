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
    ".ss-nav{width:270px;background:var(--panel,#111722);border-right:1px solid var(--line,#1e2735);" +
      "padding:20px 18px;flex-shrink:0;box-sizing:border-box;font-family:'Malgun Gothic',system-ui,sans-serif}" +
    // 메인 로고 = 크고 눈에 띄게(사장님 2026-07-21). 26px·900·자간압축으로 존재감을 준다.
    ".ss-nav h1{font-size:26px;font-weight:900;letter-spacing:-.5px;margin:2px 0 16px;display:flex;align-items:center;gap:7px}" +
    // 계정 패널(2026-07-22) — 로고 바로 아래. 구글아이디·등급·오늘 사용량·가입일·로그아웃.
    ".ss-acct{margin:0 0 16px;background:var(--inset,#0c1412);border:1px solid var(--line,#1e2735);border-radius:14px;padding:14px 14px 12px}" +
    ".ss-acct-top{display:flex;align-items:center;gap:11px}" +
    ".ss-acct-av{width:40px;height:40px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px;color:#08110e;background:var(--grad,linear-gradient(135deg,#6ff0d6,#1f9e7a))}" +
    ".ss-acct-id{min-width:0;flex:1}" +
    ".ss-acct-email{font-size:13.5px;font-weight:700;color:var(--txt,#e6edf3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".ss-acct-badge{display:inline-block;margin-top:4px;font-size:11px;font-weight:800;border:1px solid;border-radius:6px;padding:1px 8px}" +
    ".ss-acct-sub{font-size:12px;color:var(--sub,#8b98a9);margin:9px 2px 0;line-height:1.4}" +
    ".ss-acct-usage{margin-top:11px;padding-top:10px;border-top:1px solid var(--line,#1e2735)}" +
    ".ss-acct-usage-h{font-size:10.5px;color:var(--sub,#8b98a9);text-transform:uppercase;letter-spacing:.4px;margin-bottom:5px}" +
    ".ss-acct-u{display:flex;justify-content:space-between;font-size:12.5px;color:var(--txt,#e6edf3);padding:2px 2px}" +
    ".ss-acct-u b{color:var(--sel-fg,#6ff0d6);font-weight:700}" +
    ".ss-acct-since{font-size:11px;color:var(--sub,#8b98a9);margin-top:9px;text-align:right}" +
    ".ss-acct-links{display:flex;gap:8px;margin-top:12px}" +
    ".ss-acct-link{flex:1;text-align:center;font-size:12px;color:var(--txt,#e6edf3);text-decoration:none;padding:8px 6px;border:1px solid var(--line,#1e2735);border-radius:8px;background:var(--panel,#111722)}" +
    ".ss-acct-link:hover{border-color:var(--accent,#37e0bd);color:var(--sel-fg,#6ff0d6)}" +
    // 브랜드 텍스트만 민트 그라디언트(이모지는 제외 — text-fill:transparent가 이모지 글리프까지 비운다)
    // + 은은한 민트 글로우로 강조(drop-shadow는 clip:text에서도 글자 외곽에 먹는다).
    ".ss-brand{background:var(--grad,linear-gradient(135deg,#6ff0d6,#1f9e7a));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;filter:drop-shadow(0 0 12px rgba(55,224,189,.35))}" +
    // 카테고리 = 박스로 시각 구분 + 크게(사장님 2026-07-21). 그룹을 inset 카드로 감싸고
    // 라벨은 카드 헤더처럼, 항목은 15px·굵게로 키워 눈에 잘 띄고 누르기 쉽게.
    ".ss-group{margin-bottom:14px;background:var(--inset,#0c1412);border:1px solid var(--line,#1e2735);border-radius:12px;padding:9px 9px 7px}" +
    ".ss-label{font-size:12px;color:var(--sel-fg,#6ff0d6);text-transform:uppercase;letter-spacing:.4px;font-weight:700;margin:3px 6px 9px}" +
    ".ss-item{padding:12px 13px;border-radius:9px;font-size:16px;font-weight:600;color:var(--txt,#e6edf3);cursor:pointer;margin-bottom:4px}" +
    ".ss-item.ss-disabled{cursor:default;opacity:.45}" +
    // 선택/활성 표면 = 민트 토큰(--sel-bg/--sel-fg). 아직 토큰이 없는 페이지도 폴백으로 민트가 뜬다.
    ".ss-item.active{background:var(--sel-bg,linear-gradient(90deg,#123a30,#0c221c));color:var(--sel-fg,#6ff0d6)}" +
    ".ss-item:not(.active):not(.ss-disabled):hover{background:var(--hover,#131d19)}" +
    ".ss-work{padding:6px 10px;border-radius:6px;font-size:13px;color:var(--sub,#8b98a9);" +
      "cursor:pointer;margin-bottom:2px;display:flex;align-items:flex-start;gap:4px}" +
    ".ss-work:hover{color:var(--txt,#e6edf3)}" +
    ".ss-work.ss-work-current{color:var(--sel-fg,#6ff0d6);background:var(--sel-bg,linear-gradient(90deg,#123a30,#0c221c))}" +
    ".ss-toggle{margin-top:18px;padding-top:14px;border-top:1px solid var(--line,#1e2735)}" +
    ".ss-toggle-btn{width:100%;padding:9px 12px;border-radius:9px;border:1px solid var(--line,#1e2735);" +
      "background:var(--inset,#0c1412);color:var(--txt,#e6edf3);font-size:13px;cursor:pointer;" +
      "display:flex;align-items:center;justify-content:center;gap:7px;font-family:inherit}" +
    ".ss-toggle-btn:hover{border-color:var(--accent,#37e0bd)}" +
    ".ss-work-open{flex:1;min-width:0;cursor:pointer;display:block}" +
    ".ss-work-name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    // 단계 미니 진행바 — 숫자 'N단계' 대신 7칸 중 채운 칸으로 진척을 형태로 보인다
    ".ss-work-bar{display:flex;gap:2px;margin-top:5px}" +
    ".ss-work-seg{flex:1;height:3px;border-radius:2px;background:var(--line,#1e2735)}" +
    ".ss-work-seg.on{background:var(--accent,#37e0bd)}" +
    ".ss-work-del{flex-shrink:0;cursor:pointer;color:var(--sub,#8b98a9);opacity:0;padding:2px 4px;font-size:13px}" +
    ".ss-work:hover .ss-work-del{opacity:.65}" +
    ".ss-work-del:hover{opacity:1;color:#ff6b6b}" +
    "@media(max-width:760px){body{flex-direction:column}" +
      ".ss-nav{width:100%;border-right:none;border-bottom:1px solid var(--line,#1e2735);display:flex;gap:6px;" +
        "overflow-x:auto;align-items:center;white-space:nowrap;padding:10px 12px}" +
      ".ss-acct{display:none}" +   // 모바일 가로바엔 계정카드 공간이 없다 → /account로
      ".ss-nav h1{margin:0 8px 0 0;flex-shrink:0;font-size:19px}" +
      ".ss-group{margin:0;padding:0;background:none;border:none;display:flex;gap:6px;align-items:center}" +
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
  // 로고 클릭 = 홈(/)으로(사장님 2026-07-21) — 커서·title로 클릭 가능함을 알린다.
  var html = "<h1 onclick=\"location.href='/'\" style=\"cursor:pointer\" title=\"홈으로\">🛍️ <span class=\"ss-brand\">숏템박스</span></h1>";
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

  // 내 계정(유저 자기 설정) — 무료 등급도 접근(data-ss-free). 페이월 잠금 제외.
  html += '<div class="ss-group"><div class="ss-item" data-ss-href="/account" data-ss-free="1"' +
          ' onclick="location.href=\'/account\'">👤 내 계정</div></div>';

  // 테마 토글(민트-블랙 ↔ 화이트-민트). data-theme + localStorage로 전 페이지 공유.
  // 최종 FOUC 방지는 각 페이지 <head> 인라인 스니펫이 하고(렌더 전 실행), 여기선 라벨 동기화만.
  html += '<div class="ss-toggle"><button class="ss-toggle-btn" onclick="window.__ssToggleTheme()" aria-label="화면 테마 전환">' +
          '<span id="ssThemeIco">🌙</span><span id="ssThemeTxt">민트·블랙</span></button></div>';
  window.__ssToggleTheme = function () {
    var root = document.documentElement;
    if (!root) return;
    var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("ssTheme", next); } catch (e) {}
    __ssPaintTheme();
  };
  function __ssPaintTheme() {
    var root = document.documentElement;   // 하네스 mock document엔 없을 수 있다 — 가드
    var light = !!root && root.getAttribute("data-theme") === "light";
    var ico = document.getElementById("ssThemeIco"), txt = document.getElementById("ssThemeTxt");
    if (ico) ico.textContent = light ? "☀️" : "🌙";
    if (txt) txt.textContent = light ? "화이트·민트" : "민트·블랙";
  }

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
  // T6(2026-07-19): /produce 전용 가드 제거 → 전 페이지 노출. 어느 화면에서도 진행 중 작업으로
  //   바로 복귀. 숫자 'N단계'는 7칸 미니 진행바로 바꿔 진척을 형태로 보인다.
  // NAV는 로드 시 동기로 그려지는 정적 배열이라 하위 항목 개념이 없다 → 마운트 뒤에 주입한다.
  // NAV 구조 자체는 안 건드린다 — 페이지 6개가 이 파일을 공유한다.
  var WORK_STEPS = 7;   // produce 7단계 — 미니바 칸 수
  function mountWorks() {
    var nav = document.querySelector(".ss-nav");
    if (!nav) return;
    var open = null;
    try { open = new URLSearchParams(location.search).get("work"); } catch (e) {}
    fetch("/api/produce/works").then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.ok || !d.works) return;
      var h = '<div class="ss-label">내 작업</div>';
      d.works.forEach(function (w) {
        var cur = open && w.work_id === open;
        var name = escHtml(w.title || "(제목 없음)");
        var done = Math.max(0, Math.min(WORK_STEPS, (w.step || 0) + 1));
        var bar = "";
        for (var i = 0; i < WORK_STEPS; i++) bar += '<span class="ss-work-seg' + (i < done ? " on" : "") + '"></span>';
        // 열기(제목+진행바)와 삭제(✕)를 각각 클릭 가능하게 분리한다. ✕는 행 onclick으로 전파되면
        // 삭제 직후 그 작업을 또 열어버리므로 __ssDelWork가 stopPropagation한다.
        h += '<div class="ss-work' + (cur ? " ss-work-current" : "") + '" data-wid="' + escHtml(w.work_id) + '">' +
             '<span class="ss-work-open"' +
             " onclick=\"location.href='/produce?work=" + esc(w.work_id) + "'\"" +
             ' title="' + name + '">' +
             '<span class="ss-work-name">· ' + name + '</span>' +
             '<span class="ss-work-bar">' + bar + '</span></span>' +
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
      // scrollLeft가 0으로 리셋된다. 컨테이너 하나만 만들어 삽입하면 기존 자식·스크롤 위치를
      // 안 건드린다. 테마 토글(.ss-toggle)은 최하단이어야 하므로 그 앞에 끼운다.
      var wrap = document.createElement("div");
      wrap.className = "ss-group ss-works";
      wrap.innerHTML = h;
      var toggle = nav.querySelector(".ss-toggle");
      if (toggle) nav.insertBefore(wrap, toggle); else nav.appendChild(wrap);
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
      '<div style="margin-top:14px;font-size:14px;color:#7db4ff">' +
        (k ? "카톡: " + escHtml(k) + "<br>" : "") +
        (ph ? "전화: " + escHtml(ph) : "") +
        (!k && !ph ? "결제를 원하시면 안내받으신 판매 채널로 문의해 주세요." : "") +
      "</div>" +
      '<div style="margin-top:18px"><button id="ss-pw-close" style="background:#4f9dfa;color:#111;border:0;border-radius:8px;padding:10px 22px;font-weight:800;font-size:14px;cursor:pointer">닫기</button></div>' +
      "</div>";
    document.body.appendChild(m);
    document.getElementById("ss-pw-close").onclick = function () { m.style.display = "none"; };
  }
  window.__ssShowPaywall = _pwModal;
  function _pwBanner(daysLeft) {
    if (document.getElementById("ss-pw-banner")) return;
    var nav = document.querySelector(".ss-nav");
    if (!nav) return;
    // 카톡 문의로 연결(admin 연락처의 kakao가 URL이면 새 탭, 아니면 안내 모달 폴백).
    var kakao = (_pw.contact && _pw.contact.kakao) || "";
    var isUrl = /^https?:\/\//.test(kakao);
    var b = document.createElement(isUrl ? "a" : "div");
    b.id = "ss-pw-banner";
    if (isUrl) { b.href = kakao; b.target = "_blank"; b.rel = "noopener"; }
    // 좌측 사이드바 맨 아래 배치.
    b.style.cssText = "display:block;margin:14px 10px 12px;padding:11px 13px;border-radius:12px;" +
      "background:linear-gradient(135deg,#153a6b,#0d2340);border:1px solid #244a7a;color:#cfe4ff;" +
      "font-size:12.5px;line-height:1.5;text-align:left;cursor:pointer;text-decoration:none;font-family:system-ui,sans-serif";
    b.innerHTML = "🎁 무료 체험 <b style='font-size:14px;color:#fff'>D-" + daysLeft + "</b><br>" +
      "<span style='color:#9fc4f0'>결제하면 계속 써요 · <b style='color:#ffd97a'>카톡 문의 →</b></span>";
    if (!isUrl) b.onclick = function () { _pwModal(); };
    nav.appendChild(b);   // 사이드바 콘텐츠 맨 아래
  }
  function _pwLockSidebar() {
    document.querySelectorAll(".ss-item[data-ss-href]:not([data-ss-free])").forEach(function (el) {
      if (el.querySelector(".ss-lock")) return;
      el.setAttribute("onclick", "window.__ssShowPaywall()");
      el.style.opacity = ".6";
      el.innerHTML = el.innerHTML + ' <span class="ss-lock">🔒</span>';
    });
  }
  // 계정 패널(2026-07-22) — 로고 바로 아래. 구글아이디·등급·오늘 사용량·가입일·로그아웃.
  window.__ssLogout = function () {
    fetch("/logout", { method: "POST" })
      .then(function () { location.href = "/login"; })
      .catch(function () { location.href = "/login"; });
  };
  function _accountCard(d) {
    var nav = document.querySelector(".ss-nav");
    if (!nav || document.getElementById("ss-acct")) return;
    var admin = !!d.is_admin;
    var email = escHtml(d.email || "");
    var initial = escHtml((d.email || "?").trim().charAt(0).toUpperCase() || "?");
    var tier, tierColor, sub;
    if (admin) { tier = "관리자"; tierColor = "#ffd97a"; sub = "전 기능 · 무제한"; }
    else if (d.plan === "pro") { tier = "프로"; tierColor = "#6ff0d6"; sub = "전 기능 이용중"; }
    else if (d.level === "pending") { tier = "승인대기"; tierColor = "#ffa94d"; sub = "승인 후 이용 가능해요"; }
    else if (typeof d.days_left === "number" && d.days_left > 0) { tier = "체험 D-" + d.days_left; tierColor = "#7db4ff"; sub = "만료 후엔 랭킹만 열려요"; }
    else { tier = "무료"; tierColor = "#8b98a9"; sub = "랭킹 열람만 가능해요"; }
    var usage = "";
    if (d.usage && d.usage_limits) {
      var rows = [["렌즈", "lens"], ["영상", "render"], ["대본", "script"]].map(function (p) {
        var u = d.usage[p[1]], lim = d.usage_limits[p[1]];
        return '<div class="ss-acct-u"><span>' + p[0] + '</span><b>' + u + (lim != null ? " / " + lim : "") + "</b></div>";
      }).join("");
      usage = '<div class="ss-acct-usage"><div class="ss-acct-usage-h">오늘 사용량</div>' + rows + "</div>";
    }
    var member = (typeof d.member_days === "number") ? '<div class="ss-acct-since">가입 ' + d.member_days + "일째</div>" : "";
    var card = document.createElement("div");
    card.id = "ss-acct"; card.className = "ss-acct";
    card.innerHTML =
      '<div class="ss-acct-top"><div class="ss-acct-av">' + initial + "</div>" +
        '<div class="ss-acct-id"><div class="ss-acct-email" title="' + email + '">' + email + "</div>" +
          '<div class="ss-acct-badge" style="color:' + tierColor + ";border-color:" + tierColor + '">' + escHtml(tier) + "</div></div></div>" +
      '<div class="ss-acct-sub">' + escHtml(sub) + "</div>" + usage + member +
      '<div class="ss-acct-links">' +
        (admin ? '<a href="/admin" class="ss-acct-link" style="color:#ffd97a;border-color:#5a4a1e">🔐 관리페이지</a>' : '') +
        '<a href="/account" class="ss-acct-link">⚙️ 내 계정</a>' +
        '<a href="#" class="ss-acct-link" onclick="window.__ssLogout();return false">↩ 로그아웃</a></div>';
    var h1 = nav.querySelector("h1");
    if (h1 && h1.nextSibling) nav.insertBefore(card, h1.nextSibling);
    else nav.insertBefore(card, nav.firstChild);
  }
  function initPaywall() {
    fetch("/api/me").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d) return;
      _pw.level = d.level; _pw.contact = d.contact || {};
      _accountCard(d);   // 로고 아래 계정 패널
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
    document.addEventListener("DOMContentLoaded", __ssPaintTheme);
    document.addEventListener("DOMContentLoaded", mountWorks);
    document.addEventListener("DOMContentLoaded", initPaywall);
  } else {
    mount();
    __ssPaintTheme();
    mountWorks();
    initPaywall();
  }
})();
