/* 공유 좌측 네비게이션 — 모든 페이지 동일 메뉴(단일 소스).
   기존에 페이지마다 <aside class="sidebar">를 손으로 복붙하다 항목이 제각각
   드리프트되고 mix 페이지엔 아예 없던 문제를 하나로 통일(2026-07-13). */
(function () {
  // 런처 v3 팝업 핸드오프(2026-07-23): 이 창이 로그인 팝업(name=stb_login)이고 열어준 부모가
  // 살아있으면 = 로그인 성공으로 /(홈)가 뜬 것 → 부모를 홈으로 보내고 팝업을 닫는다.
  // 작은 런처 창(바로가기 --window-size)으로 열렸다가 로그인했으면 넓게 키운다(막히면 무시).
  // (try/catch·프로퍼티 접근만 — 테스트 하네스 미니 DOM에도 안전)
  try {
    if (window.name === "stb_login" && window.opener && !window.opener.closed) {
      window.opener.location.href = "/";
      window.close();
      return;
    }
    if (window.outerWidth && window.outerWidth < 700) {
      try { window.resizeTo(1500, 950); } catch (_) {}
    }
  } catch (_) {}
  // PWA 부트스트랩 — 앱 페이지 전체(사이드바 포함 페이지)에 매니페스트·아이콘을 주입.
  // 페이지마다 <head>를 손대면 드리프트되므로 여기 한 곳에서(공개 대문·로그인은 app.py가 직접).
  // (setAttribute 대신 프로퍼티 할당 — 테스트 하네스의 미니 DOM에도 안전)
  if (!document.querySelector('link[rel="manifest"]')) {
    var _mf = document.createElement("link"); _mf.rel = "manifest"; _mf.href = "/manifest.webmanifest";
    var _tc = document.createElement("meta"); _tc.name = "theme-color"; _tc.content = "#0c1411";
    var _fi = document.createElement("link"); _fi.rel = "icon"; _fi.href = "/favicon.ico";
    var _at = document.createElement("link"); _at.rel = "apple-touch-icon"; _at.href = "/apple-touch-icon.png";
    document.head.appendChild(_mf); document.head.appendChild(_tc);
    document.head.appendChild(_fi); document.head.appendChild(_at);
  }

  var NAV = [
    { label: "리서치", items: [
      { icon: "📊", text: "레퍼런스 랭킹",   href: "/", free: true },
      // ★free:true = 잠금(🔒) 대상에서 뺀다. 서버 화이트리스트(_FREE_EXACT_GET)와 짝이다 —
      //   서버만 열고 여기를 안 열면 체험 사용자는 눌러도 페이월 모달만 보고 못 들어간다.
      // 즐겨찾기 2칸(2026-09-02 사장님) — 채널과 영상을 갈라 담는다.
      // 둘 다 개인 북마크라 전역 수집(레퍼런스 채널 관리)과 성격이 다르다.
      { icon: "⭐", text: "나만의 채널등록", href: "/fav_channels", free: true },
      { icon: "⭐", text: "영상 즐겨찾기",  href: "/collection", free: true },
      { icon: "🔎", text: "신규채널 픽업",   href: "/discover" },
      { icon: "🎞️", text: "장면 라이브러리", href: "/scene_library" },
      { icon: "🏆", text: "역대 히트작",     href: "/archive", admin: true },
      { icon: "📋", text: "레퍼런스 채널 관리", href: "/refs", admin: true },
    ] },
    { label: "제작", items: [
      // 제작소는 등급에 따라 서버가 다른 파일을 준다(full=진짜 / 그 외=얼린 미리보기).
      // 그래서 잠그지 않는다 — 사장님 지시 "열어두되 사용 자체가 안 되게".

      // ★go = 실제로 이동할 주소(2026-08-24 사장님 "그냥 새로운 작업하려면 빈 페이지").
      //   href는 그대로 /produce로 둔다 — 위 active 판정(it.href === path)과
      //   유료게이트 data-ss-href가 **쿼리 없는 경로**로 맞춰져 있어서,
      //   href에 ?new=1을 붙이면 제작소에서 이 메뉴의 활성표시가 죽는다.
      //   ?new=1 → produce.html _bootRestore가 clearWork() 후 빈 작업을 열어준다.
      //   기존 작업은 아래 '내 작업'(?work=<id>) 목록에 그대로 남는다 — 유실 0.
      //   ⚠ 랭킹의 '제작소로 보내기'는 재료를 sessionStorage에 담고 **쿼리 없는**
      //      /produce로 가야 한다(_consumeProduceHandoff) — 그쪽은 안 건드린다.
      { icon: "🎬", text: "숏템 제작소",     href: "/produce", go: "/produce?new=1", free: true },
      // 1기 챌린지(2026-08-24) — 하루 2영상 업로드 챌린지.
      // free:true는 서버 _FREE_EXACT_GET과 짝이다(챌린지 참가자격은 결제등급과 별개).
      { icon: "🔥", text: "1기 챌린지",      href: "/challenge", free: true },
      { icon: "🏁", text: "챌린지 관리",     href: "/challenge/admin", free: true, admin: true },
    ] },
    { label: "소통", items: [
      { icon: "💬", text: "인스타 소통공간", href: "/outreach" },
      // 도움말(2026-08-23) — 반복 문의를 줄이는 자리. 로그인 없이도 열리므로 free.
      { icon: "❓", text: "도움말·자주 묻는 질문", href: "/help", free: true },
      // 오류 신고(2026-08-24 사장님 지시) — href 없이 클릭만 받는다(id로 잡는다).
      // ★고객에게 "job_id 알려주세요"라고 물으면 못 받는다. 화면이 자동으로 담는다.
      { icon: "🐞", text: "오류 신고", id: "ssBugBtn", free: true },
    ] },
    // ★2026-08-17 '설정 > 내 설정' 그룹을 없앴다. 상단 계정 카드의 '마이페이지'와
    //   같은 곳(/settings)인데 이름만 달라서, 사장님이 키 등록표를 못 찾으셨다.
    //   진입점을 하나로 둔다 — 계정 카드(아래 _accountCard)와 모바일 메뉴뿐이다.
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
    // 가운데 정렬(사장님 2026-07-25) — 로고는 사이드바 폭의 중앙에 놓는다.
    ".ss-nav h1{font-size:26px;font-weight:900;letter-spacing:-.5px;margin:8px 0 20px;display:flex;align-items:center;justify-content:center;gap:8px}" +
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
    ".ss-acct-links{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}" +
    // 44px 터치타깃(2026-08-15) — 실측 34px이었다.
    ".ss-acct-link{flex:1 1 0;white-space:nowrap;text-align:center;font-size:12px;color:var(--txt,#e6edf3);text-decoration:none;padding:12px 4px;min-height:44px;display:flex;align-items:center;justify-content:center;box-sizing:border-box;border:1px solid var(--line,#1e2735);border-radius:8px;background:var(--panel,#111722)}" +
    ".ss-acct-link.wide{flex-basis:100%}" +
    ".ss-acct-link:hover{border-color:var(--accent,#37e0bd);color:var(--sel-fg,#6ff0d6)}" +
    // 브랜드 텍스트만 민트 그라디언트(이모지는 제외 — text-fill:transparent가 이모지 글리프까지 비운다)
    // + 은은한 민트 글로우로 강조(drop-shadow는 clip:text에서도 글자 외곽에 먹는다).
    /* 워드마크 v3(2026-07-25): 민트→오로라 + 끝에 골드 마침점. app.py .brand .nm과 같은 규칙 */
    ".ss-brand{letter-spacing:-.3px;background:linear-gradient(135deg,#3ee0bf 0%,#a8f2e4 40%,#a78bff 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;filter:drop-shadow(0 0 14px rgba(62,224,191,.55))}" +
    ".ss-brand::after{content:'.';background:none;-webkit-text-fill-color:#facc6b;color:#facc6b;filter:none;margin-left:1px}" +
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
    // 44px 터치타깃(2026-08-15) — 실측 37px이었다. 60대가 주 사용자.
    ".ss-toggle-btn{width:100%;padding:12px;min-height:44px;border-radius:9px;border:1px solid var(--line,#1e2735);" +
      "background:var(--inset,#0c1412);color:var(--txt,#e6edf3);font-size:13px;cursor:pointer;" +
      "display:flex;align-items:center;justify-content:center;gap:7px;font-family:inherit}" +
    ".ss-toggle-btn:hover{border-color:var(--accent,#37e0bd)}" +
    ".ss-work-open{flex:1;min-width:0;cursor:pointer;display:block}" +
    ".ss-work-name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    // 단계 미니 진행바 — 숫자 'N단계' 대신 7칸 중 채운 칸으로 진척을 형태로 보인다
    ".ss-work-bar{display:flex;gap:2px;margin-top:5px}" +
    ".ss-work-seg{flex:1;height:3px;border-radius:2px;background:var(--line,#1e2735)}" +
    ".ss-work-seg.on{background:var(--accent,#37e0bd)}" +
    // ✏ 이름수정·✕ 삭제 — 같은 자리·같은 hover 규칙(모양이 다르면 하나만 있는 줄 안다).
    // ★모바일(터치)엔 hover가 없다 — 아래 @media에서 항상 보이게 한다.
    ".ss-work-del,.ss-work-ren{flex-shrink:0;cursor:pointer;color:var(--sub,#8b98a9);opacity:0;padding:2px 4px;font-size:13px}" +
    ".ss-work:hover .ss-work-del,.ss-work:hover .ss-work-ren{opacity:.65}" +
    ".ss-work-del:hover{opacity:1;color:#ff6b6b}" +
    ".ss-work-ren:hover{opacity:1;color:var(--accent,#37e0bd)}" +
    "@media(max-width:760px){.ss-work-del,.ss-work-ren{opacity:.65}}" +
    // 데스크톱: 상단 계정 카드에 '⚙️ 내 계정'이 있어 이 메뉴는 중복 → 숨김. 모바일은 카드가
    // 숨겨지므로(.ss-acct display:none) 이 메뉴를 노출한다(2026-07-24).
    "@media(min-width:761px){.ss-group-acct{display:none}}" +
    // 모바일 전용 계정 버튼 — 기본은 숨김, 위 @media(max-width:760px)에서만 켠다.
    ".ss-acct-mbtn{display:none;align-items:center;gap:6px;flex-shrink:0;cursor:pointer;" +
      "min-height:44px;padding:0 10px;border:1px solid var(--line,#1e2735);border-radius:10px;" +
      "background:var(--inset,#0c1412);font-family:inherit}" +
    ".ss-acct-mbtn .ss-acct-av{width:26px;height:26px;font-size:13px}" +
    ".ss-acct-mbtn .ss-acct-mtier{font-size:11.5px;font-weight:800}" +
    ".ss-acct-mbtn .ss-acct-mcar{font-size:9px;color:var(--sub,#8b98a9)}" +
    "@media(max-width:760px){body{flex-direction:column}" +
      ".ss-nav{width:100%;border-right:none;border-bottom:1px solid var(--line,#1e2735);display:flex;gap:6px;" +
        "overflow-x:auto;align-items:center;white-space:nowrap;padding:10px 12px}" +
      // ★모바일에서 카드를 통째로 숨기면 오늘 사용량·등급·로그아웃에 닿을 길이 없다
      //   (2026-08-26 사장님 제보). 숨기는 대신 가로띠의 아바타 버튼으로 펼친다.
      //   position:fixed = 가로띠가 overflow-x:auto라 그 안에 absolute로 두면 잘린다.
      ".ss-acct{display:none;position:fixed;left:8px;right:8px;margin:0;z-index:9999;" +
        "max-height:72vh;overflow:auto;box-shadow:0 14px 36px rgba(0,0,0,.6)}" +
      ".ss-acct.ss-open{display:block}" +
      ".ss-acct-mbtn{display:flex}" +
      // 모바일 가로바에선 가운데정렬을 되돌린다(옆으로 메뉴가 붙는 자리라 왼쪽 고정)
      ".ss-nav h1{margin:0 8px 0 0;flex-shrink:0;font-size:19px;justify-content:flex-start}" +
      ".ss-group{margin:0;padding:0;background:none;border:none;display:flex;gap:6px;align-items:center}" +
      ".ss-label{display:none}" +
      // 44px 터치타깃(2026-08-15) — 실측 28px이라 가로띠에서 손가락으로 누르기 작았다.
      // 가로띠는 어차피 가로 스크롤(scrollWidth 1477 > 390)이라 높이를 키워도 안 잘린다.
      ".ss-item{margin:0;padding:0 13px;min-height:44px;display:flex;align-items:center;" +
        "flex-shrink:0;font-size:13px}}";
  // 버튼 쿠션감(전역, 2026-07-24) — 누르면 쏙 눌렸다 통통 튀어나옴. 사장님 선택 '쿠션' 프리셋.
  // 자체 transition 없는 주버튼(.btn-next/.btn-prev/.tab/.cta-shine 등)엔 풀 적용. 자체
  // transition을 가진 버튼은 페이지 규칙(클래스>요소)이 우선이라 배경 트랜지션을 안 밟고
  // :active 누름 스케일만 얹힌다(회귀 없음). sidebar.js 로드 페이지(제작 워크플로 9종) 공통.
  css +=
    "button,.btn,.btn-next,.btn-prev,.tab,.cta,.cta-shine,[role=button]{" +
      "transition:transform .34s cubic-bezier(.22,1.4,.4,1)}" +
    "button:active,.btn:active,.btn-next:active,.btn-prev:active,.tab:active,.cta:active,.cta-shine:active,[role=button]:active{" +
      "transform:scale(.94) translateY(1px);transition-duration:.05s;transition-timing-function:ease-out}" +
    "@media(prefers-reduced-motion:reduce){" +
      "button,.btn,.btn-next,.btn-prev,.tab,.cta,.cta-shine,[role=button]{transition:none}" +
      "button:active,.btn:active,.btn-next:active,.btn-prev:active,.tab:active,.cta:active,.cta-shine:active,[role=button]:active{transform:none;filter:brightness(1.12)}}";
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
  // 브랜드 엠블럼 v4 — app.py _LOGO_SVG와 같은 그림(AI 원본 PNG, 배경 투명 전처리).
  // 사장님 선택: 내가 손으로 짠 SVG 대신 AI 원본 그림을 그대로 쓴다.
  // 배경이 투명이라 사이드바 패널에 네모로 안 뜬다(직전 문제 해결).
  var BRAND_SVG =
    '<img src="/brand-logo.png" alt="숏템메이커" width="44" height="44"' +
    ' style="flex-shrink:0;filter:drop-shadow(0 0 9px rgba(62,224,191,.45))" decoding="async">';
  var html = "<h1 onclick=\"location.href='/'\" style=\"cursor:pointer\" title=\"홈으로\">" + BRAND_SVG + " <span class=\"ss-brand\">숏템메이커</span></h1>";
  NAV.forEach(function (g) {
    html += '<div class="ss-group"><div class="ss-label">' + g.label + "</div>";
    g.items.forEach(function (it) {
      var active = !!it.href && (it.href === path || (it.href === "/" && path === "/"));
      // 관리자 전용 항목(admin:true)은 기본 숨김으로 렌더 → /api/me가 is_admin이면 아래에서 노출.
      // id 항목(오류 신고 등)은 링크가 아니라 **그 자리에서 창을 여는 버튼**이다 —
      // href가 없다고 ss-disabled(회색)로 만들면 눌리지 않는다(2026-08-24).
      var isBtn = !it.href && !!it.id;
      var cls = "ss-item" + (active ? " active" : "") + ((it.href || isBtn) ? "" : " ss-disabled") + (it.admin ? " ss-admin-only" : "");
      var hide = it.admin ? ' style="display:none"' : "";
      // 클릭 목적지는 go가 있으면 go, 없으면 href(종전과 동일).
      var target = it.go || it.href;
      // ★active여도 go가 있으면 클릭을 살린다 — 제작소를 보고 있을 때도
      //   이 버튼을 눌러 빈 작업으로 가야 한다(같은 경로라 종전엔 클릭이 죽어 있었다).
      var onclick = isBtn ? ' onclick="ssOpenBugReport()"' :
          target && (!active || it.go) ? ' onclick="location.href=\'' + esc(target) + "'\"" : "";
      var payAttr = (it.href ? ' data-ss-href="' + esc(it.href) + '"' : "") + (it.free ? ' data-ss-free="1"' : "");
      var idAttr = it.id ? ' id="' + it.id + '"' : "";
      html += '<div class="' + cls + '"' + idAttr + payAttr + hide + onclick + ">" + it.icon + " " + it.text + "</div>";
    });
    html += "</div>";
  });

  // 내 계정 메뉴 — 데스크톱에선 상단 계정 카드(_accountCard)의 '⚙️ 내 계정'과 중복이라 숨긴다.
  // 단 모바일(≤760px)에선 그 카드(.ss-acct)가 공간 부족으로 display:none이라, 이 메뉴가 /account·
  // 로그아웃에 닿는 유일한 통로다 → 모바일에만 노출(ss-item-acct + 아래 @media)(2026-07-24).
  html += '<div class="ss-group ss-group-acct"><div class="ss-item ss-item-acct" data-ss-href="/settings" data-ss-free="1"' +
          ' onclick="location.href=\'/settings\'">👤 마이페이지</div></div>';

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
        // 로컬 draft(sessionStorage)가 방금 지운 작업을 붙들고 있으면 함께 지운다(2026-07-24).
        // 안 지우면 제작소 재진입 시 _consumeProduceHandoff가 그 draft를 복원→saveWork의
        // INSERT 폴백으로 되살려, 지운 작업이 1단계로 부활하고 '내 작업'에 다시 뜬다.
        // URL ?work= 만 보던 기존 가드는 다른 화면에서 삭제할 때 이 draft를 놓쳤다.
        try {
          var w = JSON.parse(sessionStorage.getItem("produce_work") || "null");
          if (w && w.work_id === wid) sessionStorage.removeItem("produce_work");
        } catch (e) {}
        var open = null;
        try { open = new URLSearchParams(location.search).get("work"); } catch (e) {}
        if (open === wid) { location.href = "/produce?new=1"; return; }
        var node = document.querySelector('.ss-work[data-wid="' + wid + '"]');
        if (node) node.remove();
      })
      .catch(function () { window.alert("삭제 실패"); });
  };
  // 작업 이름 바꾸기(2026-08-17) — 사장님 "내 작업에 작업명 수정할수있게".
  // 목록이 '(제목 없음)' 여러 줄이라 어느 게 뭔지 구분이 안 됐다(자동 제목은 대본 앞 20자인데,
  // 대본을 아직 안 뽑은 작업은 재료가 없다).
  // ★서버가 제목을 정한다(store._work_title) — 여기서 이름을 계산하지 않고 **응답을 받아 그린다**.
  //   두 군데서 계산하면 반드시 어긋난다(CLAUDE.md 0순위-B).
  window.__ssRenWork = function (ev, wid) {
    if (ev && ev.stopPropagation) ev.stopPropagation();
    var node = document.querySelector('.ss-work[data-wid="' + wid + '"]');
    var nameEl = node ? node.querySelector(".ss-work-name") : null;
    // 현재 이름을 기본값으로 넣어준다 — '· '는 화면 장식이라 뺀다.
    var now = nameEl ? nameEl.textContent.replace(/^·\s*/, "") : "";
    if (now === "(제목 없음)") now = "";
    var next = window.prompt("작업 이름을 입력하세요 (비우면 대본 앞부분으로 자동)", now);
    if (next === null) return;   // 취소 — 빈 문자열('')은 '자동으로 되돌리기'라 통과시킨다
    fetch("/api/produce/works/" + encodeURIComponent(wid) + "/rename", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: next })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) { window.alert("이름을 바꾸지 못했어요"); return; }
        var t = d.title || "(제목 없음)";
        if (nameEl) nameEl.textContent = "· " + t;
        var open = node ? node.querySelector(".ss-work-open") : null;
        if (open) open.title = t;
        // ★지금 열려 있는 작업이면 제작소에도 알린다(2026-08-17). produce.html의 STATE는
        //   title_manual을 모르는 채라, 다음 saveWork()가 그 필드 없는 state를 덮어써
        //   **방금 지은 이름이 조용히 사라진다**. STATE에 심어 두면 이후 저장에도 실려 나간다.
        //   훅이 없는 페이지(제작소 밖)에선 그냥 넘어간다 — 그 페이지엔 덮어쓸 STATE가 없다.
        try { if (window.__ssApplyWorkTitle) window.__ssApplyWorkTitle(wid, next); } catch (e) {}
      })
      .catch(function () { window.alert("이름을 바꾸지 못했어요"); });
  };
  // 제작소 작업파일 목록(2026-07-17) — 사장님 제보 "내일 다시 들어와도 기록남고 그대로".
  // T6(2026-07-19): /produce 전용 가드 제거 → 전 페이지 노출. 어느 화면에서도 진행 중 작업으로
  //   바로 복귀. 숫자 'N단계'는 7칸 미니 진행바로 바꿔 진척을 형태로 보인다.
  // NAV는 로드 시 동기로 그려지는 정적 배열이라 하위 항목 개념이 없다 → 마운트 뒤에 주입한다.
  // NAV 구조 자체는 안 건드린다 — 페이지 6개가 이 파일을 공유한다.
  var WORK_STEPS = 7;   // produce 7단계 — 미니바 칸 수
  // curWid: '지금 작업'으로 표시할 work_id. 안 넘기면 URL(?work=)에서 뽑는다.
  // ★produce.html의 WORK_ID는 `let`이라 **window에 안 올라간다**(렉시컬 바인딩 — MIX_JOB에서
  //   이미 한 번 밟은 함정). 그래서 window를 훔쳐보지 않고 **인자로 받는다**.
  function mountWorks(curWid) {
    var nav = document.querySelector(".ss-nav");
    if (!nav) return;
    var open = curWid || null;
    if (!open) { try { open = new URLSearchParams(location.search).get("work"); } catch (e) {} }
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
             '<span class="ss-work-ren" title="이름 바꾸기"' +
             // ★U+FE0F(VS16)를 반드시 붙인다 — 맨 ✏(U+270F)는 윈도우 크롬에서 **옆으로 누운
             //   막대**로 그려진다(실측 스크린샷으로 확인). 붙이면 제대로 된 연필이 된다.
             " onclick=\"window.__ssRenWork(event,'" + esc(w.work_id) + "')\">✏️</span>" +
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
      // ★다시 그릴 때는 **기존 블록을 갈아끼운다**(2026-08-06 __ssRefreshWorks 추가).
      //   그냥 삽입하면 '내 작업' 목록이 통째로 두 벌 쌓인다. 위 주석의 "nav 통째 재파싱 금지"는
      //   그대로 지킨다 — 건드리는 건 .ss-works 하나뿐이라 nav의 다른 자식·scrollLeft는 무사하다.
      var old = nav.querySelector(".ss-works");
      if (old) { nav.replaceChild(wrap, old); return; }
      var toggle = nav.querySelector(".ss-toggle");
      if (toggle) nav.insertBefore(wrap, toggle); else nav.appendChild(wrap);
    }).catch(function () {});   // 서버가 죽어도 네비게이션은 살아 있어야 한다
  }
  // 작업 목록 다시 그리기(2026-08-06 사장님 제보 "따로 만들기 눌러도 내 작업에 추가가 안 된다").
  // mountWorks는 페이지 로드 때 딱 한 번 돈다 — 화면 안에서 작업이 새로 생기는 흐름
  // ('따로 만들기'가 그렇다)에는 다시 그릴 손잡이가 없어 새로고침 전까지 목록이 옛것이었다.
  window.__ssRefreshWorks = function (curWid) { try { mountWorks(curWid); } catch (e) {} };

  // ── 유료게이트(2026-07-19): /api/me 등급으로 UI를 잠근다. sidebar.js는 6개 페이지 공유라
  //    여기 한 곳이면 전 페이지에 체험배너·🔒메뉴·만료안내가 걸린다. ──
  var _pw = { level: "full", contact: {} };
  // opts.title/opts.body가 오면 그 사유로 띄운다. 기본은 '체험 만료' 안내.
  // ★402는 사유가 둘이다 — 등급부족(미들웨어)과 **포인트 부족**(_charge_or_402).
  //   둘을 같은 문구로 띄우면 오진한다: 2026-08-20 체험 계정이 등급 full인데 잔액 0이라
  //   402가 났는데 화면은 "무료 체험이 끝났어요"였다 → "체험 부여가 연동 안 됐다"로 읽혔다.
  function _pwModal(opts) {
    opts = opts || {};
    var ex = document.getElementById("ss-pw-modal");
    if (ex) ex.remove();   // 사유가 다를 수 있으니 다시 그린다
    var k = _pw.contact.kakao || "", ph = _pw.contact.phone || "";
    var m = document.createElement("div");
    m.id = "ss-pw-modal";
    m.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.72);display:flex;align-items:center;justify-content:center;font-family:'Malgun Gothic',system-ui,sans-serif";
    m.innerHTML = '<div style="background:#16161c;border:1px solid #2a2a30;border-radius:16px;padding:28px 26px;max-width:340px;text-align:center;color:#e8e8ea">' +
      '<div style="font-size:40px">🔒</div>' +
      '<div style="font-size:18px;font-weight:800;margin:10px 0 6px">' + escHtml(opts.title || "무료 체험이 끝났어요") + '</div>' +
      '<div style="font-size:14px;color:#b8b8c0;line-height:1.6">' +
        // 줄바꿈(\n)은 <br>로 — escHtml 먼저 하고 바꾼다(순서 반대면 태그가 escape된다).
        (opts.body ? escHtml(opts.body).replace(/\n/g, "<br>")
                   : '이 기능은 결제하시면 계속 쓸 수 있어요.<br>담아둔 영상·자료는 <b>그대로 보존</b>돼요.') + '</div>' +
      // 결제 문의처 — 키 등록 안내처럼 결제와 무관한 사유에선 숨긴다(hideContact).
      (opts.hideContact ? "" :
        '<div style="margin-top:14px;font-size:14px;color:#7db4ff">' +
          (k ? "카톡: " + escHtml(k) + "<br>" : "") +
          (ph ? "전화: " + escHtml(ph) : "") +
          (!k && !ph ? "결제를 원하시면 안내받으신 판매 채널로 문의해 주세요." : "") +
        "</div>") +
      // ★사유별 바로가기(2026-09-01) — 키 등록처럼 '지금 할 일'이 결제가 아닌 경우,
      //   그리로 보내는 버튼을 결제 CTA **대신** 띄운다.
      (opts.link
        ? '<div style="margin-top:18px"><a href="' + escHtml(opts.link) + '"' +
          (/^https?:\/\//.test(opts.link) ? ' target="_blank" rel="noopener"' : "") +
          ' style="display:block;background:linear-gradient(135deg,#6ff0d6,#1f9e7a);color:#08110e;' +
          'border-radius:10px;padding:13px 20px;font-weight:800;font-size:15px;text-decoration:none">' +
          escHtml(opts.linkText || "바로가기") + "</a></div>"
        : "") +
      // 결제로 가는 길(2026-08-23). 예전엔 '카톡 문의'만 있어서, 계좌를 넣어놔도
      // 기존 회원은 결제 안내 화면으로 갈 방법이 아예 없었다(사장님이 일일이 카톡으로
      // 계좌를 알려줘야 했다). 주소·문구는 서버(/api/me pay_cta)가 정한 것을 그대로 쓴다.
      (!opts.link && _pw.cta && _pw.cta.href
        ? '<div style="margin-top:18px"><a id="ss-pw-pay" href="' + escHtml(_pw.cta.href) + '"' +
          (/^https?:\/\//.test(_pw.cta.href) ? ' target="_blank" rel="noopener"' : "") +
          ' style="display:block;background:linear-gradient(135deg,#6ff0d6,#1f9e7a);color:#08110e;' +
          'border-radius:10px;padding:13px 20px;font-weight:800;font-size:15px;text-decoration:none">' +
          escHtml(_pw.cta.label || "💳 결제 안내") + "</a></div>"
        : "") +
      '<div style="margin-top:' + ((opts.link || (_pw.cta && _pw.cta.href)) ? "10px" : "18px") + '"><button id="ss-pw-close" style="background:' +
      ((opts.link || (_pw.cta && _pw.cta.href)) ? "transparent;color:#8a8a92;border:1px solid #2a2a30" : "#4f9dfa;color:#111;border:0") +
      ';border-radius:8px;padding:10px 22px;font-weight:800;font-size:14px;cursor:pointer">' +
      escHtml(opts.closeLabel || "닫기") + "</button></div>" +
      // ★언제 뜬 안내인지 남긴다(2026-09-01 사장님 "시간을 표시해줘 팝업에도").
      //   화면을 캡처해 보내주실 때 시각이 같이 찍혀야 원인을 찾을 수 있다.
      '<div style="margin-top:12px;font-size:11.5px;color:#6a6a72">' +
        escHtml(new Date().toLocaleString("ko-KR", {month:"2-digit", day:"2-digit",
          hour:"2-digit", minute:"2-digit", hour12:false})) + "</div>" +
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
    // 관리자면 사이드바의 admin 전용 항목(레퍼런스 채널 관리 등)을 노출.
    if (admin) document.querySelectorAll(".ss-admin-only").forEach(function (e) { e.style.display = ""; });
    var email = escHtml(d.email || "");
    var initial = escHtml((d.email || "?").trim().charAt(0).toUpperCase() || "?");
    var tier, tierColor, sub;
    if (admin) { tier = "관리자"; tierColor = "#ffd97a"; sub = "전 기능 · 무제한"; }
    else if (d.plan === "pro") { tier = "프로"; tierColor = "#6ff0d6"; sub = "전 기능 이용중"; }
    else if (d.level === "pending") { tier = "승인대기"; tierColor = "#ffa94d"; sub = "승인 후 이용 가능해요"; }
    else if (typeof d.days_left === "number" && d.days_left > 0) { tier = "체험 D-" + d.days_left; tierColor = "#7db4ff";
      // 체험판(plan="trial")은 처음부터 랭킹전용이다 — 옛 문구("만료 후엔 랭킹만")는
      // 지금 다 쓸 수 있다는 뜻으로 읽혀 오해를 준다.
      sub = (d.plan === "trial") ? "랭킹·즐겨찾기·렌즈 10회/일" : "만료 후엔 랭킹만 열려요"; }
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
        // ★새 탭(target=_blank)으로 열지 않는다(2026-08-24 사장님 "주소창 없이 따로 뜬다").
        //   레퍼런스 랭킹 등 다른 메뉴처럼 **같은 창에서** 이어서 열려야 사이드바가
        //   유지되고 뒤로가기도 자연스럽다.
        (admin ? '<a href="/admin" class="ss-acct-link wide" style="color:#ffd97a;border-color:#5a4a1e">🔐 관리페이지</a>' : '') +
        '<a href="/settings" class="ss-acct-link">👤 마이페이지</a>' +
        '<a href="#" class="ss-acct-link" onclick="window.__ssLogout();return false">↩ 로그아웃</a></div>';
    // 모바일 전용 여는 버튼(2026-08-26) — 가로띠엔 카드를 펼칠 자리가 없다.
    //   아바타+등급만 띄우고, 누르면 위 카드가 시트로 내려온다.
    var mbtn = document.createElement("button");
    mbtn.className = "ss-acct-mbtn"; mbtn.id = "ss-acct-mbtn";
    mbtn.setAttribute("aria-label", "내 계정 · 오늘 사용량");
    mbtn.innerHTML = '<span class="ss-acct-av">' + initial + "</span>" +
      '<span class="ss-acct-mtier" style="color:' + tierColor + '">' + escHtml(tier) + "</span>" +
      '<span class="ss-acct-mcar">▼</span>';
    mbtn.onclick = function (e) { e.stopPropagation(); window.__ssAcctToggle(); };

    var h1 = nav.querySelector("h1");
    var after = (h1 && h1.nextSibling) ? h1.nextSibling : nav.firstChild;
    if (after) { nav.insertBefore(mbtn, after); nav.insertBefore(card, after); }
    else { nav.appendChild(mbtn); nav.appendChild(card); }
  }
  // 모바일 계정 시트 열고닫기. 가로띠 바로 아래에 붙도록 top을 그때그때 잰다
  // (가로띠 높이가 페이지마다 다르다 — 상수로 박으면 어긋난다).
  window.__ssAcctToggle = function (force) {
    var c = document.getElementById("ss-acct");
    if (!c || !c.classList) return;
    var open = (force === false) ? false : (force === true ? true : !c.classList.contains("ss-open"));
    if (open) {
      var nav = document.querySelector(".ss-nav");
      if (nav && nav.getBoundingClientRect) c.style.top = (nav.getBoundingClientRect().bottom + 6) + "px";
      c.classList.add("ss-open");
    } else {
      c.classList.remove("ss-open");
    }
    var car = document.querySelector("#ss-acct-mbtn .ss-acct-mcar");
    if (car) car.textContent = open ? "▲" : "▼";
  };
  // 바깥을 누르면 닫는다 — 시트가 화면을 덮은 채 남으면 앱이 멈춘 것처럼 보인다.
  if (document.addEventListener) {
    document.addEventListener("click", function (e) {
      var c = document.getElementById("ss-acct");
      if (!c || !c.classList || !c.classList.contains("ss-open")) return;
      if (c.contains && c.contains(e.target)) return;
      var b = document.getElementById("ss-acct-mbtn");
      if (b && b.contains && b.contains(e.target)) return;
      window.__ssAcctToggle(false);
    });
  }
  function initPaywall() {
    fetch("/api/me").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d) return;
      _pw.level = d.level; _pw.contact = d.contact || {};
      _pw.cta = d.pay_cta || null;
      _accountCard(d);   // 로고 아래 계정 패널
      if (d.level === "ranking_only") _pwLockSidebar();
      else if (typeof d.days_left === "number" && d.days_left >= 0 && d.plan !== "pro") _pwBanner(d.days_left);
      _payPrompt(d);     // 미결제 회원에게 결제 안내 팝업(하루 1회)
    }).catch(function () {});
  }

  // ── 결제 안내 팝업 (2026-08-23, 사장님 요청) ──────────────────────
  // 무료·체험 회원이 로그인하면 하루 1회 결제 안내를 띄운다.
  // ★안 뜨는 조건은 **등급으로만** 판정한다 — 사장님이 입금을 확인하고 승인하면
  //   plan이 pro가 되고, 그 순간부터 자동으로 안 뜬다. 별도 '봤음' 처리가 필요 없다
  //   (플래그를 따로 두면 승인했는데도 계속 뜨는 사고가 난다).
  // 승인대기(pending)는 애초에 이 화면을 못 본다 — 서버가 전용 안내화면을 준다.
  var _PAY_SEEN_KEY = "ss_pay_prompt_day";
  function _payPrompt(d) {
    if (!d || d.is_admin || d.plan === "pro") return;   // 결제한 사람·관리자에겐 안 뜬다
    if (!(_pw.cta && _pw.cta.href)) return;             // 결제 안내가 준비 안 됐으면 조용히 넘긴다
    var today = new Date().toISOString().slice(0, 10);  // YYYY-MM-DD
    try { if (localStorage.getItem(_PAY_SEEN_KEY) === today) return; } catch (e) {}
    try { localStorage.setItem(_PAY_SEEN_KEY, today); } catch (e) {}
    setTimeout(function () {
      _pwModal({
        title: "가입 신청 감사합니다 🙏",
        body: "숏템메이커 1기 · 1년 이용권 770,000원\n"
            + "아래에서 결제 안내를 확인하실 수 있어요.\n"
            + "입금 후 알려주시면 바로 열어드립니다.",
        closeLabel: "나중에"
      });
    }, 900);   // 화면이 다 그려진 뒤에 띄운다(로딩 중 겹쳐 보이지 않게)
  }
  // 유료 API가 402(등급부족)를 주면 만료 안내 모달 — 페이지 내 어떤 유료버튼이든 공통 처리.
  //
  // ★모달은 **사장님이 뭔가를 눌러서 난 402**에만 뜬다(2026-08-21 근본 수정).
  //   실사고: 체험 D-7(사용량 0/10)인 랭킹 전용 계정이 랭킹 페이지를 열자마자
  //   "무료 체험이 끝났어요"를 봤다. 아무것도 안 눌렀는데 떴다 — 페이지가 로드되며
  //   스스로 부르는 배경 호출들이 402를 받았기 때문이다(서버 실측, 한 번의 접속에서
  //   /api/produce/works · /api/admin/pending · /api/prune/removed · /api/discover/added
  //   4개가 동시에 402). 이 계정 등급에서 그 API들이 402인 것 자체는 **정상**이다.
  //   틀린 건 "402면 무조건 모달"이라는 판정이었다.
  //
  //   ⚠️ URL 목록으로 거르지 않는다. 위 4개는 오늘 걸린 것일 뿐이고, 배경 호출은
  //      페이지마다 계속 늘어난다(index.html·discover.html에도 이미 있다) — 목록은
  //      반드시 썩는다(CLAUDE.md: 손 관리 목록은 이미 3번 썩었다). 대신 **가른다**:
  //      사용자의 조작에서 비롯됐는가. 배경 호출은 정의상 아무도 안 누른 순간에 난다.
  //
  //   판정은 여기 한 곳에서만 한다(0순위-B). 잠긴 메뉴를 눌렀을 때 뜨는 모달은
  //   _pwLockSidebar가 __ssShowPaywall을 직접 부르므로 이 규칙과 무관하게 그대로 산다.
  // 402의 **사유는 서버가 정한다**(2026-08-21). 화면이 사유를 다시 판단하면 어긋난다
  // (0순위-B). 실사고: 체험판 계정이 마감일 8/28로 멀쩡히 남아 있는데 잠긴 기능을 누를
  // 때마다 "무료 체험이 끝났어요"를 봤다 — 서버는 정확히 "유료 기능이에요"라고 보냈는데
  // 화면이 그 문장을 버리고 만료 문구를 재사용한 탓이다.
  //
  // ★체험판(plan=trial)은 기간과 무관하게 랭킹 전용이다(app.py access_level, 2026-08-21
  //   사장님 확정) — 즉 '막혔다'와 '끝났다'는 애초에 다른 말이다. 섞으면 사장님도
  //   고객도 "결제했는데 왜 막히지 / 체험 중인데 왜 끝났대"로 읽는다.
  function _pwReason(d) {
    var msg = (d && d.error) || "";
    var lvl = (d && d.level) || "";
    // ★내 API 키가 없어 막힌 경우(2026-09-01 사장님 확정 "v메이크랑 tts는 없으면 못하게 막아").
    //   이건 결제 문제가 **아니라** 키 등록 문제라 처방이 다르다 — 여기서 안 가르면
    //   기본 분기로 떨어져 결제 버튼이 뜨고, 회원은 등록하러 갈 길을 못 찾는다.
    if (d && d.error_code === "need_own_key") {
      return { title: "내 API 키가 필요해요", body: msg,
               link: (d.settings_url || "/settings#keys"),
               linkText: "🔑 API 키 등록하러 가기",
               hideContact: true };          // 결제 문의처를 띄우지 않는다(결제 문제가 아니다)
    }
    if (/포인트/.test(msg)) return { title: "포인트가 부족해요", body: msg };
    if (lvl === "ranking_only") {
      return { title: "체험판에서는 잠긴 기능이에요",
               body: (msg || "유료 기능이에요.") +
                     " 체험 기간은 그대로 남아 있고, 레퍼런스 랭킹은 계속 쓰실 수 있어요." };
    }
    // 사유를 모르면 서버 문장이라도 그대로 보여준다. 기본 만료 문구는 마지막 수단이다.
    return msg ? { body: msg } : {};
  }

  var _lastGesture = 0;
  ["pointerdown", "keydown", "click", "submit"].forEach(function (ev) {
    // capture 단계 — 페이지 핸들러가 stopPropagation을 걸어도 우리는 먼저 본다.
    window.addEventListener(ev, function () { _lastGesture = Date.now(); }, true);
  });
  // 조작 → 요청 사이에 허용할 간격. 누른 뒤 곧바로 나가는 요청만 '사용자 것'으로 본다.
  // 8초·30초로 도는 폴러는 이 창을 넘겨 자연히 배제된다(폴러 목록을 관리할 필요가 없다).
  var _GESTURE_MS = 3000;
  var _origFetch = window.fetch;
  window.fetch = function () {
    // ★판정 시각은 **응답이 아니라 요청**이다. 느린 API가 5초 뒤에 402를 줘도,
    //   누르고 나간 요청이면 사장님에겐 방금 누른 그 버튼의 결과다.
    var byUser = (Date.now() - _lastGesture) < _GESTURE_MS;
    // ★url은 여기서 붙잡는다 — 아래 then 안의 arguments는 (resp)라 호출 주소가 아니다.
    var _reqUrl = arguments[0];
    return _origFetch.apply(this, arguments).then(function (resp) {
      if (resp && resp.status === 402) {
        if (!byUser) {
          // 배경 호출의 402 — 정상 동작이다. 조용히 넘기되 흔적은 남긴다
          // (조용히 삼키면 다음에 "왜 안 되지"가 된다).
          try { console.debug("[paywall] 배경 호출 402 — 모달 생략:", _reqUrl); } catch (e) {}
          return resp;
        }
        // 응답 본문을 복제해서 읽는다(원본은 호출부가 그대로 쓴다).
        try {
          resp.clone().json().then(function (d) { _pwModal(_pwReason(d)); })
                             .catch(function () { _pwModal(); });
        } catch (e) { try { _pwModal(); } catch (e2) {} }
      }
      return resp;
    });
  };

  // ── 새 회원 가입 알림 — 관리자 페이지 어디서나 '띠링' + 팝업 (2026-07-24) ──
  // /api/admin/pending 을 폴링한다. 관리자만 200 → 폴러 유지, 비관리자는 첫 응답이 비-200이라
  // 조용히 꺼진다(부하·노출 없음). 새 가입(newest_id 증가)이 감지되면 소리+토스트.
  var _SS_SEEN_KEY = "ss_signup_last_seen";     // 마지막으로 본 최신 가입 id(localStorage) — 새로고침 넘어 유지
  var _SS_BUG_SEEN_KEY = "ss_bug_last_seen";    // 오류 신고도 같은 방식(2026-08-25)
  var _ssAudioCtx = null;

  function _ssDing() {
    // Web Audio로 '띠링띠링' 2연음 — 오디오 파일 없이 생성. 자동재생 정책에 막히면 조용히 실패(토스트는 뜸).
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      if (!_ssAudioCtx) _ssAudioCtx = new AC();
      if (_ssAudioCtx.state === "suspended") { try { _ssAudioCtx.resume(); } catch (e) {} }
      var t0 = _ssAudioCtx.currentTime;
      [0, 0.18].forEach(function (off) {            // 두 번 '띠링'
        var o = _ssAudioCtx.createOscillator(), g = _ssAudioCtx.createGain();
        o.type = "sine";
        o.frequency.setValueAtTime(1318, t0 + off);          // E6
        o.frequency.setValueAtTime(1760, t0 + off + 0.08);   // A6 (살짝 올려 '띠링' 느낌)
        g.gain.setValueAtTime(0.0001, t0 + off);
        g.gain.exponentialRampToValueAtTime(0.25, t0 + off + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t0 + off + 0.16);
        o.connect(g); g.connect(_ssAudioCtx.destination);
        o.start(t0 + off); o.stop(t0 + off + 0.17);
      });
    } catch (e) {}
  }

  function _ssToast(newest, count) {
    if (!document.body) return;
    var box = document.getElementById("ssSignupToasts");
    if (!box) {
      box = document.createElement("div");
      box.id = "ssSignupToasts";
      box.style.cssText = "position:fixed;top:16px;right:16px;z-index:99999;display:flex;flex-direction:column;gap:10px;max-width:340px;font-family:system-ui,sans-serif";
      document.body.appendChild(box);
    }
    var who = (newest && (newest.name || newest.username)) || "새 회원";
    var sub = (newest && (newest.phone || newest.email)) || "";
    var card = document.createElement("div");
    card.style.cssText = "background:#0c1411;color:#e9f5ee;border:1px solid #1f6f4f;border-left:4px solid #2fd18a;border-radius:12px;padding:14px 16px;box-shadow:0 8px 28px rgba(0,0,0,.45);cursor:pointer;animation:ssSlideIn .25s ease";
    card.innerHTML =
      '<div style="font-size:13px;font-weight:800;color:#2fd18a;margin-bottom:4px">🆕 새 회원 가입 신청' +
      (count > 1 ? ' <span style="color:#9fd">· 대기 ' + count + '명</span>' : '') + '</div>' +
      '<div style="font-size:15px;font-weight:700">' + _ssEsc(who) + '</div>' +
      (sub ? '<div style="font-size:12px;color:#9db;margin-top:2px">' + _ssEsc(sub) + '</div>' : '') +
      '<div style="font-size:12px;color:#7fd6a8;margin-top:8px;font-weight:700">클릭 → 승인하러 가기 →</div>';
    card.onclick = function () { location.href = "/admin"; };
    box.appendChild(card);
    setTimeout(function () { try { card.style.transition = "opacity .4s"; card.style.opacity = "0"; setTimeout(function () { card.remove(); }, 400); } catch (e) {} }, 12000);
    if (!document.getElementById("ssSignupKf")) {
      var st = document.createElement("style"); st.id = "ssSignupKf";
      st.textContent = "@keyframes ssSlideIn{from{transform:translateX(30px);opacity:0}to{transform:none;opacity:1}}";
      document.head.appendChild(st);
    }
  }

  // 오류 신고 팝업(2026-08-25 사장님 "접수되면 가입·입금처럼 왼쪽 상단에 작은 팝업").
  // 가입 토스트와 **같은 자리·같은 소리**를 쓰되 주황으로 구분한다 — 새 배선을 만들지
  // 않는다(0순위-B). 클릭하면 관리페이지로 간다(가입 알림과 동일한 동작).
  function _ssBugToast(newest, count) {
    if (!document.body) return;
    var box = document.getElementById("ssSignupToasts");
    if (!box) {
      box = document.createElement("div");
      box.id = "ssSignupToasts";
      box.style.cssText = "position:fixed;top:16px;right:16px;z-index:99999;display:flex;flex-direction:column;gap:10px;max-width:340px;font-family:system-ui,sans-serif";
      document.body.appendChild(box);
    }
    var who = (newest && newest.customer_name) || "고객";
    var msg = (newest && newest.message) || "";
    var card = document.createElement("div");
    card.style.cssText = "background:#181008;color:#f6ecdf;border:1px solid #7a4a12;border-left:4px solid #f0912b;border-radius:12px;padding:14px 16px;box-shadow:0 8px 28px rgba(0,0,0,.45);cursor:pointer;animation:ssSlideIn .25s ease";
    card.innerHTML =
      '<div style="font-size:13px;font-weight:800;color:#f0912b;margin-bottom:4px">🐞 새 오류 신고' +
      (count > 1 ? ' <span style="color:#ffd9a8">· 미해결 ' + count + '건</span>' : '') + '</div>' +
      '<div style="font-size:15px;font-weight:700">' + _ssEsc(who) + '</div>' +
      (msg ? '<div style="font-size:12.5px;color:#d9c3a6;margin-top:3px;line-height:1.45">' +
             _ssEsc(msg.length > 60 ? msg.slice(0, 60) + "…" : msg) + '</div>' : '') +
      '<div style="font-size:12px;color:#f0b16b;margin-top:8px;font-weight:700">클릭 → 확인하러 가기 →</div>';
    card.onclick = function () { location.href = "/admin"; };
    box.appendChild(card);
    setTimeout(function () { try { card.style.transition = "opacity .4s"; card.style.opacity = "0"; setTimeout(function () { card.remove(); }, 400); } catch (e) {} }, 12000);
    if (!document.getElementById("ssSignupKf")) {
      var st = document.createElement("style"); st.id = "ssSignupKf";
      st.textContent = "@keyframes ssSlideIn{from{transform:translateX(30px);opacity:0}to{transform:none;opacity:1}}";
      document.head.appendChild(st);
    }
  }

  // 운영 사고 쪽지(2026-08-04). 가입 토스트와 같은 자리·같은 소리를 쓰되 빨간색으로 구분한다.
  // 08-03 인스타 통로 폐지 사고가 반나절 넘게 안 보였던 걸 막으려고 만든 통보 경로 —
  // 클릭하면 사라지지 않고 상세(원문)를 펼친다. 사고는 원문을 봐야 손을 쓴다.
  function _ssOpsToast(alert) {
    if (!document.body) return;
    var box = document.getElementById("ssSignupToasts");
    if (!box) {
      box = document.createElement("div");
      box.id = "ssSignupToasts";
      box.style.cssText = "position:fixed;top:16px;right:16px;z-index:99999;display:flex;flex-direction:column;gap:10px;max-width:340px;font-family:system-ui,sans-serif";
      document.body.appendChild(box);
    }
    var card = document.createElement("div");
    // ★등급별 색·문구(2026-09-04 사장님 "다 큰 사고처럼 보이고 조치가 되는지 모르겠다").
    //   고객영향=빨강(즉시) / 운영주의=주황(자동 우회됨) / 정보=회색. 자동조치·할 일을 함께 보여준다.
    var g = alert.grade || "운영주의";
    var th = (g === "고객영향")
      ? { bg: "#160c0c", fg: "#f7e9e9", bd: "#7a2b2b", bar: "#ff5a5a", lc: "#ff8080", label: "🚨 고객 영향 사고 — 지금 확인" }
      : (g === "정보")
        ? { bg: "#0f1412", fg: "#e6efe9", bd: "#2a3a33", bar: "#8fa1a0", lc: "#b7c5c0", label: "ℹ️ 알림" }
        : { bg: "#171205", fg: "#f6efe0", bd: "#6a4a10", bar: "#f5a623", lc: "#ffc85c", label: "⚠️ 운영 주의 — 자동 우회됨, 서비스 정상" };
    card.style.cssText = "background:" + th.bg + ";color:" + th.fg + ";border:1px solid " + th.bd + ";border-left:4px solid " + th.bar + ";border-radius:12px;padding:14px 16px;box-shadow:0 8px 28px rgba(0,0,0,.45);animation:ssSlideIn .25s ease";
    card.innerHTML =
      '<div style="font-size:13px;font-weight:800;color:' + th.lc + ';margin-bottom:4px">' + th.label + '</div>' +
      '<div style="font-size:14px;font-weight:700;line-height:1.35">' + _ssEsc(alert.title || "") + '</div>' +
      (alert.auto ? '<div style="margin-top:6px;font-size:12px;opacity:.9">✅ 자동 조치: ' + _ssEsc(alert.auto) + '</div>' : '') +
      (alert.todo ? '<div style="margin-top:4px;font-size:12px;opacity:.9">👉 할 일: ' + _ssEsc(alert.todo) + '</div>' : '') +
      (alert.detail
        ? '<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px;color:#ffb3b3">상세 사유 보기</summary>' +
          '<div style="margin-top:6px;font-size:11px;color:#e0c0c0;white-space:pre-wrap;word-break:break-all;max-height:180px;overflow:auto">' +
          _ssEsc(alert.detail) + '</div></details>'
        : '');
    box.appendChild(card);
    // 사고 알림은 자동으로 안 사라진다(가입 토스트와 다르게) — 사람이 보고 닫아야 한다.
    var close = document.createElement("div");
    close.textContent = "닫기";
    close.style.cssText = "margin-top:8px;font-size:12px;color:#ffb3b3;cursor:pointer;font-weight:700";
    close.onclick = function () {
      card.remove();
      try { (window.fetch || fetch)("/api/admin/alerts/read", { method: "POST" }); } catch (e) {}
    };
    card.appendChild(close);
  }

  function _ssEsc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function initSignupAlert() {
    // 브라우저 밖(테스트 하네스 등)에선 조용히 꺼진다 — localStorage·fetch 없으면 no-op(스크립트 안 깬다).
    if (typeof window === "undefined" || !window.localStorage) return;
    var _f = window.fetch || (typeof fetch === "function" ? fetch : null);
    if (!_f) return;
    var firstRun = true;
    function tick() {
      _f("/api/admin/pending", { headers: { "Accept": "application/json" } })
        .then(function (r) { if (!r.ok) throw new Error("not-admin"); return r.json(); })
        .then(function (d) {
          if (!d || !d.ok) return;
          var newestId = d.newest_id || 0;
          var seen = parseInt(window.localStorage.getItem(_SS_SEEN_KEY) || "0", 10) || 0;
          if (firstRun && seen === 0) {
            // 첫 방문(기록 없음): 기존 대기자로 시끄럽게 울리지 않는다. 기준선만 잡는다.
            window.localStorage.setItem(_SS_SEEN_KEY, String(newestId));
          } else if (newestId > seen) {
            _ssDing();
            _ssToast(d.newest, d.count);
            window.localStorage.setItem(_SS_SEEN_KEY, String(newestId));
          }
          // 운영 사고 쪽지(2026-08-04) — 안 읽은 것만, 한 번 띄운 건 다시 안 띄운다.
          try {
            var shown = window.__ssOpsShown || (window.__ssOpsShown = {});
            (d.alerts || []).forEach(function (a) {
              if (!a || a.read || a.resolved || shown[a.id]) return;   // 해결된 건 다시 안 띄운다
              shown[a.id] = 1;
              _ssDing();
              _ssOpsToast(a);
            });
          } catch (e) { /* 사고 알림 실패가 승인 폴러를 죽이면 안 된다 */ }
          // 오류 신고(2026-08-25) — 가입과 똑같은 규칙: 첫 방문엔 기준선만 잡고
          // 조용히 있는다(기존 신고로 시끄럽게 울리지 않는다).
          try {
            var bugId = d.bug_newest_id || 0;
            var bugSeen = parseInt(window.localStorage.getItem(_SS_BUG_SEEN_KEY) || "0", 10) || 0;
            if (firstRun && bugSeen === 0) {
              window.localStorage.setItem(_SS_BUG_SEEN_KEY, String(bugId));
            } else if (bugId > bugSeen) {
              _ssDing();
              _ssBugToast(d.bug_newest, d.bug_open);
              window.localStorage.setItem(_SS_BUG_SEEN_KEY, String(bugId));
            }
          } catch (e) { /* 신고 알림 실패가 승인 폴러를 죽이면 안 된다 */ }
          firstRun = false;
          setTimeout(tick, 25000);                  // 관리자면 25초마다 계속
        })
        .catch(function () { /* 비관리자/에러 → 폴러 정지(재시도 안 함) */ });
    }
    tick();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
    document.addEventListener("DOMContentLoaded", __ssPaintTheme);
    document.addEventListener("DOMContentLoaded", mountWorks);
    document.addEventListener("DOMContentLoaded", initPaywall);
    document.addEventListener("DOMContentLoaded", initSignupAlert);
  } else {
    mount();
    __ssPaintTheme();
    mountWorks();
    initPaywall();
    initSignupAlert();
  }
})();

/* ── 오류 신고 + 답장(쪽지) — 2026-08-24 사장님 지시 ─────────────────────────
   "오류신고 버튼 만들기 / 내 관리페이지에 보이기 / 바로 버그 수정하고 쪽지를 남겨줄 수 있나"

   ★고객에게 job_id·URL·콘솔오류를 물어보면 못 받는다. 실제로 김만기님 제작 4회 전패를
     화면 캡처만으로는 못 찾았고 서버 DB를 뒤져서야 원인을 알았다(일레븐랩스 키 대신 키 ID).
     그래서 고객은 **한 줄만 쓰고**, 진단 정보는 화면이 스스로 담아 보낸다.
   ★자바스크립트 오류도 몰래 모아둔다 — "화면이 하얘요"의 진짜 원인이 대개 여기 있다. */
(function () {
  var ERRS = [];
  window.addEventListener("error", function (e) {
    ERRS.push(String((e && e.message) || e) + " @" + ((e && e.filename) || "?") + ":" + ((e && e.lineno) || 0));
    if (ERRS.length > 20) ERRS.shift();
  });
  window.addEventListener("unhandledrejection", function (e) {
    ERRS.push("promise: " + String((e && e.reason && e.reason.message) || (e && e.reason) || e));
    if (ERRS.length > 20) ERRS.shift();
  });

  function q(name) {
    var m = new RegExp("[?&]" + name + "=([^&]+)").exec(location.search);
    return m ? decodeURIComponent(m[1]) : "";
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function css() {
    if (document.getElementById("ssBugCss")) return;
    var st = document.createElement("style");
    st.id = "ssBugCss";
    st.textContent =
      ".ssbug-back{position:fixed;inset:0;background:rgba(0,0,0,.62);z-index:99999;display:flex;" +
      "align-items:center;justify-content:center;padding:16px}" +
      ".ssbug{background:#141a1a;border:1px solid #2b3a3a;border-radius:14px;max-width:560px;width:100%;" +
      "padding:24px;color:#e8eaed;font-size:16px;line-height:1.65;box-shadow:0 12px 40px rgba(0,0,0,.5);" +
      "max-height:92vh;overflow:auto}" +
      ".ssbug h3{margin:0 0 8px;font-size:21px;color:#6ff0d6}" +
      ".ssbug p.sub{margin:0 0 16px;color:#9db2b2;font-size:15px}" +
      ".ssbug textarea{width:100%;box-sizing:border-box;min-height:120px;background:#0e1414;color:#e8eaed;" +
      "border:1px solid #2b3a3a;border-radius:10px;padding:13px;font:inherit;font-size:16.5px;resize:vertical}" +
      ".ssbug .info{margin:12px 0 0;font-size:14px;color:#9db2b2;background:#0e1414;border-radius:8px;padding:11px 13px}" +
      ".ssbug .info b{color:#c7d2d2;font-weight:600}" +
      ".ssbug .drop{margin-top:12px;border:1px dashed #35494a;border-radius:10px;padding:14px;text-align:center;" +
      "font-size:14.5px;color:#9db2b2;background:#0e1414}" +
      ".ssbug .drop button{background:#1e2b2b;color:#cfe3e3;border:0;border-radius:9px;padding:9px 15px;" +
      "font:inherit;font-size:14.5px;font-weight:600;cursor:pointer;flex:none}" +
      ".ssbug .row{display:flex;gap:10px;margin-top:18px}" +
      ".ssbug button{flex:1;padding:14px;border-radius:10px;border:0;font:inherit;font-size:16.5px;" +
      "font-weight:700;cursor:pointer}" +
      ".ssbug .ok{background:#6ff0d6;color:#062b25}.ssbug .no{background:#222c2c;color:#c7d2d2}" +
      ".ssbug .msg{margin-top:14px;font-size:15.5px}";
    document.head.appendChild(st);
  }

  /* 지금 화면이 무엇을 하고 있었나 — 고객이 몰라도 되는 것들을 화면이 대신 안다. */
  function context() {
    var job = "";
    try { job = (window.JOB_ID || (window.MIX && window.MIX.job_id) || ""); } catch (e) { job = ""; }
    var step = "";
    try {
      var on = document.querySelector(".step.active, .stepper .active, [data-step].active");
      step = on ? (on.getAttribute("data-step") || (on.textContent || "").trim().slice(0, 30)) : "";
    } catch (e) { step = ""; }
    return {
      page_url: location.href.slice(0, 500),
      work_id: q("work"),
      job_id: String(job || ""),
      step: step,
      console: ERRS.slice(-20)
    };
  }


  /* ★2026-08-24 사장님: "지금 페이지 url을 첨부해야하는거 아닌가? 사진? 링크?
        그 문제 장면도 같이 해줘야 판단이 쉽지 / 글자 잘보이게"
     - URL은 원래도 자동으로 보내고 있었지만 **고객에게 안 보였다** → 눈에 보이게 적는다.
     - 화면 사진을 붙일 수 있게 한다: [사진 고르기] · Ctrl+V 붙여넣기 · 끌어다 놓기 셋 다.
       윈도우는 Win+Shift+S로 찍으면 클립보드에 들어가므로 **붙여넣기가 가장 빠른 길**이다.
     - 글자를 키운다(시니어 타깃) — 본문 16px, 입력칸 16.5px. */
  var SHOT = null;                       /* data:image/... 한 장 */

  function shrink(file, cb) {
    /* 화면 사진은 대개 2~4MB다. 1280px·JPEG로 줄여 보낸다 — 판독에는 충분하고
       업로드가 빠르며 서버 6MB 상한에도 안 걸린다. 실패하면 원본을 그대로 쓴다. */
    var fr = new FileReader();
    fr.onload = function () {
      var img = new Image();
      img.onload = function () {
        try {
          var max = 1280, w = img.width, h = img.height;
          var r = Math.min(1, max / Math.max(w, h));
          var cv = document.createElement("canvas");
          cv.width = Math.round(w * r); cv.height = Math.round(h * r);
          cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
          cb(cv.toDataURL("image/jpeg", 0.8));
        } catch (e) { cb(fr.result); }
      };
      img.onerror = function () { cb(fr.result); };
      img.src = fr.result;
    };
    fr.onerror = function () { cb(null); };
    fr.readAsDataURL(file);
  }

  function setShot(file) {
    if (!file || !/^image\//.test(file.type)) return;
    var box = document.getElementById("ssBugShot");
    if (box) box.innerHTML = '<span style="color:#8aa0a0">사진 줄이는 중…</span>';
    shrink(file, function (d) {
      SHOT = d;
      if (!box) return;
      box.innerHTML = d
        ? '<img src="' + d + '" style="max-width:100%;max-height:190px;border-radius:8px;' +
          'border:1px solid #2b3a3a">' +
          '<div style="margin-top:6px"><button type="button" id="ssShotDel" ' +
          'style="background:#2a2020;color:#ff9b9b;border:0;border-radius:8px;padding:7px 12px;' +
          'font:inherit;cursor:pointer">사진 빼기</button></div>'
        : '<span style="color:#ff9b9b">사진을 읽지 못했어요</span>';
      var del = document.getElementById("ssShotDel");
      if (del) del.onclick = function () { SHOT = null; box.innerHTML = ""; };
    });
  }

  /* ★🛒 쿠팡 상품 찾기 모달(2026-09-04 사장님 "쿠팡에 링크가 만들어지는 상품인지 검색 — 없는 상품이 많아서").
     영상을 만들기 **전에** 카드에서 바로 "이 제품이 쿠팡에 있나 → 내 링크"를 본다.
     한 곳(sidebar.js)에만 두고 페이지들은 버튼만 단다(0순위-B). 페이지 모달에 기대지 않는다. */
  /* ★_ssEsc는 다른 함수 안에 갇혀 있어 여기서 안 보인다(2026-09-04 라이브 실측: 클릭해도
     "_ssEsc is not defined"로 모달이 안 떴다). 이 블록 전용 이스케이프를 둔다. */
  function _cfEsc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  var _cfState = { kw: "", items: [], chips: [] };
  function _cfEl(id) { return document.getElementById(id); }
  function _cfClose() { var m = _cfEl("ssCoupangFind"); if (m) m.remove(); }
  function _cfRender(msg, msgColor) {
    var box = _cfEl("cfResults"); if (!box) return;
    var m = _cfEl("cfMsg"); if (m) { m.textContent = msg || ""; m.style.color = msgColor || "#8fa39a"; }
    var chips = _cfEl("cfChips");
    if (chips) chips.innerHTML = (_cfState.chips.length < 2) ? "" : _cfState.chips.map(function (c) {
      return '<button onclick="window.ssCoupangFind.search(decodeURIComponent(\'' + encodeURIComponent(c) + '\'))" style="padding:4px 10px;font-size:12px;border-radius:999px;border:1px solid ' + (c === _cfState.kw ? '#37e0bd' : '#1e2a24') + ';background:#0c1210;color:#e6efe9;cursor:pointer;margin:0 6px 6px 0">' + _cfEsc(c) + '</button>';
    }).join("");
    if (!_cfState.items.length) { box.innerHTML = ""; return; }
    box.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;max-height:52vh;overflow-y:auto">' +
      _cfState.items.map(function (it, i) {
        return '<div style="border:1px solid #1e2a24;border-radius:10px;padding:8px;background:#0c1210">' +
          '<img src="' + _cfEsc(it.image || "") + '" style="width:100%;aspect-ratio:1;object-fit:contain;border-radius:6px;background:#fff" onerror="this.style.visibility=\'hidden\'">' +
          '<div style="font-size:11px;line-height:1.35;margin-top:4px;max-height:44px;overflow:hidden" title="' + _cfEsc(it.name) + '">' + _cfEsc(it.name) + '</div>' +
          '<div style="font-size:12px;font-weight:700;margin-top:3px">' + _cfEsc(it.price || "") + (it.is_rocket ? ' <span style="font-size:10px;color:#5fe3d6">🚀로켓</span>' : '') + '</div>' +
          '<div id="cfLink' + i + '" onclick="window.ssCoupangFind.link(' + i + ')" title="누르면 복사" style="font-size:11px;color:#37e0bd;word-break:break-all;margin-top:4px;cursor:pointer;font-weight:700">' + (it.short_url ? '📋 ' + _cfEsc(it.short_url) : '') + '</div>' +
          '<div style="display:flex;gap:4px;margin-top:6px">' +
            '<button onclick="window.ssCoupangFind.link(' + i + ')" style="flex:1;padding:6px 4px;font-size:11px;border-radius:7px;border:1px solid #b8860b;background:linear-gradient(90deg,#3a2f0d,#2a2408);color:#ffd76b;cursor:pointer">🔗 내 링크</button>' +
            '<button onclick="window.open(\'' + _cfEsc(it.url) + '\',\'_blank\')" style="padding:6px 6px;font-size:11px;border-radius:7px;border:1px solid #1e2a24;background:#0f1512;color:#e6efe9;cursor:pointer">보기</button>' +
          '</div></div>';
      }).join("") + '</div>';
  }
  function _cfOpen(keyword, opts) {
    _cfClose();
    opts = opts || {};
    /* ★hint(사전 판독한 썸네일 제품명)는 검색어로 쓰지 않는다(2026-09-04 사장님 "바디필로우로 검색되는데
       대본엔 토닥인형") — 클릭하면 항상 근거 우선 판독(/api/coupang/identify)을 거친다. 판독이 캐시·근거로
       빠르게 끝나므로 체감 지연은 거의 없다. hint는 결과가 달라졌을 때 "썸네일 추정→대본 근거" 안내에만 쓴다. */
    _cfState = { kw: keyword || "", items: [], chips: [], sc: opts.shortcode || "", thumb: opts.thumbnail || "", hint: opts.hint || "" };
    var wrap = document.createElement("div");
    wrap.id = "ssCoupangFind";
    wrap.style.cssText = "position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;padding:16px";
    wrap.innerHTML = '<div style="background:#0f1512;color:#e6efe9;border:1px solid #1e2a24;border-radius:14px;width:min(900px,96vw);max-height:90vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.6)">' +
      '<div style="display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid #1e2a24"><b style="font-size:15px">🛒 쿠팡에 이 제품이 있나요?</b><span style="font-size:11px;color:#8fa39a">— 있으면 그 자리에서 내 추적 링크까지</span><span style="flex:1"></span><button onclick="window.ssCoupangFind.close()" style="background:none;border:none;color:#8fa39a;font-size:18px;cursor:pointer">✕</button></div>' +
      '<div style="padding:12px 14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap"><input id="cfQuery" value="' + _cfEsc(keyword || "") + '" placeholder="제품명(예: 의류 태깅건)" style="flex:1;min-width:200px;padding:9px 10px;border-radius:9px;border:1px solid #1e2a24;background:#0c1210;color:#e6efe9;font-size:13px" onkeydown="if(event.key===\'Enter\'){event.preventDefault();window.ssCoupangFind.search();}">' +
      '<button onclick="window.ssCoupangFind.search()" style="padding:9px 16px;border-radius:9px;border:none;background:linear-gradient(180deg,#37e0bd,#2bd4b0);color:#04120e;font-weight:800;cursor:pointer">찾기</button>' +
      (opts.shortcode ? '<button id="cfDeep" onclick="window.ssCoupangFind.deep()" title="영상 대본을 추출해 제품을 정확히 특정합니다(시간이 조금 걸립니다)" style="padding:9px 12px;border-radius:9px;border:1px solid #b8860b;background:linear-gradient(90deg,#3a2f0d,#2a2408);color:#ffd76b;font-weight:700;cursor:pointer">🎬 영상 보고 정확히</button>' : '') +
      '<a id="cfOut" href="#" target="_blank" rel="noopener" style="font-size:12px;color:#37e0bd">쿠팡에서 직접 ↗</a><span id="cfMsg" style="font-size:12px;color:#8fa39a;width:100%"></span><div id="cfChips" style="width:100%"></div></div>' +
      '<div id="cfResults" style="padding:0 14px 14px"></div></div>';
    wrap.addEventListener("click", function (e) { if (e.target === wrap) _cfClose(); });
    document.body.appendChild(wrap);
    if (keyword) _cfSearch(keyword);
    else if (_cfState.sc) _cfIdentify();          /* ★자동: 썸네일에서 제품을 알아내 바로 찾는다 */
    else { var q = _cfEl("cfQuery"); if (q) q.focus(); }
  }
  /* 숏템파워검색처럼 사람이 안 친다(2026-09-04 사장님) — 썸네일 → 제품명 → 첫 후보로 검색 → 링크. */
  /* 🎬 영상 보고 정확히 — 대본을 추출(기존 /api/extract_script, 캐시되면 무료)한 뒤 근거 우선 판독을 다시 돈다. */
  function _cfDeep() {
    if (!_cfState.sc) return;
    var b = _cfEl("cfDeep"); if (b) { b.disabled = true; b.textContent = "🎬 대본 추출 중…"; }
    _cfRender("🎬 영상 대본을 추출하는 중… (20~60초, 한 번 하면 다음부터는 바로)");
    fetch("/api/extract_script?shortcode=" + encodeURIComponent(_cfState.sc), { method: "POST" })
      .then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
      .then(function (d) {
        if (b) { b.disabled = false; b.textContent = "🎬 영상 보고 정확히"; }
        if (!d || !d.ok) { _cfRender("대본 추출 실패: " + ((d && d.error) || "") + " — 제품명을 직접 넣어 찾아보세요", "#ff8080"); return; }
        _cfIdentify();
      })
      .catch(function () { if (b) { b.disabled = false; b.textContent = "🎬 영상 보고 정확히"; } _cfRender("네트워크 오류", "#ff8080"); });
  }
  function _cfIdentify() {
    _cfRender("🔎 영상 근거(대본·캡션·썸네일)에서 제품을 알아내는 중… (3~8초)");
    fetch("/api/coupang/identify", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shortcode: _cfState.sc, thumbnail: _cfState.thumb }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.product) {
          _cfRender((d && d.error) || "제품을 특정하지 못했습니다 — 제품명을 직접 넣어 찾아보세요", "#ff8080");
          var q = _cfEl("cfQuery"); if (q) q.focus();
          return;
        }
        _cfState.chips = (d.queries || [d.product]).slice(0, 6);
        _cfState.basis = (d.basis || []).join("·");
        if (_cfState.hint && d.product && d.product !== _cfState.hint) _cfState.basis += " · 썸네일 추정 '" + _cfState.hint + "' 대신 근거로 특정";
        _cfSearch(_cfState.chips[0]);
      })
      .catch(function () { _cfRender("판독 중 네트워크 오류 — 제품명을 직접 넣어 찾아보세요", "#ff8080"); });
  }
  function _cfSearch(forced) {
    var q = (forced || (_cfEl("cfQuery") || {}).value || "").trim();
    if (!q) { _cfRender("제품명을 넣으세요", "#ff8080"); return; }
    _cfState.kw = q; var inp = _cfEl("cfQuery"); if (inp) inp.value = q;
    var out = _cfEl("cfOut"); if (out) out.href = "https://www.coupang.com/np/search?q=" + encodeURIComponent(q);
    _cfState.items = []; _cfRender("쿠팡에서 찾는 중…");
    fetch("/api/coupang/search?q=" + encodeURIComponent(q) + "&limit=10")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        _cfState.items = (d && d.items) || [];
        if (!_cfState.items.length) {
          _cfRender("❌ 쿠팡에 없습니다 — 이 검색어로는 링크를 만들 수 없어요. 다른 검색어 칩을 눌러 보거나 '쿠팡에서 직접'으로 확인하세요." + (d && d.notice ? " (" + d.notice + ")" : ""), "#ff8080");
          if (!_cfState.chips.length) _cfSuggest(q);
          return;
        }
        _cfRender(_cfState.items.length + "개 있음 — " + (d.source === "api_shared"
          ? "쿠팡에 있습니다. 🔗 내 링크를 누르면 상품 URL을 복사하고 파트너스 링크 생성 창을 엽니다(내 API 키를 등록하면 자동)"
          : (d.source === "api" ? "내 추적 링크를 만드는 중…" : "🔗 내 링크를 누르면 추적 링크가 만들어집니다 (내 파트너스 키를 등록하면 더 빠르고 정확합니다)")));
        if (d.source === "api") _cfAutoLinks();     /* 키 있는 회원: 카드 전부에 짧은 링크를 한 번에 */
        if (!_cfState.chips.length) _cfSuggest(q);
      })
      .catch(function () { _cfRender("네트워크 오류", "#ff8080"); });
  }
  function _cfSuggest(q) {
    /* 검색어 다듬기(제작소 8단계와 같은 API) — 서술형 제목을 살 만한 상품명 후보로 */
    fetch("/api/coupang/suggest", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target: q, script: "" }) })
      .then(function (r) { return r.json(); })
      .then(function (d) { var qs = (d && d.queries) || []; if (qs.length) { _cfState.chips = [q].concat(qs.filter(function (x) { return x && x !== q; })).slice(0, 6); _cfRender((_cfEl("cfMsg") || {}).textContent, (_cfEl("cfMsg") || {}).style ? _cfEl("cfMsg").style.color : ""); } })
      .catch(function () {});
  }
  /* 검색 결과 전부에 짧은 추적 링크를 **한 번의 호출로** 붙인다(2026-09-04 사장님 "누르면 링크까지").
     실패하면 카드의 🔗 내 링크 버튼이 그대로 남는다(단건 재시도). */
  function _cfAutoLinks() {
    var urls = _cfState.items.map(function (it) { return it.url; }).filter(Boolean);
    if (!urls.length) return;
    fetch("/api/coupang/deeplink", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ urls: urls }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var by = {}; ((d && d.links) || []).forEach(function (l) { if (l.shorten_url) by[l.url] = l.shorten_url; });
        var n = 0;
        _cfState.items.forEach(function (it) { if (by[it.url]) { it.short_url = by[it.url]; n++; } });
        var basis = _cfState.basis ? " (근거: " + _cfState.basis + ")" : "";
        _cfRender(n ? ("✅ 쿠팡에 있음 " + _cfState.items.length + "개 — 내 추적 링크 " + n + "개 준비됨. 카드의 링크를 누르면 복사됩니다" + basis) : ("✅ 쿠팡에 있음 " + _cfState.items.length + "개 — 🔗 내 링크를 누르면 추적 링크가 만들어집니다" + basis), n ? "#5fe3d6" : "");
      })
      .catch(function () { _cfRender(_cfState.items.length + "개 있음 — 🔗 내 링크를 누르면 추적 링크가 만들어집니다"); });
  }
  function _cfLink(i) {
    var it = _cfState.items[i]; if (!it) return;
    var cell = _cfEl("cfLink" + i);
    function done(url) {
      it.short_url = url; if (cell) cell.textContent = url;
      try { navigator.clipboard.writeText(url); } catch (e) {}
      _cfRender("링크를 복사했습니다: " + url, "#5fe3d6");
    }
    if (it.short_url) { done(it.short_url); return; }
    if (cell) cell.textContent = "만드는 중…";
    fetch("/api/coupang/deeplink", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: it.url }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok && d.shorten_url) { done(d.shorten_url); return; }
        if (it.partner_url) { done(it.partner_url); return; }   /* API 검색 카드엔 긴 추적 링크가 이미 있다 */
        if (d && d.need_key) {
          /* ★키 없는 회원(2026-09-04 사장님 판단): 남의 링크를 대신 걸지 않는다. 파트너스 웹에서 **본인 링크**를
             만들게 돕는다 — 상품 URL을 복사해 두고 링크 생성 화면을 연다(8단계 coupangMakeLink와 같은 방식).
             링크 생성은 파트너스 가입 즉시 되고, 15만원 실적이 쌓이면 API가 열려 그때부터 자동이 된다. */
          try { navigator.clipboard.writeText(it.url); } catch (e) {}
          window.open("https://partners.coupang.com/#affiliate/ws/link", "_blank");
          if (cell) cell.innerHTML = '상품 URL 복사됨 → 열린 파트너스 창에 붙여넣어 <b>내 링크</b>를 만드세요 · <a href="/settings#keys" style="color:#ffd76b">API 키 등록하면 자동 ↗</a>';
          _cfRender("상품 URL을 복사했습니다. 파트너스 '링크 생성' 창에 붙여넣으면 내 추적 링크가 나옵니다(가입 즉시 가능). 판매 15만원이 쌓여 API 키를 받으면 여기서 자동으로 만들어집니다.", "#ffd76b");
          return;
        }
        if (cell) cell.innerHTML = _cfEsc((d && d.error) || "실패");
      })
      .catch(function () { if (cell) cell.textContent = "네트워크 오류"; });
  }
  /* ★사전 판독(2026-09-04 사장님 "바로 뜨게"): 페이지가 카드를 그린 직후 부른다.
     보이는 카드의 shortcode·thumbnail을 모아 한 번에 판독 → 캐시. 판독된 제품명은 버튼에 바로
     박아 준다("🛒 택총 쿠팡검색") → 사장님이 누르기 전에 무엇인지 알고, 누르면 즉시 검색된다.
     같은 페이지에서 두 번 부르면 이미 처리한 shortcode는 건너뛴다. */
  var _cfWarmed = {};
  window.ssCoupangPrewarm = function (items) {
    var todo = (items || []).filter(function (it) { return it && it.shortcode && it.thumbnail && !_cfWarmed[it.shortcode]; }).slice(0, 60);
    if (!todo.length) return;
    todo.forEach(function (it) { _cfWarmed[it.shortcode] = 1; });
    fetch("/api/coupang/identify_batch", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: todo.map(function (it) { return { shortcode: it.shortcode, thumbnail: it.thumbnail, caption: (it.caption || "").slice(0, 2000) }; }) }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var pm = (d && d.products) || {};
        Object.keys(pm).forEach(function (sc) {
          var name = pm[sc]; if (!name) return;
          var btn = document.querySelector('.cp-btn[data-sc="' + sc + '"]');
          if (btn) { btn.textContent = "🛒 " + (name.length > 10 ? name.slice(0, 10) + "…" : name) + " 쿠팡검색"; btn.setAttribute("data-product", name); btn.title = "알아낸 제품: " + name + " — 누르면 쿠팡 검색과 내 추적 링크까지"; }
        });
      })
      .catch(function () {});
  };
  window.ssCoupangFind = function (keyword, opts) { _cfOpen(keyword, opts); };
  window.ssCoupangFind.search = _cfSearch;
  window.ssCoupangFind.link = _cfLink;
  window.ssCoupangFind.close = _cfClose;
  window.ssCoupangFind.deep = _cfDeep;

  window.ssOpenBugReport = function () {
    css();
    var back = document.createElement("div");
    back.className = "ssbug-back";
    SHOT = null;
    back.innerHTML =
      '<div class="ssbug" role="dialog" aria-modal="true">' +
        "<h3>🐞 오류 신고</h3>" +
        '<p class="sub">어떤 문제인지 한 줄만 적어주세요.<br>' +
          '<b style="color:#cfe3e3">문제가 보이는 화면 사진</b>을 같이 보내주시면 훨씬 빨리 찾습니다.</p>' +
        '<textarea id="ssBugText" placeholder="예) 5단계에서 영상 만들기를 누르면 계속 실패해요"></textarea>' +
        '<div class="drop" id="ssBugDrop">' +
          '📷 <b>화면 사진</b> — <button type="button" id="ssShotPick">사진 고르기</button>' +
          '<div style="margin-top:8px;font-size:13.5px;color:#7d8f8f">' +
            '캡처하신 뒤 <b>Ctrl+V</b>로 붙여넣거나 여기에 끌어다 놓으셔도 됩니다' +
            '<br>(윈도우는 <b>Win+Shift+S</b>, 맥은 <b>⌘⇧4</b>로 화면을 찍습니다)</div>' +
          '<input type="file" id="ssShotFile" accept="image/*" style="display:none">' +
          '<div id="ssBugShot" style="margin-top:10px"></div>' +
        "</div>" +
        // ★문구(2026-08-25 사장님): 무엇이 가고 **그 다음 무슨 일이 생기는지**까지 적는다.
        //   "따로 적으실 것 없습니다"만으론 고객이 '내 얘기가 어디로 갔나' 모른 채 끝난다
        //   — 실제로 사장님도 "URL을 붙여넣으라고 써야 하지 않나" 하고 되물었다(URL은
        //   context()가 page_url로 이미 보낸다). 답장은 쪽지로 간다(구현·실측 확인됨:
        //   reply_bug_report → my_bug_replies → 다음 접속 화면에 자동으로 뜬다).
        '<div class="info"><b>함께 보내지는 것</b><br>' +
          '지금 보고 계신 화면과 작업 정보가 숏템메이커 관리자에게 전송됩니다. ' +
          '확인 후 쪽지로 답변이 전송됩니다.' +
        "</div>" +
        '<div class="msg" id="ssBugMsg"></div>' +
        '<div class="row"><button class="no" id="ssBugNo">닫기</button>' +
        '<button class="ok" id="ssBugGo">보내기</button></div>' +
      "</div>";
    document.body.appendChild(back);
    var close = function () { back.remove(); };
    back.addEventListener("click", function (e) { if (e.target === back) close(); });
    document.getElementById("ssBugNo").onclick = close;
    var ta = document.getElementById("ssBugText");
    ta.focus();
    /* 사진 넣는 길 세 가지 — 하나만 되면 못 쓰는 사람이 생긴다. */
    var fileEl = document.getElementById("ssShotFile");
    document.getElementById("ssShotPick").onclick = function () { fileEl.click(); };
    fileEl.onchange = function () { if (this.files && this.files[0]) setShot(this.files[0]); };
    back.addEventListener("paste", function (e) {          /* Ctrl+V (윈도우 캡처가 여기로 온다) */
      var items = (e.clipboardData || {}).items || [];
      for (var i = 0; i < items.length; i++) {
        if (items[i].type && items[i].type.indexOf("image/") === 0) {
          setShot(items[i].getAsFile());
          e.preventDefault();
          return;
        }
      }
    });
    var drop = document.getElementById("ssBugDrop");
    drop.addEventListener("dragover", function (e) { e.preventDefault(); drop.style.borderColor = "#6ff0d6"; });
    drop.addEventListener("dragleave", function () { drop.style.borderColor = "#35494a"; });
    drop.addEventListener("drop", function (e) {
      e.preventDefault();
      drop.style.borderColor = "#35494a";
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) setShot(f);
    });
    document.getElementById("ssBugGo").onclick = function () {
      var btn = this;
      var text = (ta.value || "").trim();
      var msg = document.getElementById("ssBugMsg");
      if (!text) { msg.style.color = "#ff9b9b"; msg.textContent = "어떤 문제인지 한 줄만 적어주세요."; ta.focus(); return; }
      btn.disabled = true; btn.textContent = "보내는 중…";
      var body = context();
      body.message = text;
      body.shot = SHOT;                 /* 없으면 null — 서버가 그냥 건너뛴다 */
      fetch("/api/bug-report", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d || !d.ok) throw new Error((d && d.error) || "접수 실패");
        msg.style.color = "#7ee787";
        msg.textContent = d.message || "접수됐어요.";
        ta.disabled = true; btn.style.display = "none";
        document.getElementById("ssBugNo").textContent = "확인";
      }).catch(function (e) {
        msg.style.color = "#ff9b9b";
        msg.textContent = "보내지 못했어요 — 잠시 후 다시 눌러주세요. (" + e.message + ")";
        btn.disabled = false; btn.textContent = "보내기";
      });
    };
  };

  /* 답장(쪽지) — 신고만 받고 끝나면 "말해도 반응 없네"가 된다.
     안 읽은 답장이 있으면 다음 화면에서 자동으로 뜬다(카톡으로 따로 안 보내도 된다). */
  function showReplies() {
    fetch("/api/bug-report/replies", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.replies || !d.replies.length) return;
        var rep = d.replies[0];
        css();
        var back = document.createElement("div");
        back.className = "ssbug-back";
        back.innerHTML =
          '<div class="ssbug">' +
            "<h3>📩 신고하신 건 답변드립니다</h3>" +
            '<p class="sub">' + esc((rep.message || "").slice(0, 80)) + "</p>" +
            '<div class="info" style="color:#d7e3e3;font-size:14px;white-space:pre-wrap">' +
              esc(rep.reply) + "</div>" +
            '<div class="row"><button class="ok" id="ssRepOk">확인했어요</button></div>' +
          "</div>";
        document.body.appendChild(back);
        document.getElementById("ssRepOk").onclick = function () {
          fetch("/api/bug-report/replies/" + rep.id + "/read", { method: "POST" })
            .catch(function () {})
            .then(function () { back.remove(); });
        };
      })
      .catch(function () {});   /* 답장 확인 실패가 화면을 막으면 안 된다 */
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showReplies);
  } else {
    showReplies();
  }
})();
