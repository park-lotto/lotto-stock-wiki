/**
 * 숏템메이커 신청폼 — 1기·77만원 흔적을 전부 2기·88만원으로 (2026-10-13)
 *
 * 10-01 의 patchCohort2() 는 5곳(제목·설명·결제 안내·선택지·확인 메시지)만 바꾼다.
 * 공개 신청서를 실측하니 문항 제목·도움말에도 '1기'가 남아 있어(이메일 안내·커리큘럼·피드백·오픈채팅·개인정보 동의 등 14곳)
 * 이 스크립트는 **폼 안의 모든 글자**를 훑어 바꾼다.
 *
 * ★ 문항을 지우거나 새로 만들지 않는다 — 기존 응답·문항·폼 링크 그대로, 글자만 바꾼다.
 *
 * 사용법: 폼에 연결된 Apps Script 프로젝트에 붙여넣고 patchAllCohortText() 실행
 *        → 로그 마지막 줄이 "남은 옛 문구 0곳"이면 정상(남으면 오류로 멈추고 어디인지 알려준다)
 */

var FORM_ID  = '1j7DEOvChLxsUDl8VHnj9o18kPw1c5hDvZbZW4sWMd5Q';
var CARD_URL = 'https://shoppingshorts.duckdns.org/pay/toss';

// 순서대로 적용한다(위가 먼저). [찾을 것, 바꿀 것]
var RULES = [
  [/https?:\/\/smartstore\.naver\.com\/makerslab7\/products\/\d+/g, CARD_URL],
  [/1기 전용 오픈채팅방은 9월 중에 개설됩니다\. 개설되면 초대해 드립니다\./g, '2기 전용 오픈채팅방은 개설되면 초대해 드립니다.'],
  [/9월 중 개설되며, 개설되면 초대해 드립니다\./g, '개설되면 초대해 드립니다.'],
  [/숏템메이커 1기 모집 신청서/g, '숏템메이커 2기 신청서'],
  [/77\s*만\s*원/g, '88만원'],
  [/770,000/g, '880,000'],
  [/1기/g, '2기']
];
var LEFTOVER = /1기|77\s*만|770,000|smartstore\.naver|9월/;

function fix_(s) {
  if (!s) return s;
  for (var i = 0; i < RULES.length; i++) s = s.replace(RULES[i][0], RULES[i][1]);
  return s;
}

function patchAllCohortText() {
  var form = FormApp.openById(FORM_ID);
  var changed = 0;
  function apply(label, oldV, setter) {
    var newV = fix_(oldV);
    if (newV !== oldV) { setter(newV); changed++; Logger.log('[변경] ' + label); }
  }

  apply('폼 제목', form.getTitle(), function (v) { form.setTitle(v); });
  apply('폼 상단 설명', form.getDescription(), function (v) { form.setDescription(v); });
  apply('제출 후 확인 메시지', form.getConfirmationMessage(), function (v) { form.setConfirmationMessage(v); });

  form.getItems().forEach(function (item) {
    apply('문항 제목: ' + item.getTitle(), item.getTitle(), function (v) { item.setTitle(v); });
    apply('문항 도움말: ' + item.getTitle(), item.getHelpText(), function (v) { item.setHelpText(v); });
  });

  // 드라이브에 보이는 파일 이름(폼 제목과 따로 논다)
  try {
    var file = DriveApp.getFileById(FORM_ID);
    apply('파일 이름', file.getName(), function (v) { file.setName(v); });
  } catch (e) { Logger.log('[건너뜀] 파일 이름: ' + e); }

  // ── 검사: 옛 문구가 하나라도 남았으면 멈춘다 ──
  var left = [];
  function check(label, s) { if (s && LEFTOVER.test(s)) left.push(label + ' → ' + s.slice(0, 60)); }
  check('폼 제목', form.getTitle());
  check('폼 상단 설명', form.getDescription());
  check('확인 메시지', form.getConfirmationMessage());
  form.getItems().forEach(function (item) {
    check('문항 제목', item.getTitle());
    check('문항 도움말(' + item.getTitle() + ')', item.getHelpText());
    // 선택지 글자는 자동으로 안 바꾼다(응답 집계가 갈린다) — 남아 있으면 알려만 준다
    var t = item.getType(), choices = [];
    if (t === FormApp.ItemType.MULTIPLE_CHOICE) choices = item.asMultipleChoiceItem().getChoices();
    if (t === FormApp.ItemType.CHECKBOX) choices = item.asCheckboxItem().getChoices();
    if (t === FormApp.ItemType.LIST) choices = item.asListItem().getChoices();
    choices.forEach(function (c) { check('선택지(' + item.getTitle() + ')', c.getValue()); });
  });

  Logger.log('=== 바꾼 곳 ' + changed + '곳 / 남은 옛 문구 ' + left.length + '곳 ===');
  Logger.log('신청자용 링크 : ' + form.getPublishedUrl());
  if (left.length) throw new Error('옛 문구가 남았습니다:\n' + left.join('\n'));
  return changed;
}
