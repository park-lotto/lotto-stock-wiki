// 숏템하우스 2편 — 디자인 시스템 (2026-08-20)
// 규칙 0: 검정 배경 단독 금지. 모든 카드는 "돌아가는 영상" 위에 얹힌다.
export const C = {
  ink:      '#0b0d10',   // 가장 어두운 바닥(배경 위 딤용)
  paper:    '#e9edf2',   // 기본 글자
  dim:      '#8b97a8',   // 보조 글자
  gold:     '#facc15',   // ★강조 1 — 핵심 수치·키워드
  goldSoft: 'rgba(250,204,21,0.14)',
  green:    '#4ade80',   // 강조 2 — 긍정·결과
  red:      '#f87171',   // 강조 3 — 문제·부정
  line:     'rgba(255,255,255,0.14)',
} as const;

export const F = {
  sans: '"Noto Sans KR", Pretendard, sans-serif',
  mono: '"Space Mono", monospace',
} as const;

export const V = { width: 1920, height: 1080, fps: 30 } as const;

// 배경 처리 강도 — 여기 한 곳에서만 정한다(두 벌 금지)
export const BG = {
  brightness: 0.40,   // 밝기
  blur: 6,            // px
  zoomFrom: 1.04,
  zoomTo: 1.12,
  dimWhenCard: 0.62,  // 카드 뜰 때 추가로 눌러주는 비율
} as const;

export const sec = (s: number) => Math.round(s * V.fps);
