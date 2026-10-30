// 회원 고치기 고리(사장님 10-31 "막히면 고치고, 우리한테 오고, 우리가 덮어써 전체 배포") — 새 눈 요청·다시 시도 때 새 엔진.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { requestContent } from '../server/engine_bridge.js';
import { applyEngineNow } from '../server/updater.js';

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'repair-'));

test('새 눈 요청은 만든 Claude 에게 그림을 주지 않고 새 Agent 지시를 준다', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'p00.jpg'), 'x');
  const out = requestContent({ id: 'r1', dir, req: { tier: 'opus', prompt: '시트를 본다', tag: 'sheet_x', meta: { fresh: true },
    parts: [{ kind: 'image', file: 'p00.jpg' }, { kind: 'text', text: '대본' }] } });
  assert.equal(out.length, 1);
  assert.equal(out[0].type, 'text');
  assert.match(out[0].text, /새 Agent/);
  assert.ok(out[0].text.includes(path.join(dir, 'p00.jpg')));
  const ask = fs.readFileSync(path.join(dir, 'ask.txt'), 'utf8');
  assert.ok(ask.includes('시트를 본다') && ask.includes('대본'));
});

test('보통 요청은 그림을 그대로 싣는다', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'p00.jpg'), 'x');
  const out = requestContent({ id: 'r2', dir, req: { tier: 'opus', prompt: '본다', tag: 'plan_x', parts: [{ kind: 'image', file: 'p00.jpg' }] } });
  assert.equal(out[1].type, 'image');
});

test('제작자 과제에는 고칠 엔진 폴더가 실린다', () => {
  const out = requestContent({ id: 'r3', dir: tmp(), req: { tier: 'opus', prompt: '막힘', tag: 'task_1', parts: [] } });
  assert.match(out[0].text, /엔진 코드 폴더/);
});

test('다시 시도 때 받아 둔 새 engine 을 덮고, 같은 판은 두 번 덮지 않는다', () => {
  const home = tmp();
  fs.mkdirSync(path.join(home, 'engine'), { recursive: true });
  fs.writeFileSync(path.join(home, 'engine', 'a.py'), 'old');
  const src = path.join(home, '_update', '1.0.12', 'engine');
  fs.mkdirSync(path.join(src, 'tools', 'calcopy'), { recursive: true });
  fs.writeFileSync(path.join(src, 'tools', 'calcopy', 'make.py'), 'x');
  fs.writeFileSync(path.join(src, 'a.py'), 'new');
  fs.writeFileSync(path.join(home, '_update', 'pending.json'), JSON.stringify({ version: '1.0.12' }));
  assert.equal(applyEngineNow(home).applied, true);
  assert.equal(fs.readFileSync(path.join(home, 'engine', 'a.py'), 'utf8'), 'new');
  fs.writeFileSync(path.join(home, 'engine', 'a.py'), 'member');
  assert.equal(applyEngineNow(home).why, 'already');
  assert.equal(fs.readFileSync(path.join(home, 'engine', 'a.py'), 'utf8'), 'member');
});

test('받아 둔 판이 없으면 그대로 간다', () => {
  assert.equal(applyEngineNow(tmp()).why, 'no_pending');
});
