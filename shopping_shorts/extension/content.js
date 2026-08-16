// 로또 · 원클릭 담기 — 콘텐츠 스크립트(격리 월드).
//
// 이 확장은 **텀퍼몽키 대체품**이다. 로직(grab_logic.js)을 실행하고, 로직이 서버 API를
// 부를 수 있게 GM_xmlhttpRequest 역할의 브리지를 제공한다.
//
// ⚠️★로직 반영 방식이 유저스크립트와 **다르다**(2026-08-17 실사고로 바로잡은 설명).
//   · 유저스크립트: 로더가 매번 서버 /grab_logic.js를 받아 실행 → 서버 배포 = 자동 반영
//   · 확장:        manifest content_scripts에 **패키지 안의 grab_logic.js가 정적 등록**된다
//                  → 서버에 배포해도 **이미 설치된 확장에는 반영되지 않는다. 재설치해야 한다.**
//   예전 주석은 여기에 "재설치 불필요"라고 적어 두었는데 확장에는 거짓이다. 실제로
//   도우인 영상주소 전송 기능을 배포한 뒤 "왜 안 되지"로 한참을 헤맸다(서버는 최신을
//   서빙하고 있었고, 사장님 확장만 옛 코드였다).
//   MV3는 원격 코드 실행을 금지하므로 이 구조를 바꿀 수 없다 — 로직을 고쳤으면
//   **사장님께 재설치를 안내해야 한다**(zip은 요청 때마다 최신 원본으로 다시 만들어진다).
//
// ★★설계 핵심 — 로직을 '페이지 월드'에 주입하지 않고 **여기(격리 월드)서 직접 실행**한다.
//   2026-08-04에 페이지 주입 방식으로 만들었다가 유튜브에서 통째로 죽는 걸 실측했다.
//   유튜브 CSP: script-src 'self' https://www.google.com ... 즉 **우리 도메인도, blob:도
//   전부 차단**된다. 페이지 월드에 코드를 넣는 방법이 아예 없다(<script src>·Blob 모두 실패).
//   반면 콘텐츠 스크립트는 **페이지 CSP의 적용을 받지 않는다** — 확장 권한으로 도는 코드라
//   CSP와 무관하게 실행된다. 그래서 여기서 돌리는 게 유일하게 모든 사이트에서 되는 길이다.
//
//   격리 월드에서 로직이 정상 동작하는 근거(실측 확인):
//     · 로직은 DOM API만 쓴다 — querySelector / video.currentTime / window.open / location.
//       콘텐츠 스크립트는 **DOM을 페이지와 공유**하므로 전부 그대로 된다.
//     · 페이지의 JS 내부(React fiber)를 읽는 코드는 **도우인 전용 한 곳뿐**이고, 그 부분은
//       로직이 스스로 메인월드 스크립트를 주입해 처리한다(원래부터 그렇게 설계돼 있다).
//     · GM_xmlhttpRequest는 `typeof !== "undefined"` 가드가 있어, 없으면 postMessage
//       브리지로 폴백한다 — 그 브리지를 아래에서 우리가 받는다.
(function () {
  "use strict";

  var BASE = "https://shoppingshorts.duckdns.org";

  // ── ① GM 브리지 ────────────────────────────────────────────────
  // 로직이 postMessage로 보내는 요청(__ssGmFetch)을 받아 대신 수행한다.
  // 콘텐츠 스크립트의 fetch는 host_permissions 덕에 **쿠키가 실리고 CORS를 안 탄다** —
  // 로그인·크레딧 가드가 그대로 동작한다(유저스크립트의 @connect와 같은 역할).
  window.addEventListener("message", function (ev) {
    if (ev.source !== window) return;          // 같은 페이지가 보낸 것만
    var d = ev.data;
    if (!d || !d.__ssGmFetch || !d.reqId) return;
    // ★우리 서버로 가는 요청만 대행 — 페이지 스크립트가 이 브리지로 임의 도메인에
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

  // ── ② 로직은 manifest가 직접 실행한다 ──────────────────────────
  // content_scripts.js = ["content.js", "grab_logic.js"] — 이 파일(브리지)이 먼저 등록되고
  // 그다음 로직이 같은 격리 월드에서 돈다. 여기서 로직을 부르지 않는다.
  //
  // ★왜 '서버에서 받아 실행'을 포기했나 (2026-08-04, 유튜브 실측 3연속 실패의 결론):
  //   코드를 런타임에 가져와 돌리는 방법이 **전부 막혀 있다**.
  //     1) 페이지 월드에 <script src="우리도메인">  → 유튜브 CSP script-src에 없어 차단
  //     2) 페이지 월드에 Blob URL <script>          → 유튜브 CSP는 blob:도 차단
  //     3) 격리 월드에서 eval(받아온 코드)          → 확장 CSP가 unsafe-eval 금지로 차단
  //        ("EvalError: ... 'unsafe-eval' is not an allowed source")
  //   → 결국 **확장에 로직을 동봉**하는 것이 크롬이 허용하는 유일한 길이다.
  //     이건 MV3 '원격 코드 금지' 정책과도 맞아서 웹스토어 심사에도 유리하다.
  //
  //   대가: 로직을 고치면 확장 사용자는 **재설치가 필요**하다(유저스크립트 사용자는 종전대로
  //   자동 반영). 그래서 grab_logic.js 원본은 userscript/ 한 곳에만 두고, 배포 시
  //   extension/으로 복사한다 — /grab_extension.zip 라우트가 그 복사를 자동으로 한다.
  //   (두 벌을 손으로 관리하면 반드시 어긋난다.)
})();
