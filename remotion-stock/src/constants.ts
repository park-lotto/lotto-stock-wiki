export const C = {
  bg:           '#000000',
  cardBg:       '#111111',
  cardBgActive: '#0A1F1A',
  main:         '#00FFD0',
  mainMid:      '#00BF9A',
  mainDark:     '#003D31',
  mainLight:    '#80FFE8',
  textPrimary:  '#FFFFFF',
  textSub:      '#888888',
  borderActive: '#00FFD0',
  borderSub:    '#1A3D35',
  dataUp:       '#FF4336',
  dataDown:     '#2196F3',
} as const;

export const GLOW = {
  weak: {
    text:   '0 0 6px rgba(0,255,208,0.6)',
    box:    '0 0 8px rgba(0,255,208,0.3)',
    filter: 'drop-shadow(0 0 4px rgba(0,255,208,0.4))',
  },
  mid: {
    text:   '0 0 8px #00FFD0, 0 0 20px rgba(0,255,208,0.6), 0 0 40px rgba(0,191,154,0.4)',
    box:    '0 0 12px rgba(0,255,208,0.8), 0 0 30px rgba(0,255,208,0.3)',
    filter: 'drop-shadow(0 0 8px #00FFD0)',
  },
  strong: {
    text:   '0 0 8px #00FFD0, 0 0 20px #00FFD0, 0 0 40px #00FFD0, 0 0 80px #00BF9A',
    box:    '0 0 20px rgba(0,255,208,1.0), 0 0 60px rgba(0,255,208,0.5)',
    filter: 'drop-shadow(0 0 12px #00FFD0) drop-shadow(0 0 30px rgba(0,191,154,0.5))',
  },
} as const;

export const GRAD = {
  vertical:   'linear-gradient(180deg, #00FFD0 0%, #00BF9A 50%, #003D31 100%)',
  fade:       'linear-gradient(180deg, #00FFD0 0%, rgba(0,255,208,0) 100%)',
  horizontal: 'linear-gradient(90deg, #00BF9A 0%, #00FFD0 50%, #80FFE8 100%)',
  premium:    'linear-gradient(135deg, #003D31 0%, #00FFD0 40%, #80FFE8 70%, #00BF9A 100%)',
} as const;

export const FONT = '"Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif';
export const SDUR = 180; // 6초 × 30fps = 180프레임
