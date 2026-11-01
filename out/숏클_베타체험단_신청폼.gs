// 숏클 베타테스트 체험단 신청폼 — 새 폼을 만든다(한 번만 실행). 문항 수정은 폼 편집 화면에서.
function createBetaForm() {
  var f = FormApp.create('숏클 베타테스트 체험단 신청서');
  f.setDescription(
    '11월 1일 서비스 시작 예정인 숏클(클로드형 프로그램)의 베타테스트 체험단 신청서입니다.\n' +
    '🔥 각오가 남다른 분들을 모집합니다.\n' +
    '우선 모집 10명 · 30일 집중 미션(하루 2개 영상 제작)\n\n' +
    '🔓 체험단 혜택: 선발되신 분께는 고급형 과정까지 무료로 열어 드립니다.\n' +
    '🎁 기존 1기 회원 특권: 숏템메이커를 그대로 쓰시거나 숏클 기본형으로 업그레이드하는 것 중 선택하실 수 있습니다. 고급형·프리미엄으로 옮기실 때는 차액만 내고 이동하실 수 있습니다.\n' +
    '★ 조교 활동(단체방에서 초보 회원 돕기)과 인터뷰 영상 참여가 가능하신 분을 우선 선발합니다.\n' +
    '세부 일정은 선발되신 분께 별도로 안내드립니다.');
  f.setCollectEmail(true);
  f.setLimitOneResponsePerUser(false);
  f.setConfirmationMessage('신청해 주셔서 감사합니다. 선발 결과는 개별 연락으로 안내드리겠습니다. 🔥');

  f.addTextItem().setTitle('성함').setRequired(true);
  f.addTextItem().setTitle('연락처(휴대폰)').setHelpText('예: 010-1234-5678').setRequired(true);
  f.addTextItem().setTitle('숏템메이커 가입 아이디(이메일)').setHelpText('1기 회원분은 가입하신 아이디를 적어 주세요.').setRequired(true);
  f.addTextItem().setTitle('운영 중인 유튜브 채널 주소(있으면)');
  f.addMultipleChoiceItem().setTitle('1기 회원이시면 앞으로 어떤 프로그램을 쓰시겠어요?')
    .setChoiceValues(['숏템메이커 그대로 사용', '숏클 기본형으로 업그레이드', '1기 회원이 아닙니다']).setRequired(true);

  f.addMultipleChoiceItem().setTitle('Claude Max 구독 중이신가요? (필수 준비물)')
    .setChoiceValues(['구독 중입니다', '선발되면 구독하겠습니다', '구독 계획이 없습니다']).setRequired(true);
  f.addMultipleChoiceItem().setTitle('30일 동안 하루 2개씩 영상 제작이 가능하신가요?')
    .setChoiceValues(['네, 매일 가능합니다', '대부분 가능합니다', '어렵습니다']).setRequired(true);

  f.addSectionHeaderItem().setTitle('조교 활동 · 인터뷰 (우선 선발 기준)')
    .setHelpText('체험단은 숏클 1기의 조교 역할을 합니다. 인터뷰 가능하신 분을 우선 모십니다.');
  f.addMultipleChoiceItem().setTitle('단체방에서 새 회원 인사·초보 회원 질문 답변 등 조교 활동이 가능하신가요?')
    .setChoiceValues(['네, 적극적으로 하겠습니다', '가능한 범위에서 하겠습니다', '어렵습니다']).setRequired(true);
  f.addMultipleChoiceItem().setTitle('30일 활동 후 인터뷰 영상 촬영에 참여 가능하신가요?')
    .setChoiceValues(['네, 얼굴 공개 가능합니다', '네, 얼굴 없이(음성·화면만) 가능합니다', '어렵습니다']).setRequired(true);
  f.addMultipleChoiceItem().setTitle('활동 과정·성과 인증 자료를 제공하고, 이를 숏템메이커 홍보에 활용하는 것에 동의하십니까?')
    .setChoiceValues(['동의합니다', '동의하지 않습니다']).setRequired(true);

  f.addCheckboxItem().setTitle('가장 해 보고 싶은 숏클 프리셋 (여러 개 선택)')
    .setChoiceValues(['연예인쇼핑', '해외영상(화장품·식품·감동·반전 등)', '썰쇼핑', '인스타쇼핑', '시니어쇼핑', '여행숙박', '랭킹형'])
    .showOtherOption(true);
  f.addParagraphTextItem().setTitle('30일을 대하는 나의 각오를 적어 주세요.').setHelpText('각오가 남다른 분을 모십니다. 왜 이번에 꼭 성과를 내야 하는지, 어떻게 끝까지 해낼지 솔직하게 남겨 주세요.').setRequired(true);
  f.addParagraphTextItem().setTitle('지원 동기와 30일 뒤 이루고 싶은 목표를 적어 주세요.').setRequired(true);

  Logger.log('[추가] 응답 링크: ' + f.getPublishedUrl());
  Logger.log('[추가] 편집 링크: ' + f.getEditUrl());
}
