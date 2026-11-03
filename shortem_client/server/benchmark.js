// 고급반 채널 벤치마킹(관제 304, 사장님 11-02 "고급형은 그 노하우를 담아준다 · MCP 로 빌려주는 구조").
//   반 판단은 서버 claude_portal.benchmark_rent 한 곳(기본반은 거기서 거절). 뜯기·틀·저장 판단은 엔진 tools/calcopy/engine/bench_member.py.
//   여기는 빌리고 → 엔진 폴더에 없는 파일만 풀고 → 띄우고 → 끝나면 푼 파일만 지우고 → 결과를 내 프리셋으로 옮긴다(판단 0).
//   2판(관제 319): 띄우기 = 서버 지시서 고리(flow_driver.startBenchFlow — 제작과 같은 absorb·pump). 단계 판단은 서버 flow_bench 한 곳.
import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import { api, ApiError } from './api.js';
import { audit } from './audit.js';
import { activeRuns, engineRoot } from './engine_bridge.js';
import { anyFlowBusy, loadFlow, startBenchFlow, waitFlow } from './flow_driver.js';
import { Lease } from './lease.js';
import { VIDEO, YT_CHANNEL, waitMs } from './make_flow.js';
import { addMine, dropMine, forgetKept } from './my_presets.js';
import { ensureDir, homeDir, jail } from './paths.js';
import { flowRoot } from './flow_driver.js';
import { openPack, readZip, renting } from './preset_rent.js';
import { select } from './local_settings.js';

const MARK = '.bench_rented.json';                       // 이번에 푼 파일 목록 — 프로그램이 죽어도 다음에 켤 때 이것만 지운다(개발 PC 의 진짜 코드는 목록에 없다)
const ROOTS = ['tools/', 'shopping_shorts/'];
const FAIL = { tier_locked: '숏클 페이지에서 고급반으로 올리면 바로 쓸 수 있어요', not_ready: '잠시 뒤 다시 해 주세요', busy_other_device: '다른 PC 작업이 끝난 뒤 다시 해 주세요', lease_lost: '다른 작업이 끝난 뒤 다시 해 주세요', no_key: '숏템 설치를 다시 확인해 주세요' };
let cur = null;                                          // 지금 도는 벤치마킹(한 번에 하나) — { sid }

function wipe(root) {
  const mark = path.join(root, MARK);
  let list = [];
  try { list = JSON.parse(fs.readFileSync(mark, 'utf8')); } catch { return false; }
  for (const f of list) {
    try {
      fs.rmSync(path.join(root, f), { force: true });
      for (let d = path.dirname(f); d !== '.'; d = path.dirname(d)) fs.rmdirSync(path.join(root, d));   // 빈 폴더만 지워진다(파일이 있으면 여기서 멈춘다)
    } catch { /* 폴더에 다른 파일이 있거나 다음에 켤 때 다시 */ }
  }
  fs.rmSync(mark, { force: true });
  return list.length > 0;
}
export const sweepBench = root => (cur ? false : wipe(root));

// 받은 묶음 → 엔진 폴더. ★이미 있는 파일은 덮지 않는다 — 설치본 코드를 건드리지 않고, 지울 때도 푼 것만 지운다
export function unpackBench(zip, root) {
  const files = readZip(zip).filter(f => {
    if (!ROOTS.some(r => f.name.startsWith(r)) || f.name.includes('..') || f.name.includes('\\')) throw new Error('묶음에 바깥 경로가 있습니다');
    return !fs.existsSync(path.join(root, f.name));
  });
  fs.writeFileSync(path.join(root, MARK), JSON.stringify(files.map(f => f.name)));   // 쓰기 전에 적는다(중간에 죽어도 지울 수 있게)
  for (const f of files) {
    const dst = path.join(root, f.name);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.writeFileSync(dst, f.data);
  }
  return files.length;
}

async function rentEngine(root) {
  const jobId = 'b' + Date.now().toString(36) + randomBytes(3).toString('hex');
  const lease = new Lease(jobId, { stepName: () => '분석' });
  await lease.acquire();
  try {
    const r = await api.benchmarkRent(jobId, lease.id);
    const n = unpackBench(openPack(r), root);
    audit('benchmark_rent', { job: jobId, result: 'ok', n });
    return lease;
  } catch (e) {
    await lease.release();
    throw e;
  }
}

// 흐름이 끝났을 때 한 번(flow_driver endHooks) — 완성이면 내 프리셋으로 올리고(임시 시험본은 같은 slug 라 addMine 이 갈아 끼운다),
//   아니면 임시 시험본을 지운다. 어느 쪽이든 푼 엔진 파일만 지우고 빌림을 돌려준다.
async function endBench(f, root, lease, channel) {
  try {
    const d = f.status === 'done' && f.bench && f.bench.done;
    if (d && d.slug && d.style) {
      const W = path.join(flowRoot(), f.sid, 'job');
      const mine = addMine(W, { ok: true, name: d.name || f.bench.name, slug: d.slug, presets: [{ style: d.style, sources: [] }] }, channel);
      if (d.zip) {
        const z = jail(W, d.zip);
        fs.copyFileSync(z, path.join(ensureDir(homeDir(), path.join('내 프리셋', d.slug)), path.basename(z)));
      }
      forgetKept(d.slug);
      select(mine[0].id);
      f.bench.mine = mine.map(p => ({ id: p.id, name: p.name }));
      audit('benchmark', { result: 'ok', n: mine.length, v: 2 });
    } else {
      const slug = trialSlug(f);
      if (slug) dropMine(slug);
      audit('benchmark', { result: f.cancelled ? 'cancelled' : 'stopped', v: 2 });
    }
  } finally {
    if (cur && cur.sid === f.sid) cur = null;
    wipe(root);
    await lease.release();
  }
}
const trialSlug = f => (f.bench && f.bench.trial_slug) || '';

// 흐름 응답(flow_driver.shapeFlow 꼴) → 벤치마킹 응답. 완성만 내 프리셋 안내로 바꾸고, 나머지는 그대로(단계 한 줄·멈춤 두 줄)
async function shaped(sid, s) {
  if (!s || s.need !== 'done') return s;
  const f = loadFlow(sid);
  if (f && f.running) await f.running;     // 완성 직후 — 끝 정리(내 프리셋 올리기)가 끝날 때까지
  const mine = (f && f.bench && f.bench.mine) || [];
  if (!mine.length) return { sid, message: s.message, fail: { where: '벤치마킹', why: '프리셋을 저장하지 못했어요', fix: '잠시 뒤 다시 해 주세요', retry_ok: true } };
  return { sid, need: 'done', title: mine[0].name, info: { presets: mine.map(p => ({ preset: p.name })) },
    hints: [`'${mine[0].name}' 프리셋을 저장하고 지금 쓸 프리셋으로 골랐습니다 — shortem_presets 에 보입니다`],
    next: `shortem_make(step="start", preset_name="${mine[0].name}", video=<쓸 영상 주소>)` };
}

export async function benchStart({ channel, videos, name, n }) {
  if (cur) return benchWait(cur.sid);
  if (channel && !YT_CHANNEL.test(channel)) return { hints: ['채널 주소는 https://www.youtube.com/@이름 또는 /channel/UC… 꼴이어야 합니다(틱톡·인스타는 영상 주소를 videos 로 주세요)'] };
  if (!channel && !(videos || []).length) return { hints: ['채널 주소(channel)나 영상 주소(videos)를 주세요'] };
  if ((videos || []).some(v => !VIDEO.test(v))) return { hints: ['영상 주소는 유튜브 쇼츠·틱톡 영상·인스타 릴스 주소여야 합니다'] };
  if (activeRuns().length || anyFlowBusy() || renting()) return { fail: { where: '벤치마킹', why: '지금 만드는 편이 있습니다', fix: '끝난 뒤 다시 해 주세요', retry_ok: true } };
  const root = engineRoot();
  let lease;
  try { sweepBench(root); lease = await rentEngine(root); }
  catch (e) { return { fail: { where: '벤치마킹', why: e instanceof ApiError ? (e.msg || e.code) : '벤치마킹을 받지 못했습니다', fix: FAIL[e.code] || '잠시 뒤 다시 해 주세요', retry_ok: e.code !== 'tier_locked' } }; }
  const label = String(name || '내 프리셋').trim().slice(0, 30) || '내 프리셋';
  let f;
  try { f = await startBenchFlow({ channel, videos, name: label, n: n || 3, onEnd: fl => endBench(fl, root, lease, channel || '') }); }
  catch (e) {
    wipe(root); await lease.release();
    return { fail: { where: '벤치마킹', why: e instanceof ApiError ? (e.msg || e.code) : '벤치마킹을 시작하지 못했습니다', fix: FAIL[e.code] || '잠시 뒤 다시 해 주세요', retry_ok: e.code !== 'tier_locked' } };
  }
  if (!flowGone(f)) cur = { sid: f.sid };
  return shaped(f.sid, await waitFlow(f.sid, waitMs()));
}
const flowGone = f => f.status === 'done' || f.cancelled || !!(f.fail && !f.fail.retry_ok);

export async function benchWait(sid) {
  const id = sid || (cur && cur.sid);
  if (!id || !loadFlow(id) || !loadFlow(id).bench) return { hints: ['기다릴 벤치마킹이 없습니다 — shortem_presets 로 저장됐는지 보세요'] };
  return shaped(id, await waitFlow(id, waitMs()));
}

export const BENCH_TEXT = "채널 벤치마킹(고급반) — 고객이 준 채널의 조회수 높은 쇼츠를 이 PC 에서 받아 화면 틀을 뜯어 내 프리셋으로 저장합니다. step='start'(channel=유튜브 채널 주소 또는 videos=영상 주소 목록, name=프리셋 이름, n=쓸 편 수 1~5) → 응답의 need 가 'ai' 면 shortem_ai 로 답한 뒤 step='wait'(sid) → need='done' 이면 저장 끝, 응답의 next 로 제작합니다. 기본반이면 fail 의 이유·할 일을 그대로 전합니다.";

export function registerBenchmark(server, reply) {
  server.registerTool('shortem_benchmark', {
    title: '채널 벤치마킹(고급반)', description: BENCH_TEXT,
    inputSchema: { step: z.enum(['start', 'wait']), channel: z.string().max(200).optional(), videos: z.array(z.string().max(300)).max(5).optional(), name: z.string().max(30).optional(), n: z.number().int().min(1).max(5).optional(), sid: z.string().regex(/^[0-9a-f]{12}$/).optional(), run_id: z.string().max(40).optional() },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
  }, async a => {
    const o = a.step === 'wait' ? await benchWait(a.sid) : await benchStart(a);   // run_id = 1판 이름(받아도 무시 — 지금 도는 벤치마킹을 기다린다)
    audit('benchmark_step', { step: a.step, need: o.need || '' });
    return reply(o);
  });
}
