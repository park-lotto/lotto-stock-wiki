/**
 * 웹 접근성 테스트
 * 1. 네이버 마이박스 공유 폴더 — 파일 목록 확인
 * 2. 유튜브 @Taerins_Dad/posts — 최신 포스트 텍스트 추출
 */
import puppeteer from 'puppeteer';

const MYBOX_URL = 'https://mybox.naver.com/share/list?shareKey=ChSUOIdlgte24uds4mPeCr7bquxYxsdU3c-mlUY1dYsD';
const YT_URL    = 'https://www.youtube.com/@Taerins_Dad/posts';

async function testMyBox(browser) {
  console.log('\n=== [1] 네이버 마이박스 테스트 ===');
  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36');

  try {
    console.log('접속 중:', MYBOX_URL);
    const resp = await page.goto(MYBOX_URL, { waitUntil: 'networkidle2', timeout: 30000 });
    console.log('HTTP 상태:', resp.status());

    // 잠깐 기다려 JS 렌더링
    await new Promise(r => setTimeout(r, 3000));

    const title = await page.title();
    console.log('페이지 타이틀:', title);

    // 파일/폴더 아이템 찾기 (다양한 셀렉터 시도)
    const selectors = [
      '.file-item', '.item-name', '[class*="file"]', '[class*="item"]',
      'li[data-type]', '.share-list li', 'table tr', '.list-item'
    ];

    let found = false;
    for (const sel of selectors) {
      const items = await page.$$(sel);
      if (items.length > 0) {
        console.log(`✅ 셀렉터 "${sel}" → ${items.length}개 항목`);
        const texts = await Promise.all(items.slice(0, 5).map(el =>
          el.evaluate(e => e.innerText?.trim().split('\n')[0])
        ));
        texts.filter(Boolean).forEach(t => console.log('  -', t));
        found = true;
        break;
      }
    }

    if (!found) {
      // body 텍스트로 상태 파악
      const bodyText = await page.evaluate(() => document.body?.innerText?.slice(0, 500));
      console.log('⚠️ 파일 목록 셀렉터 미발견. body 텍스트 앞부분:');
      console.log(bodyText);
    }

    // 스크린샷 저장
    await page.screenshot({ path: 'out/test_mybox.png', fullPage: false });
    console.log('스크린샷 저장: out/test_mybox.png');

  } catch (err) {
    console.error('❌ 마이박스 접근 실패:', err.message);
  } finally {
    await page.close();
  }
}

async function testYouTube(browser) {
  console.log('\n=== [2] 유튜브 @Taerins_Dad/posts 테스트 ===');
  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36');

  try {
    console.log('접속 중:', YT_URL);
    const resp = await page.goto(YT_URL, { waitUntil: 'networkidle2', timeout: 30000 });
    console.log('HTTP 상태:', resp.status());

    await new Promise(r => setTimeout(r, 4000));

    const title = await page.title();
    console.log('페이지 타이틀:', title);

    // 커뮤니티 포스트 셀렉터
    const postSelectors = [
      'ytd-post-renderer #content-text',
      'ytd-backstage-post-renderer #content-text',
      '[id="content-text"]',
      'yt-formatted-string#content-text',
    ];

    let found = false;
    for (const sel of postSelectors) {
      const posts = await page.$$(sel);
      if (posts.length > 0) {
        console.log(`✅ 셀렉터 "${sel}" → ${posts.length}개 포스트`);
        const texts = await Promise.all(posts.slice(0, 3).map(el =>
          el.evaluate(e => e.innerText?.trim().slice(0, 200))
        ));
        texts.filter(Boolean).forEach((t, i) => {
          console.log(`\n[포스트 ${i+1}]`);
          console.log(t);
        });
        found = true;
        break;
      }
    }

    if (!found) {
      const bodyText = await page.evaluate(() => document.body?.innerText?.slice(0, 800));
      console.log('⚠️ 포스트 셀렉터 미발견. body 텍스트:');
      console.log(bodyText);
    }

    await page.screenshot({ path: 'out/test_youtube.png', fullPage: false });
    console.log('\n스크린샷 저장: out/test_youtube.png');

  } catch (err) {
    console.error('❌ 유튜브 접근 실패:', err.message);
  } finally {
    await page.close();
  }
}

// main
const browser = await puppeteer.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--lang=ko-KR'],
});

try {
  await testMyBox(browser);
  await testYouTube(browser);
} finally {
  await browser.close();
  console.log('\n=== 테스트 완료 ===');
}
