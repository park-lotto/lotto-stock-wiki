// 완성본 보내기(server/deliver.js) — 가짜 텔레그램 봇 API 로 연결·확인·영상 보내기·두 번 안 보내기·50MB 넘으면 알림, 드라이브 폴더 복사
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'shortem-deliver-'));
process.env.SHORTEM_HOME = path.join(tmp, 'home');
process.env.SHORTEM_WORK = path.join(tmp, 'work');
process.env.SHORTEM_DRIVE_ROOT = path.join(tmp, 'My Drive');
fs.mkdirSync(process.env.SHORTEM_DRIVE_ROOT, { recursive: true });
const TOKEN = '123456789:AAHfakeTokenForShortemTests_0123456789ab';
const got = { videos: [], messages: [], updates: [] };
let srv;

before(async () => {
  srv = http.createServer(async (req, res) => {
    const ch = []; for await (const d of req) ch.push(d);
    const body = Buffer.concat(ch);
    const m = req.url.match(/^\/bot([^/]+)\/(\w+)$/);
    const send = (o) => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
    if (!m || m[1] !== TOKEN) return send({ ok: false, description: 'Unauthorized' });
    if (m[2] === 'getMe') return send({ ok: true, result: { id: 1, username: 'my_shortem_bot' } });
    if (m[2] === 'getUpdates') return send({ ok: true, result: got.updates });
    if (m[2] === 'sendMessage') { got.messages.push(JSON.parse(body.toString())); return send({ ok: true, result: {} }); }
    if (m[2] === 'sendVideo') { got.videos.push({ bytes: body.length, hasChat: body.includes('777'), hasName: body.includes('final_x.mp4') }); return send({ ok: true, result: {} }); }
    return send({ ok: false, description: 'no method' });
  });
  await new Promise(r => srv.listen(0, '127.0.0.1', r));
  process.env.SHORTEM_TELEGRAM_API = `http://127.0.0.1:${srv.address().port}`;
});
after(() => { srv.close(); fs.rmSync(tmp, { recursive: true, force: true }); });

test('봇 토큰 연결 → 봇에게 말 걸기 전엔 확인 안 됨 → 말 건 뒤 확인', async () => {
  const D = await import('../server/deliver.js');
  assert.equal((await D.linkTelegram('엉터리')).ok, false);
  assert.equal((await D.linkTelegram('123456789:AAHwrongTokenForShortemTests_0123456789ab')).ok, false, '없는 봇');
  const l = await D.linkTelegram(TOKEN);
  assert.equal(l.ok, true); assert.equal(l.bot, 'my_shortem_bot');
  assert.equal(D.deliverStatus().telegram.waiting, true);
  assert.equal((await D.confirmTelegram()).ok, false, '받은 말이 없으면 확인 안 됨');
  got.updates = [{ update_id: 1, message: { chat: { id: 777, type: 'private' }, text: '/start' } }];
  assert.equal((await D.confirmTelegram()).ok, true);
  const st = D.deliverStatus();
  assert.equal(st.telegram.linked, true);
  assert.ok(!JSON.stringify(st).includes(TOKEN), '상태에 토큰 값이 나가지 않는다');
  assert.equal(got.messages.at(-1).chat_id, 777);
});

test('완성본: 텔레그램 영상 + 드라이브 복사, 같은 파일은 두 번 안 보낸다, 다시 만들면 다시', async () => {
  const D = await import('../server/deliver.js');
  D.setDeliver({ drive: true });
  const dir = path.join(process.env.SHORTEM_WORK, '완성본'); fs.mkdirSync(dir, { recursive: true });
  const v = path.join(dir, 'final_x.mp4');
  fs.writeFileSync(v, Buffer.alloc(300000, 7));
  const r = await D.deliverFinal(v, { title: '시험 영상' });
  assert.equal(r.telegram.ok, true); assert.equal(r.telegram.as, 'video'); assert.equal(r.drive.ok, true);
  assert.equal(got.videos.length, 1); assert.ok(got.videos[0].bytes > 300000 && got.videos[0].hasChat && got.videos[0].hasName);
  assert.equal(fs.statSync(path.join(process.env.SHORTEM_DRIVE_ROOT, '숏템완성본', 'final_x.mp4')).size, 300000);
  await D.deliverFinal(v, { title: '시험 영상' });
  assert.equal(got.videos.length, 1, '같은 파일은 다시 안 보낸다');
  fs.writeFileSync(v, Buffer.alloc(310000, 8));        // 다시 만들기(restyle) = 새 파일
  await D.deliverFinal(v, { title: '시험 영상' });
  assert.equal(got.videos.length, 2, '새 완성본은 다시 보낸다');
});

test('50MB 넘는 완성본은 영상 대신 알림 글(봇 한도)', async () => {
  const D = await import('../server/deliver.js');
  const v = path.join(process.env.SHORTEM_WORK, '완성본', 'big.mp4');
  fs.writeFileSync(v, ''); fs.truncateSync(v, D.TG_MAX + 1);
  const n = got.videos.length;
  const r = await D.deliverFinal(v, { title: '큰 영상' });
  assert.equal(r.telegram.as, 'notice'); assert.equal(got.videos.length, n);
  assert.match(got.messages.at(-1).text, /50MB/);
});

test('드라이브 폴더가 없으면 실패를 알리고 텔레그램은 그대로 간다', async () => {
  const D = await import('../server/deliver.js');
  const keep = process.env.SHORTEM_DRIVE_ROOT;
  process.env.SHORTEM_DRIVE_ROOT = path.join(tmp, '없는 폴더');
  const v = path.join(process.env.SHORTEM_WORK, '완성본', 'final_y.mp4');
  fs.writeFileSync(v, Buffer.alloc(1000, 1));
  const r = await D.deliverFinal(v, {});
  assert.equal(r.drive.ok, false); assert.equal(r.telegram.ok, true);
  process.env.SHORTEM_DRIVE_ROOT = keep;
});
