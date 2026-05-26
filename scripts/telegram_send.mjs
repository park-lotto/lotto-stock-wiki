/**
 * 아침 전략노트 → PNG 캡처 → 텔레그램 전송
 *
 * 사용법:
 *   node scripts/telegram_send.mjs          ← cute 버전 (기본)
 *   node scripts/telegram_send.mjs dark     ← dark 버전
 *   node scripts/telegram_send.mjs both     ← 두 버전 연속 전송
 */

import puppeteer from 'puppeteer';
import { readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ROOT   = join(dirname(fileURLToPath(import.meta.url)), '..');
const style  = process.argv[2] ?? 'cute';   // cute | dark | both

/* ── 설정 로드 ─────────────────────────────────────── */
function loadEnv() {
  const p = join(ROOT, '.env');
  if (!existsSync(p)) {
    console.error('❌ .env 파일이 없습니다. .env.example을 복사해서 만드세요.');
    process.exit(1);
  }
  const cfg = {};
  readFileSync(p, 'utf8').split('\n').forEach(line => {
    const [k, ...v] = line.split('=');
    if (k && !k.startsWith('#') && v.length) cfg[k.trim()] = v.join('=').trim();
  });
  return cfg;
}

/* ── HTML → PNG 스크린샷 ───────────────────────────── */
async function screenshot(htmlFile, pngFile) {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 840, height: 900, deviceScaleFactor: 2 });
    await page.goto(`file:///${htmlFile.replace(/\\/g, '/')}`, {
      waitUntil: 'networkidle0',
      timeout: 30000,
    });
    // 폰트 로딩 대기
    await page.evaluateHandle('document.fonts.ready');
    await page.screenshot({ path: pngFile, fullPage: true });
    return pngFile;
  } finally {
    await browser.close();
  }
}

/* ── 텔레그램 전송 ─────────────────────────────────── */
async function sendToTelegram(token, chatId, pngFile, caption) {
  const form = new FormData();
  form.append('chat_id',  chatId);
  form.append('caption',  caption);
  form.append('parse_mode', 'HTML');

  const blob = new Blob([readFileSync(pngFile)], { type: 'image/png' });
  form.append('photo', blob, 'morning_note.png');

  const res  = await fetch(`https://api.telegram.org/bot${token}/sendPhoto`, {
    method: 'POST', body: form,
  });
  const json = await res.json();
  if (!json.ok) throw new Error(json.description);
  return json.result.message_id;
}

/* ── 메인 ─────────────────────────────────────────── */
async function run(ver) {
  const htmlFile = join(ROOT, 'out', `morning_note_${ver}.html`);
  const pngFile  = join(ROOT, 'out', `morning_note_${ver}_send.png`);

  if (!existsSync(htmlFile)) {
    console.error(`❌ 파일 없음: ${htmlFile}`);
    return;
  }

  console.log(`\n📸 [${ver}] 스크린샷 생성 중...`);
  await screenshot(htmlFile, pngFile);
  console.log(`   ✅ PNG 저장 → out/morning_note_${ver}_send.png`);

  const { BOT_TOKEN, CHAT_ID } = loadEnv();
  if (!BOT_TOKEN || BOT_TOKEN.includes('여기에') || !CHAT_ID) {
    console.error('❌ .env의 BOT_TOKEN / CHAT_ID를 먼저 설정하세요.');
    return;
  }

  const today   = new Date().toLocaleDateString('ko-KR', { year:'numeric', month:'long', day:'numeric', weekday:'short' });
  const caption =
    `📈 <b>오늘의 전략</b> — ${today}\n` +
    `<i>STOCK BRAIN · 로또의 주식인사이트</i>\n` +
    `\n데이터가 판단하게 만든다 🔴`;

  console.log(`📤 텔레그램 전송 중...`);
  const msgId = await sendToTelegram(BOT_TOKEN, CHAT_ID, pngFile, caption);
  console.log(`   ✅ 전송 완료 (message_id: ${msgId})`);
}

async function main() {
  const { BOT_TOKEN, CHAT_ID } = loadEnv();

  // 간단한 검증
  if (!BOT_TOKEN || BOT_TOKEN.includes('여기에')) {
    console.error('❌ .env의 BOT_TOKEN을 설정하세요.');
    console.error('   방법: BotFather → /newbot → 토큰 복사 → .env에 BOT_TOKEN=토큰 입력');
    process.exit(1);
  }
  if (!CHAT_ID) {
    console.error('❌ .env의 CHAT_ID를 설정하세요.');
    console.error('   방법: node scripts/get_chat_id.mjs 실행 후 출력된 ID 사용');
    process.exit(1);
  }

  if (style === 'both') {
    await run('cute');
    await run('dark');
  } else {
    await run(style);
  }

  console.log('\n🎉 완료!\n');
}

main().catch(err => {
  console.error('❌ 오류:', err.message);
  process.exit(1);
});
