// 고급반 채널 벤치마킹(관제 304, 사장님 11-02 "고급형은 그 노하우를 담아준다 · MCP 로 빌려주는 구조").
//   반 판단은 서버 claude_portal.benchmark_rent 한 곳(기본반은 거기서 거절). 뜯기·틀·저장 판단은 엔진 tools/calcopy/engine/bench_member.py.
//   여기는 빌리고 → 엔진 폴더에 없는 파일만 풀고 → 띄우고 → 끝나면 푼 파일만 지우고 → 결과를 내 프리셋으로 옮긴다(판단 0).
import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import { api, ApiError } from './api.js';
import { audit } from './audit.js';
import { activeRuns, engineRoot, pending, startScript, waitRun } from './engine_bridge.js';
import { anyFlowBusy } from './flow_driver.js';
import { Lease } from './lease.js';
import { refreshCookies } from './logins.js';
import { cleanWhy, VIDEO, YT_CHANNEL, waitMs } from './make_flow.js';
import { addMine } from './my_presets.js';
import { ensureDir, homeDir } from './paths.js';
import { openPack, readZip, renting } from './preset_rent.js';
import { select } from './local_settings.js';

const MARK = '.bench_rented.json';                       // 이번에 푼 파일 목록 — 프로그램이 죽어도 다음에 켤 때 이것만 지운다(개발 PC 의 진짜 코드는 목록에 없다)
const ROOTS = ['tools/', 'shopping_shorts/'];
const ENTRY = ['tools', 'calcopy', 'engine', 'bench_member.py'];
const FAIL = { tier_locked: '숏클 페이지에서 고급반으로 올리면 바로 쓸 수 있어요', not_ready: '잠시 뒤 다시 해 주세요', busy_other_device: '다른 PC 작업이 끝난 뒤 다시 해 주세요', lease_lost: '다른 작업이 끝난 뒤 다시 해 주세요', no_key: '숏템 설치를 다시 확인해 주세요' };
let cur = null;                                          // 지금 도는 벤치마킹(한 번에 하나)

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

function progress(c) {
  try { const p = JSON.parse(fs.readFileSync(path.join(c.out, 'progress.json'), 'utf8')); return p.m ? `${p.what} ${p.n}/${p.m}` : String(p.what || ''); } catch { return '벤치마킹 준비 중'; }
}

// 엔진 결과 → 내 프리셋. 첫 프리셋을 지금 쓸 프리셋으로 고른다
function finish(c, res) {
  cur = null;
  fs.rmSync(c.out, { recursive: true, force: true, maxRetries: 2 });
  return res;
}
function done(c, r) {
  if (!r || !r.ok) {
    const why = cleanWhy((r && (r.why || r.error)) || '벤치마킹이 멈췄습니다');
    return finish(c, { fail: { where: '벤치마킹', why, fix: '영상 주소를 직접 주거나, 유튜브 로그인(shortem_login)을 확인한 뒤 다시 해 주세요', retry_ok: true } });
  }
  const mine = addMine(c.out, r, c.channel);
  select(mine[0].id);
  audit('benchmark', { result: 'ok', n: mine.length });
  const left = (r.failed || []).length;
  return finish(c, { need: 'done', title: mine[0].name, info: { presets: mine.map(p => ({ preset: p.name, videos: p.sources })), failed_videos: left },
    hints: [`'${mine[0].name}' 프리셋을 저장하고 지금 쓸 프리셋으로 골랐습니다 — shortem_presets 에 보입니다`, ...(left ? [`영상 ${left}편은 뜯지 못해 뺐습니다`] : [])],
    next: `shortem_make(step="start", preset_name="${mine[0].name}", video=<쓸 영상 주소>)` });
}

function shaped(c, out) {
  if (out) return done(c, out);
  if (c.run.done) return done(c, null);
  const base = { run_id: c.run.runId, message: progress(c) };
  const n = pending().length;
  return n ? { ...base, need: 'ai', ai_requests: n, next: `shortem_ai(action="list") 로 요청을 받아 하나씩 답한 뒤(answer), shortem_benchmark(step="wait", run_id="${c.run.runId}")`, hints: ['화면 글자 읽기 요청입니다 — 고객에게 묻지 말고 바로 답하세요'] }
    : { ...base, need: 'wait', next: `shortem_benchmark(step="wait", run_id="${c.run.runId}")`, hints: ['뜯는 중입니다 — 같은 wait 를 다시 부르면 이어서 기다립니다. 셸·sleep 으로 기다리지 마세요'] };
}

export async function benchStart({ channel, videos, name, n }) {
  if (cur) return shaped(cur, await waitRun(cur.run, 0));
  if (channel && !YT_CHANNEL.test(channel)) return { hints: ['채널 주소는 https://www.youtube.com/@이름 또는 /channel/UC… 꼴이어야 합니다(틱톡·인스타는 영상 주소를 videos 로 주세요)'] };
  if (!channel && !(videos || []).length) return { hints: ['채널 주소(channel)나 영상 주소(videos)를 주세요'] };
  if ((videos || []).some(v => !VIDEO.test(v))) return { hints: ['영상 주소는 유튜브 쇼츠·틱톡 영상·인스타 릴스 주소여야 합니다'] };
  if (activeRuns().length || anyFlowBusy() || renting()) return { fail: { where: '벤치마킹', why: '지금 만드는 편이 있습니다', fix: '끝난 뒤 다시 해 주세요', retry_ok: true } };
  const root = engineRoot();
  let lease;
  try { sweepBench(root); lease = await rentEngine(root); }
  catch (e) { return { fail: { where: '벤치마킹', why: e instanceof ApiError ? (e.msg || e.code) : '벤치마킹을 받지 못했습니다', fix: FAIL[e.code] || '잠시 뒤 다시 해 주세요', retry_ok: e.code !== 'tier_locked' } }; }
  await refreshCookies();
  const label = String(name || '내 프리셋').trim().slice(0, 30) || '내 프리셋';
  const out = ensureDir(homeDir(), path.join('bench', Date.now().toString(36)));
  const args = ['--out', out, '--name', label, '--n', String(n || 3), ...(channel ? ['--channel', channel] : []), ...(videos || []).flatMap(v => ['--video', v])];
  const run = startScript(path.join(root, ...ENTRY), args, { onClose: async () => { wipe(root); await lease.release(); } });
  cur = { run, out, channel: channel || '' };
  return shaped(cur, await waitRun(run, waitMs()));
}

export async function benchWait(runId) {
  if (!cur || (runId && cur.run.runId !== runId)) return { hints: ['기다릴 벤치마킹이 없습니다 — shortem_presets 로 저장됐는지 보세요'] };
  return shaped(cur, await waitRun(cur.run, waitMs()));
}

export const BENCH_TEXT = "채널 벤치마킹(고급반) — 고객이 준 채널의 조회수 높은 쇼츠를 이 PC 에서 받아 화면 틀을 뜯어 내 프리셋으로 저장합니다. step='start'(channel=유튜브 채널 주소 또는 videos=영상 주소 목록, name=프리셋 이름, n=쓸 편 수 1~5) → 응답의 need 가 'ai' 면 shortem_ai 로 답한 뒤 step='wait'(run_id) → need='done' 이면 저장 끝, 응답의 next 로 제작합니다. 기본반이면 fail 의 이유·할 일을 그대로 전합니다.";

export function registerBenchmark(server, reply) {
  server.registerTool('shortem_benchmark', {
    title: '채널 벤치마킹(고급반)', description: BENCH_TEXT,
    inputSchema: { step: z.enum(['start', 'wait']), channel: z.string().max(200).optional(), videos: z.array(z.string().max(300)).max(5).optional(), name: z.string().max(30).optional(), n: z.number().int().min(1).max(5).optional(), run_id: z.string().regex(/^r[0-9a-z]{6,30}$/).optional() },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
  }, async a => {
    const o = a.step === 'wait' ? await benchWait(a.run_id) : await benchStart(a);
    audit('benchmark_step', { step: a.step, need: o.need || '' });
    return reply(o);
  });
}
