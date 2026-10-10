// 로또 · 원클릭 담기 — 실제 로직 (grab.user.js 로더가 서버에서 이 파일을 매번 불러와 실행).
// ★이 파일을 고치면 모든 사용자가 다음 새로고침에 자동 반영된다(재설치 불필요).
// 로직 버전: 2026-10-08e  (LOGIC_VER가 정본)
//   · 관제 156 — 고정 검색 머리에 덮인 카드 📥·배지 숨김(elementsFromPoint, 짐작 수리 재수정).
//   · 관제 156 — 관련 검색어 상자 접기(검색 판과 같이, 접힌 채 기억), 판매자 태그 맨 위·검색창 기본값, 기다리는 초 표시.
//   · 관제 156 — 유튜브 Shorts 검색 카드 배지(날짜·조회·좋아요·댓글·길이)·조회수/좋아요/댓글/최신순, 게시물 상자 검색창.
//   · 관제 156 — 렌즈에 보고 있는 화면 캡처를 그대로 실음(유튜브가 썸네일로만 찾던 것).
//   · 관제 156 — 렌즈 한 클릭 두 번 발사 막기(DOM 표식), 옛 번호 로직 이어받을 때 옛 버튼 걷기.
//   · 관제 156 — 판매자 해시태그 줄, 유튜브 Shorts 탭 자동 선택·미리보기 📥 제자리, 인스타 접힌 카드 배지 숨김.
//   · 관제 156 — 미리보기는 서버 부담 없는 것만: 렌즈 결과창 서버 재생 끔, 동시 미리보기를 틱톡·핀·도우인·샤오홍슈로.
//   · 관제 156 — 렌즈 서버 연결 실패(30초 상한 회귀) 수리, 유튜브 검색 Shorts 전용, 인스타 카드 배지 스크롤 겹침.
//   · 관제 156 — 검색어 판 한 줄 5개 언어로 통일·끌어 옮기기, 게시물 관련 검색어 5개 언어, '찾는 중…' 영구 멈춤,
//     유튜브 미리보기 📥 겹침, 인스타 게시물 재생바가 뒤 격자 영상을 잡던 것, 렌즈 결과창 마우스 지나감 미리보기.
//   · 인스타 검색 화면 — 카드 배지 ❤좋아요·💬댓글·⏱길이, 좋아요순·댓글순 목록, 마우스 지나간 카드 동시 미리보기(관제 151, 계정02 로그인 실측).
//   · 검색어 기능을 유튜브·틱톡·핀터레스트·샤오홍슈·도우인까지(오른쪽 검색 판 + 영상 화면 관련 검색어), 렌즈 결과창 크게(관제 151).
//   · 인스타 — 비슷한 검색어를 5개 언어(한·영·일·중·러) 줄로, 팝업 관련 검색어가 "만드는 중…"에서 멈추던 것 수정(관제 151).
//   · 인스타 — 키워드 검색 제목을 검색창으로(한글→영어 검색), 비슷한 검색어 칩, 게시물 팝업 관련 검색어(관제 151).
//     같은 날 관제 150이 20261007을 썼다 → 한 칸 올린다.
//   · 유튜브 — 검색→쇼츠로 가면 숨은 검색 카드 📥 때문에 쇼츠 화면 📥 담기가 꺼지던 것,
//     검색 카드에 마우스를 올리면 미리보기 영상이 📥를 덮던 것(관제 150).
//   · 인스타 팝업·게시물 화면 — 버튼을 본문 칸 바깥 오른쪽으로(관제 094). 같은 날 핀터레스트 수정이
//     20261003을 이미 썼다 → 한 칸 올려야 옛 확장 동봉본을 새 로직이 이어받는다.
//   · 핀터레스트 — 핀 페이지 플로팅 담기 + 검색 그리드 카드마다 📥 (2026-09-11 고객 문의)
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
  var LOGIC_VER = 20261021;
  if ((window.__ssGrabVer || 0) >= LOGIC_VER) return;   // 같거나 더 새것이 이미 돎
  // ★옛 '번호 있는' 로직을 이어받을 때도 그 버튼을 걷는다(관제 156): 버튼은 id 선점이라 옛 것이 남으면
  //   그 옛 클릭 처리(예: 30초에 끊는 렌즈)가 계속 돈다 — 새 로직이 떠도 '서버 연결 실패'가 났다.
  if (window.__ssGrabLoaded) {
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
  var _MEDIA_HOSTS = ["zjcdn.com", "douyinvod.com", "xhscdn.com", "rednotecdn.com", "pinimg.com"];
  function _mediaFromPageHtml() {
    // RedNote의 새 플레이어는 실제 mp4를 MediaSource에 넣고 <video src>에는 blob:만
    // 남긴다(2026-09-14 라이브 실측). 그래도 현재 노트의 직접 mp4는 렌더된 DOM 안에
    // sns-v*.rednotecdn.com/...mp4로 남아 있으므로, 사람이 담기를 누르는 그 순간 찾는다.
    // 매 tick마다 큰 DOM을 훑지 않고 currentVideoSrc() 호출 때만 실행한다.
    try {
      var html = document.documentElement.innerHTML || "";
      var ms = html.match(/https:\/\/[^\"'<>\\\s]*(?:xhscdn|rednotecdn|pinimg)\.com\/[^\"'<>\\\s]*\.mp4(?:\?[^\"'<>\\\s]*)?/gi) || [];
      return ms.length ? ms[0].replace(/&amp;/g, "&") : "";
    } catch (e) {}
    return "";
  }
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
    return _mediaFromPageHtml();
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
      "padding:16px;max-width:1600px;width:96vw;max-height:92vh;overflow:auto;position:relative'>" +   // 크게(2026-10-07 사장님 '화면만큼')
      "<button id='ss-lens-x' type='button' style='position:absolute;" +
      "top:6px;right:12px;background:none;border:none;color:#fff;font-size:22px;cursor:pointer'>✕</button>" +
      "<div style='font-weight:800;margin-bottom:10px'>🔍 원본·유사 레퍼런스</div>" + html + "</div>";
    // ★✕는 addEventListener로 묶는다(2026-09-22 사장님 제보: 인스타에서 ✕가 안 닫힘).
    //   인라인 onclick=은 페이지 CSP(인스타: 'unsafe-inline' 없음)가 실행을 막는다 —
    //   그래서 아래 '담기' 버튼도 onclick='void(0)'만 두고 JS로 묶어 왔다. ✕만 인라인에
    //   기대고 있었다. 배경 클릭은 위에서 이미 JS로 묶여 있어 그것만 됐던 것.
    var x = document.getElementById("ss-lens-x");
    if (x) x.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); o.remove(); });
  }
  // ── 렌즈 결과창 마우스 올림 미리보기(관제 156, 2026-10-07 사장님 "인스타처럼 마우스 쭉 지나가면 재생") ──
  //   카드엔 썸네일·주소뿐이다. 서버 /api/play(받아서 mp4로 주는 길)를 **로그인 중계로** 받아
  //   이 페이지의 blob 영상으로 튼다 — 남의 사이트 위 <video src=우리서버>는 쿠키가 없어 401(실측).
  //   지나간 카드는 계속 재생(최대 9개, 인스타 동시 미리보기와 같은 규칙). 지원: 유튜브·틱톡·인스타.
  function _playKey(url) {
    var u = String(url || ""), m;
    if ((m = /youtube\.com\/(?:shorts\/|watch\?v=)([\w-]{6,})/.exec(u)) || (m = /youtu\.be\/([\w-]{6,})/.exec(u))) return ["youtube", m[1]];
    if ((m = /tiktok\.com\/.*\/video\/(\d+)/.exec(u))) return ["tiktok", m[1]];
    if ((m = /instagram\.com\/(?:[\w.]+\/)?(?:p|reel|reels|tv)\/([\w-]+)/.exec(u))) return ["instagram", m[1]];
    return null;
  }
  var _lensBlobs = {}, _lensPlaying = [];
  function _gmBlob(url, done) {
    if (typeof GM_xmlhttpRequest !== "undefined") {
      GM_xmlhttpRequest({ method: "GET", url: url, responseType: "blob", timeout: 60000,
        onload: function (r) { done(r.status === 200 && r.response ? URL.createObjectURL(r.response) : ""); },
        onerror: function () { done(""); }, ontimeout: function () { done(""); } });
      return;
    }
    var reqId = "sb" + Math.random().toString(36).slice(2), ended = false;
    var timer = setTimeout(function () { fin(""); }, 60000);
    function fin(u) { if (ended) return; ended = true; clearTimeout(timer); window.removeEventListener("message", onMsg); done(u); }
    function onMsg(ev) {
      var d = ev && ev.data;
      if (!d || d.reqId !== reqId || !d.__ssGmResult) return;
      if (d.status !== 200 || !d.b64) { fin(""); return; }
      try {
        var bin = atob(d.b64), u8 = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
        fin(URL.createObjectURL(new Blob([u8], { type: d.type || "video/mp4" })));
      } catch (e) { fin(""); }
    }
    window.addEventListener("message", onMsg);
    window.postMessage({ __ssGmFetch: true, reqId: reqId, method: "GET", url: url, b64: true }, "*");
  }
  function _lensHoverPlay(card) {
    if (card.__ssPv) return;
    var pk = _playKey(card.getAttribute("data-play"));
    if (!pk) return;
    card.__ssPv = 1;
    var box = card.querySelector(".ss-pv-box");
    var tag = document.createElement("div");
    tag.textContent = "▶ 불러오는 중…";
    tag.style.cssText = "position:absolute;left:6px;bottom:6px;background:rgba(0,0,0,.7);color:#fff;font-size:11px;padding:2px 6px;border-radius:6px";
    box.appendChild(tag);
    var key = pk[0] + ":" + pk[1];
    function put(src) {
      if (!src) { tag.textContent = "미리보기 불가"; card.__ssPv = 0; return; }
      _lensBlobs[key] = src; tag.remove();
      var v = document.createElement("video");
      v.src = src; v.muted = true; v.loop = true; v.playsInline = true; v.autoplay = true;
      v.style.cssText = "position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#000";
      box.appendChild(v);
      try { v.play().catch(function () {}); } catch (e) {}
      _lensPlaying.push(v);
      while (_lensPlaying.length > 9) { var o = _lensPlaying.shift(); try { o.pause(); } catch (e) {} }
    }
    if (_lensBlobs[key]) { put(_lensBlobs[key]); return; }
    _gmBlob(BASE + "/api/play?platform=" + pk[0] + "&id=" + encodeURIComponent(pk[1]), put);
  }
  function _lensHoverWire(ov) {
    var cards = ov.querySelectorAll("[data-play]");
    for (var i = 0; i < cards.length; i++) {
      (function (c) {
        var t = 0;
        c.addEventListener("mouseenter", function () { t = setTimeout(function () { _lensHoverPlay(c); }, 250); });
        c.addEventListener("mouseleave", function () { clearTimeout(t); });   // 지나가기만 해도(250ms) 켜지고, 켜진 건 계속 재생
      })(cards[i]);
    }
  }
  function _esc(s) { return String(s || "").replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  // ── 인스타 시크바(2026-08-03 사장님: 장면 이동이 안 돼 앞으로 못 돌아감) ──
  // 인스타 플레이어엔 시크바가 없지만 <video>는 페이지 DOM이라 currentTime을 직접
  // 움직일 수 있다(영상 소스가 CDN(교차출처)이어도 재생 제어는 무관). 지금 재생 중인
  // 비디오를 골라 슬라이더로 앞뒤 이동 + 렌즈에 '보고 있는 그 장면'(초)을 실어 보낸다.
  function _igVideo() {
    // ★팝업(게시물 창)이 떠 있으면 그 안의 영상만 본다(관제 156, 2026-10-07 사장님 "옆쪽 타임조절기가 안 먹음").
    //   인스타 검색 화면에서 게시물을 열면 뒤쪽 격자 영상이 동시 미리보기로 계속 재생 중이라,
    //   '재생 중인 첫 영상'을 고르면 팝업 영상이 아니라 뒤 격자 영상을 조절하고 있었다.
    var dv = document.querySelectorAll('[role="dialog"] video');
    var vs = dv.length ? dv : document.querySelectorAll("video"), best = null;
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
  // ★재생바 자리는 _dockBtns 한 곳에서만 정한다(0순위-B). 2026-09-02엔 여기(_placeSeekBar:
  //   top+right)와 _dockBtns(left+bottom)가 같은 tick에서 따로 정해 **넷이 다 걸려** 상자가
  //   담기 버튼 밑에서 영상 바닥까지 시커멓게 늘어났다(사장님 스샷 3장). 두 번 적지 마라.

  function syncSeekBar() {
    if (!_playerPlat()) return;
    // 게시물 창이 열리면 뒤 격자의 동시 미리보기는 멈춘다 — 재생바·소리가 그쪽에 섞이지 않게(관제 156).
    if (isSinglePost() && _pvList.length) _pvStopAll();
    var box = document.getElementById("ss-seek");
    if (!_isVideoPage()) { if (box) box.remove(); return; }
    var v = _igVideo();
    if (!v) { if (box) box.remove(); return; }
    if (!box) {
      box = document.createElement("div");
      box.id = "ss-seek";
      // ★자리는 _dockBtns가 정한다 — 여기 값은 첫 그림 전 잠깐 쓰는 초기값이다.
      box.style.cssText = "position:fixed;right:18px;bottom:174px;height:auto;width:auto;z-index:2147483647;background:rgba(20,20,20,.92);" +
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
    // 자리는 _dockBtns가 정한다 — 여기서 top/right를 건드리지 마라(검은 판 사고).
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
  // ── 인스타 검색 응답 숫자(관제 151) — ig_main.js(메인월드)가 postMessage로 넘긴다 ──
  var _igMedia = {}, _igMediaN = 0;
  window.addEventListener("message", function (ev) {
    var d = ev && ev.data;
    if (ev.source !== window || !d || !d.__ssIgMedia || !d.items || !d.items.length) return;
    for (var i = 0; i < d.items.length; i++) {
      var it = d.items[i];
      if (!it || !it.code) continue;
      if (!_igMedia[it.code]) _igMediaN++;
      _igMedia[it.code] = it;
    }
    try { _ovIgCollect(d.items); } catch (e) {}
  });
  // ── 🌐 해외 레퍼런스 수집(관제 162, 2026-10-08 사장님 "유튜브 인스타 먼저") — 관리자 전용 ──
  //   인스타가 스스로 받은 검색 응답(위 ig_main.js)에서 **계정 이름만** 서버로 보낸다. 추가 요청 0, 프록시 0원.
  //   켜기/끄기·카테고리는 화면 오른쪽 아래 작은 선택칸(인스타 도메인 localStorage). 판단·저장은 서버
  //   overseas_ref.add_instagram 한 곳 — 여기선 모아서 보내기만 한다.
  var _OV_CATS = ["국뽕", "스포츠", "동물", "해외반응", "랭킹형", "웃긴"];
  var _ovSent = {}, _ovQ = [], _ovT = 0;
  function _ovCat() { try { return localStorage.getItem("ssOvCat") || ""; } catch (e) { return ""; } }
  function _ovIgCollect(items) {
    if (window.__ssIsAdmin !== true || !_ovCat()) return;
    var q = location.pathname.indexOf("/explore/search/keyword") === 0 ? (new URLSearchParams(location.search).get("q") || "") : "";
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      if (!it || !it.user || _ovSent[it.code]) continue;
      _ovSent[it.code] = 1;
      _ovQ.push({ user: it.user, code: it.code, likes: it.likes || 0, plays: it.plays || 0, caption: it.caption || "", q: q });
    }
    if (_ovQ.length && !_ovT) _ovT = setTimeout(function () {
      _ovT = 0;
      var batch = _ovQ.splice(0, 100);
      _gmPost(BASE + "/api/overseas_ref/ig_add", { cat: _ovCat(), items: batch }, function (st, tx) {
        var el = document.getElementById("ss-ov-n");
        try { var d = JSON.parse(tx); if (el && d.ok) el.textContent = "+" + d.new + " (" + d.total + ")"; } catch (e) {}
      }, function () {});
    }, 1500);
  }
  function syncOvBox() {
    if (location.host.indexOf("instagram.com") < 0 || window.__ssIsAdmin !== true || !document.body) return;
    if (document.getElementById("ss-ov-box")) return;
    var b = document.createElement("div");
    b.id = "ss-ov-box";
    b.style.cssText = "position:fixed;left:12px;bottom:12px;z-index:2147483647;background:#0f1512;color:#e6efe9;" +
      "border:1px solid #37e0bd;border-radius:10px;padding:6px 8px;font:12px system-ui,sans-serif;display:flex;gap:6px;align-items:center";
    var cur = _ovCat();
    b.innerHTML = '🌐 해외수집 <select id="ss-ov-sel" style="font:12px system-ui;background:#0b110e;color:#e6efe9;border:1px solid #1e2a24;border-radius:6px">' +
      '<option value="">끔</option>' + _OV_CATS.map(function (c) { return '<option' + (c === cur ? " selected" : "") + ">" + c + "</option>"; }).join("") +
      '</select><span id="ss-ov-n" style="color:#8fa39a"></span>';
    document.body.appendChild(b);
    document.getElementById("ss-ov-sel").addEventListener("change", function () {
      try { localStorage.setItem("ssOvCat", this.value); } catch (e) {}
      if (this.value) { var all = []; for (var c in _igMedia) all.push(_igMedia[c]); _ovIgCollect(all); }
    });
  }
  if (location.host.indexOf("instagram.com") >= 0) {
    try { window.postMessage({ __ssIgMediaReq: true }, location.origin); } catch (e) {}
    setTimeout(function () { try { window.postMessage({ __ssIgMediaReq: true }, location.origin); } catch (e) {} }, 3000);
  }
  function _fmtSec(s) {
    if (s == null || !isFinite(s)) return "";
    s = Math.round(s);
    return s >= 60 ? Math.floor(s / 60) + "분" + (s % 60 ? (s % 60) + "초" : "") : s + "초";
  }
  function _igMediaBadge(md, date) {
    var parts = [];
    if (date) parts.push("📅 " + date);
    if (md.plays != null) parts.push("▶" + _fmtN(md.plays));
    if (md.likes != null) parts.push("❤" + _fmtN(md.likes));
    if (md.comments != null) parts.push("💬" + _fmtN(md.comments));
    if (md.dur != null) parts.push("⏱" + _fmtSec(md.dur));
    return parts.join(" ");
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
        // ★z-index 는 카드 안에서만 이기면 된다(관제 156, 2026-10-07 사장님 "스크롤 내리면 화면이 깨진다").
        //   99998 이면 인스타 검색 화면의 고정 머리(검색창·비슷한 검색어 판) 위로 스크롤된 윗줄 카드 배지가 튀어나왔다.
        el.style.cssText = "position:absolute;right:6px;bottom:6px;z-index:3;" +
          "background:rgba(0,0,0,.65);color:#fff;font:11px system-ui,sans-serif;" +
          "border-radius:8px;padding:2px 7px;pointer-events:none";
        a.appendChild(el);
      }
      if (el.getAttribute("data-c") !== code) {        // SPA 노드 재사용 대비
        el.setAttribute("data-c", code);
        el.removeAttribute("data-q");
        el.removeAttribute("data-m");
        var dd = _fmtDate(_igDate(code));
        el.textContent = dd ? "📅 " + dd.slice(2) : "";
      }
      // 인스타가 스스로 받은 검색 응답의 숫자(ig_main.js가 넘겨 줌) — 좋아요·댓글·길이(관제 151)
      var md = _igMedia[code];
      if (md && el.getAttribute("data-m") !== "1") {
        el.setAttribute("data-m", "1");
        var d0 = _fmtDate(_igDate(code));
        el.textContent = _igMediaBadge(md, d0 ? d0.slice(2) : "");
      }
      // 카드별 🔍렌즈 — 페이지 이동 없이 이 화면에서 오버레이로(2026-08-03 사장님 요청)
      var lb = a.querySelector(".ss-card-lens");
      if (!lb) {
        lb = document.createElement("button");
        lb.className = "ss-card-lens";
        lb.textContent = "🔍";
        lb.title = "이 영상 렌즈(원본·유사 추적)";
        // 위치: 우리 배지(우하단) 바로 위 — 좌하단은 인스타 자체 조회수 표기가 있어 피한다
        lb.style.cssText = "position:absolute;right:6px;bottom:32px;z-index:4;" +
          "background:#37b0e0;color:#fff;border:none;border-radius:14px;width:28px;height:28px;" +
          "font-size:13px;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.4)";
        lb.addEventListener("click", function (e) {
          e.preventDefault(); e.stopPropagation();
          var c = el.getAttribute("data-c");     // 클릭 시점의 현재 카드(SPA 재사용 대비)
          if (c) _lensRun("https://www.instagram.com/reel/" + c + "/", true);
        });
        a.appendChild(lb);
      }
      if (!md && !el.getAttribute("data-q") && r.bottom > 0 && r.top < innerHeight) {
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
  function _gmPost(url, bodyObj, done0, fail0, ms) {
    // ★상한(기본 30초, 관제 156, 2026-10-07 사장님 "비슷한 검색어 찾는 중으로 계속 나온다").
    //   브리지가 ACK만 하고 결과를 못 돌려주면(탭 이동·서비스워커 잠듦) 아무도 fail 을 안 불러
    //   화면이 '찾는 중…'에 영원히 멈췄다. 끝은 한 번만 — 늦게 온 응답은 버린다.
    // ★상한은 부르는 쪽이 정한다(기본 30초). 렌즈 추적은 서버에서 70초 넘게 걸린다(2026-10-07 라이브 실측:
    //   20:28:39 요청 → 20:29:49 200) — 30초로 끊었더니 정상 응답을 버리고 '서버 연결 실패'가 떴다.
    var ended = false, timer = setTimeout(function () { end(); if (fail0) fail0("timeout"); }, ms || 30000);
    function end() { if (ended) return false; ended = true; clearTimeout(timer); return true; }
    function done(st, tx) { if (end()) done0(st, tx); }
    function fail(why) { if (end() && fail0) fail0(why); }
    if (typeof GM_xmlhttpRequest !== "undefined") {
      GM_xmlhttpRequest({ method: "POST", url: url,
        headers: { "Content-Type": "application/json" }, data: JSON.stringify(bodyObj),
        onload: function (r) { done(r.status, r.responseText); }, onerror: fail, ontimeout: fail });
      return;
    }
    var reqId = "ss" + Math.random().toString(36).slice(2), acked = false;
    function onMsg(ev) {
      var d = ev && ev.data;
      if (!d || d.reqId !== reqId) return;
      if (d.__ssGmAck) { acked = true; return; }   // 브리지 살아있음 — 본 응답 대기
      if (!d.__ssGmResult) return;
      window.removeEventListener("message", onMsg);
      if (d.status > 0) done(d.status, d.text); else fail(d.stale ? "stale" : "");
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
  function _snapFrame(v) {
    try {
      if (!v || !v.videoWidth) return "";
      var k = Math.min(1, 1280 / Math.max(v.videoWidth, v.videoHeight));
      var c = document.createElement("canvas");
      c.width = Math.round(v.videoWidth * k); c.height = Math.round(v.videoHeight * k);
      c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
      var d = c.toDataURL("image/jpeg", 0.85);        // 교차 출처면 여기서 throw → ""
      return d.length < 3500000 ? d : "";
    } catch (e) { return ""; }
  }
  function _lensRun(url, noT) {
    // ★같은 영상 렌즈 두 번 발사 막기(관제 156, 2026-10-08 서버 실측: 10-02부터 448건 중 13건이 같은 초에 2건 —
    //   렌즈 비용도 두 번). 로직이 두 벌(옛 확장 동봉본 + 새 로직, 서로 다른 격리 월드라 window 변수를 못 본다)
    //   돌면 한 클릭을 둘이 받는다. 두 벌이 **같이 보는 것은 DOM 뿐**이라 표식을 DOM 에 둔다.
    try {
      var de = document.documentElement, mark = de.getAttribute("data-ss-lens-run") || "", now = Date.now();
      var mk = String(url || "");
      if (mark && mark.slice(mark.indexOf("|") + 1) === mk && now - (+mark.slice(0, mark.indexOf("|")) || 0) < 5000) return;
      de.setAttribute("data-ss-lens-run", now + "|" + mk);
    } catch (e) {}
    // noT=true: 그리드 카드에서 실행 — 화면의 다른(호버 재생) 비디오 시각을 잘못 싣지 않게
    // t를 빼고 보낸다(서버가 영상 중간 프레임으로 캡처).
    var v = noT ? null : _igVideo();
    var t = (v && isFinite(v.currentTime)) ? Math.round(v.currentTime * 10) / 10 : null;
    _lensOverlay("<div style='padding:30px;text-align:center;color:#aaa'>🔗 원본·유사 영상 추적 중… (보통 20초~1분)</div>");
    // 보고 있는 화면을 그대로 캡처해 보낸다(관제 156, 2026-10-08 사장님 "캡쳐그대로") — 유튜브는 서버가 영상을
    //   못 받아 썸네일로만 찾았다. 캡처가 막힌 사이트(교차 출처 영상)는 frame 없이 종전처럼 t 만 보낸다.
    var lbody = t === null ? { url: url } : { url: url, t: t };
    var fr = noT ? "" : _snapFrame(v);
    if (fr) lbody.frame = fr;
    _gmPost(BASE + "/api/lens/trace_url",
      lbody,
      function (status, text) {
        var d = {};
        try { d = JSON.parse(text); } catch (e) {}
        if (status === 429) { _lensOverlay("<div style='padding:20px;color:#e0623d'>💰 " + _esc(d.error || "이번 달 렌즈 한도 초과") + "</div>"); return; }
        if (!d.ok) { _lensOverlay("<div style='padding:20px;color:#e0623d'>❌ " + _esc(d.error || "추적 실패 — 로그인 상태를 확인해 주세요") + "</div>"); return; }
        var items = d.items || [];
        if (!items.length) { _lensOverlay("<div style='padding:20px;color:#aaa'>비슷한 영상을 못 찾았어요. 다른 장면의 링크로 시도해 보세요.</div>"); return; }
        // 플랫폼별 개수 — 어느 플랫폼이 비었는지 한눈에(2026-10-07 '핀터레스트 왜 안 잡히나')
        var cnt = {};
        for (var ci = 0; ci < items.length; ci++) { var pf = items[ci].platform || "?"; cnt[pf] = (cnt[pf] || 0) + 1; }
        var cs = [];
        for (var k in cnt) cs.push(_esc(k) + " " + cnt[k]);
        var h = "<div style='font-size:12px;color:#aaa;margin:-4px 0 10px'>" + items.length + "개 · " + cs.join(" · ") + "</div>" +
          "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px'>";
        for (var i = 0; i < items.length && i < 100; i++) {
          var it = items[i];
          h += "<div data-play='" + _esc(it.url) + "' style='background:#222;border-radius:10px;overflow:hidden'>" +
            "<a class='ss-pv-box' href='" + _esc(it.url) + "' target='_blank' rel='noopener' style='position:relative;display:block'>" +
            (it.thumbnail ? "<img data-t64='" + _esc(it.thumbnail) + "' style='width:100%;height:240px;object-fit:cover;display:block;background:#000'>" :
              "<div style='height:240px;background:#000'></div>") + "</a>" +
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
        // _lensHoverWire(ov) — 끔(관제 156, 2026-10-07 사장님 "서버부담없는것"): /api/play 는 카드마다 서버가 영상을 받는다.
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
          _lensOverlay("<div style='padding:20px;color:#e0623d'>❌ " + (
            why === "timeout" ? "3분 안에 답이 없어요 — 잠시 뒤 다시 눌러 주세요" :
            why === "stale" ? "확장프로그램이 갱신됐어요 — 이 페이지를 새로고침(F5)해 주세요" :
            "서버 연결 실패") + "</div>");
        }
      }, 180000);   // 렌즈 추적은 70초+ 걸린다(라이브 실측) — 상한 3분
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
  // ★플로팅을 띄울지는 **여기 한 곳**이 정한다(2026-10-03). 종전엔 syncFloat·syncPinFloat·_dockBtns
  //   셋이 각자 display를 썼고, 마지막에 도는 _dockBtns가 숨김을 되돌려 핀터레스트 홈 격자에
  //   '📥 담기'가 광고 카드 위에 떠 있었다(사장님 로그인 크롬 실측 — 수정 전 코드도 동일).
  function _floatWanted() {
    if (_isPin()) return _pinSingle();                    // 핀터레스트: 핀 상세 화면에서만
    // 단일 영상 페이지에선 아래 '더 보기' 그리드에 카드버튼이 생겨도 플로팅(=본 영상 담기)을 남긴다.
    return !(_shownCardBtn() && !isSinglePost());
  }
  // ★'화면에 보이는' 카드 📥만 센다(2026-10-07 사장님 "쇼츠 들어가면 담기만 없다").
  //   유튜브는 검색 → 쇼츠로 가도 검색 화면(ytd-search)을 지우지 않고 숨겨 둔다. 그 안의
  //   카드 📥 23개가 DOM에 남아 '그리드 화면'으로 오판 → 쇼츠 화면의 📥 담기가 꺼졌다.
  //   10-03 _dockBtns가 이 판단을 따르게 되면서 드러났다(그 전엔 _dockBtns가 숨김을 되돌렸다).
  function _shownCardBtn() {
    var bs = document.querySelectorAll(".ss-card-grab");
    for (var i = 0; i < bs.length; i++) if (bs[i].getClientRects().length) return true;
    return false;
  }
  function syncFloat() {
    var f = document.getElementById("ss-grab-btn");
    if (f) f.style.display = _floatWanted() ? "" : "none";
  }

  // 지금 보고 있는 게 '단일 영상/게시물' 페이지인가 (인스타 /p/·/reel/, 틱톡 /video/ 등)
  function isSinglePost() {
    return /\/(p|reel|reels|video)\/[^/]+/.test(location.pathname) ||
           /\/(?:discovery\/item|search_result)\/[^/]+/.test(location.pathname);
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
    // 유튜브는 검색 결과에서만 카드를 잡는다 — watch 화면 '관련 쇼츠'에 붙으면
    // syncFloat가 플로팅(본 영상 담기)을 숨긴다(2026-10-01).
    // 쇼츠(/shorts/ID) + **짧은 일반 영상**(/watch, 길이 ≤ _YT_SHORT_MAX — 2026-10-02 사장님
    // "📥를 붙여야지 당연히"). 렌즈 키워드탭은 '4분 미만' 필터라 결과 대부분이 /watch 카드다.
    var ytr = _ytResults();
    var links = document.querySelectorAll(ytr ? 'a[href*="/shorts/"], a#thumbnail[href*="/watch?v="]'
      : 'a[href*="/video/"], a[href*="/p/"], a[href*="/reel/"]');
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
      // 유튜브 /watch 카드: 썸네일 길이 배지(m:ss)를 읽어 짧은 것만. 배지가 아직 안 그려졌으면
      // 이번엔 건너뛴다(2초 뒤 tick이 다시 본다 — data-ssgrab은 붙일 때만 찍으므로).
      if (ytr && links[k].getAttribute("href").indexOf("/watch") === 0) {
        var d = _ytCardSeconds(links[k]);
        if (!(d > 0 && d <= _YT_SHORT_MAX)) continue;
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
        "position:absolute;top:8px;left:8px;z-index:" + (_isIg() ? 4 : 99999) + ";background:#1f6feb;color:#fff;" +   // 인스타: 고정 머리 위로 안 튀게(관제 156)
        "border:none;border-radius:16px;width:34px;height:34px;font-size:16px;" +
        "box-shadow:0 2px 8px rgba(0,0,0,.4);cursor:pointer";
      (function (a) {
        b.addEventListener("click", function (e) {
          // 버튼이 앵커 안이라 세 단계로 링크 이동을 확실히 막는다(실측 검증).
          e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
          _grabCard(a);
        }, true);
      })(a);
      a.appendChild(b);
    }
  }
  function _grabCard(a) {
    var im = a.querySelector("img, source");
    var thumb = im ? (im.src || (im.getAttribute("srcset") || "").split(" ")[0]) : "";
    var ttl = (im && im.alt) ? im.alt : "";
    openGrab(_ytCleanUrl(a.href), thumb, ttl);
  }

  // ── 유튜브 검색: 카드에 마우스를 올리면 뜨는 미리보기 위에도 📥 (2026-10-07 사장님 "다가가면 사라지고") ──
  //   미리보기 영상은 카드 안이 아니라 앱 맨 위층(ytd-app #video-preview)에 따로 그려진다.
  //   카드 📥는 검색 화면(ytd-search, z-index:0 층) 안에 있어 z-index를 아무리 올려도 그 아래다.
  //   → 미리보기 안에 📥를 하나 두고, 누를 때 그 미리보기가 가리키는 **카드**를 담는다.
  //   담을지 말지는 카드 📥(addAnchorCardBtns: 쇼츠·3분 이하)가 이미 정했다 — 그 카드가 있을 때만 보인다.
  function _ytVid(href) {
    var m = /(?:\/shorts\/|[?&]v=)([\w-]{6,})/.exec(href || "");
    return m ? m[1] : "";
  }
  function _ytPreviewCard(pv) {
    var l = pv.querySelector("a[href*='/shorts/'], a[href*='watch?v=']");
    var id = l ? _ytVid(l.getAttribute("href")) : "";
    if (!id) return null;
    var cs = document.querySelectorAll("a[data-ssgrab]");
    for (var i = 0; i < cs.length; i++) if (_ytVid(cs[i].getAttribute("href")) === id) return cs[i];
    return null;
  }
  // 미리보기가 떠 있는 동안 그 카드의 📥는 숨긴다(관제 156, 2026-10-07 사장님 "마우스를 올리면 아이콘이 하나 더 생긴다").
  //   미리보기는 카드보다 조금 크게, 살짝 비켜 그려져 밑의 카드 📥가 옆에 겹쳐 보였다.
  var _ytHidCard = null;
  function _ytCardBtnShow(a, on) {
    if (!a) return;
    var cb = a.querySelector(".ss-card-grab");
    if (cb) cb.style.visibility = on ? "" : "hidden";
  }
  function _ytPreviewBtn() {
    var pv = document.querySelector("#video-preview ytd-video-preview");
    var vis = pv && pv.getBoundingClientRect().width > 0 && getComputedStyle(pv).display !== "none" &&
              !(pv.closest("#video-preview") && pv.closest("#video-preview").hidden);
    var card = vis ? _ytPreviewCard(pv) : null;
    if (_ytHidCard && _ytHidCard !== card) { _ytCardBtnShow(_ytHidCard, true); _ytHidCard = null; }
    if (card) { _ytCardBtnShow(card, false); _ytHidCard = card; }
    if (!pv) return;
    var b = pv.querySelector(".ss-card-grab");
    if (!b) {
      b = document.createElement("button");
      b.className = "ss-card-grab ss-pv-grab";
      b.textContent = "📥";
      b.title = "이 영상 담기";
      b.style.cssText =
        "position:absolute;top:8px;left:8px;z-index:99999;background:#1f6feb;color:#fff;" +
        "border:none;border-radius:16px;width:34px;height:34px;font-size:16px;" +
        "box-shadow:0 2px 8px rgba(0,0,0,.4);cursor:pointer";
      b.addEventListener("click", function (e) {
        e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
        var a = _ytPreviewCard(pv);
        if (a) _grabCard(a);
      }, true);
      pv.appendChild(b);
    }
    b.style.display = card ? "" : "none";
    // ★카드 📥와 **같은 화면 자리**에 둔다(관제 156, 2026-10-08 사장님 "누르려 하면 왼쪽 위 대각선으로 살짝 올라간다").
    //   미리보기는 카드보다 크게·비켜 그려져 top/left 8px 고정이면 📥가 대각선으로 튀었다.
    var cb = card && card.querySelector(".ss-card-grab");
    if (cb) {
      var c0 = cb.getBoundingClientRect(), p0 = pv.getBoundingClientRect();
      if (c0.width && p0.width) { b.style.left = Math.round(c0.left - p0.left) + "px"; b.style.top = Math.round(c0.top - p0.top) + "px"; }
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

  // ── 인스타 메인월드(관제 151, 2026-10-07) — 인스타가 **스스로 받는** 검색 응답을 옆에서 읽는다(추가 요청 0).
  //   계정02 로그인 실측: 키워드 검색 응답(PolarisKeywordSearchExplorePageRelayQuery) 1번에 24개 영상의
  //   좋아요·댓글 24/24, mp4 주소·길이(efg duration_s) 22/22 — 조회수(play_count)는 **없다**.
  //   격리월드(grab_logic)는 페이지의 fetch/XHR 응답을 못 본다 → manifest world:"MAIN"으로 크롬이 이 함수를
  //   ig_main.js로 직접 주입하고(zip이 이 본문을 잘라 만든다 — douyin_main.js와 같은 방식), 결과는 postMessage로 넘긴다.
  //   ★이 함수 안의 줄은 4칸 이상 들여쓴다 — zip 빌더가 "\n  }"(2칸 닫는 중괄호)를 함수 끝으로 본다.
  function _igMainWorld() {
    if (window.__ssIgMain) return;
    window.__ssIgMain = 1;
    function efgDur(u) {
      try {
        var m = /[?&]efg=([^&]+)/.exec(u || "");
        if (!m) return null;
        var j = JSON.parse(atob(decodeURIComponent(m[1]).replace(/-/g, "+").replace(/_/g, "/")));
        return typeof j.duration_s === "number" ? j.duration_s : null;
      } catch (e) { return null; }
    }
    function walk(o, out, d) {
      if (!o || typeof o !== "object" || d > 40) return;
      if (Array.isArray(o)) { for (var i = 0; i < o.length; i++) walk(o[i], out, d + 1); return; }
      if (o.code && (o.like_count != null || o.video_versions || o.taken_at)) {
        var vv = o.video_versions || [], mp4 = vv[0] && vv[0].url || "";
        var iv = o.image_versions2 && o.image_versions2.candidates || [];
        out.push({ code: String(o.code), likes: o.like_count, comments: o.comment_count,
                   plays: o.play_count != null ? o.play_count : (o.ig_play_count != null ? o.ig_play_count : o.view_count),
                   dur: o.video_duration || efgDur(mp4), video: !!vv.length,
                   taken: o.taken_at, thumb: (iv[iv.length > 1 ? 1 : 0] || {}).url || "",
                   caption: (o.caption && o.caption.text || "").slice(0, 120),
                   user: ((o.user || o.owner || {}).username) || "" });
      }
      for (var k in o) if (o.hasOwnProperty(k) && o[k] && typeof o[k] === "object") walk(o[k], out, d + 1);
    }
    function take(text) {
      if (!text || text.indexOf('"code"') < 0) return;
      var out = [], parts = String(text).split("\n");
      for (var i = 0; i < parts.length; i++) {
        var t = parts[i].trim();
        if (t.indexOf("for (;;);") === 0) t = t.slice(9);
        if (!t || (t[0] !== "{" && t[0] !== "[")) continue;
        try { walk(JSON.parse(t), out, 0); } catch (e) {}
      }
      if (!out.length) return;
      for (var j = 0; j < out.length; j++) buf[out[j].code] = out[j];
      window.__ssIgCount = Object.keys(buf).length;         // 점검용(몇 개 읽었나)
      window.postMessage({ __ssIgMedia: true, items: out }, location.origin);
    }
    // ★확장(grab_logic)은 document_idle에 떠서, 그 전에 온 응답은 못 듣는다 → 쌓아 뒀다가 요청하면 통째로 다시 보낸다.
    var buf = {};
    window.addEventListener("message", function (ev) {
      if (ev.source !== window || !ev.data || !ev.data.__ssIgMediaReq) return;
      var all = [];
      for (var c in buf) if (buf.hasOwnProperty(c)) all.push(buf[c]);
      if (all.length) window.postMessage({ __ssIgMedia: true, items: all }, location.origin);
    });
    function wanted(u) { u = String(u || ""); return u.indexOf("/graphql") >= 0 || u.indexOf("/api/v1/") >= 0; }
    var of = window.fetch;
    if (of) window.fetch = function (input, init) {
      var p = of.apply(this, arguments);
      try {
        var u = typeof input === "string" ? input : (input && input.url);
        if (wanted(u)) p.then(function (r) { try { r.clone().text().then(take, function () {}); } catch (e) {} }, function () {});
      } catch (e) {}
      return p;
    };
    var oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) { this.__ssU = u; return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function () {
      var x = this;
      if (wanted(x.__ssU)) x.addEventListener("load", function () {
        try { if (!x.responseType || x.responseType === "text") take(x.responseText); } catch (e) {}
      });
      return os.apply(this, arguments);
    };
    // 첫 화면 데이터는 HTML 안 JSON으로도 온다(로그아웃 실측) — 다 그려진 뒤 한 번 훑는다.
    function scanDoc() {
      var ss = document.querySelectorAll('script[type="application/json"]');
      for (var i = 0; i < ss.length; i++) if ((ss[i].textContent || "").indexOf("video_versions") >= 0) take(ss[i].textContent);
    }
    if (document.readyState === "complete") scanDoc(); else window.addEventListener("load", scanDoc);
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
  // ── 인스타 영어 검색어(관제 151, 2026-10-07 사장님) ─────────────────────────────
  //   ① 키워드 검색 화면: 제목("Life hacks gadgets")을 검색창으로 바꾼다 — 한글로 치면 영어로 바꿔 검색.
  //   ② 그 아래 비슷한 검색어 칩 5개 — 누르면 그 검색으로 이동.
  //   ③ 게시물 팝업: 오른쪽 버튼 줄 아래에 관련 검색어 칩(설명글 기준, 쇼핑몰 이름 없이).
  //   ★검색어를 만드는 판단(영어·최대 3단어)은 서버 video_analysis.english_search_terms 한 곳이다.
  //     여기서는 받은 걸 그리기만 한다 — 단어 수를 여기서 또 자르지 않는다(0순위-B).
  // ★5개 플랫폼 확장(2026-10-07 사장님 "핀터레스트·유튜브·틱톡·샤오홍슈·도우인 모두, 지금까지 한 것 그대로").
  //   플랫폼마다 다른 것은 아래 표 한 곳에만 적는다 — 검색 주소, 검색어 언어, 게시물 주소 모양.
  //   (검색 주소는 숏템메이커 static/index.html 의 플랫폼 버튼 주소와 같은 값이다 — 바꿀 땐 둘 다.)
  function _qp(name) { try { return (new URLSearchParams(location.search).get(name) || "").trim(); } catch (e) { return ""; } }
  function _pm(re) { var m = location.pathname.match(re); return m ? m[1] : ""; }
  var KW_SITES = [
    { id: "instagram", lang: "en", host: ["instagram.com"],
      q: function () { return location.pathname.indexOf("/explore/search/keyword") === 0 ? _qp("q") : ""; },
      url: function (t) { return "https://www.instagram.com/explore/search/keyword/?q=" + encodeURIComponent(t); },
      post: function () { return isSinglePost() ? _pm(/\/(?:p|reel|reels)\/([A-Za-z0-9_-]+)/) : ""; } },
    { id: "youtube", lang: "en", host: ["youtube.com"],
      q: function () { return location.pathname === "/results" ? _qp("search_query") : ""; },
      url: function (t) { return "https://www.youtube.com/results?search_query=" + encodeURIComponent(t) + "&sp=EgIQCQ%253D%253D"; },   // Shorts 전용(관제 156)
      // /watch 로 열린 쇼츠도(헤드리스·일부 화면은 /shorts/ 대신 /watch?v=로 연다 — 실측).
      // 롱폼 /watch 는 tick 이 _ytOff 로 먼저 걸러 여기까지 안 온다(쇼츠 길이만 동작).
      post: function () { return _pm(/^\/shorts\/([\w-]+)/) || (location.pathname === "/watch" ? _qp("v") : ""); } },
    { id: "tiktok", lang: "en", host: ["tiktok.com"],
      q: function () { return location.pathname.indexOf("/search") === 0 ? _qp("q") : ""; },
      url: function (t) { return "https://www.tiktok.com/search?q=" + encodeURIComponent(t); },
      post: function () { return _pm(/\/video\/(\d+)/); } },
    { id: "pinterest", lang: "en", host: ["pinterest."],
      q: function () { return location.pathname.indexOf("/search/") === 0 ? _qp("q") : ""; },
      url: function (t) { return "https://www.pinterest.com/search/videos/?q=" + encodeURIComponent(t); },
      post: function () { return _pm(/^\/pin\/([\w-]+)/); } },
    { id: "xiaohongshu", lang: "zh", host: ["xiaohongshu.com", "rednote.com"],
      q: function () { return /^\/search_result\/?$/.test(location.pathname) ? _qp("keyword") : ""; },
      url: function (t) { return "https://www.xiaohongshu.com/search_result?keyword=" + encodeURIComponent(t); },
      post: function () { return _pm(/\/(?:explore|discovery\/item|search_result)\/([0-9a-f]{16,})/); } },
    { id: "douyin", lang: "zh", host: ["douyin.com"],
      q: function () { var s = _pm(/^\/search\/([^/?#]+)/); try { return s ? decodeURIComponent(s) : ""; } catch (e) { return s; } },
      url: function (t) { return "https://www.douyin.com/search/" + encodeURIComponent(t); },
      post: function () { return _pm(/\/video\/(\d+)/) || _qp("modal_id"); } }
  ];
  function _kwSite() {
    var h = location.host;
    for (var i = 0; i < KW_SITES.length; i++)
      for (var j = 0; j < KW_SITES[i].host.length; j++)
        if (h.indexOf(KW_SITES[i].host[j]) >= 0) return KW_SITES[i];
    return null;
  }
  function _isIg() { var s = _kwSite(); return !!s && s.id === "instagram"; }
  function _igKwQuery() { var s = _kwSite(); return s && s.id === "instagram" ? s.q() : ""; }
  function _igKwGo(term) { var s = _kwSite(); if (term && s) location.href = s.url(term); }
  // 같은 입력은 한 번만 묻는다(탭 안에서만 기억). 실패는 기억하지 않는다 — 다음 tick에 다시 묻게.
  // ★진행 중인 같은 요청에 붙은 화면은 **모두** 결과를 받는다(2026-10-07 사장님 화면: 팝업 상자가
  //   다시 그려지면 새 상자가 '검색어 만드는 중…'에서 영원히 멈췄다 — 중복 요청을 그냥 버렸기 때문).
  //   kind: query·caption → /api/lens/kw/en(lang: 플랫폼 언어), multi → /api/lens/kw/multi(5개 언어).
  var _igKwWaiters = {};
  function _igKwFetch(kind, text, done) {
    var s = _kwSite(), lang = (s && s.lang) || "en";
    var ck = "ss_kw:" + kind + ":" + (kind === "multi" ? "" : lang + ":") + text;
    try { var c = sessionStorage.getItem(ck); if (c) { done(JSON.parse(c)); return; } } catch (e) {}
    if (_igKwWaiters[ck]) { _igKwWaiters[ck].push(done); return; }
    _igKwWaiters[ck] = [done];
    function finish(r) {
      var ws = _igKwWaiters[ck] || []; delete _igKwWaiters[ck];
      for (var i = 0; i < ws.length; i++) { try { ws[i](r); } catch (e) {} }
    }
    var url = BASE + (kind === "multi" ? "/api/lens/kw/multi" : "/api/lens/kw/en");
    _gmPost(url, { text: text, kind: kind, lang: lang }, function (status, body) {
      var d = null;
      try { d = JSON.parse(body); } catch (e) {}
      if (status === 200 && d && d.ok) {
        var r = kind === "multi" ? { candidates: d.candidates || [] } : { main: d.main || "", related: d.related || [] };
        try { sessionStorage.setItem(ck, JSON.stringify(r)); } catch (e) {}
        finish(r);
      } else {
        finish({ error: status === 401 ? "숏템메이커에 로그인해 주세요" : "검색어를 못 만들었어요(" + status + ")" });
      }
    }, function (why) {
      finish({ error: why === "stale" ? "확장프로그램이 갱신됐어요 — 이 페이지를 새로고침(F5)해 주세요"
                    : why === "timeout" ? "30초 안에 답이 없어요 — 다시 검색해 주세요"
                    : "숏템메이커 서버에 연결하지 못했어요" });
    });
  }
  function _igKwChip(term, strong) {
    var b = document.createElement("button");
    b.type = "button"; b.textContent = term; b.title = "'" + term + "' 검색";
    b.style.cssText = "border:1px solid " + (strong ? "#0095f6" : "#dbdbdb") + ";background:" +
      (strong ? "#0095f6" : "#fff") + ";color:" + (strong ? "#fff" : "#262626") +
      ";border-radius:16px;padding:5px 12px;font:600 13px system-ui,sans-serif;cursor:pointer;white-space:nowrap";
    b.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); _igKwGo(term); });
    return b;
  }
  // 제목 = 검색어와 글자가 같은 요소(대소문자 무시). 인스타 클래스명에 기대지 않는다(자주 바뀐다).
  function _igKwTitleEl(q) {
    var want = q.toLowerCase(), best = null;
    var els = document.querySelectorAll("h1,h2,span,div");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.id === "ss-kwbar" || el.closest("#ss-kwbar")) continue;
      if ((el.textContent || "").trim().toLowerCase() !== want) continue;
      var r = el.getBoundingClientRect();
      if (r.width < 20 || r.height < 10 || r.top > 400) continue;
      if (!best || best.contains(el)) best = el;          // 가장 안쪽 요소
    }
    return best;
  }
  // 검색창 + 비슷한 검색어(5줄 × 5개 언어). 인스타는 제목 자리에, 나머지 플랫폼은 오른쪽 떠 있는 판에 넣는다.
  // 검색창(한글로 치면 이 사이트 언어로 번역해 검색) — 검색 판(_kwBarBody)과 게시물 상자(syncIgPostKw)가 같이 쓴다.
  function _kwSearchForm(q, dark) {
    var form = document.createElement("form");
    form.style.cssText = "display:flex;gap:6px;align-items:center;max-width:560px";
    var inp = document.createElement("input");
    inp.type = "text"; inp.value = q; inp.placeholder = "한글로 쳐도 이 플랫폼 언어로 바꿔 검색해요";
    inp.style.cssText = "flex:1;min-width:0;font:700 " + (dark ? "15" : "18") + "px system-ui,sans-serif;padding:8px 12px;" +
      "border:1px solid #dbdbdb;border-radius:8px;background:#fafafa;color:#262626";
    var go = document.createElement("button");
    go.type = "submit"; go.textContent = "검색";
    go.style.cssText = "border:0;background:#0095f6;color:#fff;border-radius:8px;padding:9px 16px;" +
      "font:700 14px system-ui,sans-serif;cursor:pointer";
    var note = document.createElement("div");
    note.style.cssText = "font-size:12px;color:" + (dark ? "#bbb" : "#737373") + ";min-height:16px";
    form.appendChild(inp); form.appendChild(go);
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var t = (inp.value || "").trim();
      if (!t) return;
      if (!/[ㄱ-힝]/.test(t)) { _igKwGo(t); return; }   // 한글이 없으면 그대로 검색
      go.disabled = true; note.textContent = "검색어로 바꾸는 중…";
      _igKwFetch("query", t, function (r) {
        go.disabled = false;
        if (r.main) { note.textContent = "→ " + r.main; _igKwGo(r.main); }
        else note.textContent = r.error || "바꾸지 못했어요. 직접 입력해 주세요.";
      });
    });
    // 사이트 단축키가 입력을 가로채지 않게(글자 입력 중 페이지가 반응하는 것 방지)
    inp.addEventListener("keydown", function (e) { e.stopPropagation(); });
    return { form: form, note: note };
  }
  // 검색어 판 접기(관제 156) — 머리줄만 남기고 나머지를 숨긴다. 접힌 상태는 판마다 기억(다음 영상·검색에도 접힌 채).
  //   판단은 여기 한 곳(_kwFoldBtn·_kwFoldApply) — 검색 판·관련 검색어 상자가 같이 쓴다.
  function _kwFolded(key) { try { return localStorage.getItem(key) === "1"; } catch (e) { return false; } }
  function _kwFoldApply(panel, key) {
    var shut = _kwFolded(key), kids = panel.children;
    for (var i = 1; i < kids.length; i++) kids[i].style.display = shut ? "none" : "";
    var b = panel.querySelector(".ss-kw-fold");
    if (b) b.textContent = shut ? "펼치기" : "접기";
  }
  function _kwFoldBtn(panel, key) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "ss-kw-fold"; b.textContent = "접기";
    b.style.cssText = "background:none;border:1px solid #555;color:#ccc;border-radius:6px;font-size:11px;padding:2px 8px;cursor:pointer";
    b.addEventListener("click", function (e) {
      e.preventDefault(); e.stopPropagation();
      try { localStorage.setItem(key, _kwFolded(key) ? "0" : "1"); } catch (e2) {}
      _kwFoldApply(panel, key);
    });
    return b;
  }
  // '…중' 문구에 기다린 초를 붙인다 — 서버 답이 10초 넘게 걸려도 멈춘 게 아니라는 걸 보이게(관제 156).
  //   글자가 바뀌거나(결과·오류) 화면에서 빠지면 멈춘다.
  function _kwTicking(el, msg) {
    var t0 = Date.now(), cur = msg;
    el.textContent = msg;
    var iv = setInterval(function () {
      if (!document.body.contains(el) || el.textContent !== cur) { clearInterval(iv); return; }
      cur = msg + " " + Math.round((Date.now() - t0) / 1000) + "초";
      el.textContent = cur;
    }, 1000);
  }
  function _kwBarBody(q, dark) {
    var wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;flex-direction:column;gap:8px;font-family:system-ui,sans-serif";
    var sf = _kwSearchForm(q, dark), form = sf.form, note = sf.note;
    var chips = document.createElement("div");
    chips.style.cssText = "display:flex;flex-direction:column;gap:6px";
    var lab = document.createElement("span");
    lab.textContent = "비슷한 검색어 (한·영·일·중·러)"; lab.style.cssText = "font-size:12px;color:" + (dark ? "#bbb" : "#737373");
    chips.appendChild(lab);
    var wait = document.createElement("span");
    wait.style.cssText = "font-size:12px;color:#a8a8a8"; _kwTicking(wait, "찾는 중…");
    chips.appendChild(wait);
    wrap.appendChild(form); wrap.appendChild(note); wrap.appendChild(chips);
    _igKwFetch("multi", q, function (r) {
      if (!document.body.contains(chips)) return;
      wait.remove();
      var rows = (r.candidates || []).slice(0, 5);
      if (!rows.length) { lab.textContent = r.error || "비슷한 검색어를 못 찾았어요"; return; }
      for (var i = 0; i < rows.length; i++) chips.appendChild(_igKwLangRow(rows[i]));
    });
    return wrap;
  }
  // 검색창을 걷을 때 숨겨 둔 원래 제목을 되살린다(팝업이 열려 주소가 /p/로 바뀌었다 닫히는 경우).
  function _igKwBarRemove(bar) {
    if (!bar) return;
    var t = bar.previousElementSibling;
    if (t && t.style && t.style.display === "none") t.style.display = "";
    bar.remove();
  }
  function syncIgKwBar() {
    var q = _igKwQuery(), bar = document.getElementById("ss-kwbar");
    if (!q) { _igKwBarRemove(bar); return; }
    if (bar && bar.getAttribute("data-q") === q && document.body.contains(bar)) return;
    _igKwBarRemove(bar);
    var title = _igKwTitleEl(q);
    if (!title) return;                                   // 제목이 아직 안 그려졌다 — 다음 tick
    bar = document.createElement("div");
    bar.id = "ss-kwbar"; bar.setAttribute("data-q", q);
    bar.style.cssText = "margin:0 0 12px";
    bar.appendChild(_kwBarBody(q, false));
    bar.appendChild(_igToolRow());
    title.style.display = "none";
    title.insertAdjacentElement("afterend", bar);
  }
  // ── 인스타 검색 화면 도구(관제 151): 좋아요순·댓글순 목록, 마우스 지나간 카드 동시 미리보기 ──
  //   조회수순은 못 한다 — 로그인 실측으로 검색 응답에 조회수가 **없다**(play_count 0/24). 대신 좋아요·댓글.
  function _igBtn(text, title, onClick) {
    var b = document.createElement("button");
    b.type = "button"; b.textContent = text; b.title = title;
    b.style.cssText = "border:1px solid #dbdbdb;background:#fff;color:#262626;border-radius:8px;padding:5px 10px;" +
      "font:700 12px system-ui,sans-serif;cursor:pointer";
    b.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); onClick(b); });
    return b;
  }
  function _igToolRow() {
    var row = document.createElement("div");
    row.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px";
    row.appendChild(_igBtn("❤ 좋아요순", "이 검색의 영상을 좋아요 많은 순으로", function () { _igRank("likes"); }));
    row.appendChild(_igBtn("💬 댓글순", "댓글 많은 순으로", function () { _igRank("comments"); }));
    var pv = _igBtn(_pvLabel(), "마우스를 올린 카드들을 계속 같이 재생", function (b) {
      _pvOn = !_pvOn;
      try { localStorage.setItem("ss_ig_pv", _pvOn ? "1" : "0"); } catch (e) {}
      if (!_pvOn) _pvStopAll();
      b.textContent = _pvLabel();
    });
    row.appendChild(pv);
    var n = document.createElement("span");
    n.style.cssText = "font-size:12px;color:#737373";
    row.appendChild(n);
    var tick0 = setInterval(function () {
      if (!document.body.contains(row)) { clearInterval(tick0); return; }
      n.textContent = "숫자 읽은 영상 " + _igMediaN + "개 (아래로 내리면 늘어나요)";
    }, 1500);
    return row;
  }
  function _igRank(key) {
    var list = [];
    for (var c in _igMedia) if (_igMedia.hasOwnProperty(c) && _igMedia[c].video) list.push(_igMedia[c]);
    list.sort(function (x, y) { return (y[key] || 0) - (x[key] || 0); });
    var o = document.getElementById("ss-ig-rank");
    if (o) o.remove();
    o = document.createElement("div");
    o.id = "ss-ig-rank";
    o.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:2147483647;display:flex;" +
      "align-items:center;justify-content:center;padding:20px;font-family:system-ui,sans-serif";
    var box = document.createElement("div");
    box.style.cssText = "background:#161616;color:#eee;border-radius:14px;padding:16px;max-width:1600px;width:96vw;" +
      "max-height:92vh;overflow:auto;position:relative";
    var hd = document.createElement("div");
    hd.style.cssText = "font-weight:800;margin-bottom:10px";
    hd.textContent = (key === "likes" ? "❤ 좋아요순" : "💬 댓글순") + " · " + list.length + "개 (이 화면에서 읽은 영상)";
    var x = document.createElement("button");
    x.type = "button"; x.textContent = "✕";
    x.style.cssText = "position:absolute;top:6px;right:12px;background:none;border:none;color:#fff;font-size:22px;cursor:pointer";
    x.addEventListener("click", function () { o.remove(); });
    o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
    var grid = document.createElement("div");
    grid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px";
    if (!list.length) grid.textContent = "아직 읽은 영상이 없어요. 검색 화면을 조금 내려 보세요.";
    for (var i = 0; i < list.length; i++) {
      (function (it, rank) {
        var a = document.createElement("a");
        a.href = "https://www.instagram.com/reel/" + it.code + "/";
        a.style.cssText = "display:block;background:#222;border-radius:10px;overflow:hidden;color:#eee;text-decoration:none";
        var im = document.createElement("img");
        im.src = it.thumb || ""; im.alt = "";
        im.style.cssText = "width:100%;height:240px;object-fit:cover;display:block;background:#000";
        var t = document.createElement("div");
        t.style.cssText = "padding:6px 8px;font-size:12px";
        var d0 = _fmtDate(_igDate(it.code));
        t.textContent = "#" + rank + "  " + _igMediaBadge(it, d0 ? d0.slice(2) : "");
        var cap = document.createElement("div");
        cap.style.cssText = "padding:0 8px 8px;font-size:12px;color:#aaa;max-height:32px;overflow:hidden";
        cap.textContent = it.caption || "";
        a.appendChild(im); a.appendChild(t); a.appendChild(cap);
        grid.appendChild(a);
      })(list[i], i + 1);
    }
    box.appendChild(x); box.appendChild(hd); box.appendChild(grid);
    o.appendChild(box);
    document.body.appendChild(o);
  }
  // 동시 미리보기: 인스타는 마우스가 떠나면 그 카드 영상을 **멈추기만** 하고 지우지는 않는다(로그인 실측 —
  //   떠난 뒤에도 video 요소·mp4 주소가 남고 paused=true). 그래서 우리가 다시 재생시키면 된다. 최대 9개.
  var _pvOn = true, _pvList = [];
  try { _pvOn = localStorage.getItem("ss_ig_pv") !== "0"; } catch (e) {}
  function _pvLabel() { return _pvOn ? "▶ 동시 미리보기 켜짐" : "⏸ 동시 미리보기 꺼짐"; }
  function _pvStopAll() {
    for (var i = 0; i < _pvList.length; i++) { _pvList[i].__ssKeep = 0; try { _pvList[i].pause(); } catch (e) {} }
    _pvList = [];
  }
  function _pvKeep(v) {
    if (!v || v.__ssKeep) return;
    v.__ssKeep = 1; v.muted = true; v.loop = true;
    if (!v.__ssPvHooked) {
      v.__ssPvHooked = 1;
      v.addEventListener("pause", function () {
        if (_pvOn && v.__ssKeep && document.contains(v)) setTimeout(function () { try { v.play().catch(function () {}); } catch (e) {} }, 60);
      });
    }
    _pvList.push(v);
    while (_pvList.length > 9) { var old = _pvList.shift(); old.__ssKeep = 0; try { old.pause(); } catch (e) {} }
    try { v.play().catch(function () {}); } catch (e) {}
  }
  // ★인스타 밖으로 넓힘(관제 156, 2026-10-07 사장님 "모든 플랫폼, 서버 부담 없는 것"):
  //   사이트가 마우스 올림에 스스로 붙이는 미리보기 영상을 떠난 뒤에도 계속 재생시킨다(서버 호출 0).
  //   유튜브는 빼다 — 화면 전체가 미리보기 영상 1개를 돌려 써서(실측) 여러 개를 붙잡을 수 없다.
  //   카드 모양은 사이트마다 다르다 → 표 한 곳(PV_CARD).
  var PV_CARD = {
    instagram: 'a[href*="/reel/"],a[href*="/p/"]',
    tiktok: 'a[href*="/video/"],[data-e2e="search_top-item"],[data-e2e="search-card-desc"]',
    pinterest: '[data-test-id="pin"],a[href*="/pin/"]',
    douyin: 'a[href*="/video/"],li',
    xiaohongshu: 'section.note-item,a[href*="/explore/"],a[href*="/search_result/"]'
  };
  if (document.addEventListener) document.addEventListener("mouseover", function (e) {
    if (window.__ssGrabVer !== LOGIC_VER || !_pvOn || isSinglePost()) return;
    var s0 = _kwSite(), sel = s0 && PV_CARD[s0.id];
    if (!sel) return;
    var a = e.target && e.target.closest && e.target.closest(sel);
    if (!a) return;
    setTimeout(function () {                                   // 사이트가 미리보기 영상을 붙일 시간
      var v = a.querySelector("video") || (a.parentElement && a.parentElement.querySelector("video"));
      window.__ssPvTries = (window.__ssPvTries || 0) + 1;        // 점검용
      _pvKeep(v);
    }, 900);
  }, true);
  // 인스타 밖 4+1개 플랫폼의 검색 화면: 오른쪽에 떠 있는 판(접기 가능). 사이트 화면 구조에 기대지 않는다.
  // 유튜브: 우리가 연 Shorts 검색(sp=EgIQCQ)인데 로그인 화면이 '전체' 탭으로 열리면 Shorts 탭을 한 번 눌러 준다
  //   (관제 156, 2026-10-08 사장님 화면: 주소엔 EgIQCQ 가 있는데 '전체'가 선택돼 롱폼이 섞였다. 로그아웃 화면은 Shorts만 나왔다).
  var _ytShortsTabDone = "";
  function _ytShortsTab() {
    if (location.host.indexOf("youtube.com") < 0 || location.pathname !== "/results") return;
    if (_qp("sp").indexOf("EgIQCQ") !== 0 || _ytShortsTabDone === location.href) return;
    var chips = document.querySelectorAll("yt-chip-cloud-chip-renderer, chip-view-model, yt-chip-view-model, button[role='tab']");
    for (var i = 0; i < chips.length; i++) {
      if ((chips[i].innerText || "").trim().toLowerCase() !== "shorts") continue;
      _ytShortsTabDone = location.href;
      if (chips[i].getAttribute("aria-selected") === "true" || chips[i].hasAttribute("selected") ||
          chips[i].querySelector("[aria-selected='true']")) return;
      var btn = chips[i].querySelector("button, a, [role='tab']") || chips[i];
      try { btn.click(); } catch (e) {}
      return;
    }
  }
  function syncKwSearchPanel() {
    try { _ytShortsTab(); } catch (e) {}
    var s = _kwSite(), p = document.getElementById("ss-kwfloat");
    var q = (s && s.id !== "instagram") ? s.q() : "";
    if (!q) { if (p) p.remove(); return; }
    if (p && p.getAttribute("data-q") === q) return;
    if (p) p.remove();
    p = document.createElement("div");
    p.id = "ss-kwfloat"; p.setAttribute("data-q", q);
    p.style.cssText = "position:fixed;top:76px;right:16px;z-index:2147483646;width:auto;max-width:min(760px,92vw);max-height:80vh;overflow:auto;" +
      "background:rgba(22,22,22,.94);color:#eee;border-radius:12px;padding:10px 12px;box-shadow:0 6px 20px rgba(0,0,0,.4);" +
      "font-family:system-ui,sans-serif";
    var hd = document.createElement("div");
    hd.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font:800 13px system-ui,sans-serif";
    var ttl = document.createElement("span"); ttl.textContent = "🔎 숏템 검색어";
    hd.appendChild(ttl); hd.appendChild(_kwFoldBtn(p, "ss_kwfloat_fold"));
    var body = _kwBarBody(q, true);
    if (s.id === "youtube") body.appendChild(_ytRankRow());   // 조회수순·좋아요순·댓글순·최신순(관제 156)
    p.appendChild(hd); p.appendChild(body);
    _kwFoldApply(p, "ss_kwfloat_fold");
    document.body.appendChild(p);
    _ssDrag(p, hd);
  }
  // ── 검색어 판 끌어 옮기기(관제 156, 2026-10-07 사장님 "검색창들은 마우스로 이동이 되게, 모든 사이트") ──
  //   머리줄을 잡고 끌면 그 자리에 고정된다(사이트별·판별로 기억). 한 번 옮긴 판은 도킹 자리 계산이 건드리지 않는다.
  //   판단은 여기 한 곳(_ssDrag·_ssDragPos) — 판마다 따로 적지 않는다(0순위-B).
  function _ssDragKey(id) { return "ss_drag:" + location.host + ":" + id; }
  function _ssDragPos(el) {
    try { var v = JSON.parse(localStorage.getItem(_ssDragKey(el.id)) || "null"); } catch (e) { v = null; }
    if (!v) return false;
    var x = Math.min(Math.max(0, v.x), window.innerWidth - 60), y = Math.min(Math.max(0, v.y), window.innerHeight - 40);
    el.style.left = x + "px"; el.style.top = y + "px"; el.style.right = "auto"; el.style.bottom = "auto";
    return true;
  }
  function _ssDrag(el, handle) {
    handle.style.cursor = "move"; handle.title = "잡고 끌면 옮겨져요 (두 번 누르면 원래 자리)";
    _ssDragPos(el);
    handle.addEventListener("dblclick", function () {
      try { localStorage.removeItem(_ssDragKey(el.id)); } catch (e) {}
      el.style.left = ""; el.style.top = ""; el.style.right = ""; el.style.bottom = "";
    });
    handle.addEventListener("mousedown", function (e) {
      if (e.button !== 0 || (e.target && e.target.tagName === "BUTTON")) return;
      e.preventDefault(); e.stopPropagation();
      var r = el.getBoundingClientRect(), dx = e.clientX - r.left, dy = e.clientY - r.top;
      function mv(ev) {
        var x = Math.min(Math.max(0, ev.clientX - dx), window.innerWidth - 60);
        var y = Math.min(Math.max(0, ev.clientY - dy), window.innerHeight - 40);
        el.style.left = x + "px"; el.style.top = y + "px"; el.style.right = "auto"; el.style.bottom = "auto";
      }
      function up() {
        document.removeEventListener("mousemove", mv, true); document.removeEventListener("mouseup", up, true);
        var q = el.getBoundingClientRect();
        try { localStorage.setItem(_ssDragKey(el.id), JSON.stringify({ x: q.left, y: q.top })); } catch (e2) {}
      }
      document.addEventListener("mousemove", mv, true); document.addEventListener("mouseup", up, true);
    });
  }
  function _ssDragged(el) { try { return !!localStorage.getItem(_ssDragKey(el.id)); } catch (e) { return false; } }
  // 한 검색어 = 한 줄. 언어별 버튼(빈 언어는 흐리게, 누를 수 없음). 누르면 그 말로 지금 플랫폼에서 검색.
  var IGKW_LANGS = [["ko", "한"], ["en", "EN"], ["ja", "日"], ["zh", "中"], ["ru", "RU"]];
  function _igKwLangRow(c) {
    var row = document.createElement("div");
    row.style.cssText = "display:flex;flex-wrap:nowrap;gap:6px;align-items:center";   // 한 검색어 = 한 줄(관제 156 통일)
    for (var i = 0; i < IGKW_LANGS.length; i++) {
      var lang = IGKW_LANGS[i][0], tag = IGKW_LANGS[i][1], term = (c[lang] || "").trim();
      var b = _igKwChip(term || "-", false);
      b.textContent = "";
      var t = document.createElement("span");
      t.textContent = tag; t.style.cssText = "font-size:10px;font-weight:800;color:#8e8e8e;margin-right:5px";
      b.appendChild(t); b.appendChild(document.createTextNode(term || "없음"));
      if (!term) { b.disabled = true; b.style.opacity = ".35"; b.style.cursor = "default"; }
      row.appendChild(b);
    }
    return row;
  }
  // ── ③ 게시물(영상) 화면의 관련 검색어 ─────────────────────────────────
  function _igPostCode() {
    var m = location.pathname.match(/\/(?:p|reel|reels)\/([A-Za-z0-9_-]+)/);
    return m ? m[1] : "";
  }
  // 설명글: 페이지에 박힌 JSON(로그아웃 화면 실측: media 노드의 caption.text) → 화면의 h1 → og:description.
  function _igCaptionFromDoc(doc, code) {
    var ss = doc.querySelectorAll('script[type="application/json"]');
    for (var i = 0; i < ss.length; i++) {
      var tx = ss[i].textContent || "";
      if (tx.indexOf(code) < 0 || tx.indexOf("caption") < 0) continue;
      var found = "";
      try {
        (function walk(o, d) {
          if (found || !o || typeof o !== "object" || d > 60) return;
          if (o.code === code && o.caption && o.caption.text) { found = o.caption.text; return; }
          for (var k in o) walk(o[k], d + 1);
        })(JSON.parse(tx), 0);
      } catch (e) {}
      if (found) return found;
    }
    return "";
  }
  function _igCaption(code, done) {
    var c = _igCaptionFromDoc(document, code);
    if (c) { done(c); return; }
    var h = document.querySelector('[role="dialog"] h1, article h1, main h1');
    if (h && (h.textContent || "").trim().length > 3) { done(h.textContent.trim()); return; }
    fetch("/p/" + code + "/", { credentials: "include" }).then(function (r) { return r.text(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, "text/html");
      var t = _igCaptionFromDoc(doc, code);
      if (!t) {
        var m = doc.querySelector('meta[property="og:description"]') || doc.querySelector('meta[name="description"]');
        t = m ? (m.getAttribute("content") || "") : "";
      }
      done(t.trim());
    }).catch(function () { done(""); });
  }
  // 인스타 밖 플랫폼의 설명글: 화면에 보이는 제목·설명 요소 + 탭 제목. 사이트마다 자리만 다르다.
  var KW_DESC_SEL = {
    youtube: ["ytd-reel-video-renderer[is-active] h2", "yt-shorts-video-title-view-model", "ytd-reel-video-renderer[is-active] .title",
              "ytd-watch-metadata h1", "#description-inline-expander"],
    tiktok: ['[data-e2e="browse-video-desc"]', '[data-e2e="video-desc"]'],
    pinterest: ["h1", '[data-test-id="pin-title"]', '[data-test-id="truncated-description"]'],
    xiaohongshu: ["#detail-title", "#detail-desc", ".note-content .desc"],
    douyin: ['[data-e2e="video-desc"]', '[data-e2e="detail-video-info"] h1', "h1"]
  };
  var KW_TITLE_TAIL = / [-|·] (YouTube|TikTok|Pinterest|小红书|抖音).*$/i;
  function _siteCaption(s) {
    var parts = [], seen = {};
    function add(t) {
      t = String(t || "").replace(/\s+/g, " ").trim();
      if (t.length < 4 || seen[t]) return;
      seen[t] = 1; parts.push(t);
    }
    var sels = KW_DESC_SEL[s.id] || [];
    for (var i = 0; i < sels.length; i++) {
      var el = document.querySelector(sels[i]);
      if (el) add(el.textContent);
    }
    add((document.title || "").replace(KW_TITLE_TAIL, ""));
    return parts.join(" / ").slice(0, 2000);
  }
  // 설명글의 해시태그(순서대로·중복 없이·최대 8개). 숫자만인 것은 뺀다.
  function _postHashtags(cap) {
    var out = [], seen = {}, re = /#([^\s#.,!?:;()\[\]{}"'“”‘’<>@]+)/g, m;
    while ((m = re.exec(String(cap || ""))) && out.length < 8) {
      var t = m[1].replace(/[_]+$/, "");
      var k = t.toLowerCase();
      if (!t || /^\d+$/.test(t) || seen[k]) continue;
      seen[k] = 1; out.push(t);
    }
    return out;
  }
  // 해시태그 검색 주소 — 사이트마다 태그 검색이 따로 있다(인스타는 키워드 검색에 '#태그'를 넣으면 태그 결과).
  var TAG_URL = {
    instagram: function (t) { return "https://www.instagram.com/explore/search/keyword/?q=" + encodeURIComponent("#" + t); },
    youtube: function (t) { return "https://www.youtube.com/hashtag/" + encodeURIComponent(t) + "/shorts"; },
    tiktok: function (t) { return "https://www.tiktok.com/tag/" + encodeURIComponent(t); },
    pinterest: function (t) { return "https://www.pinterest.com/search/videos/?q=" + encodeURIComponent("#" + t); },
    xiaohongshu: function (t) { return "https://www.xiaohongshu.com/search_result?keyword=" + encodeURIComponent(t); },
    douyin: function (t) { return "https://www.douyin.com/search/" + encodeURIComponent("#" + t); }
  };
  function _tagChip(s, t) {
    var b = document.createElement("button");
    b.type = "button"; b.textContent = "#" + t; b.title = "#" + t + " 태그로 검색";
    b.style.cssText = "border:1px solid #f5c542;background:#f5c542;color:#1a1206;border-radius:16px;padding:5px 12px;" +
      "font:800 13px system-ui,sans-serif;cursor:pointer;white-space:nowrap";
    b.addEventListener("click", function (e) {
      e.preventDefault(); e.stopPropagation();
      // 설명글 속 그 태그 링크가 있으면 **사이트가 쓰는 주소 그대로** 간다(사장님이 눌러서 잘 됐던 그 길).
      var as = document.querySelectorAll("a[href]");
      for (var i = 0; i < as.length; i++) {
        if ((as[i].textContent || "").trim().toLowerCase() === ("#" + t).toLowerCase()) { location.href = as[i].href; return; }
      }
      var f = s && TAG_URL[s.id];
      if (f) location.href = f(t);
    });
    return b;
  }
  function syncIgPostKw() {
    var p = document.getElementById("ss-kwpost"), s = _kwSite();
    var code = s ? s.post() : "";
    if (!code) { if (p) p.remove(); return; }
    var key = s.id + ":" + code;
    if (p && p.getAttribute("data-c") === key && p.getAttribute("data-wait") !== "1") return;
    var body, st;
    if (p && p.getAttribute("data-c") === key) {          // 설명글을 기다리는 중 — 다시 읽어 본다
      body = p.querySelector(".ss-kw-body"); st = p.querySelector(".ss-kw-st");
    } else {
      if (p) p.remove();
      p = document.createElement("div");
      p.id = "ss-kwpost"; p.setAttribute("data-c", key);
      p.style.cssText = "position:fixed;right:18px;bottom:230px;z-index:2147483646;width:auto;max-width:min(760px,92vw);max-height:70vh;overflow:auto;" +
        "background:rgba(22,22,22,.92);color:#eee;border-radius:12px;padding:10px;font-family:system-ui,sans-serif;" +
        "box-shadow:0 4px 14px rgba(0,0,0,.35);display:flex;flex-direction:column;gap:6px";
      var hd = document.createElement("div");
      hd.style.cssText = "display:flex;justify-content:space-between;align-items:center;gap:12px;font:800 13px system-ui,sans-serif";
      var hdt = document.createElement("span"); hdt.textContent = "🔎 관련 검색어";
      hd.appendChild(hdt); hd.appendChild(_kwFoldBtn(p, "ss_kwpost_fold"));
      body = document.createElement("div"); body.className = "ss-kw-body";
      body.style.cssText = "display:flex;flex-direction:column;gap:6px";
      st = document.createElement("div"); st.className = "ss-kw-st";
      st.textContent = "설명글 읽는 중…"; st.style.cssText = "font-size:12px;color:#aaa";
      body.appendChild(st);
      // 검색창(관제 156, 2026-10-08 사장님 "여기도 검색창, 한글로 바꾸면 번역돼서") — 검색 판과 같은 것.
      var psf = _kwSearchForm("", true);
      psf.form.classList.add("ss-kw-form");
      // 판매자 태그 줄 자리 = 머리 바로 아래 **맨 위**(관제 156, 2026-10-08 사장님 "제일 정확한 거야")
      var tagSlot = document.createElement("div"); tagSlot.className = "ss-kw-tagslot";
      p.appendChild(hd); p.appendChild(tagSlot); p.appendChild(psf.form); p.appendChild(psf.note); p.appendChild(body);
      _kwFoldApply(p, "ss_kwpost_fold");
      document.body.appendChild(p);
      _ssDrag(p, hd);
    }
    var run = function (cap) {
      if (p.getAttribute("data-c") !== key || !document.body.contains(p)) return;
      if (!cap) {
        // 인스타 밖 플랫폼은 설명글이 늦게 그려진다 — 몇 tick 더 기다린다(최대 5번 ≈ 10초).
        var n = +(p.getAttribute("data-tries") || 0) + 1;
        p.setAttribute("data-tries", n);
        if (s.id !== "instagram" && n < 5) { p.setAttribute("data-wait", "1"); return; }
        p.removeAttribute("data-wait");
        st.textContent = "설명글이 없어 검색어를 못 만들었어요"; return;
      }
      p.removeAttribute("data-wait");
      // ★판매자 해시태그를 맨 위 줄에(관제 156, 2026-10-08 사장님): 설명글의 #intake 를 누르니 영어 검색어로는
      //   안 나오던 제품이 정확히 나왔다. 인스타 키워드 검색이 안 될 때 가장 좋은 길 — 서버 호출 없이 설명글에서 뽑는다.
      var tags = _postHashtags(cap);
      if (tags.length && !p.querySelector(".ss-kw-tags")) {
        var tr = document.createElement("div");
        tr.className = "ss-kw-tags";
        tr.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center";
        var tl = document.createElement("span");
        tl.textContent = "판매자 태그"; tl.style.cssText = "font-size:11px;font-weight:800;color:#f5c542;margin-right:2px";
        tr.appendChild(tl);
        for (var ti = 0; ti < tags.length; ti++) tr.appendChild(_tagChip(s, tags[ti]));
        var slot = p.querySelector(".ss-kw-tagslot");
        if (slot) slot.appendChild(tr); else body.insertBefore(tr, body.firstChild);
        // 검색창 기본값 = 첫 판매자 태그(가장 정확한 검색어). 사람이 이미 쳤으면 건드리지 않는다.
        var fin = p.querySelector(".ss-kw-form input");
        if (fin && !fin.value) fin.value = tags[0];
      }
      _kwTicking(st, "검색어 만드는 중…");
      _igKwFetch("caption", cap.slice(0, 2000), function (r) {
        if (p.getAttribute("data-c") !== key || !document.body.contains(p)) return;
        var list = (r.main ? [r.main] : []).concat(r.related || []);
        if (!list.length) { st.textContent = r.error || "검색어를 못 만들었어요"; return; }
        // 5개 언어(관제 156, 사장님 "제품을 누른 페이지에도 5개국어") — 검색 판과 같은 줄 모양(_igKwLangRow).
        //   상품 이름(main) 하나로 5줄 × 5개 언어를 받는다. 못 받으면 종전 칩으로.
        _kwTicking(st, "5개 언어로 펼치는 중…");
        _igKwFetch("multi", list[0], function (m) {
          if (p.getAttribute("data-c") !== key || !document.body.contains(p)) return;
          st.remove();
          var rows = (m.candidates || []).slice(0, 5);
          if (rows.length) { for (var k = 0; k < rows.length; k++) body.appendChild(_igKwLangRow(rows[k])); return; }
          for (var i = 0; i < list.length; i++) body.appendChild(_igKwChip(list[i], i === 0 && !!r.main));
        });
      });
    };
    if (s.id === "instagram") _igCaption(code, run);
    else run(_siteCaption(s));
  }
  // 유튜브 롱폼처럼 확장이 꺼지는 화면에서 남은 판을 걷는다.
  function _kwClearAll() {
    var ids = ["ss-kwfloat", "ss-kwpost"];
    for (var i = 0; i < ids.length; i++) { var e = document.getElementById(ids[i]); if (e) e.remove(); }
  }

  var DOCK_IDS = ["ss-adopt-btn", "ss-favch-btn", "ss-lens-btn", "ss-chadd-btn", "ss-grab-btn"];
  var DOCK_STEP = 52;      // 버튼 세로 간격
  function _dockAnchor() {
    // 핀터레스트 핀 상세: 본 핀 칸(closeup-media-container)이 기준이다. 본 핀이 사진이면 '가장 큰
    //   영상'은 옆 격자의 영상 카드라 버튼이 남의 카드 위에 붙었다(2026-10-03 실측).
    if (_isPin() && _pinSingle()) {
      var cm = document.querySelector('[data-test-id="closeup-media-container"]');
      if (cm) {
        var q0 = cm.getBoundingClientRect();
        // 칸 바로 오른쪽은 하트·공유 버튼 줄이라 덮는다(실측) → 본 핀 **안쪽 오른쪽 위**에 세운다.
        if (q0.width > 200 && q0.right < window.innerWidth)
          return { top: q0.top, bottom: q0.bottom, right: q0.right - 130 };
      }
    }
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
    // ★인스타 '모달'(프로필에서 영상을 클릭했을 때)은 왼쪽 영상 + 오른쪽 캡션판이 한 칸이다
    //   (2026-09-02 사장님 스샷). 영상 오른쪽만 보면 버튼이 **캡션 글자 위를 덮는다** —
    //   모달 칸 자체를 넘어 그 바깥(오른쪽 빈 공간)에 세워야 한다. 그래서 dialog·article은
    //   폭 가드(영상의 1.6배)를 면제한다. 나머지 칸은 종전대로 — 유튜브 쇼츠의 화면 전체폭
    //   조상을 집어 버튼이 브라우저 끝까지 날아갔던 사고(2026-09-01)를 막아야 한다.
    var el = best.parentElement, guard = 0;
    while (el && guard++ < 10) {
      var rr = el.getBoundingClientRect();
      // ★/reel/ 직접 주소 화면(2026-09-03 사장님 스샷)은 dialog·article이 아닌 칸이
      //   영상+댓글판을 감싼다 — 댓글 입력창(textarea)을 품은 칸이면 같은 취급. 단 화면
      //   거의 전체를 덮는 칸은 페이지 껍데기라 버린다(버튼이 브라우저 끝으로 날아간다).
      var hasComment = !!(el.querySelector && el.querySelector("textarea")) &&
                       rr.width <= window.innerWidth * 0.85;
      var isModal = (el.getAttribute && el.getAttribute("role") === "dialog") ||
                    el.tagName === "ARTICLE" || hasComment;
      if (rr.right > right && rr.right < window.innerWidth &&
          (isModal || rr.width <= v.width * 1.6)) right = rr.right;
      el = el.parentElement;
    }
    // ★인스타 팝업 새 구조(2026-10-03 사장님 스샷 + 라이브 실측): 영상 폭 칸이 14겹이라
    //   위 10칸 안에 팝업 칸이 안 잡히고, 15겹째 칸(ARTICLE)은 **화면보다 넓어**(-114~2019)
    //   오른쪽 끝을 못 쓴다. 눈에 보이는 팝업은 그 칸의 자식 둘(영상 칸 + 본문 칸)이다.
    //   → 댓글 입력창(textarea)에서 위로 올라가며 '영상 오른쪽에 있는 칸'까지만 따라가면
    //     본문 칸이 나온다. 그 오른쪽 끝 바깥에 세운다. 댓글창이 영상 아래면(피드) 해당 없음.
    var host = best.parentElement, g2 = 0, ta = null;
    while (host && g2++ < 30) {
      ta = host.querySelector ? host.querySelector("textarea") : null;
      if (ta) break;
      host = host.parentElement;
    }
    if (ta && ta.getBoundingClientRect) {
      var p = ta, panel = null;
      while (p && p !== host) {
        var pr = p.getBoundingClientRect();
        if (pr.left < v.right - 4) break;
        panel = pr; p = p.parentElement;
      }
      if (panel && panel.left <= v.right + 200 && panel.top < v.bottom && panel.bottom > v.top &&
          panel.right > right && panel.right < window.innerWidth) right = panel.right;
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
    // ★사이트 **헤더 아래로만** 내려온다(2026-09-02 사장님 "이거때매 계정 눌러지지가
    //   않는다"). 종전 바닥값 8px은 화면 맨 위라, 영상이 위로 올라간 화면에서 담기 버튼이
    //   인스타 헤더의 **계정 아이콘 위를 덮어** 프로필을 못 눌렀다. 인스타·유튜브·틱톡
    //   헤더가 모두 60px 안팎이라 그 아래(72px)를 바닥으로 둔다.
    var HEADER_SAFE = 72;
    var base = rr ? Math.max(HEADER_SAFE, Math.min(rr.top + 8,
                 window.innerHeight - 8 - live.length * DOCK_STEP)) : 0;
    var slot = 0;
    for (var i = 0; i < live.length; i++) {
      var el = live[i];
      var off = gone || (el.id === "ss-grab-btn" && !_floatWanted());
      el.style.display = off ? "none" : "";
      if (off) continue;
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
    // 시크바: **담기 버튼(도킹 줄 맨 아래) 바로 밑**에 붙인다(2026-09-02 사장님 "댓글을 못 써서").
    // ★top·left만 건다. bottom·right는 반드시 auto로 푼다 — 고정 배치에서 top과 bottom이
    //   같이 걸리면 그 사이만큼 상자가 늘어나 검은 판이 된다(2026-09-02~03 3번 재발).
    var sk = document.getElementById("ss-seek");
    if (sk) {
      sk.style.display = gone ? "none" : "";
      if (gone) { _placeKwPost(rr, x, base, slot, gone); return; }
      if (!rr || slot === 0) {
        sk.style.left = ""; sk.style.top = "";
        sk.style.right = "18px"; sk.style.bottom = "174px";
      } else {
        var sw = sk.offsetWidth || 260;
        var sx = x + 16;
        if (sx + sw + 12 > window.innerWidth) sx = Math.max(8, window.innerWidth - sw - 12);
        sk.style.right = "auto"; sk.style.bottom = "auto";
        sk.style.left = sx + "px";
        sk.style.top = (base + slot * DOCK_STEP) + "px";   // 마지막 버튼 한 칸 아래
      }
      sk.style.height = "auto"; sk.style.maxHeight = "none"; sk.style.width = "auto";
    }
    _placeKwPost(rr, x, base, slot, gone);
  }
  // 관련 검색어 상자(관제 151): 도킹 줄(버튼들 → 시크바) **맨 아래**에 붙인다. 자리 판단은 _dockBtns 한 곳.
  function _placeKwPost(rr, x, base, slot, gone) {
    var kp = document.getElementById("ss-kwpost");
    if (!kp) return;
    kp.style.display = gone ? "none" : "";
    if (gone) return;
    if (_ssDragged(kp)) { _ssDragPos(kp); return; }   // 사장님이 옮긴 자리는 그대로(관제 156)
    if (!rr || slot === 0) {                 // 기준 영상을 못 찾았으면 종전 오른쪽 아래 자리
      kp.style.left = ""; kp.style.top = ""; kp.style.right = "18px"; kp.style.bottom = "230px";
      return;
    }
    var top = base + slot * DOCK_STEP;
    var sk = document.getElementById("ss-seek");
    if (sk && sk.style.display !== "none") {
      var sr = sk.getBoundingClientRect();
      if (sr.height) top = sr.bottom + 10;
    }
    var kw = kp.offsetWidth || 230, kx = x + 16;
    if (kx + kw + 12 > window.innerWidth) kx = Math.max(8, window.innerWidth - kw - 12);
    kp.style.right = "auto"; kp.style.bottom = "auto";
    kp.style.left = kx + "px"; kp.style.top = top + "px";
    kp.style.maxHeight = Math.max(80, window.innerHeight - top - 12) + "px";
    kp.style.overflow = "auto";
  }

  // ── 핀터레스트(2026-09-11) ────────────────────────────────────────────
  //   고객: "숏템파워검색 → 📌 누르면 영상은 뜨는데 담기 버튼이 없다". 📌는 pinterest.com
  //   검색을 새 탭에 여는 버튼이라 우리 버튼이 있을 리 없었다 — 이 로직이 핀터레스트를
  //   아예 몰랐다(@match에도 없었다). 서버 쪽 받기(media_download._download_pinterest)는
  //   이미 있었으니 화면만 붙인다.
  //   · 핀 페이지(/pin/숫자/) = 단일 영상 → 플로팅 📥 담기(location.href 그대로).
  //   · 검색·피드 그리드 = 핀 카드(a[href^="/pin/"])마다 📥. 플로팅은 숨긴다 — 검색 페이지
  //     주소를 담으면 서버가 "지원 안 함"을 낼 뿐이라 혼동만 준다.
  function _isPin() { return location.host.indexOf("pinterest.") >= 0; }
  function _pinSingle() { return /^\/pin\/[^/]+/.test(location.pathname); }
  // 카드 → 담을 핀 주소. 일반 핀은 카드 안 /pin/ 링크, **후원 핀**(광고)은 카드 링크가 광고주
  //   사이트라 /pin/이 없다 — 카드를 감싼 [data-test-pin-id]의 고유번호(영문)로 핀 주소를 만든다
  //   (2026-10-03 사장님 로그인 크롬 실측: 후원 핀 5/5 링크=temu·ljmbxx 등, 번호 AVkr… →
  //   /pin/AVkr…/ 가 열리고 서버 pin_video_info가 720w mp4를 찾았다).
  function _pinCardUrl(c) {
    var a = c.querySelector('a[href^="/pin/"]');
    if (a) return a.href;
    var h = c.closest("[data-test-pin-id]");
    var id = h ? h.getAttribute("data-test-pin-id") : "";
    return /^[\w-]{6,}$/.test(id) ? location.origin + "/pin/" + id + "/" : "";
  }
  function addPinCardBtns() {
    // 핀 상세 화면도 아래 '더 보기' 격자 카드엔 붙인다(본 핀은 플로팅이 담는다).
    if (!_isPin()) return;
    var here = _pinSingle() ? (location.pathname.match(/^\/pin\/([^/]+)/) || [])[1] : "";
    // ★핀터레스트 실측(2026-09-11): 핀 링크 <a href="/pin/…">는 **0x0**(레이아웃 없음)이고
    //   크기를 가진 상자는 [data-test-id="pin"] 래퍼다. 영상 핀은 <img> 대신 <video>만 있다.
    //   그래서 래퍼 기준으로 크기·버튼 자리를 잡고, 썸네일은 img.src 또는 video.poster.
    var cards = document.querySelectorAll('[data-test-id="pin"]');
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      if (c.getAttribute("data-ssgrab")) continue;
      var url = _pinCardUrl(c);
      var video = c.querySelector("video");
      var im = c.querySelector("img") || video;
      if (!url || !im) continue;
      if (here && url.indexOf("/pin/" + here + "/") >= 0) continue;   // 본 핀은 플로팅 몫
      var rr = c.getBoundingClientRect();
      if (rr.width < 100 || rr.height < 100) continue;     // 아직 안 그려진(0x0) 카드는 다음 tick에
      c.setAttribute("data-ssgrab", "1");
      if (getComputedStyle(c).position === "static") c.style.position = "relative";
      var b = document.createElement("button");
      b.className = "ss-card-grab";
      b.textContent = "📥";
      b.title = "이 핀 담기";
      b.style.cssText =
        "position:absolute;top:8px;left:8px;z-index:99999;background:#1f6feb;color:#fff;" +
        "border:none;border-radius:16px;width:34px;height:34px;font-size:16px;" +
        "box-shadow:0 2px 8px rgba(0,0,0,.4);cursor:pointer";
      (function (url, im, video) {
        b.addEventListener("click", function (e) {
          e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
          var direct = "";
          if (video) {
            direct = video.currentSrc || video.src || "";
            if (direct.indexOf("pinimg.com") < 0) {
              var source = video.querySelector("source");
              direct = source ? (source.src || source.getAttribute("src") || "") : "";
            }
          }
          openGrab(url, im.poster || im.src || "", im.alt || im.getAttribute("aria-label") || "",
                   direct.indexOf("pinimg.com") >= 0 ? direct : "");
        }, true);
      })(url, im, video);
      c.appendChild(b);
    }
  }

  // ── 유튜브는 '쇼츠'에서만 동작한다 (2026-09-02 사장님 요청) ──────────────
  //   메인·구독·검색·채널 등 목록 화면과 **롱폼(watch)** 에선 버튼을 아예 띄우지 않는다.
  //   예외: 공유 링크로 열린 쇼츠는 /watch?v=... 로 뜨기도 한다 → 재생 중인 영상 길이가
  //   3분 이하이면 쇼츠로 보고 허용한다(길이를 못 읽으면 롱폼으로 간주해 끈다).
  // 예외 2(2026-10-01 사장님): **검색 결과(/results)** 는 렌즈 키워드 검색이 보내는 화면이다.
  //   여기선 플로팅(=검색 페이지 통째) 없이 **쇼츠·짧은 영상 카드마다 📥** 만 붙인다(_ytResultsTick).
  // '짧은 영상'의 기준 — 이 숫자 하나가 watch 화면 허용(_ytOff)과 검색 카드 📥 둘 다를 정한다.
  var _YT_SHORT_MAX = 180;
  // 검색 카드 썸네일의 길이 배지("1:41", "1:02:03")를 초로. 못 읽으면 0.
  function _ytCardSeconds(a) {
    var els = a.querySelectorAll("*");
    for (var i = 0; i < els.length; i++) {
      if (els[i].children.length) continue;
      var m = (els[i].textContent || "").trim().match(/^(?:(\d+):)?(\d{1,2}):(\d{2})$/);
      if (m) return (+(m[1] || 0)) * 3600 + (+m[2]) * 60 + (+m[3]);
    }
    return 0;
  }
  // 검색 카드 링크의 추적 꼬리(&pp=...)를 떼고 영상 주소만 보낸다. 유튜브 밖은 그대로.
  function _ytCleanUrl(href) {
    var m = /youtube\.com\/watch\?(?:.*&)?v=([\w-]{6,})/.exec(href || "");
    return m ? "https://www.youtube.com/watch?v=" + m[1] : href;
  }
  function _ytResults() {
    return location.host.indexOf("youtube.com") >= 0 && location.pathname === "/results";
  }
  function _ytOff() {
    var h = location.host;
    if (h.indexOf("youtube.com") < 0 && h.indexOf("youtu.be") < 0) return false;
    if (/^\/shorts\//.test(location.pathname)) return false;      // 쇼츠 = 동작
    if (_ytResults()) return false;                               // 검색 = 카드만(tick에서 분기)
    if (/^\/watch/.test(location.pathname) || h.indexOf("youtu.be") >= 0) {
      var v = document.querySelector("video");
      var d = v && isFinite(v.duration) ? v.duration : 0;
      if (d > 0 && d <= _YT_SHORT_MAX) return false;                        // watch로 열린 쇼츠
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

  // 유튜브 검색 결과: 영상 페이지용 버튼(플로팅·렌즈·채널등록·시크바)은 걷고 쇼츠 카드 📥만 단다.
  // ── 유튜브 Shorts 검색: 카드 배지(📅·▶·❤·💬·⏱) + 조회수순·좋아요순·댓글순·최신순(관제 156, 2026-10-08 사장님 "인스타처럼") ──
  //   검색 화면엔 조회수만 있다(실측) → 서버 /api/yt/details(유튜브 API, 50개당 쿼터 1·6시간 캐시)로 받는다.
  var _ytMeta = {}, _ytAsked = {}, _ytBusy = false;
  function _ytCards() {
    var as = document.querySelectorAll('a[href^="/shorts/"]'), out = [];
    for (var i = 0; i < as.length; i++) {
      var r = as[i].getBoundingClientRect();
      if (r.width < 120 || r.height < 150) continue;          // 썸네일 칸만(제목 링크 제외)
      var id = _ytVid(as[i].getAttribute("href"));
      if (id) out.push([as[i], id]);
    }
    return out;
  }
  function _ytBadges() {
    var cs = _ytCards(), need = [];
    for (var i = 0; i < cs.length; i++) {
      var a = cs[i][0], id = cs[i][1], md = _ytMeta[id];
      if (!md) { if (!_ytAsked[id]) need.push(id); continue; }
      var el = a.querySelector(".ss-card-info");
      if (!el) {
        if (getComputedStyle(a).position === "static") a.style.position = "relative";
        el = document.createElement("div"); el.className = "ss-card-info";
        el.style.cssText = "position:absolute;left:6px;bottom:6px;z-index:3;background:rgba(0,0,0,.7);color:#fff;" +
          "font:11px system-ui,sans-serif;border-radius:8px;padding:2px 7px;pointer-events:none";
        a.appendChild(el);
      }
      if (el.getAttribute("data-c") !== id) {
        el.setAttribute("data-c", id);
        el.textContent = _igMediaBadge({ plays: md.views, likes: md.likes, comments: md.comments, dur: md.dur },
                                       (md.published || "").slice(2));
      }
    }
    if (!need.length || _ytBusy) return;
    need = need.slice(0, 50);
    for (var j = 0; j < need.length; j++) _ytAsked[need[j]] = 1;
    _ytBusy = true;
    _gmPost(BASE + "/api/yt/details", { ids: need }, function (st, text) {
      _ytBusy = false;
      try { var d = JSON.parse(text); if (d && d.items) for (var k in d.items) _ytMeta[k] = d.items[k]; } catch (e) {}
    }, function () { _ytBusy = false; for (var j = 0; j < need.length; j++) delete _ytAsked[need[j]]; });
  }
  function _ytRank(key) {
    var cs = _ytCards(), seen = {}, list = [];
    for (var i = 0; i < cs.length; i++) {
      var id = cs[i][1], md = _ytMeta[id]; if (!md || seen[id]) continue; seen[id] = 1;
      var im = cs[i][0].querySelector("img");
      var card = cs[i][0].closest("ytm-shorts-lockup-view-model, ytm-shorts-lockup-view-model-v2, ytd-reel-item-renderer") || cs[i][0].parentElement;
      list.push({ id: id, md: md, thumb: im ? im.src : "", title: card ? (card.innerText || "").split("\n")[0] : "" });
    }
    var val = function (x) { return key === "published" ? (x.md.published || "") : (x.md[key] || 0); };
    list.sort(function (x, y) { var a = val(x), b = val(y); return a < b ? 1 : a > b ? -1 : 0; });
    var o = document.getElementById("ss-ig-rank"); if (o) o.remove();
    o = document.createElement("div"); o.id = "ss-ig-rank";
    o.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:2147483647;display:flex;align-items:center;justify-content:center;padding:20px;font-family:system-ui,sans-serif";
    var box = document.createElement("div");
    box.style.cssText = "background:#161616;color:#eee;border-radius:14px;padding:16px;max-width:1600px;width:96vw;max-height:92vh;overflow:auto;position:relative";
    var nm = { views: "▶ 조회수순", likes: "❤ 좋아요순", comments: "💬 댓글순", published: "📅 최신순" }[key];
    box.innerHTML = "<button type='button' class='x' style='position:absolute;top:6px;right:12px;background:none;border:none;color:#fff;font-size:22px;cursor:pointer'>✕</button>" +
      "<div style='font-weight:800;margin-bottom:10px'>" + nm + " · " + list.length + "개 (이 화면에서 읽은 영상 — 아래로 내리면 늘어나요)</div>";
    var grid = document.createElement("div");
    grid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px";
    if (!list.length) grid.textContent = "아직 읽은 영상이 없어요. 몇 초 기다리거나 화면을 조금 내려 보세요.";
    for (var n = 0; n < list.length; n++) {
      var it = list[n], a2 = document.createElement("a");
      a2.href = "https://www.youtube.com/shorts/" + it.id;
      a2.style.cssText = "display:block;background:#222;border-radius:10px;overflow:hidden;color:#eee;text-decoration:none";
      a2.innerHTML = "<img src='" + _esc(it.thumb) + "' style='width:100%;height:280px;object-fit:cover;display:block;background:#000'>" +
        "<div style='padding:6px 8px;font-size:12px'>#" + (n + 1) + "  " + _esc(_igMediaBadge({ plays: it.md.views, likes: it.md.likes, comments: it.md.comments, dur: it.md.dur }, (it.md.published || "").slice(2))) + "</div>" +
        "<div style='padding:0 8px 8px;font-size:12px;color:#aaa;max-height:32px;overflow:hidden'>" + _esc(it.title) + "</div>";
      grid.appendChild(a2);
    }
    box.appendChild(grid); o.appendChild(box); document.body.appendChild(o);
    box.querySelector(".x").addEventListener("click", function () { o.remove(); });
    o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
  }
  function _ytRankRow() {
    var row = document.createElement("div");
    row.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px";
    [["views", "▶ 조회수순"], ["likes", "❤ 좋아요순"], ["comments", "💬 댓글순"], ["published", "📅 최신순"]].forEach(function (k) {
      row.appendChild(_igBtn(k[1], "이 검색의 Shorts 를 " + k[1].slice(2), function () { _ytRank(k[0]); }));
    });
    return row;
  }
  function _ytResultsTick() {
    try {
      var els = document.querySelectorAll("#ss-grab-btn,#ss-chadd-btn,#ss-lens-btn,#ss-adopt-btn,#ss-seek");
      for (var i = 0; i < els.length; i++) els[i].remove();
    } catch (e) {}
    try { addAnchorCardBtns(); } catch (e) {}
    try { _ytPreviewBtn(); } catch (e) {}
    try { _ytBadges(); } catch (e) {}
  }
  // 미리보기는 마우스를 올린 뒤 바로 뜬다 — 2초 tick만 기다리면 그사이 📥가 안 보인다.
  // 더 새 로직이 이어받으면(버전 가드) 이 리스너는 아무것도 안 한다.
  var _pvWait = 0;
  if (document.addEventListener) document.addEventListener("mouseover", function () {
    if (window.__ssGrabVer !== LOGIC_VER || !_ytResults() || _pvWait) return;
    _pvWait = setTimeout(function () { _pvWait = 0; try { _ytPreviewBtn(); } catch (e) {} }, 400);
  }, true);

  // 접힌 카드의 배지 숨기기(관제 156, 2026-10-08 사장님 "스크롤 내리면 위에 아이콘이 줄지어 남는다"):
  //   인스타는 위로 지나간 줄의 카드를 납작하게 접어 두는데(앵커는 남음) 거기 붙인 📅·🔍·📥가 검색 판 위에 줄지어 떴다.
  //   카드가 120px 보다 작아지면 숨기고, 다시 펴지면 보인다. 스크롤마다(한 프레임에 한 번) + tick 마다.
  function _hideCollapsedBadges() {
    var bs = document.querySelectorAll(".ss-card-info, .ss-card-lens, .ss-card-grab:not(.ss-pv-grab)");
    // ★2026-10-08 두 번째 수리(사장님 "왜 자꾸 안 고치나"): 첫 수리는 '카드가 접힌다'는 짐작이었고 틀렸다 —
    //   실제로는 스크롤해도 고정된 검색 머리(검색창·좋아요순 줄)가 첫 줄 카드 윗부분을 **덮는데**, 카드 왼쪽 위 📥가
    //   그 위로 튀어나왔다(날짜 배지는 카드 아래라 안 덮여 멀쩡했다). 짐작 대신 **그 자리에 실제로 카드가 보이는가**를
    //   브라우저에 묻는다(elementsFromPoint): 버튼 가운데 점의 맨 위 요소가 그 카드 안이 아니면 덮인 것 → 숨김.
    //   display 가 아니라 visibility 로 숨긴다 — 자리(좌표)가 남아야 다음 프레임에 다시 잴 수 있다.
    for (var i = 0; i < bs.length; i++) {
      var el = bs[i], a = el.parentElement; if (!a) continue;
      var r = a.getBoundingClientRect(), hide = r.width < 120 || r.height < 120;
      if (!hide && document.elementsFromPoint) {
        var q = el.getBoundingClientRect(), cx = q.left + q.width / 2, cy = q.top + q.height / 2;
        if (q.width && cy >= 0 && cy <= innerHeight && cx >= 0 && cx <= innerWidth) {
          var st = document.elementsFromPoint(cx, cy), top = null;
          for (var k = 0; k < st.length; k++) { if (st[k] !== el && !el.contains(st[k])) { top = st[k]; break; } }
          if (top && !a.contains(top) && !top.contains(a)) hide = true;
        }
      }
      if (el.style.display === "none" && el.__ssHid) el.style.display = "";      // 옛 판(display)으로 숨긴 것 되살림
      if (hide && !el.__ssHid) { el.__ssHid = 1; el.style.visibility = "hidden"; }
      else if (!hide && el.__ssHid) { el.__ssHid = 0; el.style.visibility = ""; }
    }
  }
  var _hcbRaf = 0;
  if (window.addEventListener) window.addEventListener("scroll", function () {
    if (_hcbRaf || window.__ssGrabVer !== LOGIC_VER) return;
    _hcbRaf = requestAnimationFrame(function () { _hcbRaf = 0; try { _hideCollapsedBadges(); } catch (e) {} });
  }, true);
  // ── 검색 썸네일 한국어 한 줄(관제 174, 2026-10-10 사장님 "어떤 영상인지 한국말로 · 처음에 볼 수 있게 · 돈 안 들게") ──
  //   번역 = 크롬 내장 Translator(PC 안에서 돎, 서버 호출 0·비용 0). 없으면(옛 크롬) 아무것도 안 그린다.
  //   플랫폼마다 다른 건 '카드에서 글 꺼내기' 하나뿐 → 표 KO_CARD 한 곳. 그리기·번역·캐시는 _koTick 한 곳.
  var KO_CARD = {
    instagram: { sel: 'a[href*="/reel/"],a[href*="/p/"]', text: function (a) {
      var m = (a.getAttribute("href") || "").match(/\/(?:reel|reels|p)\/([A-Za-z0-9_-]+)/);
      return m && _igMedia[m[1]] ? _igMedia[m[1]].caption : ""; } },
    youtube: { sel: 'a[href^="/shorts/"]', text: function (a) { return _koNear(a, "h3,[class*='title'],[aria-label]"); } },
    tiktok: { sel: 'a[href*="/video/"]', text: function (a) { return _koNear(a, '[data-e2e*="desc"]'); } },
    pinterest: { sel: '[data-test-id="pin"],a[href*="/pin/"]', text: function (a) { return _koNear(a, '[data-test-id*="title"],[data-test-id*="description"]'); } },
    douyin: { sel: 'a[href*="/video/"]', text: function (a) { return _koNear(a, '[class*="title"],[class*="desc"]'); } },
    xiaohongshu: { sel: 'section.note-item a[href*="/explore/"],section.note-item a[href*="/search_result/"]', text: function (a) {
      var s = a.closest("section.note-item"); var t = s && s.querySelector(".title,.footer .title,[class*='title']");
      return t ? t.textContent : _koNear(a, ""); } }
  };
  // 카드 근처의 설명 글: 지정 칸 → 그림 alt → 카드 묶음의 글 순서로(사이트가 칸 이름을 바꿔도 alt·글로 버틴다)
  function _koNear(a, sel) {
    var p = a;
    for (var i = 0; i < 5 && p; i++, p = p.parentElement) {
      var e = sel ? p.querySelector(sel) : null;
      var t = e && (e.getAttribute("aria-label") || e.textContent || "").trim();
      if (t && t.length > 3) return t;
    }
    var im = a.querySelector("img[alt]"), alt = im && (im.getAttribute("alt") || "").trim();
    return alt && alt.length > 6 ? alt : "";
  }
  // 언어는 글자 모양으로 고른다(크롬 언어 판별기는 모델이 없을 때가 많다 — 2026-10-10 실측 NotSupportedError)
  function _koLang(t) {
    if (/[가-힣]/.test(t) && (t.match(/[가-힣]/g) || []).length > t.length / 4) return "ko";
    if (/[぀-ヿ]/.test(t)) return "ja";
    if (/[一-鿿]/.test(t)) return "zh";
    return "en";
  }
  var _koDone = {}, _koTr = {}, _koBusy = 0, _koOff = false;
  function _koClean(t) {
    return String(t || "").replace(/#[^\s#]+/g, function (h) { return h.slice(1); })   // 해시태그는 낱말로
      .replace(/https?:\/\/\S+/g, "").replace(/\s+/g, " ").trim().slice(0, 140);
  }
  function _koTranslator(lang) {
    if (_koTr[lang]) return _koTr[lang];
    var T = typeof Translator !== "undefined" ? Translator : null;
    if (!T) { _koOff = true; return null; }
    _koTr[lang] = T.create({ sourceLanguage: lang, targetLanguage: "ko" }).catch(function (e) {
      console.warn("[담기] 한국어 번역기 준비 실패(" + lang + ")", e); delete _koTr[lang]; return null; });
    return _koTr[lang];
  }
  function _koLabel(a, txt) {
    var el = a.querySelector(".ss-card-ko");
    if (!el) {
      if (getComputedStyle(a).position === "static") a.style.position = "relative";
      el = document.createElement("div"); el.className = "ss-card-ko";
      el.style.cssText = "position:absolute;left:4px;right:4px;top:40px;z-index:3;background:rgba(0,0,0,.72);color:#fff;" +
        "font:600 11px/1.35 system-ui,sans-serif;border-radius:6px;padding:3px 6px;pointer-events:none;" +
        "display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden";
      a.appendChild(el);
    }
    if (el.textContent !== txt) el.textContent = txt;
  }
  function _koTick() {
    if (_koOff || isSinglePost()) return;
    var s = _kwSite(), c = s && KO_CARD[s.id];
    if (!c) return;
    var as = document.querySelectorAll(c.sel);
    for (var i = 0; i < as.length; i++) {
      var a = as[i], r = a.getBoundingClientRect();
      if (r.width < 100 || r.height < 120 || r.bottom < 0 || r.top > innerHeight * 2) continue;   // 썸네일 카드·화면 근처만
      var src = _koClean(c.text(a));
      if (!src) continue;
      if (src in _koDone) { if (_koDone[src]) _koLabel(a, _koDone[src]); continue; }
      var lang = _koLang(src);
      if (lang === "ko") { _koDone[src] = ""; continue; }
      if (_koBusy >= 4) continue;                                   // 한 번에 4개까지(화면이 굳지 않게)
      var p = _koTranslator(lang);
      if (!p) return;
      _koBusy++; _koDone[src] = null;
      (function (src0) {
        p.then(function (t) { return t ? t.translate(src0) : ""; })
         .then(function (ko) { _koDone[src0] = (ko || "").trim(); })
         .catch(function (e) { delete _koDone[src0]; console.warn("[담기] 번역 실패", e); })
         .then(function () { _koBusy--; });
      })(src);
    }
  }
  function tick() { try{_koTick();}catch(e){} if (_ytOff()) { _ytClear(); try{_kwClearAll();}catch(e){} return; } if (_ytResults()) { _ytResultsTick(); try{syncKwSearchPanel();}catch(e){} try{syncIgPostKw();}catch(e){} return; } try{addFloatBtn();}catch(e){} try{addCardBtns();}catch(e){} try{addAnchorCardBtns();}catch(e){} try{addDouyinCardBtns();}catch(e){} try{addPinCardBtns();}catch(e){} try{syncFloat();}catch(e){} try{syncChannelBtn();}catch(e){} try{syncExtraBtns();}catch(e){} try{syncSeekBar();}catch(e){} try{syncGridBadges();}catch(e){} try{syncIgKwBar();}catch(e){} try{syncKwSearchPanel();}catch(e){} try{syncIgPostKw();}catch(e){} try{_dockBtns();}catch(e){} try{_hideCollapsedBadges();}catch(e){} try{syncOvBox();}catch(e){} }
  tick();
  // SPA라 스크롤·재검색으로 카드가 갈아끼워져도 버튼을 계속 유지한다.
  // 핸들을 남긴다 — 더 새로운 로직이 로드되면 위 가드가 이걸 끄고 이어받는다.
  window.__ssGrabTimer = setInterval(tick, 2000);
})();
