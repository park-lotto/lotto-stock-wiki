// ==UserScript==
// @name         로또 · 원클릭 담기
// @namespace    lotto.shopping_shorts
// @version      2.0.0
// @description  플랫폼 영상에 '📥 담기' 버튼. ★한 번만 설치하면 됩니다 — 담기 로직은 서버에서 매번 불러오므로 이후 업데이트는 재설치 없이 자동 반영됩니다.
// @match        https://www.youtube.com/*
// @match        https://www.tiktok.com/*
// @match        https://*.instagram.com/*
// @match        https://*.xiaohongshu.com/*
// @match        https://*.rednote.com/*
// @match        https://*.douyin.com/*
// @match        https://*.iesdouyin.com/*
// @run-at       document-idle
// @grant        GM_xmlhttpRequest
// @connect      shoppingshorts.duckdns.org
// @downloadURL  https://shoppingshorts.duckdns.org/grab.user.js
// @updateURL    https://shoppingshorts.duckdns.org/grab.user.js
// ==/UserScript==
// ★이 파일은 '로더'다. 실제 담기 로직은 서버 /grab_logic.js 에서 매번 불러와 실행한다.
// 그래서 로직을 아무리 바꿔도 사용자는 재설치할 필요가 없다(이 로더는 한 번만 설치).
// GM_xmlhttpRequest로 받아 sandbox에서 eval → 페이지 CSP의 영향을 받지 않는다.
// 이 로더 자체(@match·@grant)를 바꿀 때만 재설치가 필요하므로 웬만하면 안 건드린다.
(function () {
  "use strict";
  // 분 단위 캐시버스트: 서버 코드를 고치면 늦어도 1분 안에 모두 반영, 그 안에선 캐시 활용.
  var LOGIC_URL = "https://shoppingshorts.duckdns.org/grab_logic.js?v=" + Math.floor(Date.now() / 60000);
  function run(code) { try { eval(code); } catch (e) { console.error("[담기] 로직 실행 실패", e); } }
  try {
    GM_xmlhttpRequest({
      method: "GET",
      url: LOGIC_URL,
      onload: function (r) { if (r && r.status >= 200 && r.status < 400 && r.responseText) run(r.responseText); },
      onerror: function () { console.error("[담기] 로직을 불러오지 못했습니다(네트워크)"); }
    });
  } catch (e) { console.error("[담기] 로더 오류", e); }
})();
