// update_market_data.js — 매일 07:00 KST 자동 실행
// Yahoo Finance API(무인증)로 VIX·DXY·금리·미국증시 수집 → wiki + data/ 업데이트

const https = require('https');
const fs = require('fs');
const path = require('path');

const BASE = path.dirname(require.main.filename);

function today() {
  const d = new Date();
  const kst = new Date(d.getTime() + 9 * 3600 * 1000);
  return kst.toISOString().slice(0, 10);
}

function fetchYahoo(symbol) {
  return new Promise((resolve, reject) => {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=5d`;
    const req = https.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0', Accept: 'application/json' }
    }, res => {
      let raw = '';
      res.on('data', c => raw += c);
      res.on('end', () => {
        try {
          const j = JSON.parse(raw);
          const closes = j.chart.result[0].indicators.quote[0].close.filter(v => v != null);
          if (closes.length < 2) throw new Error('데이터 부족');
          const cur = closes.at(-1), prev = closes.at(-2);
          resolve({ cur, prev, chg: cur - prev, pct: (cur - prev) / prev * 100 });
        } catch (e) { reject(new Error(`${symbol}: ${e.message}`)); }
      });
    });
    req.on('error', e => reject(new Error(`${symbol}: ${e.message}`)));
    req.setTimeout(10000, () => { req.destroy(); reject(new Error(`${symbol}: timeout`)); });
  });
}

const f2 = n => n == null ? '—' : n.toFixed(2);
const f1 = n => n == null ? '—' : n.toFixed(1);
const pct = n => n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
const bp  = n => n == null ? '—' : `${n >= 0 ? '+' : ''}${Math.round(n * 100)}bp`;

// 마크다운 테이블에 행 추가 (헤더 앵커로 위치 탐색, maxRows 초과 시 가장 오래된 행 삭제)
function appendTableRow(content, anchorText, newRow, maxRows = 7) {
  const lines = content.split('\n');
  const anchorIdx = lines.findIndex(l => l.includes(anchorText));
  if (anchorIdx === -1) return content;
  let sepIdx = anchorIdx + 1;
  while (sepIdx < lines.length && !lines[sepIdx].match(/^\|[-| ]+\|/)) sepIdx++;
  if (sepIdx >= lines.length) return content;
  lines.splice(sepIdx + 1, 0, newRow);
  let count = 0;
  for (let i = sepIdx + 1; i < lines.length; i++) {
    if (!lines[i].startsWith('|') || lines[i].match(/^\|[-| ]+\|/)) break;
    count++;
    if (count > maxRows) { lines.splice(i, 1); break; }
  }
  return lines.join('\n');
}

function sigVIX(v)  { return v < 15 ? '🟢 극저 Risk-On' : v < 20 ? '🟢 안정 Risk-On' : v < 25 ? '🟡 주의' : v < 30 ? '🟠 불안' : '🔴 공포 Risk-Off'; }
function sigDXY(v)  { return v < 95 ? '🟢 달러 약세 (위험자산 유리)' : v < 100 ? '🟡 달러 약세권' : v < 103 ? '🟠 달러 강세' : '🔴 달러 강세 (위험자산 압박)'; }
function sigTNX(bp) { return bp == null ? '—' : bp > 10 ? '🔴 급등 (성장주 압박)' : bp > 5 ? '🟠 상승' : bp < -10 ? '🟢 급락 (주식 지지)' : bp < -5 ? '🟡 하락' : '→ 안정'; }
function mode(vix, dxy) {
  if (vix == null || dxy == null) return { name: '판단 대기', icon: '❓', kosp: '대기', kospI: '❓' };
  if (vix < 20 && dxy < 100) return { name: 'Risk-On',     icon: '🟢', kosp: '상승',    kospI: '🔴' };
  if (vix > 25 || dxy > 103) return { name: 'Risk-Off',    icon: '🔴', kosp: '하락',    kospI: '⚫' };
  return                             { name: '중립',         icon: '🟡', kosp: '보합',    kospI: '🟠' };
}

async function main() {
  const DATE = today();
  console.log(`\n📡 [${new Date().toISOString()}] 시장 데이터 수집 시작`);

  const syms = {
    // L1 — 글로벌 유동성
    vix: '^VIX', dxy: 'DX-Y.NYB', tnx: '^TNX', usdkrw: 'KRW=X',
    // L2 — 미국 주요 지수·ETF
    nasdaq: '^IXIC', sp500: '^GSPC', dow: '^DJI', sox: '^SOX',
    smh: 'SMH', qqq: 'QQQ', xlk: 'XLK', xli: 'XLI', xlv: 'XLV',
    // L2 페어 — 반도체/메모리
    nvda: 'NVDA', mu: 'MU', avgo: 'AVGO', amd: 'AMD',
    // L2 페어 — 반도체장비
    amat: 'AMAT', lrcx: 'LRCX',
    // L2 페어 — PCB/기판
    mrvl: 'MRVL',
    // L2 페어 — 우주/방산
    rklb: 'RKLB', lmt: 'LMT',
    // L2 페어 — 전력인프라
    etn: 'ETN', vrt: 'VRT',
    // L2 페어 — 비만치료제
    lly: 'LLY', nvo: 'NVO',
    // L2 페어 — 전기차/배터리
    tsla: 'TSLA',
    // L2 페어 — 양자보안
    ionq: 'IONQ', qbts: 'QBTS',
    // L2 페어 — 신재생/연료전지
    be: 'BE',
    // L2 페어 — 태양광
    fslr: 'FSLR', enph: 'ENPH',
    // 기타 빅테크
    aapl: 'AAPL', msft: 'MSFT',
  };

  const R = {};
  for (const [k, s] of Object.entries(syms)) {
    try {
      R[k] = await fetchYahoo(s);
      console.log(`  ✅ ${k.padEnd(7)} ${f2(R[k].cur).padStart(9)}  (${pct(R[k].pct)})`);
    } catch (e) {
      R[k] = null;
      console.log(`  ❌ ${k.padEnd(7)} ${e.message}`);
    }
    await new Promise(r => setTimeout(r, 400));
  }

  const vix    = R.vix?.cur;
  const dxy    = R.dxy?.cur;
  const tnx    = R.tnx?.cur;   // ^TNX: 이미 % 단위 (4.59 = 4.59%)
  const tnxBp  = R.tnx ? R.tnx.chg : null;
  const usdkrw = R.usdkrw?.cur;
  const m    = mode(vix, dxy);

  // ── wiki/dashboard.md 업데이트 ──────────────────────────────────────────
  const dashPath = path.join(BASE, 'wiki', 'dashboard.md');
  let dash = fs.readFileSync(dashPath, 'utf8');

  dash = dash.replace(/마지막 업데이트: \d{4}-\d{2}-\d{2}/, `마지막 업데이트: ${DATE}`);

  const replaceLine = (pattern, newLine) => {
    const re = new RegExp(`^${pattern.replace(/[|()]/g, '\\$&')}.*$`, 'm');
    if (re.test(dash)) dash = dash.replace(re, newLine);
  };

  replaceLine('| DXY 달러인덱스',   `| DXY 달러인덱스 | ${f1(dxy)} | ${pct(R.dxy?.pct)} | — | ${sigDXY(dxy ?? 99)} |`);
  replaceLine('| VIX 공포지수',     `| VIX 공포지수 | ${f1(vix)} | ${R.vix ? (R.vix.chg >= 0 ? '+' : '') + R.vix.chg.toFixed(1) : '—'} | — | ${sigVIX(vix ?? 20)} |`);
  replaceLine('| 10년물 금리',      `| 10년물 금리 | ${f2(tnx)}% | ${bp(tnxBp)} | — | ${sigTNX(tnxBp != null ? Math.round(tnxBp * 100) : null)} |`);
  replaceLine('| 나스닥 ',          `| 나스닥 | ${pct(R.nasdaq?.pct)} | — | ${R.nasdaq?.pct < -1 ? '🔴' : R.nasdaq?.pct > 1 ? '🟢' : '🟡'} |`);
  replaceLine('| S&P 500',          `| S&P 500 | ${pct(R.sp500?.pct)} | — | ${R.sp500?.pct < -1 ? '🔴' : '🟡'} |`);
  replaceLine('| SOX 반도체',       `| SOX 반도체 | ${pct(R.sox?.pct)} | — | ${R.sox?.pct < -2 ? '🔴 약세' : R.sox?.pct > 2 ? '🟢 강세' : '🟡'} |`);
  replaceLine('| 엔비디아',         `| 엔비디아 | ${pct(R.nvda?.pct)} | — | ${R.nvda?.pct > 2 ? '🟢' : '🟡'} |`);
  replaceLine('| 다우존스',         `| 다우존스 | ${pct(R.dow?.pct)} | — | 🟡 |`);

  ['L1 Fed 기조', 'L1 DXY\\/VIX', 'L2 미국 증시', 'L3 한국 증시'].forEach(label => {
    dash = dash.replace(new RegExp(`(${label} \\| )\\d{4}-\\d{2}-\\d{2}`), `$1${DATE}`);
  });

  fs.writeFileSync(dashPath, dash, 'utf8');

  // ── data/market_data.js 생성 (HTML에서 로드) ───────────────────────────
  const dataDir = path.join(BASE, 'data');
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir);

  const payload = {
    updated: DATE,
    vix:    { value: vix,  chg: R.vix?.chg,  signal: sigVIX(vix ?? 20) },
    dxy:    { value: dxy,  pct:  R.dxy?.pct,  signal: sigDXY(dxy ?? 99) },
    tnx:    { value: tnx,  bpChg: tnxBp != null ? Math.round(tnxBp * 100) : null, signal: sigTNX(tnxBp != null ? Math.round(tnxBp * 100) : null) },
    nasdaq: { pct: R.nasdaq?.pct },
    sp500:  { pct: R.sp500?.pct },
    dow:    { pct: R.dow?.pct },
    sox:    { pct: R.sox?.pct },
    nvda:   { pct: R.nvda?.pct },
    aapl:   { pct: R.aapl?.pct },
    msft:   { pct: R.msft?.pct },
    usdkrw: { value: usdkrw, chg: R.usdkrw?.chg },
    mode:   m,
  };

  fs.writeFileSync(
    path.join(dataDir, 'market_data.js'),
    `// 자동 생성 — ${new Date().toISOString()}\n// update_market_data.js 가 매일 07:00 KST 갱신\nvar MARKET_DATA = ${JSON.stringify(payload, null, 2)};\n`,
    'utf8'
  );

  // ── out/L1_글로벌유동성.html 마커 교체 ───────────────────────────────
  const htmlPath = path.join(BASE, 'out', 'L1_글로벌유동성.html');
  if (fs.existsSync(htmlPath)) {
    let html = fs.readFileSync(htmlPath, 'utf8');

    // 단일 값 마커 교체 함수
    const replMark = (tag, val) => {
      html = html.replace(new RegExp(`<!--${tag}-->[^<]*<!--\\/${tag}-->`), `<!--${tag}-->${val}<!--/${tag}-->`);
    };

    const krwStr  = Math.round(usdkrw ?? 1520).toLocaleString('ko-KR');
    const dxyStr  = f1(dxy ?? 99.3);
    const vixStr  = f1(vix ?? 16.7);
    const tnxStr  = f2(tnx ?? 4.56);
    const tnxBpStr = tnxBp != null ? `${tnxBp >= 0 ? '+' : ''}${Math.round(tnxBp * 100)}bp` : '';

    replMark('KRW',  krwStr);
    replMark('DXY',  dxyStr);
    replMark('VIX',  vixStr);
    replMark('TNX',  tnxStr);
    replMark('DATE', DATE);

    // data-count 속성도 업데이트 (카운트업 애니메이션용)
    html = html.replace(/(<div[^>]*data-count=")[^"]*(")/,  `$1${tnxStr}$2`);

    // DXY 게이지 포인터 위치 업데이트 (80~120 스케일)
    const dxyPct = Math.round(((dxy ?? 99) - 80) / 40 * 100);
    html = html.replace(/(class="dxy-ptr" style="left:)\d+%/, `$1${dxyPct}%`);
    html = html.replace(/(현재 )[\d.]+(?= — 달러인덱스)/, `$1${dxyStr}`);

    // VIX 구간 하이라이트 업데이트
    const vixZone = (vix ?? 16) < 15 ? 'vz1' : (vix ?? 16) < 20 ? 'vz2' : (vix ?? 16) < 25 ? 'vz3' : 'vz4';
    html = html.replace(/class="vz (vz\d)" style="border:2px solid[^"]*"/, `class="vz $1"`);
    html = html.replace(new RegExp(`class="vz ${vixZone}"`), `class="vz ${vixZone}" style="border:2px solid var(--mint);box-shadow:0 0 12px rgba(0,255,208,0.4)"`);

    // 10년물 수치 업데이트 (상세 섹션)
    html = html.replace(/(font-size:28px[^>]*>)[\d.]+%(<span[^>]*>-\d+bp)/, `$1${tnxStr}%<span style="font-size:13px;color:var(--text-sub);margin-left:8px">${tnxBpStr} 안정</span>`);

    // VIX 수치 업데이트 (상세 섹션)
    html = html.replace(/(font-size:24px[^>]*>)[\d.]+( <span[^>]*>안정 구간)/, `$1${vixStr}$2`);

    fs.writeFileSync(htmlPath, html, 'utf8');
    console.log(`   out/L1_글로벌유동성.html  업데이트됨`);
  }

  // ── wiki/L1_글로벌유동성/ 업데이트 ──────────────────────────────────────
  const L1 = p => path.join(BASE, 'wiki', 'L1_글로벌유동성', p);

  const tnxBpStr  = tnxBp != null ? `${tnxBp >= 0 ? '+' : ''}${Math.round(tnxBp * 100)}bp` : '—';
  const vixChgStr = R.vix  ? `${R.vix.chg  >= 0 ? '+' : ''}${R.vix.chg.toFixed(1)}`  : '—';
  const krwStr2   = usdkrw ? Math.round(usdkrw).toLocaleString('ko-KR') + '원' : '—';
  const krwPctStr = R.usdkrw ? pct(R.usdkrw.pct) : '—';
  const dxyPctStr = R.dxy   ? pct(R.dxy.pct)   : '—';

  const vixSig = v => !v ? '—' : v < 15 ? '🟢 안도' : v < 20 ? '🟢 안정' : v < 25 ? '🟡 주의' : v < 30 ? '🟠 불안' : '🔴 공포';
  const tnxSig = v => !v ? '—' : v < 4  ? '🟢 양호' : v < 4.5 ? '🟡 부담' : v < 5  ? '🟠 압박' : '🔴 위험';
  const dxySig = v => !v ? '—' : v < 95 ? '🟢 극약세' : v < 100 ? '🟡 약세권' : v < 103 ? '🟠 강세' : '🔴 극강세';
  const krwSig = v => !v ? '—' : v < 1350 ? '🟢 안정' : v < 1450 ? '🟡 보통' : v < 1500 ? '🟠 주의' : '🔴 이탈압력';

  // ① index.md — 현재 상태 표 특정 행 덮어쓰기
  if (fs.existsSync(L1('index.md'))) {
    let idx = fs.readFileSync(L1('index.md'), 'utf8');
    const rr = (pat, line) => { idx = idx.replace(new RegExp(`\\| ${pat}[^\\n]+`), line); };
    rr('10년물 금리',    `| 10년물 금리 | ${f2(tnx)}% | ${tnxBpStr} | ${tnxSig(tnx)} | ${DATE} |`);
    rr('DXY 달러인덱스', `| DXY 달러인덱스 | ${f1(dxy)} | ${dxyPctStr} | ${dxySig(dxy)} | ${DATE} |`);
    rr('VIX 공포지수',   `| VIX 공포지수 | ${f1(vix)} | ${vixChgStr} | ${vixSig(vix)} | ${DATE} |`);
    rr('원달러 환율',    `| 원달러 환율 | ${krwStr2} | ${krwPctStr} | ${krwSig(usdkrw)} | ${DATE} |`);
    idx = idx.replace(/## 한줄 요약 \(\d{4}-\d{2}-\d{2}\)\n>[^\n]+/,
      `## 한줄 요약 (${DATE})\n> **VIX ${f1(vix)}·DXY ${f1(dxy)} ${m.name}. 원달러 ${krwStr2}·Hawkish 연준·점도표 인하 5명뿐 — 실적+수출 섹터 선별 장세.**`);
    fs.writeFileSync(L1('index.md'), idx, 'utf8');
  }

  // ② fed_watch.md — 일일 추적 행 추가
  if (fs.existsSync(L1('fed_watch.md'))) {
    let fed = fs.readFileSync(L1('fed_watch.md'), 'utf8');
    const fedRow = `| ${DATE} | — | ${f2(tnx)}% | — | ${f1(dxy)} | ${f1(vix)} | ${m.icon} ${m.name} |`;
    fed = appendTableRow(fed, '2년물 | 10년물 | 스프레드 (10Y-2Y)', fedRow, 7);
    fs.writeFileSync(L1('fed_watch.md'), fed, 'utf8');
  }

  // ③ market_vix.md — 현재 상태 덮어쓰기 + 일일 추적 행 추가
  if (fs.existsSync(L1('market_vix.md'))) {
    let vmd = fs.readFileSync(L1('market_vix.md'), 'utf8');
    vmd = vmd.replace(/\| VIX 공포지수 \|[^\n]+/, `| VIX 공포지수 | ${f1(vix)} | ${vixChgStr} | ${vixSig(vix)} |`);
    const vixRow = `| ${DATE} | ${f1(vix)} | ${vixChgStr} | — | ${vixSig(vix)} |`;
    vmd = appendTableRow(vmd, '날짜 | VIX | 전일 대비', vixRow, 7);
    fs.writeFileSync(L1('market_vix.md'), vmd, 'utf8');
  }

  // ④ market_채권금리.md — 현재 상태 덮어쓰기 + 일일 추적 행 추가
  if (fs.existsSync(L1('market_채권금리.md'))) {
    let bmd = fs.readFileSync(L1('market_채권금리.md'), 'utf8');
    bmd = bmd.replace(/\| 10년물 국채금리 \|[^\n]+/, `| 10년물 국채금리 | ${f2(tnx)}% | ${tnxBpStr} | ${tnxSig(tnx)} |`);
    const bondRow = `| ${DATE} | ${f2(tnx)}% | — | — | — | ${tnxSig(tnx)} |`;
    bmd = appendTableRow(bmd, '날짜 | 10년물 | 2년물 | 스프레드', bondRow, 7);
    fs.writeFileSync(L1('market_채권금리.md'), bmd, 'utf8');
  }

  // ⑤ market_달러_환율_흐름.md — 현재 상태 덮어쓰기 + 일일 추적 행 추가
  if (fs.existsSync(L1('market_달러_환율_흐름.md'))) {
    let fmd = fs.readFileSync(L1('market_달러_환율_흐름.md'), 'utf8');
    fmd = fmd.replace(/\| DXY 달러인덱스 \|[^\n]+/, `| DXY 달러인덱스 | ${f1(dxy)} | ${dxyPctStr} | ${dxySig(dxy)} |`);
    fmd = fmd.replace(/\| 원달러 환율 \|[^\n]+/, `| 원달러 환율 | ${krwStr2} | ${krwPctStr} | ${krwSig(usdkrw)} |`);
    const fxRow = `| ${DATE} | ${krwStr2} | ${krwSig(usdkrw)} | ${f1(dxy)} | ${dxySig(dxy)} |`;
    fmd = appendTableRow(fmd, '날짜 | 원달러 | 원달러신호', fxRow, 7);
    fs.writeFileSync(L1('market_달러_환율_흐름.md'), fmd, 'utf8');
  }

  console.log(`   wiki/L1_글로벌유동성/ (5개 파일)  업데이트됨`);

  // ── wiki/L2_미국시장/ 업데이트 ─────────────────────────────────────────
  const L2 = p => path.join(BASE, 'wiki', 'L2_미국시장', p);

  const sigIndex = pct => pct == null ? '—' : pct > 1 ? '🔴 강세' : pct > 0 ? '🟢 상승' : pct > -1 ? '🟠 하락' : '🔴 약세';
  const sigPair  = pct => pct == null ? '수집 대기' : pct > 2 ? '🔴 강세 — 한국 수혜 기대' : pct > 0 ? '🟢 상승' : pct < -2 ? '🔴 약세 — 한국 동반 주의' : '🟡 중립';

  // ① index.md — 현재 상태 표 덮어쓰기
  if (fs.existsSync(L2('index.md'))) {
    let idx2 = fs.readFileSync(L2('index.md'), 'utf8');
    const rr2 = (pat, line) => { idx2 = idx2.replace(new RegExp(`\\| ${pat}[^\\n]+`), line); };
    rr2('나스닥',       `| 나스닥 | ${R.nasdaq ? f2(R.nasdaq.cur) : '—'} | ${pct(R.nasdaq?.pct)} | ${sigIndex(R.nasdaq?.pct)} |`);
    rr2('S&P 500',     `| S&P 500 | ${R.sp500 ? f2(R.sp500.cur) : '—'} | ${pct(R.sp500?.pct)} | ${sigIndex(R.sp500?.pct)} |`);
    rr2('SOX 반도체',  `| SOX 반도체 | ${R.sox ? f2(R.sox.cur) : '—'} | ${pct(R.sox?.pct)} | ${sigIndex(R.sox?.pct)} |`);
    rr2('NVDA',        `| NVDA (AI반도체) | ${R.nvda ? f2(R.nvda.cur) : '—'} | ${pct(R.nvda?.pct)} | ${sigPair(R.nvda?.pct)} |`);
    rr2('MU',          `| MU (메모리) | ${R.mu ? f2(R.mu.cur) : '—'} | ${pct(R.mu?.pct)} | ${sigPair(R.mu?.pct)} |`);
    rr2('ETN',         `| ETN (전력인프라) | ${R.etn ? f2(R.etn.cur) : '—'} | ${pct(R.etn?.pct)} | ${sigPair(R.etn?.pct)} |`);
    rr2('마지막업데이트', `| 마지막업데이트 | ${DATE} | — | — |`);
    idx2 = idx2.replace(/## 한줄 요약 \(\d{4}-\d{2}-\d{2}\)\n>[^\n]+/,
      `## 한줄 요약 (${DATE})\n> **NVDA ${pct(R.nvda?.pct)} | SOX ${pct(R.sox?.pct)} | 나스닥 ${pct(R.nasdaq?.pct)}. ${(R.nvda?.pct ?? 0) > 1 ? 'AI반도체 강세 — SK하이닉스 수혜 기대.' : 'AI반도체 중립 — 페어 관망.'}**`);
    fs.writeFileSync(L2('index.md'), idx2, 'utf8');
  }

  // ② market_미국지수.md — 현재 상태 + 일일 추적 추가
  if (fs.existsSync(L2('market_미국지수.md'))) {
    let jmd = fs.readFileSync(L2('market_미국지수.md'), 'utf8');
    const rr3 = (pat, line) => { jmd = jmd.replace(new RegExp(`\\| ${pat}[^\\n]+`), line); };
    rr3('나스닥 \\(IXIC\\)', `| 나스닥 (IXIC) | ${R.nasdaq ? f2(R.nasdaq.cur) : '—'} | ${pct(R.nasdaq?.pct)} | — | ${sigIndex(R.nasdaq?.pct)} |`);
    rr3('S&P 500',           `| S&P 500 | ${R.sp500 ? f2(R.sp500.cur) : '—'} | ${pct(R.sp500?.pct)} | — | ${sigIndex(R.sp500?.pct)} |`);
    rr3('다우존스',           `| 다우존스 | ${R.dow ? f2(R.dow.cur) : '—'} | ${pct(R.dow?.pct)} | — | ${sigIndex(R.dow?.pct)} |`);
    rr3('SOX 반도체',        `| SOX 반도체 | ${R.sox ? f2(R.sox.cur) : '—'} | ${pct(R.sox?.pct)} | — | ${sigIndex(R.sox?.pct)} |`);
    rr3('SMH',               `| SMH | 반도체 | ${R.smh ? f2(R.smh.cur) : '—'} | ${pct(R.smh?.pct)} | ${sigIndex(R.smh?.pct)} |`);
    rr3('QQQ',               `| QQQ | 나스닥100 | ${R.qqq ? f2(R.qqq.cur) : '—'} | ${pct(R.qqq?.pct)} | ${sigIndex(R.qqq?.pct)} |`);
    rr3('XLK',               `| XLK | 기술 | ${R.xlk ? f2(R.xlk.cur) : '—'} | ${pct(R.xlk?.pct)} | ${sigIndex(R.xlk?.pct)} |`);
    rr3('XLI',               `| XLI | 산업재 | ${R.xli ? f2(R.xli.cur) : '—'} | ${pct(R.xli?.pct)} | ${sigIndex(R.xli?.pct)} |`);
    rr3('XLV',               `| XLV | 헬스케어 | ${R.xlv ? f2(R.xlv.cur) : '—'} | ${pct(R.xlv?.pct)} | ${sigIndex(R.xlv?.pct)} |`);

    // 빅테크 페어 일일 추적 행 추가
    const pairRow = `| ${DATE} | ${pct(R.nvda?.pct)} | ${pct(R.mu?.pct)} | ${pct(R.amat?.pct)} | ${pct(R.lrcx?.pct)} | ${pct(R.mrvl?.pct)} | ${pct(R.etn?.pct)} | ${pct(R.vrt?.pct)} | ${pct(R.lly?.pct)} | ${pct(R.tsla?.pct)} | ${pct(R.ionq?.pct)} | ${pct(R.be?.pct)} | ${pct(R.fslr?.pct)} |`;
    jmd = appendTableRow(jmd, '날짜 | NVDA | MU | AMAT | LRCX | MRVL | ETN | VRT | LLY | TSLA | IONQ | BE | FSLR', pairRow, 7);

    // 지수 일일 추적 행 추가
    const modeStr = m.icon + ' ' + m.name;
    const idxRow = `| ${DATE} | ${pct(R.nasdaq?.pct)} | ${pct(R.sp500?.pct)} | ${pct(R.sox?.pct)} | ${pct(R.smh?.pct)} | ${modeStr} | ${sigIndex(R.nasdaq?.pct)} |`;
    jmd = appendTableRow(jmd, '날짜 | 나스닥% | S&P% | SOX% | SMH%', idxRow, 7);

    fs.writeFileSync(L2('market_미국지수.md'), jmd, 'utf8');
  }

  console.log(`   wiki/L2_미국시장/ (2개 파일)  업데이트됨`);

  // ── out/L2_미국시장.html 마커 교체 ────────────────────────────────────
  const html2Path = path.join(BASE, 'out', 'L2_미국시장.html');
  if (fs.existsSync(html2Path)) {
    let h2 = fs.readFileSync(html2Path, 'utf8');

    const rm = (tag, val) => {
      h2 = h2.replace(new RegExp(`<!--${tag}-->[\\s\\S]*?<!--\\/${tag}-->`, 'g'), `<!--${tag}-->${val}<!--/${tag}-->`);
    };
    const cls = v => (v == null ? 'neu' : v > 0 ? 'up' : v < 0 ? 'dn' : 'neu');
    const ps  = v => (v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2) + '%');
    const pairSig = (ticker, pv) => pv == null ? '중립' : pv > 2 ? `${ticker} 강세 — 한국 수혜 기대` : pv < -2 ? `${ticker} 약세 — 동반 주의` : '중립 대기';

    rm('DATE',  DATE); rm('DATE2', DATE);

    // 지수
    rm('NASDAQ_VAL', R.nasdaq ? Math.round(R.nasdaq.cur).toLocaleString() : '—');
    rm('NASDAQ_PCT', ps(R.nasdaq?.pct)); rm('NASDAQ_CLS', cls(R.nasdaq?.pct));
    rm('SP500_VAL',  R.sp500  ? Math.round(R.sp500.cur).toLocaleString()  : '—');
    rm('SP500_PCT',  ps(R.sp500?.pct));  rm('SP500_CLS',  cls(R.sp500?.pct));
    rm('SOX_VAL',   R.sox   ? Math.round(R.sox.cur).toLocaleString()    : '—');
    rm('SOX_PCT',   ps(R.sox?.pct));    rm('SOX_CLS',   cls(R.sox?.pct));
    rm('DOW_VAL',   R.dow   ? Math.round(R.dow.cur).toLocaleString()    : '—');
    rm('DOW_PCT',   ps(R.dow?.pct));    rm('DOW_CLS',   cls(R.dow?.pct));

    // ETF
    rm('SMH_PCT', ps(R.smh?.pct));  rm('SMH_CLS', cls(R.smh?.pct));
    rm('QQQ_PCT', ps(R.qqq?.pct));  rm('QQQ_CLS', cls(R.qqq?.pct));
    rm('XLK_PCT', ps(R.xlk?.pct));  rm('XLK_CLS', cls(R.xlk?.pct));
    rm('XLI_PCT', ps(R.xli?.pct));  rm('XLI_CLS', cls(R.xli?.pct));
    rm('XLV_PCT', ps(R.xlv?.pct));  rm('XLV_CLS', cls(R.xlv?.pct));

    // 페어 종목
    const pairs = ['NVDA','AMD','AVGO','MU','AMAT','LRCX','MRVL','RKLB','LMT','ETN','VRT','LLY','NVO','TSLA','IONQ','QBTS','BE','FSLR','ENPH'];
    for (const t of pairs) {
      const k = t.toLowerCase();
      rm(`${t}_PCT`, ps(R[k]?.pct)); rm(`${t}_CLS`, cls(R[k]?.pct));
    }

    // 페어 시그널 (카드 상단 sig 뱃지)
    rm('NVDA_SIG', (R.nvda?.pct ?? 0) > 2 ? 'NVDA 강세 — HBM 수혜' : (R.nvda?.pct ?? 0) < -2 ? 'NVDA 약세 — 주의' : '중립 대기');
    rm('MU_SIG',   (R.mu?.pct   ?? 0) > 2 ? 'MU 강세 — DRAM 수혜'  : '중립 대기');
    rm('AMAT_SIG', (R.amat?.pct ?? 0) > 2 ? 'AMAT 강세 — 장비 수혜' : '중립');
    rm('MRVL_SIG', (R.mrvl?.pct ?? 0) > 2 ? 'MRVL 강세 — 기판 수혜' : '중립');
    rm('RKLB_SIG', (R.rklb?.pct ?? 0) > 2 ? 'RKLB 강세 — 위성 수혜' : '중립');
    rm('ETN_SIG',  (R.etn?.pct  ?? 0) > 2 ? 'ETN 강세 — 전력 수혜'  : '중립');
    rm('LLY_SIG',  (R.lly?.pct  ?? 0) > 2 ? 'LLY 강세 — CMO 수혜'  : '중립');
    rm('TSLA_SIG', (R.tsla?.pct ?? 0) > 2 ? 'TSLA 강세 — 배터리 수혜' : '중립');
    rm('IONQ_SIG', (R.ionq?.pct ?? 0) > 2 ? 'IONQ 강세 — 양자 수혜' : '중립');
    rm('BE_SIG',   (R.be?.pct   ?? 0) > 2 ? 'BE 강세 — 연료전지 수혜' : '중립');
    rm('FSLR_SIG', (R.fslr?.pct ?? 0) > 2 ? 'FSLR 강세 — 태양광 수혜' : '중립');

    fs.writeFileSync(html2Path, h2, 'utf8');
    console.log(`   out/L2_미국시장.html  업데이트됨`);
  }

  // ── wiki/log.md 업데이트 ──────────────────────────────────────────────
  const logPath = path.join(BASE, 'wiki', 'log.md');
  const existing = fs.existsSync(logPath) ? fs.readFileSync(logPath, 'utf8') : '';
  const entry = `## ${DATE}\n- [07:00] 자동 수집 ✅\n- VIX ${f1(vix)} | DXY ${f1(dxy)} | 10yr ${f2(tnx)}% | 원달러 ${Math.round(usdkrw ?? 0).toLocaleString('ko-KR')}원\n- Nasdaq ${pct(R.nasdaq?.pct)} | SOX ${pct(R.sox?.pct)} | NVDA ${pct(R.nvda?.pct)}\n- 유동성 모드: ${m.icon} ${m.name} → 코스피 ${m.kospI} ${m.kosp}\n\n`;
  fs.writeFileSync(logPath, entry + existing, 'utf8');

  console.log(`\n✅ 완료: ${DATE} | ${m.icon} ${m.name} | 코스피 ${m.kospI} ${m.kosp}`);
  console.log(`   wiki/dashboard.md  wiki/log.md  data/market_data.js  out/L1_글로벌유동성.html  업데이트됨\n`);
}

main().catch(e => { console.error('❌ 오류:', e.message); process.exit(1); });
