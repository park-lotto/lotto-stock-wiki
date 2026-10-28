// 썰쇼핑형 훅에 이븐쇼핑식 '흰 띠 보조제목'을 붙인다(2026-09-18 사장님 "보조제목 없는 템플릿 모두 만들고
// 이븐쇼핑처럼 효과도 다 되게").
//
// 왜 생성기(build_precision20_data.py)가 아니라 이 패치인가: 지금 out/precision20-data.js는 생성 뒤 손으로
// 다듬은 값이 섞여 있어 생성기를 다시 돌리면 그대로 재현되지 않는다(실측: s0101 폰트·자간·외곽선이 바뀜).
// 그래서 현재 파일 위에 '보조제목 줄이 없을 때만' 덧붙인다 — 여러 번 돌려도 결과가 같다.
//
// 모양은 이븐쇼핑(t11) 원본 비율을 따른다: 띠 높이 6.8%·위아래 여백 1.2%·글자 크기 띠의 0.49배·
// 흰 그라데이션 + 흰 빛 번짐. 편집기는 훅 3번째 줄을 bodyTitle로, 띠 면을 precision-patch로 그리므로
// '흰 띠 스윽 올라오기'가 글자와 상자를 한 덩어리로 잡는다.
//   node tools/add_story_support_band.js            # 적용
//   node tools/add_story_support_band.js --check    # 바꾸지 않고 무엇이 바뀔지만 출력
const fs = require('fs'), path = require('path');
const FILE = path.resolve(__dirname, '../out/precision20-data.js');
const check = process.argv.includes('--check');

const src = fs.readFileSync(FILE, 'utf8');
const w = {}; new Function('window', src)(w);
const rows = w.PRECISION20;
const report = [];

for (const p of rows) {
  const f = p.hook;
  if (!f || !Array.isArray(f.lines) || !f.lines.length) { report.push([p.id, 'skip:no-lines']); continue; }
  // 이미 흰 띠가 있는 훅은 건드리지 않는다 — 줄(bind)로 있거나, 별도 white_box 글자로 있다(s0101·t03·t06).
  //   white_box를 놓치고 덧붙였다가 보조제목이 두 번 겹쳐 찍힌 실사고(2026-09-18) 뒤 추가.
  if (f.lines.some(l => l.bind === 'bodyTitle') || f.lines.length > 2 || f.white_box?.text) { report.push([p.id, 'skip:has-support']); continue; }
  const W = f.width, H = f.height;
  const titleEnd = Math.max(...f.lines.map(l => l.y1));
  const bandH = Math.round(H * 0.068), gap = Math.round(H * 0.012), inset = Math.round(W * 0.012);
  const bandY = titleEnd + gap;
  const oldVideo = f.video_from.y;
  const newVideo = Math.max(oldVideo, bandY + bandH + gap);
  const bg = f.title_bg || f.lines[0].background || '#000000';
  const pad = Math.round(bandH * 0.12);
  const surfaces = f.surfaces || (f.surfaces = []);
  // 제목 아래~새 영상 시작까지 제목판 색으로 채운다(영상을 내린 만큼 빈 곳이 생기지 않게).
  surfaces.push({ x: 0, y: titleEnd, width: W, height: newVideo - titleEnd, background: bg, role: 'support-band-fill' });
  surfaces.push({
    x: inset, y: bandY, width: W - inset * 2, height: bandH, role: 'support-band',
    background: 'linear-gradient(180deg,#FFFFFF,#FFFFFF 72%,#ECEEEC)',
    shadow: `0 0 ${Math.round(bandH * 0.24)}px ${Math.round(bandH * 0.14)}px #FFFFFFB0`, radius: 2,
  });
  f.lines.push({
    bind: 'bodyTitle', x0: inset + 8, x1: W - inset - 8, y0: bandY + pad, y1: bandY + bandH - pad, h: bandH - pad * 2,
    font_size: Math.round(bandH * 0.49), font_family: f.font_family || f.lines[0].font_family,
    font_weight: f.font_weight ?? f.lines[0].font_weight ?? 400, color: '#080808', background: '#FFFFFF',
    no_patch: true, max_lines: 1, letter_spacing: -0.6, stroke: 0, shadow_y: 0,
  });
  f.video_from = { y: newVideo, pct: +(newVideo / H * 100).toFixed(2) };
  report.push([p.id, `band y${bandY}+${bandH} video ${oldVideo}->${newVideo} (${(((newVideo - oldVideo) / H) * 100).toFixed(1)}%)`]);
}

for (const r of report) console.log(r.join('  '));
if (!check) {
  fs.writeFileSync(FILE, 'window.PRECISION20=' + JSON.stringify(rows) + ';\n', 'utf8');
  console.log('written', FILE);
}
