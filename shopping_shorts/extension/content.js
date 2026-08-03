// 로또 · 원클릭 담기 — 콘텐츠 스크립트(격리 월드).
//
// 이 확장은 **텀퍼몽키 대체품**이다. 하는 일은 grab.user.js(로더)와 똑같다:
//   ① 서버에서 실제 로직(grab_logic.js)을 가져와 페이지에서 돌린다
//   ② 로직이 서버 API를 부를 수 있게 GM_xmlhttpRequest 역할의 '브리지'를 제공한다
// 로직 파일 자체는 건드리지 않는다 — 유저스크립트 사용자와 **같은 파일을 공유**하므로
// 서버에서 로직을 고치면 양쪽 모두 자동 반영된다(재설치 불필요).
//
// ★MV3 제약(추측 금지 — 여기가 설계의 핵심):
//   - MV3는 **원격 코드 실행을 금지**한다. fetch로 받은 코드를 eval()하면 정책 위반이라
//     웹스토어 심사에서 거부되고, CSP상 실행도 막힌다. 그래서 코드를 '가져와 실행'하지 않고
//     `<script src="서버주소">`를 페이지에 꽂아 **브라우저가 정상 로드**하게 한다.
//     (유저스크립트 로더가 인스타에서 eval로 죽어 Blob 폴백을 넣었던 것과 같은 문제 —
//      여기선 아예 src 로드라 CSP unsafe-eval이 필요 없다.)
//   - 단 페이지 CSP의 script-src가 우리 도메인을 막으면 <script src>도 막힌다.
//     인스타가 그렇다(실측). 그래서 **확장 자체 파일(inject.js)을 web_accessible_resources로
//     꽂는 경로**를 기본으로 쓴다 — 확장 리소스는 페이지 CSP의 적용을 받지 않는다.
//     inject.js가 페이지 월드에서 로직을 받아 실행한다.
(function () {
  "use strict";

  var BASE = "https://shoppingshorts.duckdns.org";

  // ── ① GM 브리지 ────────────────────────────────────────────────
  // 로직(페이지 월드)은 GM_xmlhttpRequest가 없으면 postMessage로 요청을 보낸다
  // (grab_logic.js의 _gmPost/_gmGet 폴백). 그 요청을 여기서 받아 대신 수행한다.
  // 콘텐츠 스크립트의 fetch는 host_permissions 덕에 **쿠키가 실리고 CORS를 안 탄다** —
  // 로그인·크레딧 가드가 그대로 동작한다(유저스크립트의 @connect와 같은 역할).
  window.addEventListener("message", function (ev) {
    // 같은 페이지가 보낸 것만 받는다(다른 프레임/확장 메시지 무시).
    if (ev.source !== window) return;
    var d = ev.data;
    if (!d || !d.__ssGmFetch || !d.reqId) return;
    // ★우리 서버로 가는 요청만 대행한다 — 페이지 스크립트가 이 브리지로 임의 도메인에
    //   쿠키 실린 요청을 쏘는 걸 막는다(유저스크립트 로더와 동일한 안전장치).
    if (String(d.url || "").indexOf(BASE + "/") !== 0) return;

    // 즉시 ACK — 로직은 1.5초 안에 ACK가 없으면 '브리지 없음'으로 보고 딥링크로 폴백한다.
    window.postMessage({ __ssGmAck: true, reqId: d.reqId }, "*");

    var opt = {
      method: d.method || "GET",
      credentials: "include",          // 로그인 쿠키 — 크레딧·회원 가드에 필요
      headers: d.headers || {}
    };
    if (d.body) opt.body = d.body;

    fetch(d.url, opt)
      .then(function (r) {
        return r.text().then(function (t) {
          window.postMessage({ __ssGmResult: true, reqId: d.reqId,
                               status: r.status, text: t }, "*");
        });
      })
      .catch(function () {
        window.postMessage({ __ssGmResult: true, reqId: d.reqId, status: 0, text: "" }, "*");
      });
  });

  // ── ② 로직 주입 ────────────────────────────────────────────────
  // 확장 리소스를 페이지 월드에 꽂는다. inject.js가 거기서 서버 로직을 실행한다.
  // (콘텐츠 스크립트는 격리 월드라 페이지의 video·React 내부에 못 닿는다 —
  //  로직은 반드시 페이지 월드에서 돌아야 한다.)
  try {
    var s = document.createElement("script");
    s.src = chrome.runtime.getURL("inject.js");
    s.dataset.ssBase = BASE;
    s.onload = function () { s.remove(); };
    (document.head || document.documentElement).appendChild(s);
  } catch (e) {
    console.error("[담기] 주입 실패", e);
  }
})();
