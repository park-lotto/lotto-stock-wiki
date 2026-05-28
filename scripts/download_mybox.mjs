/**
 * 네이버 마이박스 공유 폴더 자동 다운로드
 * - 전체 내려받기 → zip → 압축해제 → 추정이익 변경 파일을 MMDD 이름으로 저장 → zip 삭제
 * 사용: node scripts/download_mybox.mjs
 */
import puppeteer from 'puppeteer';
import path from 'path';
import fs from 'fs';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname   = path.dirname(fileURLToPath(import.meta.url));
const DOWNLOAD_DIR = path.resolve(__dirname, '..', 'raw', '매일 엑셀넣을것');
const MYBOX_URL   = 'https://mybox.naver.com/share/list?shareKey=ChSUOIdlgte24uds4mPeCr7bquxYxsdU3c-mlUY1dYsD';
const ZIP_PATH    = path.join(DOWNLOAD_DIR, '아메리카노.zip');

// 오늘 날짜 MMDD
const now = new Date();
const MMDD = String(now.getMonth() + 1).padStart(2, '0') + String(now.getDate()).padStart(2, '0');

// ── 1. 브라우저 다운로드 ─────────────────────────────────────────────
const browser = await puppeteer.launch({
  headless: true,
  args: ['--no-sandbox', '--lang=ko-KR'],
  defaultViewport: { width: 1280, height: 800 },
});
const page = await browser.newPage();

const client = await page.createCDPSession();
await client.send('Browser.setDownloadBehavior', {
  behavior: 'allow',
  downloadPath: DOWNLOAD_DIR,
  eventsEnabled: true,
});

let downloadDone = false;
let downloadFailed = false;
client.on('Browser.downloadWillBegin', (e) => {
  process.stdout.write(`[1/4] 다운로드 시작: ${e.suggestedFilename}\n`);
});
client.on('Browser.downloadProgress', (e) => {
  if (e.state === 'completed') { downloadDone = true; }
  else if (e.state === 'canceled') { downloadFailed = true; }
});

try {
  await page.goto(MYBOX_URL, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // 전체 내려받기 버튼
  const btnInfo = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button, a')]
      .find(el => el.innerText?.includes('전체 내려받기'));
    if (!btn) return null;
    const r = btn.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (!btnInfo) throw new Error('"전체 내려받기" 버튼을 찾지 못했습니다.');

  await page.mouse.click(btnInfo.x, btnInfo.y);
  await new Promise(r => setTimeout(r, 1200));

  // 드롭다운 "내려받기" 클릭
  const menuInfo = await page.evaluate(() => {
    const item = [...document.querySelectorAll('li, a, button, span, div')]
      .find(el => el.innerText?.trim() === '내려받기');
    if (!item) return null;
    const r = item.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (!menuInfo) throw new Error('"내려받기" 메뉴를 찾지 못했습니다.');

  await page.mouse.click(menuInfo.x, menuInfo.y);

  // 다운로드 완료 대기 (최대 60초)
  for (let i = 0; i < 120; i++) {
    if (downloadDone || downloadFailed) break;
    await new Promise(r => setTimeout(r, 500));
  }
  if (downloadFailed) throw new Error('다운로드가 취소되었습니다.');
  if (!downloadDone) throw new Error('다운로드 완료 신호를 받지 못했습니다 (타임아웃).');

} finally {
  await browser.close();
}

// ── 2. zip 압축 해제 + 추정이익 파일 날짜 이름으로 저장 ────────────────
process.stdout.write(`[2/4] zip 압축 해제 중...\n`);

const pyCode = `
import zipfile, os, sys, shutil

zip_path  = sys.argv[1]
out_dir   = sys.argv[2]
mmdd      = sys.argv[3]

saved = []
with zipfile.ZipFile(zip_path, 'r') as z:
    for info in z.infolist():
        if info.file_size == 0:
            continue
        name = info.filename                      # UTF-8 (flag_bits=2048)
        basename = os.path.basename(name)
        dest = os.path.join(out_dir, basename)
        with z.open(info) as src, open(dest, 'wb') as dst:
            dst.write(src.read())
        saved.append(basename)

# 추정이익 변경(태린이아빠).xlsm → 추정이익 변경(태린이아빠)MMDD.xlsm
for fname in saved:
    if '추정이익 변경' in fname and '크롤링' not in fname:
        stem, ext = os.path.splitext(fname)
        new_name = stem + mmdd + ext
        src_path = os.path.join(out_dir, fname)
        dst_path = os.path.join(out_dir, new_name)
        if os.path.exists(dst_path):
            os.remove(dst_path)
        os.rename(src_path, dst_path)
        print('RENAMED:' + new_name)
    else:
        print('EXTRACTED:' + fname)
`;

const result = execSync(
  `python3 - "${ZIP_PATH}" "${DOWNLOAD_DIR}" "${MMDD}"`,
  { input: pyCode, encoding: 'utf8' }
);
process.stdout.write(result);

// ── 3. zip 삭제 ────────────────────────────────────────────────────────
process.stdout.write(`[3/4] zip 삭제 중...\n`);
fs.unlinkSync(ZIP_PATH);

// ── 4. 결과 확인 ───────────────────────────────────────────────────────
process.stdout.write(`[4/4] 완료 — raw/매일 엑셀넣을것/ 파일 목록:\n`);
const files = fs.readdirSync(DOWNLOAD_DIR)
  .filter(f => f.includes('태린이아빠'))
  .sort();
files.forEach(f => process.stdout.write(`  ✅ ${f}\n`));
