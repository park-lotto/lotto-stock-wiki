/**
 * 단순 HTML → PNG 스크린샷 유틸
 * 사용법: node scripts/screenshot.mjs <html파일> [출력png파일] [너비]
 */
import puppeteer from 'puppeteer';
import { existsSync } from 'fs';
import { join, dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const ROOT   = join(dirname(fileURLToPath(import.meta.url)), '..');
const input  = process.argv[2];
const output = process.argv[3] ?? input.replace('.html', '.png');
const width  = parseInt(process.argv[4] ?? '1240');

if (!input || !existsSync(resolve(ROOT, input))) {
  console.error('❌ 파일을 지정하세요: node scripts/screenshot.mjs out/파일.html');
  process.exit(1);
}

const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
const page    = await browser.newPage();
await page.setViewport({ width, height: 900, deviceScaleFactor: 2 });
await page.goto(`file:///${resolve(ROOT, input).replace(/\\/g, '/')}`, { waitUntil: 'networkidle0' });
await page.evaluateHandle('document.fonts.ready');
await page.screenshot({ path: resolve(ROOT, output), fullPage: true });
await browser.close();
console.log(`✅ 저장: ${output}`);
