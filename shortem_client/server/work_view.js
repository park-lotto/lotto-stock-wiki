// 숏템 작업실 탭(관제 291, 사장님 10-30 "설정·진행현황·원본 찾기를 한 페이지 탭으로") — 진행현황·원본 찾기 탭이 보여 줄 것을 모은다.
//   읽기만 한다(판단 0). 단계·멈춤·안내 = flow_driver.shapeFlow 그대로, 원본 후보 = 실행기가 job 에 남긴 파일, 판정 = AI 요청 폴더의 답.
//   판정을 후보에 짝짓는 표식은 서버 지시서가 질문에 붙인 meta(flow._rv) — 여기서 새로 정하지 않는다.
import fs from 'node:fs';
import path from 'node:path';
import { flowRoot, loadFlow, shapeFlow, FLOW_SID_RE } from './flow_driver.js';
import { aiRootDir } from './engine_bridge.js';
import { jail } from './paths.js';

const rj = p => { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return null; } };
const mtime = p => { try { return fs.statSync(p).mtimeMs; } catch { return 0; } };
const ls = d => { try { return fs.readdirSync(d); } catch { return []; } };
const OF_TAGS = ['of_judge', 'of_peer', 'of_find', 'of_verify'];
const baseTag = t => String(t || '').replace(/^s\d+:/, '');   // 소재 여럿 동시 찾기(flow.f_of_dual)는 's1:' 를 앞에 붙인다

// 화면에 내지 않는 칸(Claude 에게 주는 다음 할 일·도움말)
function shape(f) {
  const { next, hints, ...s } = shapeFlow(f);
  return s;
}

export function flowList(limit = 30) {
  return ls(flowRoot()).filter(sid => FLOW_SID_RE.test(sid)).map(sid => {
    const f = loadFlow(sid);
    if (!f) return null;
    const s = shape(f);
    return { sid, preset: f.preset || null, video: f.video || null, title: f.title || null, created: f.created || 0,
      updated: mtime(path.join(flowRoot(), sid, 'flow.json')), need: s.need, message: s.message, stage: s.stage || null, step: s.step || 0, step_total: s.step_total || 0 };
  }).filter(Boolean).sort((a, b) => b.updated - a.updated).slice(0, limit);
}

// AI 판정 요청(시간순) — 질문 글은 빼고 이름·그림·답만
function reviews(sid) {
  const root = path.join(aiRootDir(), 'flow_' + sid);
  return ls(root).map(id => {
    const d = path.join(root, id);
    const q = rj(path.join(d, 'request.json'));
    if (!q) return null;
    const a = rj(path.join(d, 'answer.json'));
    return { id, tag: baseTag(q.tag), part: /^s\d+:/.test(String(q.tag)) ? String(q.tag).split(':')[0] : '', at: Math.round((q.made_at || 0) * 1000),
      images: (q.parts || []).filter(p => p.kind === 'image').map(p => `fa/${sid}/${encodeURIComponent(id)}/${encodeURIComponent(p.file)}`),
      meta: q.meta || null, answered: !!a, answer_at: a ? mtime(path.join(d, 'answer.json')) : 0,
      answer: a ? { same: a.same, picks: a.picks, why: typeof a.why === 'string' ? a.why.slice(0, 300) : undefined } : null };
  }).filter(Boolean).sort((x, y) => x.at - y.at);
}

// job 안 원본 찾기 폴더 — 한 소재면 job/origin_foreign, 여럿이면 job/<sub>/origin_foreign
function originDirs(job) {
  const out = [];
  if (fs.existsSync(path.join(job, 'origin_foreign'))) out.push('');
  for (const s of ls(job)) if (s !== 'origin_foreign' && fs.existsSync(path.join(job, s, 'origin_foreign'))) out.push(s);
  return out;
}

function origin(sid, rv) {
  const job = path.join(flowRoot(), sid, 'job');
  const img = rel => `fl/${sid}/${rel.split('/').map(encodeURIComponent).join('/')}`;
  return originDirs(job).map(sub => {
    const pre = sub ? sub + '/' : '';
    const od = path.join(job, sub, 'origin_foreign');
    const files = ls(od);
    const seeds = files.filter(n => /^seed_.*\.jpg$/.test(n)).sort().map(n => img(`${pre}origin_foreign/${n}`));
    const rounds = ['lens', 'peers', 'find'].map(mode => {
      const cs = rj(path.join(od, `cands_${mode}.json`));
      if (!Array.isArray(cs)) return null;
      const mine = r => r.meta && (r.meta.sub ?? '') === sub;   // 소재 여럿 동시 찾기면 서버가 meta.sub 로 폴더를 알려 준다(flow._slot_items)
      const j = rv.filter(r => (r.tag === 'of_judge' || r.tag === 'of_peer') && mine(r) && r.meta.mode === mode && r.answered).pop();
      const ok = new Set(((j && j.answer && (j.answer.same || j.answer.picks)) || []).map(Number));
      const legacy = !j && rv.some(r => (r.tag === 'of_judge' || r.tag === 'of_peer') && !r.meta && r.answered);   // meta 를 붙이기 전(10-30 전) 기록 — 짝을 지을 수 없다
      return { mode, at: mtime(path.join(od, `cands_${mode}.json`)), judged: !!j, legacy, why: j && j.answer ? j.answer.why : undefined,
        cands: cs.map(c => ({ n: c.n, platform: c.platform, title: String(c.title || '').slice(0, 80), views: c.views ?? null, dur: c.dur ?? null, korean: !!c.korean,
          thumb: files.includes(`thumb_${c.id}.jpg`) ? img(`${pre}origin_foreign/thumb_${c.id}.jpg`) : null, same: j ? ok.has(Number(c.n)) : null })) };
    }).filter(Boolean).sort((a, b) => a.at - b.at);
    const vr = rv.filter(r => r.tag === 'of_verify' && (!r.meta || (r.meta.sub ?? '') === sub));
    const verify = vr.map(r => {
      const rows = (r.meta && r.meta.rows) || [];
      const ok = new Set((r.answer && r.answer.same) || []);
      return { at: r.at, answered: r.answered, why: r.answer ? r.answer.why : undefined, images: r.images,
        rows: rows.map((vid, k) => ({ vid: String(vid).slice(0, 4) + '…', ok: r.answered ? ok.has(k + 1) : null })) };
    });
    const sheets = files.filter(n => /^judge_\d+\.jpg$/.test(n)).sort().map(n => img(`${pre}origin_foreign/${n}`));   // AI 가 본 후보 판(후보 썸네일 파일이 없는 이전 기록은 이걸 보여 준다)
    return { part: sub, seeds, rounds, verify, sheets };
  });
}

export function flowView(sid) {
  const f = loadFlow(sid);
  if (!f) return null;
  const rv = reviews(sid);
  return { ...shape(f), preset: f.preset || null, video: f.video || null, created: f.created || 0,
    waiting_ai: rv.filter(r => !r.answered).map(r => r.tag), reviews: rv.map(({ meta, ...r }) => r), origin: origin(sid, rv) };
}

// 그림 파일 — job 안(fl/) · AI 요청 폴더 안(fa/)만, jpg/png 만
export function viewFile(kind, sid, rel) {
  if (!FLOW_SID_RE.test(String(sid || '')) || !/\.(jpe?g|png)$/i.test(rel)) return null;
  try {
    if (kind === 'fl') return jail(path.join(flowRoot(), sid, 'job'), rel);
    if (kind === 'fa') return jail(path.join(aiRootDir(), 'flow_' + sid), rel);
  } catch { return null; }
  return null;
}
