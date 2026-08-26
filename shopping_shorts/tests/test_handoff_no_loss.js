// 담은 영상 유실 방지 회귀 테스트 (2026-08-18)
//   사장님: "제작소로 보냈는데 왜 분석이 안 되지" → 새로고침하니 재료가 비고 옛 작업이 복원됐다.
//   원인: _consumeProduceHandoff가 sessionStorage를 **먼저 지우고**, 서버 저장은 1초 디바운스
//   뒤에 했다. 저장이 실패하면(조용히) 담은 영상이 통째로 증발한다.
//   실측: 바구니 담기(17:14) 뒤 POST /api/produce/works가 한 건도 없었다.
//   → 지우기는 저장 성공(WORK_ID 채워짐) 뒤에만.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../static/produce.html'), 'utf8');

const i = src.indexOf('function _consumeProduceHandoff(){');
if (i < 0) { console.error('_consumeProduceHandoff not found'); process.exit(1); }
let d = 0, body = '';
for (let k = src.indexOf('{', i); k < src.length; k++) {
  if (src[k] === '{') d++;
  else if (src[k] === '}') { d--; if (d === 0) { body = src.slice(i, k + 1); break; } }
}

let p = 0, f = 0;
const t = (n, c) => { c ? (p++, console.log('  PASS', n)) : (f++, console.log('  FAIL', n)); };

// 주석을 뺀 실행부만 본다(주석에 단어가 있다고 통과되면 안 된다).
const code = body.split('\n').filter(l => !l.trim().startsWith('//')).join('\n');

t('저장 성공 확인(WORK_ID) 뒤에 지운다', /WORK_ID\)\s*\{\s*_clearHandoffStorage\(\)/.test(code));
t('무조건 지우기가 남아 있지 않다',
  !/^\s*_clearHandoffStorage\(\);\s*$/m.test(code.split('if(arrived')[0].replace(/if\(!HANDOFF\.length[^\n]*\n/, '')));
t('실패하면 사용자에게 알린다', code.includes('담은 영상은 그대로 있습니다'));
t('디바운스 예약분을 끄고 즉시 저장한다', code.includes('clearTimeout(_workTimer)') && code.includes('_pushWork'));

console.log('\n결과: PASS ' + p + ' / FAIL ' + f);
process.exit(f ? 1 : 0);
