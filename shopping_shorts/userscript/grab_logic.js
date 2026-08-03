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

  function openGrab(url, thumb, title) {
    window.open(
      BASE + "/api/grab?url=" + encodeURIComponent(url) +
        "&thumbnail=" + encodeURIComponent(thumb || "") +
        "&title=" + encodeURIComponent((title || "").slice(0, 120)),
      "ss_grab", "width=380,height=220"
    );
  }

  // ── 채널등록 버튼(인스타 전용, 2026-08-03 사장님 요청): 지금 보는 게시물의 '채널'을
  // 레퍼런스 추적목록에 등록한다. 게시물/릴스 페이지면 URL을 서버로 보내 yt-dlp가 채널을
  // 해석해 등록, 프로필 페이지(/{username}/)면 그 계정을 바로 등록. popup GET이라
  // 서버 세션 쿠키가 실려 관리자 가드가 그대로 동작(/api/grab과 같은 방식).
  var _IG_RESERVED = { p: 1, reel: 1, reels: 1, explore: 1, stories: 1, accounts: 1,
                       direct: 1, tv: 1 };
  function _igProfileName() {
    var m = location.pathname.match(/^\/([^/]+)\/?(reels\/?)?$/);
    return (m && !_IG_RESERVED[m[1]]) ? m[1] : "";
  }
  function addChannelBtn() {
    if (location.host.indexOf("instagram.com") < 0) return;
    if (document.getElementById("ss-chadd-btn") || !document.body) return;
    var prof = _igProfileName();
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
      var p = _igProfileName();
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
  function syncSeekBar() {
    if (location.host.indexOf("instagram.com") < 0) return;
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
      box.innerHTML = "<span title='장면 이동'>⏱</span>" +
        "<input id='ss-seek-r' type='range' min='0' max='100' step='0.1' value='0' style='width:150px;cursor:pointer'>" +
        "<span id='ss-seek-t' style='min-width:70px;text-align:right'>0:00/0:00</span>";
      document.body.appendChild(box);
      var r = document.getElementById("ss-seek-r");
      r.addEventListener("input", function () {
        var vv = _igVideo(); if (vv) { try { vv.currentTime = parseFloat(this.value); } catch (e) {} }
      });
    }
    var r2 = document.getElementById("ss-seek-r"), t2 = document.getElementById("ss-seek-t");
    if (r2 && t2) {
      r2.max = v.duration;
      if (document.activeElement !== r2) r2.value = v.currentTime;   // 드래그 중엔 안 덮음
      t2.textContent = _fmtT(v.currentTime) + "/" + _fmtT(v.duration);
    }
  }
  function _lensRun(url) {
    var v = _igVideo();
    var t = (v && isFinite(v.currentTime)) ? Math.round(v.currentTime * 10) / 10 : null;
    if (typeof GM_xmlhttpRequest === "undefined") {   // 폴백: 랭킹 페이지 딥링크
      window.open(BASE + "/?lens_url=" + encodeURIComponent(url), "_blank"); return;
    }
    _lensOverlay("<div style='padding:30px;text-align:center;color:#aaa'>🔗 원본·유사 영상 추적 중… (10~20초)</div>");
    GM_xmlhttpRequest({
      method: "POST", url: BASE + "/api/lens/trace_url",
      headers: { "Content-Type": "application/json" },
      data: JSON.stringify(t === null ? { url: url } : { url: url, t: t }),
      onload: function (r) {
        var d = {};
        try { d = JSON.parse(r.responseText); } catch (e) {}
        if (r.status === 429) { _lensOverlay("<div style='padding:20px;color:#e0623d'>💰 " + _esc(d.error || "이번 달 렌즈 한도 초과") + "</div>"); return; }
        if (!d.ok) { _lensOverlay("<div style='padding:20px;color:#e0623d'>❌ " + _esc(d.error || "추적 실패 — 로그인 상태를 확인해 주세요") + "</div>"); return; }
        var items = d.items || [];
        if (!items.length) { _lensOverlay("<div style='padding:20px;color:#aaa'>비슷한 영상을 못 찾았어요. 다른 장면의 링크로 시도해 보세요.</div>"); return; }
        var h = "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px'>";
        for (var i = 0; i < items.length && i < 40; i++) {
          var it = items[i];
          h += "<div style='background:#222;border-radius:10px;overflow:hidden'>" +
            "<a href='" + _esc(it.url) + "' target='_blank' rel='noopener'>" +
            (it.thumbnail ? "<img src='" + _esc(it.thumbnail) + "' referrerpolicy='no-referrer' style='width:100%;height:110px;object-fit:cover;display:block;background:#000'>" :
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
        var ov = document.getElementById("ss-lens-ov");
        var bs = ov.querySelectorAll("button[data-u]");
        for (var j = 0; j < bs.length; j++) {
          bs[j].addEventListener("click", function () {
            openGrab(this.getAttribute("data-u"), this.getAttribute("data-t"), this.getAttribute("data-n"));
          });
        }
      },
      onerror: function () { _lensOverlay("<div style='padding:20px;color:#e0623d'>❌ 서버 연결 실패</div>"); }
    });
  }
  function syncExtraBtns() {
    if (location.host.indexOf("instagram.com") < 0) return;
    var lens = document.getElementById("ss-lens-btn");
    if (isSinglePost()) {
      _miniBtn("ss-lens-btn", "🔍 렌즈", "이 영상으로 원본·유사 레퍼런스 역추적(화면 안에서)", 122, "#37b0e0",
               function () { _lensRun(location.href); });
    } else if (lens) { lens.remove(); }
    var coll = document.getElementById("ss-coll-btn"); if (coll) coll.remove();   // ⭐ 제거(담기와 중복)
  }
  function syncChannelBtn() {
    var b = document.getElementById("ss-chadd-btn");
    var want = location.host.indexOf("instagram.com") >= 0 && (isSinglePost() || _igProfileName());
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
      openGrab(location.href, meta("og:image"), meta("og:title") || document.title || "");
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
    function openGrab(url, thumb, title) {
      window.open(BASE + "/api/grab?url=" + encodeURIComponent(url) + "&thumbnail=" + encodeURIComponent(thumb || "") + "&title=" + encodeURIComponent((title || "").slice(0, 120)), "ss_grab", "width=380,height=220");
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
            if (id) openGrab("https://www.douyin.com/video/" + id, img.src || "", img.alt || "");
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

  function tick() { try{addFloatBtn();}catch(e){} try{addCardBtns();}catch(e){} try{addAnchorCardBtns();}catch(e){} try{addDouyinCardBtns();}catch(e){} try{syncFloat();}catch(e){} try{syncChannelBtn();}catch(e){} try{syncExtraBtns();}catch(e){} try{syncSeekBar();}catch(e){} }
  tick();
  // SPA라 스크롤·재검색으로 카드가 갈아끼워져도 버튼을 계속 유지한다.
  setInterval(tick, 2000);
})();
