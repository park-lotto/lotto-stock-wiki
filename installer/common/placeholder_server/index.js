#!/usr/bin/env node
// 자리표시 서버 — shortem_client/server 가 아직 없을 때만 설치팩에 들어간다(빌드가 알린다).
// 도구 6개 이름은 진짜와 같고, shortem_setup 만 실제로 설치 상태(실행 도구 sha·ffmpeg ass 필터)를 잰다.
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const TOOLS_DIR = process.env.SHORTEM_TOOLS || path.resolve(__dirname, '..', 'tools');
const VERSION = '0.0.0-placeholder';
const TOOLS = ['shortem_setup', 'shortem_presets', 'shortem_profile', 'shortem_make', 'shortem_job', 'shortem_feedback'];

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function setupCheck() {
  const out = { ok: true, items: [] };
  let man;
  try { man = JSON.parse(fs.readFileSync(path.join(TOOLS_DIR, 'tools.manifest.json'), 'utf8')); } catch (e) {
    return { ok: false, items: [{ where: '설치', ok: false, why: 'tools.manifest.json 없음', fix: '설치팩 다시' }] };
  }
  let bad = 0;
  for (const f of man.files) {
    const p = path.join(TOOLS_DIR, f.path);
    if (!fs.existsSync(p) || sha256(p) !== f.sha256) bad += 1;
  }
  out.items.push({ where: '실행 도구', ok: bad === 0, why: `${man.files.length - bad}/${man.files.length} 일치` });
  const ff = path.join(TOOLS_DIR, man.tools.ffmpeg.path);
  try {
    const filters = execFileSync(ff, ['-hide_banner', '-filters'], { encoding: 'utf8', windowsHide: true });
    const ass = / ass /.test(filters);
    out.items.push({ where: 'ffmpeg', ok: ass, why: ass ? 'ass(libass) 필터 있음' : 'ass 필터 없음', fix: ass ? undefined : '설치팩 다시' });
  } catch (e) {
    out.items.push({ where: 'ffmpeg', ok: false, why: '실행 실패', fix: '설치팩 다시' });
  }
  out.items.push({ where: '라이선스', ok: Boolean(process.env.SHORTEM_LICENSE), why: process.env.SHORTEM_LICENSE ? '키 있음' : '키 없음' });
  out.ok = out.items.every((i) => i.ok);
  return out;
}

const send = (o) => process.stdout.write(JSON.stringify(o) + '\n');
let buf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => {
  buf += c;
  let nl;
  while ((nl = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    let r;
    try { r = JSON.parse(line); } catch (_) { continue; }
    if (r.id === undefined || r.id === null) continue;
    if (r.method === 'initialize') {
      send({ jsonrpc: '2.0', id: r.id, result: { protocolVersion: (r.params && r.params.protocolVersion) || '2025-06-18', capabilities: { tools: {} }, serverInfo: { name: 'shortem', version: VERSION } } });
    } else if (r.method === 'tools/list') {
      send({ jsonrpc: '2.0', id: r.id, result: { tools: TOOLS.map((n) => ({ name: n, description: n === 'shortem_setup' ? '숏템 준비 점검(자리표시 서버)' : '준비 중(자리표시 서버)', inputSchema: { type: 'object' } })) } });
    } else if (r.method === 'tools/call') {
      const n = r.params && r.params.name;
      const res = n === 'shortem_setup' ? setupCheck() : { ok: false, fail: { where: n, why: '숏템 서버가 아직 들어 있지 않은 시험용 설치팩입니다', fix: '정식 설치팩으로 다시 설치', retry_ok: false } };
      send({ jsonrpc: '2.0', id: r.id, result: { content: [{ type: 'text', text: JSON.stringify(res) }], structuredContent: res, isError: !res.ok } });
    } else if (r.method === 'ping') {
      send({ jsonrpc: '2.0', id: r.id, result: {} });
    } else {
      send({ jsonrpc: '2.0', id: r.id, error: { code: -32601, message: 'Method not found' } });
    }
  }
});
process.stdin.on('end', () => process.exit(0));
