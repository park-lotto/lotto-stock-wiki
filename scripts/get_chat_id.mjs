/**
 * 텔레그램 Chat ID 확인 스크립트
 * 사용법:
 *   1. 텔레그램에서 내 봇에 아무 메시지나 보내기 (예: "안녕")
 *   2. node scripts/get_chat_id.mjs 실행
 *   3. 출력된 CHAT_ID를 .env에 저장
 */

import { readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

function loadEnv() {
  const p = join(ROOT, '.env');
  if (!existsSync(p)) {
    console.error('❌ .env 파일이 없습니다. .env.example을 복사해서 .env로 만드세요.');
    process.exit(1);
  }
  const cfg = {};
  readFileSync(p, 'utf8').split('\n').forEach(line => {
    const [k, ...v] = line.split('=');
    if (k && !k.startsWith('#') && v.length) cfg[k.trim()] = v.join('=').trim();
  });
  return cfg;
}

const { BOT_TOKEN } = loadEnv();
if (!BOT_TOKEN || BOT_TOKEN.includes('여기에')) {
  console.error('❌ .env의 BOT_TOKEN을 먼저 설정하세요.');
  process.exit(1);
}

console.log('🔍 텔레그램 업데이트 확인 중...\n');
const res  = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/getUpdates`);
const json = await res.json();

if (!json.ok) {
  console.error('❌ API 오류:', json.description);
  process.exit(1);
}

if (!json.result.length) {
  console.log('⚠️  메시지가 없습니다.');
  console.log('👉 텔레그램에서 내 봇에 "안녕" 이라고 보낸 뒤 다시 실행하세요.');
  process.exit(0);
}

const last    = json.result[json.result.length - 1];
const chat    = last.message?.chat ?? last.channel_post?.chat;
const chatId  = chat?.id;
const title   = chat?.username ?? chat?.title ?? chat?.first_name ?? '(없음)';

console.log(`✅ Chat ID : ${chatId}`);
console.log(`   이름    : ${title}`);
console.log(`\n👉 .env 파일에 아래 줄 추가하세요:`);
console.log(`   CHAT_ID=${chatId}`);
