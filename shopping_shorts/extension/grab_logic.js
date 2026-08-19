// 로또 · 원클릭 담기 — 실제 로직 (grab.user.js 로더가 서버에서 이 파일을 매번 불러와 실행).
// ★이 파일을 고치면 모든 사용자가 다음 새로고침에 자동 반영된다(재설치 불필요).
// 로직 버전: 2026-08-03-a  (틱톡 뷰어 카드버튼 잔존 정리 + 빈 앵커 버튼 차단)
(function () {
  "use strict";
  if (window.__ssGrabLoaded) return;   // 로더가 중복 실행돼도 한 번만
  window.__ssGrabLoaded = true;
  var BASE = "https://shoppingshorts.duckdns.org";

  // ── 설치 확인 비컨 ─────────────────────────────────────────────
  // 이 로직이 우리 설치 안내 페이지(shoppingshorts.duckdns.org/grab*)에서 돌면
  // = 유저스크립트가 정상 설치됐다는 뜻. DOM에 표식을 남겨 그 페이지가 "설치 완료"를
  // 스스로 감지하게 한다(사용자가 '됐나?'를 판단할 필요 없음). Tampermonkey 샌드박스는
  // JS 스코프만 격리하고 DOM은 페이지와 공유하므로 이 attribute를 페이지 스크립트가 읽는다.
  // 우리 도메인에선 담기 버튼을 붙이지 않고 여기서 끝낸다(자기 페이지에 엉뚱한 📥 방지).
  try {
    if (location.hostname.indexOf("shoppingshorts.duckdns.org") >= 0) {
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
  function _ttProfile() {   // 틱톡 프로필(/@handle) — 영상 페이지(/@handle/video/..)는 제외
    var m = location.pathname.match(/^\/@([\w.\-]+)\/?$/);
    return m ? m[1] : "";
  }
  function _igProfileName() {
    var m = location.pathname.match(/^\/([^/]+)\/?(reels\/?)?$/);
    return (m && !_IG_RESERVED[m[1]]) ? m[1] : "";
  }
  function addChannelBtn() {
    var host = _snsHost();
    if (!host) return;
    if (document.getElementById("ss-chadd-btn") || !document.body) return;
    var prof = host === "instagram" ? _igProfileName() : _ttProfile();
    if (!isSinglePost() && !prof) return;   // 피드/탐색에선 대상이 모호해 안 띄운다
    var b = document.createElement("button");
    b.id = "ss-chadd-btn";
    b.textContent = "📌 채널등록";
    b.title = "이 게시물의 채널을 레퍼런스 추적목록에 등록";
    b.style.cssText =
      "position:fixed;right:18px;bottom:70px;z-index:2147483647;background:#8250df;" +
      "color:#fff;border:none;border-radius:24px;padding:10px 16px;font-size:14px;" +
      "font-weight:800;box-shadow:0 4px 14px rgba(0,0,0,.35);cursor:pointer;font-family:system-ui,sans-serif";
    b.addEventListener("click", function (e) {
      e.preventDefault();
      // 틱톡은 URL에 @핸들이 들어 있어 서버가 URL만으로 채널을 뽑는다(시드 등록).
      var p = _snsHost() === "instagram" ? _igProfileName() : "";
      var q = p ? "username=" + encodeURIComponent(p)
                : "url=" + encodeURIComponent(location.href);
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
    if (!_snsHost()) return;
    var box = document.getElementById("ss-seek");
    if (!isSinglePost()) { if (box) box.remove(); return; }
    var v = _igVideo();
    if (!v) { if (box) box.remove(); return; }
    if (!box) {
      box = document.createElement("div");
      box.id = "ss-seek";
      box.style.cssText = "position:fixed;right:18px;bottom:174px;z-index:2147483647;background:rgba(20,20,20,.92);" +
        "border:1px solid #444;border-radius:14px;padding:8px 12px;display:flex;align-items:center;gap:8px;" +
        "font-family:system-ui,sans-serif;color:#fff;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.35)";
      box.innerHTML = "<button id='ss-seek-p' title='일시정지/재생' style='background:none;border:none;" +
        "color:#fff;font-size:15px;cursor:pointer;padding:0 2px'>⏸</button>" +
        "<input id='ss-seek-r' type='range' min='0' max='100' step='0.1' value='0' style='width:150px;cursor:pointer'>" +
        "<span id='ss-seek-t' style='min-width:70px;text-align:right'>0:00/0:00</span>" +
        "<span id='ss-seek-d' title='영상 등록일' style='color:#aaa;border-left:1px solid #555;padding-left:8px'></span>" +
        "<span id='ss-seek-s' title='조회수·댓글수' style='color:#aaa;border-left:1px solid #555;padding-left:8px'></span>";
      document.body.appendChild(box);
      var r = document.getElementById("ss-seek-r");
      r.addEventListener("input", function () {
        var vv = _igVideo(); if (vv) { try { vv.currentTime = parseFloat(this.value); } catch (e) {} }
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
    var m = location.pathname.match(/\/(?:reel|reels|p|tv|video)\/[A-Za-z0-9_-]+/);
    if (!m) { el.style.display = "none"; return; }
    var key = m[0];
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
  function syncExtraBtns() {
    if (!_snsHost()) return;
    var lens = document.getElementById("ss-lens-btn");
    if (isSinglePost()) {
      _miniBtn("ss-lens-btn", "🔍 렌즈", "이 영상으로 원본·유사 레퍼런스 역추적(화면 안에서)", 122, "#37b0e0",
               function () { _lensRun(location.href); });
    } else if (lens) { lens.remove(); }
    var coll = document.getElementById("ss-coll-btn"); if (coll) coll.remove();   // ⭐ 제거(담기와 중복)
  }
  function syncChannelBtn() {
    var b = document.getElementById("ss-chadd-btn");
    var host = _snsHost();
    var want = !!host && (isSinglePost() ||
                          (host === "instagram" ? _igProfileName() : _ttProfile()));
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
      openGrab(location.href, meta("og:image"), meta("og:title") || document.title || "",
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
  //   20/20 카드에서 aweme_id 추출·버튼부착을 실측 확인했고, 도우인 CSP는 인라인 스크립트를
  //   막지 않는다(실측). 주입 스크립트가 자체 interval로 유지하며, 클릭 시 BASE/api/grab로 바로
  //   담는다(sandbox와의 데이터 왕래 불필요). 주입 실패 시 버튼이 안 생기고 플로팅으로 폴백된다.
  function _douyinMainWorld() {
    if (window.__ssDouyinMW) return;
    window.__ssDouyinMW = true;
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
    if (window.__ssDouyinInjected) return;   // 한 번만 주입(주입된 스크립트가 자체 interval로 유지)
    window.__ssDouyinInjected = true;
    try {
      var sc = document.createElement("script");
      sc.textContent = "(" + _douyinMainWorld.toString() + ")();";
      (document.head || document.documentElement).appendChild(sc);
      sc.remove();
    } catch (e) { window.__ssDouyinInjected = false; }   // 실패 시 다음 tick에 재시도(폴백=플로팅)
  }

  function tick() { try{addFloatBtn();}catch(e){} try{addCardBtns();}catch(e){} try{addAnchorCardBtns();}catch(e){} try{addDouyinCardBtns();}catch(e){} try{syncFloat();}catch(e){} try{syncChannelBtn();}catch(e){} try{syncExtraBtns();}catch(e){} try{syncSeekBar();}catch(e){} try{syncGridBadges();}catch(e){} }
  tick();
  // SPA라 스크롤·재검색으로 카드가 갈아끼워져도 버튼을 계속 유지한다.
  setInterval(tick, 2000);
})();
