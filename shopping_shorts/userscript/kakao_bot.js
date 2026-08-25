// 숏템메이커 카톡 답변봇 — 메신저봇R 스크립트
// ★이 파일은 배달만 한다. 판정·검색·생성·상한·정지는 전부 서버에 있다(0순위-B).
//   카톡 업데이트로 여기가 깨져도 답변 품질 코드는 무사하다.
//
// ★통신은 jsoup을 직접 쓴다(2026-08-25 조사).
//   - `Utils.getWebText2(url, "UTF-8")`는 **인자 2개짜리 레거시**라 POST·헤더를 못 싣는다
//     (공식 문서가 "하위호환용, 쓰지 마라"로 표시).
//   - `Http.request`는 헤더·메서드는 받지만 **본문(body) 키가 문서에 없고** 응답이
//     jsoup 객체라 문자열을 꺼내는 법도 안 적혀 있다.
//   - 그래서 그 둘이 안에서 쓰는 **jsoup을 그대로** 쓴다 — API가 널리 알려져 있고 안 변한다.
//     `ignoreContentType(true)`가 없으면 JSON 응답에서 UnsupportedMimeTypeException이 난다.
//
// 설치: 메신저봇R → 새 스크립트 → 이 내용 붙여넣기 → 아래 두 줄만 채운다.
const API = "https://shoppingshorts.duckdns.org/api/kakao/ask";
const SECRET = "여기에_서버와_같은_비밀키";

function response(room, msg, sender, isGroupChat, replier) {
  if (msg.charAt(0) !== "!") return;          // 호출된 때만 — 판정 자체는 서버가 다시 한다
  try {
    const body = JSON.stringify({ room: room, sender: sender, text: msg });
    const text = org.jsoup.Jsoup.connect(API)
      .header("Content-Type", "application/json; charset=utf-8")
      .header("X-Bot-Secret", SECRET)
      .requestBody(body).method(org.jsoup.Connection.Method.POST)
      .ignoreContentType(true).ignoreHttpErrors(true)
      .timeout(20000).execute().body();
    const reply = JSON.parse(text).reply;     // 401·오류면 reply가 없어 조용히 끝난다
    if (reply) {
      java.lang.Thread.sleep(800);            // 즉답은 봇 티가 난다
      replier.reply(reply);
    }
  } catch (e) {
    // 조용히 넘긴다 — 방에 오류 메시지를 뿌리면 그것도 도배가 된다
  }
}
