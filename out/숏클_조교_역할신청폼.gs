// 숏클 1기 조교 역할 신청서 — 새 폼을 만든다(한 번만 실행). 문항 수정은 폼 편집 화면에서.
function buildTaRoleForm() {
  var ROLES = [
    '기본방 1차 질문응대',
    '단체방 1차 질문응대',
    '카페 관리 스탭',
    '강의 운영 도움',
    '설치 도우미',
    '오류 접수 정리',
    'FAQ 정리',
    '신입 버디',
    '결과물 첫 검수',
    '성과·후기 수집'
  ];
  var f = FormApp.create('숏클 1기 조교 역할 신청서');
  f.setDescription(
    '숏클 1기 조교 여러분, 함께해 주셔서 감사합니다.\n' +
    '조교 한 분 한 분이 맡은 자리를 책임져 주시면, 회원분들이 더 빨리 첫 영상을 만들고 대표는 개발과 영상 제작에 집중할 수 있습니다.\n\n' +
    '✅ 공통 역할(모든 조교): 단체방에 새 회원이 들어오면 반갑게 맞이 인사\n' +
    '✅ 개별 역할: 아래에서 하고 싶은 역할을 1·2·3순위로 골라 주세요. 순위와 인원을 보고 배정해 드립니다.\n' +
    '✅ 임기: 1기 기간 동안. 끝나면 연장 여부를 직접 선택합니다.\n' +
    '✅ 역할마다 팀장 1명을 둡니다. 팀장은 팀원과 함께 그 역할을 책임지고 대표와 직접 소통합니다.\n\n' +
    '역할 설명은 다음 칸에 있습니다.');
  f.setCollectEmail(false);
  f.setConfirmationMessage('신청해 주셔서 감사합니다. 배정 결과와 역할 설명서를 단체방으로 안내드리겠습니다. 🙌');

  f.addTextItem().setTitle('성함').setRequired(true);
  f.addTextItem().setTitle('카톡 닉네임').setHelpText('단체방에서 쓰시는 닉네임을 적어 주세요.').setRequired(true);
  f.addTextItem().setTitle('연락처(휴대폰)').setHelpText('예: 010-1234-5678').setRequired(true);

  f.addPageBreakItem().setTitle('역할 고르기').setHelpText(
    '① 기본방 1차 질문응대 — 기본방 질문에 먼저 답하고, 모르는 것은 오류 접수 담당에게 넘깁니다.\n' +
    '② 단체방 1차 질문응대 — 단체방 질문에 먼저 답하고, 모르는 것은 오류 접수 담당에게 넘깁니다.\n' +
    '③ 카페 관리 스탭 — 네이버 카페 게시글·등업·공지를 관리합니다.\n' +
    '④ 강의 운영 도움 — 강의 일정 공지, 출석·과제 확인, 강의 자료·녹화본 안내를 돕습니다.\n' +
    '⑤ 설치 도우미 — 설치하다 막힌 회원을 1:1로 도와 끝까지 설치시켜 드립니다(원격 지원 가능하면 좋습니다).\n' +
    '⑥ 오류 접수 정리 — 질문응대가 못 푼 문제를 정해진 양식(캡처·단계·PC 사양·프리셋)으로 정리해 대표에게 올립니다.\n' +
    '⑦ FAQ 정리 — 자주 나오는 질문과 답을 모아 카페 게시판에 올리고 계속 고칩니다.\n' +
    '⑧ 신입 버디 — 새 회원 한 분을 맡아 첫 영상 완성까지 챙깁니다.\n' +
    '⑨ 결과물 첫 검수 — 회원 영상을 체크리스트(자막 겹침·광고 표시·장면 반복)로 먼저 봐 드립니다.\n' +
    '⑩ 성과·후기 수집 — 회원 조회수·수익 인증과 후기를 모으고 인터뷰하실 분을 찾습니다.');
  f.addMultipleChoiceItem().setTitle('1순위 역할').setChoiceValues(ROLES).setRequired(true);
  f.addListItem().setTitle('2순위 역할').setChoiceValues(ROLES).setRequired(true);
  f.addListItem().setTitle('3순위 역할').setChoiceValues(ROLES).setRequired(true);
  f.addMultipleChoiceItem().setTitle('고른 역할의 팀장에 지원하시겠어요?')
    .setChoiceValues(['네, 팀장을 맡고 싶습니다', '팀원으로 하겠습니다']).setRequired(true);

  f.addPageBreakItem().setTitle('활동 가능 시간과 경험');
  f.addCheckboxItem().setTitle('활동 가능한 시간대 (여러 개 선택)')
    .setChoiceValues(['평일 오전(9~12시)', '평일 오후(12~18시)', '평일 저녁(18~22시)', '평일 밤(22시 이후)', '주말 낮', '주말 저녁']).setRequired(true);
  f.addMultipleChoiceItem().setTitle('하루에 조교 활동에 쓸 수 있는 시간')
    .setChoiceValues(['30분 미만', '30분~1시간', '1~2시간', '2시간 이상']).setRequired(true);
  f.addMultipleChoiceItem().setTitle('숏클 설치·사용은 어느 정도 하시나요?')
    .setChoiceValues(['혼자 막힘 없이 설치하고 영상을 만듭니다', '도움을 받아 설치했고 영상을 만듭니다', '아직 설치 중이거나 영상을 못 만들었습니다']).setRequired(true);
  f.addMultipleChoiceItem().setTitle('원격 프로그램(애니데스크·팀뷰어 등)으로 다른 회원 PC를 도와줄 수 있나요?')
    .setChoiceValues(['네, 할 수 있습니다', '배우면 할 수 있습니다', '어렵습니다']).setRequired(true);
  f.addCheckboxItem().setTitle('직접 만들어 본 프리셋 (여러 개 선택)')
    .setChoiceValues(['연예인쇼핑', '해외영상(화장품·식품·감동·반전 등)', '썰쇼핑', '인스타쇼핑', '시니어쇼핑', '여행숙박', '랭킹형', '아직 없음'])
    .showOtherOption(true);

  f.addPageBreakItem().setTitle('나의 다짐');
  f.addParagraphTextItem().setTitle('맡은 역할에서 꼭 해내고 싶은 것 한 가지를 적어 주세요.')
    .setHelpText('예: "제 담당 신입 회원은 첫 주 안에 첫 영상을 꼭 올리게 하겠습니다."').setRequired(true);
  f.addCheckboxItem().setTitle('조교 약속 (모두 체크해 주세요)')
    .setChoiceValues([
      '1기 임기 동안 배정된 역할을 책임지고 맡겠습니다',
      '회원의 비밀번호·API 키·쿠키 같은 개인 정보는 받지도, 묻지도 않겠습니다',
      '모르는 것은 짐작으로 답하지 않고 담당자에게 넘기겠습니다',
      '회원 정보와 단체방 내용을 밖으로 옮기지 않겠습니다'
    ])
    .setValidation(FormApp.createCheckboxValidation().requireSelectExactly(4).build())
    .setRequired(true);
  f.addParagraphTextItem().setTitle('대표에게 하고 싶은 말이나 제안(선택)');

  f.setPublished(true);
  Logger.log('[추가] 응답 링크: ' + f.getPublishedUrl());
  Logger.log('[추가] 편집 링크: ' + f.getEditUrl());
}
