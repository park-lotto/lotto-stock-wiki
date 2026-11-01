#!/usr/bin/env node
// 설치 직후 1회 — 설치 프로그램(NSIS / 맥 pkg postinstall)이 동봉 node 로 부른다.
// 하는 일: install.json 기록 · 시작.md 를 실제 설치 경로로 채워 설치 폴더와 바탕화면 '숏템작업'에 둔다.
// 네트워크 0, 셸 0. 인자: --home <설치 폴더> --desktop <바탕화면 폴더> [--version x.y.z]
'use strict';
const fs = require('fs');
const path = require('path');

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const home = path.resolve(arg('--home', path.resolve(__dirname)));
const desktop = arg('--desktop', null);
const version = arg('--version', '0.0.0');

if (!fs.existsSync(path.join(home, 'tools', 'tools.manifest.json'))) {
  console.error(`[postinstall] 설치 폴더가 아닙니다: ${home}`);
  process.exit(2);
}

// 설치된 실행 도구가 설치 목록(sha256)과 같은지 — 경로 길이·디스크 부족으로 몇 개만 빠진 설치를 여기서 잡는다
{
  const crypto = require('crypto');
  const tdir = path.join(home, 'tools');
  const man = JSON.parse(fs.readFileSync(path.join(tdir, 'tools.manifest.json'), 'utf8'));
  const bad = [];
  for (const f of man.files || []) {
    const p = path.join(tdir, ...f.path.split('/'));
    let ok = false;
    try { ok = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex') === f.sha256; } catch (_) { ok = false; }
    if (!ok) bad.push(f.path);
  }
  if (bad.length) {
    console.error(`[postinstall] 설치 파일 ${bad.length}개가 목록과 다릅니다(첫 파일: ${bad[0]})`);
    process.exit(4);
  }
  console.log(`[postinstall] 실행 도구 ${(man.files || []).length}개 sha256 일치`);
}

fs.writeFileSync(path.join(home, 'install.json'), JSON.stringify({
  product: 'shortem',
  version,
  platform: process.platform,
  arch: process.arch,
  home,
  installed_at: new Date().toISOString(),
}, null, 2) + '\n', 'utf8');

const pluginDir = path.join(home, 'claude-plugin').split(path.sep).join('/');
const tpl = fs.readFileSync(path.join(home, '시작.template.md'), 'utf8');
const startMd = tpl.split('{{PLUGIN_DIR}}').join(pluginDir);
fs.writeFileSync(path.join(home, '시작.md'), startMd, 'utf8');

if (desktop) {
  const work = path.join(desktop, '숏템작업');
  fs.mkdirSync(work, { recursive: true });
  fs.writeFileSync(path.join(work, '시작.md'), startMd, 'utf8');
  const guide = path.join(home, '설치안내.html');
  if (fs.existsSync(guide)) fs.copyFileSync(guide, path.join(work, '설치안내.html'));
  console.log(`[postinstall] 작업 폴더: ${work}`);
}
console.log(`[postinstall] 완료: ${home}`);
