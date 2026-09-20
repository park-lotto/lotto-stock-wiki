// _markScriptProduct 가 실제로 도는지 확인한다 (index.html에서 함수만 떼어 실행).
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(
  path.join(__dirname, '..', 'shopping_shorts', 'static', 'index.html'), 'utf8');

const s = src.indexOf('function _markScriptProduct');
if (s < 0) { console.error('함수를 못 찾음'); process.exit(1); }
// 함수 본문 끝 = 첫 컬럼의 '}' 줄
const rest = src.slice(s);
const end = rest.indexOf('\n}\n');
eval(rest.slice(0, end + 3));

let ok = true;
function check(label, cond, detail) {
  ok = ok && cond;
  console.log((cond ? '  OK  ' : '  실패 ') + label + (detail ? '   ' + detail : ''));
}

// ① 제품명 토큰이 들어간 검색어가 맨 위로 올라온다
let st = {
  product: '미니 재봉틀',
  cnCands: [
    { ko: '옷 수선 꿀템' }, { ko: '바지 밑단 줄이기 셀프' },
    { ko: '미니 재봉틀' }, { ko: '초보자 재봉틀 추천' },
  ],
};
_markScriptProduct(st);
check('제품 검색어가 맨 위', st.cnCands[0].ko === '미니 재봉틀', st.cnCands[0].ko);
check('그 줄에 표시', st.cnCands[0]._scriptHit === true);
check('어간이 겹치는 다른 줄도 표시', st.cnCands.filter(c => c._scriptHit).length === 2,
  JSON.stringify(st.cnCands.map(c => [c.ko, !!c._scriptHit])));
check('안 겹치는 줄은 표시 없음', st.cnCands.find(c => c.ko === '옷 수선 꿀템')._scriptHit === false);

// ② 제품이 없으면 아무것도 안 한다
st = { cnCands: [{ ko: 'A' }, { ko: 'B' }] };
_markScriptProduct(st);
check('제품 없음 → 순서 그대로', st.cnCands[0].ko === 'A');
check('제품 없음 → 표시 없음', st.cnCands.every(c => c._scriptHit === undefined));

// ③ 하나도 안 맞으면 순서를 안 바꾼다
st = { product: '전동 드릴', cnCands: [{ ko: '재봉틀' }, { ko: '바느질' }] };
_markScriptProduct(st);
check('안 맞으면 순서 유지', st.cnCands[0].ko === '재봉틀');
check('안 맞으면 전부 표시 없음', st.cnCands.every(c => c._scriptHit === false));

// ④ 1글자 토큰은 무시한다(아무 데나 걸린다)
st = { product: '틀', cnCands: [{ ko: '재봉틀' }, { ko: '수선' }] };
_markScriptProduct(st);
check('1글자는 무시', st.cnCands.every(c => c._scriptHit === undefined),
  JSON.stringify(st.cnCands));

// ⑤ 후보가 비어도 안 터진다
_markScriptProduct({ product: '재봉틀', cnCands: [] });
_markScriptProduct(null);
check('빈 입력에도 안 터짐', true);

console.log(ok ? '\n전부 통과' : '\n★실패 있음');
process.exit(ok ? 0 : 1);
