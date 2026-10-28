/**
 * 숏템메이커 신청폼 — '콘텐츠 운영 안내' 필수 동의 문항 추가 (2026-10-14, 관제 199)
 *
 * ★ 기존 문항·응답은 건드리지 않는다. 맨 끝에 필수 체크 문항 1개만 붙인다.
 *   이미 붙어 있으면(같은 제목) 설명만 최신 문구로 바꾸고 새로 만들지 않는다 → 여러 번 실행해도 안전.
 * ★ 문구 원본 = shopping_shorts/app.py `_CONTENT_NOTICE_ITEMS` (가입·대기실·결제·약관과 같은 문장)
 *
 * 사용법: 기존 Apps Script 프로젝트(폼 아이콘)에 붙여넣고 addContentNotice() 실행
 *        → 실행 로그에 [추가] 또는 [갱신] 한 줄이 찍히면 정상
 */
var FORM_ID = '1j7DEOvChLxsUDl8VHnj9o18kPw1c5hDvZbZW4sWMd5Q';
var TITLE   = '⚠️ 꼭 읽어 주세요 · 콘텐츠 운영 안내 (필수)';
var ITEMS = [
  "숏템메이커는 영상 제작을 돕는 도구예요. 어떤 소재를 골라 어떻게 편집하고 어느 채널에 올릴지는 회원님이 정하시며, 그 결과에 대한 책임도 회원님께 있어요.",
  "해외 영상 등 다른 사람이 만든 영상을 활용할 때는 원작자의 권리와 각 플랫폼(유튜브·인스타그램·틱톡 등)의 정책을 먼저 확인해 주세요. 같은 소재를 거의 그대로 쓰거나 비슷한 영상을 반복해 올리면 '재사용·중복 콘텐츠'나 저작권 신고 대상이 되어 노출 감소, 수익 제한, 채널 정지·삭제로 이어질 수 있어요.",
  "플랫폼의 조치나 권리자의 신고·청구는 회사가 대신 해결하거나 되돌려 드릴 수 없고, 이로 인한 손해는 회사가 책임지지 않으며 이용권 환불 사유에도 해당하지 않아요.",
  "오래 가는 채널을 위해 직접 촬영·구매했거나 사용 허락을 받은 소재를 우선 쓰고, 자신만의 대본·편집을 충분히 더해 주세요. 비슷한 영상을 한 채널에 몰아서 올리는 것도 피해 주세요."
];
var AGREE = "위 콘텐츠 운영 안내를 읽었고, 채널 운영과 업로드 결과의 책임이 저에게 있음을 확인합니다.";

function addContentNotice() {
  var form = FormApp.openById(FORM_ID);
  var help = ITEMS.map(function (t) { return '• ' + t; }).join(String.fromCharCode(10, 10));
  var found = form.getItems().filter(function (it) { return it.getTitle() === TITLE; });
  if (found.length) {
    found[0].setHelpText(help);
    Logger.log('[갱신] 기존 문항 설명을 최신 문구로 바꿈');
    return;
  }
  var cb = form.addCheckboxItem();
  cb.setTitle(TITLE).setHelpText(help).setRequired(true);
  cb.setChoices([cb.createChoice(AGREE)]);
  Logger.log('[추가] 필수 동의 문항을 맨 끝에 붙임');
}
