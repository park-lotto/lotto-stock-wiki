export const COLORS = {
  bg: '#0F112A',
  text: '#FFFFFF',
  textDim: 'rgba(255,255,255,0.45)',
  mint: 'rgb(0, 255, 200)',
  orange: 'rgb(255, 128, 0)',
  bull: 'rgb(255, 67, 54)',
  bear: 'rgb(33, 150, 243)',
  grid: 'rgba(255,255,255,0.06)',
  card: 'rgba(255,255,255,0.07)',
} as const;

export const FONT = {
  main: 'Roboto, sans-serif',
  mono: '"Roboto Mono", monospace',
} as const;

// 쇼츠 포맷 기준 (9:16)
export const VIDEO = {
  width: 1080,
  height: 1920,
  fps: 30,
  duration: 300, // 10초
} as const;

// 스테이지 프레임 경계
export const STAGE = {
  s1Start: 0,
  s1End: 90,   // 0~3초: 도입
  s2End: 210,  // 3~7초: 분석
  s3End: 300,  // 7~10초: 결론
} as const;
