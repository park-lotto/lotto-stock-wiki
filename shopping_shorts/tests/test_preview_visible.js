// 미리보기가 실제로 보이는 자리에 그려지는가 (2026-08-18)
//   사장님: "미리보기 성공하면 재생되어야 하는데 그게 없네."
//   실측(브라우저 직접 확인): 렌더 성공(preview_status=ready, preview.mp4 8.5MB)이고
//   <video>도 만들어졌는데 getBoundingClientRect가 0×0이었다. 부모를 따라가니
//   #mixPreviewRail이 display:none이었고, **그걸 여는 코드가 어디에도 없었다**(선언 1건뿐).
//   2026-08-16에 미리보기를 장면 편집 안으로 옮기며 이 슬롯을 감췄는데, 그리는 코드는
//   그대로 남아 결과가 영영 안 보이게 됐다.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../static/produce.html'), 'utf8');
const code = src.split('\n').filter(l => !l.trim().startsWith('//')).join('\n');

let p = 0, f = 0;
const t = (n, c) => { c ? (p++, console.log('  PASS', n)) : (f++, console.log('  FAIL', n)); };

t('여닫기가 한 곳에 정의돼 있다', /function _pvOpen\(\)/.test(code) && /function _pvClose\(\)/.test(code));
t('여는 쪽이 레일까지 연다', /_pvOpen[\s\S]{0,200}mixPreviewRail[\s\S]{0,120}display *= *''/.test(code));
t('영상 그릴 때 자리를 연다', /_renderPreviewVideo[\s\S]{0,200}_pvOpen\(\)/.test(code));
t('미리보기 시작할 때도 연다', code.split('_pvOpen()').length - 1 >= 2);
// _pvOpen/_pvClose 정의 안은 당연히 패널을 직접 만진다 — 그 둘을 뺀 나머지에서
// 직접 만지는 곳이 없어야 한다(있으면 레일을 안 열어 또 0x0이 된다).
t('정의 밖에서 패널을 직접 만지지 않는다', (function(){
  var stripped = code.split('function _pvOpen()')[0]
                 + (code.split('function _renderPreviewVideo')[1] || '');
  return !/mixPreviewPanel'\)[^\n]*style\.display *=/.test(stripped);
})());

console.log('\n결과: PASS ' + p + ' / FAIL ' + f);
process.exit(f ? 1 : 0);
