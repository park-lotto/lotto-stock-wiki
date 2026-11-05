// #3954(11-04 김미화): PC 가 꺼져 실행기가 죽은 편이 디스크에 status 'execute' 로 남아, 다음 날 프로그램을 켜자
//   '실행기 일이 1462분째' 경보 + anyFlowBusy()=true(업데이트 교체·벤치마킹·종료 대기가 막힌다).
//   이 프로그램이 돌리지 않는 execute 편은 마지막 움직임이 DEAD_MS(2시간) 안일 때만 바쁨 — 다른 창이 진짜 돌리는 편은 진행 신호로 계속 움직인다.
//   review(회원 Claude 답 대기)는 그대로 바쁨(사용 한도 뒤 돌아올 수 있다 — 그 사이 엔진을 바꾸면 안 된다).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('flow_dead_execute');
const { loadFlow, flowBusy, flowRoot } = await import('../server/flow_driver.js');

function put(sid, d) {
  fs.mkdirSync(path.join(flowRoot(), sid), { recursive: true });
  fs.writeFileSync(path.join(flowRoot(), sid, 'flow.json'), JSON.stringify({ sid, preset: 'p_aaaaaaaaaa', ...d }));
  return loadFlow(sid);
}
const H = 3600 * 1000;

test('하루 전에 멈춘 execute 편(실행기 죽음)은 바쁜 편이 아니다', () => {
  assert.equal(flowBusy(put('aaaaaaaaaa01', { status: 'execute', movedAt: Date.now() - 24 * H })), false);
});

test('방금 움직인 execute 편(다른 창이 돌리는 중)은 바쁜 편이다', () => {
  assert.equal(flowBusy(put('aaaaaaaaaa02', { status: 'execute', movedAt: Date.now() - 5 * 60 * 1000 })), true);
});

test('진행 파일이 최근에 바뀌면 movedAt 이 오래돼도 바쁜 편이다', () => {
  const f = put('aaaaaaaaaa03', { status: 'execute', movedAt: Date.now() - 24 * H });
  fs.mkdirSync(path.join(flowRoot(), 'aaaaaaaaaa03', 'job'), { recursive: true });
  fs.writeFileSync(path.join(flowRoot(), 'aaaaaaaaaa03', 'job', 'progress.json'), '{}');
  assert.equal(flowBusy(f), true);
});

test('회원 Claude 답을 기다리는 review 편은 오래돼도 바쁜 편이다(엔진 교체 금지)', () => {
  assert.equal(flowBusy(put('aaaaaaaaaa04', { status: 'review', movedAt: Date.now() - 24 * H })), true);
});
