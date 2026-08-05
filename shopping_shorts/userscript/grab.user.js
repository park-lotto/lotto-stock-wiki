// ==UserScript==
// @name         로또 · 원클릭 담기
// @namespace    lotto.shopping_shorts
// @version      2.3.0
// @description  플랫폼 영상에 '📥 담기' 버튼. ★한 번만 설치하면 됩니다 — 담기 로직은 서버에서 매번 불러오므로 이후 업데이트는 재설치 없이 자동 반영됩니다.
// @match        https://www.youtube.com/*
// @match        https://www.tiktok.com/*
// @match        https://*.instagram.com/*
// @match        https://*.xiaohongshu.com/*
// @match        https://*.rednote.com/*
// @match        https://*.douyin.com/*
// @match        https://*.iesdouyin.com/*
// @match        https://shoppingshorts.duckdns.org/grab*
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
// v2.1.0: /grab(설치 안내 페이지)도 @match에 추가 — 설치가 끝나면 이 로직이 그 페이지에서
// 실행돼 '설치됨' 표식을 남기고, 페이지가 그걸 감지해 자동으로 '완료'로 바꾼다(자가감지 신호등).
// 이 한 줄 때문에 기존 설치자는 한 번만 재설치하면 되고, 이후 로직 변경은 여전히 재설치 불필요.
(function () {
  "use strict";
  // 분 단위 캐시버스트: 서버 코드를 고치면 늦어도 1분 안에 모두 반영, 그 안에선 캐시 활용.
  var LOGIC_URL = "https://shoppingshorts.duckdns.org/grab_logic.js?v=" + Math.floor(Date.now() / 60000);

  // ★인스타는 eval이 막힌다 (2026-07-29 실측, 이 로더가 인스타에서 통째로 죽던 진짜 원인):
  //   "EvalError: Evaluating a string as JavaScript violates ... 'unsafe-eval' is not an allowed source"
  //   Tampermonkey 샌드박스라도 확장 userscript 컨텍스트가 페이지 CSP를 상속받아 eval이 거부된다
  //   (기존 주석의 "CSP 영향을 받지 않는다"는 틀렸다). 그래서 폴백을 둔다:
  //   인스타 CSP script-src에는 `blob:`이 허용돼 있으므로 Blob URL <script>로 로직을 넣는다.
  //   폴백은 '메인월드'에서 돌지만 로직은 GM API를 안 쓰고 window.open만 쓰므로 그대로 동작한다.
  function runViaBlob(code) {
    try {
      var u = URL.createObjectURL(new Blob([code], { type: "text/javascript" }));
      var s = document.createElement("script");
      s.src = u;
      s.onload = function () { try { URL.revokeObjectURL(u); s.remove(); } catch (e) {} };
      (document.head || document.documentElement).appendChild(s);
      return true;
    } catch (e) { return false; }
  }
  function run(code) {
    try { eval(code); }
    catch (e) { if (!runViaBlob(code)) console.error("[담기] 로직 실행 실패", e); }
  }
  // ★GM 브리지(v2.3.0, 2026-08-03): 인스타에선 로직이 Blob(메인월드)로 돌아 GM API가
  //   없다 → 렌즈 in-page 오버레이가 서버 API를 못 불렀다(쿠키 없는 fetch는 CORS/로그인
  //   벽). 로더(샌드박스, GM 보유)가 postMessage로 요청을 받아 GM_xmlhttpRequest를 대신
  //   수행하고 결과를 되돌려준다. 로직 쪽은 브리지 응답이 없으면(구버전 로더) 딥링크 폴백.
  window.addEventListener("message", function (ev) {
    var d = ev && ev.data;
    if (!d || !d.__ssGmFetch || !d.reqId) return;
    // 우리 서버로 가는 요청만 대행 — 페이지(메인월드) 스크립트가 이 브리지로 임의
    // 도메인에 쿠키 실린 요청을 쏘는 악용을 막는다.
    if (String(d.url || "").indexOf("https://shoppingshorts.duckdns.org/") !== 0) return;
    // 즉시 ACK — 본 응답은 수십 초 걸릴 수 있어, 로직 쪽 '브리지 존재 확인'(1.5초)용.
    window.postMessage({ __ssGmAck: true, reqId: d.reqId }, "*");
    try {
      GM_xmlhttpRequest({
        method: d.method || "GET",
        url: d.url,
        headers: d.headers || {},
        data: d.body || undefined,
        onload: function (r) {
          window.postMessage({ __ssGmResult: true, reqId: d.reqId,
                               status: r.status, text: r.responseText }, "*");
        },
        onerror: function () {
          window.postMessage({ __ssGmResult: true, reqId: d.reqId, status: 0, text: "" }, "*");
        }
      });
    } catch (e) {
      window.postMessage({ __ssGmResult: true, reqId: d.reqId, status: 0, text: "" }, "*");
    }
  });

  try {
    GM_xmlhttpRequest({
      method: "GET",
      url: LOGIC_URL,
      onload: function (r) { if (r && r.status >= 200 && r.status < 400 && r.responseText) run(r.responseText); },
      onerror: function () { console.error("[담기] 로직을 불러오지 못했습니다(네트워크)"); }
    });
  } catch (e) { console.error("[담기] 로더 오류", e); }
})();
