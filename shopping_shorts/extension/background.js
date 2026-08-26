// 로또 · 원클릭 담기 — 서비스 워커.
// 설치 직후 안내 페이지를 한 번 열어준다(사용자가 '설치는 됐는데 이제 뭐하지?'로 멈추지 않게).
// 그 외에는 하는 일이 없다 — 실제 동작은 전부 content.js/inject.js가 한다.
chrome.runtime.onInstalled.addListener(function (details) {
  if (details && details.reason === "install") {
    try {
      chrome.tabs.create({ url: "https://shoppingshorts.duckdns.org/grab?installed=ext" });
    } catch (e) {}
  }
});

// ── 서버 요청 대행(2026-08-18) ────────────────────────────────────────────────
// 콘텐츠 스크립트가 직접 fetch하면 **그 페이지의 CORS**를 그대로 받는다(MV3).
// instagram.com에서 우리 서버로 POST → 브라우저가 OPTIONS를 먼저 쏘고, 우리 로그인
// 가드가 401로 막아 요청이 통째로 죽었다(실측: "OPTIONS /api/lens/trace_url" 401).
// 서비스워커는 host_permissions 덕에 CORS를 안 타므로 여기서 보낸다.
// ★우리 서버로 가는 요청만 대행한다 — 아무 도메인이나 열어주면 페이지 스크립트가
//   사용자 쿠키로 임의 요청을 쏘는 통로가 된다.
var SS_BASE = "https://shoppingshorts.duckdns.org/";
chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
  if (!msg || !msg.__ssRelay) return;
  if (String(msg.url || "").indexOf(SS_BASE) !== 0) { sendResponse({ status: 0, text: "" }); return; }
  var opt = { method: msg.method || "GET", credentials: "include", headers: msg.headers || {} };
  if (msg.body) opt.body = msg.body;
  fetch(msg.url, opt)
    .then(function (r) { return r.text().then(function (t) { sendResponse({ status: r.status, text: t }); }); })
    .catch(function () { sendResponse({ status: 0, text: "" }); });
  return true;   // 비동기 응답 — 이 true가 없으면 sendResponse가 무시된다
});
