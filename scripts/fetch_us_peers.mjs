#!/usr/bin/env node
/**
 * fetch_us_peers.mjs
 * 미국 페어 종목 전일 등락 자동 수집
 * 실행: node scripts/fetch_us_peers.mjs
 * 출력: raw/market/YYYYMMDD_us_peers.md  ← Claude ingest용
 *       raw/market/YYYYMMDD_us_peers.json ← 원본 보관
 */

import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 섹터별 미국 페어 매핑
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const SECTOR_PEERS = {
  '반도체': [
    { ticker: 'NVDA', name: '엔비디아',  note: 'HBM 수요 핵심 → SK하이닉스' },
    { ticker: 'AMAT', name: 'AMAT',      note: '전공정 장비 → 한미반도체·원익IPS' },
    { ticker: 'MU',   name: '마이크론',  note: '메모리 경쟁사 → 사이클 확인' },
    { ticker: 'TSM',  name: 'TSMC',      note: '파운드리 → DB하이텍' },
  ],
  '로봇': [
    { ticker: 'TSLA', name: '테슬라',    note: '옵티머스 → 레인보우로보틱스·에스비비테크' },
    { ticker: 'ABBNY', name: 'ABB',      note: '산업용 로봇 → 현대로보틱스' },
    { ticker: 'ISRG', name: 'Intuitive', note: '의료로봇 → 큐렉소·고영' },
  ],
  '원전': [
    { ticker: 'CEG',  name: 'Constellation', note: '미국 최대 원전 → 두산에너빌리티' },
    { ticker: 'VST',  name: 'Vistra',     note: 'AI 전력 수요 → 한전기술' },
    { ticker: 'CCJ',  name: 'Cameco',     note: '우라늄 → 원전 섹터 전반' },
  ],
  'LNG_조선': [
    { ticker: 'LNG',  name: 'Cheniere',   note: 'LNG 수출 → HD현대중공업·한화오션' },
    { ticker: 'CQP',  name: 'CQP',        note: 'LNG 파트너십 → 삼성중공업' },
  ],
  '방산': [
    { ticker: 'LMT',  name: 'Lockheed',   note: 'F-35·미사일 → 한화에어로스페이스' },
    { ticker: 'RTX',  name: 'Raytheon',   note: '방공·유도탄 → LIG넥스원' },
    { ticker: 'NOC',  name: 'Northrop',   note: 'B-21·우주 → 한국항공우주' },
  ],
  'ESS_2차전지': [
    { ticker: 'TSLA', name: '테슬라',     note: 'ESS·EV 배터리 → LG에너지솔루션' },
    { ticker: 'ENPH', name: 'Enphase',    note: '가정용 ESS → 솔라엣지 커플링' },
    { ticker: 'FSLR', name: 'First Solar', note: '태양광 → 한화솔루션' },
  ],
  '전력기기': [
    { ticker: 'ETN',  name: 'Eaton',      note: '전력 관리 → 현대일렉트릭·효성중공업' },
    { ticker: 'GEV',  name: 'GE Vernova', note: '변압기·그리드 → 일진전기' },
    { ticker: 'EMR',  name: 'Emerson',    note: '전력 자동화 → LS일렉트릭' },
  ],
};

// 지수
const INDICES = [
  { ticker: '^IXIC', name: '나스닥' },
  { ticker: '^GSPC', name: 'S&P500' },
  { ticker: '^SOX',  name: '필라델피아반도체' },
  { ticker: '^VIX',  name: 'VIX' },
];

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Yahoo Finance API 호출
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://finance.yahoo.com/',
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`파싱 실패 (${res.statusCode})`)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(12000, () => { req.destroy(); reject(new Error('타임아웃')); });
  });
}

async function getQuote(ticker) {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1d&range=7d`;
    const data = await fetchJSON(url);
    const result = data?.chart?.result?.[0];
    if (!result) return { ticker, error: 'No data' };

    const closes = (result.indicators?.quote?.[0]?.close || []).filter(v => v != null);
    if (closes.length < 2) return { ticker, error: '데이터 부족' };

    const last  = closes[closes.length - 1];
    const prev  = closes[closes.length - 2];
    const ago5  = closes.length >= 6 ? closes[closes.length - 6] : closes[0];

    const chg1d = ((last - prev) / prev) * 100;
    const chg5d = ((last - ago5) / ago5) * 100;

    return {
      ticker,
      price:    last.toFixed(2),
      chg1d:    parseFloat(chg1d.toFixed(2)),
      chg5d:    parseFloat(chg5d.toFixed(2)),
      dir1d:    chg1d >=  0.5 ? '↑' : chg1d <= -0.5 ? '↓' : '→',
      dir5d:    chg5d >=  1.5 ? '↑강세' : chg5d <= -1.5 ? '↓약세' : '→횡보',
    };
  } catch (e) {
    return { ticker, error: e.message };
  }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 시장 분위기 판단
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function getMood(nasdaqChg, vixVal) {
  if (nasdaqChg >  1.0 && vixVal < 20) return '🟢 위험선호 — 공격적 진입 유효';
  if (nasdaqChg >  0   && vixVal < 25) return '🟡 완만한 상승 — 정상 진입';
  if (nasdaqChg < -1.5 || vixVal > 28) return '🔴 위험회피 — 포지션 축소';
  if (nasdaqChg < -0.5)                return '🟠 하락 — 선별적 접근';
  return '🟡 혼조 — 섹터별 차별화';
}

function fmt(chg) {
  return (chg >= 0 ? '+' : '') + chg + '%';
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 마크다운 생성 (Claude ingest용)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function buildMarkdown(date, indices, sectors) {
  const nasdaq = indices.find(i => i.name === '나스닥') || {};
  const sox    = indices.find(i => i.name === '필라델피아반도체') || {};
  const vix    = indices.find(i => i.name === 'VIX') || {};
  const mood   = getMood(nasdaq.chg1d || 0, parseFloat(vix.price || '20'));

  let md = `# 미국장 새벽 분위기 — ${date}\n\n`;
  md += `> **종합 판단**: ${mood}\n\n`;
  md += `---\n\n`;

  // 지수
  md += `## 주요 지수\n\n`;
  md += `| 지수 | 전일등락 | 5일방향 |\n|------|--------|--------|\n`;
  for (const idx of indices) {
    if (idx.error) md += `| ${idx.name} | ❌ 수집실패 | — |\n`;
    else           md += `| ${idx.name} | ${fmt(idx.chg1d)} | ${idx.dir5d} |\n`;
  }
  md += `\n`;

  // 섹터별 페어
  md += `## 섹터별 미국 페어\n\n`;
  for (const [sector, peers] of Object.entries(sectors)) {
    // 섹터 대표 방향 요약 (첫 번째 종목 기준)
    const lead = peers.find(p => !p.error);
    const sectorDir = lead ? (lead.chg1d >= 1 ? '🔴 상승선행' : lead.chg1d <= -1 ? '⚫ 하락선행' : '🟡 보합') : '—';
    md += `### ${sector} — ${sectorDir}\n\n`;
    md += `| 종목 | 전일등락 | 5일방향 | 국내 연결 |\n|------|--------|--------|----------|\n`;
    for (const p of peers) {
      if (p.error) md += `| ${p.name}(${p.ticker}) | ❌ | — | ${p.note} |\n`;
      else         md += `| ${p.name}(${p.ticker}) | ${fmt(p.chg1d)} | ${p.dir5d} | ${p.note} |\n`;
    }
    md += `\n`;
  }

  // 인사이트 힌트 (Claude가 인사이트 작성 시 참고)
  md += `## 오늘 주목할 움직임\n\n`;
  const notable = [];
  for (const [sector, peers] of Object.entries(sectors)) {
    for (const p of peers) {
      if (!p.error && Math.abs(p.chg1d) >= 2) {
        notable.push(`- **${sector}** — ${p.name}(${p.ticker}) ${fmt(p.chg1d)}: ${p.note}`);
      }
    }
  }
  if (notable.length) md += notable.join('\n') + '\n';
  else md += `- 전반적으로 ±2% 이내 조용한 장\n`;

  return md;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 메인
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async function main() {
  const now     = new Date();
  const dateStr = now.toISOString().slice(0,10).replace(/-/g,'');
  const dateDisp = now.toISOString().slice(0,10);

  console.log(`\n🌙 미국장 데이터 수집 — ${dateDisp}`);
  console.log(`${'─'.repeat(44)}`);

  // 중복 제거한 전체 티커 목록
  const allTickers = [...new Set([
    ...INDICES.map(i => i.ticker),
    ...Object.values(SECTOR_PEERS).flatMap(s => s.map(p => p.ticker)),
  ])];

  console.log(`📡 ${allTickers.length}개 티커 조회 시작...\n`);

  // 순차 요청 (Rate limit 방지)
  const cache = {};
  for (const ticker of allTickers) {
    process.stdout.write(`  ${ticker.padEnd(8)}`);
    const q = await getQuote(ticker);
    cache[ticker] = q;
    if (q.error) console.log(`❌  ${q.error}`);
    else         console.log(`${q.dir1d}  ${fmt(q.chg1d).padStart(7)}  (5일: ${q.dir5d})`);
    await new Promise(r => setTimeout(r, 350)); // 야후 Rate limit 방지
  }

  // 데이터 조립
  const indicesData = INDICES.map(idx => ({ ...idx, ...(cache[idx.ticker] || { error: '수집 실패' }) }));
  const sectorsData = {};
  for (const [sec, peers] of Object.entries(SECTOR_PEERS)) {
    sectorsData[sec] = peers.map(p => ({ ...p, ...(cache[p.ticker] || { error: '수집 실패' }) }));
  }

  // 저장 경로
  const marketDir = path.join(ROOT, 'raw', 'market');
  if (!fs.existsSync(marketDir)) fs.mkdirSync(marketDir, { recursive: true });

  const jsonPath = path.join(marketDir, `${dateStr}_us_peers.json`);
  const mdPath   = path.join(marketDir, `${dateStr}_us_peers.md`);

  fs.writeFileSync(jsonPath, JSON.stringify({ date: dateDisp, indices: indicesData, sectors: sectorsData }, null, 2), 'utf8');
  fs.writeFileSync(mdPath, buildMarkdown(dateDisp, indicesData, sectorsData), 'utf8');

  // 요약 출력
  console.log(`\n${'─'.repeat(44)}`);
  console.log(`✅ 저장 완료`);
  console.log(`   MD  → raw/market/${dateStr}_us_peers.md`);
  console.log(`   JSON→ raw/market/${dateStr}_us_peers.json`);

  console.log(`\n📋 지수 요약:`);
  for (const idx of indicesData) {
    if (!idx.error) console.log(`   ${idx.name.padEnd(12)} ${fmt(idx.chg1d)}`);
  }

  const nasdaq = indicesData.find(i => i.name === '나스닥') || {};
  const vix    = indicesData.find(i => i.name === 'VIX') || {};
  console.log(`\n   → ${getMood(nasdaq.chg1d || 0, parseFloat(vix.price || '20'))}`);
  console.log(`\n💡 /ingest raw/market/${dateStr}_us_peers.md 로 위키에 반영하세요\n`);
}

main().catch(err => {
  console.error(`\n❌ 오류: ${err.message}`);
  process.exit(1);
});
