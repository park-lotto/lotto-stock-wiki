// 매칭 완료 자동이동은 job당 한 번만 (2026-08-18)
//   사장님: "3단계 다 만들고 재생 다 해본 뒤 2단계 누르니 넘어갔다가 다시 3단계로 튕겨온다."
//   원인: pollMix의 완료 분기가 '방금 끝났다'가 아니라 **'상태가 완료다'**로 판정한다.
//   폴러가 재기동되면(_restoreWork가 job 상태를 보고 MIX_POLL을 다시 건다) 이미 끝난 job에도
//   매 tick jump가 돌아, 사용자가 어느 단계에 있든 2.5초 만에 3단계로 끌려온다.
//   clearInterval만으론 못 막는다 — 핸들이 다시 만들어지는 경로가 따로 있다.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../static/produce.html'), 'utf8');

let p = 0, f = 0;
const t = (n, c) => { c ? (p++, console.log('  PASS', n)) : (f++, console.log('  FAIL', n)); };

const code = src.split('\n').filter(l => !l.trim().startsWith('//')).join('\n');

t('래치 변수가 선언돼 있다', /let\s+_mixAutoJumped/.test(code));
t('완료 자동이동이 래치로 감싸여 있다',
  /_mixAutoJumped\s*!==[\s\S]{0,80}\n[\s\S]{0,120}jump\(\(d\.candidates/.test(code));
t('래치를 이동 전에 세운다(재진입 방지)',
  code.indexOf('_mixAutoJumped = (d.job_id') < code.indexOf('jump((d.candidates'));
t('맨몸 jump가 남아 있지 않다',
  !/^\s*jump\(\(d\.candidates && d\.candidates\.length > 1\) \? 1 : 2\);\s*$/m
    .test(code.replace(/if\(_mixAutoJumped[\s\S]*?\n\s*\}/, '')));

console.log('\n결과: PASS ' + p + ' / FAIL ' + f);
process.exit(f ? 1 : 0);
