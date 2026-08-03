// 로또 · 원클릭 담기 — 페이지 월드 주입기.
//
// content.js가 <script src="chrome-extension://…/inject.js">로 꽂는다. 여기서부터는
// **페이지와 같은 JS 월드**라, 로직이 video 엘리먼트·React 내부·window.open을 정상적으로
// 만질 수 있다(콘텐츠 스크립트의 격리 월드에선 불가능하다).
//
// 하는 일은 한 가지: 서버의 실제 로직(grab_logic.js)을 <script src>로 불러온다.
// ★코드를 fetch해서 eval하지 않는다 — MV3 원격코드 금지 정책 위반이고, 인스타 CSP의
//   unsafe-eval 차단에도 걸린다(유저스크립트 로더가 실제로 여기서 죽었다).
//   src 로드는 CSP script-src만 통과하면 되고, 우리 도메인은 아래 폴백으로 처리한다.
(function () {
  "use strict";
  if (window.__ssGrabInjected) return;        // SPA 재주입 방지
  window.__ssGrabInjected = true;

  var me = document.currentScript;
  var BASE = (me && me.dataset && me.dataset.ssBase) || "https://shoppingshorts.duckdns.org";
  // 분 단위 캐시버스트 — 서버 로직을 고치면 늦어도 1분 안에 모두 반영(로더와 동일 정책).
  var LOGIC_URL = BASE + "/grab_logic.js?v=" + Math.floor(Date.now() / 60000);

  function loadViaScript(done) {
    var s = document.createElement("script");
    s.src = LOGIC_URL;
    s.onload = function () { s.remove(); done(true); };
    s.onerror = function () { s.remove(); done(false); };
    (document.head || document.documentElement).appendChild(s);
  }

  // 폴백: 페이지 CSP(script-src)가 우리 도메인을 막는 경우(인스타 등).
  // 확장의 콘텐츠 스크립트에 코드를 대신 받아달라고 부탁하고, 받은 코드를 **Blob**으로 돈다.
  // 인스타 CSP는 script-src에 blob:을 허용한다(실측 2026-07-29, 유저스크립트에서 검증된 경로).
  function loadViaBlob() {
    var reqId = "logic_" + Date.now() + "_" + Math.random().toString(36).slice(2);
    var done = false;
    function onMsg(ev) {
      if (ev.source !== window) return;
      var d = ev.data;
      if (!d || !d.__ssGmResult || d.reqId !== reqId) return;
      window.removeEventListener("message", onMsg);
      done = true;
      if (!d.text) { console.error("[담기] 로직을 불러오지 못했습니다"); return; }
      try {
        var u = URL.createObjectURL(new Blob([d.text], { type: "text/javascript" }));
        var s = document.createElement("script");
        s.src = u;
        s.onload = function () { URL.revokeObjectURL(u); s.remove(); };
        (document.head || document.documentElement).appendChild(s);
      } catch (e) {
        console.error("[담기] 로직 실행 실패", e);
      }
    }
    window.addEventListener("message", onMsg);
    window.postMessage({ __ssGmFetch: true, reqId: reqId, method: "GET", url: LOGIC_URL }, "*");
    setTimeout(function () {
      if (!done) { window.removeEventListener("message", onMsg);
                   console.error("[담기] 로직 응답 없음(브리지 무응답)"); }
    }, 15000);
  }

  loadViaScript(function (ok) { if (!ok) loadViaBlob(); });
})();
