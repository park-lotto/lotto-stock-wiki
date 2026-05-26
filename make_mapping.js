const XLSX = require('./node_modules/xlsx/xlsx.js');

// ── 데이터 ──────────────────────────────────────────────
const themes = [
  {
    rank: 1, theme: 'AI 반도체·HBM', sub: 'HBM / 파운드리 / 후공정',
    strength: '🔴 높음', etf: 'SOXX, SMH',
    us: 'NVDA, AVGO, MRVL, MU, AMD',
    kr: ['SK하이닉스', '한미반도체', 'HPSP', '리노공업', '이오테크닉스'],
    note: '미국 신고가 → 국내 1~2일 시차 수급 유입 패턴'
  },
  {
    rank: 2, theme: 'AI 인프라·전력', sub: '데이터센터 건설 / 전력기기',
    strength: '🟡 보통', etf: 'GRID, XLU',
    us: 'STRL, VRT, ETN, EATON',
    kr: ['효성중공업', 'LS ELECTRIC', '두산에너빌리티', '산일전기', '일진전기'],
    note: '테마 공명 수준 — 공급망 직접 연결 아님. 수급 선행 여부 확인 후 진입'
  },
  {
    rank: 3, theme: 'AI 소프트웨어·플랫폼', sub: '빅테크 / 클라우드 / LLM',
    strength: '🟡 보통', etf: 'QQQ, IGV',
    us: 'GOOGL, MSFT, META, AMZN',
    kr: ['크래프톤', '네이버', '카카오', '더존비즈온', ''],
    note: '국내는 개별 실적 모멘텀 선(先) 확인 필수'
  },
  {
    rank: 4, theme: '바이오·제약', sub: '항암제 / GLP-1 / 바이오시밀러',
    strength: '🟡 보통', etf: 'XBI, IBB',
    us: 'LLY, NVO, MRNA, REGN',
    kr: ['삼성바이오로직스', '셀트리온', '알테오젠', '유한양행', '한미약품'],
    note: '임상 이벤트 주도 — 미국 강세 종목과 파이프라인 유사성 확인'
  },
  {
    rank: 5, theme: '방산·우주', sub: '방위산업 / 위성 / 드론',
    strength: '🔴 높음', etf: 'ITA, XAR',
    us: 'LMT, RTX, GD, PLTR',
    kr: ['한화에어로스페이스', '한화시스템', 'LIG넥스원', '현대로템', 'KAI'],
    note: '지정학 리스크 발생 시 연결강도 즉시 높음으로 격상'
  },
  {
    rank: 6, theme: '에너지·정유', sub: '원유 / 천연가스 / 정제마진',
    strength: '🔴 높음', etf: 'XLE, USO',
    us: 'XOM, CVX, COP, OXY',
    kr: ['S-Oil', 'SK이노베이션', 'GS', 'HD현대오일뱅크', ''],
    note: '유가 급등 시 당일 수급 직결. 정제마진 방향 함께 확인'
  },
  {
    rank: 7, theme: '해운·물류', sub: '컨테이너 / 벌크 / LNG선',
    strength: '🟡 보통', etf: 'SHIP, BDRY',
    us: 'ZIM, MATX, DAC',
    kr: ['HMM', '팬오션', '대한해운', 'KSS해운', ''],
    note: '호르무즈·수에즈 등 항로 이슈 발생 시 높음으로 격상'
  },
  {
    rank: 8, theme: '전기차·배터리', sub: 'EV / 배터리셀 / 소재',
    strength: '🟡 보통', etf: 'LIT, DRIV, BATT',
    us: 'TSLA, F, GM, RIVN',
    kr: ['LG에너지솔루션', '삼성SDI', 'SK이노베이션', '에코프로', '포스코퓨처엠'],
    note: 'TSLA 실적·가이던스 발표일 전후 연결강도 급등 패턴'
  },
  {
    rank: 9, theme: '클라우드·사이버보안', sub: 'SaaS / 제로트러스트 / EDR',
    strength: '🟢 낮음', etf: 'BUG, CIBR, WCLD',
    us: 'CRWD, PANW, FTNT, ZS',
    kr: ['윈스', '파수', 'SK쉴더스(비상장)', '', ''],
    note: '국내 시장 규모 작음 — 대형 해킹 이벤트 발생 시 단기 급등 패턴'
  },
  {
    rank: 10, theme: '로보틱스·드론', sub: '산업용 로봇 / 자율주행 드론',
    strength: '🟢 낮음', etf: 'ROBT, IRBO',
    us: 'ISRG, ABB, FANUC',
    kr: ['두산로보틱스', '레인보우로보틱스', '한화시스템', '', ''],
    note: '테마 초기 단계 — 정책 이벤트(드론 규제 완화 등) 발생 시 단기 수급'
  },
  {
    rank: 11, theme: '금융·핀테크', sub: '투자은행 / 금리 수혜 / 결제',
    strength: '🟢 낮음', etf: 'XLF, FINX',
    us: 'JPM, GS, BAC, V, MA',
    kr: ['KB금융', '신한지주', '카카오뱅크', '', ''],
    note: '미국 금리 방향 변화 시 연결강도 변동. 국내 은행주는 환율 동시 확인'
  },
  {
    rank: 12, theme: '소비재·명품·리테일', sub: '명품 / 스포츠 / 이커머스',
    strength: '🟢 낮음', etf: 'XLY, CNYA',
    us: 'AMZN, NKE, LVMH, TJX',
    kr: ['F&F', '한섬', '이마트', '신세계', ''],
    note: '미국 소비 강세 → 국내 연결 약함. 중국 소비 회복 테마와 함께 볼 것'
  },
];

// ── 워크북 생성 ────────────────────────────────────────
const wb = XLSX.utils.book_new();

// ── Sheet 1: 테마_종목매핑 ─────────────────────────────
const headers = [
  '순위', '미국장 테마명', '서브카테고리', '연결강도',
  '관련 ETF', '미국 대표종목',
  '국내 종목 1', '국내 종목 2', '국내 종목 3', '국내 종목 4', '국내 종목 5',
  '메모 / 조건부 격상 기준'
];

const rows = [headers];
themes.forEach(t => {
  rows.push([
    t.rank, t.theme, t.sub, t.strength,
    t.etf, t.us,
    t.kr[0] || '', t.kr[1] || '', t.kr[2] || '', t.kr[3] || '', t.kr[4] || '',
    t.note
  ]);
});

const ws1 = XLSX.utils.aoa_to_sheet(rows);

// 열 너비
ws1['!cols'] = [
  { wch: 5  }, // 순위
  { wch: 20 }, // 테마명
  { wch: 22 }, // 서브카테고리
  { wch: 10 }, // 연결강도
  { wch: 16 }, // ETF
  { wch: 26 }, // 미국종목
  { wch: 16 }, // 국내1
  { wch: 16 }, // 국내2
  { wch: 16 }, // 국내3
  { wch: 16 }, // 국내4
  { wch: 16 }, // 국내5
  { wch: 42 }, // 메모
];

// 행 높이
ws1['!rows'] = [{ hpt: 22 }]; // 헤더 행
themes.forEach(() => ws1['!rows'].push({ hpt: 18 }));

XLSX.utils.book_append_sheet(wb, ws1, '테마_종목매핑');

// ── Sheet 2: 일일_수급데이터_입력 ───────────────────────
const supplyHeaders = [
  '날짜', '외국인순매수_1위', '외국인순매수_2위', '외국인순매수_3위',
  '외국인순매수_4위', '외국인순매수_5위',
  '기관순매수_1위', '기관순매수_2위', '기관순매수_3위',
  'SOX등락률', '달러인덱스', '원달러환율', '나스닥선물', '메모'
];

const supplyGuide = [
  supplyHeaders,
  [
    '← 날짜 입력', 'HTS 외국인 순매수 탭에서', '상위 5종목 복붙', '', '', '',
    'HTS 기관 순매수 탭에서', '상위 3종목', '',
    'investing.com', 'investing.com', 'investing.com', 'investing.com', '특이사항'
  ],
  ['2026-05-06', 'SK하이닉스', '삼성전자', '한미반도체', '', '', '효성중공업', 'LS ELECTRIC', '', '+1.8%', '99.2', '1,380', '+0.5%', '샘플 데이터'],
];

const ws2 = XLSX.utils.aoa_to_sheet(supplyGuide);
ws2['!cols'] = [
  { wch: 12 }, // 날짜
  { wch: 16 }, { wch: 16 }, { wch: 16 }, { wch: 16 }, { wch: 16 }, // 외국인
  { wch: 16 }, { wch: 16 }, { wch: 16 }, // 기관
  { wch: 10 }, { wch: 12 }, { wch: 12 }, { wch: 12 }, // 지표
  { wch: 30 }, // 메모
];

XLSX.utils.book_append_sheet(wb, ws2, '일일_수급데이터_입력');

// ── Sheet 3: 사용방법 ─────────────────────────────────
const guide = [
  ['로또의 주식 — 테마 × 종목 매핑표 사용방법'],
  [''],
  ['【 테마_종목매핑 시트 】'],
  ['• 연결강도 범례:', '🔴 높음 = 미국 강세 당일~익일 국내 동반 상승 70%↑, 공급망 직결'],
  ['', '🟡 보통 = 1~2일 시차 반응, 간접 수혜 또는 테마 공명'],
  ['', '🟢 낮음 = 테마 연관은 있으나 국내 개별 모멘텀 필요'],
  [''],
  ['• 수정 방법:', '국내 종목 1~5 열에 직접 종목명 입력/수정'],
  ['', '연결강도는 시장 상황 변화에 따라 수시 업데이트 권장'],
  ['', '메모 열에 조건부 격상 기준 기록 (예: 유가 $90↑ 시 에너지 높음)'],
  [''],
  ['【 일일_수급데이터_입력 시트 】'],
  ['• 매일 아침 장 시작 전 (6:30~7:00) 입력 권장'],
  ['• 외국인/기관 순매수: HTS → 당일 순매수 상위 탭 → 종목명 복붙'],
  ['• SOX / 달러인덱스 / 원달러 / 나스닥선물: investing.com 에서 확인'],
  [''],
  ['【 Claude 활용법 】'],
  ['• 이 파일을 raw/ 폴더에 저장 후:'],
  ['  → "raw/테마_종목매핑표.xlsx 보고 오늘 리포트 만들어줘"'],
  ['  → Claude가 매핑표 기반으로 국내 종목을 정확하게 연결함'],
  [''],
  ['마지막 업데이트: 2026-05-06 | 로또의 주식'],
];

const ws3 = XLSX.utils.aoa_to_sheet(guide);
ws3['!cols'] = [{ wch: 35 }, { wch: 60 }];
ws3['!merges'] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 1 } }];

XLSX.utils.book_append_sheet(wb, ws3, '사용방법');

// ── 저장 ─────────────────────────────────────────────
const outPath = 'raw/테마_종목매핑표.xlsx';
XLSX.writeFile(wb, outPath);
console.log('생성 완료:', outPath);
