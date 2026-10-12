/**
 * 숏템메이커 1기 신청폼 — 결제 안내 문구만 갈아끼운다
 *
 * ★ 문항을 지우지 않는다. 기존 응답·문항·폼 링크 전부 그대로 두고
 *   결제 관련 문구 4곳만 바꾼다. (갱신본 rebuildForm()은 문항을 전부
 *   삭제하고 다시 만들기 때문에 이미 응답이 쌓인 폼에는 쓰면 안 된다)
 *
 * 사용법: 같은 Apps Script 프로젝트에 붙여넣고 patchPayment() 실행
 *        → 실행 로그에 [변경] 줄이 4개 찍히면 정상
 *
 * 2026-09-15 변경 내용
 *   · 계좌이체  카카오뱅크 3333-13-9497518 (최지희)
 *            → 국민은행 649701-01-357828 (메이커스랩)
 *   · 카드결제  "8월 31일(일) 오전 11시 오픈" 안내 전부 삭제 (이미 오픈)
 */

var FORM_ID  = '1j7DEOvChLxsUDl8VHnj9o18kPw1c5hDvZbZW4sWMd5Q';
var CARD_URL = 'https://smartstore.naver.com/makerslab7/products/13765673887';
var PRICE    = '77만원';
var BANK     = '국민은행 649701-01-357828 (예금주: 메이커스랩)';

function patchPayment() {
  var form = FormApp.openById(FORM_ID);
  var changed = 0;

  // ── ① 폼 상단 설명 ────────────────────────────
  form.setDescription(
    '숏템메이커 1기에 신청해 주셔서 감사합니다.\n\n' +
    '------------------------------\n' +
    '참가비 ' + PRICE + '\n' +
    '모집 인원: 정원 마감 시 종료 (선착순)\n' +
    '------------------------------\n\n' +
    '[신청 → 결제 순서]\n' +
    '1) 이 신청서를 작성해 주세요.\n' +
    '2) 카드결제 또는 계좌이체로 참가비를 결제해 주세요.\n\n' +
    '[결제 방법]\n' +
    '· 카드결제 → ' + CARD_URL + '\n' +
    '· 계좌이체 → ' + BANK + '\n' +
    '  ※ 입금자명은 신청자 성함과 같게 넣어주세요.\n\n' +
    '작성해 주신 이메일로 결제 링크를 다시 보내드립니다. ' +
    '메일함에서 "숏템메이커 결제"로 검색하시면 언제든 찾으실 수 있습니다.'
  );
  Logger.log('[변경] ① 폼 상단 설명');
  changed++;

  // ── ②③ 5. 결제 페이지 안내 + 결제방법 선택지 ──
  var items = form.getItems();
  for (var i = 0; i < items.length; i++) {
    var item  = items[i];
    var title = item.getTitle();
    var type  = item.getType();

    // ② 5. 결제 페이지의 도움말
    if (type === FormApp.ItemType.PAGE_BREAK && title === '5. 결제') {
      item.asPageBreakItem().setHelpText(
        '참가비 ' + PRICE + '\n\n' +
        '· 카드결제 → ' + CARD_URL + '\n' +
        '· 계좌이체 → ' + BANK + '\n' +
        '  ※ 입금자명은 신청자 성함과 같게 넣어주세요.'
      );
      Logger.log('[변경] ② 5. 결제 페이지 안내');
      changed++;
    }

    // ③ 결제 방법 선택지에서 날짜 문구 제거
    if (type === FormApp.ItemType.MULTIPLE_CHOICE &&
        title === '결제 방법을 선택해 주세요') {
      item.asMultipleChoiceItem().setChoiceValues([
        '카드결제',
        '계좌이체 (이미 입금했습니다)',
        '계좌이체 (곧 입금하겠습니다)'
      ]);
      Logger.log('[변경] ③ 결제 방법 선택지');
      changed++;
    }
  }

  // ── ④ 제출 후 확인 메시지 ─────────────────────
  form.setConfirmationMessage(
    '신청이 접수되었습니다. 감사합니다!\n\n' +
    '------------------------------\n' +
    '[카드결제 링크]\n' + CARD_URL + '\n\n' +
    '[계좌이체]\n' + BANK + '\n' +
    '  ※ 입금자명은 신청자 성함과 같게\n' +
    '------------------------------\n\n' +
    '적어주신 이메일로 이 링크를 다시 보내드렸습니다.\n' +
    '메일함에서 "숏템메이커 결제"로 검색하시면 언제든 찾으실 수 있습니다.\n\n' +
    '1기 전용 카카오톡 오픈채팅방은 9월 중 개설되며, 개설되면 초대해 드립니다.\n\n' +
    '이 화면은 캡처해 두시면 편합니다.'
  );
  Logger.log('[변경] ④ 제출 후 확인 메시지');
  changed++;

  Logger.log('=== 결제 문구 패치 완료: ' + changed + '곳 (4곳이어야 정상) ===');
  Logger.log('신청자용 링크 : ' + form.getPublishedUrl());

  if (changed !== 4) {
    throw new Error('4곳이 바뀌어야 하는데 ' + changed +
                    '곳만 바뀌었습니다. 문항 제목이 달라졌는지 확인하세요.');
  }
  return form.getPublishedUrl();
}
