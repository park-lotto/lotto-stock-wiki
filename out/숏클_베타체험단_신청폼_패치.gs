// 이미 만든 숏클 체험단 신청폼(링크 유지)에 최신 문구를 넣는다. 여러 번 돌려도 같은 결과.
function patchBetaForm() {
  var f = FormApp.openById('17RpffES5LX3gBdlB2LNOX_kZw--GW4mODgAcZl47oEU');
  f.setDescription(
    '11월 1일 서비스 시작 예정인 숏클(클로드형 프로그램)의 베타테스트 체험단 신청서입니다.\n' +
    '🔥 각오가 남다른 분들을 모집합니다.\n' +
    '우선 모집 10명 · 30일 집중 미션(하루 2개 영상 제작)\n\n' +
    '🔓 체험단 혜택: 선발되신 분께는 고급형 과정까지 무료로 열어 드립니다.\n' +
    '🎁 기존 1기 회원 특권: 숏템메이커를 그대로 쓰시거나 숏클 기본형으로 업그레이드하는 것 중 선택하실 수 있습니다. 고급형·프리미엄으로 옮기실 때는 차액만 내고 이동하실 수 있습니다.\n' +
    '★ 조교 활동(단체방에서 초보 회원 돕기)과 인터뷰 영상 참여가 가능하신 분을 우선 선발합니다.\n' +
    '세부 일정은 선발되신 분께 별도로 안내드립니다.');

  var items = f.getItems();
  function find(prefix) {
    for (var i = 0; i < items.length; i++) if (items[i].getTitle().indexOf(prefix) === 0) return items[i];
    return null;
  }
  if (!find('1기 회원이시면')) {
    var yt = find('운영 중인 유튜브');
    var q = f.addMultipleChoiceItem().setTitle('1기 회원이시면 앞으로 어떤 프로그램을 쓰시겠어요?')
      .setChoiceValues(['숏템메이커 그대로 사용', '숏클 기본형으로 업그레이드', '1기 회원이 아닙니다']).setRequired(true);
    f.moveItem(q.getIndex(), yt.getIndex() + 1);
  }
  items = f.getItems();
  var motive = find('지원 동기');
  motive.setTitle('지원 동기와 30일 뒤 이루고 싶은 목표를 적어 주세요.');
  if (!find('30일을 대하는 나의 각오')) {
    var g = f.addParagraphTextItem().setTitle('30일을 대하는 나의 각오를 적어 주세요.')
      .setHelpText('각오가 남다른 분을 모십니다. 왜 이번에 꼭 성과를 내야 하는지, 어떻게 끝까지 해낼지 솔직하게 남겨 주세요.').setRequired(true);
    f.moveItem(g.getIndex(), motive.getIndex());
  }
  Logger.log('[갱신] 응답 링크: ' + f.getPublishedUrl());
}
