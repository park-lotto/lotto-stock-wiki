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
