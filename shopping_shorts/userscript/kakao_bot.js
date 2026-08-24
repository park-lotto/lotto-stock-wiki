// 숏템메이커 카톡 답변봇 — 메신저봇R 스크립트
// ★이 파일은 배달만 한다. 판정·검색·생성·상한·정지는 전부 서버에 있다(0순위-B).
//   카톡 업데이트로 여기가 깨져도 답변 품질 코드는 무사하다.
// 설치: 메신저봇R → 새 스크립트 → 이 내용 붙여넣기 → 아래 두 줄만 채운다.
const API = "https://shoppingshorts.duckdns.org/api/kakao/ask";
const SECRET = "여기에_서버와_같은_비밀키";

function response(room, msg, sender, isGroupChat, replier) {
  if (msg.charAt(0) !== "!") return;          // 호출된 때만 — 판정 자체는 서버가 다시 한다
  try {
    const res = Utils.getWebText2(API, "POST", JSON.stringify({
      room: room, sender: sender, text: msg
    }), { "Content-Type": "application/json", "X-Bot-Secret": SECRET });
    const reply = JSON.parse(res).reply;
    if (reply) {
      java.lang.Thread.sleep(800);            // 즉답은 봇 티가 난다
      replier.reply(reply);
    }
  } catch (e) {
    // 조용히 넘긴다 — 방에 오류 메시지를 뿌리면 그것도 도배가 된다
  }
}
