// 미리보기가 실제로 보이는 자리에 그려지는가 (2026-08-18)
//   사장님: "미리보기 성공하면 재생되어야 하는데 그게 없네."
//   실측(브라우저 직접 확인): 렌더 성공(preview_status=ready, preview.mp4 8.5MB)이고
//   <video>도 만들어졌는데 getBoundingClientRect가 0×0이었다. 부모를 따라가니
//   #mixPreviewRail이 display:none이었고, **그걸 여는 코드가 어디에도 없었다**(선언 1건뿐).
//   2026-08-16에 미리보기를 장면 편집 안으로 옮기며 이 슬롯을 감췄는데, 그리는 코드는
//   그대로 남아 결과가 영영 안 보이게 됐다.
const fs = require('fs');
const path = require('path');
// ★원본 위치는 env로 덮어쓸 수 있다(2026-08-21). js_harness.run_js는 이 소스를
//   **임시 .js 파일**로 옮겨 실행하므로 __dirname이 temp 폴더가 되고, 그러면
//   '../static/produce.html'이 엉뚱한 곳(AppData\Local\static\...)을 가리켜 ENOENT로 죽는다.
//   `node shopping_shorts/tests/test_preview_visible.js` 직접 실행은 종전 그대로 돈다.
const src = fs.readFileSync(
  process.env.PRODUCE_HTML || path.join(__dirname, '../static/produce.html'), 'utf8');
const code = src.split('\n').filter(l => !l.trim().startsWith('//')).join('\n');

let p = 0, f = 0;
const t = (n, c) => { c ? (p++, console.log('  PASS', n)) : (f++, console.log('  FAIL', n)); };

t('여닫기가 한 곳에 정의돼 있다', /function _pvOpen\(\)/.test(code) && /function _pvClose\(\)/.test(code));
t('여는 쪽이 레일까지 연다', /_pvOpen[\s\S]{0,200}mixPreviewRail[\s\S]{0,120}display *= *''/.test(code));
// ★2026-08-21: 자리 주인 판정처를 _pvShow 하나로 모으면서 여기서 부르는 이름이 바뀌었다.
//   _pvShow는 첫 줄에서 _pvOpen()을 부르므로 "레일까지 연다"는 규약은 그대로고,
//   거기에 더해 #mixPreview까지 켠다(가조립 재생 뒤 확정 결과가 안 보이던 것을 고친 부분).
//   그래서 **둘 중 무엇을 부르든** 통과시킨다 — 이 단언이 지키려는 건 함수 이름이 아니라
//   "그리기 전에 자리를 연다"는 규약이다(옛 이름만 고집하면 판정처 일원화를 막는다).
t('영상 그릴 때 자리를 연다', /_renderPreviewVideo[\s\S]{0,200}(_pvOpen\(\)|_pvShow\('video'\))/.test(code));
// ★이 단언은 원래 `_pvOpen()`이 2번 이상 나오는지 셌다. 판정처를 _pvShow로 모은 뒤엔
//   실제 호출부가 전부 _pvShow로 옮겨가, **정의 1줄 + _pvShow 안의 1줄 = 2**로 우연히
//   통과하게 됐다(2026-08-21 실측) — 즉 startPreview를 더는 검사하지 않는 빈 단언이었다.
//   그래서 세는 것을 그만두고 **이름 그대로 "미리보기 시작할 때 자리를 여는가"**를 본다.
t('미리보기 시작할 때도 연다',
  /async function startPreview\(\)[\s\S]{0,1200}_pvShow\('video'\)/.test(code));
// _pvOpen/_pvClose 정의 안은 당연히 패널을 직접 만진다 — 그 둘을 뺀 나머지에서
// 직접 만지는 곳이 없어야 한다(있으면 레일을 안 열어 또 0x0이 된다).
t('정의 밖에서 패널을 직접 만지지 않는다', (function(){
  var stripped = code.split('function _pvOpen()')[0]
                 + (code.split('function _renderPreviewVideo')[1] || '');
  return !/mixPreviewPanel'\)[^\n]*style\.display *=/.test(stripped);
})());

console.log('\n결과: PASS ' + p + ' / FAIL ' + f);
process.exit(f ? 1 : 0);
