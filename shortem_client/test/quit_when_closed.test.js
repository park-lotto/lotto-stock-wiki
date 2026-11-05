import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';

// index.js 는 불러오면 서버가 뜬다 — 함수 본문을 떼어 같은 코드로 시험한다(가짜 audit·바쁨)
const src = fs.readFileSync(new URL('../server/index.js', import.meta.url), 'utf8');
const body = src.slice(src.indexOf('export function quitWhenClaudeCloses'), src.indexOf('\n}\n', src.indexOf('export function quitWhenClaudeCloses')) + 3)
  .replace('export function', 'function');
const make = new Function('audit', 'anyFlowBusy', 'anyRunning', 'process', body + '\nreturn quitWhenClaudeCloses;');

test('Claude 창이 닫히면(입력 끝) 프로그램이 끝난다', () => {
  const stdin = new EventEmitter();
  let code = null;
  const q = make(() => {}, () => false, () => false, { stdin, exit() {} });
  q({ stdin, exit: c => { code = c; } });
  stdin.emit('end');
  assert.equal(code, 0);
});

test('도는 실행기가 있으면 끝날 때까지 기다린다', async () => {
  const stdin = new EventEmitter();
  let code = null, busy = true;
  const q = make(() => {}, () => busy, () => false, { stdin, exit() {} });
  q({ stdin, busy: () => busy, exit: c => { code = c; }, every: 20 });
  stdin.emit('close');
  await new Promise(r => setTimeout(r, 60));
  assert.equal(code, null);
  busy = false;
  await new Promise(r => setTimeout(r, 60));
  assert.equal(code, 0);
});

test('index.js 는 연결 직후 이 함수를 부른다', () => {
  assert.match(src, /await server\.connect\(new StdioServerTransport\(\)\);\s*\n\s*quitWhenClaudeCloses\(\);/);
});
