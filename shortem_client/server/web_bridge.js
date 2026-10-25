// 웹 설정 화면(서버 /claude/studio) ↔ 이 PC 다리(관제 266, 사장님 10-25 '서버는 화면만 빌려주고 다 회원 PC 에서').
//   완성본 재생·시간 줄·캡컷 내보내기는 이 PC 파일이라 서버를 거치지 않는다 — 고객 브라우저가 127.0.0.1 로 직접 부른다.
//   ★받는 곳: 우리 웹 주소(Origin)에서 온 요청만(브라우저가 Origin 을 바꿀 수 없다). 다른 사이트는 403.
//   ★여는 것: 완성본 목록·영상·시간 줄뿐(읽기). 바꾸는 일(고치기)은 Claude 가 지시를 받아 한다 — 여기서 엔진을 돌리지 않는다.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { workDir } from './paths.js';
import { baseUrl } from './api.js';
import { videos, send, serveFile } from './local_ui.js';

export const BRIDGE_PORT = Number(process.env.SHORTEM_BRIDGE_PORT || 17842);
const VERSION = 1;

export function webOrigins() {
  const out = new Set(['https://stmaker.kr', 'https://www.stmaker.kr']);   // 라이브 주소(10-25 shoppingshorts.duckdns.org → stmaker.kr 로 넘어간다)
  try { out.add(new URL(baseUrl()).origin); } catch { /* 주소 꼴이 아니면 기본만 */ }
  for (const o of String(process.env.SHORTEM_WEB_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean)) out.add(o);
  return out;
}

function cors(origin) {
  return { 'Access-Control-Allow-Origin': origin, Vary: 'Origin', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Private-Network': 'true', 'Access-Control-Max-Age': '600' };
}

// 완성본 시간 줄 — 그 편 소재 폴더의 timeline.json(엔진이 만든 것) 그대로. 없으면 빈 줄(화면은 미리보기 장면으로 그린다)
function timelineOf(name) {
  const v = videos().find(x => x.name === name);
  if (!v) return null;
  let meta = {};
  try { meta = JSON.parse(fs.readFileSync(path.join(workDir(), '완성본', name + '.json'), 'utf8')); } catch { /* 표식 없음 */ }
  let beats = [];
  try { beats = JSON.parse(fs.readFileSync(path.join(meta.topic_dir || '', 'timeline.json'), 'utf8')).beats || []; } catch { /* 없음 */ }
  return { name, title: v.title, scenes: beats.map((b, i) => ({ i, start: +b.t0 || 0, end: (+b.t0 || 0) + (+b.dur || 0), caption: (b.caption_lines || [b.narration || '']).join(' ') })) };
}

async function route(req, res) {
  const origin = String(req.headers.origin || '');
  const host = String(req.headers.host || '');
  if (host !== `127.0.0.1:${BRIDGE_PORT}` && host !== `localhost:${BRIDGE_PORT}`) return send(res, 403, { error: '이 PC 에서만' });
  const u = new URL(req.url, `http://${host}`);
  const isVideo = u.pathname.startsWith('/bridge/v/') && req.method === 'GET';
  // 영상(<video src>)은 브라우저가 Origin 을 안 붙일 수 있다 — 대신 완성본 목록에 있는 파일만, 읽기만
  if (!isVideo && !webOrigins().has(origin)) return send(res, 403, { error: '숏템 웹 화면에서만 부를 수 있습니다' });
  const h = origin ? cors(origin) : {};
  if (req.method === 'OPTIONS') { res.writeHead(204, h); return res.end(); }
  if (u.pathname === '/bridge/hello') return send(res, 200, { ok: true, version: VERSION }, undefined, h);
  if (u.pathname === '/bridge/videos') return send(res, 200, { ok: true, videos: videos().map(v => ({ name: v.name, title: v.title, at: v.at })) }, undefined, h);
  if (u.pathname.startsWith('/bridge/timeline/')) {
    const t = timelineOf(decodeURIComponent(u.pathname.slice('/bridge/timeline/'.length)));
    return send(res, t ? 200 : 404, t || { error: '없음' }, undefined, h);
  }
  if (isVideo) {
    const name = decodeURIComponent(u.pathname.slice('/bridge/v/'.length));
    if (!videos().some(v => v.name === name)) return send(res, 404, { error: '없음' });
    return serveFile(req, res, path.join(workDir(), '완성본', name), 'video/mp4');
  }
  if (u.pathname === '/bridge/capcut' && req.method === 'POST') {
    // 캡컷 내보내기 — 회원 PC 엔진에 캡컷 묶음 만들기가 아직 없다(서버 숏템메이커에만 있음). 붙이기 전까지 이유를 그대로 돌려준다
    return send(res, 200, { ok: false, why: '캡컷 내보내기는 회원 PC 엔진에 붙이는 중입니다' }, undefined, h);
  }
  return send(res, 404, { error: '없음' }, undefined, h);
}

let server = null;
export async function startBridge() {
  if (server) return { port: BRIDGE_PORT };
  const s = http.createServer((req, res) => { route(req, res).catch(e => { try { send(res, 500, { error: String(e && e.message || e) }); } catch { /* 이미 보냄 */ } }); });
  try {
    await new Promise((resolve, reject) => { s.once('error', reject); s.listen(BRIDGE_PORT, '127.0.0.1', resolve); });
  } catch (e) {
    return { error: e && e.code === 'EADDRINUSE' ? '다리 자리가 이미 쓰이는 중' : String(e && e.message || e) };
  }
  s.unref();   // MCP 프로세스를 붙잡지 않는다
  server = s;
  return { port: BRIDGE_PORT };
}
