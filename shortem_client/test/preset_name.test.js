// 한 줄 요청의 프리셋 이름("이 영상으로 연예인상품+후기형으로 만들어줘") → 내 프리셋 id (index.js presetByName · shortem_make preset_name)
import test from 'node:test';
import assert from 'node:assert/strict';
import { presetByName } from '../server/index.js';

const LIST = [
  { id: 'p_1111111111', name: '제품비하인드썰형' },
  { id: 'p_2222222222', name: '샤크탱크+리뷰형' },
  { id: 'p_3333333333', name: '해외핫영상+리뷰형' },
  { id: 'p_4444444444', name: '연예인상품+후기형' },
  { id: 'p_5555555555', name: '연예인꿀맛' },
];

test('고객용 이름 그대로·띄어쓰기·+ 빠짐 모두 같은 프리셋', () => {
  for (const s of ['연예인상품+후기형', '연예인상품 후기형', '연예인상품후기형', ' 연예인상품 + 후기형 ']) assert.equal(presetByName(LIST, s)?.id, 'p_4444444444', s);
  assert.equal(presetByName(LIST, '연예인꿀맛')?.id, 'p_5555555555');
  assert.equal(presetByName(LIST, '샤크탱크')?.id, 'p_2222222222');   // 앞부분만 말해도 하나뿐이면
});

test('여럿에 걸리거나 없으면 고르지 않는다(대신 고르지 않음)', () => {
  assert.equal(presetByName(LIST, '리뷰형'), null);     // 샤크탱크+리뷰형 · 해외핫영상+리뷰형
  assert.equal(presetByName(LIST, '연예인'), null);     // 연예인상품+후기형 · 연예인꿀맛
  assert.equal(presetByName(LIST, '없는프리셋'), null);
  assert.equal(presetByName(LIST, ''), null);
});
