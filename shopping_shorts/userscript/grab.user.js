// ==UserScript==
// @name         로또 · 원클릭 담기
// @namespace    lotto.shopping_shorts
// @version      1.2.0
// @description  유튜브·틱톡·샤오홍슈·도우인 영상에 '📥 담기' 버튼을 띄운다. 검색 그리드에선 영상 카드마다, 단일 영상 페이지에선 화면 우하단에.
// @match        https://www.youtube.com/*
// @match        https://www.tiktok.com/*
// @match        https://*.xiaohongshu.com/*
// @match        https://*.rednote.com/*
// @match        https://*.douyin.com/*
// @match        https://*.iesdouyin.com/*
// @run-at       document-idle
// @downloadURL  https://shoppingshorts.duckdns.org/grab.user.js
// @updateURL    https://shoppingshorts.duckdns.org/grab.user.js
// ==/UserScript==
// 담기는 window.open("우리서버/api/grab?...")로 처리한다. top-level 이동이라 세션쿠키가
// (samesite=lax) 실려 고객이 식별되고, CSP·@grant도 필요 없다.
// 카드 셀렉터(section.note-item / a.cover)는 2026-07-19 rednote.com 로그인 상태 실측으로 확정.
(function () {
  "use strict";
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

  // ── 카드별 버튼: 샤오홍슈/도우인(rednote) 검색·탐색 그리드의 영상 카드마다 ──
  // 카드=section.note-item, 커버 링크=a.cover(→/search_result/{id} 또는 /explore/{id}).
  function addCardBtns() {
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

  function tick() { addFloatBtn(); addCardBtns(); syncFloat(); }
  tick();
  // SPA라 스크롤·재검색으로 카드가 갈아끼워져도 버튼을 계속 유지한다.
  setInterval(tick, 2000);
})();
