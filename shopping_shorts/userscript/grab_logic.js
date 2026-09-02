// 로또 · 원클릭 담기 — 실제 로직 (grab.user.js 로더가 서버에서 이 파일을 매번 불러와 실행).
// ★이 파일을 고치면 모든 사용자가 다음 새로고침에 자동 반영된다(재설치 불필요).
// 로직 버전: 2026-09-02-b  (LOGIC_VER가 정본)
//   · ⭐볼채널등록 — 회원용 개인 채널 즐겨찾기
//   · 유튜브는 쇼츠에서만 동작 — 메인·롱폼 차단
//   ★두 트랙이 같은 날 각각 20260905를 달아 병합에서 부딪혔다. 합친 파일이라
//     번호를 한 칸 올린다 — 버전은 "무엇이 들어있나"의 유일한 표식이다.
(function () {
  "use strict";
  // ── 중복 실행 방지 → '새 로직이 이긴다'로 교체(2026-08-18 실사고) ──────────
  // 종전엔 `__ssGrabLoaded`가 true면 무조건 return이라 **먼저 뜬 쪽이 이겼다**.
  // 사장님 PC에서 옛 확장(1.0.0)이 텀퍼몽키 v2.4.0의 새 로직을 밀어내, 새 기능이
  // 배포됐는데도 옛 버튼("채널등록")만 보였다 — 게다가 **아무 오류도 안 나서**
  // 원인 찾는 데 한참 걸렸다. 그래서 버전을 숫자로 박고 큰 쪽이 이어받게 한다.
  // (옛 코드는 이 숫자가 없다 → 0으로 보고 새 로직이 이긴다. 옛 인터벌은 남지만
  //  버튼은 id 선점이라 서로 안 덮고, 새 화면(유튜브·쓰레드)은 새 로직이 그린다.)
  var LOGIC_VER = 20260907;
  if ((window.__ssGrabVer || 0) >= LOGIC_VER) return;   // 같거나 더 새것이 이미 돎
  if (window.__ssGrabLoaded && !window.__ssGrabVer) {
    // 옛 로직이 이미 돌고 있다 — 그 버튼을 걷어내고 새 로직이 다시 그린다.
    try {
      var olds = document.querySelectorAll("#ss-grab-btn,#ss-chadd-btn,#ss-lens-btn,#ss-adopt-btn,#ss-seek");
      for (var oi = 0; oi < olds.length; oi++) olds[oi].remove();
    } catch (e) {}
  }
  try { clearInterval(window.__ssGrabTimer); } catch (e) {}   // 새 버전끼리 교체될 때
  window.__ssGrabLoaded = true;
  window.__ssGrabVer = LOGIC_VER;
  var BASE = "https://shoppingshorts.duckdns.org";

  // ── 설치 확인 비컨 ─────────────────────────────────────────────
  // 이 로직이 우리 설치 안내 페이지(shoppingshorts.duckdns.org/grab*)에서 돌면
  // = 유저스크립트가 정상 설치됐다는 뜻. DOM에 표식을 남겨 그 페이지가 "설치 완료"를
  // 스스로 감지하게 한다(사용자가 '됐나?'를 판단할 필요 없음). Tampermonkey 샌드박스는
  // JS 스코프만 격리하고 DOM은 페이지와 공유하므로 이 attribute를 페이지 스크립트가 읽는다.
  // 우리 도메인에선 담기 버튼을 붙이지 않고 여기서 끝낸다(자기 페이지에 엉뚱한 📥 방지).
  try {
    if (["shoppingshorts.duckdns.org", "app.stmaker.kr"]
        .some(function (h) { return location.hostname.indexOf(h) >= 0; })) {
      document.documentElement.setAttribute("data-ss-grab-installed", "1");
      // localStorage는 JS월드가 아니라 '출처(origin)'로 공유돼 샌드박스 경계에 가장 강하다.
      try { localStorage.setItem("ss_grab_ok", "1"); } catch (e) {}
      try { window.postMessage({ __ssGrabInstalled: true }, "*"); } catch (e) {}
      return;
    }
  } catch (e) {}

  function meta(p) {
    var e = document.querySelector('meta[property="' + p + '"]');
    return e ? e.content : "";
  }

  // ★지금 보는 영상의 **파일 직접 주소**(2026-08-17). 도우인은 yt-dlp가 쿠키를 요구해
  //   페이지 URL만으로는 서버가 영상을 못 받는다(서버·PC 양쪽에서 재현 — IP 문제가 아니다).
  //   그런데 브라우저에는 CDN 주소가 그대로 있다. 담는 순간 그걸 함께 보내면 서버가
  //   그 주소로 바로 받는다(download_any가 video_url을 우선 쓴다).
  //   blob:은 이 탭 안에서만 유효하므로 보내지 않는다 — 서버가 받을 수 없다.
  var _MEDIA_HOSTS = ["zjcdn.com", "douyinvod.com", "xhscdn.com"];
  function currentVideoSrc() {
    try {
      var vs = document.querySelectorAll("video");
      for (var i = 0; i < vs.length; i++) {
        var cand = [vs[i].currentSrc, vs[i].src];
        var ss = vs[i].querySelectorAll("source");
        for (var k = 0; k < ss.length; k++) cand.push(ss[k].src);
        for (var j = 0; j < cand.length; j++) {
          var u = cand[j] || "";
          if (u.indexOf("https://") !== 0) continue;      // blob:·상대경로 제외
          for (var h = 0; h < _MEDIA_HOSTS.length; h++) {
            if (u.indexOf(_MEDIA_HOSTS[h]) >= 0) return u;
          }
        }
      }
    } catch (e) {}
    return "";
  }
  // ★지금 보는 영상의 **커버 이미지**(2026-08-17 사장님 "도우인은 썸네일이 없음").
  //   도우인 영상 페이지는 SPA라 og:image가 없다(og:title도 "观看更多精彩视频 - 抖音"
  //   라는 기본값이 그대로 담겨 있었다 → 담긴 카드가 제목·썸네일 둘 다 기본값/빈값).
  //   서버 보강(_enrich_grab→yt-dlp)도 도우인은 쿠키를 요구해 못 채운다.
  //   브라우저에는 커버가 <video poster> 또는 douyinpic 이미지로 이미 떠 있으므로
  //   담는 순간 그걸 함께 보낸다(video_url을 같이 보내는 것과 같은 원리).
  // ⚠️호스트를 넓히지 마라 — collection.html thumbSrc()가 no-referrer 직접로드로
  //   통과시키는 CDN(douyinpic·xhscdn)만 받는다. 나머지는 /api/thumb 프록시를 타는데
  //   허용호스트가 아니면 400이 나 카드가 다시 빈칸이 된다.
  var _IMG_HOSTS = ["douyinpic.com", "xhscdn.com"];
  function _knownImg(u) {
    if (!u || u.indexOf("https://") !== 0) return "";   // data:·blob:·상대경로 제외
    for (var h = 0; h < _IMG_HOSTS.length; h++) if (u.indexOf(_IMG_HOSTS[h]) >= 0) return u;
    return "";
  }
  function currentPoster() {
    try {
      var vs = document.querySelectorAll("video");
      for (var i = 0; i < vs.length; i++) {
        var p = _knownImg(vs[i].poster || "");
        if (p) return p;
      }
      // poster가 비면 화면에서 가장 큰(=커버) 이미지를 쓴다.
      var imgs = document.querySelectorAll("img"), best = "", bestA = 0;
      for (var j = 0; j < imgs.length; j++) {
        var u = _knownImg(imgs[j].currentSrc || imgs[j].src || "");
        if (!u) continue;
        var r = imgs[j].getBoundingClientRect(), a = r.width * r.height;
        if (r.width >= 120 && a > bestA) { bestA = a; best = u; }
      }
      return best;
    } catch (e) {}
    return "";
  }
  function openGrab(url, thumb, title, videoUrl) {
    window.open(
      BASE + "/api/grab?url=" + encodeURIComponent(url) +
        "&thumbnail=" + encodeURIComponent(thumb || "") +
        "&title=" + encodeURIComponent((title || "").slice(0, 120)) +
        (videoUrl ? "&video_url=" + encodeURIComponent(videoUrl) : ""),
      "ss_grab", "width=380,height=220"
    );
  }

  // ── 채널등록 버튼(인스타 전용, 2026-08-03 사장님 요청): 지금 보는 게시물의 '채널'을
  // 레퍼런스 추적목록에 등록한다. 게시물/릴스 페이지면 URL을 서버로 보내 yt-dlp가 채널을
  // 해석해 등록, 프로필 페이지(/{username}/)면 그 계정을 바로 등록. popup GET이라
  // 서버 세션 쿠키가 실려 관리자 가드가 그대로 동작(/api/grab과 같은 방식).
  var _IG_RESERVED = { p: 1, reel: 1, reels: 1, explore: 1, stories: 1, accounts: 1,
                       direct: 1, tv: 1 };
  // 인스타+틱톡 공통(2026-08-03 사장님 '틱톡도 동일하게') — 시크바·채널등록·렌즈.
  function _snsHost() {
    if (location.host.indexOf("instagram.com") >= 0) return "instagram";
    if (location.host.indexOf("tiktok.com") >= 0) return "tiktok";
    return "";
  }
  // 시크바·렌즈가 붙는 플랫폼(2026-09-01 사장님 "유튜브도 인스타랑 같게").
  // _snsHost()는 인스타·틱톡 전용 로직(그리드 카드 등)에 계속 쓰인다 — 섞지 않는다.
  function _playerPlat() {
    var h = location.host;
    if (h.indexOf("instagram.com") >= 0) return "instagram";
    if (h.indexOf("tiktok.com") >= 0) return "tiktok";
    if (h.indexOf("youtube.com") >= 0 || h.indexOf("youtu.be") >= 0) return "youtube";
    if (h.indexOf("threads.com") >= 0 || h.indexOf("threads.net") >= 0) return "threads";
    return "";
  }
  // 이 영상 한 편을 가리키는 키(캐시·통계용). 플랫폼마다 주소 모양이 다르다.
  function _pageKey() {
    var m = location.pathname.match(/\/(?:reel|reels|p|tv|video|shorts)\/[A-Za-z0-9_-]+/);
    if (m) return m[0];
    var v = location.search.match(/[?&]v=([A-Za-z0-9_-]+)/);       // 유튜브 watch
    if (v && _playerPlat() === "youtube") return "/watch/" + v[1];
    var t = location.pathname.match(/^\/@[\w.\-]+\/post\/[A-Za-z0-9_-]+/);  // 쓰레드
    return t ? t[0] : "";
  }
  function _ttProfile() {   // 틱톡 프로필(/@handle) — 영상 페이지(/@handle/video/..)는 제외
    var m = location.pathname.match(/^\/@([\w.\-]+)\/?$/);
    return m ? m[1] : "";
  }
  function _igProfileName() {
    var m = location.pathname.match(/^\/([^/]+)\/?(reels\/?)?$/);
    return (m && !_IG_RESERVED[m[1]]) ? m[1] : "";
  }
  // ── 릴스/게시물 화면의 **작성자 핸들**을 화면에서 읽는다 (2026-09-02 사장님 제보) ──
  //   증상: 릴스에서 📌채널수집을 누르면 "❌ 채널을 못 찾았어요"만 떴다.
  //   원인: 서버가 username 없이 오면 yt-dlp로 인스타를 해석하는데, 로그인 없는 서버는
  //         자주 막힌다(_resolve_uploader). 그런데 **화면에는 계정명이 이미 떠 있다** —
  //         담기가 조회수를 화면에서 읽어 보내는 것과 같은 처방으로, 여기서 읽어 보낸다.
  //   ★영상 근처(조상 6단계 안)의 프로필 링크만 고른다 — 사이드바 추천 계정을 집으면
  //     엉뚱한 채널이 등록된다.
  function _igAuthor() {
    var ok = function (h) {
      var m = String(h || "").match(/^\/([A-Za-z0-9._]+)\/?(\?|$)/);
      return (m && !_IG_RESERVED[m[1]]) ? m[1] : "";
    };
    var vs = document.querySelectorAll("video"), best = null, area = 0;
    for (var i = 0; i < vs.length; i++) {
      var r = vs[i].getBoundingClientRect();
      if (r.width * r.height > area) { area = r.width * r.height; best = vs[i]; }
    }
    var el = best && best.parentElement, guard = 0;
    while (el && guard++ < 6) {
      var as = el.querySelectorAll('a[href^="/"]');
      for (var k = 0; k < as.length; k++) {
        var u = ok(as[k].getAttribute("href"));
        if (u) return u;
      }
      el = el.parentElement;
    }
    // 폴백: 페이지 안 JSON에 owner.username이 들어 있는 경우
    try {
      var m2 = (document.body.innerHTML || "").match(/"owner":\{[^}]*"username":"([A-Za-z0-9._]+)"/);
      if (m2) return m2[1];
    } catch (e) {}
    return "";
  }

  // ── 채널수집 버튼 — 인스타·틱톡에 이어 유튜브·쓰레드까지(2026-08-18 사장님 요청) ──
  // 플랫폼마다 '어디에 넣어야 수집이 잡느냐'가 다르다(인스타=discovered_channels,
  // 나머지=platform_seeds account). 그 갈래는 **서버 한 곳**(/api/discover/add_by_url)
  // 에서만 정한다 — 여기서 또 정하면 0순위-B(같은 판단 두 곳)에 걸려 언젠가 어긋난다.
  // 여기서 정하는 건 '지금 화면에 대상이 있느냐'와 '무엇을 보내느냐'뿐이다.
  function _chPlat() {
    var h = location.host;
    if (h.indexOf("instagram.com") >= 0) return "instagram";
    if (h.indexOf("tiktok.com") >= 0) return "tiktok";
    if (h.indexOf("youtube.com") >= 0 || h.indexOf("youtu.be") >= 0) return "youtube";
    if (h.indexOf("threads.com") >= 0 || h.indexOf("threads.net") >= 0) return "threads";
    return "";
  }
  // 쓰레드는 프로필(/@핸들)이든 게시물(/@핸들/post/코드)이든 경로 맨 앞이 핸들이다.
  function _thProfile() {
    var m = location.pathname.match(/^\/@([\w.\-]+)/);
    return m ? m[1] : "";
  }
  // 유튜브: 채널 페이지(/@핸들·/channel/·/c/·/user/)면 그 채널, 영상(watch·shorts·live)이면
  // URL을 서버에 맡겨 yt-dlp가 소속 채널을 해석한다.
  function _ytTarget() {
    var p = location.pathname;
    if (/^\/@[\w.\-]+/.test(p) || /^\/(channel|c|user)\//.test(p)) return "channel";
    if (/^\/(watch|shorts\/|live\/)/.test(p) || location.host.indexOf("youtu.be") >= 0) return "video";
    return "";
  }
  // 서버로 보낼 질의문자열. ""이면 대상이 모호한 화면(피드·탐색)이라 버튼을 안 띄운다.
  function _chQuery() {
    var plat = _chPlat();
    if (plat === "instagram") {
      var ig = _igProfileName();
      if (ig) return "username=" + encodeURIComponent(ig);
      if (!isSinglePost()) return "";
      var q = "url=" + encodeURIComponent(location.href);
      var au = _igAuthor();
      if (au) q += "&username=" + encodeURIComponent(au);   // 서버 yt-dlp 해석을 건너뛴다
      return q;
    }
    if (plat === "tiktok")
      return (_ttProfile() || isSinglePost()) ? "url=" + encodeURIComponent(location.href) : "";
    if (plat === "threads")
      return _thProfile() ? "url=" + encodeURIComponent(location.href) : "";
    if (plat === "youtube")
      return _ytTarget() ? "url=" + encodeURIComponent(location.href) : "";
    return "";
  }
  function addChannelBtn() {
    if (document.getElementById("ss-chadd-btn") || !document.body) return;
    if (!_chQuery()) return;
    // 회원에겐 아예 안 붙인다(관리자 전용 API라 눌러도 "관리자 필요"만 뜬다).
    // ★syncExtraBtns에서 지우기만 하면 붙였다 지웠다를 반복해 깜빡인다 —
    //   붙이는 쪽에서 막는 게 유일한 정답이다. 아직 모르는 동안(null)도 안 붙인다.
    if (window.__ssIsAdmin !== true) return;
    var b = document.createElement("button");
    b.id = "ss-chadd-btn";
    b.textContent = "📌 채널수집";
    b.title = "이 채널을 레퍼런스 수집 목록에 등록";
    b.style.cssText =
      "position:fixed;right:18px;bottom:70px;z-index:2147483647;background:#8250df;" +
      "color:#fff;border:none;border-radius:24px;padding:10px 16px;font-size:14px;" +
      "font-weight:800;box-shadow:0 4px 14px rgba(0,0,0,.35);cursor:pointer;font-family:system-ui,sans-serif";
    b.addEventListener("click", function (e) {
      e.preventDefault();
      // SPA라 붙일 때와 누를 때의 화면이 다를 수 있다 — 클릭 시점에 다시 읽는다.
      var q = _chQuery();
      if (!q) return;
      window.open(BASE + "/api/discover/add_by_url?" + q, "ss_chadd", "width=380,height=240");
    });
    document.body.appendChild(b);
  }
  // ── ⭐즐겨찾기 이동 + 🔍렌즈(2026-08-03 사장님 요청): 인스타에서 바로.
  // 렌즈는 랭킹 페이지 ?lens_url= 딥링크로 보내 traceByUrl(원본 역추적)을 즉시 실행.
  function _miniBtn(id, text, title, bottom, bg, onClick) {
    if (document.getElementById(id) || !document.body) return;
    var b = document.createElement("button");
    b.id = id; b.textContent = text; b.title = title;
    b.style.cssText =
      "position:fixed;right:18px;bottom:" + bottom + "px;z-index:2147483647;background:" + bg + ";" +
      "color:#fff;border:none;border-radius:24px;padding:10px 16px;font-size:14px;" +
      "font-weight:800;box-shadow:0 4px 14px rgba(0,0,0,.35);cursor:pointer;font-family:system-ui,sans-serif";
    b.addEventListener("click", function (e) { e.preventDefault(); onClick(); });
    document.body.appendChild(b);
  }
  // 렌즈 결과를 '인스타 화면 안' 오버레이로 그린다(2026-08-03 사장님: 사이트 이동 없이).
  // GM_xmlhttpRequest(로더 @grant·@connect)가 쿠키를 실어 보내 로그인·크레딧 가드가
  // 그대로 동작한다. GM이 없는 환경(주입 폴백 등)만 옛 딥링크 새탭으로.
  function _lensOverlay(html) {
    var o = document.getElementById("ss-lens-ov");
    if (!o) {
      o = document.createElement("div");
      o.id = "ss-lens-ov";
      o.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:2147483647;" +
        "display:flex;align-items:center;justify-content:center;padding:20px;font-family:system-ui,sans-serif";
      o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
      document.body.appendChild(o);
    }
    o.innerHTML = "<div style='background:#161616;color:#eee;border:1px solid #333;border-radius:14px;" +
      "padding:16px;max-width:720px;width:100%;max-height:82vh;overflow:auto;position:relative'>" +
      "<button onclick='document.getElementById(\"ss-lens-ov\").remove()' style='position:absolute;" +
      "top:6px;right:12px;background:none;border:none;color:#fff;font-size:22px;cursor:pointer'>✕</button>" +
      "<div style='font-weight:800;margin-bottom:10px'>🔍 원본·유사 레퍼런스</div>" + html + "</div>";
  }
  function _esc(s) { return String(s || "").replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  // ── 인스타 시크바(2026-08-03 사장님: 장면 이동이 안 돼 앞으로 못 돌아감) ──
  // 인스타 플레이어엔 시크바가 없지만 <video>는 페이지 DOM이라 currentTime을 직접
  // 움직일 수 있다(영상 소스가 CDN(교차출처)이어도 재생 제어는 무관). 지금 재생 중인
  // 비디오를 골라 슬라이더로 앞뒤 이동 + 렌즈에 '보고 있는 그 장면'(초)을 실어 보낸다.
  function _igVideo() {
    var vs = document.querySelectorAll("video"), best = null;
    for (var i = 0; i < vs.length; i++) {
      var v = vs[i];
      if (!v.duration || !isFinite(v.duration)) continue;
      var r = v.getBoundingClientRect();
      if (r.width < 100 || r.bottom < 0 || r.top > innerHeight) continue;   // 화면 밖 제외
      if (!v.paused) return v;   // 재생 중인 놈이 정답
      if (!best) best = v;
    }
    return best;
  }
  function _fmtT(s) { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }
  // 영상 등록일 — 서버 호출 없이 URL의 ID에서 계산한다(무료·즉시).
  //   인스타: shortcode(base64url) → media pk, 발행ms = (pk>>23) + 1314220021721
  //           (2026-07-31 레퍼런스수집급감 트랙에서 실데이터 6/6 일치 검증한 공식)
  //   틱톡:   /video/{id} → 발행초 = id>>32 (틱톡 ID 상위 32비트가 unix time)
  function _igDate(code) {                       // 인스타 shortcode → 등록일
    try {
      var A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_", pk = 0n;
      code = code.slice(0, 11);                  // 11자 초과분은 pk 아님(비공개 접미)
      for (var i = 0; i < code.length; i++) {
        var d = A.indexOf(code[i]); if (d < 0) return null;
        pk = pk * 64n + BigInt(d);
      }
      return new Date(Number((pk >> 23n) + 1314220021721n));
    } catch (e) { return null; }
  }
  function _postDate() {
    try {
      var m = location.pathname.match(/\/(?:reel|reels|p|tv)\/([A-Za-z0-9_-]+)/);
      if (m && location.host.indexOf("instagram") >= 0) return _igDate(m[1]);
      var t = location.pathname.match(/\/video\/(\d{15,})/);
      if (t && location.host.indexOf("tiktok") >= 0)
        return new Date(Number(BigInt(t[1]) >> 32n) * 1000);
    } catch (e) {}
    return null;
  }
  function _fmtDate(d) {
    if (!d || !isFinite(d.getTime())) return "";
    var y = d.getFullYear();
    if (y < 2010 || y > 2100) return "";        // 공식이 안 맞는 ID면 표시 안 함
    return y + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
  }
  function syncSeekBar() {
    if (!_playerPlat()) return;
    var box = document.getElementById("ss-seek");
    if (!_isVideoPage()) { if (box) box.remove(); return; }
    var v = _igVideo();
    if (!v) { if (box) box.remove(); return; }
    if (!box) {
      box = document.createElement("div");
      box.id = "ss-seek";
      box.style.cssText = "position:fixed;right:18px;bottom:174px;z-index:2147483647;background:rgba(20,20,20,.92);" +
        "border:1px solid #444;border-radius:12px;padding:5px 8px;display:flex;align-items:center;gap:6px;" +
        "font-family:system-ui,sans-serif;color:#fff;font-size:11px;box-shadow:0 4px 14px rgba(0,0,0,.35)";
      box.innerHTML = "<button id='ss-seek-p' title='일시정지/재생' style='background:none;border:none;" +
        "color:#fff;font-size:13px;cursor:pointer;padding:0 2px'>⏸</button>" +
        "<button id='ss-seek-x' title='재생 속도' style='background:none;border:none;" +
        "color:#fff;font-size:11px;font-weight:800;cursor:pointer;padding:0 2px'>1x</button>" +
        "<input id='ss-seek-r' type='range' min='0' max='100' step='0.1' value='0' style='width:90px;cursor:pointer'>" +
        "<span id='ss-seek-t' style='min-width:58px;text-align:right'>0:00/0:00</span>" +
        "<span id='ss-seek-d' title='영상 등록일' style='color:#aaa;border-left:1px solid #555;padding-left:6px'></span>" +
        "<span id='ss-seek-s' title='조회수·댓글수' style='color:#aaa;border-left:1px solid #555;padding-left:6px'></span>";
      document.body.appendChild(box);
      var r = document.getElementById("ss-seek-r");
      r.addEventListener("input", function () {
        var vv = _igVideo(); if (vv) { try { vv.currentTime = parseFloat(this.value); } catch (e) {} }
      });
      var SPEEDS = [1, 1.25, 1.5, 2, 0.5];
      document.getElementById("ss-seek-x").addEventListener("click", function () {
        var vv = _igVideo(); if (!vv) return;
        var i = SPEEDS.indexOf(vv.playbackRate);
        vv.playbackRate = SPEEDS[(i + 1) % SPEEDS.length];   // 목록에 없으면 i=-1 → 1x
      });
      document.getElementById("ss-seek-p").addEventListener("click", function () {
        var vv = _igVideo(); if (!vv) return;
        try { if (vv.paused) vv.play(); else vv.pause(); } catch (e) {}
        this.textContent = vv.paused ? "▶" : "⏸";
      });
    }
    var r2 = document.getElementById("ss-seek-r"), t2 = document.getElementById("ss-seek-t"),
        p2 = document.getElementById("ss-seek-p");
    if (r2 && t2) {
      r2.max = v.duration;
      if (document.activeElement !== r2) r2.value = v.currentTime;   // 드래그 중엔 안 덮음
      t2.textContent = _fmtT(v.currentTime) + "/" + _fmtT(v.duration);
      if (p2) p2.textContent = v.paused ? "▶" : "⏸";
    }
    var x2 = document.getElementById("ss-seek-x");
    if (x2) x2.textContent = (v.playbackRate || 1) + "x";
    var d2 = document.getElementById("ss-seek-d");
    if (d2) {                                    // SPA라 영상이 바뀌면 URL도 바뀜 — 매 tick 갱신
      var dd = _fmtDate(_postDate());
      d2.textContent = dd ? "📅 " + dd : "";
      d2.style.display = dd ? "" : "none";
    }
    _syncStats();
  }
  // 조회수·댓글수 — 서버 /api/media_stats(yt-dlp 메타, 서버측 캐시)를 GM 브리지로.
  // URL(게시물)당 1회만 요청하고 결과를 로컬에도 캐시해 스크롤해도 재호출 없음.
  var _statsCache = {}, _statsPending = {};
  function _fmtN(n) {
    if (n == null) return null;
    if (n >= 100000000) return (n / 100000000).toFixed(1).replace(/\.0$/, "") + "억";
    if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, "") + "만";
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "천";
    return "" + n;
  }
  function _statsText(s) {
    var parts = [];
    if (s.views != null) parts.push("▶" + _fmtN(s.views));
    if (s.likes != null) parts.push("♥" + _fmtN(s.likes));
    if (s.comments != null) parts.push("💬" + _fmtN(s.comments));
    return parts.join(" ");
  }
  function _syncStats() {
    var el = document.getElementById("ss-seek-s");
    if (!el) return;
    var key = _pageKey();
    if (!key) { el.style.display = "none"; return; }
    if (_statsCache[key]) {
      var t = _statsText(_statsCache[key]);
      el.textContent = t; el.style.display = t ? "" : "none"; return;
    }
    if (_statsPending[key]) { el.textContent = "…"; el.style.display = ""; return; }
    _statsPending[key] = 1;
    el.textContent = "…"; el.style.display = "";
    _gmGet(BASE + "/api/media_stats?url=" + encodeURIComponent(location.href), function (st, text) {
      try {
        var d = JSON.parse(text || "{}");
        if (st === 200 && d.ok) _statsCache[key] = d;
        else _statsCache[key] = {};             // 실패는 빈값 캐시(같은 게시물 재폭격 방지)
      } catch (e) { _statsCache[key] = {}; }
      delete _statsPending[key];
    }, function () { _statsCache[key] = {}; delete _statsPending[key]; });
  }
  // ── 인스타 채널 릴스 그리드 카드에 📅등록일+💬댓글수 배지(2026-08-03 사장님 요청) ──
  // 등록일은 카드 href의 shortcode에서 즉시(무료). 댓글수는 서버 media_stats가 필요해
  // '화면에 보이는 카드만' 동시 2개씩 천천히 조회한다 — 한 번에 다 쏘면 서버 yt-dlp가
  // 인스타 429 예산을 갉아먹는다. 결과는 서버·로컬 이중 캐시라 재방문 땐 즉시 뜬다.
  var _gridQ = [], _gridActive = 0;
  function _gridPump() {
    while (_gridActive < 2 && _gridQ.length) {
      (function (it) {
        var key = it[0], url = it[1], cb = it[2];
        if (_statsCache[key]) { cb(_statsCache[key]); return; }
        _gridActive++;
        _gmGet(BASE + "/api/media_stats?url=" + encodeURIComponent(url), function (st, text) {
          var d = {}; try { d = JSON.parse(text || "{}"); } catch (e) {}
          _statsCache[key] = (st === 200 && d.ok) ? d : {};
          _gridActive--; cb(_statsCache[key]); _gridPump();
        }, function () { _statsCache[key] = {}; _gridActive--; cb({}); _gridPump(); });
      })(_gridQ.shift());
    }
  }
  function syncGridBadges() {
    if (location.host.indexOf("instagram") < 0 || isSinglePost()) return;
    var as = document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]');
    for (var i = 0; i < as.length; i++) {
      var a = as[i];
      var m = (a.getAttribute("href") || "").match(/\/(?:reel|reels|p)\/([A-Za-z0-9_-]+)/);
      if (!m) continue;
      var r = a.getBoundingClientRect();
      if (r.width < 120 || r.height < 120) continue;   // 그리드 카드만(아이콘·텍스트 링크 제외)
      var code = m[1], key = "/reel/" + code;
      var el = a.querySelector(".ss-card-info");
      if (!el) {
        if (getComputedStyle(a).position === "static") a.style.position = "relative";
        el = document.createElement("div");
        el.className = "ss-card-info";
        el.style.cssText = "position:absolute;right:6px;bottom:6px;z-index:99998;" +
          "background:rgba(0,0,0,.65);color:#fff;font:11px system-ui,sans-serif;" +
          "border-radius:8px;padding:2px 7px;pointer-events:none";
        a.appendChild(el);
      }
      if (el.getAttribute("data-c") !== code) {        // SPA 노드 재사용 대비
        el.setAttribute("data-c", code);
        el.removeAttribute("data-q");
        var dd = _fmtDate(_igDate(code));
        el.textContent = dd ? "📅 " + dd.slice(2) : "";
      }
      // 카드별 🔍렌즈 — 페이지 이동 없이 이 화면에서 오버레이로(2026-08-03 사장님 요청)
      var lb = a.querySelector(".ss-card-lens");
      if (!lb) {
        lb = document.createElement("button");
        lb.className = "ss-card-lens";
        lb.textContent = "🔍";
        lb.title = "이 영상 렌즈(원본·유사 추적)";
        // 위치: 우리 배지(우하단) 바로 위 — 좌하단은 인스타 자체 조회수 표기가 있어 피한다
        lb.style.cssText = "position:absolute;right:6px;bottom:32px;z-index:99999;" +
          "background:#37b0e0;color:#fff;border:none;border-radius:14px;width:28px;height:28px;" +
          "font-size:13px;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.4)";
        lb.addEventListener("click", function (e) {
          e.preventDefault(); e.stopPropagation();
          var c = el.getAttribute("data-c");     // 클릭 시점의 현재 카드(SPA 재사용 대비)
          if (c) _lensRun("https://www.instagram.com/reel/" + c + "/", true);
        });
        a.appendChild(lb);
      }
      if (!el.getAttribute("data-q") && r.bottom > 0 && r.top < innerHeight) {
        el.setAttribute("data-q", "1");                // 보이는 카드만 큐에
        (function (el, code) {
          _gridQ.push([key, "https://www.instagram.com/reel/" + code + "/", function (s) {
            if (el.getAttribute("data-c") !== code) return;
            if (s && s.comments != null) el.textContent += " 💬" + _fmtN(s.comments);
          }]);
        })(el, code);
        _gridPump();
      }
    }
  }
  // 서버 POST(쿠키 동봉) — 샌드박스면 GM 직접, 메인월드(인스타 Blob 폴백)면 로더의
  // GM 브리지(postMessage)로 위임. 브리지 응답이 1.5초 안에 없으면(구버전 로더) 실패 콜백.
  function _gmPost(url, bodyObj, done, fail) {
    if (typeof GM_xmlhttpRequest !== "undefined") {
      GM_xmlhttpRequest({ method: "POST", url: url,
        headers: { "Content-Type": "application/json" }, data: JSON.stringify(bodyObj),
        onload: function (r) { done(r.status, r.responseText); }, onerror: fail });
      return;
    }
    var reqId = "ss" + Math.random().toString(36).slice(2), acked = false;
    function onMsg(ev) {
      var d = ev && ev.data;
      if (!d || d.reqId !== reqId) return;
      if (d.__ssGmAck) { acked = true; return; }   // 브리지 살아있음 — 본 응답 대기
      if (!d.__ssGmResult) return;
      window.removeEventListener("message", onMsg);
      if (d.status > 0) done(d.status, d.text); else fail();
    }
    window.addEventListener("message", onMsg);
    window.postMessage({ __ssGmFetch: true, reqId: reqId, method: "POST", url: url,
                         headers: { "Content-Type": "application/json" },
                         body: JSON.stringify(bodyObj) }, "*");
    setTimeout(function () {   // ACK 확인용 — 구버전 로더(브리지 없음)면 폴백
      if (!acked) { window.removeEventListener("message", onMsg); fail("nobridge"); }
    }, 1500);
  }
  function _gmGet(url, done, fail) {
    if (typeof GM_xmlhttpRequest !== "undefined") {
      GM_xmlhttpRequest({ method: "GET", url: url,
        onload: function (r) { done(r.status, r.responseText); }, onerror: fail });
      return;
    }
    var reqId = "sg" + Math.random().toString(36).slice(2), acked = false;
    function onMsg(ev) {
      var d = ev && ev.data;
      if (!d || d.reqId !== reqId) return;
      if (d.__ssGmAck) { acked = true; return; }
      if (!d.__ssGmResult) return;
      window.removeEventListener("message", onMsg);
      if (d.status > 0) done(d.status, d.text); else fail();
    }
    window.addEventListener("message", onMsg);
    window.postMessage({ __ssGmFetch: true, reqId: reqId, method: "GET", url: url }, "*");
    setTimeout(function () { if (!acked) { window.removeEventListener("message", onMsg); fail(); } }, 1500);
  }
  // 인스타 CSP img-src가 외부 CDN 이미지를 전부 막아 오버레이 썸네일이 깨졌다(2026-08-03
  // 사장님 제보). data:는 허용 → 서버 /api/thumb64가 base64로 감싸 주고 여기서 src에 넣는다.
  function _fillThumbs() {
    var ov = document.getElementById("ss-lens-ov"); if (!ov) return;
    var imgs = ov.querySelectorAll("img[data-t64]");
    for (var i = 0; i < imgs.length; i++) {
      (function (im) {
        var u = im.getAttribute("data-t64"); im.removeAttribute("data-t64");
        _gmGet(BASE + "/api/thumb64?url=" + encodeURIComponent(u), function (st, text) {
          try { var d = JSON.parse(text); if (d.ok && d.data) im.src = d.data; } catch (e) {}
        }, function () {});
      })(imgs[i]);
    }
  }
  function _lensRun(url, noT) {
    // noT=true: 그리드 카드에서 실행 — 화면의 다른(호버 재생) 비디오 시각을 잘못 싣지 않게
    // t를 빼고 보낸다(서버가 영상 중간 프레임으로 캡처).
    var v = noT ? null : _igVideo();
    var t = (v && isFinite(v.currentTime)) ? Math.round(v.currentTime * 10) / 10 : null;
    _lensOverlay("<div style='padding:30px;text-align:center;color:#aaa'>🔗 원본·유사 영상 추적 중… (10~20초)</div>");
    _gmPost(BASE + "/api/lens/trace_url",
      t === null ? { url: url } : { url: url, t: t },
      function (status, text) {
        var d = {};
        try { d = JSON.parse(text); } catch (e) {}
        if (status === 429) { _lensOverlay("<div style='padding:20px;color:#e0623d'>💰 " + _esc(d.error || "이번 달 렌즈 한도 초과") + "</div>"); return; }
        if (!d.ok) { _lensOverlay("<div style='padding:20px;color:#e0623d'>❌ " + _esc(d.error || "추적 실패 — 로그인 상태를 확인해 주세요") + "</div>"); return; }
        var items = d.items || [];
        if (!items.length) { _lensOverlay("<div style='padding:20px;color:#aaa'>비슷한 영상을 못 찾았어요. 다른 장면의 링크로 시도해 보세요.</div>"); return; }
        var h = "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px'>";
        for (var i = 0; i < items.length && i < 40; i++) {
          var it = items[i];
          h += "<div style='background:#222;border-radius:10px;overflow:hidden'>" +
            "<a href='" + _esc(it.url) + "' target='_blank' rel='noopener'>" +
            (it.thumbnail ? "<img data-t64='" + _esc(it.thumbnail) + "' style='width:100%;height:110px;object-fit:cover;display:block;background:#000'>" :
              "<div style='height:110px;background:#000'></div>") + "</a>" +
            "<div style='padding:6px;font-size:11px'>" +
            "<div style='color:#8ab4f8'>" + _esc(it.platform || "") + "</div>" +
            "<div style='color:#ccc;max-height:30px;overflow:hidden'>" + _esc((it.title || "").slice(0, 60)) + "</div>" +
            "<button style='margin-top:5px;width:100%;background:#1f6feb;color:#fff;border:none;border-radius:6px;padding:5px;cursor:pointer' " +
            "data-u='" + _esc(it.url) + "' data-t='" + _esc(it.thumbnail || "") + "' data-n='" + _esc((it.title || "").slice(0, 100)) + "' " +
            "onclick='void(0)'>📥 담기</button></div></div>";
        }
        h += "</div>";
        _lensOverlay(h);
        _fillThumbs();
        var ov = document.getElementById("ss-lens-ov");
        var bs = ov.querySelectorAll("button[data-u]");
        for (var j = 0; j < bs.length; j++) {
          bs[j].addEventListener("click", function () {
            openGrab(this.getAttribute("data-u"), this.getAttribute("data-t"), this.getAttribute("data-n"));
          });
        }
      },
      function (why) {
        var ov = document.getElementById("ss-lens-ov"); if (ov) ov.remove();
        if (why === "nobridge") {   // 구버전 로더(브리지 없음) → 랭킹 페이지 딥링크 폴백
          window.open(BASE + "/?lens_url=" + encodeURIComponent(url), "_blank");
        } else {
          _lensOverlay("<div style='padding:20px;color:#e0623d'>❌ 서버 연결 실패</div>");
        }
      });
  }
  // ── ⭐볼채널등록(2026-09-02 사장님) — 회원용 개인 채널 즐겨찾기 ────────────
  //  📌채널수집·⭐레퍼런스등록은 **관리자 전용 + 전역 수집**이라 회원이 눌러도
  //  "관리자 필요"만 뜬다. 회원에겐 이 버튼이 그 자리를 대신한다.
  //  ★담아도 크롤 대상은 안 늘어난다(순수 북마크) — 서버 주석과 같은 이유.
  var _ssIsAdmin = null;      // null=아직 모름, true/false=확정
  function _ssWhoAmI(cb) {
    if (_ssIsAdmin !== null) { cb(_ssIsAdmin); return; }
    _gmGet(BASE + "/api/me", function (st, text) {
      try {
        var d = (st === 200) ? JSON.parse(text) : null;
        _ssIsAdmin = !!(d && d.is_admin);
      } catch (e) { _ssIsAdmin = false; }
      window.__ssIsAdmin = _ssIsAdmin;   // addChannelBtn이 읽는다(같은 판정 한 곳)
      cb(_ssIsAdmin);
    }, function () { _ssIsAdmin = false; window.__ssIsAdmin = false; cb(false); });
  }
  // 지금 화면의 대표 썸네일(카드에 그림을 채우는 용도 — 없으면 이름만 뜬다).
  function _ssPageThumb() {
    var v = document.querySelector("video[poster]");
    if (v && v.getAttribute("poster")) return v.getAttribute("poster");
    var og = document.querySelector("meta[property='og:image']");
    return og ? (og.getAttribute("content") || "") : "";
  }
  function addFavChannelBtn() {
    var b = document.getElementById("ss-favch-btn");
    // 대상 판정은 📌채널수집과 **같은 함수**를 쓴다 — 여기서 또 정하면 어긋난다.
    // ★관리자(사장님)에겐 안 띄운다 — 📌채널수집과 자리가 겹쳐 헷갈린다(2026-09-02 사장님).
    //   회원에겐 그대로 필요하다(회원은 📌채널수집을 못 쓴다).
    var want = !!_chQuery() && window.__ssIsAdmin !== true;
    if (b && !want) { b.remove(); return; }
    if (b || !want) return;
    _miniBtn("ss-favch-btn", "⭐ 나만의 채널등록",
             "이 채널을 내 즐겨찾기(나만의 채널등록)에 담습니다 — 수집 목록과는 별개", 278, "#d1a054",
             function () {
               var q = "url=" + encodeURIComponent(location.href);
               var t = _ssPageThumb();
               if (t) q += "&thumb=" + encodeURIComponent(t);
               window.open(BASE + "/api/fav_channel/grab?" + q,
                           "ss_favch", "width=400,height=250");
             });
  }

  function syncExtraBtns() {
    var lens = document.getElementById("ss-lens-btn");
    if (_playerPlat() && _isVideoPage()) {
      _miniBtn("ss-lens-btn", "🔍 렌즈", "이 영상으로 원본·유사 레퍼런스 역추적(화면 안에서)", 122, "#37b0e0",
               function () { _lensRun(location.href); });
    } else if (lens) { lens.remove(); }
    var coll = document.getElementById("ss-coll-btn"); if (coll) coll.remove();   // ⭐ 제거(담기와 중복)
    // ── ⭐ 레퍼런스 등록(2026-08-18 사장님 "보다가 좋은 영상 발견하면 바로 반영해서 정렬")
    //   담기(📥)는 내 즐겨찾기로만 가고, 채널수집(📌)은 다음 수집까지 기다려야 했다.
    //   이 버튼은 **영상+채널을 한 번에** 넣고 그 영상을 지금 랭킹 스냅샷에 끼워 넣는다.
    //   ★영상 페이지에서만 띄운다 — 피드·프로필에선 "어느 영상"이 정해지지 않는다.
    // ★회원에겐 관리자 전용 버튼(📌채널수집·⭐레퍼런스등록)을 감추고 ⭐볼채널등록을
    //   대신 띄운다. 관리자(사장님)는 넷 다 보인다 — 개인 즐겨찾기도 쓰기 때문.
    _ssWhoAmI(function (isAdmin) {
      addFavChannelBtn();
      if (!isAdmin) {   // 판정 전에 이미 붙은 것이 있으면 걷어낸다
        var ch = document.getElementById("ss-chadd-btn"); if (ch) ch.remove();
        var ad = document.getElementById("ss-adopt-btn"); if (ad) ad.remove();
      }
    });
    var adopt = document.getElementById("ss-adopt-btn");
    var wantAdopt = !!_chPlat() && _isVideoPage() && window.__ssIsAdmin === true;
    if (adopt && !wantAdopt) adopt.remove();
    else if (!adopt && wantAdopt) {
      _miniBtn("ss-adopt-btn", "⭐ 레퍼런스 등록",
               "이 영상을 랭킹에 바로 넣고 채널도 등록합니다", 226, "#c9922e",
               function () {
                 window.open(BASE + "/api/reference/adopt?url=" + encodeURIComponent(location.href)
                             + _pageStatsQuery(),
                             "ss_adopt", "width=420,height=260");
               });
    }
  }
  // 이 화면이 '영상 한 편'인가 — 유튜브 쇼츠·watch, 인스타 릴스/게시물, 틱톡 video,
  // 쓰레드 post. 채널수집(_chQuery)과 달리 프로필은 제외한다(등록할 영상이 없다).

  // ── 화면에 떠 있는 숫자를 같이 보낸다(2026-08-18 사장님 A안) ─────────────────
  // 왜: 서버(yt-dlp)는 로그인 없이 인스타를 읽어 **조회수·팔로워가 0**으로 들어왔다
  //     (실측: 채이홈 항목 views 0 / followers 0 / 제목 "Video by chae2home").
  //     그러면 조회수당댓글·팔로워당댓글이 계산되지 않아 정렬에서 불리해진다.
  //     그런데 사장님 화면에는 그 숫자가 이미 떠 있다 — 담는 순간 함께 보내면 된다.
  // ⚠️ 화면 글자를 읽는 근사치다. 못 읽으면 안 보낸다(서버는 받은 값이 없으면 종전대로).
  function _num(t) {
    if (!t) return 0;
    var s = String(t).replace(/[,\s]/g, "");
    var m = s.match(/([\d.]+)\s*(만|천|억|K|M|k|m)?/);
    if (!m) return 0;
    var n = parseFloat(m[1]);
    if (!isFinite(n)) return 0;
    var u = m[2] || "";
    if (u === "만") n *= 10000;
    else if (u === "천") n *= 1000;
    else if (u === "억") n *= 100000000;
    else if (u === "K" || u === "k") n *= 1000;
    else if (u === "M" || u === "m") n *= 1000000;
    return Math.round(n);
  }
  function _pageStats() {
    var out = {};
    try {
      // 화면 글자 전체에서 '조회수 12,345' 같은 짝을 찾는다(한국어·영어 둘 다).
      var txt = (document.body && document.body.innerText || "").slice(0, 20000);
      var pats = [
        ["views", /(?:조회수|조회|views?)\s*[:\s]?\s*([\d.,]+\s*[만천억KkMm]?)/],
        ["likes", /(?:좋아요|likes?)\s*[:\s]?\s*([\d.,]+\s*[만천억KkMm]?)/],
        ["comments", /(?:댓글|comments?)\s*[:\s]?\s*([\d.,]+\s*[만천억KkMm]?)/],
        ["followers", /(?:팔로워|followers?)\s*[:\s]?\s*([\d.,]+\s*[만천억KkMm]?)/]
      ];
      for (var i = 0; i < pats.length; i++) {
        var m = txt.match(pats[i][1]);
        if (m) { var v = _num(m[1]); if (v > 0) out[pats[i][0]] = v; }
      }
    } catch (e) {}
    return out;
  }
  function _pageStatsQuery() {
    var st = _pageStats(), q = "";
    for (var k in st) if (st[k] > 0) q += "&" + k + "=" + st[k];
    return q;
  }
  function _isVideoPage() {
    var p = location.pathname;
    if (/\/(p|reel|reels|tv|video)\/[^/]+/.test(p)) return true;          // 인스타·틱톡
    if (/^\/(shorts\/|watch|live\/)/.test(p)) return true;                 // 유튜브
    if (location.host.indexOf("youtu.be") >= 0) return true;
    return /^\/@[\w.\-]+\/post\//.test(p);                                // 쓰레드
  }
  function syncChannelBtn() {
    var b = document.getElementById("ss-chadd-btn");
    var want = !!_chQuery();
    if (b && !want) b.remove();
    else if (!b && want) addChannelBtn();
  }

  // ── 플로팅 버튼: 지금 보고 있는 '페이지'를 담는다(단일 영상 페이지용) ──
  function addFloatBtn() {
    if (document.getElementById("ss-grab-btn") || !document.body) return;
    var b = document.createElement("button");
    b.id = "ss-grab-btn";
    b.textContent = "📥 담기";
    b.title = "이 영상을 스탁브레인 모음집에 담기";
    b.style.cssText =
      "position:fixed;right:18px;bottom:18px;z-index:2147483647;background:#1f6feb;" +
      "color:#fff;border:none;border-radius:24px;padding:12px 18px;font-size:15px;" +
      "font-weight:800;box-shadow:0 4px 14px rgba(0,0,0,.35);cursor:pointer;font-family:system-ui,sans-serif";
    b.addEventListener("click", function (e) {
      e.preventDefault();
      openGrab(location.href, meta("og:image") || currentPoster(),
               meta("og:title") || document.title || "",
               currentVideoSrc());
    });
    document.body.appendChild(b);
  }

  // 검색 그리드(카드 담기 버튼이 있는 페이지)에선 플로팅을 숨긴다 — '검색 페이지 전체'를
  // 담는 오작동/혼동을 막고, 카드마다 있는 버튼만 쓰게 한다. 단일 영상 페이지에선 다시 보인다.
  function syncFloat() {
    var f = document.getElementById("ss-grab-btn");
    // 단일 영상 페이지에선 아래 '더 보기' 그리드에 카드버튼이 생겨도 플로팅(=본 영상 담기)을 남긴다.
    if (f) f.style.display = (document.querySelector(".ss-card-grab") && !isSinglePost()) ? "none" : "";
  }

  // 지금 보고 있는 게 '단일 영상/게시물' 페이지인가 (인스타 /p/·/reel/, 틱톡 /video/ 등)
  function isSinglePost() {
    return /\/(p|reel|reels|video)\/[^/]+/.test(location.pathname);
  }

  // 검색·탐색 '그리드' 페이지에서만 카드 버튼을 붙인다. 단일 영상 페이지에선 관련영상 카드가
  // 있어도 카드버튼을 안 붙여야 플로팅(본 영상 담기)이 안 가려진다(2026-07-19 보강).
  function isGridPage() {
    return /(^|\/)(search|explore|tag)(\/|$|\?)/.test(location.pathname + location.search) ||
           /\/search_result/.test(location.pathname);
  }

  // ── 카드별 버튼: 샤오홍슈/도우인(rednote) 검색·탐색 그리드의 영상 카드마다 ──
  // 카드=section.note-item, 커버 링크=a.cover(→/search_result/{id} 또는 /explore/{id}).
  // ★카드 링크는 반드시 xsec_token이 붙은 앵커를 고른다(2026-07-19 실측 사고):
  //   카드 맨 앞에 클래스 없는 래퍼 <a href="/search_result/{id}">(토큰 없음)가 있어서
  //   querySelector 콤마목록(문서순서 첫 매칭)이 그걸 집었다 → 토큰 없는 URL이 저장돼
  //   다운로드가 전부 실패했다. a.cover/a.title엔 토큰이 있다 — 토큰 있는 놈 우선.
  function xhsCardLink(card) {
    var as = card.querySelectorAll('a[href*="/search_result/"], a[href*="/explore/"], a.cover[href]');
    var fallback = null;
    for (var i = 0; i < as.length; i++) {
      var h = as[i].getAttribute("href") || "";
      if (h.indexOf("xsec_token") >= 0) return as[i];
      if (!fallback) fallback = as[i];
    }
    return fallback;
  }
  function addCardBtns() {
    if (!isGridPage()) return;
    var cards = document.querySelectorAll("section.note-item");
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      if (card.querySelector(".ss-card-grab")) continue;   // 중복 방지
      var cover = xhsCardLink(card);
      if (!cover) continue;   // 광고·라이브 등 링크 없는 카드는 건너뜀
      if (getComputedStyle(card).position === "static") card.style.position = "relative";
      var b = document.createElement("button");
      b.className = "ss-card-grab";
      b.textContent = "📥";
      b.title = "이 영상 담기";
      b.style.cssText =
        "position:absolute;top:8px;right:8px;z-index:99999;background:#1f6feb;color:#fff;" +
        "border:none;border-radius:16px;width:34px;height:34px;font-size:16px;" +
        "box-shadow:0 2px 8px rgba(0,0,0,.4);cursor:pointer";
      (function (card) {
        b.addEventListener("click", function (e) {
          // 클릭 시점에 카드에서 URL·썸네일·제목을 읽는다(SPA가 노드를 재사용해도 항상 현재 내용).
          e.preventDefault();
          e.stopPropagation();
          var cv = xhsCardLink(card);   // 토큰 있는 앵커 우선(위 주석 참조)
          var im = card.querySelector("a.cover img, img");
          var tt = card.querySelector("a.title, .footer .title");
          if (cv) openGrab(cv.href, im ? im.src : "", tt ? tt.textContent.trim() : "");
        });
      })(card);
      card.appendChild(b);
    }
  }

  // ── 카드별 버튼(앵커형): 틱톡·인스타 검색 그리드 ──
  // 틱톡 카드=a[href*="/video/"], 인스타 카드=a[href*="/p/"]·"/reel/". 카드가 <a>라서
  // note-item 방식과 달리 앵커 '안'에 버튼을 넣고, 클릭 시 이동을 막는다(2026-07-19 틱톡·인스타 실측).
  // ★인스타는 URL만으로 그리드를 못 가른다(2026-07-29 실측): 렌즈 검색으로 들어오는 화면이
  //   /explore/search/keyword/ 뿐 아니라 해시태그(/explore/tags/), 계정 프로필(/{id}/),
  //   릴스 탭(/{id}/reels/) 등 제각각이라 isGridPage()가 전부 false가 돼 버튼이 안 붙었다.
  //   → URL 대신 '화면 모양'으로 판단한다: 카드 크기(120px+) 게시물 앵커가 3개 이상 = 그리드.
  //   단일 게시물 페이지는 아래 '더 보기' 그리드가 있어도 isSinglePost()로 제외해 플로팅을 남긴다.
  // 단일 영상 뷰어로 넘어가면 카드 버튼을 걷어낸다(2026-08-03 틱톡 실사고: SPA 전환이라
  // 검색 그리드에 붙인 버튼이 DOM에 남아 플레이어 화면 위에 8개씩 떠다녔다).
  // data-ssgrab 표식도 같이 지워야 그리드로 돌아갔을 때 버튼이 다시 붙는다.
  function clearCardBtns() {
    var bs = document.querySelectorAll(".ss-card-grab");
    for (var i = 0; i < bs.length; i++) { try { bs[i].remove(); } catch (e) {} }
    var marked = document.querySelectorAll("[data-ssgrab]");
    for (var j = 0; j < marked.length; j++) { try { marked[j].removeAttribute("data-ssgrab"); } catch (e) {} }
  }
  function addAnchorCardBtns() {
    // ★아래 두 보정은 틱톡 전용(2026-08-03): 인스타에 전역 적용했더니 검색 그리드에서
    // 담기 버튼이 통째로 사라졌다(실사고 — 인스타는 모달 뷰어라 URL이 /p/로 바뀌어도
    // 그리드가 뒤에 살아 있고, img 실렌더 조건이 인스타 지연로딩 카드를 걸러버림).
    var tk = location.host.indexOf("tiktok") >= 0;
    if (isSinglePost()) {
      if (tk) clearCardBtns();   // 틱톡: SPA 뷰어에 그리드 버튼이 남아 떠다니는 것 제거
      return;                    // 공통: 뷰어에선 새 카드버튼 안 붙임(플로팅만) — 종전 동작
    }
    var links = document.querySelectorAll('a[href*="/video/"], a[href*="/p/"], a[href*="/reel/"]');
    var big = [];
    for (var k = 0; k < links.length; k++) {
      var rr = links[k].getBoundingClientRect();
      if (rr.width < 120 || rr.height < 120) continue;
      // 틱톡만: 썸네일이 실제로 그려진 카드에만 붙인다 — 뷰어의 투명/자리표시 앵커(빈
      // 검정칸)에 붙으면 버튼만 허공에 뜬다(2026-08-03 실사고의 나머지 절반).
      if (tk) {
        var im = links[k].querySelector("img");
        if (!im || im.getBoundingClientRect().width < 80) continue;
      }
      big.push(links[k]);
    }
    if (!isGridPage() && big.length < 3) return;
    for (var i = 0; i < big.length; i++) {
      var a = big[i];
      if (a.getAttribute("data-ssgrab")) continue;      // 중복 방지
      a.setAttribute("data-ssgrab", "1");
      if (getComputedStyle(a).position === "static") a.style.position = "relative";
      var b = document.createElement("button");
      b.className = "ss-card-grab";
      b.textContent = "📥";
      b.title = "이 영상 담기";
      // 인스타·틱톡은 카드 '오른쪽 위'에 자체 릴스/재생 배지가 있어 겹친다 → 왼쪽 위에 붙인다.
      b.style.cssText =
        "position:absolute;top:8px;left:8px;z-index:99999;background:#1f6feb;color:#fff;" +
        "border:none;border-radius:16px;width:34px;height:34px;font-size:16px;" +
        "box-shadow:0 2px 8px rgba(0,0,0,.4);cursor:pointer";
      (function (a) {
        b.addEventListener("click", function (e) {
          // 버튼이 앵커 안이라 세 단계로 링크 이동을 확실히 막는다(실측 검증).
          e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
          var im = a.querySelector("img, source");
          var thumb = im ? (im.src || (im.getAttribute("srcset") || "").split(" ")[0]) : "";
          var ttl = (im && im.alt) ? im.alt : "";
          openGrab(a.href, thumb, ttl);
        }, true);
      })(a);
      a.appendChild(b);
    }
  }

  // ── 카드별 버튼(도우인): 도우인 검색 카드는 <a href>·data-id가 없고(스크래핑 방지)
  //   영상 ID가 React 내부 props(__reactFiber$)에만 있다. 그런데 유저스크립트는 격리(sandbox)에서
  //   돌아 페이지가 DOM 노드에 박은 그 내부 프로퍼티가 '안 보인다'(2026-07-19 실측: sandbox에선
  //   첫 카드만 간헐 성공 = 사장님이 본 "맨 앞 하나만"의 정체). unsafeWindow로도 불안정했다.
  //   → 도우인만은 페이지 '메인월드'에 자립 스크립트를 주입한다. 메인월드에선 fiber가 다 보여
  //   20/20 카드에서 aweme_id 추출·버튼부착을 실측 확인했다.
  //   주입 스크립트가 자체 interval로 유지하며, 클릭 시 BASE/api/grab로 바로
  //   담는다(sandbox와의 데이터 왕래 불필요). 주입 실패 시 버튼이 안 생기고 플로팅으로 폴백된다.
  //
  // ⚠️★2026-08-17 정정 — "도우인 CSP는 인라인을 막지 않는다"는 옛 주석은 **틀렸다**.
  //   막는 주체는 도우인이 아니라 **확장 자신의 CSP**다. 격리월드(콘텐츠 스크립트) 코드가
  //   스스로 만든 <script>는 확장 CSP('unsafe-inline' 없음)의 검사를 받아 차단된다.
  //   사장님 콘솔 실측:
  //     grab_logic.js:716 Executing inline script violates ... 'script-src 'self'
  //     'wasm-unsafe-eval' 'inline-speculation-rules' http://localhost:* http://127.0.0.1:*
  //     chrome-extension://9adf66a6-.../'  → The action has been blocked.
  //   (localhost·chrome-extension: 이 소스에 있는 CSP는 도우인이 보낼 수 없다 = 확장 것)
  //   결과: 메인월드 도달 실패 → fiber 못 읽음 → 카드버튼 0개 → 플로팅만 남았다
  //   ("샤오·틱톡·인스타는 되는데 도우인만 안 된다"의 정체. 나머지는 DOM만 써서 주입이 불필요).
  //   ★해법: 확장은 manifest에 world:"MAIN" 으로 douyin_main.js를 **크롬이 직접** 주입한다
  //   (확장 CSP의 인라인 검사를 아예 타지 않는다). 그 경우 아래 주입은 건너뛴다 —
  //   같은 판단을 두 번 하지 않기 위해 __ssDouyinMW 플래그 하나로만 갈린다(0순위-B).
  //   유저스크립트(텀퍼몽키)는 world 선언이 없으므로 종전 주입 경로를 그대로 쓴다.
  function _douyinMainWorld() {
    if (window.__ssDouyinMW) return;
    window.__ssDouyinMW = true;
    // 격리월드는 페이지 window를 못 보므로 DOM에 표식을 남긴다(두 월드가 공유하는 유일한 통로).
    // 이걸 보고 addDouyinCardBtns가 중복 주입을 멈춘다.
    try { document.documentElement.setAttribute("data-ss-douyin-mw", "1"); } catch (e) {}
    var BASE = "https://shoppingshorts.duckdns.org";
    function isGrid() { return /(^|\/)(search|explore|tag)(\/|$|\?)/.test(location.pathname + location.search) || /\/search_result/.test(location.pathname); }
    // 메인월드는 별도 스코프라 위 헬퍼를 못 쓴다 — 같은 규칙을 여기서도 지킨다.
    // (그리드 카드는 대개 재생 전이라 빈 값이고, 그때는 종전대로 페이지 URL만 간다)
    var _MEDIA_HOSTS = ["zjcdn.com", "douyinvod.com", "xhscdn.com"];
    function currentVideoSrc() {
      try {
        var vs = document.querySelectorAll("video");
        for (var i = 0; i < vs.length; i++) {
          var cand = [vs[i].currentSrc, vs[i].src];
          for (var j = 0; j < cand.length; j++) {
            var u = cand[j] || "";
            if (u.indexOf("https://") !== 0) continue;
            for (var h = 0; h < _MEDIA_HOSTS.length; h++) if (u.indexOf(_MEDIA_HOSTS[h]) >= 0) return u;
          }
        }
      } catch (e) {}
      return "";
    }
    function openGrab(url, thumb, title, videoUrl) {
      window.open(BASE + "/api/grab?url=" + encodeURIComponent(url) + "&thumbnail=" + encodeURIComponent(thumb || "") + "&title=" + encodeURIComponent((title || "").slice(0, 120)) + (videoUrl ? "&video_url=" + encodeURIComponent(videoUrl) : ""), "ss_grab", "width=380,height=220");
    }
    function deepFindId(o, d) {
      if (!o || d > 4) return null;
      if (typeof o === "string") { var m = o.match(/\/video\/(\d{15,})/); if (m) return m[1]; return /^\d{18,20}$/.test(o) ? o : null; }
      if (typeof o !== "object") return null;
      for (var k in o) { if (/aweme.?id|awemeId/i.test(k)) { var v = String(o[k]); if (/^\d{15,}$/.test(v)) return v; } }
      try { for (var k2 in o) { if (k2 === "return" || k2 === "_owner" || k2 === "stateNode" || k2 === "child" || k2 === "sibling") continue; var r = deepFindId(o[k2], d + 1); if (r) return r; } } catch (e) {}
      return null;
    }
    function fiberKey(el) { for (var kk in el) { if (kk.indexOf("__reactFiber$") === 0) return kk; } return null; }
    function findId(el) {
      for (var d = 0; d < 9 && el; d++, el = el.parentElement) {
        try { var fk = fiberKey(el); if (fk) { var f = el[fk]; for (var i = 0; i < 12 && f; i++, f = f.return) { var id = deepFindId(f.memoizedProps, 0); if (id) return id; } } } catch (e) {}
      }
      return null;
    }
    function tick() {
      if (!isGrid() || location.host.indexOf("douyin") < 0) return;
      var imgs = document.querySelectorAll("img");
      for (var j = 0; j < imgs.length; j++) {
        var img = imgs[j], ir = img.getBoundingClientRect();
        if (ir.width < 150 || ir.height < 150) continue;
        var id0 = findId(img); if (!id0) continue;
        // 같은 aweme_id에 이미 버튼이 있으면 건너뜀(도우인이 숨은 단열 레이아웃을 중복 렌더해도 1개만).
        if (document.querySelector('.ss-card-grab[data-aid="' + id0 + '"]')) continue;
        // ★box는 img의 '부모'부터 찾는다 — img는 void 요소라 appendChild해도 렌더가 안 돼(0×0)
        //   19/20 카드가 안 보였던 원인. 부모 컨테이너(썸네일 래퍼)에 붙여야 카드 위에 뜬다.
        var box = img.parentElement;
        while (box && box !== document.body) { var r = box.getBoundingClientRect(); if (r.width >= 150 && r.width < 440 && r.height >= 180) break; box = box.parentElement; }
        if (!box || box === document.body || box.querySelector(".ss-card-grab")) continue;
        if (getComputedStyle(box).position === "static") box.style.position = "relative";
        var b = document.createElement("button");
        b.className = "ss-card-grab"; b.setAttribute("data-aid", id0); b.textContent = "📥"; b.title = "이 영상 담기";
        b.style.cssText = "position:absolute;top:8px;right:8px;z-index:99999;background:#1f6feb;color:#fff;border:none;border-radius:16px;width:34px;height:34px;font-size:16px;box-shadow:0 2px 8px rgba(0,0,0,.4);cursor:pointer";
        (function (img) {
          b.addEventListener("click", function (e) {
            e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
            var id = findId(img);
            if (id) openGrab("https://www.douyin.com/video/" + id, img.src || "", img.alt || "", currentVideoSrc());
          }, true);
        })(img);
        box.appendChild(b);
      }
    }
    tick(); setInterval(tick, 2000);
  }
  function addDouyinCardBtns() {
    if (location.host.indexOf("douyin") < 0) return;
    // ★확장(world:"MAIN")이 이미 메인월드에서 돌고 있으면 주입하지 않는다.
    //   __ssDouyinMW는 메인월드에서 세워지는 플래그다. 격리월드에선 페이지 window가
    //   분리돼 이 값이 안 보이므로, 확장 경로에선 douyin_main.js가 DOM에 표식을 남기고
    //   여기서 그 표식을 읽는다(DOM은 두 월드가 공유한다 — 유일하게 확실한 통로).
    try {
      if (document.documentElement.getAttribute("data-ss-douyin-mw") === "1") return;
    } catch (e) {}
    if (window.__ssDouyinMW) return;         // 유저스크립트 unsafeWindow 등에서 보이는 경우
    if (window.__ssDouyinInjected) return;   // 한 번만 주입(주입된 스크립트가 자체 interval로 유지)
    window.__ssDouyinInjected = true;
    try {
      var sc = document.createElement("script");
      sc.textContent = "(" + _douyinMainWorld.toString() + ")();";
      (document.head || document.documentElement).appendChild(sc);
      sc.remove();
      // ⚠️확장 CSP가 막으면 위 appendChild는 **예외를 안 던지고** 조용히 실행만 안 된다
      //   (콘솔에 CSP 위반만 찍힌다). 그래서 catch로는 실패를 알 수 없다 —
      //   실패해도 다음 tick에 재시도하도록 플래그를 되돌린다. 성공했다면 메인월드가
      //   표식을 남기므로 위 return에서 걸러진다(무한 재주입 안 함).
      window.__ssDouyinInjected = false;
    } catch (e) { window.__ssDouyinInjected = false; }   // 실패 시 다음 tick에 재시도(폴백=플로팅)
  }


  // ── 버튼 자리: 화면 오른쪽 끝 → **영상 칸 바로 옆**(2026-09-01 사장님 요청) ─────
  //   종전엔 right:18px 고정이라 사이트 UI(쓰레드 '메시지' 팝업 등)와 겹쳤고,
  //   넓은 화면에선 영상에서 한참 떨어진 구석에 붙어 있었다.
  //   자리 판단은 **여기 한 곳에서만** 한다(0순위-B) — 만드는 쪽은 right:18px로 두고,
  //   이 함수가 매 tick에 left로 덮어쓴다. 못 정하면 종전 자리 그대로 둔다.
  // 위→아래 순서. 지금 화면에 있는 것만 골라 빈칸 없이 연속으로 쌓는다.
  var DOCK_IDS = ["ss-adopt-btn", "ss-favch-btn", "ss-lens-btn", "ss-chadd-btn", "ss-grab-btn"];
  var DOCK_STEP = 52;      // 버튼 세로 간격
  function _dockAnchor() {
    // 가장 큰 <video>가 지금 보는 영상이다.
    var vs = document.querySelectorAll("video"), best = null, area = 0;
    for (var i = 0; i < vs.length; i++) {
      var r = vs[i].getBoundingClientRect();
      if (r.width * r.height > area) { area = r.width * r.height; best = vs[i]; }
    }
    if (!best || area < 10000) return null;
    var v = best.getBoundingClientRect();
    var right = v.right;
    // ★조상 칸을 쓰되 '영상보다 지나치게 넓은 칸'은 버린다(2026-09-01 실사고).
    //   유튜브 쇼츠의 ytd-reel-video-renderer는 **화면 전체 폭**이라, 그걸 그대로 쓰면
    //   버튼이 브라우저 오른쪽 끝(주소창 밑)까지 날아갔다. 액션열까지만 감싸는 칸이 목표다.
    var el = best.parentElement, guard = 0;
    while (el && guard++ < 6) {
      var rr = el.getBoundingClientRect();
      if (rr.width <= v.width * 1.6 && rr.right > right && rr.right < window.innerWidth) right = rr.right;
      el = el.parentElement;
    }
    // 액션열(좋아요·댓글·공유)이 영상 **바깥 형제**인 경우(유튜브 쇼츠) — 따로 찾아 넘는다.
    var rails = document.querySelectorAll("#actions,ytd-reel-player-overlay-renderer #actions");
    for (var k = 0; k < rails.length; k++) {
      var q = rails[k].getBoundingClientRect();
      if (q.height < 100 || q.width > 200) continue;                 // 세로 아이콘 열만
      if (q.left < v.right - 40 || q.right > v.right + 300) continue; // 이 영상 옆의 것만
      if (q.right > right) right = q.right;
    }
    if (right <= 0 || right >= window.innerWidth) return null;
    return { top: v.top, bottom: v.bottom, right: right };
  }
  function _dockBtns() {
    var rr = _dockAnchor();
    var x = rr ? rr.right : 0;
    // 버튼 4개: 영상 칸 오른쪽 + **위에서부터** 아래로(2026-09-01 사장님 요청 —
    // 종전엔 아래에 깔려 사이트 액션 아이콘·'메시지' 팝업과 겹쳤다).
    // ★스크롤로 영상이 화면 위로 밀리면 rr.top이 음수가 된다. 종전엔 각 버튼이
    //   Math.max(8, rr.top + 8 + slot*STEP)라 **전부 top:8로 눌려 한 자리에 포개졌다**
    //   (2026-09-02 사장님 "스크롤 조금 내리면 합쳐진다"). 바닥값을 버튼별로 두지 말고
    //   **기준선 하나를 먼저 정하고** 거기서 간격을 더한다 — 그러면 절대 겹치지 않는다.
    var live = [];
    for (var i0 = 0; i0 < DOCK_IDS.length; i0++) {
      var e0 = document.getElementById(DOCK_IDS[i0]);
      if (e0) live.push(e0);
    }
    // 영상이 화면에서 거의 사라졌으면 버튼도 숨긴다(엉뚱한 자리에 떠 있는 것보다 낫다).
    var gone = !!rr && (rr.bottom < 120 || rr.top > window.innerHeight - 80);
    var base = rr ? Math.max(8, Math.min(rr.top + 8,
                 window.innerHeight - 8 - live.length * DOCK_STEP)) : 0;
    var slot = 0;
    for (var i = 0; i < live.length; i++) {
      var el = live[i];
      el.style.display = gone ? "none" : "";
      if (gone) continue;
      // 화면 밖으로 밀리면(좁은 창) 종전 오른쪽 아래 자리로 되돌린다.
      var w = el.offsetWidth || 150;
      if (!rr || x + 16 + w + 12 > window.innerWidth) {
        el.style.left = ""; el.style.right = "18px"; el.style.top = ""; el.style.bottom = "";
      } else {
        el.style.right = "auto"; el.style.left = (x + 16) + "px";
        el.style.bottom = "auto";
        el.style.top = (base + slot * DOCK_STEP) + "px";
        slot++;
      }
    }
    // 시크바: 버튼과 겹치지 않게 **영상 아래쪽**에 붙인다(폭은 만들 때 줄여둔다).
    var sk = document.getElementById("ss-seek");
    if (sk) {
      sk.style.display = gone ? "none" : "";
      if (gone) return;
      if (!rr) { sk.style.left = ""; sk.style.right = "18px"; sk.style.bottom = "174px"; }
      else {
        var sw = sk.offsetWidth || 260;
        var sx = x + 16;
        if (sx + sw + 12 > window.innerWidth) sx = Math.max(8, window.innerWidth - sw - 12);
        sk.style.right = "auto"; sk.style.left = sx + "px";
        sk.style.bottom = Math.max(8, window.innerHeight - rr.bottom + 8) + "px";
      }
    }
  }

  // ── 유튜브는 '쇼츠'에서만 동작한다 (2026-09-02 사장님 요청) ──────────────
  //   메인·구독·검색·채널 등 목록 화면과 **롱폼(watch)** 에선 버튼을 아예 띄우지 않는다.
  //   예외: 공유 링크로 열린 쇼츠는 /watch?v=... 로 뜨기도 한다 → 재생 중인 영상 길이가
  //   3분 이하이면 쇼츠로 보고 허용한다(길이를 못 읽으면 롱폼으로 간주해 끈다).
  function _ytOff() {
    var h = location.host;
    if (h.indexOf("youtube.com") < 0 && h.indexOf("youtu.be") < 0) return false;
    if (/^\/shorts\//.test(location.pathname)) return false;      // 쇼츠 = 동작
    if (/^\/watch/.test(location.pathname) || h.indexOf("youtu.be") >= 0) {
      var v = document.querySelector("video");
      var d = v && isFinite(v.duration) ? v.duration : 0;
      if (d > 0 && d <= 180) return false;                        // watch로 열린 쇼츠
    }
    return true;                                                  // 그 외 유튜브 = 끔
  }
  // 유튜브 비대상 화면에서 이미 붙은 것들을 걷어낸다(SPA 이동 대응).
  function _ytClear() {
    try {
      var els = document.querySelectorAll(
        "#ss-grab-btn,#ss-chadd-btn,#ss-lens-btn,#ss-adopt-btn,#ss-seek,.ss-card-grab");
      for (var i = 0; i < els.length; i++) els[i].remove();
    } catch (e) {}
  }

  function tick() { if (_ytOff()) { _ytClear(); return; } try{addFloatBtn();}catch(e){} try{addCardBtns();}catch(e){} try{addAnchorCardBtns();}catch(e){} try{addDouyinCardBtns();}catch(e){} try{syncFloat();}catch(e){} try{syncChannelBtn();}catch(e){} try{syncExtraBtns();}catch(e){} try{syncSeekBar();}catch(e){} try{syncGridBadges();}catch(e){} try{_dockBtns();}catch(e){} }
  tick();
  // SPA라 스크롤·재검색으로 카드가 갈아끼워져도 버튼을 계속 유지한다.
  // 핸들을 남긴다 — 더 새로운 로직이 로드되면 위 가드가 이걸 끄고 이어받는다.
  window.__ssGrabTimer = setInterval(tick, 2000);
})();
