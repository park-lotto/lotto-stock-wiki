// 2단계 스냅샷 주인 검사 회귀 테스트 (2026-08-18)
//   사장님 제보: "2단계에서 아예 딴게 나온다" — 1단계는 다이소 자석 네일펜 5편인데
//   2단계 재료 카드가 '홈데코랩 / 장모님 댁 30년 구축'이었다.
//   실측(서버 work 3b8e5099a22e): handoff·_load_work_sources·aipick은 전부 정상
//   (pick_id=DcIrfnOzHre 네일). 틀린 건 저장된 state.s2뿐 — seed는 옛 작업의
//   홈데코랩(DbmCnyTTobw), drafts는 또 다른 작업의 카드지갑 대본이었다.
//   뿌리: S2가 순수 메모리라 작업을 갈아타도 살아남는데, 스냅샷에 주인 표시가 없어
//   '따로 만들기'(WORK_ID=null) 직후 저장이 옛 S2를 새 작업에 담았다.
//   실행: node shopping_shorts/tests/test_s2_work_owner.js
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../static/produce.html'), 'utf8');

function fn(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i < 0) { console.error(name + ' not found'); process.exit(1); }
  let d = 0;
  for (let k = src.indexOf('{', i); k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(i, k + 1); }
  }
  process.exit(1);
}

let S2 = { seed: null, seeds: [], drafts: [], curDraft: 0, picked: [], materials: null };
let WORK_ID = null;
eval(fn('_s2Reset'));
eval(fn('_s2Snapshot'));
eval(fn('_s2Hydrate'));

let p = 0, f = 0;
const t = (n, c) => { c ? (p++, console.log('  PASS', n)) : (f++, console.log('  FAIL', n)); };

console.log('[1] 스냅샷은 주인(work_id)을 새긴다');
WORK_ID = 'W-new';
S2 = { seed: { shortcode: 'SEED_A' }, seeds: [], drafts: [{ script: 'a' }], curDraft: 0, picked: [], materials: null };
const snap = _s2Snapshot();
t('work_id가 담긴다', snap && snap.work_id === 'W-new');

console.log('[2] 남의 작업 스냅샷은 복원하지 않는다 (이번 사고)');
S2 = { seed: { shortcode: 'LIVE' }, seeds: [], drafts: [{ script: 'live' }], curDraft: 0, picked: [], materials: null };
_s2Hydrate({ work_id: 'W-other', s2: { work_id: 'W-old', drafts: [{ script: '옛 카드지갑 대본' }], seed: { shortcode: 'DbmCnyTTobw', title: '홈데코랩' } } });
t('옛 대본이 안 딸려온다', S2.drafts.length === 0);
t('옛 씨앗(홈데코랩)이 안 딸려온다', S2.seed === null);

console.log('[3] 같은 작업이면 그대로 되살린다');
S2 = { seed: null, seeds: [], drafts: [], curDraft: 0, picked: [], materials: null };
_s2Hydrate({ work_id: 'W-1', s2: { work_id: 'W-1', drafts: [{ script: '내 대본' }], seed: { shortcode: 'MINE' } } });
t('내 작업 대본은 복원', S2.drafts.length === 1 && S2.drafts[0].script === '내 대본');
t('내 작업 씨앗도 복원', S2.seed && S2.seed.shortcode === 'MINE');

console.log('[4] 회귀 — work_id 없는 옛 스냅샷은 종전대로 복원(주인을 알 길이 없다)');
S2 = { seed: null, seeds: [], drafts: [], curDraft: 0, picked: [], materials: null };
_s2Hydrate({ work_id: 'W-2', s2: { drafts: [{ script: '옛 형식' }], seed: { shortcode: 'OLD' } } });
t('옛 형식은 그대로 산다', S2.drafts.length === 1 && S2.seed && S2.seed.shortcode === 'OLD');

console.log('\n결과: PASS ' + p + ' / FAIL ' + f);
process.exit(f ? 1 : 0);
