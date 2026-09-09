// lensOpenAll 이 실제로 다섯 곳을 여는지 확인한다(index.html에서 함수만 떼어 실행).
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(
  path.join(__dirname, '..', 'shopping_shorts', 'static', 'index.html'), 'utf8');

function grab(name) {
  const s = src.indexOf('function ' + name);
  if (s < 0) throw new Error('함수를 못 찾음: ' + name);
  const rest = src.slice(s);
  return rest.slice(0, rest.indexOf('\n}\n') + 3);
}

// 의존 함수까지 함께 올린다 — 호출부 형태 그대로 돌려야 검증이 유효하다.
const consts = src.slice(src.indexOf('const _LENS_AUTO_LANG'), src.indexOf('function _lensKwFor'))
  + src.slice(src.indexOf('const _LENS_OPEN_ALL'), src.indexOf('function lensOpenAll'));
eval(consts + grab('lensOpenAll') + grab('_lensSearchUrl') + grab('_igKw')
     + grab('_lensKwFor') + grab('_openUrl'));

const opened = [];
let allow = 99;
global.window = { open: (u) => { if (opened.length >= allow) return null; opened.push(u); return {}; } };
global.LENS_STATE = {};
global.renderLens = () => {};

let ok = true;
const check = (label, cond, detail) => {
  ok = ok && cond;
  console.log((cond ? '  OK  ' : '  실패 ') + label + (detail ? '   ' + detail : ''));
};

const cand = { ko: '미니 재봉틀', zh: '迷你缝纫机', en: 'mini sewing machine', ja: 'ミニミシン' };

// ① 해외 원본(auto) — 플랫폼마다 언어가 갈린다
LENS_STATE.X = { lang: 'auto', cnCands: [cand] };
lensOpenAll('X', 0);
check('다섯 곳이 열린다', opened.length === 5, String(opened.length));
// 샤오홍슈는 _openUrl이 rednote.com 으로 바꿔 연다(정상). 중국어인지는 %E8%BF%B7(迷)로 본다.
check('샤오홍슈가 중국어로 열린다', /rednote\.com|xiaohongshu/.test(opened[0]||'') && /%E8%BF%B7/.test(opened[0]||''), (opened[0]||'').slice(0,58));
check('틱톡이 들어있다', opened.some(u => /tiktok\.com/.test(u)));
check('인스타가 들어있다', opened.some(u => /instagram\.com/.test(u)));
check('핀터레스트가 들어있다', opened.some(u => /pinterest\.com/.test(u)));
check('팝업 안내 없음', !LENS_STATE.X.openNote, LENS_STATE.X.openNote || '');

// ② 팝업이 막힌 경우 — 몇 개만 열리고 안내가 뜬다
opened.length = 0; allow = 2;
LENS_STATE.Y = { lang: 'en', cnCands: [cand] };
lensOpenAll('Y', 0);
check('막히면 열린 만큼만', opened.length === 2, String(opened.length));
check('막히면 안내가 뜬다', /2\/5/.test(LENS_STATE.Y.openNote || ''),
  (LENS_STATE.Y.openNote || '').slice(0, 40));

// ③ 검색어가 없으면 아무것도 안 연다
opened.length = 0; allow = 99;
LENS_STATE.Z = { lang: 'ja', cnCands: [{ ko: '', zh: '', en: '', ja: '' }] };
lensOpenAll('Z', 0);
check('빈 검색어면 안 연다', opened.length === 0, String(opened.length));

// ④ 없는 카드/상태에도 안 터진다
lensOpenAll('없음', 0); lensOpenAll('Z', 99);
check('빈 입력에도 안 터짐', true);

console.log(ok ? '\n전부 통과' : '\n★실패 있음');
process.exit(ok ? 0 : 1);
