// ==UserScript==
// @name         로또 · 원클릭 담기
// @namespace    lotto.shopping_shorts
// @version      1.1.0
// @description  유튜브·틱톡·샤오홍슈·도우인 영상 페이지에 '📥 담기' 버튼을 띄운다. 누르면 모음집에 담김(드래그·북마크 불필요).
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
// (samesite=lax) 실려 고객이 식별되고, CSP·@grant도 필요 없다(insta 스크립트와 달리
// GM_xmlhttpRequest 불필요). 서버가 작은 팝업으로 "담겼어요"를 보여주고 자동으로 닫는다.
(function () {
  "use strict";
  var BASE = "https://shoppingshorts.duckdns.org";

  function meta(p) {
    var e = document.querySelector('meta[property="' + p + '"]');
    return e ? e.content : "";
  }

  function grab() {
    var th = meta("og:image");
    var ti = meta("og:title") || document.title || "";
    window.open(
      BASE + "/api/grab?url=" + encodeURIComponent(location.href) +
        "&thumbnail=" + encodeURIComponent(th) +
        "&title=" + encodeURIComponent(ti.slice(0, 120)),
      "ss_grab", "width=380,height=220"
    );
  }

  function addBtn() {
    if (document.getElementById("ss-grab-btn") || !document.body) return;
    var b = document.createElement("button");
    b.id = "ss-grab-btn";
    b.textContent = "📥 담기";
    b.title = "이 영상을 스탁브레인 모음집에 담기";
    b.style.cssText =
      "position:fixed;right:18px;bottom:18px;z-index:2147483647;background:#1f6feb;" +
      "color:#fff;border:none;border-radius:24px;padding:12px 18px;font-size:15px;" +
      "font-weight:800;box-shadow:0 4px 14px rgba(0,0,0,.35);cursor:pointer;font-family:system-ui,sans-serif";
    b.addEventListener("click", function (e) { e.preventDefault(); grab(); });
    document.body.appendChild(b);
  }

  addBtn();
  // 틱톡·샤오홍슈는 SPA라 페이지가 갈아끼워져도 버튼을 계속 유지한다.
  setInterval(addBtn, 2000);
})();
