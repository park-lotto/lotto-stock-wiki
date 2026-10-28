// 썰쇼핑형 훅에 채널명 칸을 붙인다(2026-09-18 사장님 "모든 게 채널명/훅제목1/훅제목2/보조제목 다 들어가고").
// 실측: 썰쇼핑형 20종 중 10종(t11·t05·t06·t07·t08·t10·t13·t14·t16·t19)은 본문에만 채널명 칸이 있고 훅에는 없어,
//   편집기에 채널명 입력칸이 안 떴다. 같은 템플릿 본문의 채널명 칸을 훅에 복사한다.
// 훅 첫 제목줄과 겹치면(t06·t19) 칸을 제목줄 위로 올리고, 그래도 모자라면 칸과 글자를 같이 줄인다.
// 생성기가 아니라 이 패치인 이유는 add_story_support_band.js와 같다(데이터 파일에 손 다듬은 값이 섞임).
// 여러 번 돌려도 결과가 같다(이미 채널 칸이 있으면 건너뜀).
//   node tools/add_story_hook_channel.js [--check]
const fs = require('fs'), path = require('path');
const FILE = path.resolve(__dirname, '../out/precision20-data.js');
const check = process.argv.includes('--check');
const src = fs.readFileSync(FILE, 'utf8');
const w = {}; new Function('window', src)(w);
const rows = w.PRECISION20;
const report = [];
for (const p of rows) {
  const f = p.hook, b = p.body;
  if (!f || !b) continue;
  if (f.channel_box || f.channel_boxes?.length) { report.push([p.id, 'skip:has-channel']); continue; }
  const c = b.channel_box || b.channel_boxes?.[0];
  if (!c) { report.push([p.id, 'skip:no-body-channel']); continue; }
  const box = JSON.parse(JSON.stringify(c));
  // 훅에는 본문 같은 머리띠가 없어 작은 칸으로 맨 위에 둔다. 글자색은 훅 제목판 배경에서 읽히는 색으로.
  const bg = f.top_band?.color || f.title_bg || '#000000';
  const rgb = (bg.match(/[a-f\d]{2}/gi) || []).slice(0, 3).map(n => parseInt(n, 16) / 255);
  const lum = rgb.length === 3 ? rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722 : 0;
  // 이븐쇼핑은 훅에도 본문과 같은 머리띠(☰ 🔍)가 있어 본문 칸을 그대로 쓴다.
  const keep = p.id === 't11';
  const h = keep ? box.height : Math.min(box.height, 26);
  box.font_size = Math.round(box.font_size * h / box.height); box.height = h; if (!keep) box.y = 14;   // y=8은 글자 윗부분이 화면 밖으로 잘렸다(실측)
  if (!keep) { box.color = lum > .5 ? '#111111' : '#FFFFFF'; box.background = bg; }
  // 첫 제목줄이 칸 바로 밑이면 제목·흰 띠·영상 시작을 함께 내린다(글자는 줄이지 않는다).
  //   실측: 제목 글자는 맞춤 확대 때문에 y0보다 20px가량 위에 그려진다(t19) → 여유 24px.
  const firstLine = Math.min(...(f.lines || []).map(l => l.y0));
  const need = box.y + box.height + 24, d = Math.max(0, need - firstLine);
  if (d) {
    const from = firstLine - 10, mv = o => { if (o && typeof o.y0 === 'number' && o.y0 >= from) { o.y0 += d; if (typeof o.y1 === 'number') o.y1 += d; } };
    (f.lines || []).forEach(mv);
    if (f.white_box) { mv(f.white_box.text); if (f.white_box.y0 >= from) { f.white_box.y0 += d; f.white_box.y1 += d; } }
    for (const k of ['surfaces', 'boxes', 'ornaments']) (f[k] || []).forEach(o => { if (o.y >= from) o.y += d; });
    (f.cleanup_regions || []).forEach(o => { if (o.role !== 'original-title' && o.y >= from) o.y += d; });
    f.video_from.y += d;
  }
  f.channel_box = box;
  report.push([p.id, `add h=${box.height} fs=${box.font_size} color=${box.color} shift=${d}`]);
}
console.log(report.map(r => r.join(' ')).join('\n'));
if (!check) fs.writeFileSync(FILE, 'window.PRECISION20=' + JSON.stringify(rows) + ';\n', 'utf8');
