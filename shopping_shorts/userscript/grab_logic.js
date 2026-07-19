// 로또 · 원클릭 담기 — 실제 로직 (grab.user.js 로더가 서버에서 이 파일을 매번 불러와 실행).
// ★이 파일을 고치면 모든 사용자가 다음 새로고침에 자동 반영된다(재설치 불필요).
// 로직 버전: 2026-07-19-b  (틱톡·인스타 카드별 담기 추가)
(function () {
  "use strict";
  if (window.__ssGrabLoaded) return;   // 로더가 중복 실행돼도 한 번만
  window.__ssGrabLoaded = true;
  var BASE = "https://shoppingshorts.duckdns.org";

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
    if (f) f.style.display = document.querySelector(".ss-card-grab") ? "none" : "";
  }

  // 검색·탐색 '그리드' 페이지에서만 카드 버튼을 붙인다. 단일 영상 페이지에선 관련영상 카드가
  // 있어도 카드버튼을 안 붙여야 플로팅(본 영상 담기)이 안 가려진다(2026-07-19 보강).
  function isGridPage() {
    return /(^|\/)(search|explore|tag)(\/|$|\?)/.test(location.pathname + location.search) ||
           /\/search_result/.test(location.pathname);
  }

  // ── 카드별 버튼: 샤오홍슈/도우인(rednote) 검색·탐색 그리드의 영상 카드마다 ──
  // 카드=section.note-item, 커버 링크=a.cover(→/search_result/{id} 또는 /explore/{id}).
  function addCardBtns() {
    if (!isGridPage()) return;
    var cards = document.querySelectorAll("section.note-item");
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      if (card.querySelector(".ss-card-grab")) continue;   // 중복 방지
      var cover = card.querySelector('a.cover[href], a[href*="/search_result/"], a[href*="/explore/"]');
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
          var cv = card.querySelector('a.cover[href], a[href*="/search_result/"], a[href*="/explore/"]');
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
  function addAnchorCardBtns() {
    if (!isGridPage()) return;
    var links = document.querySelectorAll('a[href*="/video/"], a[href*="/p/"], a[href*="/reel/"]');
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      var r = a.getBoundingClientRect();
      if (r.width < 120 || r.height < 120) continue;   // 카드 크기 썸네일 링크만(작은 링크 제외)
      if (a.getAttribute("data-ssgrab")) continue;      // 중복 방지
      a.setAttribute("data-ssgrab", "1");
      if (getComputedStyle(a).position === "static") a.style.position = "relative";
      var b = document.createElement("button");
      b.className = "ss-card-grab";
      b.textContent = "📥";
      b.title = "이 영상 담기";
      b.style.cssText =
        "position:absolute;top:8px;right:8px;z-index:99999;background:#1f6feb;color:#fff;" +
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

  function tick() { addFloatBtn(); addCardBtns(); addAnchorCardBtns(); syncFloat(); }
  tick();
  // SPA라 스크롤·재검색으로 카드가 갈아끼워져도 버튼을 계속 유지한다.
  setInterval(tick, 2000);
})();
