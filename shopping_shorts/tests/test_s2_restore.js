// 2단계 '옛 작업 구제' 회귀 테스트 (2026-08-18)
//   track/씨앗오염과 origin/main(옛 작업 구제)이 _s2Hydrate의 같은 else 블록에서
//   충돌했다. 손으로 합쳤으므로 **양쪽 기능이 다 사는지** 실행해서 확인한다.
//     · 상대 기능: s2 스냅샷이 없는 옛 작업도 확정 대본(w.script)을 1안으로 되살린다
//     · 내 기능:   그때도 옛 씨앗(seed)은 되살리지 않는다(다이소 사고 방지)
//   실행: node shopping_shorts/tests/test_s2_restore.js   (PASS 7 / FAIL 0)
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../static/produce.html'), 'utf8');

// _s2Hydrate 본문만 뽑아 실제로 실행한다(문자열 검사가 아니라 진짜 동작을 본다).
const i = src.indexOf('function _s2Hydrate(w){');
if (i < 0) { console.error('_s2Hydrate not found'); process.exit(1); }
let d = 0, body = '';
for (let k = src.indexOf('{', i); k < src.length; k++) {
  if (src[k] === '{') d++;
  else if (src[k] === '}') { d--; if (d === 0) { body = src.slice(i, k + 1); break; } }
}
let S2 = { seed: null, seeds: [], drafts: [], curDraft: 0, picked: [], materials: null };
eval(body);

let p = 0, f = 0;
const t = (n, c) => { c ? (p++, console.log('  PASS', n)) : (f++, console.log('  FAIL', n)); };

console.log('[상대 작업] 옛 작업 구제 — s2 없고 확정 대본만 있는 경우');
S2 = { seed: { shortcode: 'OLD_SEED' }, seeds: [], drafts: [], curDraft: 0, picked: [], materials: null };
_s2Hydrate({ script: '확정했던 대본입니다.\n둘째 줄.' });
t('확정 대본이 1안으로 되살아난다', S2.drafts.length === 1 && S2.drafts[0].restored === true);
t('  대본 내용 보존', S2.drafts[0].script.startsWith('확정했던 대본'));
t('  hook은 첫 줄', S2.drafts[0].hook === '확정했던 대본입니다.');
t('★그래도 옛 씨앗은 안 살아난다(다이소 방지)', S2.seed === null);

console.log('\n[상대 작업] 확정 대본도 없는 완전 새 작업');
S2 = { seed: { shortcode: 'OLD' }, seeds: [], drafts: [], curDraft: 0, picked: [], materials: null };
_s2Hydrate({});
t('drafts 비어있다', S2.drafts.length === 0);
t('씨앗도 비어있다', S2.seed === null);

console.log('\n[상대 작업] script가 공백만인 경우');
S2 = { seed: null, seeds: [], drafts: [], curDraft: 0, picked: [], materials: null };
_s2Hydrate({ script: '   ' });
t('빈 대본은 안 만든다', S2.drafts.length === 0);

console.log('\n결과: PASS ' + p + ' / FAIL ' + f);
process.exit(f ? 1 : 0);
