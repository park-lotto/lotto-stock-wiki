/**
 * 숏템메이커 1기 모집 신청폼 자동 생성 + 제출 시 결제안내 자동메일
 * 사용법: script.google.com 새 프로젝트에 통째로 붙여넣고 createForm() 실행
 */

var CARD_URL   = 'https://stmaker.kr/surl/O/3068';
var CARD_OPEN  = '8월 31일(일) 오전 11시';
var PRICE      = '77만원';
var BANK       = '카카오뱅크 3333-13-9497518 (예금주: 최지희)';
var FORM_TITLE = '숏템메이커 1기 모집 신청서';

function createForm() {
  var form = FormApp.create(FORM_TITLE);
  form.setTitle(FORM_TITLE);
  form.setDescription(
    '숏템메이커 1기에 신청해 주셔서 감사합니다.\n\n' +
    '------------------------------\n' +
    '참가비 ' + PRICE + '\n' +
    '모집 인원: 정원 마감 시 종료 (선착순)\n' +
    '------------------------------\n\n' +
    '[신청 → 결제 순서]\n' +
    '1) 오늘부터 이 신청서를 받습니다.\n' +
    '2) 카드결제는 ' + CARD_OPEN + '부터 열립니다. 그 전에는 결제 페이지가 열리지 않습니다.\n' +
    '3) 계좌이체는 지금 바로 가능합니다.\n\n' +
    '[결제 방법]\n' +
    '· 카드결제 → ' + CARD_URL + '  (' + CARD_OPEN + ' 오픈)\n' +
    '· 계좌이체 → ' + BANK + '\n' +
    '  ※ 입금자명은 신청자 성함과 같게 넣어주세요.\n\n' +
    '작성해 주신 이메일로 결제 링크를 다시 보내드립니다. 메일함에서 "숏템메이커 결제"로 검색하시면 언제든 찾으실 수 있습니다.'
  );
  form.setCollectEmail(false);
  form.setProgressBar(true);
  form.setAllowResponseEdits(true);

  // ── 1. 기본 정보 ──────────────────────────────
  form.addSectionHeaderItem().setTitle('1. 기본 정보');

  form.addTextItem().setTitle('성함').setRequired(true);

  form.addTextItem()
      .setTitle('휴대폰 번호')
      .setHelpText('예) 010-1234-5678 — 개별 안내가 이 번호로 갑니다')
      .setRequired(true);

  var email = form.addTextItem()
      .setTitle('이메일')
      .setHelpText('결제 링크와 1기 안내가 이 주소로 발송됩니다. 정확히 적어주세요.')
      .setRequired(true);
  email.setValidation(
    FormApp.createTextValidation().requireTextIsEmail()
      .setHelpText('이메일 형식으로 입력해 주세요').build()
  );

  form.addTextItem()
      .setTitle('카카오톡 ID 또는 오픈채팅 닉네임')
      .setHelpText('선택 — 단체방 초대에 씁니다')
      .setRequired(false);

  // ── 2. 영상 경험·장비 ─────────────────────────
  form.addPageBreakItem().setTitle('2. 영상 제작 경험과 장비');

  form.addMultipleChoiceItem()
      .setTitle('영상(숏폼) 제작 경험이 어느 정도이신가요?')
      .setChoiceValues([
        '완전 처음입니다',
        '몇 번 만들어봤지만 꾸준히는 못 했습니다',
        '직접 꾸준히 만들고 있습니다',
        '외주를 맡겨서 만들고 있습니다'
      ]).setRequired(true);

  form.addCheckboxItem()
      .setTitle('지금 쓰고 계신 도구가 있다면 골라주세요')
      .setChoiceValues([
        '없음',
        '캡컷(CapCut)',
        '프리미어 / 파이널컷',
        '블로(VLLO) · 키네마스터 등 모바일 앱',
        '브루(Vrew)',
        '다른 AI 영상 제작 서비스'
      ])
      .showOtherOption(true)
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('주로 어떤 기기로 작업하시나요?')
      .setChoiceValues([
        'PC / 노트북 위주',
        '스마트폰 위주',
        '둘 다 씁니다'
      ]).setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('영상 작업에 쓸 수 있는 시간은 하루 어느 정도인가요?')
      .setChoiceValues([
        '30분 이하',
        '30분 ~ 1시간',
        '1 ~ 2시간',
        '2시간 이상'
      ]).setRequired(true);

  // ── 3. 기대치·목표 ────────────────────────────
  form.addPageBreakItem().setTitle('3. 기대하시는 것');

  form.addParagraphTextItem()
      .setTitle('숏템메이커로 무엇을 해결하고 싶으신가요?')
      .setHelpText('지금 가장 답답한 점을 편하게 적어주세요. 1기 커리큘럼에 반영합니다.')
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('한 달에 영상을 몇 편쯤 만들 계획이신가요?')
      .setChoiceValues([
        '1 ~ 5편',
        '6 ~ 15편',
        '16 ~ 30편',
        '30편 이상',
        '아직 모르겠습니다'
      ]).setRequired(true);

  form.addParagraphTextItem()
      .setTitle('만들고 싶은 영상의 주제나 상품이 있다면 적어주세요')
      .setHelpText('선택 — 예) 주방용품 리뷰, 다이소 신상, 반려동물 용품 등')
      .setRequired(false);

  form.addParagraphTextItem()
      .setTitle('1기를 마쳤을 때 "이것만 되면 성공이다" 싶은 게 있다면?')
      .setHelpText('선택')
      .setRequired(false);

  // ── 4. 유입경로·피드백 ────────────────────────
  form.addPageBreakItem().setTitle('4. 마지막 몇 가지');

  form.addMultipleChoiceItem()
      .setTitle('숏템메이커를 어디서 알게 되셨나요?')
      .setChoiceValues([
        '유튜브',
        '인스타그램 / 스레드',
        '카카오톡 오픈채팅방',
        '블로그 / 카페',
        '지인 소개'
      ])
      .showOtherOption(true)
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('1기 진행 중 피드백(설문·짧은 인터뷰)에 참여해 주실 수 있나요?')
      .setHelpText('1기는 함께 만들어가는 기수입니다. 부담 갖지 않으셔도 됩니다.')
      .setChoiceValues([
        '네, 참여하겠습니다',
        '상황 봐서 가능합니다',
        '어렵습니다'
      ]).setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('결과가 좋으면 후기(사례) 공개에 협조해 주실 수 있나요?')
      .setChoiceValues([
        '네, 가능합니다',
        '익명이면 가능합니다',
        '어렵습니다'
      ]).setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('1기 전용 카카오톡 오픈채팅방에 초대해 드릴까요?')
      .setChoiceValues(['네, 초대해 주세요', '아니요'])
      .setRequired(true);

  // ── 5. 결제 ───────────────────────────────────
  form.addPageBreakItem()
      .setTitle('5. 결제')
      .setHelpText(
        '참가비 ' + PRICE + '\n\n' +
        '· 카드결제 → ' + CARD_URL + '\n' +
        '  ※ ' + CARD_OPEN + '부터 열립니다. 그 전에는 접속되지 않습니다.\n' +
        '· 계좌이체 → ' + BANK + '\n' +
        '  ※ 입금자명은 신청자 성함과 같게 넣어주세요.'
      );

  form.addMultipleChoiceItem()
      .setTitle('결제 방법을 선택해 주세요')
      .setChoiceValues([
        '카드결제 (' + CARD_OPEN + ' 오픈 — 그때 결제하겠습니다)',
        '계좌이체 (이미 입금했습니다)',
        '계좌이체 (곧 입금하겠습니다)'
      ]).setRequired(true);

  form.addSectionHeaderItem()
      .setTitle('▼ 계좌이체로 이미 입금하신 분만 아래 3칸을 채워주세요')
      .setHelpText('카드결제를 선택하셨다면 비워두고 제출하시면 됩니다.');

  form.addTextItem()
      .setTitle('입금자명')
      .setHelpText('통장에 찍히는 이름 그대로 적어주세요')
      .setRequired(false);

  form.addCheckboxItem()
      .setTitle('입금 완료 확인')
      .setChoiceValues(['입금을 완료했습니다'])
      .setRequired(false);

  form.addDateItem()
      .setTitle('입금일')
      .setRequired(false);

  // ── 6. 동의 ───────────────────────────────────
  form.addPageBreakItem().setTitle('6. 개인정보 수집 동의');

  form.addCheckboxItem()
      .setTitle('개인정보 수집·이용에 동의합니다 (필수)')
      .setHelpText(
        '수집 항목: 성함, 연락처, 이메일, 카카오톡 ID, 설문 응답, 입금 정보\n' +
        '이용 목적: 1기 참가자 확인, 결제 대사, 강의·서비스 안내\n' +
        '보유 기간: 1기 종료 후 1년 (요청 시 즉시 파기)'
      )
      .setChoiceValues(['동의합니다'])
      .setRequired(true);

  // ── 제출 후 확인 메시지 ───────────────────────
  form.setConfirmationMessage(
    '신청이 접수되었습니다. 감사합니다!\n\n' +
    '------------------------------\n' +
    '[카드결제 링크]\n' + CARD_URL + '\n' +
    '  → ' + CARD_OPEN + '부터 열립니다\n\n' +
    '[계좌이체]\n' + BANK + '\n' +
    '------------------------------\n\n' +
    '적어주신 이메일로 이 링크를 다시 보내드렸습니다.\n' +
    '메일함에서 "숏템메이커 결제"로 검색하시면 언제든 찾으실 수 있습니다.\n\n' +
    '이 화면은 캡처해 두시면 편합니다.'
  );

  // 응답 스프레드시트 연결
  var ss = SpreadsheetApp.create(FORM_TITLE + ' (응답)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  // 제출 시 자동메일 트리거
  ScriptApp.newTrigger('onFormSubmitMail')
           .forForm(form)
           .onFormSubmit()
           .create();

  Logger.log('=== 폼 생성 완료 ===');
  Logger.log('신청자용 링크 : ' + form.getPublishedUrl());
  Logger.log('편집용 링크   : ' + form.getEditUrl());
  Logger.log('응답 시트     : ' + ss.getUrl());
  return form.getPublishedUrl();
}

/** 제출 즉시 결제 안내 메일 발송 */
function onFormSubmitMail(e) {
  try {
    var items = e.response.getItemResponses();
    var name = '', to = '';
    for (var i = 0; i < items.length; i++) {
      var t = items[i].getItem().getTitle();
      if (t === '성함')   name = items[i].getResponse();
      if (t === '이메일') to   = items[i].getResponse();
    }
    if (!to) return;

    var subject = '[숏템메이커 결제] 1기 신청 접수 완료 — 결제 링크 안내';
    var body =
      (name ? name + '님, ' : '') + '숏템메이커 1기 신청이 접수되었습니다.\n\n' +
      '------------------------------\n' +
      '참가비 ' + PRICE + '\n' +
      '------------------------------\n\n' +
      '[카드결제]\n' + CARD_URL + '\n' +
      '   → ' + CARD_OPEN + '부터 열립니다.\n' +
      '     그 전에 눌러도 결제 페이지가 뜨지 않으니 시간 맞춰 접속해 주세요.\n\n' +
      '[계좌이체]\n' + BANK + '\n' +
      '   → 입금자명은 신청자 성함과 같게 넣어주세요.\n\n' +
      '------------------------------\n' +
      '이 메일을 지우지 마세요. 결제 링크를 다시 찾으실 때\n' +
      '메일함에서 "숏템메이커 결제"로 검색하시면 바로 나옵니다.\n' +
      '------------------------------\n\n' +
      '궁금한 점은 이 메일에 회신해 주세요.\n\n숏템메이커 드림';

    MailApp.sendEmail(to, subject, body);
  } catch (err) {
    Logger.log('메일 발송 실패: ' + err);
  }
}
